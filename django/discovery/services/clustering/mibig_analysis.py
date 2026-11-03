"""Post-clustering MIBiG validation artifacts.

After a clustering run has been applied (iBGCs updated with their leaf
``gene_cluster_family``), this module emits two files under
``settings.CLUSTERING_ARTIFACTS_DIR / <run_sha[:12]>/``:

* ``mibig_validation.tsv``                  — one row per validated iBGC
* ``mibig_class_cluster_heatmap.html``      — Plotly heatmap (class × leaf cluster)

The TSV captures cluster assignments + purity metrics for each validated
iBGC, giving a direct quality check against curated NP taxonomies. The
heatmap is interactive (Plotly HTML, plotly.js loaded from CDN) so the run
dir stays compact. (A UMAP scatter used to be emitted too; the 2D layout was
removed.)

"MIBiG class" is derived from the top-level segment of the iBGC's first
``IbgcNaturalProduct.np_class_path``. iBGCs without an NP record fall back
to the generic ``"validated"`` bucket so they still appear in the heatmap.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TOP_N_CLUSTERS_FOR_HEATMAP = 50

UNCLASSIFIED_BUCKET = "validated"


def emit_run_artifacts(run, *, ibgc_ids, leaf_paths) -> Path:
    """Materialize the TSV + heatmap HTML for an applied ClusteringRun.

    Parameters
    ----------
    run : ClusteringRun
        The just-completed run (must already have ``sha256`` populated).
    ibgc_ids : sequence[int]
        Row-aligned iBGC ids — matches ``leaf_paths`` indices.
    leaf_paths : sequence[str]
        Leaf cluster path per iBGC (``DashboardGCF.family_path``-style ltree).

    Returns
    -------
    Path
        Absolute path to the artifact directory.
    """
    from django.conf import settings

    out_dir = Path(settings.CLUSTERING_ARTIFACTS_DIR) / run.sha256[:12]
    out_dir.mkdir(parents=True, exist_ok=True)

    ibgc_lookup = {int(ibgc_id): leaf_paths[i] for i, ibgc_id in enumerate(ibgc_ids)}
    mibig_rows = _collect_validated_rows(ibgc_lookup)

    if mibig_rows:
        _build_mibig_validation_tsv(mibig_rows, out_dir / "mibig_validation.tsv")
        _build_confusion_heatmap_html(
            mibig_rows,
            out_dir / "mibig_class_cluster_heatmap.html",
            run_sha=run.sha256,
        )
    else:
        log.warning("emit_run_artifacts: no validated iBGCs — skipping TSV and heatmap")

    log.info("emit_run_artifacts: wrote artifacts to %s", out_dir)
    return out_dir


def _collect_validated_rows(
    ibgc_lookup: dict[int, str],
) -> list[dict[str, Any]]:
    """Pull validated iBGCs and join with cluster info + NP class breakdown.

    One row per validated iBGC (an iBGC with at least one
    ``SourceBgcPrediction.is_validated=True``). ``mibig_class_top`` comes
    from the top-level segment of the first ``IbgcNaturalProduct.np_class_path``;
    iBGCs without an NP record fall back to the ``UNCLASSIFIED_BUCKET``.
    """
    from discovery.models import (
        IbgcNaturalProduct,
        IntegratedBgc,
        SourceBgcPrediction,
    )

    validated_ibgc_ids = list(
        SourceBgcPrediction.objects.filter(
            is_validated=True,
            integrated_bgc__isnull=False,
        )
        .values_list("integrated_bgc_id", flat=True)
        .distinct()
    )
    if not validated_ibgc_ids:
        return []

    np_paths_by_ibgc: dict[int, str] = {}
    for ibgc_id, path in (
        IbgcNaturalProduct.objects.filter(ibgc_id__in=validated_ibgc_ids)
        .exclude(np_class_path="")
        .order_by("ibgc_id", "id")
        .values_list("ibgc_id", "np_class_path")
        .iterator(chunk_size=5_000)
    ):
        np_paths_by_ibgc.setdefault(int(ibgc_id), path)

    detector_by_prediction: dict[int, str] = {}
    pred_accessions_by_ibgc: dict[int, list[str]] = defaultdict(list)
    for pred_id, ibgc_id, acc, tool in (
        SourceBgcPrediction.objects.filter(
            is_validated=True,
            integrated_bgc__isnull=False,
        )
        .select_related("detector")
        .values_list(
            "id",
            "integrated_bgc_id",
            "prediction_accession",
            "detector__tool",
        )
    ):
        detector_by_prediction[int(pred_id)] = tool or ""
        pred_accessions_by_ibgc[int(ibgc_id)].append(acc)

    ibgc_meta = {
        ibgc.id: ibgc.accession
        for ibgc in IntegratedBgc.objects.filter(id__in=validated_ibgc_ids).only(
            "id",
            "accession",
        )
    }

    rows: list[dict[str, Any]] = []
    for ibgc_id in validated_ibgc_ids:
        leaf_path = ibgc_lookup.get(int(ibgc_id))
        if leaf_path is None:
            continue
        class_path = np_paths_by_ibgc.get(int(ibgc_id), "")
        class_top = class_path.split(".", 1)[0] if class_path else UNCLASSIFIED_BUCKET
        rows.append(
            {
                "ibgc_accession": ibgc_meta.get(int(ibgc_id), str(ibgc_id)),
                "integrated_bgc_id": int(ibgc_id),
                "source_prediction_accessions": "|".join(
                    sorted(pred_accessions_by_ibgc.get(int(ibgc_id), []))
                ),
                "leaf_cluster_path": leaf_path,
                "mibig_class_top": class_top,
                "mibig_class_full_path": class_path,
            }
        )
    return rows


def _build_mibig_validation_tsv(
    mibig_rows: list[dict[str, Any]], out_path: Path
) -> None:
    import pandas as pd

    if not mibig_rows:
        return

    leaf_size: Counter[str] = Counter()
    leaf_class_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in mibig_rows:
        leaf_size[row["leaf_cluster_path"]] += 1
        leaf_class_counts[row["leaf_cluster_path"]][row["mibig_class_top"]] += 1

    enriched = []
    for row in mibig_rows:
        leaf = row["leaf_cluster_path"]
        cls_top = row["mibig_class_top"]
        mibig_count_in_leaf = leaf_size[leaf]
        same_class = leaf_class_counts[leaf][cls_top]
        purity = same_class / mibig_count_in_leaf if mibig_count_in_leaf else 0.0
        level_parts = leaf.split(".") if leaf else []
        enriched.append(
            {
                "ibgc_accession": row["ibgc_accession"],
                "integrated_bgc_id": row["integrated_bgc_id"],
                "source_prediction_accessions": row["source_prediction_accessions"],
                "leaf_cluster_path": leaf,
                "level_0_cluster": level_parts[0] if len(level_parts) > 0 else "",
                "level_1_cluster": level_parts[1] if len(level_parts) > 1 else "",
                "level_2_cluster": level_parts[2] if len(level_parts) > 2 else "",
                "level_3_cluster": level_parts[3] if len(level_parts) > 3 else "",
                "mibig_class_top": cls_top,
                "mibig_class_full_path": row["mibig_class_full_path"],
                "leaf_cluster_mibig_count": mibig_count_in_leaf,
                "leaf_cluster_mibig_purity": purity,
                "n_neighbors_same_class_in_cluster": same_class - 1,
            }
        )

    df = pd.DataFrame(enriched).sort_values(
        ["leaf_cluster_path", "mibig_class_top", "ibgc_accession"]
    )
    df.to_csv(out_path, sep="\t", index=False)
    log.info("MIBiG validation TSV: %d rows → %s", len(df), out_path)


def _build_confusion_heatmap_html(
    mibig_rows: list[dict[str, Any]],
    out_path: Path,
    *,
    run_sha: str,
) -> None:
    import numpy as np
    import plotly.graph_objects as go

    if not mibig_rows:
        return

    counts: dict[tuple[str, str], int] = Counter()
    leaf_totals: Counter[str] = Counter()
    classes: set[str] = set()
    for row in mibig_rows:
        cls = row["mibig_class_top"]
        leaf = row["leaf_cluster_path"]
        counts[(cls, leaf)] += 1
        leaf_totals[leaf] += 1
        classes.add(cls)

    top_leaves = [
        leaf for leaf, _ in leaf_totals.most_common(TOP_N_CLUSTERS_FOR_HEATMAP)
    ]
    classes_sorted = sorted(classes)

    matrix = np.zeros((len(classes_sorted), len(top_leaves)), dtype=int)
    for ci, cls in enumerate(classes_sorted):
        for li, leaf in enumerate(top_leaves):
            matrix[ci, li] = counts.get((cls, leaf), 0)

    annotate = matrix.shape[0] <= 30 and matrix.shape[1] <= 30
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=top_leaves,
            y=classes_sorted,
            colorscale="Viridis",
            colorbar=dict(title="iBGC count"),
            hovertemplate="class=%{y}<br>cluster=%{x}<br>count=%{z}<extra></extra>",
            text=matrix if annotate else None,
            texttemplate="%{text}" if annotate else None,
        )
    )
    fig.update_layout(
        title=(
            f"MIBiG class × leaf cluster — top {len(top_leaves)} clusters — "
            f"run {run_sha[:12]}"
        ),
        xaxis_title="leaf cluster path",
        yaxis_title="MIBiG class (top)",
        xaxis=dict(tickangle=-45),
        template="plotly_white",
    )
    fig.write_html(out_path, include_plotlyjs="cdn")
    log.info("MIBiG heatmap HTML → %s", out_path)
