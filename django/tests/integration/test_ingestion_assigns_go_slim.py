"""Ingestion populates ``BgcDomain.go_slim`` inline.

Pins the behaviour added so operators no longer need to remember to run
``manage.py load_pfam_go_slim`` after each fresh load. A row whose Pfam
accession exists in the bundled ``pfam2goSlim.json`` must come out of
``load_domains`` with a non-empty ``go_slim``.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from discovery.models import (
    AssemblySource,
    AssemblyType,
    BgcDomain,
    DashboardAssembly,
    DashboardBgc,
    DashboardContig,
    DashboardDetector,
)
from discovery.services.ingestion.loader import load_domains
from discovery.services.go_slim import go_slim_for


def _seed_parent_rows():
    src = AssemblySource.objects.create(name="GTDB")
    assembly = DashboardAssembly.objects.create(
        assembly_accession="A1",
        organism_name="Test sp.",
        source=src,
        assembly_type=AssemblyType.GENOME,
        biome_path="root.Env",
    )
    contig = DashboardContig.objects.create(
        assembly=assembly,
        sequence_sha256=hashlib.sha256(b"c1").hexdigest(),
        accession="CONTIG_1",
        length=10_000,
    )
    detector = DashboardDetector.objects.create(
        name="antiSMASH v7.1",
        tool="antiSMASH",
        version="7.1.0",
        tool_name_code="ANT",
        version_sort_key=710,
    )
    bgc = DashboardBgc.objects.create(
        assembly=assembly,
        contig=contig,
        bgc_accession="MGYB10000001.ANT.1.01",
        start_position=1_000,
        end_position=5_000,
        classification_path="Polyketide",
        detector=detector,
    )
    return contig, bgc


@pytest.mark.django_db
def test_load_domains_populates_go_slim(tmp_path: Path):
    contig, bgc = _seed_parent_rows()

    detector_name = "antiSMASH v7.1"
    bgc_lookup = {
        (contig.sequence_sha256, bgc.start_position, bgc.end_position, detector_name): bgc.id
    }
    cds_lookup: dict = {}

    data_dir = tmp_path
    tsv_path = data_dir / "domains.tsv"
    with open(tsv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            delimiter="\t",
            fieldnames=[
                "contig_sha256",
                "bgc_start",
                "bgc_end",
                "detector_name",
                "protein_id_str",
                "domain_acc",
                "domain_name",
                "domain_description",
                "ref_db",
                "start_position",
                "end_position",
                "score",
                "url",
            ],
        )
        writer.writeheader()
        # PF00001 is in the bundled mapping with a molecular_function slim.
        writer.writerow({
            "contig_sha256": contig.sequence_sha256,
            "bgc_start": bgc.start_position,
            "bgc_end": bgc.end_position,
            "detector_name": detector_name,
            "protein_id_str": "",
            "domain_acc": "PF00001",
            "domain_name": "Pf001",
            "domain_description": "GPCR-like",
            "ref_db": "Pfam",
            "start_position": "0",
            "end_position": "100",
            "score": "1.5",
            "url": "",
        })

    rows_loaded = load_domains(data_dir, bgc_lookup, cds_lookup)
    assert rows_loaded == 1

    row = BgcDomain.objects.get(bgc=bgc, domain_acc="PF00001")
    assert row.go_slim != ""
    assert row.go_slim == go_slim_for("PF00001")
