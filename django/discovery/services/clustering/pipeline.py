"""Shared helpers for clustering runs.

Clustering itself runs on the HPC (``bgc-cluster`` in common-core) and is
loaded with ``manage.py import_clustering_results``. This module holds what
the export, import and scoring-cache commands share: metric defaults, the
run sha, vocab/weight alignment and the on-disk scoring-cache rebuild.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

log = logging.getLogger(__name__)


DEFAULT_DOMAIN_SOURCES: tuple[str, ...] = ("PFAM", "NCBIFAM", "TIGRFAM")
DEFAULT_SCORE_WEIGHTS: tuple[float, float] = (0.5, 0.5)
DEFAULT_RESOLUTIONS: tuple[float, ...] = (0.03, 0.08, 0.15, 0.25)
KNN_K_FLOOR = 5
# Thresholds every Dice run so far was built with; a run that keeps them
# (and the Dice metric) keeps its pre-ADR-0003 sha.
DEFAULT_PRUNE_BELOW = 0.05
DEFAULT_MIN_PROJECTION_SIMILARITY = 0.1


def metric_run_defaults(
    similarity_metric: str,
    score_weights: Sequence[float] | None = None,
    idf_exponent: float | None = None,
) -> tuple[tuple[float, float], float]:
    """Resolve ``(score_weights, idf_exponent)`` for a run of ``similarity_metric``.

    Dice: ``(0.5, 0.5)`` unless given, and always ``idf_exponent=1.0`` (Dice
    has no feature weights). ``cosine_idf_enrich``: the ADR 0003 amendment's
    ``(0.6, 0.4)`` and ``0.5`` unless given.
    """
    from common_core.clustering.similarity import METRIC_DICE
    from common_core.clustering.weights import (
        COSINE_IDF_EXPONENT,
        COSINE_SCORE_WEIGHTS,
    )

    is_dice = similarity_metric == METRIC_DICE
    default_weights = DEFAULT_SCORE_WEIGHTS if is_dice else COSINE_SCORE_WEIGHTS
    weights = (
        (float(score_weights[0]), float(score_weights[1]))
        if score_weights
        else default_weights
    )
    if is_dice:
        return weights, 1.0
    return weights, float(COSINE_IDF_EXPONENT if idf_exponent is None else idf_exponent)


def auto_knn_k(n: int) -> int:
    """Heuristic kNN k for ``n`` nodes: ``max(KNN_K_FLOOR, ceil(ln(n)))``."""
    if n <= 1:
        return KNN_K_FLOOR
    return max(KNN_K_FLOOR, math.ceil(math.log(n)))


def _safe_version(pkg: str) -> str:
    try:
        return _pkg_version(pkg)
    except PackageNotFoundError:
        return ""


def _align_rows(M_pairs, ibgc_ids_adj, ibgc_ids_target):
    """Project ``M_pairs`` onto the row ordering of ``ibgc_ids_target``.

    The adjacency builder can return fewer rows than the domain builder
    (an iBGC may have no source CDS-linked domains, producing an empty
    adjacency sequence). Missing rows become all-zero in the aligned
    matrix.
    """
    import numpy as np
    import scipy.sparse as sp

    n_target = len(ibgc_ids_target)
    n_cols = M_pairs.shape[1]

    if M_pairs.shape[0] == n_target and (
        n_target == 0 or np.array_equal(ibgc_ids_adj, ibgc_ids_target)
    ):
        return M_pairs

    target_index = {int(x): i for i, x in enumerate(ibgc_ids_target.tolist())}
    row_map = {
        i: target_index[int(x)]
        for i, x in enumerate(ibgc_ids_adj.tolist())
        if int(x) in target_index
    }

    if not row_map:
        return sp.csr_matrix((n_target, n_cols), dtype=M_pairs.dtype)

    coo = M_pairs.tocoo(copy=False)
    keep = np.fromiter((r in row_map for r in coo.row), dtype=bool, count=coo.nnz)
    new_rows = np.fromiter(
        (row_map[r] for r in coo.row[keep]),
        dtype=np.int64,
        count=int(keep.sum()),
    )
    return sp.csr_matrix(
        (coo.data[keep], (new_rows, coo.col[keep])),
        shape=(n_target, n_cols),
        dtype=M_pairs.dtype,
    )


def _build_sig_to_ipr_lookup(
    *,
    sources: tuple[str, ...],
    vocab_set: set[str],
) -> dict[str, str]:
    """Return a ``{signature_acc: ipr_entry_acc}`` mapping restricted to the vocab.

    Only includes signatures whose IPR entry actually appears in the active
    domain-acc vocabulary (``vocab_set``).
    """
    from discovery.models import ContigDomain
    from django.db.models.functions import Upper

    pairs = (
        ContigDomain.objects.annotate(ref_db_upper=Upper("ref_db"))
        .filter(
            ref_db_upper__in=sources,
            interpro_entry_acc__gt="",
        )
        .values_list("domain_acc", "interpro_entry_acc")
        .distinct()
    )
    out: dict[str, str] = {}
    for sig, ipr in pairs:
        if not sig or not ipr:
            continue
        ipr_stripped = ipr.strip()
        if not ipr_stripped or ipr_stripped not in vocab_set:
            continue
        out[sig] = ipr_stripped
    log.info("sig_to_ipr lookup: %d signature→IPR mappings", len(out))
    return out


def _compute_run_sha(
    *,
    sources: tuple[str, ...],
    weights: tuple[float, float],
    knn_k: int,
    leiden_resolutions: tuple[float, ...],
    seed: int,
    ibgc_etag: str,
    domain_etag: str,
    domain_vocab: str,
    similarity_metric: str = "dice",
    enrichment_version: str = "",
    idf_exponent: float = 1.0,
    prune_below: float = DEFAULT_PRUNE_BELOW,
    min_projection_similarity: float = DEFAULT_MIN_PROJECTION_SIMILARITY,
    weights_sha: str = "",
) -> str:
    """Return a stable sha256 hex digest for ``ClusteringRun.update_or_create``.

    A Dice run with the default thresholds hashes exactly as before ADR 0003,
    so re-running it reproduces its sha. Other thresholds append
    ``prune`` / ``min_proj``; a weighted metric also appends the metric,
    enrichment version and the weight-vector digest, plus ``idf_exp`` when it
    isn't 1 (so cosine runs built before the ADR 0003 amendment keep their sha).
    """
    parts = [
        f"sources={','.join(sources)}",
        f"vocab={domain_vocab}",
        f"weights={weights[0]:.6f},{weights[1]:.6f}",
        f"k={knn_k}",
        "res=" + ",".join(f"{r:.6f}" for r in leiden_resolutions),
        f"seed={seed}",
        f"ibgc_etag={ibgc_etag}",
        f"domain_etag={domain_etag}",
    ]
    is_dice = similarity_metric == "dice"
    if not is_dice or (prune_below, min_projection_similarity) != (
        DEFAULT_PRUNE_BELOW,
        DEFAULT_MIN_PROJECTION_SIMILARITY,
    ):
        parts += [
            f"prune={prune_below:.6f}",
            f"min_proj={min_projection_similarity:.6f}",
        ]
    if not is_dice:
        parts += [
            f"metric={similarity_metric}",
            f"enrichment={enrichment_version}",
            f"weights_sha={weights_sha}",
        ]
        if idf_exponent != 1.0:
            parts.append(f"idf_exp={idf_exponent:.6f}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _check_metric(similarity_metric: str, enrichment_version: str) -> bool:
    """Validate the metric; return True for Dice."""
    from common_core.clustering.similarity import METRIC_DICE, SIMILARITY_METRICS

    if similarity_metric not in SIMILARITY_METRICS:
        raise ValueError(
            f"unknown similarity_metric {similarity_metric!r}; "
            f"expected one of {SIMILARITY_METRICS}"
        )
    if similarity_metric == METRIC_DICE:
        return True
    if not enrichment_version:
        raise ValueError(
            f"similarity_metric={similarity_metric!r} needs an enrichment_version"
        )
    return False


def _weights_sha(run_weights) -> str:
    if run_weights is None:
        return ""
    from common_core.clustering.weights import weights_sha256

    return weights_sha256(run_weights.domain_weights, run_weights.pair_weights)


def _cache_weights(run_weights) -> dict:
    """``domain_weights`` / ``pair_weights`` kwargs (both None for Dice)."""
    if run_weights is None:
        return {"domain_weights": None, "pair_weights": None}
    return {
        "domain_weights": run_weights.domain_weights,
        "pair_weights": run_weights.pair_weights,
    }


def rebuild_scoring_cache_from_db(run) -> Path | None:
    """Rebuild and persist the on-demand scoring cache for ``run`` from DB state.

    ``run_clustering_pipeline(apply=True)`` writes ``scoring_cache/`` as a side
    effect. When clustering runs on HPC and is folded back via
    ``import_clustering_results`` that side effect never happens, so
    ``get_active_scoring_cache`` raises ``FileNotFoundError`` (surfaced as a 503
    by ``/query/similar-ibgc/`` and ``/query/ibgc-architecture/``).

    The signature matrices are fully derivable from the post-import DB — iBGC
    domain membership, adjacency pairs, and each iBGC's ``gene_cluster_family``
    leaf path — so reconstruct them here and persist under
    ``<CLUSTERING_ARTIFACTS_DIR>/<sha[:12]>/scoring_cache/``. Returns the cache
    directory, or ``None`` when there is nothing clusterable to score.

    A weighted-metric run (``similarity_metric != "dice"``) is rebuilt on the
    run's own vocabulary (``<sha[:12]>/weights/``, written by the pipeline or
    by ``import_clustering_results``) and the cache gets those exact weights.
    IDF is never recomputed here: the corpus may have changed since the run.
    """
    from discovery.models import IntegratedBgc, SourceBgcPrediction
    from discovery.services.clustering.adjacency import (
        build_ibgc_adjacency_pair_matrix,
    )
    from discovery.services.clustering.feature_weights import load_run_weights
    from discovery.services.clustering.ibgc_scoring import persist_scoring_cache
    from discovery.services.clustering.membership import (
        build_ibgc_domain_matrix,
        query_sources,
    )
    from django.conf import settings
    from django.db.models import Q

    upper_sources = tuple(
        sorted({s.upper() for s in (run.domain_sources or DEFAULT_DOMAIN_SOURCES)})
    )
    vocab = run.domain_vocab or "IPR_PROJECTED"
    artifacts_dir = Path(settings.CLUSTERING_ARTIFACTS_DIR) / run.sha256[:12]
    run_weights = None
    if (run.similarity_metric or "dice") != "dice":
        run_weights = load_run_weights(artifacts_dir)
        if run_weights is None:
            raise FileNotFoundError(
                f"ClusteringRun sha={run.sha256[:12]} uses "
                f"{run.similarity_metric!r} but has no persisted weights under "
                f"{artifacts_dir}; re-import its output tarball"
            )

    # Same clusterable subset the pipeline scores: iBGCs with at least one
    # non-partial-or-validated source prediction.
    clusterable_ibgc_ids = list(
        SourceBgcPrediction.objects.filter(integrated_bgc__isnull=False)
        .filter(Q(is_partial=False) | Q(is_validated=True))
        .values_list("integrated_bgc_id", flat=True)
        .distinct()
    )
    if not clusterable_ibgc_ids:
        return None

    M_domains, ibgc_ids, domain_accs = build_ibgc_domain_matrix(
        sources=upper_sources,
        ibgc_ids_subset=clusterable_ibgc_ids,
        vocab=vocab,
        domain_accs_subset=(
            run_weights.domain_accs.tolist() if run_weights is not None else None
        ),
    )
    if M_domains.shape[0] == 0:
        return None

    M_pairs, ibgc_ids_adj, pair_vocab = build_ibgc_adjacency_pair_matrix(
        sources=upper_sources,
        ibgc_ids_subset=ibgc_ids.tolist(),
        vocab=vocab,
        pair_vocab_subset=(
            run_weights.pair_vocab.tolist() if run_weights is not None else None
        ),
    )
    M_pairs = _align_rows(M_pairs, ibgc_ids_adj, ibgc_ids)
    cache_weights: dict = {"domain_weights": None, "pair_weights": None}
    if run_weights is not None:
        if M_pairs.shape[1] == 0 and len(run_weights.pair_vocab):
            # No adjacency rows at all: keep the run's column space.
            import scipy.sparse as sp

            M_pairs = sp.csr_matrix(
                (M_pairs.shape[0], len(run_weights.pair_vocab)), dtype=M_pairs.dtype
            )
            pair_vocab = run_weights.pair_vocab
        cache_weights = {
            "domain_weights": _align_weights(
                run_weights.domain_accs, run_weights.domain_weights, domain_accs
            ),
            "pair_weights": _align_weights(
                run_weights.pair_vocab, run_weights.pair_weights, pair_vocab
            ),
        }

    # Leaf GCF paths come straight from the imported iBGC rows, aligned to the
    # matrix row order.
    gcf_by_id = dict(
        IntegratedBgc.objects.filter(
            id__in=[int(x) for x in ibgc_ids.tolist()]
        ).values_list("id", "gene_cluster_family")
    )
    leaf_paths = [gcf_by_id.get(int(i)) or "" for i in ibgc_ids.tolist()]

    sig_to_ipr = _build_sig_to_ipr_lookup(
        sources=query_sources(upper_sources, vocab),
        vocab_set=set(domain_accs.tolist()),
    )

    return persist_scoring_cache(
        artifacts_dir=artifacts_dir,
        M_domains=M_domains,
        M_pairs=M_pairs,
        ibgc_ids=ibgc_ids,
        domain_accs=domain_accs,
        pair_vocab=pair_vocab,
        leaf_paths=leaf_paths,
        sig_to_ipr=sig_to_ipr,
        **cache_weights,
        similarity_metric=run.similarity_metric or "dice",
    )


def _align_weights(src_vocab, src_weights, dst_vocab):
    """Reorder ``src_weights`` onto ``dst_vocab`` by label; every label must exist."""
    import numpy as np

    def _key(x):
        return tuple(x) if isinstance(x, (list, tuple)) else x

    index = {_key(v): i for i, v in enumerate(src_vocab.tolist())}
    missing = [v for v in dst_vocab.tolist() if _key(v) not in index]
    if missing:
        raise ValueError(
            f"{len(missing)} columns have no persisted weight (e.g. {missing[:3]})"
        )
    order = np.fromiter(
        (index[_key(v)] for v in dst_vocab.tolist()),
        dtype=np.int64,
        count=len(dst_vocab),
    )
    return np.asarray(src_weights, dtype=np.float32)[order]
