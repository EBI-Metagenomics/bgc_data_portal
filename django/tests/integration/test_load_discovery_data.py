"""End-to-end ingestion: TSV package → cBGCs/source predictions → iBGCs.

Exercises the real loader (``run_pipeline``) and the iBGC builder
(``build_integrated_bgcs``) against a tiny hand-authored TSV dataset, then
asserts the stable-accession bookkeeping the rest of the portal depends on:

  * cBGC envelopes minted as ``MGYB-XXXXXX`` (Crockford base32, no I/L/O/U)
  * overlapping per-tool predictions collapsed into one cBGC
  * iBGCs minted as ``MGYB-XXXXXX-YY`` and wired back onto their source rows
  * the accession registry resolves both kinds to the live row

No clustering libraries are touched, so this runs in the plain web image.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from discovery.models import (
    ConsensusBgc,
    ContigCds,
    ContigDomain,
    DashboardAssembly,
    DashboardContig,
    DashboardDetector,
    IntegratedBgc,
    SourceBgcPrediction,
)
from discovery.services.accession_registry import AccessionEntityType, resolve
from discovery.services.clustering.integrated import build_integrated_bgcs
from discovery.services.ingestion.loader import run_pipeline

# Crockford base32 alphabet (I, L, O, U omitted).
_C = "[0-9ABCDEFGHJKMNPQRSTVWXYZ]"
CBGC_RE = re.compile(rf"^MGYB-{_C}{{6}}$")
IBGC_RE = re.compile(rf"^MGYB-{_C}{{6}}-{_C}{{2}}$")

CONTIG_SHA = "a" * 64


def _write_tsvs(data_dir: Path) -> None:
    """Write a minimal but complete TSV package for one contig.

    Three predictions on one contig:
      * antiSMASH 1000–5000 and GECCO 1200–4800 overlap → one cBGC, and the
        iBGC build folds the antiSMASH tool tag onto the GECCO chain.
      * a lone antiSMASH 10000–14000 → a second, disjoint cBGC + iBGC.
    """
    (data_dir / "detectors.tsv").write_text(
        "name\ttool\tversion\n"
        "antiSMASH v1\tantiSMASH\t1.0\n"
        "GECCO v1\tGECCO\t1.0\n"
    )
    (data_dir / "assemblies.tsv").write_text(
        "assembly_accession\torganism_name\tsource\tassembly_type\t"
        "biome_path\tassembly_size_mb\n"
        "GCA_000001.1\tStreptomyces test\tmibig__4.0\t2\troot.Environmental\t5.0\n"
    )
    (data_dir / "contigs.tsv").write_text(
        "assembly_accession\tsequence_sha256\taccession\tlength\ttaxonomy_path\n"
        f"GCA_000001.1\t{CONTIG_SHA}\tcontig_1\t20000\tBacteria.Actinomycetota\n"
    )
    (data_dir / "bgcs.tsv").write_text(
        "contig_sha256\tdetector_name\tstart_position\tend_position\t"
        "is_partial\tis_validated\n"
        f"{CONTIG_SHA}\tantiSMASH v1\t1000\t5000\tfalse\tfalse\n"
        f"{CONTIG_SHA}\tGECCO v1\t1200\t4800\tfalse\tfalse\n"
        f"{CONTIG_SHA}\tantiSMASH v1\t10000\t14000\tfalse\tfalse\n"
    )
    (data_dir / "cds.tsv").write_text(
        "contig_sha256\tstart_position\tend_position\tstrand\t"
        "protein_id_str\tprotein_length\n"
        f"{CONTIG_SHA}\t1100\t1400\t1\tcontig_1_1\t100\n"
        f"{CONTIG_SHA}\t1500\t1900\t1\tcontig_1_2\t133\n"
        f"{CONTIG_SHA}\t10100\t10500\t1\tcontig_1_3\t133\n"
    )
    (data_dir / "domains.tsv").write_text(
        "contig_sha256\tprotein_id_str\tdomain_acc\tdomain_name\tref_db\t"
        "start_position\tend_position\tscore\n"
        f"{CONTIG_SHA}\tcontig_1_1\tPF00001\tTest domain\tPFAM\t1\t100\t1e-20\n"
        f"{CONTIG_SHA}\tcontig_1_2\tPF00002\tAnother domain\tPFAM\t5\t120\t1e-15\n"
        f"{CONTIG_SHA}\tcontig_1_3\tPF00003\tThird domain\tPFAM\t1\t130\t1e-30\n"
    )


@pytest.fixture
def ingested(tmp_path) -> Path:
    """Run the loader over the TSV package and return the data dir."""
    _write_tsvs(tmp_path)
    run_pipeline(tmp_path, truncate=False, skip_stats=True)
    return tmp_path


@pytest.mark.django_db
def test_loader_populates_entities_and_collapses_cbgcs(ingested):
    assert DashboardDetector.objects.count() == 2
    assert DashboardAssembly.objects.count() == 1
    assert DashboardContig.objects.count() == 1

    # Three per-tool predictions; the two overlapping ones share a cBGC, so
    # only two disjoint envelopes are minted.
    assert SourceBgcPrediction.objects.count() == 3
    assert ConsensusBgc.objects.count() == 2

    assert ContigCds.objects.count() == 3
    assert ContigDomain.objects.count() == 3

    # Every prediction is anchored to a cBGC envelope.
    assert not SourceBgcPrediction.objects.filter(cbgc__isnull=True).exists()

    # cBGC accessions are stable Crockford base32 ids.
    for acc in ConsensusBgc.objects.values_list("accession", flat=True):
        assert CBGC_RE.match(acc), acc

    # The two overlapping predictions resolve to the same cBGC.
    overlap = SourceBgcPrediction.objects.filter(
        bgc_range__overlap=(1000, 5000)
    ).values_list("cbgc_id", flat=True)
    assert len(set(overlap)) == 1


@pytest.mark.django_db
def test_build_integrated_bgcs_mints_and_wires_ibgcs(ingested):
    result = build_integrated_bgcs()

    n = result["n_ibgcs"]
    assert n > 0
    assert IntegratedBgc.objects.count() == n

    # Stable iBGC accessions, suffixed within their parent cBGC.
    for acc in IntegratedBgc.objects.values_list("accession", flat=True):
        assert IBGC_RE.match(acc), acc

    # Build wires every (non-orphan) source prediction back onto its iBGC.
    assert not SourceBgcPrediction.objects.filter(
        integrated_bgc__isnull=True
    ).exists()

    # The only tools in play are antiSMASH and GECCO, and the overlapping
    # pair is folded into a single iBGC carrying both tool tags.
    all_tools = set()
    for tools in IntegratedBgc.objects.values_list("source_tools", flat=True):
        all_tools.update(tools or [])
    assert all_tools == {"antiSMASH", "GECCO"}
    assert IntegratedBgc.objects.filter(
        source_tools__contains=["GECCO"]
    ).filter(source_tools__contains=["antiSMASH"]).exists()


@pytest.mark.django_db
def test_loader_dedups_duplicate_cds_chemont(tmp_path):
    """Duplicate ``(cds, chemont_id)`` rows must not crash the upsert.

    Regression for ``ProgrammingError: ON CONFLICT DO UPDATE command cannot
    affect row a second time`` — the loader now dedups the batch (last wins).
    """
    from discovery.models import CdsChemOnt

    _write_tsvs(tmp_path)
    (tmp_path / "cds_chemont.tsv").write_text(
        "contig_sha256\tprotein_id_str\tchemont_id\tchemont_name\t"
        "probability\tweight\n"
        f"{CONTIG_SHA}\tcontig_1_1\tCHEMONTID:0001\tTerpenes\t0.9\t0.5\n"
        f"{CONTIG_SHA}\tcontig_1_1\tCHEMONTID:0001\tTerpenes\t0.7\t0.4\n"
    )

    run_pipeline(tmp_path, truncate=False, skip_stats=True)

    rows = CdsChemOnt.objects.filter(chemont_id="CHEMONTID:0001")
    assert rows.count() == 1  # collapsed to one row
    assert rows.first().probability == pytest.approx(0.7)  # last occurrence wins


@pytest.mark.django_db
def test_registry_resolves_minted_accessions(ingested):
    build_integrated_bgcs()

    cbgc = ConsensusBgc.objects.first()
    cres = resolve(cbgc.accession)
    assert cres is not None
    assert cres.kind == AccessionEntityType.CBGC
    assert cres.current_id == cbgc.id
    assert cres.tombstoned is False

    ibgc = IntegratedBgc.objects.first()
    ires = resolve(ibgc.accession)
    assert ires is not None
    assert ires.kind == AccessionEntityType.IBGC
    assert ires.current_id == ibgc.id
    assert ires.tombstoned is False
