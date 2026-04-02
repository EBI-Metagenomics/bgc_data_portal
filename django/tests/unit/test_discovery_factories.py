"""Tests for discovery model factories."""

import pytest

from tests.factories.discovery_models import (
    GCFFactory,
    GCFMembershipFactory,
    NaturalProductFactory,
    MibigReferenceFactory,
    AssemblyScoreFactory,
    BgcScoreFactory,
)


@pytest.mark.django_db
class TestDiscoveryFactories:
    def test_gcf_factory(self):
        gcf = GCFFactory()
        assert gcf.pk is not None
        assert gcf.family_id.startswith("GCF_")
        assert gcf.member_count >= 3

    def test_gcf_membership_factory(self):
        membership = GCFMembershipFactory()
        assert membership.pk is not None
        assert membership.gcf is not None
        assert membership.bgc is not None
        assert 0.0 <= membership.distance_to_representative <= 0.5

    def test_natural_product_factory(self):
        np_ = NaturalProductFactory()
        assert np_.pk is not None
        assert np_.smiles
        assert np_.chemical_class_l1 in (
            "Polyketide", "NRP", "Alkaloid", "RiPP",
            "Terpene", "Saccharide", "Other",
        )

    def test_mibig_reference_factory(self):
        ref = MibigReferenceFactory()
        assert ref.pk is not None
        assert ref.accession.startswith("BGC")
        assert ref.compound_name
        assert ref.embedding is not None
        assert len(ref.embedding) == 1152

    def test_assembly_score_factory(self):
        gs = AssemblyScoreFactory()
        assert gs.pk is not None
        assert 0.0 <= gs.bgc_diversity_score <= 1.0
        assert 0.0 <= gs.bgc_novelty_score <= 1.0
        assert 0.0 <= gs.bgc_density <= 1.0
        assert gs.assembly is not None

    def test_bgc_score_factory(self):
        bs = BgcScoreFactory()
        assert bs.pk is not None
        assert 0.0 <= bs.novelty_score <= 1.0
        assert bs.size_kb >= 5.0
        assert bs.classification_l1 in (
            "Polyketide", "NRP", "Alkaloid", "RiPP",
            "Terpene", "Saccharide", "Other",
        )
