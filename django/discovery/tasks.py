"""Background tasks for the Discovery platform (django-tasks).

Each task dispatches to a service, mirrors its result/progress into the default
cache under ``set_job_cache``, and returns its result (persisted by the
django-tasks-db backend as the source of truth for terminal status).

Celery's ``link=`` chaining has no django-tasks equivalent, so chains are
expressed by enqueuing the successor at the end of the predecessor (guarded by
a ``then_*`` flag where the task is also runnable on its own).

Tasks are plain ``@task`` callables (no ``takes_context``) so they run
identically under ``.enqueue()`` (worker) and ``.call()`` (synchronous, used by
``--sync`` management commands and tests). The diagnostic progress/result cache
is keyed on a generated id; final status is owned by the django-tasks-db result.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from django_tasks import task

from discovery.cache_utils import set_job_cache

log = logging.getLogger(__name__)

KEYWORD_TTL = 300  # 5 minutes
CHEMICAL_QUERY_TTL = 3_600  # 1 hour


@task()
def keyword_resolve(search_key: str, keyword: str) -> bool:
    """Resolve a landing-page keyword to a dashboard filter and cache the redirect URL."""
    task_id = uuid4().hex
    set_job_cache(search_key=search_key, task_id=task_id, timeout=KEYWORD_TTL)

    from discovery.services.keyword_resolver import resolve_keyword

    result = resolve_keyword(keyword)

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=KEYWORD_TTL,
    )
    log.info(
        "Keyword resolved: %r → %s (task %s)",
        keyword,
        result.get("match_type"),
        task_id,
    )
    return True


@task(queue_name="scores")
def recompute_scores_task() -> bool:
    """Recompute all discovery scores (novelty, assembly, GCF, catalogs, UMAP)."""
    from discovery.services.scores import recompute_all_scores

    recompute_all_scores()
    log.info("Score recomputation complete (task %s)", uuid4().hex)
    return True


@task()
def chemical_similarity_search(
    smiles: str, similarity_threshold: float
) -> dict[int, float]:
    """Compute ChemOnt ontology-based semantic similarity of a SMILES query.

    Thin task wrapper over ``discovery.services.query.run_chemical_search`` —
    the canonical resolver shared with the combined multi-criterion query.
    Returns ``{ibgc_id: similarity_score}``; raises if the IC cache is missing
    or ClassyFire is unreachable so the failure is visible to the operator.
    """
    from discovery.services.query import run_chemical_search

    return run_chemical_search(smiles, similarity_threshold)


@task()
def combined_query(criteria: list[dict], filters: dict | None = None) -> dict:
    """Resolve a combined multi-criterion query (AND intersection of criteria).

    Thin task wrapper over ``discovery.services.query.run_combined_query`` — it
    resolves every scoring criterion, intersects their iBGC id sets, narrows by
    the supplied filters, and returns the serialisable result dict the
    ``/query/combined/status`` + ``/scores`` endpoints render. Runs on the
    default (worker) queue so it has access to phmmer, rdkit and the scoring
    cache the individual criteria need.
    """
    from discovery.services.query import run_combined_query

    return run_combined_query(criteria, filters or {})


SEQUENCE_QUERY_TTL = 3_600  # 1 hour
COMBINED_QUERY_TTL = 3_600  # 1 hour
CLUSTERING_TTL = 86_400  # 24 hours


# ── Integrated BGC table builder ───────────────────────────────────────────


@task()
def build_integrated_bgcs_task(
    *,
    then_update_stats: bool = False,
    then_run_clustering: dict | None = None,
    stats_queue: str = "default",
    clustering_queue: str = "scores",
) -> dict:
    """Rebuild the IntegratedBgc table from latest-version SourceBgcPrediction rows.

    On success, optionally enqueues a follow-up: ``then_run_clustering`` (a kwargs
    dict) chains ``run_bgc_clustering_task``; otherwise ``then_update_stats``
    chains ``update_discovery_stats_task``. Chaining on success (vs dispatching
    both up front) preserves the old Celery ``link=`` ordering — the clustering
    task must not capture iBGC ids before the rebuild recreates them.
    """
    task_id = uuid4().hex
    search_key = "integrated_bgcs"
    set_job_cache(search_key=search_key, task_id=task_id, timeout=CLUSTERING_TTL)

    from discovery.services.clustering.integrated import build_integrated_bgcs

    def _progress(phase: str, processed: int, total: int) -> None:
        set_job_cache(
            search_key=search_key,
            results={"phase": phase, "processed": processed, "total": total},
            task_id=task_id,
            timeout=CLUSTERING_TTL,
        )

    result = build_integrated_bgcs(progress_cb=_progress)
    set_job_cache(
        search_key=search_key,
        results={**result, "phase": "complete"},
        task_id=task_id,
        timeout=CLUSTERING_TTL,
    )
    if then_run_clustering is not None:
        run_bgc_clustering_task.using(queue_name=clustering_queue).enqueue(
            **then_run_clustering
        )
    elif then_update_stats:
        update_discovery_stats_task.using(queue_name=stats_queue).enqueue()
    log.info("build_integrated_bgcs complete (task %s): %s", task_id, result)
    return result


# ── BGC clustering pipeline ───────────────────────────────────────────────────


@task(queue_name="scores")
def run_bgc_clustering_task(
    *,
    domain_sources: list[str] | None = None,
    score_weights: list[float] | None = None,
    knn_k: int | None = None,
    leiden_resolutions: list[float] | tuple[float, ...] | None = None,
    seed: int = 42,
    apply: bool = False,
    auto_reclassify: bool = True,
    reclassify_scope: str = "all_non_primary",
    score_ibgcs: bool = True,
) -> dict:
    """Domain+adjacency hierarchical-CPM-Leiden clustering over iBGCs.

    Runs the orchestrator in ``services.clustering.pipeline``. If ``apply``
    is True, writes leaf paths + umap coords to ``IntegratedBgc``, upserts
    ``DashboardGCF`` rows, and emits MIBiG validation artifacts under
    ``settings.CLUSTERING_ARTIFACTS_DIR / <run.sha256[:12]>/``. Optionally
    chains a reclassify task to assign partial iBGCs and a projection task
    that fills umap / leaf path / novelty for partials.
    """
    task_id = uuid4().hex
    search_key = f"bgc_clustering:{task_id}"
    set_job_cache(search_key=search_key, task_id=task_id, timeout=CLUSTERING_TTL)

    from discovery.services.clustering.pipeline import (
        DEFAULT_DOMAIN_SOURCES,
        DEFAULT_RESOLUTIONS,
        DEFAULT_SCORE_WEIGHTS,
        run_clustering_pipeline,
    )

    sources = tuple(s.upper() for s in (domain_sources or DEFAULT_DOMAIN_SOURCES))
    weights = (
        (float(score_weights[0]), float(score_weights[1]))
        if score_weights
        else DEFAULT_SCORE_WEIGHTS
    )
    resolutions = (
        tuple(leiden_resolutions) if leiden_resolutions else DEFAULT_RESOLUTIONS
    )

    result = run_clustering_pipeline(
        domain_sources=sources,
        score_weights=weights,
        knn_k=knn_k,
        leiden_resolutions=resolutions,
        seed=seed,
        apply=apply,
        score_ibgcs=score_ibgcs,
    )

    if apply and auto_reclassify and "run_pk" in result:
        knn = result.get("knn_k") or knn_k or 5
        # Enqueue reclassify on the scores queue; it chains the partial-iBGC
        # projection itself when ``then_project`` is set (was a Celery link).
        reclassify_result = reclassify_bgcs_task.enqueue(
            clustering_run_pk=result["run_pk"],
            scope=reclassify_scope,
            knn_k=knn,
            then_project=score_ibgcs,
            project_knn_k=knn,
        )
        if score_ibgcs:
            result["project_partial_ibgcs_chained"] = True
        result["reclassify_task_id"] = reclassify_result.id

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=CLUSTERING_TTL,
    )
    log.info("run_bgc_clustering complete (task %s): %s", task_id, result)
    return result


# ── Reclassification of partial / late BGCs ───────────────────────────────────


@task(queue_name="scores")
def reclassify_bgcs_task(
    *,
    clustering_run_pk: int,
    scope: str = "partial",
    knn_k: int = 5,
    min_total_similarity: float = 0.1,
    then_project: bool = False,
    project_knn_k: int = 5,
) -> dict:
    """Assign leaf family paths to partial / non-primary iBGCs against an existing run.

    Re-runnable independently of ``run_bgc_clustering_task``. Updates only
    classification fields on ``IntegratedBgc``; never touches the hierarchy.
    When ``then_project`` is set, chains the partial-iBGC UMAP projection on
    success (replaces the old Celery ``link=`` on the clustering chain).
    """
    task_id = uuid4().hex
    search_key = f"bgc_reclassify:{clustering_run_pk}"
    set_job_cache(search_key=search_key, task_id=task_id, timeout=CLUSTERING_TTL)

    from discovery.services.clustering.reclassify import reclassify_bgcs

    def _progress(payload: dict) -> None:
        set_job_cache(
            search_key=search_key,
            results={**payload, "phase": "running"},
            task_id=task_id,
            timeout=CLUSTERING_TTL,
        )

    result = reclassify_bgcs(
        clustering_run_pk=clustering_run_pk,
        scope=scope,
        knn_k=knn_k,
        min_total_similarity=min_total_similarity,
        progress_cb=_progress,
    )
    set_job_cache(
        search_key=search_key,
        results={**result, "phase": "complete"},
        task_id=task_id,
        timeout=CLUSTERING_TTL,
    )
    if then_project:
        project_partial_ibgcs_task.enqueue(
            clustering_run_pk=clustering_run_pk,
            knn_k=project_knn_k,
            min_total_similarity=min_total_similarity,
        )
    log.info("reclassify_bgcs complete (task %s): %s", task_id, result)
    return result


# ── Partial-iBGC projection (umap coords + scores for non-primary iBGCs) ───────


@task(queue_name="scores")
def project_partial_ibgcs_task(
    *,
    clustering_run_pk: int,
    knn_k: int = 5,
    min_total_similarity: float = 0.1,
) -> dict:
    """Project partial / non-primary iBGCs onto a ClusteringRun's UMAP.

    Writes ``umap_x`` / ``umap_y`` (similarity-weighted average of top-K
    primary neighbours), ``gene_cluster_family``, ``novelty_score``, and
    ``domain_novelty`` on every ``IntegratedBgc`` whose ``classification_run``
    differs from the target run. Marks ``umap_projected = True``.
    """
    task_id = uuid4().hex
    search_key = f"bgc_project_partial:{clustering_run_pk}"
    set_job_cache(search_key=search_key, task_id=task_id, timeout=CLUSTERING_TTL)

    from discovery.services.clustering.ibgc_scoring import project_partial_ibgcs

    def _progress(payload: dict) -> None:
        set_job_cache(
            search_key=search_key,
            results={**payload, "phase": "running"},
            task_id=task_id,
            timeout=CLUSTERING_TTL,
        )

    result = project_partial_ibgcs(
        clustering_run_pk=clustering_run_pk,
        knn_k=knn_k,
        min_total_similarity=min_total_similarity,
        progress_cb=_progress,
    )
    set_job_cache(
        search_key=search_key,
        results={**result, "phase": "complete"},
        task_id=task_id,
        timeout=CLUSTERING_TTL,
    )
    log.info("project_partial_ibgcs complete (task %s): %s", task_id, result)
    return result


@task()
def sequence_similarity_search(
    sequence: str,
    min_bitscore: float = 30.0,
    min_pident: float = 70.0,
    min_qcov: float = 70.0,
) -> dict[int, dict[str, float | str]]:
    """Run phmmer for a query protein and return matching iBGCs.

    Thin task wrapper over ``discovery.services.query.run_sequence_search`` —
    the canonical resolver shared with the combined multi-criterion query.
    Returns ``{ibgc_id: {"bitscore": ..., "pident": ..., "qcoverage": ...,
    "protein_id": ...}}`` from the highest-bitscore matched protein per iBGC.
    """
    from discovery.services.query import run_sequence_search

    return run_sequence_search(
        sequence,
        min_bitscore=min_bitscore,
        min_pident=min_pident,
        min_qcov=min_qcov,
    )


@task()
def update_protein_search_index_task(
    rebuild: bool = False,
    then_update_stats: bool = False,
    stats_queue: str = "default",
) -> dict:
    """Append new proteins to the on-disk phmmer index (or rebuild from scratch).

    Enqueued automatically at the end of ``load_discovery_data``; can also be
    invoked manually via ``python manage.py build_protein_search_index``.
    Chains ``update_discovery_stats_task`` on success when ``then_update_stats``.
    """
    from discovery.services.protein_search.build import rebuild_index, update_index

    stats = rebuild_index() if rebuild else update_index()
    log.info(
        "update_protein_search_index_task: total=%d added=%d elapsed=%.1fs version=%d",
        stats.total_in_db,
        stats.newly_added,
        stats.elapsed_seconds,
        stats.version,
    )
    if then_update_stats:
        update_discovery_stats_task.using(queue_name=stats_queue).enqueue()
    return {
        "total_in_db": stats.total_in_db,
        "already_indexed": stats.already_indexed,
        "newly_added": stats.newly_added,
        "elapsed_seconds": stats.elapsed_seconds,
        "version": stats.version,
    }


@task()
def update_discovery_stats_task() -> bool:
    """Recompute platform-overview counts and append a new DiscoveryStats row."""
    from discovery.models import DiscoveryStats
    from discovery.services.stats import generate_discovery_stats
    from django.db import transaction

    stats = generate_discovery_stats()
    with transaction.atomic():
        ds = DiscoveryStats.objects.create(stats=stats)
    log.info("DiscoveryStats id=%s created: %s", ds.pk, stats)
    return True


# ── Ephemeral asset upload ──────────────────────────────────────────────────


@task()
def process_asset_upload_task(token: str) -> dict:
    """Validate, parse, build virtual iBGCs and project an uploaded asset.

    The upload bytes are read from the shared PVC staging dir
    (``settings.UPLOAD_STAGING_DIR``) — the API handler parks them there
    because the worker runs in a separate pod with its own filesystem. The
    file is dropped in ``finally`` so a successful run doesn't pin ~100 MB.
    """
    from discovery.services.asset_upload import cache as asset_cache
    from discovery.services.asset_upload.parse import parse_asset_tar
    from discovery.services.asset_upload.project import project_asset
    from discovery.services.asset_upload.validate import (
        AssetValidationError,
        inspect_tarball,
    )

    task_id = uuid4().hex
    asset_cache.mark_running(token, task_id=task_id, progress={"step": "validate"})

    try:
        raw = asset_cache.read_upload(token)
        if raw is None:
            error = "Upload bytes missing from staging (file expired or evicted)"
            asset_cache.mark_failed(token, task_id=task_id, error=error)
            return {"token": token, "state": "FAILED", "error": error}

        try:
            validated = inspect_tarball(raw)
            asset_cache.mark_running(token, task_id=task_id, progress={"step": "parse"})
            data = parse_asset_tar(validated)
        except AssetValidationError as exc:
            asset_cache.mark_failed(token, task_id=task_id, error=str(exc))
            return {"token": token, "state": "FAILED", "error": str(exc)}
        except (
            Exception
        ) as exc:  # noqa: BLE001 — never let the UI hang on a 5-min poll timeout
            log.exception(
                "process_asset_upload: unexpected error during validate/parse"
            )
            asset_cache.mark_failed(
                token,
                task_id=task_id,
                error=f"Could not parse upload: {exc}",
            )
            return {"token": token, "state": "FAILED", "error": str(exc)}

        asset_cache.mark_running(token, task_id=task_id, progress={"step": "project"})
        try:
            summary = project_asset(token, data, task_id=task_id)
        except Exception as exc:  # noqa: BLE001 — surface to caller via cache
            log.exception("process_asset_upload: projection failed")
            asset_cache.mark_failed(token, task_id=task_id, error=str(exc))
            return {"token": token, "state": "FAILED", "error": str(exc)}

        return {"token": token, "state": "SUCCESS", "summary": summary}
    finally:
        asset_cache.evict_upload(token)
