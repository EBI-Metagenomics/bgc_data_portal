"""Load-asset endpoints: upload, status and eviction of a user tarball."""

import logging

from ninja.errors import HttpError

from discovery.api._common import make_router
from discovery.api_schemas import (
    AssetStatusResponse,
    AssetUploadAccepted,
)
from discovery.security import first_party_gate
from discovery.throttling import (
    upload_throttle,
)

router = make_router()


logger = logging.getLogger(__name__)


_ASSET_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post(
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


@router.get(
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


@router.delete(
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
