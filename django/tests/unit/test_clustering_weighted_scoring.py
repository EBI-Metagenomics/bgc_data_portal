"""Pure tests for the metric-aware scorers (ADR 0003, Phase 3).

Every on-demand scorer must give, for a ``cosine_idf_enrich`` run, exactly the
similarity the clustering used (common-core's weighted cosine), and for a
``dice`` run exactly what it gave before:

* ``bgc_similarity.compute_composite_similarity`` / ``_block``
* ``similarity_on_demand.score_against_all`` (Find similar)
* ``architecture_search`` (dict cache and ``ScoringCache``)
* ``ibgc_scoring.compute_novelty_against_validated``
"""

from __future__ import annotations

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")

from common_core.clustering.similarity import (  # noqa: E402
    compute_composite_similarity as cc_composite,
)
from common_core.clustering.similarity import weighted_rows  # noqa: E402
from discovery.services.clustering.architecture_search import (  # noqa: E402
    architecture_search,
)
from discovery.services.clustering.bgc_similarity import (  # noqa: E402
    compute_composite_similarity,
    compute_composite_similarity_block,
)
from discovery.services.clustering.ibgc_scoring import (  # noqa: E402
    compute_novelty_against_validated,
)
from discovery.services.clustering.similarity_on_demand import (  # noqa: E402
    ScoringCache,
    score_against_all,
)

COSINE = "cosine_idf_enrich"


def _fixture(seed: int = 0, n: int = 40, d: int = 15, p: int = 25):
    rng = np.random.default_rng(seed)
    M_dom = (rng.random((n, d)) > 0.7).astype(np.uint8)
    M_pair = (rng.random((n, p)) > 0.85).astype(np.uint8)
    M_pair[5] = 0  # a row without pairs
    w_dom = rng.uniform(0.0, 3.0, d).astype(np.float32)
    w_pair = rng.uniform(0.0, 3.0, p).astype(np.float32)
    w_dom[0] = 0.0  # zero-weight feature (ubiquitous → idf 0)
    return (
        scipy_sparse.csr_matrix(M_dom),
        scipy_sparse.csr_matrix(M_pair),
        w_dom,
        w_pair,
    )


def _full_cosine(M_dom, M_pair, w_dom, w_pair, weights=(0.5, 0.5)):
    """Unpruned common-core composite, diagonal restored (self = 1)."""
    sim = cc_composite(
        M_dom,
        M_pair,
        weights=weights,
        prune_below=0.0,
        metric=COSINE,
        domain_weights=w_dom,
        pair_weights=w_pair,
    ).toarray()
    return sim


def _dense_dice(M):
    M = M.toarray().astype(np.float64)
    inter = M @ M.T
    s = M.sum(axis=1)
    den = s[:, None] + s[None, :]
    out = np.zeros_like(inter)
    np.divide(2.0 * inter, den, out=out, where=den > 0)
    return out


def _scoring_cache(M_dom, M_pair, w_dom=None, w_pair=None, *, weights=(0.5, 0.5)):
    metric = "dice" if w_dom is None else COSINE
    n = M_dom.shape[0]
    return ScoringCache(
        sha256="0" * 64,
        M_domains=M_dom,
        M_pairs=M_pair,
        domain_accs=np.asarray([f"D{i}" for i in range(M_dom.shape[1])], dtype=object),
        pair_vocab=np.asarray(
            [(f"D{i}", f"D{i + 1}") for i in range(M_pair.shape[1])], dtype=object
        ),
        ibgc_ids=np.arange(100, 100 + n),
        row_sums_domains=np.asarray(M_dom.sum(axis=1)).ravel().astype(np.float32),
        row_sums_pairs=np.asarray(M_pair.sum(axis=1)).ravel().astype(np.float32),
        weight_domain=weights[0],
        weight_adjacency=weights[1],
        _id_to_row={100 + i: i for i in range(n)},
        sig_to_ipr={},
        similarity_metric=metric,
        domain_weights=w_dom,
        pair_weights=w_pair,
        X_domains=None if w_dom is None else weighted_rows(M_dom, w_dom),
        X_pairs=None if w_pair is None else weighted_rows(M_pair, w_pair),
    )


# ── bgc_similarity ──────────────────────────────────────────────────────────


