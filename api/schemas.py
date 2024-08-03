from ninja import Schema
from typing import Optional, List, Set
from enum import Enum
from .models import BgcDetector

class BgcSearchInputSchema(Schema):
    bgc_id: int
    bgc_accession: str
    assembly_accession: str
    contig_mgyc: str
    start_position: int
    end_position: int
    bgc_detector_name: str
    bgc_class_name: str

class BgcSearchOutputSchema(Schema):
    bgc_ids: List[int]
    bgc_accessions: List[str]
    assembly_accession: str
    contig_mgyc: str
    start_position: int
    end_position: int
    bgc_detector_names: List[str]
    bgc_class_names: List[str]

class BgcSearchUserOutputSchema(Schema):
    bgc_accessions: List[str]
    assembly_accession: str
    contig_mgyc: str
    start_position: int
    end_position: int
    bgc_detector_names: List[str]
    bgc_class_names: List[str]


class PfamStrategy(Enum):
    union: str = 'union'
    intersection: str = 'intersection'
    
class Aggregate(Enum):
    single: str = 'single'
    union: str = 'union'
    intersection: str = 'intersection'