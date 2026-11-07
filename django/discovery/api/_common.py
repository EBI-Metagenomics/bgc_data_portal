"""Helpers shared by the discovery routers: pagination, id-scope tokens, asset rows and roster-row serialisation."""

import math

from ninja import Router
from ninja.errors import HttpError

from discovery.api_schemas import (
    IbgcRosterItem,
)
from discovery.models import (
    IntegratedBgc,
    SourceBgcPrediction,
)
from discovery.services.ibgc_filters import (
    IbgcFilterParams,
    apply_ibgc_filters,
    asset_only_mode,
    filters_active,
)
from discovery.throttling import (
    default_throttle,
)


def make_router() -> Router:
    """One Router per endpoint module, all sharing the Discovery tag and throttle."""
    return Router(tags=["Discovery Platform"], throttle=default_throttle)


def paginate(page: int, page_size: int, total_count: int):
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total_pages = max(1, math.ceil(total_count / page_size))
    offset = (page - 1) * page_size
    return page, page_size, total_pages, offset


DASHBOARD_RESULT_CAP = 5_000


IBGC_IDSET_TTL_SECONDS = 24 * 3600


def ibgc_idset_cache_key(token: str) -> str:
    return f"ibgcset:{token}"


def cache_ibgc_idset(ids: list[int]) -> tuple[str, int]:
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
    cache.set(ibgc_idset_cache_key(token), ids, IBGC_IDSET_TTL_SECONDS)
    return token, len(ids)


def parse_ibgc_id_scope(
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

        cached = cache.get(ibgc_idset_cache_key(ibgc_ids_token))
        if cached is None:
            raise HttpError(
                404,
                "Result set expired — re-run your query to refresh it.",
            )
        return list(cached) or None
    if ibgc_ids:
        return [int(x) for x in ibgc_ids.split(",") if x.strip().isdigit()] or None
    return None


def ibgc_label(ibgc_id: int) -> str:
    return f"iBGC-{ibgc_id}"


def ibgc_is_partial(ibgc: IntegratedBgc) -> bool:
    """An iBGC is "partial" when it didn't go through the primary clustering
    pass — either no clustering run touched it, or its GCF / novelty were
    projected from its top-K primary neighbours (``is_partial=True``)."""
    return bool(ibgc.is_partial) or ibgc.classification_run_id is None


def ibgc_queryset(filters: IbgcFilterParams, parsed_ids, asset_token):
    """DB rows for the filter surface, or none() while an asset is shown alone."""
    if asset_only_mode(asset_token, parsed_ids, filters_active(filters)):
        return IntegratedBgc.objects.none()
    return apply_ibgc_filters(IntegratedBgc.objects.all(), filters, ibgc_ids=parsed_ids)


def asset_roster_rows(asset_token: str | None) -> list[dict]:
    if not asset_token:
        return []
    from discovery.services.asset_upload import cache as asset_cache

    return list(asset_cache.read_ibgc_list(asset_token) or [])


def asset_row_to_roster_item(row: dict) -> IbgcRosterItem:
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


def ibgc_to_roster_item(
    ibgc: IntegratedBgc,
    facts: dict | None = None,
    *,
    similarity_score: float | None = None,
    best_hit_protein_id: str | None = None,
    best_pident: float | None = None,
    best_qcoverage: float | None = None,
) -> IbgcRosterItem:
    """Serialise one roster row; ``facts`` comes from ``ibgc_member_facts``."""
    facts = facts or {}
    parent_assembly = facts.get("parent_assembly")
    return IbgcRosterItem(
        id=ibgc.id,
        accession=ibgc.accession or "",
        label=ibgc_label(ibgc.id),
        cbgc_accession=facts.get("cbgc_accession"),
        classification_path=ibgc.gene_cluster_family or "",
        bgc_class=ibgc.bgc_class or "",
        size_kb=round((ibgc.end_position - ibgc.start_position) / 1000.0, 3),
        n_source_bgcs=facts.get("n_source_bgcs", 0),
        source_tools=list(ibgc.source_tools or []),
        novelty_score=ibgc.novelty_score,
        domain_novelty=ibgc.domain_novelty,
        is_partial=ibgc_is_partial(ibgc),
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


_MEMBER_FACTS_CHUNK = 500


def ibgc_member_facts(ibgc_ids: list[int]) -> dict[int, dict]:
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


def asset_token_header(request) -> str | None:
    """Frontend passes the active asset token via ``X-Asset-Token`` so the
    negative-id dispatcher can resolve asset iBGCs out of the cache without
    polluting the URL with a query param."""
    return request.headers.get("X-Asset-Token") or request.GET.get("asset_token")
