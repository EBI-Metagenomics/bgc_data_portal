"""Unit tests for the landing-page keyword resolver.

The resolver maps a free-text keyword to the single best-matching dashboard
filter and always returns a redirect URL. These tests pin the behaviour that
a non-accession free-text term (e.g. "Polyketide") falls through to the
``domain_text`` filter — the param the v2 dashboard searches against the
iBGC's domain annotations — rather than the organism-only ``search`` param.
"""

from __future__ import annotations

import pytest

from discovery.services.keyword_resolver import resolve_keyword


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
