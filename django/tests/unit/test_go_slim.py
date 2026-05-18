"""Unit tests for the shared Pfam → GO slim helper.

Pins the selection rule (first molecular_function term, capitalised, deduped)
and the in-process caching behaviour relied on by the ingestion loader and
asset projection paths.
"""

from __future__ import annotations

import json
from unittest.mock import patch, mock_open

from discovery.services import go_slim as go_slim_mod
from discovery.services.go_slim import go_slim_for


def _clear_cache():
    go_slim_mod._pfam_to_slim.cache_clear()


def test_picks_first_molecular_function_term():
    _clear_cache()
    payload = {
        "PF00001": [
            ["receptor activity", "molecular_function"],
            ["dna binding", "molecular_function"],
        ],
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(payload))):
        assert go_slim_for("PF00001") == "Receptor activity"
    _clear_cache()


def test_ignores_non_molecular_function_terms():
    _clear_cache()
    payload = {
        "PF00002": [
            ["membrane", "cellular_component"],
            ["signal transduction", "biological_process"],
            ["kinase activity", "molecular_function"],
        ],
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(payload))):
        assert go_slim_for("PF00002") == "Kinase activity"
    _clear_cache()


def test_dedupes_repeated_terms_keeping_order():
    _clear_cache()
    payload = {
        "PF00003": [
            ["transporter activity", "molecular_function"],
            ["TRANSPORTER ACTIVITY", "molecular_function"],
            ["catalytic activity", "molecular_function"],
        ],
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(payload))):
        assert go_slim_for("PF00003") == "Transporter activity"
    _clear_cache()


def test_unknown_accession_returns_empty_string():
    _clear_cache()
    with patch("builtins.open", mock_open(read_data="{}")):
        assert go_slim_for("PF99999") == ""
        assert go_slim_for("") == ""
    _clear_cache()


def test_missing_file_returns_empty_mapping():
    _clear_cache()
    with patch("builtins.open", side_effect=FileNotFoundError):
        assert go_slim_for("PF00001") == ""
    _clear_cache()


def test_json_loaded_once_per_process():
    """lru_cache should mean a single read of pfam2goSlim.json."""
    _clear_cache()
    payload = {"PF00001": [["a", "molecular_function"]]}
    m = mock_open(read_data=json.dumps(payload))
    with patch("builtins.open", m):
        go_slim_for("PF00001")
        go_slim_for("PF00001")
        go_slim_for("PF99999")
    assert m.call_count == 1
    _clear_cache()


def test_bundled_mapping_loads_real_data():
    """Smoke check that the actual bundled JSON parses and resolves a Pfam."""
    _clear_cache()
    # PF00001 is a classic GPCR Pfam present in the bundled mapping.
    assert go_slim_for("PF00001") != ""
    _clear_cache()
