from ninja import Schema
from typing import Optional, List

class BGCOutputSchema(Schema):
    bgc_accession: str
    assembly_accession: str
    contig_mgyc: str
    start_position: int
    end_position: int
    bgc_detector_name: str
    bgc_class_name: str

class BGCSearchSchema(Schema):
    bgc_detector_name: Optional[str] = None
    bgc_class_name: Optional[str] = None
    bgc_accession: Optional[str] = None
    assembly_accession: Optional[str] = None
    contig_mgyc: Optional[str] = None
    bgc_partial: Optional[int] = None
    biome_lineage: Optional[str] = None
    keyword: Optional[str] = None
    protein_pfam: Optional[str] = None