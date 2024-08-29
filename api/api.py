import re
from ninja import NinjaAPI
from ninja.pagination import paginate
from ninja.errors import HttpError
from typing import Any, List, Optional, Union, Tuple
from enum import Enum
from api.services import search_bgcs_by_keyword, search_bgcs_by_advanced
from django.db.models import Q
from ninja import Query
import pandas as pd
from .models import Bgc, BgcClass, BgcDetector, Contig, Assembly, Biome, Protein, Metadata
from .schemas import Aggregate, PfamStrategy
from .schemas import BgcSearchOutputSchema, BgcSearchUserOutputSchema, BgcSearchInputSchema, OutputType, BgcSearchCallSchema
from .utils import RegionFeatureError, get_region_features, complex_bgc_search, search_keyword_in_models
from .generate_outputs import WriteRegion
from .aggregate_bgcs import BgcAggregator
from django.http import Http404, HttpResponse
from bgc_plots.contig_region_visualisation import ContigRegionViewer
from bgc_data_portal import __version__, __name__, __description__


api = NinjaAPI(
    title="MGnify Biosynthetic Gene Clusters Portal API",
    description="API for accessing and retrieving biosynthetic gene cluster predictions from metagenomic assemblies.",
    version=__version__,
    docs_url="/docs/"
)

@api.exception_handler(HttpError)
def custom_error_handler(request, exc):
    """
    Handles errors returned by the API, providing a clear error message.
    """
    return api.create_response(
        request,
        {"detail": str(exc)},
        status=exc.status_code,
    )

# Constants for BGC completeness and detector names
_PARTIALS = ['full_length', 'single_truncated', 'double_truncated']
_DETECTORS = ['antiSMASH', 'GECCO', 'SanntiS']

def perform_keyword_search(keyword: Optional[str] = None):
    """
    Searches BGCs by a given keyword. If no keyword is provided, returns all BGCs.

    :param keyword: A keyword to search across BGCs and associated data.
    :return: A list of BGCs matching the keyword search.
    """
    if keyword is None:
        bgcs = Bgc.objects.all()
    else:
        matching_bgcs = search_keyword_in_models(keyword)
        bgcs = Bgc.objects.filter(mgyb__in=matching_bgcs)

    return ( 
        [ BgcSearchUserOutputSchema(
            mgybs=[bgc.mgyb],
            assembly_accession=bgc.mgyc.assembly.accession,
            contig_mgyc=bgc.mgyc.mgyc,
            start_position=bgc.start_position,
            end_position=bgc.end_position,
            bgc_detector_names=[bgc.bgc_detector.bgc_detector_name],
            bgc_class_names=[bgc.bgc_class.bgc_class_name]
        ) for bgc in bgcs ], 
        bgcs
    )

def perform_complex_search(params: BgcSearchCallSchema):
    """
    Performs a complex search for BGCs based on multiple criteria.

    :param params: Parameters for complex BGC search, including detector names, BGC class, assembly accession, and others.
    :return: A list of aggregated BGCs based on the search criteria.
    """
    detectors = [name for name, value in zip(_DETECTORS, [params.antismash, params.gecco, params.sanntis]) if value]
    pfams = re.split(r"[,\s]", params.protein_pfam)
    
    bgcs = complex_bgc_search(
        detectors,
        params.bgc_class_name,
        params.mgyb,
        params.assembly_accession,
        params.contig_mgyc,
        params.full_length,
        params.single_truncated,
        params.double_truncated,
        params.biome_lineage,
        pfams,
        params.pfam_strategy.value,
    )

    individual_bgcs = [
        BgcSearchInputSchema(
            mgyb=bgc.mgyb,
            assembly_accession=bgc.mgyc.assembly.accession,
            contig_mgyc=bgc.mgyc.mgyc,
            start_position=bgc.start_position,
            end_position=bgc.end_position,
            bgc_detector_name=bgc.bgc_detector.bgc_detector_name,
            bgc_class_name=bgc.bgc_class.bgc_class_name,
        )
        for bgc in bgcs
    ]

    # Aggregate BGC regions according to the selected strategy
    aggregate_function = getattr(BgcAggregator, params.aggregate_strategy.value)
    aggregated_bgcs = aggregate_function(individual_bgcs, detectors)

    return ([
        BgcSearchUserOutputSchema(
            mgybs=aggregated_bgc.mgybs,
            assembly_accession=aggregated_bgc.assembly_accession,
            contig_mgyc=aggregated_bgc.contig_mgyc,
            start_position=aggregated_bgc.start_position,
            end_position=aggregated_bgc.end_position,
            bgc_detector_names=aggregated_bgc.bgc_detector_names,
            bgc_class_names=aggregated_bgc.bgc_class_names,
        ) for aggregated_bgc in aggregated_bgcs 
        ], 
        bgcs
    )

