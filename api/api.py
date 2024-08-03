
from ninja import NinjaAPI, Schema, ModelSchema
from ninja.pagination import paginate
from ninja.errors import HttpError
from typing import List, Optional,Union
from enum import Enum
from django.db.models import Q
from ninja import Query
from .models import Bgc, BgcClass, BgcDetector, Contig, Assembly, Biome, Protein
from .schemas import Aggregate,PfamStrategy
from .schemas import BgcSearchOutputSchema, BgcSearchUserOutputSchema, BgcSearchInputSchema
from .aggregate_bgcs import BgcAggregator

api = NinjaAPI()


@api.exception_handler(HttpError)
def custom_error_handler(request, exc):
    return api.create_response(
        request,
        {"detail": str(exc)},
        status=exc.status_code,
    )

_detectors = ['antiSMASH','GECCO','SanntiS']
_partials = ['complete','single_truncated','double_truncated']

@api.get("/bgc/", response=List[BgcSearchUserOutputSchema])
@paginate
def search_bgc(request, 
              antismash: bool = True, 
              gecco: bool = True, 
              sanntis: bool = True, 
              bgc_class_name: Optional[str] = None, 
              bgc_accession: Optional[str] = None, 
              assembly_accession: Optional[str] = None, 
              contig_mgyc: Optional[str] = None, 
              complete: bool = True, # TODO, FUNCTION WRITEN BUT NEEDS DB MODEL AND POPULATE
              single_truncated: bool = True, 
              double_truncated: bool = True, 
              biome_lineage: Optional[str] = None, 
              keyword: Optional[str] = None, 
              protein_pfam: Optional[List[str]] = Query(None), # TODO
              pfam_strategy: PfamStrategy = None, # TODO
              aggragate_strategy: Aggregate = Aggregate.single,
              ):

    qs = Bgc.objects.select_related('bgc_detector', 'bgc_class', 'mgyc__assembly__biome').all()

    detectors = [name for name,value in zip(_detectors,[antismash,gecco,sanntis]) if value!=False]    
    if detectors:
        qs = qs.filter(Q(bgc_detector__bgc_detector_name__in=detectors))
    
    if bgc_class_name:
        qs = qs.filter(bgc_class__bgc_class_name__icontains=bgc_class_name)
    
    if bgc_accession:
        qs = qs.filter(bgc_accession__icontains=bgc_accession)
    
    if assembly_accession:
        qs = qs.filter(mgyc__assembly__accession__icontains=assembly_accession)
    
    if contig_mgyc:
        qs = qs.filter(mgyc__mgyc__icontains=contig_mgyc)
        # qs = qs.filter(mgyc__assembly__biome__lineage__icontains=biome_lineage)
    

    # TODO
    """
    partials = [name for name,value in zip(_partials,[complete,single_truncated,double_truncated]) if value!=False]    
    if partials:
        qs = qs.filter(Q(partial__partial_name__in=partials))
    """

    if biome_lineage:
        qs = qs.filter(mgyc__assembly__biome__lineage__icontains=biome_lineage)
    
    if keyword:
        qs = qs.filter(
            models.Q(bgc_class__bgc_class_name__icontains=keyword) |
            models.Q(mgyc__assembly__biome__lineage__icontains=keyword) |
            models.Q(bgc_metadata__icontains=keyword)
        )
    
    if protein_pfam:
        qs = qs.filter(mgyc__protein__pfam__icontains=protein_pfam)
    
    individual_bgcs = [
       BgcSearchInputSchema(
            bgc_id=bgc.bgc_id,
            bgc_accession=bgc.bgc_accession,
            assembly_accession=bgc.mgyc.assembly.accession,
            contig_mgyc=bgc.mgyc.mgyc,
            start_position=bgc.start_position,
            end_position=bgc.end_position,
            bgc_detector_name=bgc.bgc_detector.bgc_detector_name,
            bgc_class_name=bgc.bgc_class.bgc_class_name,
            )
            for bgc in qs
    ]

    # Agregte strategy function
    aggregate_function = getattr(BgcAggregator, aggragate_strategy.value)
    aggregated_bgcs = aggregate_function(individual_bgcs, detectors)

    return [
        BgcSearchUserOutputSchema(
            bgc_accessions=aggregated_bgc.bgc_accessions,
            assembly_accession=aggregated_bgc.assembly_accession,
            contig_mgyc=aggregated_bgc.contig_mgyc,
            start_position=aggregated_bgc.start_position,
            end_position=aggregated_bgc.end_position,
            bgc_detector_names=aggregated_bgc.bgc_detector_names,
            bgc_class_names=aggregated_bgc.bgc_class_names
        )
        for aggregated_bgc in aggregated_bgcs
    ]

