"""Pydantic schemas for the Discovery Platform API."""

from datetime import datetime

from ninja import Schema

# ── Pagination ────────────────────────────────────────────────────────────────


class PaginationMeta(Schema):
    page: int
    page_size: int
    total_count: int
    total_pages: int


# ── Assembly schemas ─────────────────────────────────────────────────────────


# ── Detector / Region schemas ─────────────────────────────────────────────────


# ── Source BGC prediction (per-tool drill-down) ────────────────────────────


class DomainArchitectureItem(Schema):
    domain_acc: str
    domain_name: str
    ref_db: str
    start: int
    end: int
    score: float | None = None
    url: str = ""


class ParentAssemblySummary(Schema):
    # ``None`` for ephemeral asset-upload assemblies that have no DB row.
    assembly_id: int | None = None
    accession: str
    organism_name: str | None = None
    source_name: str | None = None
    is_type_strain: bool = False
    url: str = ""


# ── iBGC (Integrated BGC) schemas ──────────────────────────────────────────


class IbgcRosterItem(Schema):
    """Row in the iBGC-level results table.

    iBGCs are the primary unit. Each iBGC consolidates one or more
    ``SourceBgcPrediction`` rows; the table here flattens metadata the
    UI needs in the roster view.
    """

    id: int
    accession: str = ""  # MGYB-XXXXXX-YY (stable)
    label: str  # human-facing identifier (e.g. "iBGC-12345")
    cbgc_accession: str | None = None
    classification_path: str = ""  # leaf GCF path (gene_cluster_family)
    bgc_class: str = ""  # normalised product class (Polyketide, NRP, Hybrid(P+N), …)
    size_kb: float = 0.0  # (end - start) / 1000
    n_source_bgcs: int = 0
    source_tools: list[str] = []
    novelty_score: float | None = None
    domain_novelty: float | None = None
    is_partial: bool = False
    is_validated: bool = False
    is_type_strain: bool = False  # any source BGC sits on a type-strain assembly
    parent_assembly_id: int | None = None
    parent_assembly_accession: str | None = None
    parent_assembly_collection: str | None = None  # assembly source name
    organism_name: str | None = None
    contig_accession: str | None = None
    similarity_score: float | None = None  # filled by similar-ibgc / query
    # Populated only by sequence-protein search responses — the protein_id
    # of the highest-bitscore CDS within the iBGC, and that CDS's aggregate
    # alignment stats. Percent identity and query coverage are 0–100.
    best_hit_protein_id: str | None = None
    best_pident: float | None = None
    best_qcoverage: float | None = None
    # True for iBGCs sourced from an uploaded asset (negative id, ephemeral).
    is_asset: bool = False


class PaginatedIbgcRosterResponse(Schema):
    items: list[IbgcRosterItem]
    pagination: PaginationMeta


class IbgcIdsResponse(Schema):
    """Bulk iBGC ids matching the active filter surface.

    Powers the roster's "Add all to shortlist" action. ``truncated`` is
    True when the underlying filter would have matched more than ``ids``
    carries — callers should surface that to the user.
    """

    ids: list[int]
    total_count: int
    truncated: bool


# ── Combined multi-criterion query ─────────────────────────────────────────


class CombinedQueryCriterion(Schema):
    """One scoring criterion instance in a combined query.

    ``id`` is a stable, client-generated per-instance key — it is what the
    roster columns and Variables-map axes reference, so two criteria of the same
    ``type`` (e.g. a domain AND filter and a domain OR filter) stay distinct.
    ``params`` carries the criterion-specific fields (validated server-side):

    * ``domain`` — ``domains_text``, ``logic`` (``and``/``or``), ``threshold``
    * ``architecture`` — ``architecture`` (list), ``weight``, ``k``, ``threshold``
    * ``sequence`` — ``sequence``, ``min_bitscore``, ``min_pident``, ``min_qcov``
    * ``similar`` — ``ibgc_id``, ``k``
    """

    id: str
    type: str  # domain | architecture | sequence | similar
    params: dict = {}


