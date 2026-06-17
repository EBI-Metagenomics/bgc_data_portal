"""Unit tests for the landing-page keyword resolver.

The resolver maps a free-text keyword to the single best-matching dashboard
filter and always returns a redirect URL. These tests pin the behaviour that
a non-accession free-text term (e.g. "Polyketide") falls through to the
``domain_text`` filter — the param the v2 dashboard searches against the
iBGC's domain annotations — rather than the organism-only ``search`` param.
"""

from __future__ import annotations

import pytest
from discovery.services.keyword_resolver import classify_accession, resolve_keyword


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MGYB-AB12CD-0A", "ibgc"),
        ("mgyb-ab12cd-0a", "ibgc"),
        ("MGYB-AB12CD.ANT.01", "prediction"),
        ("MGYB-AB12CD", "cbgc"),
        ("MGYB00000123", "cbgc"),  # legacy pre-refactor form
        ("ERZ123456", "assembly"),
        ("GCA_000001405.1", "assembly"),
        ("GCF_000001405", "assembly"),
        ("BGC0000422", "assembly"),  # MIBiG entry accession
        ("bgc0000422", "assembly"),
        ("BGC042", "unknown"),  # too short — not a MIBiG accession
        ("MGYP000123456789", "protein"),
        ("Ga0181741_11_94", "unknown"),  # free-form contig / protein id
        ("", "unknown"),
        ("  ", "unknown"),
    ],
)
def test_classify_accession(value, expected):
    assert classify_accession(value) == expected


@pytest.mark.django_db
def test_free_text_keyword_falls_back_to_domain_text():
    result = resolve_keyword("Polyketide")
    assert result["match_type"] == "fallback"
    assert result["filter_param"] == "domain_text"
    assert result["filter_value"] == "Polyketide"
    assert "domain_text=Polyketide" in result["redirect_url"]
    assert "auto_run=true" in result["redirect_url"]


@pytest.mark.django_db
def test_empty_keyword_returns_empty_domain_text_fallback():
    result = resolve_keyword("")
    assert result["match_type"] == "fallback"
    assert result["filter_param"] == "domain_text"
    assert result["filter_value"] == ""
