"""Unit tests for free-text domain-query token parsing.

Covers ``_parse_domain_tokens`` — the include/exclude split that backs the
text-entry AND/OR domain filter. Pure function, no DB needed.
"""

from discovery.api import _parse_domain_tokens


def test_splits_on_comma_and_whitespace():
    inc, exc = _parse_domain_tokens("PF00501, PF00668\tIPR000873")
    assert inc == ["PF00501", "PF00668", "IPR000873"]
    assert exc == []


def test_exclude_prefixes():
    inc, exc = _parse_domain_tokens("PF00501 -PF00668 !IPR000873")
    assert inc == ["PF00501"]
    assert exc == ["PF00668", "IPR000873"]


def test_uppercases_and_dedupes():
    inc, exc = _parse_domain_tokens("pf00501, PF00501, g3dsa:3.30.559.30")
    assert inc == ["PF00501", "G3DSA:3.30.559.30"]
    assert exc == []


def test_empty_and_bare_prefix_tokens_dropped():
    inc, exc = _parse_domain_tokens("  ,  - , ! , PF00501")
    assert inc == ["PF00501"]
    assert exc == []


def test_blank_input():
    assert _parse_domain_tokens("") == ([], [])
    assert _parse_domain_tokens(None) == ([], [])
