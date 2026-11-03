"""DB tests for the ADR 0003 similarity plumbing (Phase 2).

Locks:

1. ``build_enrichment_counts`` classifies CDS exactly as the benchmark did:
   core = inside a GECCO/SanntiS iBGC; flank = outside any iBGC plus the
   antiSMASH overhang of an absorbed prediction; antiSMASH-only iBGCs and
   other assembly sources contribute nothing.
2. The matrix builders: ``IPR_PROJECTED`` ignores Gene3D/PRINTS/ProSite;
   ``IPR_GAPFILLED`` adds only the hits that fill a gap.
3. End to end: ``export_clustering_inputs --similarity-metric cosine_idf_enrich``
   ships species-dereplicated IDF × enrichment weights; ``bgc-cluster run``
   consumes them; ``import_clustering_results`` records the metric on the
   ``ClusteringRun`` and persists the weights, which the rebuilt scoring
   cache reuses verbatim. A Dice export / import still carries no weights.
4. The in-portal pipeline records and persists the same for a cosine run.

Requires igraph/leidenalg for the clustering steps.
"""

from __future__ import annotations

import pytest

pytest.importorskip("igraph")
pytest.importorskip("leidenalg")

from pathlib import Path

import numpy as np
from discovery.models import ClusteringRun, DomainEnrichment, IntegratedBgc
from discovery.services.clustering.adjacency import build_ibgc_adjacency_pair_matrix
from discovery.services.clustering.enrichment import (
    build_enrichment_counts,
    save_enrichment_table,
)
from discovery.services.clustering.feature_weights import load_run_weights
from discovery.services.clustering.ibgc_scoring import load_scoring_cache
from discovery.services.clustering.membership import (
    VOCAB_IPR_GAPFILLED,
    VOCAB_IPR_PROJECTED,
    build_ibgc_domain_matrix,
)
from django.core.management import call_command
from django.test import override_settings
from tests.factories.discovery_models import (
    AssemblySourceFactory,
    ConsensusBgcFactory,
    ContigCdsFactory,
    ContigDomainFactory,
    DashboardAssemblyFactory,
    DashboardContigFactory,
    DashboardDetectorFactory,
    IntegratedBgcFactory,
    SourceBgcPredictionFactory,
)

COSINE = "cosine_idf_enrich"
CATALOGUE = "catalogue_t"


# ── Fixture helpers ─────────────────────────────────────────────────────────


@pytest.fixture
def dets():
    return {
        tool: DashboardDetectorFactory(
            name=f"{tool} v1", tool=tool, tool_name_code=tool[:3].upper()
        )
        for tool in ("GECCO", "SanntiS", "antiSMASH", "MIBiG")
    }


def _contig(source: str, taxonomy: str = "Bacteria.P.sp1"):
    asm = DashboardAssemblyFactory(source=AssemblySourceFactory(name=source))
    return DashboardContigFactory(assembly=asm, taxonomy_path=taxonomy)


def _cds(contig, start: int, hits):
    cds = ContigCdsFactory(contig=contig, start_pos=start, end_pos=start + 900)
    for db, acc, ipr, s, e in hits:
        ContigDomainFactory(
            cds=cds,
            domain_acc=acc,
            interpro_entry_acc=ipr,
            ref_db=db,
            start_position=s,
            end_position=e,
        )
    return cds


def _locus(
    contig,
    start: int,
    cds_hits,
    dets,
    *,
    tools=("GECCO",),
    overhang=(),
    partial=False,
    validated=False,
):
    """One iBGC over ``cds_hits`` (1 kb per CDS). With ``antiSMASH`` in
    ``tools`` its prediction also covers the ``overhang`` CDS that follow."""
    n, m = len(cds_hits), len(overhang)
    chain_end = start + n * 1000 - 50
    full_end = start + (n + m) * 1000 - 50
    cbgc = ConsensusBgcFactory(contig=contig, start_pos=start, end_pos=full_end)
    ibgc = IntegratedBgcFactory(
        cbgc=cbgc,
        contig=contig,
        start_pos=start,
        end_pos=chain_end,
        source_tools=sorted(set(tools)),
    )
    for tool in tools:
        SourceBgcPredictionFactory(
            contig=contig,
            detector=dets[tool],
            cbgc=cbgc,
            integrated_bgc=ibgc,
            start_pos=start,
            end_pos=full_end if tool == "antiSMASH" else chain_end,
            is_partial=partial,
            is_validated=validated,
        )
    for i, hits in enumerate(list(cds_hits) + list(overhang)):
        _cds(contig, start + i * 1000, hits)
    return ibgc