class CombinedQueryFilters(Schema):
    """Non-scoring narrowing filters applied to the criteria intersection.

    Mirrors the ``_apply_ibgc_filters`` kwargs the single-criterion endpoints
    accept as query params; every field is optional and defaults to "no narrowing".
    """

    include_partials: bool = True
    validated_only: bool = False
    min_length_kb: float | None = None
    max_length_kb: float | None = None
    min_novelty: float | None = None
    max_novelty: float | None = None
    min_domain_novelty: float | None = None
    max_domain_novelty: float | None = None
    detector_tools: str | None = None
    source_tools: str | None = None  # deprecated alias for detector_tools
    source_names: str | None = None
    assembly_type: str | None = None
    leaf_path_prefix: str | None = None
    bgc_class: str | None = None
    npc_terms: str | None = None
    npc_confident: bool = True
    accession: str | None = None
    bgc_accession: str | None = None
    assembly_accession: str | None = None
    assembly_ids: str | None = None
    organism: str | None = None
    biome_lineage: str | None = None
    taxonomy_path: str | None = None
    domain_text: str | None = None


class CombinedQueryRequest(Schema):
    criteria: list[CombinedQueryCriterion] = []
    filters: CombinedQueryFilters | None = None


class CombinedQueryAccepted(Schema):
    task_id: str


class CriterionMetricSchema(Schema):
    """One sortable column a criterion contributes (``key`` indexes the score payload)."""

    key: str
    label: str
    sortable: bool = True


class CriterionColumn(Schema):
    """Column descriptor for one criterion instance — drives roster columns / map axes.

    Sort the roster/map by ``score:<id>`` (the criterion's primary ``value``) or
    ``score:<id>:<metric.key>`` for a secondary metric (e.g. a sequence pident).
    """

    id: str
    type: str
    label: str
    metrics: list[CriterionMetricSchema]


class CriterionScore(Schema):
    """A single criterion's score for one iBGC. ``value`` is the primary metric.

    The ``pident`` / ``qcoverage`` / ``best_hit_protein_id`` fields are populated
    for sequence-search criteria only.
    """

    value: float | None = None
    pident: float | None = None
    qcoverage: float | None = None
    best_hit_protein_id: str | None = None


class CombinedRosterItem(IbgcRosterItem):
    """Roster row carrying one score payload per criterion, keyed by criterion id."""

    scores: dict[str, CriterionScore] = {}


class CombinedRosterResponse(Schema):
    items: list[CombinedRosterItem]
    pagination: PaginationMeta
    criteria: list[CriterionColumn]


class CombinedScoreRow(Schema):
    id: int
    scores: dict[str, CriterionScore] = {}


class CombinedScoresResponse(Schema):
    """Compact, full (capped) combined-query payload for the Variables map.

    ``ibgc_ids_token`` resolves the result allow-list for the scatter / count /
    roster GET endpoints (avoids threading thousands of ids through the URL).
    """

    items: list[CombinedScoreRow]
    criteria: list[CriterionColumn]
    total_matched: int
    capped: bool
    cap: int
    ibgc_ids_token: str
    warnings: list[str] = []


class IbgcMemberBgc(Schema):
    """Source BGC prediction contributing to an iBGC (drill-down list)."""

    id: int
    accession: str  # prediction_accession
    detector_name: str | None = None
    detector_version: str | None = None
    is_partial: bool = False
    is_validated: bool = False
    size_kb: float = 0.0
    score: float | None = (
        None  # detector-native region score (SanntiS 1.0 mean ORF score, GECCO p)
    )
    probability: float | None = (
        None  # detector BGC probability (SanntiS 1.0: 1 - p_non_bgc)
    )
    classification_path: str = ""  # raw per-tool class string


class NpcLabelOut(Schema):
    """NPClassifier label of an iBGC (union of its source predictions)."""

    term_id: str
    level: str  # pathway | superclass | class
    name: str
    score: float | None = None
    confident: bool = False
    sources: list[str] = []  # predicted | curated
    detector_tools: list[str] = []


class IbgcDetail(Schema):
    id: int
    accession: str = ""  # MGYB-XXXXXX-YY (stable)
    cbgc_accession: str | None = None
    label: str
    classification_path: str = ""
    bgc_class: str = ""  # normalised product class (Polyketide, NRP, Hybrid(P+N), …)
    size_kb: float = 0.0
    start_position: int = 0
    end_position: int = 0
    contig_accession: str | None = None
    source_tools: list[str] = []
    novelty_score: float | None = None
    domain_novelty: float | None = None
    is_partial: bool = False
    is_validated: bool = False
    is_type_strain: bool = False
    parent_assembly: ParentAssemblySummary | None = None
    region_endpoint_url: str | None = None  # /api/discovery/ibgcs/{id}/region/
    member_bgcs: list[IbgcMemberBgc] = []
    domain_architecture: list[DomainArchitectureItem] = []
    npc_labels: list[NpcLabelOut] = []


