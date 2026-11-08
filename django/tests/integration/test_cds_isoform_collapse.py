"""Alternative transcripts with one outer span collapse to one CDS, logged.

``ContigCds`` is unique on ``(contig, cds_range, strand)``. Eukaryotic
isoforms (``.t1`` / ``.t2``) of one gene often share that span; the loader
keeps the first row and warns about the dropped one instead of dropping it
silently. A repeated row for the same protein is not counted.
"""

from __future__ import annotations

import csv
import logging

import pytest
from discovery.models import ContigCds
from discovery.services.ingestion.loader import load_cds
from tests.factories.discovery_models import DashboardContigFactory

pytestmark = pytest.mark.django_db

COLUMNS = [
    "contig_sha256",
    "start_position",
    "end_position",
    "strand",
    "protein_id_str",
    "protein_length",
    "gene_caller",
    "protein_sha256",
]


def test_isoforms_on_one_span_keep_t1_and_warn(tmp_path, caplog):
    contig = DashboardContigFactory()
    sha = contig.sequence_sha256
    rows = [
        [sha, "100", "3100", "1", "g1.t1", "995", "AUGUSTUS", "a" * 64],
        [sha, "100", "3100", "1", "g1.t1", "995", "AUGUSTUS", "a" * 64],  # repeat
        [sha, "100", "3100", "1", "g1.t2", "979", "AUGUSTUS", "b" * 64],  # isoform
        [sha, "5000", "6000", "-1", "g2.t1", "333", "AUGUSTUS", "c" * 64],
    ]
    with (tmp_path / "cds.tsv").open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(COLUMNS)
        w.writerows(rows)

    with caplog.at_level(logging.WARNING):
        lookup = load_cds(tmp_path, {sha: contig.id})

    assert sorted(ContigCds.objects.values_list("protein_id_str", flat=True)) == [
        "g1.t1",
        "g2.t1",
    ]
    assert (contig.id, "g1.t2") not in lookup
    assert "1 CDS shared a (contig, span, strand)" in caplog.text
    assert "g1.t2" in caplog.text