def _pf(acc, ipr="", s=0, e=100):
    return ("PFAM", acc, ipr, s, e)


def _g3d(acc, s, e, ipr=""):
    return ("GENE3D", acc, ipr, s, e)


# ── 1. Enrichment core / flank classification ───────────────────────────────


@pytest.mark.django_db
def test_enrichment_roles_match_the_benchmark_definition(dets):
    a = _contig(CATALOGUE)
    _locus(
        a,
        1000,
        [
            [_pf("PF_A", "IPR_A"), _g3d("G_blocked", 10, 90)],
            [_pf("PF_B"), _g3d("G_fill", 200, 300)],
            [_pf("PF_C")],
        ],
        dets,
        tools=("GECCO", "antiSMASH"),
        overhang=[[_pf("PF_TCS")]],  # c4: antiSMASH overhang → flank
    )
    _cds(a, 20_000, [_pf("PF_TCS"), ("PRINTS", "PR_X", "", 300, 400)])  # outside
    _cds(a, 25_000, [])  # outside, no domains: counts towards n_flank only
    _locus(a, 30_000, [[_pf("PF_ASM")]], dets, tools=("antiSMASH",))  # neither
    other = _contig("other_t")
    _cds(other, 1000, [_pf("PF_OTHER")])  # not in the selected datasets

    c = build_enrichment_counts(datasets=[CATALOGUE])
    assert (c.n_core, c.n_flank) == (3, 3)
    assert dict(c.core) == {"IPR_A": 1, "PF_B": 1, "G_fill": 1, "PF_C": 1}
    assert dict(c.flank) == {"PF_TCS": 2, "PR_X": 1}

    n = save_enrichment_table("t0", c, vocab=VOCAB_IPR_GAPFILLED, datasets=[CATALOGUE])
    assert n == 6
    w = dict(
        DomainEnrichment.objects.filter(version="t0").values_list("label", "weight")
    )
    assert w["PF_B"] > 0.5 > w["PF_TCS"]
    meta = {
        (vocab, tuple(datasets))
        for vocab, datasets in DomainEnrichment.objects.filter(
            version="t0"
        ).values_list("vocab", "datasets")
    }
    assert meta == {(VOCAB_IPR_GAPFILLED, (CATALOGUE,))}
    with pytest.raises(ValueError, match="already exists"):
        save_enrichment_table("t0", c, vocab=VOCAB_IPR_GAPFILLED, datasets=[CATALOGUE])


@pytest.mark.django_db
def test_builders_projected_vs_gapfilled(dets):
    a = _contig(CATALOGUE)
    ibgc = _locus(
        a,
        1000,
        [
            [_pf("PF_A", "IPR_A"), _g3d("G_blocked", 10, 90)],
            [_pf("PF_B"), _g3d("G_fill", 200, 300)],
        ],
        dets,
    )
    M, ids, accs = build_ibgc_domain_matrix(ibgc_ids_subset=[ibgc.id])
    assert accs.tolist() == ["IPR_A", "PF_B"]
    M, ids, accs = build_ibgc_domain_matrix(
        ibgc_ids_subset=[ibgc.id], vocab=VOCAB_IPR_GAPFILLED
    )
    assert accs.tolist() == ["G_fill", "IPR_A", "PF_B"]
    assert M.toarray().tolist() == [[1, 1, 1]]

    _, _, pairs = build_ibgc_adjacency_pair_matrix(ibgc_ids_subset=[ibgc.id])
    assert pairs.tolist() == [("IPR_A", "PF_B")]
    _, _, pairs = build_ibgc_adjacency_pair_matrix(
        ibgc_ids_subset=[ibgc.id], vocab=VOCAB_IPR_GAPFILLED
    )
    # Sequence IPR_A | PF_B, G_fill → pairs (IPR_A, PF_B), (G_fill, PF_B).
    assert sorted(pairs.tolist()) == [("G_fill", "PF_B"), ("IPR_A", "PF_B")]


