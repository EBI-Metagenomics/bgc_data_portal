# filters.py
import django_filters
from django.db.models import Q, F
from .models import Bgc, Contig, Protein, Metadata
from .utils import mgyb_converter
import django_filters
from django.db.models import Q, F
from functools import reduce
from operator import and_, or_
from .models import Bgc

class BgcKeywordFilter(django_filters.FilterSet):

    @staticmethod
    def filter_by_keyword(queryset, name, value):
        # Build the BGC query
        bgc_query = Q(bgc_metadata__icontains=value)
        
        if value.startswith("MGYB") and value[4:].isdigit():
            bgc_query |= Q(mgyb=mgyb_converter(value))
        
        # Filter Contig by the keyword
        contig_query = Q(mgyc=value)
        contig_query |= Q(
            Q(assembly__accession__icontains=value) |
            Q(assembly__study__accession__icontains=value) |
            Q(assembly__biome__lineage__icontains=value)
        )
        
        # Find matching contigs
        matching_contigs = Contig.objects.filter(contig_query)
        mgybs_from_contigs = Bgc.objects.filter(mgyc__in=matching_contigs).values_list('mgyb', flat=True)
        
        # Find proteins matching the keyword
        matching_proteins = Protein.objects.filter(Q(pfam__icontains=value))
        matching_metadata = Metadata.objects.filter(mgyp__in=matching_proteins)
        
        # BGCs that overlap with proteins/metadata on the same contig
        mgybs_from_protein_metadata = Bgc.objects.filter(
            Q(mgyc__metadata__in=matching_metadata) &
            Q(start_position__lte=F('mgyc__metadata__end_position')) &
            Q(end_position__gte=F('mgyc__metadata__start_position'))
        ).values_list('mgyb', flat=True)
        
        # Combine all found BGC ids
        combined_mgybs = set(mgybs_from_contigs) | set(mgybs_from_protein_metadata) | set(queryset.filter(bgc_query).values_list('mgyb', flat=True))
        return queryset.filter(mgyb__in=combined_mgybs)

    keyword = django_filters.CharFilter(method='filter_by_keyword')

    class Meta:
        model = Bgc
        fields = []



class BgcFilter(django_filters.FilterSet):
    bgc_class_name = django_filters.CharFilter(field_name='bgc_class__bgc_class_name', lookup_expr='icontains')
    mgyb = django_filters.CharFilter(lookup_expr='exact')
    assembly_accession = django_filters.CharFilter(field_name='mgyc__assembly__accession', lookup_expr='icontains')
    contig_mgyc = django_filters.CharFilter(field_name='mgyc__mgyc', lookup_expr='exact')
    biome_lineage = django_filters.CharFilter(field_name='mgyc__assembly__biome__lineage', lookup_expr='icontains')

    class Meta:
        model = Bgc
        fields = ['bgc_class_name', 'mgyb', 'assembly_accession', 'contig_mgyc', 'biome_lineage']
