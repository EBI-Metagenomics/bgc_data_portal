"""Chemical (ChemOnt/ClassyFire) search scoring.

The HTTP query endpoints were retired in favour of the combined multi-criterion
query (``/query/combined/``); these tests now pin the underlying scoring compute
— ``run_chemical_search``, exercised here through the thin
``chemical_similarity_search`` task wrapper — which the combined query relies on:
classify → IC lookup → range-overlap pooling → Lin BMA → threshold.
"""

from __future__ import annotations

import pytest
from tests.factories.discovery_models import (
    ContigCdsFactory,
    IntegratedBgcFactory,
)


class _FakeOntology:
    def get_ancestor_ids(self, tid):
        return {tid}


@pytest.mark.django_db
def test_task_scores_overlapping_ibgc_above_threshold(monkeypatch):
    """A query sharing an iBGC's ChemOnt term scores 1.0 (identical) and is
    returned keyed by the iBGC id."""
    from common_core.chemont.classyfire_client import ClassyFireResult
    from discovery.models import CdsChemOnt, PrecomputedStats
    from discovery.tasks import chemical_similarity_search

    term = "CHEMONTID:0001"
    ibgc = IntegratedBgcFactory(start_pos=1000, end_pos=5000)
    cds = ContigCdsFactory(contig=ibgc.contig, start_pos=1100, end_pos=1400)
    CdsChemOnt.objects.create(
        cds=cds,
        chemont_id=term,
        chemont_name="Terpenes",
        probability=0.9,
        weight=0.5,
    )
    PrecomputedStats.objects.update_or_create(
        key="chemont_ic", defaults={"data": {term: 2.0}}
    )

    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda: _FakeOntology()
    )
    monkeypatch.setattr(
        "common_core.chemont.classyfire_client.classify",
        lambda *a, **k: ClassyFireResult(inchikey="x", chemont_ids=[term]),
    )
    # Force a cache miss so the (patched) classifier is used.
    monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)

    result = chemical_similarity_search.call("CCO", 0.5)

    assert result == {ibgc.id: 1.0}


@pytest.mark.django_db
def test_task_raises_when_ic_cache_missing(monkeypatch):
    """No precomputed IC must fail loudly, not silently return empty."""
    from common_core.chemont.classyfire_client import ClassyFireResult
    from discovery.models import PrecomputedStats
    from discovery.tasks import chemical_similarity_search

    PrecomputedStats.objects.filter(key="chemont_ic").delete()
    monkeypatch.setattr(
        "common_core.chemont.ontology.get_ontology", lambda: _FakeOntology()
    )
    monkeypatch.setattr(
        "common_core.chemont.classyfire_client.classify",
        lambda *a, **k: ClassyFireResult(inchikey="x", chemont_ids=["CHEMONTID:0001"]),
    )
    monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)

    # Running synchronously surfaces the failure by raising (no result store).
    with pytest.raises(RuntimeError):
        chemical_similarity_search.call("CCO", 0.5)