# ── 3 / 4. End to end ───────────────────────────────────────────────────────

FAM_A = [
    [_pf("PF_A1", "IPR_A1"), _g3d("G_A1", 10, 90)],
    [_pf("PF_A2"), _g3d("G_A2", 200, 300)],
    [_pf("PF_A3")],
]
FAM_B = [[_pf("PF_B1")], [_pf("PF_B2")], [_pf("PF_B3"), _pf("PF_B4", s=200, e=300)]]


def _corpus(dets) -> dict:
    """8 catalogue loci (2 families, 6 species), 1 validated, 1 partial.

    Three family-A loci share species sp0, so the species-dereplicated df
    differs from the raw row count.
    """
    for i in range(8):
        contig = _contig(CATALOGUE, taxonomy=f"Bacteria.P.sp{max(0, i - 2)}")
        _locus(
            contig,
            1000,
            FAM_A if i < 4 else FAM_B,
            dets,
            tools=("GECCO", "antiSMASH"),
            overhang=[[_pf("PF_TCS")]],
        )
        _cds(contig, 20_000, [_pf("PF_TCS"), ("PRINTS", "PR_X", "", 300, 400)])
    validated = _locus(
        _contig("mibig_t", taxonomy=""),
        1000,
        FAM_A,
        dets,
        tools=("MIBiG",),
        validated=True,
    )
    partial = _locus(
        _contig(CATALOGUE, taxonomy="Bacteria.P.sp9"),
        1000,
        FAM_B[:2],
        dets,
        tools=("SanntiS",),
        partial=True,
    )
    save_enrichment_table(
        "t1",
        build_enrichment_counts(datasets=[CATALOGUE]),
        vocab=VOCAB_IPR_GAPFILLED,
        datasets=[CATALOGUE],
    )
    return {"validated": validated, "partial": partial}


def _export(tag: str, **opts) -> Path:
    from django.conf import settings

    call_command("export_clustering_inputs", run_tag=tag, **opts)
    return Path(settings.CLUSTERING_ARTIFACTS_DIR) / "exports" / f"{tag}.tgz"


def _hpc(inp: Path) -> Path:
    from common_core.clustering.cli import main

    out = inp.with_name(inp.name.replace(".tgz", "_out.tgz"))
    assert main(["run", "--input", str(inp), "--output", str(out)]) == 0
    return out


