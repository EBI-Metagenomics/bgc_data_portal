"""Pure tests for the ADR 0003 vocabulary, enrichment counting and run sha.

Locks:

1. **Gap-fill rule** (``membership.gapfilled_labels``): Pfam/NCBIfam/TIGRFAM
   hits always kept; a Gene3D / PRINTS / ProSitePatterns hit kept only when it
   overlaps no already-kept hit on the CDS by ≥ 50 % of the shorter span,
   visited Gene3D > PRINTS > ProSite. When the experiment package ``bgcsim``
   is importable, the rule matches ``bgcsim.tokens.cds_labels("V3_all_ipr")``
   on random hits; otherwise that test is skipped.
2. **Asset builders**: ``IPR_PROJECTED`` output is unchanged; ``IPR_GAPFILLED``
   adds exactly the gap-filling labels.
3. **Enrichment counting**: per-CDS label sets, weights from
   ``common_core.clustering.weights``; MIBiG / metagenomes refused.
4. **Run sha**: a default Dice run hashes exactly as before ADR 0003.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")

from discovery.services.asset_upload.matrices import (  # noqa: E402
    build_asset_adjacency_pair_matrix,
    build_asset_domain_matrix,
)
from discovery.services.asset_upload.schemas import AssetCds, AssetDomain  # noqa: E402
from discovery.services.clustering.enrichment import (  # noqa: E402
    ROLE_CORE,
    ROLE_FLANK,
    check_datasets,
    count_cds_labels,
)
from discovery.services.clustering.membership import (  # noqa: E402
    VOCAB_IPR_GAPFILLED,
    VOCAB_IPR_PROJECTED,
    gapfilled_labels,
    query_sources,
)
from discovery.services.clustering.run_support import (  # noqa: E402
    _align_weights,
    _compute_run_sha,
)

PROD = ("PFAM", "NCBIFAM", "TIGRFAM")


def _labels(rows):
    return [(k, s, lab) for k, s, lab in gapfilled_labels(rows, sources=PROD)]


# ── Gap-fill rule ───────────────────────────────────────────────────────────


def test_prod_hits_always_kept_and_projected():
    rows = [
        (1, "Pfam", "PF00001", "IPR000001", 10, 100),
        (1, "NCBIfam", "NF000001", "", 50, 150),  # overlaps, still kept
        (1, "PFAM", "", "IPR9", 1, 5),  # empty acc dropped
    ]
    assert _labels(rows) == [(1, 10, "IPR000001"), (1, 50, "NF000001")]


def test_gene3d_overlapping_half_of_shorter_span_is_dropped():
    rows = [
        (1, "PFAM", "PF1", "", 0, 100),
        # overlap 50 of shorter span 60 → 50 ≥ 30: dropped
        (1, "GENE3D", "G3D:1", "", 50, 110),
        # overlap 10 of shorter span 100 → 10 < 50: kept
        (1, "Gene3D", "G3D:2", "IPR777", 90, 190),
    ]
    assert _labels(rows) == [(1, 0, "PF1"), (1, 90, "IPR777")]


def test_gapfill_priority_and_blocking_by_kept_gapfill_hits():
    rows = [
        # PRINTS visited after Gene3D even though it starts first.
        (1, "PRINTS", "PR1", "", 200, 300),
        (1, "GENE3D", "G1", "", 210, 310),
        (1, "PROSITEPATTERNS", "PS1", "", 400, 420),
        (1, "PROSITEPATTERNS", "PS2", "", 405, 425),  # blocked by PS1
    ]
    assert _labels(rows) == [(1, 210, "G1"), (1, 400, "PS1")]


def test_overlap_is_per_cds_and_unknown_dbs_ignored():
    rows = [
        (1, "PFAM", "PF1", "", 0, 100),
        (2, "GENE3D", "G1", "", 0, 100),  # different CDS → kept
        (2, "SUPERFAMILY", "SSF1", "", 300, 400),  # not a gap-fill source
    ]
    assert _labels(rows) == [(1, 0, "PF1"), (2, 0, "G1")]


def test_dedup_on_cds_start_label():
    rows = [
        (1, "PFAM", "PF1", "IPR1", 0, 100),
        (1, "NCBIFAM", "NF1", "IPR1", 0, 90),
    ]
    assert _labels(rows) == [(1, 0, "IPR1")]


def test_query_sources_widen_only_for_gapfill():
    assert query_sources(["pfam"], VOCAB_IPR_PROJECTED) == ("PFAM",)
    assert query_sources(["pfam"], VOCAB_IPR_GAPFILLED) == (
        "GENE3D",
        "PFAM",
        "PRINTS",
        "PROSITEPATTERNS",
    )
    with pytest.raises(ValueError):
        query_sources(["pfam"], "RAW")


def test_gapfill_parity_with_bgcsim_tokens():
    tokens = pytest.importorskip("bgcsim.tokens")
    pd = pytest.importorskip("pandas")

    rng = np.random.default_rng(0)
    dbs = ["PFAM", "NCBIFAM", "TIGRFAM", "GENE3D", "PRINTS", "PROSITEPATTERNS"]
    recs = []
    for cds_id in range(300):
        for _ in range(rng.integers(0, 9)):
            s = int(rng.integers(0, 400))
            e = s + int(rng.integers(5, 150))
            db = dbs[int(rng.integers(0, len(dbs)))]
            acc = f"{db[:2]}{int(rng.integers(0, 40))}"
            ipr = f"IPR{int(rng.integers(0, 30))}" if rng.random() < 0.6 else ""
            recs.append((cds_id, db, acc, ipr, s, e))
    df = pd.DataFrame(
        recs,
        columns=["cds_id", "ref_db", "domain_acc", "ipr_acc", "dom_start", "dom_end"],
    )
    # Unique (cds, db, start) so the benchmark's sort has no ties to break.
    df = df.drop_duplicates(["cds_id", "ref_db", "dom_start"])

    ref = tokens.cds_labels(df, "V3_all_ipr")
    want = {cid: sorted(set(labs)) for cid, labs in ref.items()}
    got: dict[int, set] = {}
    for key, _s, lab in gapfilled_labels(df.itertuples(index=False), sources=PROD):
        got.setdefault(int(key), set()).add(lab)
    assert {k: sorted(v) for k, v in got.items()} == want


# ── Asset builders ──────────────────────────────────────────────────────────

_BGC = ("contig_1", 1, 5000, "antiSMASH")


def _vibgc() -> SimpleNamespace:
    """Stand-in for ``VirtualIbgc``: the builders only read ``cds`` / ``domains``."""
    cds = [
        AssetCds(
            bgc_key=_BGC,
            protein_id_str=f"p{i}",
            start_position=1000 * i,
            end_position=1000 * i + 900,
            strand=1,
        )
        for i in range(3)
    ]
    domains = [
        AssetDomain(
            _BGC, "p0", "PF1", ref_db="PFAM", start_position=0, end_position=100
        ),
        AssetDomain(
            _BGC, "p0", "G1", ref_db="GENE3D", start_position=10, end_position=90
        ),
        AssetDomain(
            _BGC, "p1", "G2", ref_db="GENE3D", start_position=0, end_position=80
        ),
        AssetDomain(_BGC, "p2", "PF3", ref_db="", start_position=0, end_position=80),
    ]
    return SimpleNamespace(cds=cds, domains=domains)


def test_asset_builders_projected_unchanged_and_gapfill_adds_gap_only():
    accs = ["G1", "G2", "PF1", "PF3"]
    pairs = [("G2", "PF1"), ("G2", "PF3"), ("PF1", "PF3")]
    v = [_vibgc()]

    proj = build_asset_domain_matrix(v, domain_accs=accs).toarray()[0].tolist()
    gap = (
        build_asset_domain_matrix(v, domain_accs=accs, vocab=VOCAB_IPR_GAPFILLED)
        .toarray()[0]
        .tolist()
    )
    assert proj == [0, 0, 1, 1]  # blank ref_db counts as selected
    assert gap == [0, 1, 1, 1]  # G1 blocked by PF1, G2 fills CDS p1

    proj_p = build_asset_adjacency_pair_matrix(v, pair_vocab=pairs).toarray()[0]
    gap_p = build_asset_adjacency_pair_matrix(
        v, pair_vocab=pairs, vocab=VOCAB_IPR_GAPFILLED
    ).toarray()[0]
    assert proj_p.tolist() == [0, 0, 1]
    assert gap_p.tolist() == [1, 1, 0]


# ── Enrichment counting ─────────────────────────────────────────────────────


def test_count_cds_labels_counts_each_cds_label_set_once():
    rows = [
        (1, ROLE_CORE, "PFAM", "PF1", "", 0, 100),
        (1, ROLE_CORE, "PFAM", "PF1", "", 200, 300),  # same label twice: once
        (1, ROLE_CORE, "GENE3D", "G1", "", 50, 120),  # blocked
        (2, ROLE_FLANK, "PFAM", "PF1", "", 0, 100),
        (2, ROLE_FLANK, "GENE3D", "G1", "", 300, 400),  # fills a gap
        (3, ROLE_FLANK, "PFAM", "PF2", "", 0, 100),
    ]
    c = count_cds_labels(rows, sources=PROD)
    c.n_core, c.n_flank = 10, 30
    assert dict(c.core) == {"PF1": 1}
    assert dict(c.flank) == {"PF1": 1, "G1": 1, "PF2": 1}

    from common_core.clustering.weights import enrichment_from_counts

    table = {label: (nc, nf, w) for label, nc, nf, w in c.table()}
    want = enrichment_from_counts([1, 0, 0], [1, 1, 1], 10, 30)
    assert [table[x][2] for x in ("PF1", "G1", "PF2")] == pytest.approx(want.tolist())
    assert table["PF1"][:2] == (1, 1)


def test_count_cds_labels_projected_vocab_ignores_gapfill_sources():
    rows = [
        (1, ROLE_CORE, "PFAM", "PF1", "IPR1", 0, 100),
        (1, ROLE_CORE, "GENE3D", "G1", "", 300, 400),
    ]
    c = count_cds_labels(rows, sources=PROD, vocab=VOCAB_IPR_PROJECTED)
    assert dict(c.core) == {"IPR1": 1}


@pytest.mark.parametrize("bad", ["mibig_v4.0", "MIBiG", "MGnify_Assemblies_v5"])
def test_enrichment_refuses_mibig_and_metagenomes(bad):
    with pytest.raises(ValueError, match="must not be learned"):
        check_datasets(["catalogue_x", bad])
    assert check_datasets(["catalogue_x"]) == ("catalogue_x",)


# ── Run sha + weight alignment ──────────────────────────────────────────────

_SHA = {
    "sources": ("NCBIFAM", "PFAM"),
    "weights": (0.5, 0.5),
    "knn_k": 12,
    "leiden_resolutions": (0.03, 0.08, 0.15, 0.25),
    "seed": 42,
    "ibgc_etag": "10:99",
    "domain_etag": "500:999",
    "domain_vocab": "IPR_PROJECTED",
}


def test_default_dice_run_sha_is_unchanged():
    payload = (
        "sources=NCBIFAM,PFAM|vocab=IPR_PROJECTED|weights=0.500000,0.500000|k=12|"
        "res=0.030000,0.080000,0.150000,0.250000|seed=42|ibgc_etag=10:99|"
        "domain_etag=500:999"
    )
    assert _compute_run_sha(**_SHA) == hashlib.sha256(payload.encode()).hexdigest()
    assert _compute_run_sha(**_SHA, prune_below=0.1) != _compute_run_sha(**_SHA)


def test_cosine_run_sha_keys_enrichment_and_weights():
    cos = dict(_SHA, similarity_metric="cosine_idf_enrich", enrichment_version="v1")
    base = _compute_run_sha(**cos, weights_sha="a")
    assert base != _compute_run_sha(**_SHA)
    assert base != _compute_run_sha(**cos, weights_sha="b")
    assert base != _compute_run_sha(
        **dict(cos, enrichment_version="v2"), weights_sha="a"
    )
    # idf_exponent: 1.0 keeps the pre-amendment sha, anything else changes it;
    # Dice ignores it.
    assert _compute_run_sha(**cos, weights_sha="a", idf_exponent=1.0) == base
    assert _compute_run_sha(**cos, weights_sha="a", idf_exponent=0.5) != base
    assert _compute_run_sha(**_SHA, idf_exponent=0.5) == _compute_run_sha(**_SHA)


def test_metric_run_defaults():
    from discovery.services.clustering.run_support import metric_run_defaults

    assert metric_run_defaults("dice") == ((0.5, 0.5), 1.0)
    # Dice has no feature weights: an exponent is ignored, weights are kept.
    assert metric_run_defaults("dice", [0.7, 0.3], 0.5) == ((0.7, 0.3), 1.0)
    assert metric_run_defaults("cosine_idf_enrich") == ((0.6, 0.4), 0.5)
    assert metric_run_defaults("cosine_idf_enrich", [0.5, 0.5], 1.0) == (
        (0.5, 0.5),
        1.0,
    )


def test_align_weights_reorders_by_label_and_rejects_unknown():
    src = np.empty(2, dtype=object)
    src[0], src[1] = ("A", "B"), ("A", "C")
    dst = np.empty(2, dtype=object)
    dst[0], dst[1] = ("A", "C"), ("A", "B")
    got = _align_weights(src, np.array([1.0, 2.0]), dst)
    assert got.tolist() == [2.0, 1.0]
    bad = np.empty(1, dtype=object)
    bad[0] = ("X", "Y")
    with pytest.raises(ValueError, match="no persisted weight"):
        _align_weights(src, np.array([1.0, 2.0]), bad)
