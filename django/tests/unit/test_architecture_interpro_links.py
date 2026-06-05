"""Tests for InterPro link construction in the Protein Information card.

``collapse_to_interpro_rows`` folds per-signature domain rows into one row per
InterPro entry and decides the outbound link. These tests pin the rule that:

  * integrated signatures (``interpro_entry_acc`` set) link to the InterPro
    *entry* page, and
  * unintegrated signatures fall back to the canonical InterPro *member-database*
    page derived from ``ref_db`` + ``domain_acc`` (the bug fix — previously these
    relied on an ingested ``url`` that some sources, e.g. MIBIG, never supplied).

The collapse helper accepts any object with the ContigDomain attribute surface,
so these run without a DB.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from discovery.services.architecture import (
    _signature_url,
    collapse_to_interpro_rows,
)


def _dom(**kw):
    """Minimal stand-in for a ContigDomain row."""
    base = dict(
        interpro_entry_acc="",
        interpro_entry_description="",
        domain_acc="",
        domain_name="",
        domain_description="",
        ref_db="",
        start_position=1,
        end_position=100,
        score=1e-10,
        url="",
        go_slim=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize(
    "ref_db,acc,expected",
    [
        ("Gene3D", "G3DSA:1.20.1720.10",
         "https://www.ebi.ac.uk/interpro/entry/cathgene3d/G3DSA:1.20.1720.10/"),
        ("Pfam", "PF00109",
         "https://www.ebi.ac.uk/interpro/entry/pfam/PF00109/"),
        # TIGRFAM is served under the NCBIFAM slug on InterPro.
        ("TIGRFAM", "TIGR00001",
         "https://www.ebi.ac.uk/interpro/entry/ncbifam/TIGR00001/"),
        # PROSITE patterns vs profiles map to distinct slugs.
        ("PROSITE_PATTERNS", "PS00012",
         "https://www.ebi.ac.uk/interpro/entry/prosite/PS00012/"),
        ("PROSITE_PROFILES", "PS50011",
         "https://www.ebi.ac.uk/interpro/entry/profile/PS50011/"),
        # Case-insensitive ref_db.
        ("ncbifam", "NF000001",
         "https://www.ebi.ac.uk/interpro/entry/ncbifam/NF000001/"),
    ],
)
def test_signature_url_known_refdbs(ref_db, acc, expected):
    assert _signature_url(ref_db, acc) == expected


@pytest.mark.parametrize("ref_db", ["", "  ", "MobiDBLite", "Coils", "SignalP"])
def test_signature_url_unknown_refdb_is_empty(ref_db):
    # Unmapped / structural-feature ref_dbs never produce a (potentially 404) link.
    assert _signature_url(ref_db, "X12345") == ""


def test_signature_url_blank_accession_is_empty():
    assert _signature_url("Pfam", "") == ""


def test_unintegrated_signature_gets_member_db_link():
    """The reported MIBIG bug: no entry acc, no ingested url -> still links."""
    rows = collapse_to_interpro_rows(
        [_dom(domain_acc="G3DSA:1.20.1720.10", ref_db="Gene3D", url="")]
    )
    assert len(rows) == 1
    assert rows[0]["accession"] == "G3DSA:1.20.1720.10"
    assert rows[0]["url"] == (
        "https://www.ebi.ac.uk/interpro/entry/cathgene3d/G3DSA:1.20.1720.10/"
    )


def test_integrated_signature_links_to_interpro_entry():
    rows = collapse_to_interpro_rows(
        [
            _dom(
                domain_acc="G3DSA:1.10.357.10",
                ref_db="Gene3D",
                interpro_entry_acc="IPR000123",
                interpro_entry_description="Some entry",
            )
        ]
    )
    assert len(rows) == 1
    assert rows[0]["accession"] == "IPR000123"
    assert rows[0]["url"] == (
        "https://www.ebi.ac.uk/interpro/entry/InterPro/IPR000123/"
    )


def test_canonical_url_overrides_ingested_url():
    """Per design: the canonical InterPro URL wins over any ingested ``url``."""
    rows = collapse_to_interpro_rows(
        [
            _dom(
                domain_acc="PF00109",
                ref_db="Pfam",
                url="https://example.org/legacy-link",
            )
        ]
    )
    assert rows[0]["url"] == "https://www.ebi.ac.uk/interpro/entry/pfam/PF00109/"


def test_unmappable_refdb_stays_unlinked():
    rows = collapse_to_interpro_rows(
        [_dom(domain_acc="mobidb-lite", ref_db="MobiDBLite", url="")]
    )
    assert rows[0]["url"] == ""
