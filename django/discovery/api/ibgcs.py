"""iBGC endpoints: count, roster, ids, scatter, detail, architecture, region.

The literal ``/ibgcs/<name>/`` routes are declared before ``/ibgcs/{ibgc_id}/``
because Django Ninja matches in declaration order."""

import logging

from django.db.models import (
    Count,
    ExpressionWrapper,
    FloatField,
    OuterRef,
    Subquery,
)
from ninja import Query
from ninja.errors import HttpError

from discovery.api._common import (
    DASHBOARD_RESULT_CAP,
    asset_roster_rows,
    asset_row_to_roster_item,
    asset_token_header,
    cache_ibgc_idset,
    ibgc_is_partial,
    ibgc_label,
    ibgc_member_facts,
    ibgc_queryset,
    ibgc_to_roster_item,
    make_router,
    paginate,
    parse_ibgc_id_scope,
)
from discovery.api_schemas import (
    DomainArchitectureItem,
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
    PaginatedIbgcRosterResponse,
    PaginationMeta,
    ParentAssemblySummary,
    PfamAnnotationOut,
    RegionCdsOut,
    RegionClusterOut,
    RegionDomainOut,
)
from discovery.models import (
    ContigCds,
    ContigDomain,
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

router = make_router()


logger = logging.getLogger(__name__)


_IBGC_AXES = {
    "size_kb",  # length / 1000
    "n_cds",
    "novelty_score",
    "domain_novelty",
    "similarity_score",  # populated only from a similarity query context
}


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


@router.get("/ibgcs/count/", response=IbgcCountResponse)
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
    parsed_ids = parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    qs = ibgc_queryset(filters, parsed_ids, asset_token)
    total = qs.count() + len(asset_roster_rows(asset_token))
    return IbgcCountResponse(
        exact_count=total,
        cap=DASHBOARD_RESULT_CAP,
        will_sample=total > DASHBOARD_RESULT_CAP,
    )


@router.post(
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
    token, n = cache_ibgc_idset(ids)
    return IbgcIdSetResponse(token=token, n_ibgcs=n)


@router.get(
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
    parsed_ids = parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    qs = ibgc_queryset(filters, parsed_ids, asset_token)
    # ``sort_by=similarity`` honours the caller-supplied order of ``ibgc_ids``;
    # every other key sorts the stored columns NULLS LAST. Shared with the
    # scatter endpoint so both surfaces agree on rank.
    qs = apply_ibgc_sort(qs, sort_by, order, parsed_ids)

    asset_items = [asset_row_to_roster_item(r) for r in asset_roster_rows(asset_token)]
    total_count = qs.count() + len(asset_items)
    pg, ps, tp, offset = paginate(page, page_size, total_count)

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
    facts = ibgc_member_facts([ibgc.id for ibgc in page_qs])
    db_items = [ibgc_to_roster_item(ibgc, facts[ibgc.id]) for ibgc in page_qs]
    return PaginatedIbgcRosterResponse(
        items=asset_slice + db_items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


IBGC_IDS_MAX = 1_000


@router.get("/ibgcs/ids/", response=IbgcIdsResponse)
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
    parsed_ids = parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
    qs = apply_ibgc_sort(
        ibgc_queryset(filters, parsed_ids, asset_token), sort_by, order, parsed_ids
    )
    # Asset iBGCs lead the roster, so they lead the id list too ("Add all"
    # mirrors what the user sees on page 1).
    asset_id_seq = [int(r["id"]) for r in asset_roster_rows(asset_token)]
    total_count = qs.count() + len(asset_id_seq)
    remaining = max(0, IBGC_IDS_MAX - len(asset_id_seq))
    ids = asset_id_seq + list(qs.values_list("id", flat=True)[:remaining])
    return IbgcIdsResponse(
        ids=ids, total_count=total_count, truncated=len(ids) < total_count
    )


@router.get(
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

    parsed_ids = parse_ibgc_id_scope(ibgc_ids, ibgc_ids_token)
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
        facts = ibgc_member_facts([n.id for n in ibgc_list])

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
                    is_partial=ibgc_is_partial(ibgc),
                    is_validated=facts[ibgc.id]["is_validated"],
                    is_type_strain=facts[ibgc.id]["is_type_strain"],
                )
            )
    asset_points: list[IbgcScatterPoint] = []
    for row in asset_roster_rows(asset_token):
        pt = _asset_row_to_scatter_point(row, x_axis, y_axis)
        if pt is not None:
            asset_points.append(pt)
    return asset_points + points


@router.get("/ibgcs/{ibgc_id}/", response=IbgcDetail)
def ibgc_detail(request, ibgc_id: int):
    if ibgc_id < 0:
        token = asset_token_header(request)
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
        label=ibgc_label(ibgc.id),
        classification_path=ibgc.gene_cluster_family or "",
        bgc_class=ibgc.bgc_class or "",
        size_kb=round((ibgc.end_position - ibgc.start_position) / 1000.0, 3),
        start_position=ibgc.start_position,
        end_position=ibgc.end_position,
        contig_accession=ibgc.contig.accession if ibgc.contig else None,
        source_tools=list(ibgc.source_tools or []),
        novelty_score=ibgc.novelty_score,
        domain_novelty=ibgc.domain_novelty,
        is_partial=ibgc_is_partial(ibgc),
        is_validated=is_validated,
        is_type_strain=is_type_strain,
        parent_assembly=parent,
        region_endpoint_url=f"/api/discovery/ibgcs/{ibgc.id}/region/",
        member_bgcs=member_items,
        domain_architecture=domain_arch,
        npc_labels=npc_items,
    )


@router.get(
    "/ibgcs/{ibgc_id}/architecture/",
    response=IbgcArchitectureResponse,
)
def ibgc_architecture_endpoint(request, ibgc_id: int):
    """Pooled positional domain accessions for an iBGC (clipboard payload).

    Lightweight wrapper around the same ordering rule that ``ibgc_detail``
    uses for ``domain_architecture``.
    """
    if ibgc_id < 0:
        token = asset_token_header(request)
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
        label=ibgc_label(ibgc.id),
        ordered_accs=ordered_accs,
    )


@router.get("/ibgcs/{ibgc_id}/region/", response=IbgcRegionOut)
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
        token = asset_token_header(request)
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
