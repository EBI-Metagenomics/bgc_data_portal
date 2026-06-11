"""Cache helper utilities for discovery assessment tasks.

Provides the same set_job_cache / get_job_status pattern used by the
core search tasks, but kept within the discovery package so the module
has no imports from mgnify_bgcs.
"""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult

from django.conf import settings
from django.core.cache import cache


def set_job_cache(
    search_key: str,
    task_id: str,
    results: dict | None = None,
    timeout: int | None = None,
) -> None:
    """Store task results under consistent cache keys."""
    ttl = timeout if timeout is not None else getattr(settings, "CACHE_TIMEOUT", None)
    cache.set(task_id, search_key, ttl)
    if results is None:
        results = {}
    results["task_id"] = task_id
    cache.set(search_key, results, ttl)


def get_job_status(
    search_key: str | None = None, task_id: str | None = None
) -> dict[str, Any]:
    """Return a dict with task_id, search_key, status, result (if available)."""
    if task_id:
        search_key = cache.get(task_id)

    if search_key:
        result = cache.get(search_key, {})
        task_id = result.pop("task_id", None)
        if result:
            return {"search_key": search_key, "status": "SUCCESS", "result": result}

    try:
        res = AsyncResult(task_id)
        data: dict[str, Any] = {
            "task_id": task_id,
            "search_key": search_key,
            "status": res.status,
        }
        if res.ready():
            try:
                data["result"] = cache.get(search_key)
            except Exception:
                data["result"] = None
        return data
    except Exception:
        return {"task_id": task_id, "search_key": search_key, "status": "UNKNOWN"}