class IbgcScatterPoint(Schema):
    """Point for the Variables Map (axes chosen from numeric iBGC columns)."""

    id: int
    x: float
    y: float
    classification_path: str = ""
    bgc_class: str = ""  # normalised product class (Polyketide, NRP, Hybrid(P+N), …)
    novelty_score: float | None = None
    domain_novelty: float | None = None
    is_partial: bool = False
    is_validated: bool = False
    is_type_strain: bool = False
    similarity_score: float | None = None
    is_asset: bool = False


class IbgcCountResponse(Schema):
    """Filter-surface count + capping metadata for the dashboard.

    Used by the v2 Discovery dashboard to drive the empty-state guard and
    the "showing X of Y, sampled" banner *before* firing the expensive
    roster / Variables-map requests. Same filter surface as
    ``/ibgcs/roster/``.
    """

    exact_count: int
    cap: int
    will_sample: bool


class IbgcIdSetRequest(Schema):
    """A Run Query result allow-list to stash server-side.

    The dashboard POSTs the resolved id set here when it is too large to ride
    inline as an ``ibgc_ids`` CSV on the roster / map / count GET requests
    (which would exceed the HTTP request-line limit). Order is significant —
    it is preserved so ``sort_by=similarity`` keeps the caller's best-first
    rank.
    """

    ibgc_ids: list[int]


class IbgcIdSetResponse(Schema):
    """Short token referencing a cached :class:`IbgcIdSetRequest` list."""

    token: str
    n_ibgcs: int


class SimilarIbgcRequest(Schema):
    ibgc_id: int
    k: int = 25


class IbgcArchitectureResponse(Schema):
    """Pooled positional domain accessions for an iBGC.

    Lightweight payload for the "copy domain architecture" action — avoids
    pulling the full IbgcDetail. ``ordered_accs`` mirrors the ordering rule
    used by the clustering pipeline (CDS start, then domain start).
    """

    id: int
    label: str
    ordered_accs: list[str]


# ── Shortlist Report schemas ─────────────────────────────────────────────────


class ReportSnapshotRequest(Schema):
    ibgc_ids: list[int]
    # When negative ids are present in ``ibgc_ids`` the snapshot endpoint
    # resolves them out of the asset cache identified by ``asset_token``.
    asset_token: str | None = None


class ReportSnapshotResponse(Schema):
    token: str
    expires_at: str
    n_ibgcs: int


class DomainCompositionEntry(Schema):
    domain_acc: str
    domain_name: str = ""
    domain_description: str = ""
    go_slim: str = ""
    interpro_entry_acc: str = ""
    interpro_entry_description: str = ""
    # InterPro entry page (if integrated) else the signature's member-DB page;
    # "" when neither resolves.
    domain_url: str = ""
    ibgc_count: int
    fraction: float
    tier: str  # "core" | "variable" | "rare"


class DomainGoslimDomain(Schema):
    domain_acc: str
    domain_name: str = ""
    domain_description: str = ""
    interpro_entry_acc: str = ""


class DomainGoslimCell(Schema):
    category: str
    tier: str  # "core" | "variable" | "rare"
    count: int = 0
    domains: list[DomainGoslimDomain] = []


class DomainGoslimMatrix(Schema):
    categories: list[str] = []
    tiers: list[str] = []
    cells: list[DomainGoslimCell] = []


class DomainCompositionSummary(Schema):
    core_count: int = 0
    variable_count: int = 0
    rare_count: int = 0
    total_unique: int = 0
    rows: list[DomainCompositionEntry] = []


class GcfDistributionEntry(Schema):
    classification_path: str
    ibgc_count: int
    fraction: float


class CategoryCount(Schema):
    name: str
    count: int


class LengthBucket(Schema):
    label: str
    count: int


class ReportIbgcRow(Schema):
    id: int
    accession: str = ""  # MGYB-XXXXXX-YY
    cbgc_accession: str | None = None
    label: str
    classification_path: str = ""
    bgc_class: str = ""
    size_kb: float = 0.0
    start: int | None = None
    end: int | None = None
    novelty_score: float | None = None
    domain_novelty: float | None = None
    n_source_bgcs: int = 0
    source_tools: list[str] = []
    is_partial: bool = False
    is_validated: bool = False
    is_type_strain: bool = False
    parent_assembly_accession: str | None = None
    parent_assembly_id: int | None = None
    organism_name: str | None = None
    collection: str | None = None  # parent-assembly data source (MGnify/GTDB/…)
    biome_path: str = ""
    taxonomy_phylum: str | None = None
    taxonomy_path: str = ""  # full lineage dot-path
    contig_accession: str | None = None


