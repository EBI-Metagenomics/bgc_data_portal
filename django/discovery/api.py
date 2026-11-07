"""Discovery Platform API: the Django Ninja router mounted at /api/discovery/.

Endpoints documented in /api/docs are open and rate-limited; UI-only ones are
``include_in_schema=False`` and gated to same-origin browser traffic
(``discovery.security.first_party_gate``). Filtering lives in
``discovery.services.ibgc_filters``; this module only shapes responses.

Known limitation: ``domain_text`` matches any domain on the iBGC's contig, not
only those inside ``bgc_range`` (TODO(v2-range-overlap) in ibgc_filters).
"""

import json
import logging
import math

from django.db.models import (
    Count,
    ExpressionWrapper,
    FloatField,
    OuterRef,
    Subquery,
)
from django.http import HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError

from discovery.api_schemas import (
    AssetStatusResponse,
    AssetUploadAccepted,
    BgcClassOption,
    CombinedQueryAccepted,
    CombinedQueryRequest,
    CombinedRosterItem,
    CombinedRosterResponse,
    CombinedScoreRow,
    CombinedScoresResponse,
    CriterionColumn,
    CriterionMetricSchema,
    CriterionScore,
    DetectorOption,
    DiscoveryStatsResponse,
    DomainArchitectureItem,
    GcfOption,
    IbgcArchitectureResponse,
    IbgcCountResponse,
    IbgcDetail,
    IbgcIdSetRequest,
    IbgcIdSetResponse,
    IbgcIdsResponse,
    IbgcMemberBgc,
    IbgcRegionOut,
    IbgcRosterItem,
    IbgcScatterPoint,
    InterproAnnotationOut,
    NpcLabelOut,
    NpcTreeNode,
    PaginatedDetectorResponse,
    PaginatedGcfResponse,
    PaginatedIbgcRosterResponse,
    PaginatedSourceResponse,
    PaginationMeta,
    ParentAssemblySummary,
    PfamAnnotationOut,
    RegionCdsOut,
    RegionClusterOut,
    RegionDomainOut,
    ReportPayload,
    ReportSnapshotRequest,
    ReportSnapshotResponse,
    SimilarIbgcRequest,
    SourceOption,
    TaxonomyNode,
)
from discovery.models import (
    AssemblySource,
    ClusteringRun,
    ContigCds,
    ContigDomain,
    DashboardBgcClass,
    DashboardDetector,
    DashboardGCF,
    DiscoveryStats,
    IbgcNpcLabel,
    IntegratedBgc,
    SourceBgcPrediction,
)
from discovery.security import first_party_gate
from discovery.services.architecture import (
    collapse_to_interpro_rows,
    ibgc_architecture,
)
from discovery.services.ibgc_filters import (
    IbgcFilterParams,
    apply_ibgc_filters,
    apply_ibgc_sort,
    asset_only_mode,
    filters_active,
    ibgc_span_bp,
)
from discovery.services.npc import npc_tree
from discovery.throttling import (
    default_throttle,
    search_throttle,
    upload_throttle,
)

logger = logging.getLogger(__name__)

discovery_router = Router(tags=["Discovery Platform"], throttle=default_throttle)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _paginate(page: int, page_size: int, total_count: int):
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total_pages = max(1, math.ceil(total_count / page_size))
    offset = (page - 1) * page_size
    return page, page_size, total_pages, offset


# ── Shared filter helpers ────────────────────────────────────────────────────


# ── Assembly endpoints ───────────────────────────────────────────────────────


# ── BGC endpoints ────────────────────────────────────────────────────────────


# ── iBGC (Integrated BGC) endpoints ────────────────────────────────────────


_IBGC_AXES = {
    "size_kb",  # length / 1000
    "n_cds",
    "novelty_score",
    "domain_novelty",
    "similarity_score",  # populated only from a similarity query context
}


# Soft cap applied uniformly across the dashboard's "show me all matching
# iBGCs" surfaces: /ibgcs/scatter/ (Variables map points) and the client-side top-K clip on scored query results. The
# roster paginates and is *not* capped here. ``/ibgcs/count/`` surfaces this
# value so the UI can warn before firing the heavier requests.
DASHBOARD_RESULT_CAP = 5_000


# A Run Query result allow-list lives this long in the cache. Generous so a
# user can explore the roster/maps for a full session without the token
# expiring; the cap mirrors the report snapshot TTL.
IBGC_IDSET_TTL_SECONDS = 24 * 3600


def _ibgc_idset_cache_key(token: str) -> str:
    return f"ibgcset:{token}"


def _cache_ibgc_idset(ids: list[int]) -> tuple[str, int]:
    """Persist an ordered iBGC id allow-list in the cache and return ``(token, n)``.

    The dashboard's Run Query result can be thousands of ids; threading them
    back through ``/ibgcs/roster|scatter|count/`` as an ``ibgc_ids`` CSV
    blows past gunicorn's request-line limit (HTTP 414). Instead we stash the
    list server-side — the same DatabaseCache + token pattern as the shortlist
    Report — and the GET endpoints reference it via ``ibgc_ids_token``.

    Order is preserved (not sorted) so ``sort_by=similarity`` ranking by
    ``array_position`` keeps the caller's best-first order. The token hashes
    the ordered seed, so an identical ordered list resolves to the same token.
    """
    import hashlib

    from django.core.cache import cache

    seed = ",".join(str(i) for i in ids)
    token = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    cache.set(_ibgc_idset_cache_key(token), ids, IBGC_IDSET_TTL_SECONDS)
    return token, len(ids)


def _parse_ibgc_id_scope(
    ibgc_ids: str | None, ibgc_ids_token: str | None = None
) -> list[int] | None:
    """Resolve the iBGC id allow-list shared by the roster / maps / count / ids.

    Prefers ``ibgc_ids_token`` (a server-cached list minted by
    ``POST /ibgcs/idset/``) over the inline ``ibgc_ids`` CSV. A token that has
    expired from the cache is a hard 404 so the client re-runs its query rather
    than silently rendering the unfiltered catalogue.
    """
    if ibgc_ids_token:
        from django.core.cache import cache

        cached = cache.get(_ibgc_idset_cache_key(ibgc_ids_token))
        if cached is None:
            raise HttpError(
                404,
                "Result set expired — re-run your query to refresh it.",
            )
        return list(cached) or None
    if ibgc_ids:
        return [int(x) for x in ibgc_ids.split(",") if x.strip().isdigit()] or None
    return None


def _ibgc_label(ibgc_id: int) -> str:
    return f"iBGC-{ibgc_id}"


def _ibgc_is_partial(ibgc: IntegratedBgc) -> bool:
    """An iBGC is "partial" when it didn't go through the primary clustering
    pass — either no clustering run touched it, or its GCF / novelty were
    projected from its top-K primary neighbours (``is_partial=True``)."""
    return bool(ibgc.is_partial) or ibgc.classification_run_id is None


# ── Asset-iBGC injection helpers ───────────────────────────────────────────
#
# Uploaded assets are stored in Redis under ``asset:{token}:*`` and never hit
# the DB. Negative ids mark them everywhere — the dispatcher in this module
# routes ``ibgc_id < 0`` to the cache instead of the ORM. Asset iBGCs bypass
# every filter ("always shown in results") per the locked product decision.


def _ibgc_queryset(filters: IbgcFilterParams, parsed_ids, asset_token):
    """DB rows for the filter surface, or none() while an asset is shown alone."""
    if asset_only_mode(asset_token, parsed_ids, filters_active(filters)):
        return IntegratedBgc.objects.none()
    return apply_ibgc_filters(IntegratedBgc.objects.all(), filters, ibgc_ids=parsed_ids)


def _get_asset_roster_rows(asset_token: str | None) -> list[dict]:
    if not asset_token:
        return []
    from discovery.services.asset_upload import cache as asset_cache

    return list(asset_cache.read_ibgc_list(asset_token) or [])