def test_portal_composite_cosine_delegates_to_common_core():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    got = compute_composite_similarity(
        M_dom,
        M_pair,
        prune_below=0.05,
        metric=COSINE,
        domain_weights=w_dom,
        pair_weights=w_pair,
    ).toarray()
    want = cc_composite(
        M_dom,
        M_pair,
        prune_below=0.05,
        metric=COSINE,
        domain_weights=w_dom,
        pair_weights=w_pair,
    ).toarray()
    np.testing.assert_array_equal(got, want)


def test_cosine_block_equals_full_matrix_slice():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    full = _full_cosine(M_dom, M_pair, w_dom, w_pair, weights=(0.3, 0.7))
    n_ref = 30
    block = compute_composite_similarity_block(
        M_dom[n_ref:],
        M_dom[:n_ref],
        M_pair[n_ref:],
        M_pair[:n_ref],
        weights=(0.3, 0.7),
        metric=COSINE,
        domain_weights=w_dom,
        pair_weights=w_pair,
    ).toarray()
    np.testing.assert_allclose(block, full[n_ref:, :n_ref], atol=1e-6)


def test_cosine_block_requires_weights():
    M_dom, M_pair, _, _ = _fixture()
    with pytest.raises(ValueError, match="needs domain_weights"):
        compute_composite_similarity_block(
            M_dom[:5], M_dom, M_pair[:5], M_pair, metric=COSINE
        )


def test_dice_block_unchanged_by_metric_plumbing():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    a = compute_composite_similarity_block(
        M_dom[30:], M_dom[:30], M_pair[30:], M_pair[:30]
    )
    b = compute_composite_similarity_block(
        M_dom[30:],
        M_dom[:30],
        M_pair[30:],
        M_pair[:30],
        metric="dice",
        domain_weights=w_dom,
        pair_weights=w_pair,
    )
    want = 0.5 * _dense_dice(M_dom)[30:, :30] + 0.5 * _dense_dice(M_pair)[30:, :30]
    np.testing.assert_array_equal(a.toarray(), b.toarray())
    np.testing.assert_allclose(a.toarray(), want, atol=1e-6)


# ── Find similar (score_against_all) ────────────────────────────────────────


def test_find_similar_cosine_matches_clustering_similarity():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    cache = _scoring_cache(M_dom, M_pair, w_dom, w_pair)
    full = _full_cosine(M_dom, M_pair, w_dom, w_pair)
    for row in (0, 5, 17):
        scores = score_against_all(M_dom.getrow(row), M_pair.getrow(row), cache)
        scores[row] = 0.0  # the clustering matrix zeroes the diagonal
        np.testing.assert_allclose(scores, full[row], atol=1e-6)


def test_find_similar_dice_is_the_closed_form():
    M_dom, M_pair, _, _ = _fixture()
    cache = _scoring_cache(M_dom, M_pair)
    want = 0.5 * _dense_dice(M_dom) + 0.5 * _dense_dice(M_pair)
    for row in (0, 5, 17):
        scores = score_against_all(M_dom.getrow(row), M_pair.getrow(row), cache)
        np.testing.assert_allclose(scores, want[row], atol=1e-6)


def test_find_similar_weight_override_and_empty_query():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    cache = _scoring_cache(M_dom, M_pair, w_dom, w_pair)
    dom_only = score_against_all(
        M_dom.getrow(3),
        M_pair.getrow(3),
        cache,
        weight_domain=1.0,
        weight_adjacency=0.0,
    )
    full = _full_cosine(M_dom, M_pair, w_dom, w_pair, weights=(1.0, 0.0))
    dom_only[3] = 0.0
    np.testing.assert_allclose(dom_only, full[3], atol=1e-6)

    empty = scipy_sparse.csr_matrix((1, M_dom.shape[1]), dtype=np.uint8)
    empty_p = scipy_sparse.csr_matrix((1, M_pair.shape[1]), dtype=np.uint8)
    assert not score_against_all(empty, empty_p, cache).any()


# ── Architecture search ─────────────────────────────────────────────────────


