from django.contrib import admin

from .models import (
    GCF,
    GCFMembership,
    NaturalProduct,
    MibigReference,
    GenomeScore,
    BgcScore,
)


@admin.register(GCF)
class GCFAdmin(admin.ModelAdmin):
    list_display = ("family_id", "member_count", "known_chemistry_annotation", "mibig_accession")
    search_fields = ("family_id", "known_chemistry_annotation")


@admin.register(GCFMembership)
class GCFMembershipAdmin(admin.ModelAdmin):
    list_display = ("gcf", "bgc", "distance_to_representative")
    raw_id_fields = ("gcf", "bgc")


@admin.register(NaturalProduct)
class NaturalProductAdmin(admin.ModelAdmin):
    list_display = ("name", "chemical_class_l1", "chemical_class_l2", "producing_organism")
    search_fields = ("name", "smiles")
    list_filter = ("chemical_class_l1",)


@admin.register(MibigReference)
class MibigReferenceAdmin(admin.ModelAdmin):
    list_display = ("accession", "compound_name", "bgc_class")
    search_fields = ("accession", "compound_name")


@admin.register(GenomeScore)
class GenomeScoreAdmin(admin.ModelAdmin):
    list_display = (
        "assembly",
        "bgc_count",
        "bgc_diversity_score",
        "bgc_novelty_score",
        "bgc_density",
    )


@admin.register(BgcScore)
class BgcScoreAdmin(admin.ModelAdmin):
    list_display = ("bgc", "novelty_score", "domain_novelty", "size_kb", "classification_l1")
    list_filter = ("classification_l1", "is_validated")