@pytest.mark.django_db
def test_cosine_export_hpc_import_round_trip(dets, tmp_path):
    from common_core.clustering import weights as W
    from common_core.clustering.io import read_inputs_tarball, read_outputs_tarball

    fx = _corpus(dets)
    with override_settings(CLUSTERING_ARTIFACTS_DIR=tmp_path):
        inp = _export("cos", similarity_metric=COSINE, enrichment_version="t1")
        inputs = read_inputs_tarball(inp)
        p = inputs.params
        assert (p.similarity_metric, p.domain_vocab, p.enrichment_version) == (
            COSINE,
            VOCAB_IPR_GAPFILLED,
            "t1",
        )
        # ADR 0003 amendment defaults for cosine runs.
        assert (p.idf_exponent, tuple(p.score_weights)) == (
            W.COSINE_IDF_EXPONENT,
            W.COSINE_SCORE_WEIGHTS,
        )
        accs = inputs.domain_accs.tolist()
        assert "G_A2" in accs and "G_A1" not in accs and "PR_X" not in accs

        # Weights = species-dereplicated IDF ** 0.5 over the primaries × enrichment.
        tax = dict(IntegratedBgc.objects.values_list("id", "contig__taxonomy_path"))
        groups = np.asarray(
            [tax[int(i)] or "NA" for i in inputs.ibgc_ids], dtype=object
        )
        table = dict(
            DomainEnrichment.objects.filter(version="t1").values_list("label", "weight")
        )
        e_dom = W.enrichment_vector(accs, table)
        np.testing.assert_allclose(
            inputs.domain_weights,
            np.sqrt(W.idf_weights(inputs.M_domains, groups)) * e_dom,
            rtol=1e-6,
        )
        np.testing.assert_allclose(
            inputs.pair_weights,
            np.sqrt(W.idf_weights(inputs.M_pairs, groups))
            * W.pair_enrichment(inputs.pair_vocab.tolist(), accs, e_dom),
            rtol=1e-6,
        )
        assert fx["partial"].id in inputs.partials_ibgc_ids.tolist()
        # Family domains carry weight. The antiSMASH overhang (PF_TCS) lies
        # outside every iBGC range, so it never enters the vocabulary.
        w = dict(zip(accs, inputs.domain_weights.tolist()))
        assert min(w["IPR_A1"], w["G_A2"], w["PF_B1"]) > 0.0
        assert "PF_TCS" not in w
        # Family A: 5 rows (4 primaries + the validated one) but only 3
        # groups (sp0 ×3, sp1, MIBiG "NA"); family B: 4 rows in 4 species.
        # Counting df per species makes A the rarer family despite more rows.
        idf = W.idf_weights(inputs.M_domains, groups)
        assert idf[accs.index("PF_A3")] > idf[accs.index("PF_B1")]

        out = _hpc(inp)
        sha = read_outputs_tarball(out)["run"]["sha256"]
        call_command("import_clustering_results", str(out), skip_discovery_stats=True)

        run = ClusteringRun.objects.get(sha256=sha)
        assert run.similarity_metric == COSINE
        assert run.domain_vocab == VOCAB_IPR_GAPFILLED
        assert run.enrichment_version == "t1"
        assert run.idf_exponent == W.COSINE_IDF_EXPONENT
        assert run.score_weights == list(W.COSINE_SCORE_WEIGHTS)
        assert (run.prune_below, run.min_projection_similarity) == (0.05, 0.1)

        art = tmp_path / sha[:12]
        rw = load_run_weights(art)
        np.testing.assert_array_equal(rw.domain_weights, inputs.domain_weights)
        assert rw.domain_accs.tolist() == accs

        cache = load_scoring_cache(art)
        assert cache["domain_accs"].tolist() == accs
        np.testing.assert_array_equal(cache["domain_weights"], inputs.domain_weights)
        np.testing.assert_array_equal(cache["pair_weights"], inputs.pair_weights)

        fx["validated"].refresh_from_db()
        assert fx["validated"].novelty_score == pytest.approx(0.0, abs=1e-6)
        assert fx["validated"].gene_cluster_family

        # Dice: no weights anywhere, run recorded as Dice.
        out_d = _hpc(_export("dice"))
        sha_d = read_outputs_tarball(out_d)["run"]["sha256"]
        assert sha_d != sha
        call_command("import_clustering_results", str(out_d), skip_discovery_stats=True)
        run_d = ClusteringRun.objects.get(sha256=sha_d)
        assert (run_d.similarity_metric, run_d.domain_vocab) == (
            "dice",
            VOCAB_IPR_PROJECTED,
        )
        assert (run_d.idf_exponent, run_d.score_weights) == (1.0, [0.5, 0.5])
        assert load_run_weights(tmp_path / sha_d[:12]) is None
        assert load_scoring_cache(tmp_path / sha_d[:12])["domain_weights"] is None


@pytest.mark.django_db
def test_cosine_export_full_idf_is_the_benchmark_reference(dets, tmp_path):
    """``--idf-exponent 1`` reproduces the pre-amendment (benchmark) weights."""
    from common_core.clustering import weights as W
    from common_core.clustering.io import read_inputs_tarball

    _corpus(dets)
    with override_settings(CLUSTERING_ARTIFACTS_DIR=tmp_path):
        half = read_inputs_tarball(
            _export("half", similarity_metric=COSINE, enrichment_version="t1")
        )
        full = read_inputs_tarball(
            _export(
                "full",
                similarity_metric=COSINE,
                enrichment_version="t1",
                idf_exponent=1.0,
                score_weights=[0.5, 0.5],
            )
        )
    assert full.params.idf_exponent == 1.0
    assert tuple(full.params.score_weights) == (0.5, 0.5)
    tax = dict(IntegratedBgc.objects.values_list("id", "contig__taxonomy_path"))
    groups = np.asarray([tax[int(i)] or "NA" for i in full.ibgc_ids], dtype=object)
    table = dict(
        DomainEnrichment.objects.filter(version="t1").values_list("label", "weight")
    )
    e_dom = W.enrichment_vector(full.domain_accs.tolist(), table)
    idf = W.idf_weights(full.M_domains, groups)
    np.testing.assert_array_equal(full.domain_weights, W.combine(idf, e_dom))
    np.testing.assert_allclose(half.domain_weights**2, idf * e_dom**2, rtol=1e-5)


