"""Structure-derived ChemOnt: the ``classify_ibgc_natural_products`` command and
its pooling into the chemical search.

Covers the "third element" — running ClassyFire on an iBGC's natural-product
SMILES and storing the result in ``IbgcChemOnt``, which the search scoring and
ChemOnt IC then pool alongside the gene-based ``CdsChemOnt``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.core.management import call_command

from common_core.chemont.classyfire_client import ClassyFireResult
from discovery.models import IbgcChemOnt, IbgcNaturalProduct
from tests.factories.discovery_models import IntegratedBgcFactory


class _FakeOntology:
    """Minimal ontology: get_term(name) and self-only ancestors."""

    _NAMES = {"CHEMONTID:0000259": "Prenol lipids", "CHEMONTID:0000147": "Macrolides"}

    def get_term(self, cid):
        return SimpleNamespace(id=cid, name=self._NAMES.get(cid, ""))

    def get_ancestor_ids(self, tid):
        return {tid}


def _np(ibgc, smiles, name="cmpd"):
    return IbgcNaturalProduct.objects.create(
        ibgc=ibgc, name=name, smiles=smiles, dedup_hash=f"{name}|{smiles}"
    )


@pytest.fixture
def patched_classify(monkeypatch):
    """ClassyFire → fixed terms; ontology → fake; cache → always miss."""
    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda *a, **k: _FakeOntology()
    )
    monkeypatch.setattr(
        "common_core.chemont.classyfire_client.classify",
        lambda *a, **k: ClassyFireResult(
            inchikey="IK", chemont_ids=["CHEMONTID:0000259", "CHEMONTID:0000147"]
        ),
    )
    monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)


@pytest.mark.django_db
def test_command_writes_structure_chemont(patched_classify):
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    _np(ibgc, "CCO")

    call_command("classify_ibgc_natural_products", "--sleep", "0")

    cids = set(
        IbgcChemOnt.objects.filter(ibgc=ibgc).values_list("chemont_id", flat=True)
    )
    assert cids == {"CHEMONTID:0000259", "CHEMONTID:0000147"}
    # name resolved from the ontology
    assert IbgcChemOnt.objects.get(
        ibgc=ibgc, chemont_id="CHEMONTID:0000259"
    ).chemont_name == "Prenol lipids"


@pytest.mark.django_db
def test_command_skips_already_classified(patched_classify):
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    _np(ibgc, "CCO")
    IbgcChemOnt.objects.create(ibgc=ibgc, chemont_id="CHEMONTID:0000259")

    call_command("classify_ibgc_natural_products", "--sleep", "0")

    # Not reclassified → still just the pre-existing row, no duplicates.
    assert IbgcChemOnt.objects.filter(ibgc=ibgc).count() == 1


@pytest.mark.django_db
def test_command_dry_run_writes_nothing(patched_classify):
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    _np(ibgc, "CCO")

    call_command("classify_ibgc_natural_products", "--dry-run", "--sleep", "0")

    assert not IbgcChemOnt.objects.filter(ibgc=ibgc).exists()


@pytest.mark.django_db
def test_task_pools_structure_chemont(monkeypatch):
    """An iBGC with ONLY a structure-derived term (no CdsChemOnt) is scored."""
    from discovery.models import PrecomputedStats
    from discovery.tasks import chemical_similarity_search

    term = "CHEMONTID:0000259"
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    IbgcChemOnt.objects.create(ibgc=ibgc, chemont_id=term, chemont_name="Prenol lipids")
    PrecomputedStats.objects.update_or_create(
        key="chemont_ic", defaults={"data": {term: 2.0}}
    )

    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda *a, **k: _FakeOntology()
    )
    monkeypatch.setattr(
        "common_core.chemont.classyfire_client.classify",
        lambda *a, **k: ClassyFireResult(inchikey="IK", chemont_ids=[term]),
    )
    monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)

    result = chemical_similarity_search.apply(args=["CCO", 0.5]).result

    assert result.get(ibgc.id) == 1.0
