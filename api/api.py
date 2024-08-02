
from ninja import NinjaAPI, Schema, ModelSchema
from ninja.pagination import paginate
from ninja.errors import HttpError
from typing import List, Optional
from .models import Bgc, BgcClass, BgcDetector, Contig, Assembly, Biome, Protein
from .schemas import BGCOutputSchema, BGCSearchSchema
api = NinjaAPI()


@api.exception_handler(HttpError)
def custom_error_handler(request, exc):
    return api.create_response(
        request,
        {"detail": str(exc)},
        status=exc.status_code,
    )

@api.get("/bgc/", response=List[BGCOutputSchema])
@paginate
def search_bgc(request, bgc_detector_name: Optional[str] = None, 
                      bgc_class_name: Optional[str] = None, 
                      bgc_accession: Optional[str] = None, 
                      assembly_accession: Optional[str] = None, 
                      contig_mgyc: Optional[str] = None, 
                      bgc_partial: Optional[int] = None, 
                      biome_lineage: Optional[str] = None, 
                      keyword: Optional[str] = None, 
                      protein_pfam: Optional[str] = None):
    
    qs = Bgc.objects.select_related('bgc_detector', 'bgc_class', 'mgyc__assembly__biome').all()

    # print(f"Query Set: {qs.first()}")
    print(Bgc.objects.count())

    if bgc_detector_name:
        qs = qs.filter(bgc_detector__bgc_detector_name__icontains=bgc_detector_name)
    
    if bgc_class_name:
        qs = qs.filter(bgc_class__bgc_class_name__icontains=bgc_class_name)
    
    if bgc_accession:
        qs = qs.filter(bgc_accession__icontains=bgc_accession)
    
    if assembly_accession:
        qs = qs.filter(mgyc__assembly__accession__icontains=assembly_accession)
    
    if contig_mgyc:
        qs = qs.filter(mgyc__icontains=contig_mgyc)
    
    if bgc_partial is not None:
        qs = qs.filter(partial=bgc_partial)
    
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
    
    return [
        BGCOutputSchema(
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

