"""Post-hoc KNN reclassification for non-primary BGCs.

The primary clustering pass operates only on complete BGCs (``is_partial=False``).
This module assigns family paths to every other BGC via the same Sørensen–Dice
metric: compute Dice between each query BGC and every primary BGC of a given
``ClusteringRun``, take top-K, and inherit the most common leaf family path.

Re-runnable independently: invoke whenever new partial BGCs land or whenever
stale assignments need refreshing — does not reshape the hierarchy.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discovery.services.clustering.metrics import BgcSimilarityMetric

log = logging.getLogger(__name__)


SCOPE_PARTIAL = "partial"
SCOPE_STALE = "stale"
SCOPE_ALL_NON_PRIMARY = "all_non_primary"
ALLOWED_SCOPES = (SCOPE_PARTIAL, SCOPE_STALE, SCOPE_ALL_NON_PRIMARY)


def reclassify_bgcs(
    *,
    clustering_run_pk: int,
    scope: str = SCOPE_PARTIAL,
    knn_k: int = 5,
    metric: "BgcSimilarityMetric | None" = None,
    min_total_similarity: float = 0.1,
    chunk_size: int = 256,
    progress_cb=None,
) -> dict:
    """Assign a leaf family path to every BGC matching ``scope``.

    Parameters
    ----------
    clustering_run_pk:
        ``ClusteringRun`` pk whose hierarchy to inherit.
    scope:
        Which BGCs to (re)classify — see ``SCOPE_*`` constants.
    knn_k:
        Number of nearest primary BGCs whose leaf paths vote for the
        assignment.
    metric:
        Pluggable similarity metric. Defaults to ``SorensenDiceSimilarity``
        instantiated with the run's ``dice_threshold``.
    min_total_similarity:
        Minimum sum of top-K similarities required to commit an assignment.
        Below this the BGC remains ``classification_source="unclassified"``.
    """
    import numpy as np
    from django.utils import timezone

    from discovery.models import DashboardBgc, DashboardGCF, ProteinEmbedding
    from discovery.services.clustering.bgc_similarity import compute_bgc_similarity
    from discovery.services.clustering.membership import build_bgc_protein_matrix
    from discovery.services.clustering.metrics import (
        SorensenDiceSimilarity,
        get_metric,
    )
    from discovery.services.clustering.similarity import (
        build_protein_similarity_matrix,
    )

    if scope not in ALLOWED_SCOPES:
        raise ValueError(f"scope must be one of {ALLOWED_SCOPES}, got {scope!r}")

    from discovery.models import ClusteringRun

    run = ClusteringRun.objects.get(pk=clustering_run_pk)

    # ── 1. Determine query BGCs ───────────────────────────────────────────
    qs = DashboardBgc.objects.all()
    if scope == SCOPE_PARTIAL:
        qs = qs.filter(is_partial=True).exclude(classification_run_id=run.pk)
    elif scope == SCOPE_STALE:
        qs = qs.exclude(classification_source="primary").exclude(
            classification_run_id=run.pk
        )
    elif scope == SCOPE_ALL_NON_PRIMARY:
        qs = qs.exclude(
            classification_source="primary", classification_run_id=run.pk
        )

    query_bgc_ids = list(qs.values_list("id", flat=True))
    if not query_bgc_ids:
        log.info("reclassify_bgcs: no BGCs to classify (scope=%s)", scope)
        return {
            "clustering_run_pk": run.pk,
            "scope": scope,
            "classified": 0,
            "unclassified": 0,
            "skipped": 0,
        }

    # ── 2. Determine primary BGC ids and their leaf paths ─────────────────
    primary_qs = DashboardBgc.objects.filter(
        classification_source="primary",
        classification_run_id=run.pk,
    ).exclude(gene_cluster_family="")
    primary_ids = list(primary_qs.values_list("id", flat=True))
    primary_paths = dict(primary_qs.values_list("id", "gene_cluster_family"))

    if not primary_ids:
        log.warning(
            "reclassify_bgcs: ClusteringRun pk=%s has no primary BGCs", run.pk
        )
        return {
            "clustering_run_pk": run.pk,
            "scope": scope,
            "classified": 0,
            "unclassified": 0,
            "skipped": len(query_bgc_ids),
        }

    # ── 3. Pick the metric (defaults to the run's metric/threshold). ─────
    metric_obj = metric
    if metric_obj is None:
        if run.metric_name == "dice":
            metric_obj = SorensenDiceSimilarity(threshold=run.dice_threshold)
        else:
            metric_obj = get_metric(run.metric_name, threshold=run.dice_threshold)

    # ── 4. Walk query BGCs in chunks; build M_block + primary M, compute  ─
    classified = 0
    unclassified = 0
    update_batch: list[DashboardBgc] = []
    now = timezone.now()

    # Pre-build the primary M and protein vocabulary once for the run.
    M_primary, primary_id_arr, protein_shas = build_bgc_protein_matrix(
        only_complete=True,
        bgc_ids_subset=primary_ids,
    )
    if M_primary.shape[0] == 0:
        return {
            "clustering_run_pk": run.pk,
            "scope": scope,
            "classified": 0,
            "unclassified": 0,
            "skipped": len(query_bgc_ids),
        }
    S = build_protein_similarity_matrix(protein_shas, threshold=run.dice_threshold)
    primary_idx_to_path = np.asarray(
        [primary_paths.get(int(pid), "") for pid in primary_id_arr], dtype=object
    )

    import scipy.sparse as sp

    for start in range(0, len(query_bgc_ids), chunk_size):
        chunk_ids = query_bgc_ids[start : start + chunk_size]
        M_q, q_id_arr, _ = build_bgc_protein_matrix(
            only_complete=False,
            bgc_ids_subset=chunk_ids,
            protein_shas_subset=protein_shas.tolist(),
        )
        if M_q.shape[0] == 0:
            unclassified += len(chunk_ids)
            continue

        # Stack [primary; query]; compute similarity; slice the query rows.
        M_full = sp.vstack([M_primary, M_q], format="csr")
        sim_full = compute_bgc_similarity(M_full, S, metric_obj)
        n_primary = M_primary.shape[0]
        sim_block = sim_full[n_primary:, :n_primary].tocsr()

        for q_row in range(M_q.shape[0]):
            qid = int(q_id_arr[q_row])
            start_p = sim_block.indptr[q_row]
            end_p = sim_block.indptr[q_row + 1]
            if start_p == end_p:
                unclassified += 1
                continue
            cols = sim_block.indices[start_p:end_p]
            vals = sim_block.data[start_p:end_p]
            order = np.argsort(-vals)[:knn_k]
            top_cols = cols[order]
            top_vals = vals[order]
            if float(top_vals.sum()) < min_total_similarity:
                unclassified += 1
                continue
            votes: Counter[str] = Counter()
            for col, val in zip(top_cols.tolist(), top_vals.tolist()):
                path = primary_idx_to_path[col]
                if not path:
                    continue
                votes[str(path)] += float(val)
            if not votes:
                unclassified += 1
                continue
            best_path, _ = votes.most_common(1)[0]
            update_batch.append(
                DashboardBgc(
                    id=qid,
                    gene_cluster_family=best_path,
                    classification_source="knn",
                    classification_run=run,
                    classified_at=now,
                )
            )
            classified += 1

        if progress_cb is not None:
            progress_cb(
                {
                    "scope": scope,
                    "processed": min(start + chunk_size, len(query_bgc_ids)),
                    "total": len(query_bgc_ids),
                    "classified": classified,
                    "unclassified": unclassified,
                }
            )

    # Mark the BGCs we *couldn't* classify so they don't keep stale state.
    unclassified_ids = [
        qid for qid in query_bgc_ids
        if not any(b.id == qid for b in update_batch)
    ]

    if update_batch:
        DashboardBgc.objects.bulk_update(
            update_batch,
            ["gene_cluster_family", "classification_source", "classification_run", "classified_at"],
            batch_size=5_000,
        )

    if unclassified_ids:
        DashboardBgc.objects.filter(id__in=unclassified_ids).update(
            gene_cluster_family="",
            classification_source="unclassified",
            classification_run=run,
            classified_at=now,
        )

    # ── 5. Refresh DashboardGCF aggregates on the new assignments. ───────
    _refresh_gcf_aggregates(run.pk)

    log.info(
        "reclassify_bgcs: run=%s scope=%s classified=%d unclassified=%d",
        run.pk, scope, classified, unclassified + len(unclassified_ids),
    )
    return {
        "clustering_run_pk": run.pk,
        "scope": scope,
        "classified": classified,
        "unclassified": unclassified + len(unclassified_ids),
        "skipped": 0,
    }


def _refresh_gcf_aggregates(clustering_run_pk: int) -> None:
    """Recount ``member_count`` / ``validated_count`` / ``mean_novelty`` for the run.

    Called after any reclassification step changes ``DashboardBgc.gene_cluster_family``.
    """
    from django.db.models import Avg, Count, Q

    from discovery.models import DashboardBgc, DashboardGCF

    gcf_qs = DashboardGCF.objects.filter(clustering_run_id=clustering_run_pk)

    # member_count and validated_count are computed via descendant ltree
    # match: a BGC at leaf path X belongs to every ancestor along X.
    nodes = list(gcf_qs.values_list("id", "family_path"))
    if not nodes:
        return

    bgc_rows = list(
        DashboardBgc.objects.exclude(gene_cluster_family="").values_list(
            "id", "gene_cluster_family", "is_validated", "novelty_score"
        )
    )

    # Pre-bucket BGCs by every prefix of their leaf path so the aggregation
    # stays O(N · depth) instead of O(N · #nodes).
    counts: dict[str, list[tuple[bool, float]]] = {}
    for _, leaf_path, is_validated, novelty in bgc_rows:
        parts = leaf_path.split(".")
        # All path prefixes from the first segment up to the leaf are
        # ancestors; e.g. cluster.0042.0007 is an ancestor of cluster.0042.0007.0003.
        for d in range(1, len(parts) + 1):
            prefix = ".".join(parts[:d])
            counts.setdefault(prefix, []).append((bool(is_validated), float(novelty)))

    update_batch: list[DashboardGCF] = []
    for gcf_id, family_path in nodes:
        members = counts.get(family_path, [])
        member_count = len(members)
        validated_count = sum(1 for v, _ in members if v)
        mean_novelty = (
            sum(n for _, n in members) / member_count if member_count else 0.0
        )
        update_batch.append(
            DashboardGCF(
                id=gcf_id,
                member_count=member_count,
                validated_count=validated_count,
                mean_novelty=mean_novelty,
            )
        )

    if update_batch:
        DashboardGCF.objects.bulk_update(
            update_batch,
            ["member_count", "validated_count", "mean_novelty"],
            batch_size=5_000,
        )
