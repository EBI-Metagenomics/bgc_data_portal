"""NPClassifier labels: ontology load, staged-bundle loading, iBGC aggregation,
the ``npc_terms`` filter, the tree endpoint and the detail payload.

The TSV package mirrors ``test_load_discovery_data`` with SanntiS 1.0 columns
(``score`` / ``probability`` / ``attributes_json``) and a ``bgc_np_classes.tsv``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from discovery.models import (
    IbgcNpcLabel,
    IntegratedBgc,
    NpcTerm,
    NpcTermEdge,
    SourceBgcNpcLabel,
    SourceBgcPrediction,
)
from discovery.services.clustering.integrated import build_integrated_bgcs
from discovery.services.ingestion.loader import run_pipeline
from discovery.services.npc import (
    aggregate_ibgc_npc_labels,
    build_npc_sunburst,
    expand_term_ids,
    load_npc_ontology,
)
from django.test import Client

CONTIG_SHA = hashlib.sha256(b"contig-npc").hexdigest()
PK = "NPC:pathway:polyketides"
AA = "NPC:pathway:amino_acids_and_peptides"
MACRO = "NPC:superclass:macrolides"
# β-lactams has a single parent (Oligopeptides hangs under both AA and Polyketides)
BLAC = "NPC:superclass:beta_lactams"
TERP = "NPC:pathway:terpenoids"


def _write_tsvs(data_dir: Path) -> None:
    attrs = json.dumps(
        {"bgc_class": "NRPS", "n_orfs": "16", "npc_pathway": "Polyketides"}
    )
    (data_dir / "detectors.tsv").write_text(
        "name\ttool\tversion\n"
        "SanntiSv1.0.0\tSanntiS\t1.0.0\n"
        "antiSMASH v8\tantiSMASH\t8.0.1\n"
        "mibig:5.0\tmibig\t5.0\n"
    )
    (data_dir / "assemblies.tsv").write_text(
        "assembly_accession\torganism_name\tsource\tassembly_type\tbiome_path\tassembly_size_mb\n"
        "GCA_000001.1\tStreptomyces test\ttest__1\t2\troot.Environmental\t5.0\n"
    )
    (data_dir / "contigs.tsv").write_text(
        "assembly_accession\tsequence_sha256\taccession\tlength\ttaxonomy_path\n"
        f"GCA_000001.1\t{CONTIG_SHA}\tcontig_1\t60000\tBacteria.Actinomycetota\n"
    )
    # iBGC A: SanntiS 1000-5000 (confident Polyketides / Macrolides) + antiSMASH overlap
    # iBGC B: SanntiS 10000-14000 (non-confident Terpenoids)
    # iBGC C: validated MIBiG region 20000-30000 (curated AA pathway + Oligopeptides)
    (data_dir / "bgcs.tsv").write_text(
        "contig_sha256\tdetector_name\tstart_position\tend_position\tclassification_path\t"
        "is_partial\tis_validated\tscore\tprobability\tattributes_json\n"
        f"{CONTIG_SHA}\tSanntiSv1.0.0\t1000\t5000\tPolyketide\tfalse\tfalse\t0.8120\t0.9500\t{attrs}\n"
        f"{CONTIG_SHA}\tantiSMASH v8\t1200\t4800\tT1PKS\tfalse\tfalse\t\t\t\n"
        f"{CONTIG_SHA}\tSanntiSv1.0.0\t10000\t14000\tTerpene\tfalse\tfalse\t0.3300\t0.5100\t\n"
        f"{CONTIG_SHA}\tmibig:5.0\t20000\t30000\tNRP\tfalse\ttrue\t\t\t\n"
    )
    (data_dir / "bgc_np_classes.tsv").write_text(
        "contig_sha256\tbgc_start\tbgc_end\tdetector_name\tnp_term_id\tlevel\tname\trank\tscore\tconfident\tsource\n"
        f"{CONTIG_SHA}\t1000\t5000\tSanntiSv1.0.0\t{PK}\tpathway\tPolyketides\t1\t0.9495\ttrue\tpredicted\n"
        f"{CONTIG_SHA}\t1000\t5000\tSanntiSv1.0.0\t{MACRO}\tsuperclass\tMacrolides\t1\t0.9725\ttrue\tpredicted\n"
        f"{CONTIG_SHA}\t10000\t14000\tSanntiSv1.0.0\t{TERP}\tpathway\tTerpenoids\t1\t0.5771\tfalse\tpredicted\n"
        f"{CONTIG_SHA}\t20000\t30000\tmibig:5.0\t{AA}"
        f"\tpathway\tAmino acids and Peptides\t1\t\ttrue\tcurated\n"
        f"{CONTIG_SHA}\t20000\t30000\tmibig:5.0\t{BLAC}\tsuperclass\tβ-lactams\t1\t\ttrue\tcurated\n"
        f"{CONTIG_SHA}\t20000\t30000\tmibig:5.0\tNPC:class:does_not_exist\tclass\tNope\t1\t\ttrue\tcurated\n"
        f"{CONTIG_SHA}\t40000\t41000\tSanntiSv1.0.0\t{PK}\tpathway\tPolyketides\t1\t\ttrue\tpredicted\n"
    )


@pytest.fixture
def loaded(tmp_path, db) -> Path:
    _write_tsvs(tmp_path)
    run_pipeline(tmp_path, truncate=False, skip_stats=True)
    build_integrated_bgcs()
    return tmp_path


@pytest.mark.django_db
def test_ontology_loads_idempotently():
    counts = load_npc_ontology()
    assert counts == {"terms": 777, "edges": 792}
    assert load_npc_ontology() == counts
    assert NpcTerm.objects.filter(level="pathway").count() == 7
    assert NpcTermEdge.objects.filter(child_id=MACRO).count() == 2
    assert expand_term_ids([PK]) >= {PK, MACRO}
    assert TERP not in expand_term_ids([PK])


@pytest.mark.django_db
def test_loader_reads_scores_and_labels(loaded):
    sanntis = SourceBgcPrediction.objects.get(
        bgc_range__startswith=1000, detector__tool="SanntiS"
    )
    assert (sanntis.score, sanntis.probability) == (0.812, 0.95)
    assert sanntis.attributes["bgc_class"] == "NRPS"
    anti = SourceBgcPrediction.objects.get(detector__tool="antiSMASH")
    assert anti.score is None and anti.probability is None and anti.attributes is None
    # 5 valid rows; the unknown term and the unknown BGC are skipped
    assert SourceBgcNpcLabel.objects.count() == 5
    lab = SourceBgcNpcLabel.objects.get(source_bgc=sanntis, term_id=PK)
    assert (lab.score, lab.confident, lab.source, lab.rank) == (
        0.9495,
        True,
        "predicted",
        1,
    )
    curated = SourceBgcNpcLabel.objects.filter(source="curated")
    assert curated.count() == 2 and all(
        c.confident and c.score is None for c in curated
    )


@pytest.mark.django_db
def test_ibgc_aggregation(loaded):
    assert IntegratedBgc.objects.count() == 3
    by_term = {
        (lab.ibgc.bgc_range.lower, lab.term_id): lab
        for lab in IbgcNpcLabel.objects.select_related("ibgc")
    }
    assert set(by_term) == {
        (1000, PK),
        (1000, MACRO),
        (10000, TERP),
        (20000, AA),
        (20000, BLAC),
    }
    a = by_term[(1000, PK)]
    assert (
        a.confident
        and a.score == 0.9495
        and a.sources == ["predicted"]
        and a.detector_tools == ["SanntiS"]
    )
    assert by_term[(10000, TERP)].confident is False
    assert by_term[(20000, AA)].sources == ["curated"] and by_term[
        (20000, AA)
    ].detector_tools == ["mibig"]
    # rebuilding is idempotent
    assert aggregate_ibgc_npc_labels() == 5
    assert IbgcNpcLabel.objects.count() == 5


def _ids(resp) -> set[int]:
    assert resp.status_code == 200, resp.content[:300]
    return {row["id"] for row in resp.json()["items"]}


@pytest.mark.django_db
def test_npc_terms_filter_expands_descendants_and_confidence(loaded):
    c = Client()
    starts = {i.id: i.bgc_range.lower for i in IntegratedBgc.objects.all()}
    pk_ids = _ids(c.get("/api/discovery/ibgcs/roster/", {"npc_terms": PK}))
    assert {starts[i] for i in pk_ids} == {1000}
    # superclass selection matches the iBGC labelled with it
    assert {
        starts[i]
        for i in _ids(c.get("/api/discovery/ibgcs/roster/", {"npc_terms": MACRO}))
    } == {1000}
    # default confident-only hides the non-confident Terpenoids call
    assert _ids(c.get("/api/discovery/ibgcs/roster/", {"npc_terms": TERP})) == set()
    terp_all = _ids(
        c.get(
            "/api/discovery/ibgcs/roster/",
            {"npc_terms": TERP, "npc_confident": "false"},
        )
    )
    assert {starts[i] for i in terp_all} == {10000}
    # OR across the selection, curated labels included
    both = _ids(c.get("/api/discovery/ibgcs/roster/", {"npc_terms": f"{PK},{AA}"}))
    assert {starts[i] for i in both} == {1000, 20000}
    # count endpoint agrees and treats the filter as active
    resp = c.get("/api/discovery/ibgcs/count/", {"npc_terms": PK})
    assert resp.status_code == 200 and resp.json()["exact_count"] == 1
    # unknown term matches nothing
    assert (
        _ids(c.get("/api/discovery/ibgcs/roster/", {"npc_terms": "NPC:pathway:nope"}))
        == set()
    )


@pytest.mark.django_db
def test_npc_tree_endpoint(loaded):
    from django.core.cache import cache

    cache.delete("discovery:npc-tree:v1")
    resp = Client().get("/api/discovery/filters/npc-tree/")
    assert resp.status_code == 200
    tree = resp.json()
    by_name = {n["name"]: n for n in tree}
    assert len(tree) == 8 and tree[0]["level"] == "pathway"
    pk = by_name["Polyketides"]
    assert (pk["term_id"], pk["count"], pk["confident_count"]) == (PK, 1, 1)
    terp = by_name["Terpenoids"]
    assert (terp["count"], terp["confident_count"]) == (1, 0)
    macro = next(ch for ch in pk["children"] if ch["name"] == "Macrolides")
    assert macro["level"] == "superclass" and macro["count"] == 1
    assert all(ch["level"] == "class" for ch in macro["children"])


@pytest.mark.django_db
def test_detail_lists_labels_and_member_scores(loaded):
    ibgc = IntegratedBgc.objects.get(bgc_range__startswith=1000)
    resp = Client().get(f"/api/discovery/ibgcs/{ibgc.id}/")
    assert resp.status_code == 200
    body = resp.json()
    labels = {lab["term_id"]: lab for lab in body["npc_labels"]}
    assert set(labels) == {PK, MACRO}
    assert (
        labels[PK]["name"] == "Polyketides"
        and labels[PK]["confident"]
        and labels[PK]["sources"] == ["predicted"]
    )
    sanntis = next(m for m in body["member_bgcs"] if m["detector_name"] == "SanntiS")
    assert (sanntis["score"], sanntis["probability"], sanntis["detector_version"]) == (
        0.812,
        0.95,
        "1.0.0",
    )
    assert sanntis["classification_path"] == "Polyketide"


@pytest.mark.django_db
def test_npc_sunburst_counts_confident_chains(loaded):
    nodes = {n["id"]: n for n in build_npc_sunburst(IntegratedBgc.objects.all())}
    assert nodes[PK]["count"] == 2  # the pathway label + the Macrolides chain
    assert (
        nodes[f"{PK}/{MACRO}"]["parent"] == PK and nodes[f"{PK}/{MACRO}"]["count"] == 1
    )
    assert TERP not in nodes  # non-confident
    # AA label + the AA/Macrolides chain (multi-parent) + AA/β-lactams
    assert nodes[AA]["count"] == 3


@pytest.mark.django_db
def test_legacy_bundle_without_new_columns_still_loads(tmp_path):
    _write_tsvs(tmp_path)
    (tmp_path / "bgc_np_classes.tsv").unlink()
    lines = (tmp_path / "bgcs.tsv").read_text().splitlines()
    header = lines[0].split("\t")[:7]
    (tmp_path / "bgcs.tsv").write_text(
        "\n".join(
            ["\t".join(header)] + ["\t".join(ln.split("\t")[:7]) for ln in lines[1:]]
        )
        + "\n"
    )
    run_pipeline(tmp_path, truncate=False, skip_stats=True)
    build_integrated_bgcs()
    assert SourceBgcPrediction.objects.count() == 4
    assert SourceBgcPrediction.objects.filter(score__isnull=False).count() == 0
    assert SourceBgcNpcLabel.objects.count() == 0 and IbgcNpcLabel.objects.count() == 0
    resp = Client().get("/api/discovery/ibgcs/roster/", {"npc_terms": PK})
    assert resp.status_code == 200 and resp.json()["items"] == []
