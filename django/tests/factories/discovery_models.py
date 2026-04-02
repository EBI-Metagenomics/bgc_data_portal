"""
factory_boy DjangoModelFactory definitions for discovery app models.

Usage:
    from tests.factories.discovery_models import GCFFactory
    gcf = GCFFactory()
"""

import random

import factory
import numpy as np
from factory.django import DjangoModelFactory

from discovery.models import (
    GCF,
    GCFMembership,
    NaturalProduct,
    MibigReference,
    GenomeScore,
    BgcScore,
)
from tests.factories.models import AssemblyFactory, BgcFactory


def _embedding() -> list:
    return np.random.randn(1152).astype(np.float32).tolist()


# Curated pools for realistic data generation

_MIBIG_COMPOUNDS = [
    ("erythromycin", "Polyketide"),
    ("vancomycin", "NRP"),
    ("rifamycin", "Polyketide"),
    ("tetracycline", "Polyketide"),
    ("daptomycin", "NRP"),
    ("rapamycin", "Polyketide"),
    ("bleomycin", "NRP"),
    ("avermectin", "Polyketide"),
    ("streptomycin", "Saccharide"),
    ("epothilone", "Polyketide"),
    ("lanthipeptide A", "RiPP"),
    ("nisin", "RiPP"),
    ("geosmin", "Terpene"),
    ("albaflavenone", "Terpene"),
    ("staurosporine", "Alkaloid"),
    ("rebeccamycin", "Alkaloid"),
    ("enterobactin", "NRP"),
    ("bacillibactin", "NRP"),
    ("prodiginine", "Alkaloid"),
    ("desferrioxamine", "NRP"),
    ("salinosporamide", "Polyketide"),
    ("thiostrepton", "RiPP"),
    ("calicheamicin", "Polyketide"),
    ("actinomycin", "NRP"),
    ("chloramphenicol", "Other"),
    ("novobiocin", "Other"),
    ("clavulanic acid", "Other"),
    ("melanin", "Other"),
    ("ectoine", "Other"),
    ("hopanoid", "Terpene"),
]

_NP_CLASSES = {
    "Polyketide": {
        "Macrolide": ["14-membered macrolide", "16-membered macrolide", "Ansamycin"],
        "Aromatic polyketide": ["Tetracycline", "Anthracycline", "Angucycline"],
        "Linear polyketide": ["Polyene", "Polyether", None],
    },
    "NRP": {
        "Cyclic peptide": ["Lipopeptide", "Glycopeptide", "Depsipeptide"],
        "Linear peptide": ["Siderophore", None, None],
    },
    "Alkaloid": {
        "Indole alkaloid": ["Bisindole", "Carbazole", None],
        "Pyrrolidine": [None, None, None],
    },
    "RiPP": {
        "Lanthipeptide": ["Class I", "Class II", None],
        "Thiopeptide": [None, None, None],
        "Sactipeptide": [None, None, None],
    },
    "Terpene": {
        "Sesquiterpene": [None, None, None],
        "Diterpene": [None, None, None],
    },
    "Saccharide": {
        "Aminoglycoside": ["4,6-disubstituted", None, None],
        "Oligosaccharide": [None, None, None],
    },
    "Other": {
        "Phosphonate": [None, None, None],
        "Aminocoumarin": [None, None, None],
    },
}

_SMILES_POOL = [
    "CC1OC(=O)C(C)C(OC2CC(C)(OC)C(O)C(C)O2)C(C)C(OC2OC(C)CC(N(C)C)C2O)C(C)(O)CC(C)C(=O)C(C)C(O)C1(C)O",
    "CC(=O)NC1C(O)C(O)C(CO)OC1OC1C(O)C(OC2OC(CO)C(O)C(N)C2O)C(O)C(CO)O1",
    "CC1=CC(O)=C2C(=O)C3=C(O)C(N(C)C)=CC(O)=C3CC2=C1",
    "O=C(O)C1=CC=C(N)C=C1",
    "CC(O)CC(=O)OC1CC(O)C(C)C(OC2CC(C)C(O)C(C)O2)C(C)C(=O)CC(O)C(C)C(=O)C(C)C1OC1CC(N(C)C)C(O)C(C)O1",
    "CC1OC(OC2C(O)C(O)CC(O2)C2=CC3=CC(=CC(O)=C3C(=O)C2)OC)CC(N)C1O",
    "CCC(C)C(NC(=O)C(CC(C)C)NC(=O)C(CCC(=O)O)NC(=O)C(CC(=O)O)NC(=O)C(NC=O)CCCN)C(=O)O",
    "OC1=CC=C(C=C1)C(=O)O",
    "CC1=C(C=CC=C1O)O",
    "CC1OC(O)CC1=O",
    "CC(CC1=CNC2=CC=CC=C12)NC",
    "OC(=O)CCCCC1SCC2NC(=O)NC12",
    "CC(C)CC1NC(=O)C(CC(=O)O)NC(=O)C(CC2=CC=CC=C2)NC(=O)C(CO)NC1=O",
    "OC(=O)C1CCCN1",
    "CC1=CC=CC=C1NC(=O)C1=CC=CC(O)=C1O",
    "OC1C(O)C(OC1CO)N1C=NC2=C1N=CN=C2N",
    "CC(=O)OC1CC2CCC3C(CCC4(C)C3CC=C3CC(O)CCC34C)C2(C)CC1OC(=O)C",
    "CC1(C)CCC2(CCC3(C)C(=CCC4C5(C)CCC(O)C(C)(C)C5CCC43C)C2C1)C(=O)O",
    "O=C1C=CC(=O)C2=C1C=CC=C2",
    "CC1OC(=O)CC(O)C1O",
]


