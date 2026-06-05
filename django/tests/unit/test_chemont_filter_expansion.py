"""Parent-class subtree expansion for the ChemOnt filter.

Each CDS carries only its *deepest* ChemOnt class, so selecting a parent node in
the filter tree must match anything in that subtree. ``_expand_chemont_ids``
expands selected ids to their ontology descendants, and degrades to exact-id
match when the OBO ontology is unavailable (rather than raising).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from discovery.api import _expand_chemont_ids


def _term(tid: str) -> SimpleNamespace:
    return SimpleNamespace(id=tid)


class _FakeOntology:
    """Minimal stand-in exposing ``get_descendants`` keyed by a static map."""

    def __init__(self, descendants: dict[str, list[str]]):
        self._descendants = descendants

    def get_descendants(self, chemont_id: str):
        return [_term(t) for t in self._descendants.get(chemont_id, [])]


def test_expands_parent_to_descendants(monkeypatch):
    fake = _FakeOntology(
        {"CHEMONTID:0001": ["CHEMONTID:0002", "CHEMONTID:0003"]}
    )
    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda: fake
    )

    result = set(_expand_chemont_ids(["CHEMONTID:0001"]))

    # Selected id plus its whole subtree.
    assert result == {"CHEMONTID:0001", "CHEMONTID:0002", "CHEMONTID:0003"}


def test_leaf_selection_unchanged(monkeypatch):
    fake = _FakeOntology({"CHEMONTID:0001": ["CHEMONTID:0002"]})
    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda: fake
    )

    # A leaf (no descendants) expands to just itself.
    assert set(_expand_chemont_ids(["CHEMONTID:0099"])) == {"CHEMONTID:0099"}


@pytest.mark.parametrize("exc", [FileNotFoundError, ImportError])
def test_falls_back_when_ontology_unavailable(monkeypatch, exc):
    def _boom():
        raise exc("no OBO")

    monkeypatch.setattr("common_core.chemont.ontology.get_ontology", _boom)

    # Degrades to exact-id match instead of raising.
    assert set(_expand_chemont_ids(["CHEMONTID:0001", "CHEMONTID:0002"])) == {
        "CHEMONTID:0001",
        "CHEMONTID:0002",
    }