class ReportAssemblyRow(Schema):
    id: int
    accession: str
    organism_name: str | None = None
    source_name: str | None = None
    biome_path: str = ""
    taxonomy_path: str = ""
    taxonomy_phylum: str | None = None
    assembly_size_mb: float | None = None
    total_bgcs_in_assembly: int = 0
    ibgcs_in_shortlist: int = 0
    is_type_strain: bool = False


class ReportPayload(Schema):
    token: str
    generated_at: str
    expires_at: str
    n_ibgcs: int
    n_assemblies: int
    ibgc_rows: list[ReportIbgcRow] = []
    domain_composition: DomainCompositionSummary = DomainCompositionSummary()
    gcf_distribution: list[GcfDistributionEntry] = []
    gcf_sunburst: list[dict] = []
    score_distributions: list[dict] = []
    completeness_bar: list[CategoryCount] = []
    bgc_class_pie: list[CategoryCount] = []
    length_histogram: list[LengthBucket] = []
    predictor_distribution: list[CategoryCount] = []
    source_distribution: list[CategoryCount] = []
    assembly_rows: list[ReportAssemblyRow] = []
    assembly_stats: dict = {}
    # iBGC-derived sunbursts (one count per iBGC). Items follow the
    # ``SunburstNode`` shape ({id, label, parent, count}); typed as ``dict``
    # because SunburstNode is defined further down in this module.
    taxonomy_sunburst: list[dict] = []
    biome_sunburst: list[dict] = []
    domain_goslim_matrix: DomainGoslimMatrix = DomainGoslimMatrix()

    # Inner shape is {label: str, values: list[float]} — kept as raw dict to
    # avoid a forward reference to ScoreDistribution defined further down.


# ── Filter schemas ────────────────────────────────────────────────────────────


class TaxonomyNode(Schema):
    name: str
    rank: str
    path: str = ""  # full ltree path to this node — use as the taxonomy_path filter
    count: int
    children: list["TaxonomyNode"] = []


class BgcClassOption(Schema):
    name: str
    count: int


class NpcTreeNode(Schema):
    """NPClassifier ontology node (pathway → superclass → class) with iBGC counts."""

    term_id: str  # e.g. NPC:pathway:polyketides — the npc_terms filter value
    level: str
    name: str
    count: int  # iBGCs labelled with exactly this term (any confidence)
    confident_count: int
    children: list["NpcTreeNode"] = []


class GcfOption(Schema):
    family_path: str
    level: int
    member_count: int
    validated_count: int
    mean_novelty: float


class PaginatedGcfResponse(Schema):
    items: list[GcfOption]
    pagination: PaginationMeta


class SourceOption(Schema):
    name: str
    count: int


class PaginatedSourceResponse(Schema):
    items: list[SourceOption]
    pagination: PaginationMeta


class DetectorOption(Schema):
    tool: str
    count: int


class PaginatedDetectorResponse(Schema):
    items: list[DetectorOption]
    pagination: PaginationMeta


# ── Query mode schemas ────────────────────────────────────────────────────────


# ── Stats schemas ────────────────────────────────────────────────────────────


class SunburstNode(Schema):
    id: str
    label: str
    parent: str = ""
    count: int = 0


class ScoreDistribution(Schema):
    label: str
    values: list[float] = []


class CoreDomain(Schema):
    acc: str
    name: str
    bgc_count: int = 0
    fraction: float = 0.0


class BgcClassCount(Schema):
    name: str
    count: int = 0


class BgcStatsResponse(Schema):
    core_domains: list[CoreDomain] = []
    score_distributions: list[ScoreDistribution] = []
    complete_count: int = 0
    partial_count: int = 0
    npc_sunburst: list[SunburstNode] = (
        []
    )  # NPClassifier pathway/superclass/class (confident labels)
    bgc_class_distribution: list[BgcClassCount] = []
    total_bgcs: int = 0


# ── Export schemas ────────────────────────────────────────────────────────────


# ── BGC Region schemas ───────────────────────────────────────────────────────


