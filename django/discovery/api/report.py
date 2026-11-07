"""Shortlist Report endpoints: snapshot, fetch and exports."""

import json
import logging

from django.http import HttpResponse
from ninja.errors import HttpError

from discovery.api._common import (
    make_router,
)
from discovery.api_schemas import (
    ReportPayload,
    ReportSnapshotRequest,
    ReportSnapshotResponse,
)
from discovery.security import first_party_gate

router = make_router()


logger = logging.getLogger(__name__)


@router.post(
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


@router.get(
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


@router.get(
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


@router.get(
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


@router.get(
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
