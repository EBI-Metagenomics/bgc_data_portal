from typing import Literal, Optional
from pydantic import BaseModel, Field


# ------------------------------------
# CORE Ingestion Schemas
# ------------------------------------


class StudyIn(BaseModel):
    accession: str = Field(..., max_length=255)


class StudyRow(BaseModel):
    kind: Literal["study"] = "study"
    payload: StudyIn


class BiomeIn(BaseModel):
    lineage: Optional[str] = Field(None, max_length=255)


class BiomeRow(BaseModel):
    kind: Literal["biome"] = "biome"
    payload: BiomeIn


class AssemblyIn(BaseModel):
    accession: str = Field(..., max_length=255)
    collection: Optional[str] = Field(None, max_length=255)
    study_accession: Optional[str] = None  # natural key for Study FK
    biome_lineage: Optional[str] = None  # natural key for Biome FK


class AssemblyRow(BaseModel):
    kind: Literal["assembly"] = "assembly"
    payload: AssemblyIn


class ContigIn(BaseModel):
    sequence_sha256: str = Field(..., max_length=64)
    mgyc: Optional[str] = Field(None, max_length=255)
    name: Optional[str] = Field(None, max_length=255)
    length: Optional[int] = None
    source_organism: Optional[dict] = None
    sequence: str
    assembly_accession: Optional[str] = None  # natural key for Assembly FK


class ContigRow(BaseModel):
    kind: Literal["contig"] = "contig"
    payload: ContigIn


class BgcClassIn(BaseModel):
    name: str = Field(..., max_length=255)


class BgcClassRow(BaseModel):
    kind: Literal["bgc_class"] = "bgc_class"
    payload: BgcClassIn


class BgcDetectorIn(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    tool: Optional[str] = Field(None, max_length=255)
    version: Optional[str] = Field(None, max_length=50)


class BgcDetectorRow(BaseModel):
    kind: Literal["bgc_detector"] = "bgc_detector"
    payload: BgcDetectorIn


class BgcIn(BaseModel):
    contig_sequence_sha256: Optional[str] = None  # natural key for Contig FK
    detector_name: Optional[str] = None  # natural key for BgcDetector.name
    identifier: str = Field(..., max_length=255)
    start_position: int
    end_position: int
    metadata: Optional[dict] = None
    is_partial: bool = False
    classes: list[str] = []  # list of BgcClass.name
    embedding: Optional[list[float]] = None


class BgcRow(BaseModel):
    kind: Literal["bgc"] = "bgc"
    payload: BgcIn


class DomainIn(BaseModel):
    name: str = Field(..., max_length=255)
    acc: str = Field(..., max_length=50)
    ref_db: str = Field(..., max_length=50)
    description: Optional[str] = None


class DomainRow(BaseModel):
    kind: Literal["domain"] = "domain"
    payload: DomainIn


class ProteinIn(BaseModel):
    sequence: str
    sequence_sha256: str = Field(..., max_length=64)
    cluster_representative: Optional[str] = None  # sequence_sha256 of rep
    embedding: list[float]


class ProteinRow(BaseModel):
    kind: Literal["protein"] = "protein"
    payload: ProteinIn


class ProteinDomainIn(BaseModel):
    protein_sequence_sha256: str
    domain_acc: str
    start_position: int
    end_position: int
    score: Optional[float] = None


class ProteinDomainRow(BaseModel):
    kind: Literal["protein_domain"] = "protein_domain"
    payload: ProteinDomainIn


class GeneCallerIn(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    tool: Optional[str] = Field(None, max_length=255)
    version: Optional[str] = Field(None, max_length=50)


class GeneCallerRow(BaseModel):
    kind: Literal["gene_caller"] = "gene_caller"
    payload: GeneCallerIn


class CdsIn(BaseModel):
    protein_sequence_sha256: str
    contig_sequence_sha256: str
    gene_caller_name: Optional[str] = None
    gene_caller_version: Optional[str] = None
    start_position: int
    end_position: int
    strand: int
    protein_identifier: Optional[str] = None
    pipeline_version: str = Field(..., max_length=50)


class CdsRow(BaseModel):
    kind: Literal["cds"] = "cds"
    payload: CdsIn


# ------------------------------------
# SECONDARY Ingestion Schemas
# ------------------------------------
class UMAPManifest(BaseModel):
    n_neighbors: int
    min_dist: float
    metric: str
    pca_components: int
    n_samples_fit: int
    sha256: str
    model_file: str
    coords_file: str
    sklearn_version: str
    umap_version: str