@pytest.mark.django_db
def test_import_rejects_cosine_tarball_without_weights(dets, tmp_path):
    from common_core.clustering.io import read_outputs_tarball

    _corpus(dets)
    with override_settings(CLUSTERING_ARTIFACTS_DIR=tmp_path):
        out = _hpc(_export("cos", similarity_metric=COSINE, enrichment_version="t1"))
        payload = read_outputs_tarball(out)

    from discovery.management.commands.import_clustering_results import (
        _run_weights_from_payload,
    )
    from django.core.management.base import CommandError

    assert _run_weights_from_payload(payload, COSINE) is not None
    payload["pair_weights"] = None
    with pytest.raises(CommandError, match="lacks"):
        _run_weights_from_payload(payload, COSINE)


@pytest.mark.django_db
def test_in_portal_pipeline_cosine_run(dets, tmp_path):
    from discovery.services.clustering.pipeline import run_clustering_pipeline

    fx = _corpus(dets)
    with override_settings(CLUSTERING_ARTIFACTS_DIR=tmp_path):
        with pytest.raises(ValueError, match="needs an enrichment_version"):
            run_clustering_pipeline(similarity_metric=COSINE)
        # t1 was learned on IPR_GAPFILLED: a run on another vocab must refuse it.
        with pytest.raises(ValueError, match="learned on vocab"):
            run_clustering_pipeline(
                similarity_metric=COSINE,
                domain_vocab=VOCAB_IPR_PROJECTED,
                enrichment_version="t1",
            )

        dice = run_clustering_pipeline(apply=False, seed=42)
        res = run_clustering_pipeline(
            similarity_metric=COSINE,
            domain_vocab=VOCAB_IPR_GAPFILLED,
            enrichment_version="t1",
            apply=True,
            seed=42,
        )
        assert "error" not in res, res
        assert res["sha256"] != dice["sha256"]
        run = ClusteringRun.objects.get(pk=res["run_pk"])
        assert (run.similarity_metric, run.enrichment_version) == (COSINE, "t1")

        art = Path(res["artifacts_dir"])
        rw = load_run_weights(art)
        assert rw is not None and len(rw.domain_weights) == res["n_domains"]
        cache = load_scoring_cache(art)
        np.testing.assert_array_equal(cache["domain_weights"], rw.domain_weights)

        fx["validated"].refresh_from_db()
        assert fx["validated"].novelty_score == pytest.approx(0.0, abs=1e-6)