def _asset_row_to_roster_item(row: dict) -> IbgcRosterItem:
    return IbgcRosterItem(
        id=int(row["id"]),
        label=row.get("label", ""),
        classification_path=row.get("classification_path", "") or "",
        size_kb=float(row.get("size_kb", 0.0) or 0.0),
        n_source_bgcs=int(row.get("n_source_bgcs", 0) or 0),
        source_tools=list(row.get("source_tools") or []),
        novelty_score=row.get("novelty_score"),
        domain_novelty=row.get("domain_novelty"),
        is_partial=bool(row.get("is_partial", False)),
        is_validated=bool(row.get("is_validated", False)),
        is_type_strain=bool(row.get("is_type_strain", False)),
        parent_assembly_id=row.get("parent_assembly_id"),
        parent_assembly_accession=row.get("parent_assembly_accession"),
        organism_name=row.get("organism_name"),
        contig_accession=row.get("contig_accession"),
        similarity_score=row.get("similarity_score"),
        best_hit_protein_id=row.get("best_hit_protein_id"),
        best_pident=row.get("best_pident"),
        best_qcoverage=row.get("best_qcoverage"),
        is_asset=True,
    )


def _asset_row_to_scatter_point(
    row: dict, x_axis: str, y_axis: str
) -> IbgcScatterPoint | None:
    # Asset rows expose the same numeric columns the DB rows do (novelty_score,
    # domain_novelty, size_kb). For non-existent axes we drop the point so the
    # surface stays consistent with the DB-row behaviour.
    axis_value: dict[str, float | None] = {
        "novelty_score": row.get("novelty_score"),
        "domain_novelty": row.get("domain_novelty"),
        "size_kb": row.get("size_kb"),
    }
    x_val = axis_value.get(x_axis)
    y_val = axis_value.get(y_axis)
    if x_val is None or y_val is None:
        return None
    return IbgcScatterPoint(
        id=int(row["id"]),
        x=float(x_val),
        y=float(y_val),
        classification_path=row.get("classification_path", "") or "",
        novelty_score=row.get("novelty_score"),
        domain_novelty=row.get("domain_novelty"),
        is_partial=bool(row.get("is_partial", False)),
        is_validated=bool(row.get("is_validated", False)),
        is_type_strain=bool(row.get("is_type_strain", False)),
        is_asset=True,
    )


def _ibgc_to_roster_item(
    ibgc: IntegratedBgc,
    facts: dict | None = None,
    *,
    similarity_score: float | None = None,
    best_hit_protein_id: str | None = None,
    best_pident: float | None = None,
    best_qcoverage: float | None = None,
) -> IbgcRosterItem:
    """Serialise one roster row; ``facts`` comes from ``_ibgc_member_facts``."""
    facts = facts or {}
    parent_assembly = facts.get("parent_assembly")
    return IbgcRosterItem(
        id=ibgc.id,
        accession=ibgc.accession or "",
        label=_ibgc_label(ibgc.id),
        cbgc_accession=facts.get("cbgc_accession"),
        classification_path=ibgc.gene_cluster_family or "",
        bgc_class=ibgc.bgc_class or "",
        size_kb=round((ibgc.end_position - ibgc.start_position) / 1000.0, 3),
        n_source_bgcs=facts.get("n_source_bgcs", 0),
        source_tools=list(ibgc.source_tools or []),
        novelty_score=ibgc.novelty_score,
        domain_novelty=ibgc.domain_novelty,
        is_partial=_ibgc_is_partial(ibgc),
        is_validated=facts.get("is_validated", False),
        is_type_strain=facts.get("is_type_strain", False),
        parent_assembly_id=parent_assembly.id if parent_assembly else None,
        parent_assembly_accession=(
            parent_assembly.assembly_accession if parent_assembly else None
        ),
        parent_assembly_collection=(
            getattr(parent_assembly, "source_name", None) if parent_assembly else None
        ),
        organism_name=parent_assembly.organism_name if parent_assembly else None,
        contig_accession=facts.get("contig_accession"),
        similarity_score=similarity_score,
        best_hit_protein_id=best_hit_protein_id,
        best_pident=best_pident,
        best_qcoverage=best_qcoverage,
    )


# Keep each `IN (...)` clause well under sqlparse's 10k-token cap (which
# Django's DEBUG-mode SQL logger trips on). At ~3 tokens per id (digits,
# comma, space) 500 ids is comfortably below the ceiling.
_MEMBER_FACTS_CHUNK = 500


def _ibgc_member_facts(ibgc_ids: list[int]) -> dict[int, dict]:
    """Return per-iBGC aggregates: ``n_source_bgcs``, ``is_validated``,
    ``is_type_strain``, ``parent_assembly``, ``contig_accession``.

    ``is_type_strain`` is ORed across every member BGC's parent assembly so
    an iBGC is flagged whenever *any* of its source BGCs sits on a
    type-strain assembly. Mirrors the ``is_validated`` accumulator.

    The SourceBgcPrediction lookup is chunked so the generated SQL stays under the
    DEBUG-mode SQL formatter's token limit on large id lists (scatter
    can request several thousand iBGCs in one call).
    """
    facts: dict[int, dict] = {
        nid: {
            "n_source_bgcs": 0,
            "is_validated": False,
            "is_type_strain": False,
            "parent_assembly": None,
            "contig_accession": None,
            "cbgc_accession": None,
        }
        for nid in ibgc_ids
    }
    # Parent cBGC accession per iBGC (one chunked query, no N+1).
    for i in range(0, len(ibgc_ids), _MEMBER_FACTS_CHUNK):
        chunk = ibgc_ids[i : i + _MEMBER_FACTS_CHUNK]
        for iid, cbgc_acc in IntegratedBgc.objects.filter(id__in=chunk).values_list(
            "id", "cbgc__accession"
        ):
            f = facts.get(iid)
            if f is not None:
                f["cbgc_accession"] = cbgc_acc
    for i in range(0, len(ibgc_ids), _MEMBER_FACTS_CHUNK):
        chunk = ibgc_ids[i : i + _MEMBER_FACTS_CHUNK]
        rows = (
            SourceBgcPrediction.objects.filter(integrated_bgc_id__in=chunk)
            .select_related("assembly", "assembly__source", "contig")
            .values(
                "integrated_bgc_id",
                "is_validated",
                "assembly_id",
                "assembly__assembly_accession",
                "assembly__organism_name",
                "assembly__source__name",
                "assembly__is_type_strain",
                "contig__accession",
            )
        )
        for r in rows:
            nid = r["integrated_bgc_id"]
            f = facts.get(nid)
            if not f:
                continue
            f["n_source_bgcs"] += 1
            f["is_validated"] = f["is_validated"] or bool(r["is_validated"])
            f["is_type_strain"] = f["is_type_strain"] or bool(
                r["assembly__is_type_strain"]
            )
            if f["parent_assembly"] is None and r["assembly_id"]:
                f["parent_assembly"] = type(
                    "AsmStub",
                    (),
                    {
                        "id": r["assembly_id"],
                        "assembly_accession": r["assembly__assembly_accession"],
                        "organism_name": r["assembly__organism_name"],
                        "source_name": r["assembly__source__name"],
                    },
                )()
            if not f["contig_accession"]:
                f["contig_accession"] = r["contig__accession"]
    return facts


@discovery_router.get("/ibgcs/count/", response=IbgcCountResponse)
def ibgc_count(
    request,
    filters: Query[IbgcFilterParams],
    ibgc_ids: str | None = None,
    ibgc_ids_token: str | None = None,
    asset_token: str | None = None,
):
    """Cheap COUNT over the iBGC filter surface.

    The dashboard hits this before firing /ibgcs/roster/ and /ibgcs/scatter/
    so it can gate the empty-state CTA when no scope is set and warn the user
    when the result will be sampled by the maps (count > DASHBOARD_RESULT_CAP).
    """
    parsed_ids = _parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    qs = _ibgc_queryset(filters, parsed_ids, asset_token)
    total = qs.count() + len(_get_asset_roster_rows(asset_token))
    return IbgcCountResponse(
        exact_count=total,
        cap=DASHBOARD_RESULT_CAP,
        will_sample=total > DASHBOARD_RESULT_CAP,
    )


