"""On-demand composite similarity backed by the small signature matrices.

Scores with the active run's ``similarity_metric`` (ADR 0003): composite Dice
on the binary matrices, or the IDF × enrichment weighted cosine. For the
latter the cache holds row-normalised weighted copies ``X = rownorm(M·diag(w))``
built once on load (same nnz as ``M``), so a query is ``rownorm(q·w) · Xᵀ``.
The binary matrices stay loaded: domain novelty and architecture input need
them.

Both ``/query/similar-ibgc/`` and ``/query/ibgc-architecture/`` now run the same
single sparse-vector-matmul kernel against the persisted ``M_domains`` /
``M_pairs`` for the active ``ClusteringRun``. We never load (or compute) the
full N×N similarity matrix on the K8s side.

A per-process singleton caches the loaded matrices. The active sha is
checked on every call — if a new ``ClusteringRun`` has been imported,
the singleton silently reloads. Per-request results are memoised in Redis
with a 24h TTL keyed on the active sha, so the cache invalidates by virtue
of orphaning when a new run is published.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)


CACHE_KEY_PREFIX_IBGC = "sim:ibgc"
CACHE_KEY_PREFIX_ARCH = "sim:arch"
CACHE_TTL_SECONDS = 60 * 60 * 24  # 24h


@dataclass
class ScoringCache:
    """In-memory primary-iBGC signature cache for the active ClusteringRun."""

    sha256: str
    M_domains: object  # scipy.sparse.csr_matrix
    M_pairs: object
    domain_accs: object  # numpy object array
    pair_vocab: object
    ibgc_ids: object  # numpy int64 array
    row_sums_domains: object
    row_sums_pairs: object
    weight_domain: float
    weight_adjacency: float
    _id_to_row: dict[int, int]
    # Signature accession → IPR entry accession, for resolving user-pasted
    # Pfam/NCBIFAM/TIGRFAM accs onto the IPR-projected vocabulary. Empty
    # dict for caches predating the IPR projection.
    sig_to_ipr: dict[str, str] = None  # type: ignore[assignment]
    # ADR 0003. For "dice" the four arrays below are None.
    similarity_metric: str = "dice"
    domain_weights: object = None  # numpy float32, aligned to domain_accs
    pair_weights: object = None
    X_domains: object = None  # rownorm(M_domains · diag(domain_weights)), CSR
    X_pairs: object = None

    def row_index_for(self, ibgc_id: int) -> int | None:
        return self._id_to_row.get(int(ibgc_id))

    # Dict-style access so legacy consumers (architecture_search) work without
    # change. The dataclass is the source of truth; the keys mirror the on-disk
    # cache layout for clarity.
    def __getitem__(self, key: str):
        if key == "M_domains":
            return self.M_domains
        if key == "M_pairs":
            return self.M_pairs
        if key == "domain_accs":
            return self.domain_accs
        if key == "pair_vocab":
            return self.pair_vocab
        if key == "ibgc_ids":
            return self.ibgc_ids
        if key == "sig_to_ipr":
            return self.sig_to_ipr or {}
        if key in (
            "similarity_metric",
            "domain_weights",
            "pair_weights",
            "X_domains",
            "X_pairs",
        ):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default


_lock = threading.Lock()
_active: ScoringCache | None = None


def get_active_scoring_cache() -> ScoringCache:
    """Return the cached signature matrices for the active ClusteringRun.

    Reloads on demand whenever the active ``ClusteringRun.sha256`` differs
    from the cached one. Raises ``FileNotFoundError`` if no run has matrices
    on disk yet.
    """
    from discovery.models import ClusteringRun

    run = ClusteringRun.objects.order_by("-created_at").first()
    if run is None:
        raise FileNotFoundError("No ClusteringRun available")

    global _active
    with _lock:
        if _active is not None and _active.sha256 == run.sha256:
            return _active
        _active = _load_cache(run)
        return _active


def _load_cache(run) -> ScoringCache:
    import numpy as np
    import scipy.sparse as sp

    cache_dir = (
        Path(settings.CLUSTERING_ARTIFACTS_DIR) / run.sha256[:12] / "scoring_cache"
    )
    if not cache_dir.exists():
        raise FileNotFoundError(
            f"Scoring cache not present for run sha={run.sha256[:12]}: {cache_dir}",
        )

    M_domains = sp.load_npz(cache_dir / "M_domains.npz")
    M_pairs = sp.load_npz(cache_dir / "M_pairs.npz")
    domain_accs = np.load(cache_dir / "domain_accs.npy", allow_pickle=True)
    pair_vocab = np.load(cache_dir / "pair_vocab.npy", allow_pickle=True)
    ibgc_ids = np.load(cache_dir / "ibgc_ids.npy", allow_pickle=True)
    row_sums_domains = np.asarray(M_domains.sum(axis=1)).reshape(-1).astype(np.float32)
    row_sums_pairs = np.asarray(M_pairs.sum(axis=1)).reshape(-1).astype(np.float32)
    sig_to_ipr_path = cache_dir / "sig_to_ipr.json"
    sig_to_ipr: dict[str, str] = (
        json.loads(sig_to_ipr_path.read_text()) if sig_to_ipr_path.exists() else {}
    )

    from discovery.services.clustering.ibgc_scoring import (
        DOMAIN_WEIGHTS_FILE,
        PAIR_WEIGHTS_FILE,
        cached_similarity_metric,
    )

    metric = run.similarity_metric or "dice"
    cache_metric = cached_similarity_metric(cache_dir)
    if cache_metric != metric:
        raise FileNotFoundError(
            f"Scoring cache for run sha={run.sha256[:12]} was written for "
            f"{cache_metric!r} but the run uses {metric!r}; rebuild it "
            "(manage.py rebuild_scoring_cache)"
        )
    domain_weights = pair_weights = X_domains = X_pairs = None
    if metric != "dice":
        from common_core.clustering.similarity import weighted_rows

        try:
            domain_weights = np.load(cache_dir / DOMAIN_WEIGHTS_FILE)
            pair_weights = np.load(cache_dir / PAIR_WEIGHTS_FILE)
        except OSError as exc:
            raise FileNotFoundError(
                f"Scoring cache for run sha={run.sha256[:12]} lacks its "
                f"{metric!r} feature weights"
            ) from exc
        X_domains = weighted_rows(M_domains.tocsr(), domain_weights)
        X_pairs = weighted_rows(M_pairs.tocsr(), pair_weights)

    weights = list(run.score_weights or (0.5, 0.5))
    total = float(weights[0]) + float(weights[1])
    if total <= 0:
        wd, wa = 0.5, 0.5
    else:
        wd, wa = float(weights[0]) / total, float(weights[1]) / total

    id_to_row = {int(x): i for i, x in enumerate(ibgc_ids.tolist())}
    log.info(
        "similarity_on_demand: loaded cache sha=%s metric=%s n_rows=%d (D=%d, P=%d)",
        run.sha256[:12],
        metric,
        len(ibgc_ids),
        M_domains.shape[1],
        M_pairs.shape[1],
    )
    return ScoringCache(
        sha256=run.sha256,
        M_domains=M_domains.tocsr(),
        M_pairs=M_pairs.tocsr(),
        domain_accs=domain_accs,
        pair_vocab=pair_vocab,
        ibgc_ids=ibgc_ids,
        row_sums_domains=row_sums_domains,
        row_sums_pairs=row_sums_pairs,
        weight_domain=wd,
        weight_adjacency=wa,
        _id_to_row=id_to_row,
        sig_to_ipr=sig_to_ipr,
        similarity_metric=metric,
        domain_weights=domain_weights,
        pair_weights=pair_weights,
        X_domains=X_domains,
        X_pairs=X_pairs,
    )


# ── Core scoring kernel ─────────────────────────────────────────────────────


def score_against_all(
    q_dom,
    q_pair,
    cache: ScoringCache,
    *,
    weight_domain: float | None = None,
    weight_adjacency: float | None = None,
):
    """Return the composite score vector (length n_primary) under the run's metric.

    ``q_dom`` / ``q_pair`` are binary 1×D / 1×P rows on the cache's columns.
    Either weight may be overridden by the caller (e.g. ARCH supplies its
    own weight); when both are None we use the cached weights from the
    active run.
    """
    import numpy as np

    w_d = cache.weight_domain if weight_domain is None else float(weight_domain)
    w_a = (
        cache.weight_adjacency if weight_adjacency is None else float(weight_adjacency)
    )
    total = w_d + w_a
    if total <= 0:
        return np.zeros(cache.M_domains.shape[0], dtype=np.float32)
    w_d, w_a = w_d / total, w_a / total

    if cache.similarity_metric != "dice":
        n_rows = cache.M_domains.shape[0]
        out = np.zeros(n_rows, dtype=np.float32)
        if w_d > 0.0 and q_dom.nnz:
            out += w_d * weighted_cosine_scores(
                q_dom, cache.domain_weights, cache.X_domains
            )
        if w_a > 0.0 and q_pair.nnz:
            out += w_a * weighted_cosine_scores(
                q_pair, cache.pair_weights, cache.X_pairs
            )
        return out

    n_rows = cache.M_domains.shape[0]
    dice_d = np.zeros(n_rows, dtype=np.float32)
    dice_a = np.zeros(n_rows, dtype=np.float32)
    n_q_dom = int(q_dom.nnz)
    n_q_pair = int(q_pair.nnz)

    if w_d > 0.0 and n_q_dom > 0:
        num_d = (
            np.asarray((q_dom @ cache.M_domains.T).todense())
            .reshape(-1)
            .astype(np.float32)
        )
        denom_d = cache.row_sums_domains + float(n_q_dom)
        with np.errstate(divide="ignore", invalid="ignore"):
            dice_d = np.where(
                denom_d > 0,
                2.0 * num_d / denom_d,
                0.0,
            ).astype(np.float32)

    if w_a > 0.0 and n_q_pair > 0:
        num_a = (
            np.asarray((q_pair @ cache.M_pairs.T).todense())
            .reshape(-1)
            .astype(np.float32)
        )
        denom_a = cache.row_sums_pairs + float(n_q_pair)
        with np.errstate(divide="ignore", invalid="ignore"):
            dice_a = np.where(
                denom_a > 0,
                2.0 * num_a / denom_a,
                0.0,
            ).astype(np.float32)

    return (w_d * dice_d) + (w_a * dice_a)


def weighted_cosine_scores(q, w, X):
    """Weighted cosine of one binary query row against every row of ``X``.

    ``X`` is the pre-normalised ``rownorm(M · diag(w))``; the query is
    weighted and normalised the same way, so the dot product is the cosine.
    Clipped to 1.0 like the clustering matrix.
    """
    import numpy as np
    from common_core.clustering.similarity import weighted_rows

    qx = weighted_rows(q.tocsr(), w)
    if qx.nnz == 0:
        return np.zeros(X.shape[0], dtype=np.float32)
    scores = np.asarray((qx @ X.T).todense(), dtype=np.float32).reshape(-1)
    return np.minimum(scores, 1.0)


def top_k(scores, k: int) -> tuple[list[int], list[float]]:
    """argpartition + sort over a score vector. Returns row indices + scores."""
    import numpy as np

    n_rows = len(scores)
    k_eff = max(1, min(int(k), n_rows))
    if n_rows == 0 or k_eff == 0:
        return [], []
    top_partition = np.argpartition(-scores, k_eff - 1)[:k_eff]
    top_sorted = top_partition[np.argsort(-scores[top_partition])]
    return top_sorted.tolist(), [float(scores[i]) for i in top_sorted.tolist()]


# ── Redis caching wrapper ───────────────────────────────────────────────────


def cache_similarity_query(
    *,
    cache_key: str,
    ttl: int = CACHE_TTL_SECONDS,
    compute: Callable[[], dict],
) -> dict:
    """Return ``compute()``'s result, memoised in Redis under ``cache_key``."""
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    result = compute()
    if result:
        cache.set(cache_key, result, ttl)
    return result


def cache_key_find_similar(*, sha256: str, ibgc_id: int, k: int) -> str:
    return f"{CACHE_KEY_PREFIX_IBGC}:{sha256[:12]}:{int(ibgc_id)}:{int(k)}"


def cache_key_architecture(
    *,
    sha256: str,
    accs_ordered: Sequence[str],
    weight: float,
    k: int,
) -> str:
    blob = json.dumps(list(accs_ordered), sort_keys=False).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return f"{CACHE_KEY_PREFIX_ARCH}:{sha256[:12]}:{digest}:{weight:.3f}:{int(k)}"