# ── Phase 3: every consumer scores a cosine run with the run's weights ──────

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.mark.django_db
def test_consumers_score_cosine_run_with_its_weights(dets, tmp_path):
    from types import SimpleNamespace

    from common_core.clustering.io import read_inputs_tarball, read_outputs_tarball
    from common_core.clustering.similarity import compute_composite_similarity
    from discovery.services.asset_upload.project import _project_against_run
    from discovery.services.asset_upload.schemas import AssetCds, AssetDomain
    from discovery.services.clustering import similarity_on_demand as sod
    from discovery.services.clustering.ibgc_scoring import project_partial_ibgcs
    from discovery.services.query.criteria import (
        ArchitectureParams,
        SimilarParams,
        architecture_top,
        similar_top,
    )

    fx = _corpus(dets)
    with override_settings(CLUSTERING_ARTIFACTS_DIR=tmp_path, CACHES=LOCMEM):
        inp = _export("cos", similarity_metric=COSINE, enrichment_version="t1")
        out = _hpc(inp)
        call_command("import_clustering_results", str(out), skip_discovery_stats=True)
        run = ClusteringRun.objects.get(
            sha256=read_outputs_tarball(out)["run"]["sha256"]
        )
        inputs = read_inputs_tarball(inp)
        sod._active = None

        # Reference: the clustering's own (unpruned) similarity over primaries.
        full = compute_composite_similarity(
            inputs.M_domains,
            inputs.M_pairs,
            prune_below=0.0,
            metric=COSINE,
            domain_weights=inputs.domain_weights,
            pair_weights=inputs.pair_weights,
        ).toarray()
        ids = inputs.ibgc_ids.tolist()

        # Find similar
        cache = sod.get_active_scoring_cache()
        assert cache.similarity_metric == COSINE and cache.X_domains is not None
        seed = ids[0]
        top_ids, top_scores = similar_top(SimilarParams(ibgc_id=seed, k=len(ids) - 1))
        got = dict(zip(top_ids, top_scores))
        for j, nid in enumerate(ids[1:], start=1):
            assert got[nid] == pytest.approx(full[0, j], abs=1e-6)

        # Architecture search: the validated MIBiG locus's own architecture.
        v_row = ids.index(fx["validated"].id)
        arch = ["IPR_A1", "PF_A2", "G_A2", "PF_A3"]
        a_ids, a_scores = architecture_top(
            ArchitectureParams(architecture=arch, weight=0.5, k=len(ids), threshold=0)
        )
        assert dict(zip(a_ids, a_scores))[ids[v_row]] == pytest.approx(1.0, abs=1e-6)

        # Partial projection (portal path) uses the run's metric and threshold.
        # The HPC import already projected the partial; detach it first.
        def _detach():
            IntegratedBgc.objects.filter(pk=fx["partial"].pk).update(
                classification_run=None, gene_cluster_family="", is_partial=False
            )

        hpc_leaf = IntegratedBgc.objects.get(pk=fx["partial"].pk).gene_cluster_family
        _detach()
        res = project_partial_ibgcs(clustering_run_pk=run.pk)
        assert (res["scope"], res["projected"]) == (1, 1)
        fx["partial"].refresh_from_db()
        assert fx["partial"].is_partial
        assert fx["partial"].gene_cluster_family == hpc_leaf  # same as HPC's
        _detach()
        run.min_projection_similarity = 99.0
        run.save(update_fields=["min_projection_similarity"])
        assert project_partial_ibgcs(clustering_run_pk=run.pk)["projected"] == 0

        # Upload projection: a virtual copy of the validated locus lands on it.
        key = ("up", 1, 3000, "MIBiG")
        doms = []
        for i, hits in enumerate(FAM_A):
            for db, acc, ipr, s, e in hits:
                doms.append(
                    AssetDomain(
                        key,
                        f"p{i}",
                        acc,
                        ref_db=db,
                        interpro_entry_acc=ipr,
                        start_position=s,
                        end_position=e,
                    )
                )
        cds = [AssetCds(key, f"p{i}", 1000 * i, 1000 * i + 900, 1) for i in range(3)]
        vibgc = SimpleNamespace(
            cds=cds,
            domains=doms,
            projected=False,
            gene_cluster_family="",
            novelty_score=None,
            domain_novelty=None,
        )
        _project_against_run([vibgc], run)  # threshold still 99 → unprojected
        assert not vibgc.projected
        run.min_projection_similarity = 0.1
        _project_against_run([vibgc], run)
        assert vibgc.projected
        assert vibgc.novelty_score == pytest.approx(0.0, abs=1e-6)  # = validated

        # A cache written for another metric is refused, not silently reused.
        from discovery.services.clustering.ibgc_scoring import SIMILARITY_FILE

        (tmp_path / run.sha256[:12] / "scoring_cache" / SIMILARITY_FILE).write_text(
            '{"similarity_metric": "dice"}'
        )
        sod._active = None
        with pytest.raises(FileNotFoundError, match="written for 'dice'"):
            sod.get_active_scoring_cache()
        sod._active = None