class PfamAnnotationOut(Schema):
    """Per-signature domain hit. One row per BgcDomain. ``go_slim`` is the
    deduplicated list of slim names derived from the signature's GO terms.

    Deprecated by ``InterproAnnotationOut`` (collapsed by IPS entry) — kept
    for one release while the frontend migrates.
    """

    accession: str
    description: str = ""
    go_slim: list[str] = []
    envelope_start: int = 0
    envelope_end: int = 0
    e_value: str | None = None
    url: str = ""


class InterproAnnotationOut(Schema):
    """Non-redundant CDS annotation row, deduplicated by InterPro entry.

    When the signature maps to an InterPro entry (``interpro_entry_acc`` set
    on the BgcDomain row), all signatures sharing that entry collapse into
    one row carrying the entry accession and description. Signatures with no
    entry mapping fall back to the signature accession.
    """

    accession: str
    description: str = ""
    go_slim: list[str] = []
    envelope_start: int = 0  # min start across collapsed signatures
    envelope_end: int = 0  # max end across collapsed signatures
    e_value: str | None = None  # best (smallest) e-value across signatures
    url: str = ""


class RegionCdsOut(Schema):
    protein_id: str
    start: int
    end: int
    strand: int
    protein_length: int
    gene_caller: str = ""
    cluster_representative: str | None = None
    cluster_representative_url: str | None = None
    sequence: str = ""
    pfam: list[PfamAnnotationOut] = []
    # Non-redundant InterPro-entry annotations for the protein info card.
    interpro: list[InterproAnnotationOut] = []
    # Tools whose source-BGC prediction range covers this CDS, within the
    # owning iBGC. Range-overlap derived at request time; not stored.
    # Empty for the per-prediction BGC region endpoint.
    claimed_by_tools: list[str] = []


class RegionDomainOut(Schema):
    accession: str
    description: str = ""
    start: int
    end: int
    strand: int
    score: float | None = None
    go_slim: list[str] = []
    parent_cds_id: str = ""
    url: str = ""


class RegionClusterOut(Schema):
    accession: str
    start: int
    end: int
    source: str = ""
    bgc_classes: list[str] = []


class BgcRegionOut(Schema):
    """Region payload for a single source-BGC prediction (drill-down)."""

    region_length: int
    window_start: int
    window_end: int
    cds_list: list[RegionCdsOut] = []
    domain_list: list[RegionDomainOut] = []
    cluster_list: list[RegionClusterOut] = []


class IbgcRegionOut(Schema):
    """Merged region payload for an iBGC — all CDS overlapping bgc_range.

    Bug fix for the legacy "primary BGC" view: ``cds_list`` is the union of
    every ``ContigCds`` that overlaps the iBGC's genomic span, regardless
    of which source tool listed it. ``claimed_by_tools`` on each CDS is the
    range-overlap attribution against the iBGC's ``SourceBgcPrediction``s.
    """

    ibgc_id: int
    ibgc_accession: str
    cbgc_accession: str
    region_length: int  # iBGC bgc_range size, in bp
    window_start: int
    window_end: int
    contig_accession: str | None = None
    cds_list: list[RegionCdsOut] = []
    domain_list: list[RegionDomainOut] = []
    # Each source prediction's range, for per-tool tinting in the region plot.
    cluster_list: list[RegionClusterOut] = []


# ── Accession resolve ─────────────────────────────────────────────────────────


# Assessment schemas removed in v2 — the Evaluate Asset feature was
# replaced by the Shortlist Report endpoints (ReportPayload above).


# ── Platform overview ─────────────────────────────────────────────────────────


class DiscoveryStatsResponse(Schema):
    genomes: int = 0
    metagenomes: int = 0
    validated_bgcs: int = 0
    ibgcs: int = 0
    total_bgc_predictions: int = 0
    updated_at: datetime | None = None


# ── Ephemeral asset upload schemas ──────────────────────────────────────────


class AssetUploadAccepted(Schema):
    """Response for ``POST /assets/upload/`` — async processing started."""

    token: str
    task_id: str


class AssetStatusResponse(Schema):
    """Polling response for ``GET /assets/{token}/status/``.

    ``state`` is one of ``PENDING``, ``RUNNING``, ``SUCCESS``, ``FAILED``,
    ``UNKNOWN`` (when the token has expired or never existed).
    """

    state: str
    task_id: str | None = None
    progress: dict | None = None
    error: str | None = None
    summary: dict | None = None
