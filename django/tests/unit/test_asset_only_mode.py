"""Unit coverage for the asset-only-mode gate.

An uploaded asset shows asset-only on a *bare* load, but the moment the user
applies a chip/slider filter (or runs a search that yields an ``ibgc_ids``
allow-list), the DB query must re-engage with the asset rows pinned on top.
This pins the decision logic that drives that — regression for the bug where
filters were silently ignored while an asset was loaded.
"""

from __future__ import annotations

from discovery.api import _asset_only_mode, _ibgc_filters_active


def test_filters_active_false_for_bare_load():
    # All defaults → no filter narrowing.
    assert _ibgc_filters_active() is False
    assert _ibgc_filters_active(include_partials=True, validated_only=False) is False
    # Empty strings (frontend may send them) are not active filters.
    assert _ibgc_filters_active(bgc_class="", detector_tools="") is False


def test_filters_active_true_for_each_filter_kind():
    assert _ibgc_filters_active(validated_only=True) is True
    assert _ibgc_filters_active(include_partials=False) is True
    assert _ibgc_filters_active(min_novelty=0.5) is True
    assert _ibgc_filters_active(max_length_kb=10.0) is True
    assert _ibgc_filters_active(bgc_class="Polyketide") is True
    assert _ibgc_filters_active(detector_tools="antiSMASH") is True
    assert _ibgc_filters_active(domain_text="PF00001") is True


def test_asset_only_requires_token_and_no_ids_and_no_filters():
    # Bare asset load → asset-only.
    assert _asset_only_mode("tok", None, filters_active=False) is True
    # Filter applied → DB re-engages (the reported bug).
    assert _asset_only_mode("tok", None, filters_active=True) is False
    # Search allow-list present → DB re-engages.
    assert _asset_only_mode("tok", [1, 2], filters_active=False) is False
    # No asset token → never asset-only.
    assert _asset_only_mode(None, None, filters_active=False) is False
    # Back-compat: default filters_active is False.
    assert _asset_only_mode("tok", None) is True