class GCFFactory(DjangoModelFactory):
    class Meta:
        model = GCF
        django_get_or_create = ("family_id",)

    family_id = factory.Sequence(lambda n: f"GCF_{n:06d}")
    representative_bgc = factory.SubFactory(BgcFactory)
    member_count = factory.LazyFunction(lambda: random.randint(3, 50))
    known_chemistry_annotation = factory.LazyFunction(
        lambda: random.choice([None, None, "polyketide synthase", "NRPS", "lanthipeptide", "siderophore"])
    )
    mibig_accession = factory.LazyFunction(
        lambda: f"BGC{random.randint(1, 2500):07d}" if random.random() < 0.3 else None
    )


class GCFMembershipFactory(DjangoModelFactory):
    class Meta:
        model = GCFMembership

    gcf = factory.SubFactory(GCFFactory)
    bgc = factory.SubFactory(BgcFactory)
    distance_to_representative = factory.LazyFunction(lambda: round(random.uniform(0.0, 0.5), 4))


class NaturalProductFactory(DjangoModelFactory):
    class Meta:
        model = NaturalProduct
        exclude = ("_np_class",)

    name = factory.Faker("word")
    smiles = factory.LazyFunction(lambda: random.choice(_SMILES_POOL))
    bgc = factory.SubFactory(BgcFactory)

    @factory.lazy_attribute
    def _np_class(self):
        l1 = random.choice(list(_NP_CLASSES.keys()))
        l2 = random.choice(list(_NP_CLASSES[l1].keys()))
        l3 = random.choice(_NP_CLASSES[l1][l2])
        return l1, l2, l3

    @factory.lazy_attribute
    def chemical_class_l1(self):
        return self._np_class[0]

    @factory.lazy_attribute
    def chemical_class_l2(self):
        return self._np_class[1]

    @factory.lazy_attribute
    def chemical_class_l3(self):
        return self._np_class[2]

    @factory.lazy_attribute
    def producing_organism(self):
        return random.choice([
            "Streptomyces coelicolor", "Streptomyces griseus",
            "Amycolatopsis mediterranei", "Bacillus subtilis",
            "Pseudomonas fluorescens", "Myxococcus xanthus",
            None,
        ])


class MibigReferenceFactory(DjangoModelFactory):
    class Meta:
        model = MibigReference
        django_get_or_create = ("accession",)
        exclude = ("_compound_info",)

    accession = factory.Sequence(lambda n: f"BGC{n:07d}")
    embedding = factory.LazyFunction(_embedding)

    @factory.lazy_attribute
    def _compound_info(self):
        return random.choice(_MIBIG_COMPOUNDS)

    @factory.lazy_attribute
    def compound_name(self):
        return self._compound_info[0]

    @factory.lazy_attribute
    def bgc_class(self):
        return self._compound_info[1]

    @factory.lazy_attribute
    def umap_x(self):
        return round(random.uniform(-10, 10), 4)

    @factory.lazy_attribute
    def umap_y(self):
        return round(random.uniform(-10, 10), 4)


class AssemblyScoreFactory(DjangoModelFactory):
    class Meta:
        model = GenomeScore

    assembly = factory.SubFactory(AssemblyFactory)
    bgc_count = factory.LazyFunction(lambda: random.randint(1, 30))
    bgc_diversity_score = factory.LazyFunction(lambda: round(random.betavariate(3, 2), 4))
    bgc_novelty_score = factory.LazyFunction(lambda: round(random.betavariate(2, 5), 4))
    bgc_density = factory.LazyFunction(lambda: round(random.betavariate(2, 3), 4))
    taxonomic_novelty = factory.LazyFunction(lambda: round(random.betavariate(2, 4), 4))
    assembly_quality = factory.LazyFunction(lambda: round(random.betavariate(8, 2), 4))
    l1_class_count = factory.LazyFunction(lambda: random.randint(1, 7))


class BgcScoreFactory(DjangoModelFactory):
    class Meta:
        model = BgcScore

    bgc = factory.SubFactory(BgcFactory)
    novelty_score = factory.LazyFunction(lambda: round(random.betavariate(2, 5), 4))
    domain_novelty = factory.LazyFunction(lambda: round(random.betavariate(2, 6), 4))
    nearest_mibig_distance = factory.LazyFunction(lambda: round(random.uniform(0.0, 1.0), 4))
    size_kb = factory.LazyFunction(lambda: round(random.uniform(5.0, 120.0), 2))
    is_validated = factory.LazyFunction(lambda: random.random() < 0.05)

    @factory.lazy_attribute
    def nearest_mibig_accession(self):
        return f"BGC{random.randint(1, 2500):07d}" if self.nearest_mibig_distance < 0.5 else None

    @factory.lazy_attribute
    def classification_l1(self):
        return random.choice(["Polyketide", "NRP", "Alkaloid", "RiPP", "Saccharide", "Other", "Terpene"])

    @factory.lazy_attribute
    def classification_l2(self):
        l1 = self.classification_l1
        if l1 in _NP_CLASSES:
            return random.choice(list(_NP_CLASSES[l1].keys()))
        return None

    @factory.lazy_attribute
    def classification_l3(self):
        l1 = self.classification_l1
        l2 = self.classification_l2
        if l1 in _NP_CLASSES and l2 in _NP_CLASSES.get(l1, {}):
            return random.choice(_NP_CLASSES[l1][l2])
        return None
