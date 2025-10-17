from typing import Any, Optional, Literal

from ninja import Schema


class TaskResponse(Schema):
    task_id: str


class JobStatusResponse(Schema):
    task_id: str
    status: str
    result: Optional[Any] = None


class KeywordSearchIn(Schema):
    """Mirror of BgcKeywordSearchForm."""

    keyword: str = ""


class AdvancedSearchIn(Schema):
    """Mirror of BgcAdvancedSearchForm. All fields optional.

    - completeness: list of 0,1,2 (Complete, Single bounded, Double bounded)
    - detectors: list of detector names (e.g. ["antiSMASH", "GECCO"]). Server resolves names to latest versions.
    - domain_strategy: 'intersection' (AND) or 'union' (OR)
    """

    bgc_class_name: Optional[str] = None
    mgyb: Optional[str] = None
    assembly_accession: Optional[str] = None
    contig_accession: Optional[str] = None
    biome_lineage: Optional[str] = None
    completeness: Optional[list[int]] = None
    protein_domain: Optional[str] = None
    domain_strategy: Optional[str] = "intersection"
    detectors: Optional[list[str]] = None


class SequenceSearchIn(Schema):
    """Mirror of SequenceSearchForm.

    similarity_threshold semantics:
    - when similarity_measure == 'hmmer' typical values are 0–100 (default ~32)
    - when similarity_measure == 'cosine' typical values are 0–1 (default ~0.85)
    set_similarity_threshold is used when unit_of_comparison == 'proteins'; if not
    provided in that case, it defaults to 0.5.
    """

    sequence: str
    sequence_type: str = "nucleotide"  # 'nucleotide' | 'protein'
    unit_of_comparison: str = "bgc"  # 'bgc' | 'proteins'
    similarity_measure: str = "hmmer"  # 'hmmer' | 'cosine'
    similarity_threshold: float = 32.0
    set_similarity_threshold: Optional[float] = None


class ChemicalSearchIn(Schema):
    """Mirror of ChemicalStructureSearchForm.

    Provide either smiles_text or smiles; when both are present we prefer
    smiles_text and place it into 'smiles' in the clean params.
    """

    similarity_threshold: float = 0.85
    smiles_text: Optional[str] = None
    smiles: Optional[str] = None


class DownloadBGCIn(Schema):
    """Query parameters for downloading a BGC in various formats.

    - bgc_id: BGC identifier (numeric id or MGYB accession)
    - output_type: one of 'gbk', 'fna', 'faa', 'json' (default 'gbk')
    """

    bgc_id: str
    output_type: Literal["gbk", "fna", "faa", "json"] = "gbk"


class DownloadResultsTSVIn(Schema):
    """Query parameters for downloading search results as TSV by task id.

    - task_id: Celery task id associated with the search
    - sort: column to sort by (default 'assembly_accession')
    - order: 'asc' or 'desc' (default 'asc')
    """

    task_id: str