def _arch_cache(w_dom=None, w_pair=None):
    accs = ["A", "B", "C", "D"]
    pairs = [("A", "B"), ("B", "C"), ("C", "D")]
    M_dom = scipy_sparse.csr_matrix(
        np.array([[1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1]], dtype=np.uint8)
    )
    M_pair = scipy_sparse.csr_matrix(
        np.array([[1, 1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.uint8)
    )
    cache = {
        "M_domains": M_dom,
        "M_pairs": M_pair,
        "ibgc_ids": np.array([10, 20, 30]),
        "domain_accs": np.asarray(accs, dtype=object),
        "pair_vocab": np.asarray(pairs, dtype=object),
        "sig_to_ipr": {},
    }
    if w_dom is not None:
        cache.update(
            similarity_metric=COSINE, domain_weights=w_dom, pair_weights=w_pair
        )
    return cache


def test_architecture_cosine_scores_match_weighted_cosine():
    w_dom = np.array([2.0, 0.5, 1.0, 1.0], dtype=np.float32)
    w_pair = np.array([1.0, 3.0, 1.0], dtype=np.float32)
    cache = _arch_cache(w_dom, w_pair)
    out = architecture_search(["A", "B", "C"], weight=0.5, k=3, cache=cache)
    # Query == row 0 exactly → 1.0; others by the weighted cosine formula.
    by_id = dict(zip(out["ibgc_ids"], out["scores"]))
    assert by_id[10] == pytest.approx(1.0, abs=1e-6)

    def cos(a, b, w):
        a, b, w2 = np.asarray(a, float), np.asarray(b, float), np.asarray(w, float) ** 2
        return (a * b * w2).sum() / np.sqrt((a * w2).sum() * (b * w2).sum())

    want_20 = 0.5 * cos([1, 1, 1, 0], [1, 1, 0, 0], w_dom) + 0.5 * cos(
        [1, 1, 0], [1, 0, 0], w_pair
    )
    assert by_id[20] == pytest.approx(want_20, abs=1e-6)


def test_architecture_cosine_scoring_cache_equals_dict_cache():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    sc = _scoring_cache(M_dom, M_pair, w_dom, w_pair)
    d = {
        "M_domains": M_dom,
        "M_pairs": M_pair,
        "ibgc_ids": sc.ibgc_ids,
        "domain_accs": sc.domain_accs,
        "pair_vocab": sc.pair_vocab,
        "sig_to_ipr": {},
        "similarity_metric": COSINE,
        "domain_weights": w_dom,
        "pair_weights": w_pair,
    }
    query = ["D1", "D2", "D3", "D7"]
    a = architecture_search(query, weight=0.6, k=40, cache=sc)
    b = architecture_search(query, weight=0.6, k=40, cache=d)
    assert a["ibgc_ids"] == b["ibgc_ids"]
    np.testing.assert_allclose(a["scores"], b["scores"], atol=1e-7)


def test_architecture_cosine_without_weights_is_an_error():
    cache = _arch_cache()
    cache["similarity_metric"] = COSINE
    with pytest.raises(ValueError, match="lacks its feature weights"):
        architecture_search(["A", "B"], weight=0.5, k=3, cache=cache)


def test_architecture_dice_cache_unchanged():
    out = architecture_search(["A", "B", "C"], weight=1.0, k=3, cache=_arch_cache())
    by_id = dict(zip(out["ibgc_ids"], out["scores"]))
    assert by_id[10] == pytest.approx(1.0)
    assert by_id[20] == pytest.approx(2 * 2 / (3 + 2))
    assert by_id[30] == pytest.approx(2 * 1 / (3 + 2))


# ── Novelty ─────────────────────────────────────────────────────────────────


def test_portal_novelty_cosine_matches_full_similarity():
    M_dom, M_pair, w_dom, w_pair = _fixture()
    validated = [1, 7, 22]
    nov = compute_novelty_against_validated(
        M_dom,
        M_pair,
        validated,
        metric=COSINE,
        domain_weights=w_dom,
        pair_weights=w_pair,
    )
    full = _full_cosine(M_dom, M_pair, w_dom, w_pair)
    want = 1.0 - full[:, validated].max(axis=1)
    # Self-similarity of a non-validated row never enters; validated → 0.
    want[validated] = 0.0
    np.testing.assert_allclose(nov, want, atol=1e-6)


def test_portal_novelty_dice_unchanged():
    M_dom, M_pair, _, _ = _fixture()
    nov = compute_novelty_against_validated(M_dom, M_pair, [1, 7])
    full = 0.5 * _dense_dice(M_dom) + 0.5 * _dense_dice(M_pair)
    want = 1.0 - full[:, [1, 7]].max(axis=1)
    want[[1, 7]] = 0.0
    np.testing.assert_allclose(nov, want, atol=1e-6)