@api.get("/search/", response=List[BgcSearchUserOutputSchema], tags=["Search"], summary="Keyword search for BGCs")
@paginate
def search_by_keyword(request, keyword: str):
    """
    Perform a keyword search across the BGC Portal.

    Use this endpoint to retrieve BGCs based on keywords or accession numbers.
    This is equivalent to the portal's keyword search.
    """
    search_results = search_bgcs_by_keyword(keyword)

    return [ BgcSearchUserOutputSchema( mgybs=bgc.mgybs,
                    assembly_accession=bgc.mgyc.assembly.accession,
                    contig_mgyc=bgc.mgyc.mgyc,
                    start_position=bgc.start_position,
                    end_position=bgc.end_position,
                    bgc_detector_names=bgc.bgc_detector_names,
                    bgc_class_names=bgc.bgc_class_names
            ) 
            for bgc in search_results 
    ]

@api.get("/bgcs/", response=List[BgcSearchUserOutputSchema], tags=["Search"], summary="Advanced search for BGCs")
@paginate
def search_bgcs(request, params: BgcSearchCallSchema = Query(...)):
    """
    Execute a detailed search across the BGC Portal.

    This endpoint allows for advanced queries using various criteria such as BGC class, 
    detector names, biome lineage, Pfam domains, and more. 
    The search results reflect the data shown on the "Explore BGCs" page of the portal.
    """
    aggregated_result, _ = perform_complex_search(params)
    return aggregated_result

@api.get("/contig_region/", tags=["Data download"], summary="Download BGC data by contig region")
def download_bgcs(request, 
                 mgyc: str = None, 
                 start_position: int = None, 
                 end_position: int = None,
                 output_type: OutputType = OutputType.fasta,
                 precomuted_data: Optional[Any] = False # Leave as false
                 ):
    """
    Download data related to a specific BGC region within a contig.

    Provide the MGYC, start position, and end position to retrieve the BGC data 
    in your desired format (FASTA, GeneBank, JSON, GFF3).
    - **precomuted_data**: Should be set as false
    """

    if str(precomuted_data).lower()!='false':
       contig, assembly_accession, features_df = precomuted_data
    else:
        try:
            contig, assembly_accession, features_df = get_region_features(mgyc, start_position, end_position)
        except RegionFeatureError as e:
            raise Http404(str(e))

    # Generate the requested output format
    write_output_function = getattr(WriteRegion, output_type.value)
    output_content = write_output_function(contig, start_position, end_position, assembly_accession, features_df)

    # Return the file as an HTTP response
    response = HttpResponse(output_content, content_type=f'contig_region/{output_type}')
    response['Content-Disposition'] = f'attachment; filename="{mgyc}_{start_position}_{end_position}.{output_type.value}"'
    return response

@api.get("/contig_region_plot/", tags=["Visualisation"], summary="Visualise a BGC Region")
def get_contig_region_plot(request, 
                           mgyc: str = None, 
                           start_position: int = None, 
                           end_position: int = None,
                           precomuted_data: Optional[Any] = False # Leave as false
                           ):
    """
    Generate and return a plot visualizing the BGC region within a contig.

    Provide the MGYC, start position, and end position to view the BGC region. 
    The plot includes coding regions, Pfam annotations, and BGC predictions from various detectors.
    - **precomuted_data**: Should be set as false
    """
    if str(precomuted_data).lower()!='false':
        _, _, features_df = precomuted_data
    else:
        _, _, features_df = get_region_features(mgyc, start_position, end_position)
    
    plot_html,_ = ContigRegionViewer.plot_contig_region(features_df)
    return plot_html