@discovery_router.post(
    "/ibgcs/idset/",
    response=IbgcIdSetResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def ibgc_idset(request, body: IbgcIdSetRequest):
    """Stash a Run Query result allow-list server-side and return a short token.

    Lets the dashboard reference a multi-thousand-id result set from the
    roster / map / count GET endpoints via ``ibgc_ids_token=`` instead of a
    CSV that would overflow the HTTP request line (gunicorn 414). The id order
    is preserved so ``sort_by=similarity`` keeps the caller's best-first rank.
    """
    ids = [int(i) for i in body.ibgc_ids]
    if not ids:
        raise HttpError(400, "ibgc_ids must be non-empty")
    if len(ids) > DASHBOARD_RESULT_CAP:
        raise HttpError(400, f"ibgc_ids exceeds the {DASHBOARD_RESULT_CAP} result cap")
    token, n = _cache_ibgc_idset(ids)
    return IbgcIdSetResponse(token=token, n_ibgcs=n)


@discovery_router.get(
    "/ibgcs/roster/",
    response=PaginatedIbgcRosterResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def ibgc_roster(
    request,
    filters: Query[IbgcFilterParams],
    sort_by: str = "novelty_score",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
    ibgc_ids: str | None = None,
    ibgc_ids_token: str | None = None,
    asset_token: str | None = None,
):
    """Paginated, filterable iBGC roster (the dashboard's primary table).

    ``ibgc_ids`` / ``ibgc_ids_token`` restrict the roster to a Run Query result
    set without re-issuing the query. ``asset_token`` pre-pends the uploaded
    asset's iBGCs (negative ids) ahead of the DB rows on page 1; they bypass
    filters and always render.
    """
    parsed_ids = _parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    qs = _ibgc_queryset(filters, parsed_ids, asset_token)
    # ``sort_by=similarity`` honours the caller-supplied order of ``ibgc_ids``;
    # every other key sorts the stored columns NULLS LAST. Shared with the
    # scatter endpoint so both surfaces agree on rank.
    qs = apply_ibgc_sort(qs, sort_by, order, parsed_ids)

    asset_items = [
        _asset_row_to_roster_item(r) for r in _get_asset_roster_rows(asset_token)
    ]
    total_count = qs.count() + len(asset_items)
    pg, ps, tp, offset = _paginate(page, page_size, total_count)

    # Asset rows always sit at the very top, so they only land in the slice
    # covering global offset 0.
    asset_slice: list[IbgcRosterItem] = []
    db_offset, db_limit = offset, ps
    if offset < len(asset_items):
        asset_slice = asset_items[offset : offset + ps]
        db_limit = max(0, ps - len(asset_slice))
        db_offset = 0
    else:
        db_offset = offset - len(asset_items)

    page_qs = list(qs[db_offset : db_offset + db_limit]) if db_limit > 0 else []
    facts = _ibgc_member_facts([ibgc.id for ibgc in page_qs])
    db_items = [_ibgc_to_roster_item(ibgc, facts[ibgc.id]) for ibgc in page_qs]
    return PaginatedIbgcRosterResponse(
        items=asset_slice + db_items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


# Cap on /ibgcs/ids/ so "Add all to shortlist" can fill the 1000-iBGC
# shortlist in a single fetch without ever loading unbounded result sets.
IBGC_IDS_MAX = 1_000


@discovery_router.get("/ibgcs/ids/", response=IbgcIdsResponse)
def ibgc_ids(
    request,
    filters: Query[IbgcFilterParams],
    sort_by: str = "novelty_score",
    order: str = "desc",
    ibgc_ids: str | None = None,
    ibgc_ids_token: str | None = None,
    asset_token: str | None = None,
):
    """Bulk iBGC ids matching the same filter surface as ``/ibgcs/roster/``.

    Cheaper than the roster (no row hydration); capped at ``IBGC_IDS_MAX`` so
    callers can size buffers up front. Honours ``sort_by`` / ``order`` so the
    ordering matches the roster. ``truncated=True`` when the filter matched
    more rows than the cap.
    """
    parsed_ids = _parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    qs = apply_ibgc_sort(
        _ibgc_queryset(filters, parsed_ids, asset_token), sort_by, order, parsed_ids
    )
    # Asset iBGCs lead the roster, so they lead the id list too ("Add all"
    # mirrors what the user sees on page 1).
    asset_id_seq = [int(r["id"]) for r in _get_asset_roster_rows(asset_token)]
    total_count = qs.count() + len(asset_id_seq)
    remaining = max(0, IBGC_IDS_MAX - len(asset_id_seq))
    ids = asset_id_seq + list(qs.values_list("id", flat=True)[:remaining])
    return IbgcIdsResponse(
        ids=ids, total_count=total_count, truncated=len(ids) < total_count
    )


@discovery_router.get(
    "/ibgcs/scatter/",
    response=list[IbgcScatterPoint],
    include_in_schema=False,
    auth=first_party_gate,
)
def ibgc_scatter(
    request,
    filters: Query[IbgcFilterParams],
    x_axis: str = "novelty_score",
    y_axis: str = "domain_novelty",
    max_points: int = DASHBOARD_RESULT_CAP,
    sort_by: str = "novelty_score",
    order: str = "desc",
    ibgc_ids: str | None = None,
    ibgc_ids_token: str | None = None,
    asset_token: str | None = None,
):
    """Points for the Variables map: the roster's top ``max_points`` rows.

    ``similarity_score`` is not a stored column, so it is only a valid axis in
    a query-result context (the combined-query payload), not here.
    """
    if x_axis not in _IBGC_AXES or y_axis not in _IBGC_AXES:
        raise HttpError(400, f"axes must be one of: {', '.join(sorted(_IBGC_AXES))}")
    if x_axis == "similarity_score" or y_axis == "similarity_score":
        raise HttpError(
            400,
            "similarity_score axis requires a similarity-query context; "
            "use the query response payload instead of /ibgcs/scatter/",
        )
    max_points = min(max_points, DASHBOARD_RESULT_CAP)

    parsed_ids = _parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    points: list[IbgcScatterPoint] = []
    if not asset_only_mode(asset_token, parsed_ids, filters_active(filters)):
        qs = apply_ibgc_filters(
            IntegratedBgc.objects.all(), filters, ibgc_ids=parsed_ids
        )

        # CDS are contig-anchored in v2; an iBGC's CDS are those on its contig
        # whose range overlaps ``bgc_range`` (same membership rule as the region
        # view). There is no per-prediction ``cds_list`` relation to count.
        n_cds_subq = (
            ContigCds.objects.filter(
                contig_id=OuterRef("contig_id"),
                cds_range__overlap=OuterRef("bgc_range"),
            )
            .order_by()
            .values("contig_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        # NB: annotate the span under ``_size_kb`` — ``size_kb`` is a read-only
        # property on ``IntegratedBgc``, so an annotation of that name explodes
        # with "property 'size_kb' has no setter" when the rows materialise.
        qs = qs.annotate(
            _size_kb=ExpressionWrapper(
                ibgc_span_bp() / 1000.0, output_field=FloatField()
            ),
            n_cds=Subquery(n_cds_subq[:1]),
        )

        # Sample the roster's top ``max_points`` (same sort) so the Variables
        # map plots exactly the iBGCs the roster surfaces first — the chosen
        # x/y axes only affect where those points land, not which are shown.
        qs = apply_ibgc_sort(qs, sort_by, order, parsed_ids)
        ibgc_list = list(qs[:max_points])
        facts = _ibgc_member_facts([n.id for n in ibgc_list])

        # ``size_kb`` lives on the ``_size_kb`` annotation (the model property of
        # that name is read-only and can't carry the annotated value).
        def _axis_val(obj, axis):
            return getattr(obj, "_size_kb" if axis == "size_kb" else axis, None)

        for ibgc in ibgc_list:
            x_val = _axis_val(ibgc, x_axis)
            y_val = _axis_val(ibgc, y_axis)
            if x_val is None or y_val is None:
                continue
            points.append(
                IbgcScatterPoint(
                    id=ibgc.id,
                    x=float(x_val),
                    y=float(y_val),
                    classification_path=ibgc.gene_cluster_family or "",
                    bgc_class=ibgc.bgc_class or "",
                    novelty_score=ibgc.novelty_score,
                    domain_novelty=ibgc.domain_novelty,
                    is_partial=_ibgc_is_partial(ibgc),
                    is_validated=facts[ibgc.id]["is_validated"],
                    is_type_strain=facts[ibgc.id]["is_type_strain"],
                )
            )
    asset_points: list[IbgcScatterPoint] = []
    for row in _get_asset_roster_rows(asset_token):
        pt = _asset_row_to_scatter_point(row, x_axis, y_axis)
        if pt is not None:
            asset_points.append(pt)
    return asset_points + points


# NOTE: this catch-all path-param route MUST come after every other
# `/ibgcs/<literal>/` route above (roster, scatter, …) — Django Ninja
# matches in declaration order, so an earlier `{ibgc_id}` would swallow
# "scatter" and 422 on int parsing.
def _asset_token_header(request) -> str | None:
    """Frontend passes the active asset token via ``X-Asset-Token`` so the
    negative-id dispatcher can resolve asset iBGCs out of Redis without
    polluting the URL with a query param."""
    return request.headers.get("X-Asset-Token") or request.GET.get("asset_token")


@discovery_router.get("/ibgcs/{ibgc_id}/", response=IbgcDetail)
def ibgc_detail(request, ibgc_id: int):
    if ibgc_id < 0:
        token = _asset_token_header(request)
        if not token:
            raise HttpError(404, "Asset token required for asset iBGC")
        from discovery.services.asset_upload import cache as asset_cache

        payload = asset_cache.read_ibgc_detail(token, ibgc_id)
        if payload is None:
            raise HttpError(404, "Asset iBGC not found or expired")
        return IbgcDetail(**payload)

    try:
        ibgc = IntegratedBgc.objects.select_related("contig", "cbgc").get(id=ibgc_id)
    except IntegratedBgc.DoesNotExist:
        raise HttpError(404, "iBGC not found") from None

    member_qs = (
        SourceBgcPrediction.objects.filter(integrated_bgc_id=ibgc_id)
        .select_related("assembly", "assembly__source", "detector")
        .order_by("id")
    )
    members = list(member_qs)
    is_validated = any(m.is_validated for m in members)
    is_type_strain = any(
        m.assembly is not None and m.assembly.is_type_strain for m in members
    )

    parent = None
    if members:
        asm = members[0].assembly
        if asm:
            parent = ParentAssemblySummary(
                assembly_id=asm.id,
                accession=asm.assembly_accession,
                organism_name=asm.organism_name,
                source_name=asm.source.name if asm.source else None,
                is_type_strain=asm.is_type_strain,
                url=asm.url or "",
            )

    # Pooled positional domain architecture over all CDS overlapping the
    # iBGC's range (range-overlap membership — the same rule the clustering
    # pipeline scored). ``ibgc_architecture`` takes the single iBGC id.
    domain_arch = [
        DomainArchitectureItem(
            domain_acc=r["domain_acc"],
            domain_name=r["domain_name"],
            ref_db=r["ref_db"],
            start=0,
            end=0,
            score=None,
            url=r["url"] or "",
        )
        for r in ibgc_architecture(ibgc_id)
    ]

    member_items = [
        IbgcMemberBgc(
            id=m.id,
            accession=m.prediction_accession,
            detector_name=m.detector.tool if m.detector else None,
            detector_version=m.detector.version if m.detector else None,
            is_partial=m.is_partial,
            is_validated=m.is_validated,
            size_kb=m.size_kb,
            score=m.score,
            probability=m.probability,
            classification_path=m.classification_path,
        )
        for m in members
    ]

    npc_items = [
        NpcLabelOut(
            term_id=lab.term_id,
            level=lab.term.level,
            name=lab.term.name,
            score=lab.score,
            confident=lab.confident,
            sources=list(lab.sources or []),
            detector_tools=list(lab.detector_tools or []),
        )
        for lab in IbgcNpcLabel.objects.filter(ibgc_id=ibgc_id)
        .select_related("term")
        .order_by("term__level", "-confident", "-score", "term__name")
    ]

    return IbgcDetail(
        id=ibgc.id,
        accession=ibgc.accession or "",
        cbgc_accession=ibgc.cbgc.accession if ibgc.cbgc_id else None,
        label=_ibgc_label(ibgc.id),
        classification_path=ibgc.gene_cluster_family or "",
        bgc_class=ibgc.bgc_class or "",
        size_kb=round((ibgc.end_position - ibgc.start_position) / 1000.0, 3),
        start_position=ibgc.start_position,
        end_position=ibgc.end_position,
        contig_accession=ibgc.contig.accession if ibgc.contig else None,
        source_tools=list(ibgc.source_tools or []),
        novelty_score=ibgc.novelty_score,
        domain_novelty=ibgc.domain_novelty,
        is_partial=_ibgc_is_partial(ibgc),
        is_validated=is_validated,
        is_type_strain=is_type_strain,
        parent_assembly=parent,
        region_endpoint_url=f"/api/discovery/ibgcs/{ibgc.id}/region/",
        member_bgcs=member_items,
        domain_architecture=domain_arch,
        npc_labels=npc_items,
    )


@discovery_router.get(
    "/ibgcs/{ibgc_id}/architecture/",
    response=IbgcArchitectureResponse,
)
def ibgc_architecture_endpoint(request, ibgc_id: int):
    """Pooled positional domain accessions for an iBGC (clipboard payload).

    Lightweight wrapper around the same ordering rule that ``ibgc_detail``
    uses for ``domain_architecture``.
    """
    if ibgc_id < 0:
        token = _asset_token_header(request)
        if not token:
            raise HttpError(404, "Asset token required for asset iBGC")
        from discovery.services.asset_upload import cache as asset_cache

        ordered_accs = asset_cache.read_architecture(token, ibgc_id)
        if ordered_accs is None:
            raise HttpError(404, "Asset iBGC not found or expired")
        return IbgcArchitectureResponse(
            id=ibgc_id,
            label=f"iBGC-A{abs(ibgc_id)}",
            ordered_accs=ordered_accs,
        )

    try:
        ibgc = IntegratedBgc.objects.get(id=ibgc_id)
    except IntegratedBgc.DoesNotExist:
        raise HttpError(404, "iBGC not found") from None

    # ``ibgc_architecture`` takes the single iBGC id and pools the architecture
    # across the CDS overlapping its range (same rule the detail view uses) —
    # not a list of member-prediction ids.
    ordered_accs = [r["domain_acc"] for r in ibgc_architecture(ibgc_id)]
    return IbgcArchitectureResponse(
        id=ibgc.id,
        label=_ibgc_label(ibgc.id),
        ordered_accs=ordered_accs,
    )


@discovery_router.post(
    "/query/similar-ibgc/",
    response=PaginatedIbgcRosterResponse,
    include_in_schema=False,
    auth=first_party_gate,
    throttle=search_throttle,
)
def similar_ibgc_query(
    request,
    body: SimilarIbgcRequest,
    page: int = 1,
    page_size: int = 25,
):
    """Top-K iBGCs by composite similarity to ``body.ibgc_id``.

    The composite (the run's similarity metric: IDF × enrichment weighted
    cosine, or Dice on older runs) is computed on demand against the per-iBGC
    signature matrices of the active ClusteringRun. The full N×N similarity matrix
    is no longer materialised; the result is cached in Redis for 24h keyed
    on the run's sha256 so a new clustering run invalidates the cache by
    orphaning the previous keys.

    Delegates scoring to ``discovery.services.query.similar_top`` — the
    canonical resolver shared with the combined query engine.
    """
    from discovery.services.query import (
        CriterionError,
        build_params,
        similar_top,
    )

    try:
        top_ids, top_sims = similar_top(build_params("similar", body))
    except CriterionError as exc:
        raise HttpError(exc.status, exc.message) from exc
    sim_lookup = dict(zip(top_ids, top_sims))

    if not top_ids:
        return PaginatedIbgcRosterResponse(
            items=[],
            pagination=PaginationMeta(
                page=1, page_size=page_size, total_count=0, total_pages=0
            ),
        )

    total_count = len(top_ids)
    pg, ps, tp, offset = _paginate(page, page_size, total_count)
    page_ids = top_ids[offset : offset + ps]

    ibgcs = {n.id: n for n in IntegratedBgc.objects.filter(id__in=page_ids)}
    facts = _ibgc_member_facts(page_ids)
    items = [
        _ibgc_to_roster_item(
            ibgcs[nid],
            facts[nid],
            similarity_score=round(sim_lookup[nid], 4),
        )
        for nid in page_ids
        if nid in ibgcs
    ]
    return PaginatedIbgcRosterResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg,
            page_size=ps,
            total_count=total_count,
            total_pages=tp,
        ),
    )


# ── Shortlist Report endpoints ───────────────────────────────────────────────


@discovery_router.post(
    "/report/snapshot/",
    response=ReportSnapshotResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def report_snapshot(request, body: ReportSnapshotRequest):
    """Materialise a shortlist Report payload and cache it in Redis by token.

    The token is ``sha256(sorted comma-joined ids)[:32]`` so the same shortlist
    always resolves to the same token (cheap re-render across browsers/sessions).
    """
    import hashlib

    from django.core.cache import cache

    from discovery.services.report import (
        MAX_SHORTLIST,
        REPORT_TTL_SECONDS,
        build_report_payload,
    )

    ids = sorted({int(i) for i in body.ibgc_ids})
    if not ids:
        raise HttpError(400, "ibgc_ids must be non-empty")
    if len(ids) > MAX_SHORTLIST:
        raise HttpError(400, f"shortlist limit is {MAX_SHORTLIST} iBGCs")

    # Split positive (DB) from negative (asset) ids and hydrate the asset
    # rows from Redis if a token was supplied.
    asset_ids = [i for i in ids if i < 0]
    extra_rows: list[dict] = []
    extra_domain_rows: list[dict] = []
    if asset_ids:
        if not body.asset_token:
            raise HttpError(
                400,
                "asset_token is required when asset iBGC ids (negative) are shortlisted",
            )
        from discovery.services.asset_upload import cache as asset_cache

        cached_roster = {
            int(r["id"]): r
            for r in (asset_cache.read_ibgc_list(body.asset_token) or [])
        }
        for nid in asset_ids:
            row = cached_roster.get(nid)
            if row is None:
                raise HttpError(
                    404,
                    f"Asset iBGC {nid} not found in asset token {body.asset_token!r}",
                )
            extra_rows.append(row)

        # Domain hits feed the report's domain composition + GO slim matrix
        # panels for the asset rows. Scope to the shortlisted asset ids so
        # an upload with many iBGCs doesn't drag the rest into the rollup.
        shortlisted = set(asset_ids)
        extra_domain_rows = [
            r
            for r in (asset_cache.read_domain_hits(body.asset_token) or [])
            if int(r.get("ibgc_id", 0)) in shortlisted
        ]

    # The token covers both ids and asset rows so cached snapshots don't
    # collide across different asset uploads with the same negative ids.
    token_seed = ",".join(str(i) for i in ids)
    if body.asset_token:
        token_seed += f"|asset={body.asset_token}"
    token = hashlib.sha256(token_seed.encode("utf-8")).hexdigest()[:32]
    cache_key = f"report:{token}"

    cached = cache.get(cache_key)
    if cached:
        return ReportSnapshotResponse(
            token=token,
            expires_at=cached.get("expires_at", ""),
            n_ibgcs=cached.get("n_ibgcs", len(ids)),
        )

    payload = build_report_payload(
        ids,
        extra_ibgc_rows=extra_rows,
        extra_domain_rows=extra_domain_rows,
    )
    cache.set(cache_key, payload, REPORT_TTL_SECONDS)
    return ReportSnapshotResponse(
        token=token,
        expires_at=payload["expires_at"],
        n_ibgcs=payload["n_ibgcs"],
    )


@discovery_router.get(
    "/report/{token}/",
    response=ReportPayload,
    include_in_schema=False,
    auth=first_party_gate,
)
def report_get(request, token: str):
    """Return the cached Report payload for ``token``; 404 if expired."""
    from django.core.cache import cache

    cached = cache.get(f"report:{token}")
    if not cached:
        raise HttpError(
            404,
            "Report not found or expired — POST /report/snapshot/ to regenerate.",
        )
    return ReportPayload(token=token, **cached)


def _get_cached_report(token: str) -> dict:
    from django.core.cache import cache

    cached = cache.get(f"report:{token}")
    if not cached:
        raise HttpError(
            404,
            "Report not found or expired — POST /report/snapshot/ to regenerate.",
        )
    return cached


@discovery_router.get(
    "/report/{token}/export.ibgcs.tsv",
    include_in_schema=False,
    auth=first_party_gate,
)
def report_export_ibgcs_tsv(request, token: str):
    """Download the report's iBGC results as a TSV (one row per iBGC).

    Columns mirror the per-iBGC block of the analyst JSON. Reads from the
    cached snapshot — no extra DB queries within the 24h TTL.
    """
    from discovery.services.export import build_report_ibgc_tsv

    cached = _get_cached_report(token)
    tsv = build_report_ibgc_tsv(cached.get("ibgc_rows", []))
    response = HttpResponse(tsv, content_type="text/tab-separated-values")
    response["Content-Disposition"] = f'attachment; filename="report_{token}_ibgcs.tsv"'
    return response


@discovery_router.get(
    "/report/{token}/export.json",
    include_in_schema=False,
    auth=first_party_gate,
)
def report_export_json(request, token: str):
    """Download the report as an analyst-friendly tidy JSON.

    Reshapes the cached chart-oriented payload into a two-layer
    ``{metadata, ...tables}`` structure. Pure reshape (no DB).
    """
    from discovery.services.report import build_report_analyst_export

    cached = _get_cached_report(token)
    body = build_report_analyst_export(token, cached)
    response = HttpResponse(
        json.dumps(body, default=str),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="report_{token}.json"'
    return response


@discovery_router.get(
    "/report/{token}/export.gbk.zip",
    include_in_schema=False,
    auth=first_party_gate,
)
def report_export_gbk_zip(request, token: str):
    """Download a zip of GBK files (one per source BGC) for the shortlist.

    Each record carries BGC / iBGC / Region features in addition to CDSs.
    Files are grouped as ``iBGC-{id}/{bgc_accession}.gbk``.
    """
    from discovery.services.gbk import build_shortlist_gbk_zip

    cached = _get_cached_report(token)
    ibgc_ids = [row["id"] for row in cached.get("ibgc_rows", [])]
    zip_bytes = build_shortlist_gbk_zip(ibgc_ids)
    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="report_{token}_gbk.zip"'
    return response


# ── Query mode endpoints ─────────────────────────────────────────────────────


# ── iBGC-collapsed query endpoints ────────────────────────────────────────────


# ── Combined multi-criterion query ─────────────────────────────────────────
#
# One async query carrying several scoring criteria (e.g. domain-AND +
# domain-ARCH + sequence). The worker resolves each criterion, AND-intersects
# their iBGC id sets, applies the narrowing filters, and caches a result the
# status/scores endpoints render — each criterion keeps its own sortable
# column(s) in the roster and its own axis in the Variables map.

# Roster/map sort keys that map to an IntegratedBgc column (alongside the
# per-criterion ``score:<id>[:metric]`` keys, resolved from the cached scores).
_COMBINED_DB_SORT = {
    "id": "id",
    "novelty_score": "novelty_score",
    "domain_novelty": "domain_novelty",
    "classification_path": "gene_cluster_family",
    "bgc_class": "bgc_class",
}

_MAX_COMBINED_CRITERIA = 12


def _clean_protein_sequence(sequence: str) -> str:
    """Strip FASTA headers/whitespace from a pasted protein sequence."""
    lines = (sequence or "").strip().splitlines()
    return "".join(line.strip() for line in lines if not line.startswith(">"))


def _validate_criterion_params(ctype: str, params) -> dict:
    """Per-type synchronous validation; returns the (possibly normalised) params dict.

    Mirrors the checks the single-criterion POST handlers do so obvious user
    errors fail fast with 400 instead of a failed background task. The sequence
    criterion's FASTA input is cleaned here so the worker receives bare residues.
    """
    if ctype == "domain":
        if not (params.domains_text or "").strip():
            raise HttpError(400, "domain criterion requires domains_text")
        if not (0.0 <= params.threshold <= 1.0):
            raise HttpError(400, "domain threshold must be between 0 and 1")
    elif ctype == "architecture":
        if not params.architecture:
            raise HttpError(
                400, "architecture criterion requires at least one accession"
            )
    elif ctype == "sequence":
        cleaned = _clean_protein_sequence(params.sequence)
        if not cleaned:
            raise HttpError(400, "sequence criterion requires a protein sequence")
        if len(cleaned) > 5000:
            raise HttpError(400, "Sequence exceeds maximum length of 5,000 amino acids")
        if not (0.0 <= params.min_bitscore <= 10_000.0):
            raise HttpError(400, "min_bitscore must be between 0 and 10000")
        if not (0.0 <= params.min_pident <= 100.0):
            raise HttpError(400, "min_pident must be between 0 and 100")
        if not (0.0 <= params.min_qcov <= 100.0):
            raise HttpError(400, "min_qcov must be between 0 and 100")
        return {
            "sequence": cleaned,
            "min_bitscore": params.min_bitscore,
            "min_pident": params.min_pident,
            "min_qcov": params.min_qcov,
        }
    elif ctype == "similar" and not params.ibgc_id:
        raise HttpError(400, "similar criterion requires an ibgc_id")
    return None


def _normalise_combined_criteria(criteria) -> list[dict]:
    """Validate + normalise combined criteria into the dicts the task consumes.

    Enforces unique non-empty ids and a sane criterion count, builds each typed
    params (catching unknown types), and runs per-type validation. Returns a
    list of ``{"id", "type", "params"}`` dicts ready to enqueue.
    """
    from discovery.services.query import CriterionError, build_params

    if not criteria:
        raise HttpError(400, "At least one criterion is required")
    if len(criteria) > _MAX_COMBINED_CRITERIA:
        raise HttpError(400, f"Too many criteria (max {_MAX_COMBINED_CRITERIA})")

    seen: set[str] = set()
    out: list[dict] = []
    for c in criteria:
        cid = (c.id or "").strip()
        if not cid:
            raise HttpError(400, "Each criterion needs a non-empty id")
        if cid in seen:
            raise HttpError(400, f"Duplicate criterion id: {cid!r}")
        seen.add(cid)
        raw_params = c.params or {}
        try:
            params = build_params(c.type, raw_params)
        except CriterionError as exc:
            raise HttpError(exc.status, exc.message) from exc
        normalised = _validate_criterion_params(c.type, params)
        out.append({"id": cid, "type": c.type, "params": normalised or raw_params})
    return out


def _load_combined_result(task_id: str) -> dict:
    """Poll the combined-query task; raise 503 (pending) / 500 (failed)."""
    from discovery.cache_utils import fetch_job

    res = fetch_job(task_id)
    if res.failed():
        logger.error("Combined query task %s failed: %s", task_id, res.errors)
        raise HttpError(500, "Combined query failed")
    if not res.ready():
        raise HttpError(503, "Combined query still running")
    return res.result or {}


def _criterion_columns(result: dict) -> list[CriterionColumn]:
    return [
        CriterionColumn(
            id=c["id"],
            type=c["type"],
            label=c["label"],
            metrics=[CriterionMetricSchema(**m) for m in c.get("metrics", [])],
        )
        for c in result.get("criteria", [])
    ]


def _combined_scores_map(scores_by_id: dict, ibgc_id: int) -> dict[str, CriterionScore]:
    raw = scores_by_id.get(str(ibgc_id), {})
    return {
        cid: CriterionScore(
            value=p.get("value"),
            pident=p.get("pident"),
            qcoverage=p.get("qcoverage"),
            best_hit_protein_id=p.get("best_hit_protein_id"),
        )
        for cid, p in raw.items()
    }


def _combined_sorted_ids(
    ordered_ids: list[int],
    scores_by_id: dict,
    ibgcs: dict,
    *,
    sort_by: str,
    order: str,
    primary_cid: str | None,
) -> list[int]:
    """Sort the result ids by a ``score:<id>[:metric]`` key or an iBGC column.

    Nulls always sort last (matching the DB roster's ``nulls_last``). An empty
    ``sort_by`` defaults to the primary criterion's value; an unknown key keeps
    the task's primary-best-first order.
    """
    reverse = order != "asc"
    if not sort_by:
        sort_by = f"score:{primary_cid}" if primary_cid else "id"

    if sort_by.startswith("score:"):
        _, _, rest = sort_by.partition(":")
        cid, _, metric = rest.partition(":")
        metric = metric or "value"

        def valuefn(i):
            return scores_by_id.get(str(i), {}).get(cid, {}).get(metric)

    elif sort_by == "size_kb":

        def valuefn(i):
            n = ibgcs.get(i)
            return (n.end_position - n.start_position) if n else None

    elif sort_by in _COMBINED_DB_SORT:
        col = _COMBINED_DB_SORT[sort_by]

        def valuefn(i):
            n = ibgcs.get(i)
            return getattr(n, col, None) if n else None

    else:
        return ordered_ids

    present = [i for i in ordered_ids if valuefn(i) is not None]
    missing = [i for i in ordered_ids if valuefn(i) is None]
    present.sort(key=valuefn, reverse=reverse)
    return present + missing


@discovery_router.post(
    "/query/combined/",
    response={202: CombinedQueryAccepted},
    tags=["Query"],
    auth=first_party_gate,
    throttle=search_throttle,
)
def combined_query_endpoint(request, body: CombinedQueryRequest):
    """Dispatch a combined multi-criterion query.

    Accepts a list of scoring ``criteria`` (each with a stable per-instance
    ``id``) plus the standard narrowing ``filters``. The criteria are
    AND-intersected server-side; slow sub-searches (sequence) make this
    always-async. Returns ``202`` with a ``task_id``; poll
    ``GET /query/combined/status/{task_id}/`` (roster) and ``…/scores/``
    (Variables map).
    """
    criteria = _normalise_combined_criteria(body.criteria)
    filters = dict(body.filters) if body.filters else {}

    from discovery.tasks import combined_query

    try:
        result = combined_query.enqueue(criteria, filters)
    except Exception as e:
        logger.error("Failed to dispatch combined query task: %s", e)
        raise HttpError(503, "Search service temporarily unavailable") from e

    return 202, CombinedQueryAccepted(task_id=result.id)


@discovery_router.get(
    "/query/combined/status/{task_id}/",
    response=CombinedRosterResponse,
    tags=["Query"],
    auth=first_party_gate,
)
def combined_query_status(
    request,
    task_id: str,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "",
    order: str = "desc",
):
    """Poll a combined query and return a paginated roster with per-criterion columns.

    ``sort_by`` accepts ``score:<criterion_id>`` / ``score:<criterion_id>:<metric>``
    (e.g. a sequence criterion's ``pident``) or an iBGC column (``novelty_score``,
    ``size_kb``, ``bgc_class``, …). Empty sorts by the primary criterion.
    PENDING raises 503 so the client can poll; FAILURE raises 500.
    """
    result = _load_combined_result(task_id)
    columns = _criterion_columns(result)
    ordered_ids = [int(i) for i in result.get("ordered_ids", [])]
    scores_by_id = result.get("scores_by_id", {})
    primary_cid = result["criteria"][0]["id"] if result.get("criteria") else None

    if not ordered_ids:
        return CombinedRosterResponse(
            items=[],
            pagination=PaginationMeta(
                page=1, page_size=page_size, total_count=0, total_pages=0
            ),
            criteria=columns,
        )

    ibgcs = {n.id: n for n in IntegratedBgc.objects.filter(id__in=ordered_ids)}
    sorted_ids = _combined_sorted_ids(
        ordered_ids,
        scores_by_id,
        ibgcs,
        sort_by=sort_by,
        order=order,
        primary_cid=primary_cid,
    )
    total_count = len(sorted_ids)
    pg, ps, tp, offset = _paginate(page, page_size, total_count)
    page_ids = sorted_ids[offset : offset + ps]
    facts = _ibgc_member_facts(page_ids)

    items = []
    for nid in page_ids:
        n = ibgcs.get(nid)
        if n is None:
            continue
        base = _ibgc_to_roster_item(
            n,
            facts[nid],
        )
        items.append(
            CombinedRosterItem(
                **dict(base), scores=_combined_scores_map(scores_by_id, nid)
            )
        )
    return CombinedRosterResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
        criteria=columns,
    )


@discovery_router.get(
    "/query/combined/status/{task_id}/scores/",
    response=CombinedScoresResponse,
    tags=["Query"],
    auth=first_party_gate,
)
def combined_query_scores(request, task_id: str):
    """Compact, full (capped) combined-query payload for the Variables map.

    Returns every result id with its per-criterion scores, the criteria column
    descriptors, and an ``ibgc_ids_token`` scoping the result set for the
    scatter / count / roster GET endpoints. PENDING raises 503; FAILURE 500.
    """
    result = _load_combined_result(task_id)
    columns = _criterion_columns(result)
    ordered_ids = [int(i) for i in result.get("ordered_ids", [])]
    scores_by_id = result.get("scores_by_id", {})
    token, _ = _cache_ibgc_idset(ordered_ids)
    items = [
        CombinedScoreRow(id=i, scores=_combined_scores_map(scores_by_id, i))
        for i in ordered_ids
    ]
    return CombinedScoresResponse(
        items=items,
        criteria=columns,
        total_matched=result.get("total_matched", len(ordered_ids)),
        capped=result.get("capped", False),
        cap=result.get("cap", DASHBOARD_RESULT_CAP),
        ibgc_ids_token=token,
        warnings=result.get("warnings", []),
    )


# ── Filter endpoints ─────────────────────────────────────────────────────────


@discovery_router.get(
    "/filters/taxonomy/",
    response=list[TaxonomyNode],
    include_in_schema=False,
    auth=first_party_gate,
)
def taxonomy_tree(request):
    from discovery.models import DashboardContig
    from discovery.services.taxonomy import ranked_labels, ranked_labels_by_taxon

    rows = list(
        DashboardContig.objects.exclude(taxonomy_path="")
        .values_list("taxonomy_path", "taxon_id")
        .annotate(n=Count("id"))
        .order_by()
    )
    lookup = ranked_labels_by_taxon(r[1] for r in rows)

    tree: dict = {}
    for path, taxon_id, n in rows:
        node = tree
        prefix: list[str] = []
        for rank, label in ranked_labels(path, taxon_id, lookup):
            prefix.append(label)
            if label not in node:
                node[label] = {
                    "_rank": rank,
                    "_path": ".".join(prefix),
                    "_count": 0,
                    "_children": {},
                }
            node[label]["_count"] += n
            node = node[label]["_children"]

    def _build_nodes(level: dict) -> list[TaxonomyNode]:
        return [
            TaxonomyNode(
                name=name,
                rank=data["_rank"],
                path=data["_path"],
                count=data["_count"],
                children=_build_nodes(data["_children"]),
            )
            for name, data in sorted(level.items())
        ]

    return _build_nodes(tree)


@discovery_router.get(
    "/filters/bgc-classes/",
    response=list[BgcClassOption],
    include_in_schema=False,
    auth=first_party_gate,
)
def bgc_classes(request):
    return [
        BgcClassOption(name=row.name, count=row.bgc_count)
        for row in DashboardBgcClass.objects.filter(bgc_count__gt=0).order_by(
            "-bgc_count"
        )
    ]


@discovery_router.get(
    "/filters/npc-tree/",
    response=list[NpcTreeNode],
    include_in_schema=False,
    auth=first_party_gate,
)
def npc_tree_endpoint(request):
    """NPClassifier ontology (pathway → superclass → class) with iBGC counts.

    ``count`` / ``confident_count`` are iBGCs carrying that exact term; the
    ``npc_terms`` filter also matches descendants of a selected term. Served
    from a short cache: the ontology is fixed and counts change only on load.
    """
    from django.core.cache import cache

    key = "discovery:npc-tree:v1"
    tree = cache.get(key)
    if tree is None:
        tree = npc_tree()
        cache.set(key, tree, 300)
    return tree


@discovery_router.get(
    "/filters/gcfs/",
    response=PaginatedGcfResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def gcf_list(
    request,
    search: str | None = None,
    level: int | None = None,
    page: int = 1,
    page_size: int = 50,
):
    # Scope to the latest ClusteringRun — IntegratedBgc.gene_cluster_family is
    # rewritten on every successful run, so this is the only set whose paths
    # match the live iBGC rows that ``leaf_path_prefix`` filters against.
    run = ClusteringRun.objects.order_by("-created_at").first()
    if run is None:
        return PaginatedGcfResponse(
            items=[],
            pagination=PaginationMeta(
                page=1, page_size=page_size, total_count=0, total_pages=0
            ),
        )

    from django.db.models.expressions import RawSQL

    qs = DashboardGCF.objects.filter(clustering_run=run, member_count__gt=0)
    if search:
        qs = qs.filter(family_path__icontains=search)
    if level is not None:
        qs = qs.filter(level=level)

    total_count = qs.count()
    pg, ps, tp, offset = _paginate(page, page_size, total_count)

    # Paths are unpadded (e.g. "42.7.3"), so a plain string sort would order
    # "10" before "2". Cast the dot-path to an int[] for hierarchical numeric
    # ordering as the final tiebreaker.
    qs = qs.annotate(_path_key=RawSQL("string_to_array(family_path, '.')::int[]", []))
    items = [
        GcfOption(
            family_path=g.family_path,
            level=g.level,
            member_count=g.member_count,
            validated_count=g.validated_count,
            mean_novelty=g.mean_novelty,
        )
        for g in qs.order_by("-member_count", "level", "_path_key")[
            offset : offset + ps
        ]
    ]

    return PaginatedGcfResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


@discovery_router.get(
    "/filters/sources/",
    response=PaginatedSourceResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def source_list(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    qs = AssemblySource.objects.filter(assemblies__isnull=False).annotate(
        assembly_count=Count("assemblies", distinct=True)
    )
    if search:
        qs = qs.filter(name__icontains=search)
    total_count = qs.count()
    pg, ps, tp, offset = _paginate(page, page_size, total_count)
    items = [
        SourceOption(name=s.name, count=s.assembly_count)
        for s in qs.order_by("-assembly_count")[offset : offset + ps]
    ]
    return PaginatedSourceResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


@discovery_router.get(
    "/filters/detectors/",
    response=PaginatedDetectorResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def detector_list(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    qs = (
        DashboardDetector.objects.values("tool")
        .annotate(count=Count("source_bgcs"))
        .filter(count__gt=0)
    )
    if search:
        qs = qs.filter(tool__icontains=search)
    total_count = qs.count()
    pg, ps, tp, offset = _paginate(page, page_size, total_count)
    items = [
        DetectorOption(tool=d["tool"], count=d["count"])
        for d in qs.order_by("-count")[offset : offset + ps]
    ]
    return PaginatedDetectorResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


# ── Stats endpoints ──────────────────────────────────────────────────────────


# ── Export endpoints ─────────────────────────────────────────────────────────


# Assessment endpoints removed in v2 — the Evaluate Asset feature is
# superseded by the Shortlist Report flow (see /report/snapshot/).


# ── Platform overview ─────────────────────────────────────────────────────────


@discovery_router.get(
    "/stats/",
    response=DiscoveryStatsResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def discovery_stats(request):
    """Latest Discovery Platform overview counts for the Run Query card."""
    latest = DiscoveryStats.objects.order_by("-created_at").first()
    if latest is None:
        return DiscoveryStatsResponse()
    known = {
        k: v
        for k, v in latest.stats.items()
        if k in DiscoveryStatsResponse.model_fields
    }
    return DiscoveryStatsResponse(**known, updated_at=latest.updated_at)


# ── Ephemeral asset upload ───────────────────────────────────────────────────


# Compressed (.tar.gz) upload cap. The decompressed cap lives in
# ``asset_upload/schemas.py:MAX_TARBALL_BYTES``; this one bounds the bytes we
# accept on the wire so a hostile client can't OOM us before validation.
_ASSET_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@discovery_router.post(
    "/assets/upload/",
    response={202: AssetUploadAccepted},
    include_in_schema=False,
    auth=first_party_gate,
    throttle=upload_throttle,
)
def asset_upload(request):
    """Upload an ephemeral tarball of BGC TSVs (``Ga…_assembly_upload.tar.gz``).

    Returns ``202`` with ``{token, task_id}``; the projection runs in a
    Celery worker and the result is cached in Redis under ``asset:{token}:*``
    for 6 hours. Poll ``GET /assets/{token}/status/`` for progress.

    The request body is ``multipart/form-data`` with a single ``file`` field.
    """
    import hashlib

    from discovery.services.asset_upload import cache as asset_cache
    from discovery.tasks import process_asset_upload_task

    upload = request.FILES.get("file")
    if upload is None:
        raise HttpError(400, "Missing 'file' field in multipart upload")

    if upload.size and upload.size > _ASSET_MAX_UPLOAD_BYTES:
        raise HttpError(413, "Upload exceeds 5 MB cap")

    raw = upload.read(_ASSET_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _ASSET_MAX_UPLOAD_BYTES:
        raise HttpError(413, "Upload exceeds 5 MB cap")

    if not raw.startswith(b"\x1f\x8b"):
        raise HttpError(400, "Upload must be a gzip-compressed tarball")

    token = hashlib.sha256(raw).hexdigest()[:24]

    # Stage the bytes on the shared PVC so the worker (separate pod, separate
    # /tmp) can read them by token.
    asset_cache.stash_upload(token, raw)

    # Mark pending up front so concurrent status polls don't return UNKNOWN
    # in the gap between dispatch and the worker writing RUNNING.
    asset_cache.mark_pending(token, task_id="")
    async_result = process_asset_upload_task.enqueue(token)
    # If the cache still says PENDING, fold the actual task_id in. The worker
    # may have already written RUNNING / SUCCESS by now — leave that alone.
    status_payload = asset_cache.read_status(token)
    if status_payload and status_payload.get("state") == "PENDING":
        asset_cache.mark_pending(token, task_id=async_result.id)

    return 202, AssetUploadAccepted(token=token, task_id=async_result.id)


@discovery_router.get(
    "/assets/{token}/status/",
    response=AssetStatusResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def asset_status(request, token: str):
    """Return the current state of the asset projection.

    ``state`` is one of ``PENDING``, ``RUNNING``, ``SUCCESS``, ``FAILED``,
    ``UNKNOWN`` (when the token has expired or never existed).
    """
    from discovery.services.asset_upload import cache as asset_cache

    payload = asset_cache.read_status(token)
    if payload is None:
        return AssetStatusResponse(state="UNKNOWN")
    return AssetStatusResponse(**payload)


@discovery_router.delete(
    "/assets/{token}/",
    response={204: None},
    include_in_schema=False,
    auth=first_party_gate,
)
def asset_evict(request, token: str):
    """Drop every Redis key tied to this asset token (user X-click on chip)."""
    from discovery.services.asset_upload import cache as asset_cache

    asset_cache.evict_asset(token)
    return 204, None


# ── iBGC region (merged CDS view) ──────────────────────────────────────────────


@discovery_router.get("/ibgcs/{ibgc_id}/region/", response=IbgcRegionOut)
def ibgc_region(request, ibgc_id: int):
    """Merged region payload for an iBGC.

    Pools every ``ContigCds`` whose ``cds_range`` overlaps the iBGC's
    ``bgc_range`` on the same contig. Each CDS carries ``claimed_by_tools``
    — the sorted unique tool codes whose ``SourceBgcPrediction`` range
    covers it within this iBGC. Coordinates are relative to the iBGC
    interval (``window_start=0``).
    """
    from discovery.models import IntegratedBgc

    if ibgc_id < 0:
        token = _asset_token_header(request)
        if not token:
            raise HttpError(404, "Asset token required for asset iBGC")
        from discovery.services.asset_upload import cache as asset_cache

        payload = asset_cache.read_region(token, ibgc_id)
        if payload is None:
            raise HttpError(404, "Asset iBGC not found or expired")
        # The cached payload carries only the region fields; the iBGC identity
        # fields aren't read by the region plot, so synthesise a label.
        return IbgcRegionOut(
            ibgc_id=ibgc_id,
            ibgc_accession=f"iBGC-A{abs(ibgc_id)}",
            cbgc_accession="",
            contig_accession=None,
            **payload,
        )

    try:
        ibgc = IntegratedBgc.objects.select_related("contig", "cbgc").get(id=ibgc_id)
    except IntegratedBgc.DoesNotExist:
        raise HttpError(404, f"iBGC {ibgc_id} not found") from None

    bgc_range = ibgc.bgc_range
    window_start = bgc_range.lower
    window_end = bgc_range.upper
    region_length = window_end - window_start

    predictions = list(
        SourceBgcPrediction.objects.filter(integrated_bgc_id=ibgc.id).select_related(
            "detector"
        )
    )

    # CDS overlapping the iBGC range, on the same contig.
    cds_rows = list(
        ContigCds.objects.filter(
            contig_id=ibgc.contig_id,
            cds_range__overlap=bgc_range,
        )
        .select_related("seq")
        .order_by("cds_range")
    )
    cds_ids = [c.id for c in cds_rows]

    # Domains per CDS (with InterPro projection done client-side via collapse).
    domains_by_cds: dict[int, list] = {}
    if cds_ids:
        for d in ContigDomain.objects.filter(cds_id__in=cds_ids).order_by(
            "cds_id",
            "start_position",
        ):
            domains_by_cds.setdefault(d.cds_id, []).append(d)

    cds_list_out: list[RegionCdsOut] = []
    domain_list_out: list[RegionDomainOut] = []
    for cds in cds_rows:
        cds_doms = domains_by_cds.get(cds.id, [])
        interpro = collapse_to_interpro_rows(cds_doms)

        pfam = []
        for d in cds_doms:
            pfam.append(
                PfamAnnotationOut(
                    accession=d.domain_acc or "",
                    description=d.domain_description or d.domain_name or "",
                    go_slim=list(d.go_slim or []),
                    envelope_start=d.start_position or 0,
                    envelope_end=d.end_position or 0,
                    e_value=str(d.score) if d.score is not None else None,
                    url=d.url or "",
                )
            )
            if (cds.strand or 1) >= 0:
                dom_nt_start = cds.start_position + (d.start_position or 0) * 3
                dom_nt_end = cds.start_position + (d.end_position or 0) * 3
            else:
                dom_nt_start = cds.end_position - (d.end_position or 0) * 3
                dom_nt_end = cds.end_position - (d.start_position or 0) * 3
            domain_list_out.append(
                RegionDomainOut(
                    accession=d.domain_acc or "",
                    description=d.domain_description or d.domain_name or "",
                    start=max(0, dom_nt_start - window_start),
                    end=max(0, dom_nt_end - window_start),
                    strand=cds.strand,
                    score=d.score,
                    go_slim=list(d.go_slim or []),
                    parent_cds_id=cds.protein_id_str,
                    url=d.url or "",
                )
            )

        # claimed_by_tools: predictions whose bgc_range overlaps this CDS.
        claimed: set[str] = set()
        for pred in predictions:
            if pred.bgc_range is None:
                continue
            if (
                pred.bgc_range.lower < cds.cds_range.upper
                and cds.cds_range.lower < pred.bgc_range.upper
            ):
                tool = pred.detector.tool if pred.detector_id else ""
                if tool:
                    claimed.add(tool)

        seq_obj = getattr(cds, "seq", None)
        sequence = seq_obj.get_sequence() if seq_obj else ""

        cds_list_out.append(
            RegionCdsOut(
                protein_id=cds.protein_id_str,
                start=cds.start_position - window_start,
                end=cds.end_position - window_start,
                strand=cds.strand,
                protein_length=cds.protein_length,
                gene_caller=cds.gene_caller or "",
                cluster_representative=cds.cluster_representative or None,
                cluster_representative_url=None,
                sequence=sequence,
                pfam=pfam,
                interpro=[InterproAnnotationOut(**r) for r in interpro],
                claimed_by_tools=sorted(claimed),
            )
        )

    cluster_list_out = []
    for pred in predictions:
        if pred.bgc_range is None:
            continue
        cluster_list_out.append(
            RegionClusterOut(
                accession=pred.prediction_accession,
                start=max(0, pred.bgc_range.lower - window_start),
                end=max(0, pred.bgc_range.upper - 1 - window_start),
                source=pred.detector.tool if pred.detector_id else "",
                # Raw per-tool product class, shown verbatim on prediction hover.
                bgc_classes=(
                    [pred.classification_path] if pred.classification_path else []
                ),
            )
        )

    return IbgcRegionOut(
        ibgc_id=ibgc.id,
        ibgc_accession=ibgc.accession,
        cbgc_accession=ibgc.cbgc.accession if ibgc.cbgc_id else "",
        region_length=region_length,
        window_start=0,
        window_end=region_length,
        contig_accession=ibgc.contig.accession if ibgc.contig_id else None,
        cds_list=cds_list_out,
        domain_list=domain_list_out,
        cluster_list=cluster_list_out,
    )


# ── Accession resolve ─────────────────────────────────────────────────────────
