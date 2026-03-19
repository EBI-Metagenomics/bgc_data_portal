"""
factory_boy DjangoModelFactory definitions for every ORM model.

Usage:
    from tests.factories.models import BgcFactory
    bgc = BgcFactory()          # creates with all related objects
    bgc = BgcFactory(contig=c)  # share an existing contig
"""

import hashlib
import random
import string

import factory
import numpy as np
from factory.django import DjangoModelFactory

from mgnify_bgcs.models import (
    Assembly,
    Bgc,
    BgcClass,
    BgcDetector,
    Biome,
    Cds,
    Contig,
    Domain,
    GeneCaller,
    Protein,
    ProteinDomain,
    Study,
)

_NT_BASES = "ACGT"
_AA_CHARS = "ACDEFGHIKLMNPQRSTVWY"


def _random_nt(length: int) -> str:
    return "".join(random.choices(_NT_BASES, k=length))


def _random_aa(length: int) -> str:
    return "".join(random.choices(_AA_CHARS, k=length))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _embedding() -> list:
    return np.random.randn(1152).astype(np.float32).tolist()


class StudyFactory(DjangoModelFactory):
    class Meta:
        model = Study
        django_get_or_create = ("accession",)

    accession = factory.Sequence(lambda n: f"ERP{n:07d}")


class BiomeFactory(DjangoModelFactory):
    class Meta:
        model = Biome
        django_get_or_create = ("lineage",)

    lineage = factory.Sequence(lambda n: f"root:Environmental:Soil:type{n}")


class AssemblyFactory(DjangoModelFactory):
    class Meta:
        model = Assembly
        django_get_or_create = ("accession",)

    accession = factory.Sequence(lambda n: f"ERZ{n:07d}")
    study = factory.SubFactory(StudyFactory)
    biome = factory.SubFactory(BiomeFactory)
    collection = None


class ContigFactory(DjangoModelFactory):
    class Meta:
        model = Contig

    assembly = factory.SubFactory(AssemblyFactory)
    mgyc = factory.Sequence(lambda n: f"MGYC{n:012d}")
    accession = factory.Sequence(lambda n: f"contig_{n:012d}")
    name = factory.Sequence(lambda n: f"contig_{n:012d}")
    length = 20_000

    @factory.lazy_attribute
    def sequence(self):
        return _random_nt(self.length)

    @factory.lazy_attribute
    def sequence_sha256(self):
        return _sha256(self.sequence)


class BgcClassFactory(DjangoModelFactory):
    class Meta:
        model = BgcClass
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"BgcClass{n}")


class BgcDetectorFactory(DjangoModelFactory):
    class Meta:
        model = BgcDetector
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Detector{n}")
    tool = factory.LazyAttribute(lambda o: o.name)
    version = "1.0.0"


class BgcFactory(DjangoModelFactory):
    class Meta:
        model = Bgc

    contig = factory.SubFactory(ContigFactory)
    detector = factory.SubFactory(BgcDetectorFactory)
    identifier = factory.Sequence(lambda n: f"bgc_{n:08d}")
    is_partial = False
    is_aggregated_region = False
    embedding = factory.LazyFunction(_embedding)

    @factory.lazy_attribute
    def start_position(self):
        return random.randint(0, 8_000)

    @factory.lazy_attribute
    def end_position(self):
        return self.start_position + random.randint(500, 3_000)

    @factory.lazy_attribute
    def metadata(self):
        return {
            "umap_x_coord": random.uniform(-10, 10),
            "umap_y_coord": random.uniform(-10, 10),
            "detectors": [self.detector.tool or self.detector.name],
            "aggregated_region_ids": [],
        }

    class Params:
        aggregated = factory.Trait(is_aggregated_region=True)


class DomainFactory(DjangoModelFactory):
    class Meta:
        model = Domain
        django_get_or_create = ("acc",)

    acc = factory.Sequence(lambda n: f"PF{n:05d}")
    name = factory.Faker("word")
    ref_db = "Pfam"
    description = factory.Faker("sentence", nb_words=6)


class ProteinFactory(DjangoModelFactory):
    class Meta:
        model = Protein

    mgyp = factory.Sequence(lambda n: f"MGYP{n:012d}")
    cluster_representative = factory.LazyFunction(
        lambda: f"MGYP{random.randint(0, 999_999_999_999):012d}"
        if random.random() < 0.5
        else None
    )
    embedding = factory.LazyFunction(_embedding)

    @factory.lazy_attribute
    def sequence(self):
        return _random_aa(200)

    @factory.lazy_attribute
    def sequence_sha256(self):
        return _sha256(self.sequence)


class ProteinDomainFactory(DjangoModelFactory):
    class Meta:
        model = ProteinDomain

    protein = factory.SubFactory(ProteinFactory)
    domain = factory.SubFactory(DomainFactory)
    score = factory.LazyFunction(lambda: random.uniform(10.0, 300.0))

    @factory.lazy_attribute
    def start_position(self):
        return random.randint(0, 100)

    @factory.lazy_attribute
    def end_position(self):
        return self.start_position + random.randint(20, 80)


class GeneCallerFactory(DjangoModelFactory):
    class Meta:
        model = GeneCaller
        django_get_or_create = ("name",)

    name = factory.Iterator(["Prodigal", "Pyrodigal"])
    tool = factory.LazyAttribute(lambda o: o.name)
    version = "1.0.0"


class CdsFactory(DjangoModelFactory):
    class Meta:
        model = Cds

    protein = factory.SubFactory(ProteinFactory)
    contig = factory.SubFactory(ContigFactory)
    gene_caller = factory.SubFactory(GeneCallerFactory)
    strand = factory.LazyFunction(lambda: random.choice([1, -1]))
    pipeline_version = "1.0"

    @factory.lazy_attribute
    def start_position(self):
        return random.randint(0, 18_000)

    @factory.lazy_attribute
    def end_position(self):
        return self.start_position + random.randint(300, 1_500)

    @factory.lazy_attribute
    def protein_identifier(self):
        return self.protein.mgyp
