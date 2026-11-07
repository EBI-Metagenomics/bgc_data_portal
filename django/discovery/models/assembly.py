"""Assemblies, their contigs (with on-demand sequence) and contig taxonomy."""

from django.db import models

from .mixins import ZlibSequenceMixin


class AssemblySource(models.Model):
    """Lookup table for assembly data sources (auto-populated via get_or_create)."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "discovery_assembly_source"

    def __str__(self):
        return self.name


class AssemblyType(models.IntegerChoices):
    METAGENOME = 1, "metagenome"
    GENOME = 2, "genome"
    REGION = 3, "region"


class DashboardAssembly(models.Model):
    """Denormalised assembly row: identity + biome + precomputed scores."""

    id = models.BigAutoField(primary_key=True)

    assembly_accession = models.CharField(max_length=255, unique=True, db_index=True)
    organism_name = models.CharField(max_length=255, blank=True, default="")

    source = models.ForeignKey(
        AssemblySource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assemblies",
        db_index=True,
    )

    assembly_type = models.SmallIntegerField(
        choices=AssemblyType.choices,
        default=AssemblyType.GENOME,
        db_index=True,
    )

    biome_path = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="ltree dot-path, e.g. root.Environmental.Terrestrial.Soil",
    )

    is_type_strain = models.BooleanField(default=False, db_index=True)
    type_strain_catalog_url = models.URLField(blank=True, default="")
    assembly_size_mb = models.FloatField(null=True, blank=True)
    url = models.URLField(max_length=512, blank=True, default="")

    # Precomputed scores (denormalised from per-iBGC stats)
    bgc_count = models.IntegerField(default=0)
    l1_class_count = models.IntegerField(default=0)
    bgc_diversity_score = models.FloatField(default=0.0)
    bgc_novelty_score = models.FloatField(default=0.0)
    bgc_density = models.FloatField(default=0.0)
    taxonomic_novelty = models.FloatField(default=0.0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_assembly"
        indexes = [
            models.Index(fields=["-bgc_novelty_score"], name="idx_da_novelty_desc"),
            models.Index(fields=["-bgc_diversity_score"], name="idx_da_diversity_desc"),
            models.Index(fields=["-bgc_density"], name="idx_da_density_desc"),
            models.Index(fields=["organism_name"], name="idx_da_organism"),
            models.Index(fields=["biome_path"], name="idx_da_biome"),
        ]

    def __str__(self):
        return self.assembly_accession


class Taxon(models.Model):
    """NCBI taxon with its canonical 8-rank lineage.

    One row per taxid referenced by a contig lineage: the leaf a contig is
    assigned to plus every canonical-rank ancestor. ``ltree_path`` is the
    sanitised dot-path of the present ranks (absent ranks skipped), i.e. the
    value written to ``DashboardContig.taxonomy_path``; its labels pair
    one-to-one, in order, with the non-empty ``<rank>_taxid`` columns.
    Populated by ``apply_taxonomy_mapping``.
    """

    taxid = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    rank = models.CharField(max_length=32, help_text="NCBI rank of this node")
    parent_taxid = models.IntegerField(
        null=True, blank=True, help_text="Nearest canonical-rank ancestor"
    )
    ltree_path = models.CharField(max_length=1024)
    deepest_informative_rank = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Deepest rank ignoring genus-less placeholder species "
        "(e.g. 'Pseudomonadota bacterium' → phylum)",
    )
    taxdump_version = models.CharField(max_length=64, blank=True, default="")

    domain_name = models.CharField(max_length=255, blank=True, default="")
    domain_taxid = models.IntegerField(null=True, blank=True)
    kingdom_name = models.CharField(max_length=255, blank=True, default="")
    kingdom_taxid = models.IntegerField(null=True, blank=True)
    phylum_name = models.CharField(max_length=255, blank=True, default="")
    phylum_taxid = models.IntegerField(null=True, blank=True)
    class_name = models.CharField(max_length=255, blank=True, default="")
    class_taxid = models.IntegerField(null=True, blank=True)
    order_name = models.CharField(max_length=255, blank=True, default="")
    order_taxid = models.IntegerField(null=True, blank=True)
    family_name = models.CharField(max_length=255, blank=True, default="")
    family_taxid = models.IntegerField(null=True, blank=True)
    genus_name = models.CharField(max_length=255, blank=True, default="")
    genus_taxid = models.IntegerField(null=True, blank=True)
    species_name = models.CharField(max_length=255, blank=True, default="")
    species_taxid = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "discovery_taxon"
        indexes = [
            models.Index(fields=["phylum_taxid"], name="idx_taxon_phylum"),
            models.Index(fields=["genus_taxid"], name="idx_taxon_genus"),
        ]

    def __str__(self):
        return f"{self.name} ({self.rank}, {self.taxid})"


class DashboardContig(models.Model):
    """Contig within an assembly — CDS, cBGCs and iBGCs hang off this."""

    id = models.BigAutoField(primary_key=True)
    assembly = models.ForeignKey(
        DashboardAssembly,
        on_delete=models.CASCADE,
        related_name="contigs",
        db_index=True,
    )
    sequence_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    accession = models.CharField(max_length=255, blank=True, default="", db_index=True)
    length = models.IntegerField(default=0)

    taxonomy_path = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        help_text="ltree dot-path, e.g. Bacteria.Actinomycetota.Actinomycetia...",
    )
    taxon = models.ForeignKey(
        Taxon,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contigs",
        help_text="Rank-aware NCBI lineage; null until apply_taxonomy_mapping runs",
    )
    taxonomy_path_legacy = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        help_text="taxonomy_path before apply_taxonomy_mapping rewrote it "
        "(kept for --revert)",
    )

    class Meta:
        db_table = "discovery_contig"
        indexes = [
            models.Index(fields=["taxonomy_path"], name="idx_dcontig_tax_path"),
        ]

    def __str__(self):
        return self.accession or self.sequence_sha256


class ContigSequence(ZlibSequenceMixin, models.Model):
    """On-demand nucleotide sequence for a contig — zlib-compressed."""

    contig = models.OneToOneField(
        DashboardContig,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="seq",
    )
    data = models.BinaryField(help_text="zlib-compressed nucleotide sequence")

    class Meta:
        db_table = "discovery_contig_sequence"

    def __str__(self):
        return f"Sequence for {self.contig_id}"
