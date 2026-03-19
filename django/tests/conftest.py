"""
Root conftest — shared fixtures across unit/, integration/, and e2e/ tests.

Session-scoped dataset fixtures build once per pytest session and are reused
across all integration tests, avoiding expensive repeated DB setup.
"""

from pathlib import Path

import pytest

from tests.factories.builders import DatasetBuilder
from tests.factories.models import (
    BgcFactory,
    CdsFactory,
    ContigFactory,
    ProteinDomainFactory,
    ProteinFactory,
)

SMALL_MANIFEST = Path(__file__).parent / "factories/manifests/small.yaml"


@pytest.fixture(scope="session")
def small_dataset(django_db_setup, django_db_blocker):
    """
    Session-scoped: build a small dataset once and reuse across all tests.

    Provides ~24 BGCs (2 studies × 2 assemblies × 1 contig × 3 BGCs).
    """
    with django_db_blocker.unblock():
        return DatasetBuilder(SMALL_MANIFEST).build()


@pytest.fixture
def bgc(db):
    """Single BGC with auto-generated contig, detector, and assembly chain."""
    return BgcFactory()


@pytest.fixture
def bgc_with_cds(db):
    """BGC with 3 CDS entries, each having 2 Pfam domain annotations."""
    bgc = BgcFactory()
    proteins = ProteinFactory.create_batch(3)
    for protein in proteins:
        CdsFactory(contig=bgc.contig, protein=protein)
        ProteinDomainFactory.create_batch(2, protein=protein)
    return bgc
