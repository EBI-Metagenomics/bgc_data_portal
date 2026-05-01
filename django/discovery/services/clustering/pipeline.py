"""Orchestrator for the pair-based hierarchical Leiden clustering pipeline.

Called by ``run_bgc_clustering_task`` in ``discovery/tasks.py``. Operates only
on complete BGCs (``is_partial=False``) — partial BGCs are routed through
``reclassify_bgcs`` after the hierarchy is built.
"""

from __future__ import annotations

import hashlib
import logging
from importlib.metadata import PackageNotFoundError, version as _pkg_version

log = logging.getLogger(__name__)


DEFAULT_RESOLUTIONS: tuple[float, ...] = (0.4, 0.8, 1.4, 2.0)


def _safe_version(pkg: str) -> str:
    try:
        return _pkg_version(pkg)
    except PackageNotFoundError:
        return ""


def run_clustering_pipeline(
    *,
    dice_threshold: float = 0.9,
    knn_k: int = 5,
    leiden_resolutions: tuple[float, ...] = DEFAULT_RESOLUTIONS,
    metric: str = "dice",
    seed: int = 42,
    apply: bool = False,
    pair_floor: float = 0.7,
) -> dict:
    """Run the full pipeline and (optionally) write paths to DashboardBgc / DashboardGCF.

    Returns a result dict with ``run_pk``, ``sha256``, and counts. The
    caller (the Celery task) is responsible for chaining a reclassify step.
    """
    from django.utils import timezone

    from discovery.models import ClusteringRun, DashboardBgc, DashboardGCF
    from discovery.services.clustering.bgc_similarity import compute_bgc_similarity
    from discovery.services.clustering.knn_graph import build_knn_graph
    from discovery.services.clustering.layout import compute_2d_layout
    from discovery.services.clustering.leiden import run_hierarchical_leiden
    from discovery.services.clustering.membership import build_bgc_protein_matrix
    from discovery.services.clustering.metrics import get_metric
    from discovery.services.clustering.pairs import pair_table_etag
    from discovery.services.clustering.paths import build_ltree_paths
    from discovery.services.clustering.representative import pick_medoid
    from discovery.services.clustering.similarity import (
        build_protein_similarity_matrix,
    )

    leiden_resolutions = tuple(leiden_resolutions)

    # ── 1. Membership (complete BGCs only) ────────────────────────────────
    M, bgc_ids, protein_shas = build_bgc_protein_matrix(only_complete=True)
    if M.shape[0] == 0:
        return {"error": "no complete BGCs with proteins found"}

    # ── 2. Protein-protein similarity at the runtime threshold ───────────
    S = build_protein_similarity_matrix(protein_shas, threshold=dice_threshold)

    # ── 3. BGC×BGC similarity via the chosen metric ──────────────────────
    metric_obj = get_metric(metric, threshold=dice_threshold)
    sim = compute_bgc_similarity(M, S, metric_obj, prune_below=0.05)

    # ── 4. KNN graph ──────────────────────────────────────────────────────
    graph = build_knn_graph(sim, k=knn_k)

    # ── 5. Hierarchical Leiden ────────────────────────────────────────────
    levels = run_hierarchical_leiden(graph, resolutions=leiden_resolutions, seed=seed)

    # ── 6. 2D layout ──────────────────────────────────────────────────────
    coords = compute_2d_layout(graph, sim, seed=seed)

    # ── 7. ltree paths ────────────────────────────────────────────────────
    paths_per_bgc, gcf_nodes = build_ltree_paths(levels, bgc_ids)

    # ── 8. ClusteringRun dedup + persist ─────────────────────────────────
    pair_etag = pair_table_etag()
    sha = _compute_run_sha(
        dice_threshold, knn_k, leiden_resolutions, seed, pair_etag,
        n_complete=M.shape[0], metric=metric,
    )
    run, created = ClusteringRun.objects.update_or_create(
        sha256=sha,
        defaults={
            "pair_floor": pair_floor,
            "dice_threshold": dice_threshold,
            "knn_k": knn_k,
            "leiden_resolutions": list(leiden_resolutions),
            "metric_name": metric,
            "seed": seed,
            "n_proteins": int(S.shape[0]),
            "n_pairs": int(S.nnz - S.shape[0]),  # off-diagonal entries
            "n_bgcs": int(M.shape[0]),
            "n_levels": len(leiden_resolutions),
            "n_root_communities": sum(1 for n in gcf_nodes if n.level == 0),
            "n_leaf_communities": sum(
                1 for n in gcf_nodes if n.level == len(leiden_resolutions) - 1
            ),
            "igraph_version": _safe_version("igraph"),
            "leidenalg_version": _safe_version("leidenalg"),
            "umap_version": _safe_version("umap-learn"),
            "scipy_version": _safe_version("scipy"),
        },
    )
    log.info(
        "%s ClusteringRun pk=%s sha=%s%s",
        "Created" if created else "Updated",
        run.pk,
        sha[:12],
        "..." if len(sha) > 12 else "",
    )

    # ── 9. Replace DashboardGCF rows for this run; pick medoids. ─────────
    DashboardGCF.objects.filter(clustering_run=run).delete()
    bgc_id_to_db: dict[int, DashboardBgc] = {}
    if apply:
        bgc_id_to_db = DashboardBgc.objects.in_bulk(list(paths_per_bgc.keys()))

    gcf_rows: list[DashboardGCF] = []
    for node in gcf_nodes:
        # Medoid is over the global member indices (vertex indices into bgc_ids).
        medoid_v = pick_medoid(node.member_indices, sim)
        medoid_bgc_id = int(bgc_ids[medoid_v])
        gcf_rows.append(
            DashboardGCF(
                clustering_run=run,
                family_path=node.family_path,
                parent_path=node.parent_path,
                level=node.level,
                representative_bgc_id=medoid_bgc_id,
                member_count=len(node.member_indices),
                descendant_count=0,  # filled in below
            )
        )
    DashboardGCF.objects.bulk_create(gcf_rows, batch_size=5_000)

    # Fill descendant_count via a single-pass parent lookup.
    parent_to_children: dict[str, int] = {}
    for node in gcf_nodes:
        if node.parent_path:
            parent_to_children[node.parent_path] = (
                parent_to_children.get(node.parent_path, 0) + 1
            )
    if parent_to_children:
        rows_to_update = list(
            DashboardGCF.objects.filter(
                clustering_run=run,
                family_path__in=list(parent_to_children.keys()),
            )
        )
        for row in rows_to_update:
            row.descendant_count = parent_to_children.get(row.family_path, 0)
        DashboardGCF.objects.bulk_update(rows_to_update, ["descendant_count"], batch_size=5_000)

    # ── 10. Apply paths and umap coords to DashboardBgc (primary only). ──
    gcf_updated = 0
    if apply:
        now = timezone.now()
        update_batch: list[DashboardBgc] = []
        # Map vertex idx → coord
        for v_idx, bgc_id in enumerate(bgc_ids):
            bgc = bgc_id_to_db.get(int(bgc_id))
            if bgc is None:
                continue
            bgc.umap_x = float(coords[v_idx, 0])
            bgc.umap_y = float(coords[v_idx, 1])
            bgc.gene_cluster_family = paths_per_bgc[int(bgc_id)]
            bgc.classification_source = "primary"
            bgc.classification_run = run
            bgc.classified_at = now
            update_batch.append(bgc)
        DashboardBgc.objects.bulk_update(
            update_batch,
            [
                "umap_x", "umap_y", "gene_cluster_family",
                "classification_source", "classification_run", "classified_at",
            ],
            batch_size=10_000,
        )
        gcf_updated = len(update_batch)

    return {
        "run_pk": run.pk,
        "created": created,
        "sha256": sha,
        "n_bgcs": int(M.shape[0]),
        "n_proteins": int(S.shape[0]),
        "n_pairs_used": int(S.nnz - S.shape[0]),
        "n_levels": len(leiden_resolutions),
        "n_leaf_communities": sum(1 for n in gcf_nodes if n.level == len(leiden_resolutions) - 1),
        "gcf_updated": gcf_updated,
    }


def _compute_run_sha(
    dice_threshold: float,
    knn_k: int,
    leiden_resolutions: tuple[float, ...],
    seed: int,
    pair_etag: str,
    *,
    n_complete: int,
    metric: str,
) -> str:
    """Return a stable sha256 hex digest for ``ClusteringRun.update_or_create``."""
    payload = "|".join([
        f"metric={metric}",
        f"dice={dice_threshold:.6f}",
        f"k={knn_k}",
        "res=" + ",".join(f"{r:.6f}" for r in leiden_resolutions),
        f"seed={seed}",
        f"pair_etag={pair_etag}",
        f"n_complete={n_complete}",
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
