"""Cache + job-status helpers for discovery background tasks.

Progress and final results are mirrored into the default Django cache (Postgres
``DatabaseCache``) under consistent keys; the django-tasks-db backend is the
source of truth for terminal status. ``fetch_job`` adapts a django-tasks
``TaskResult`` to the small ``.ready()/.failed()/.result`` surface the API poll
endpoints expect (so they need only swap their import + lookup line).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django_tasks import TaskResultStatus, default_task_backend


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


class JobResult:
    """Thin adapter over a django-tasks ``TaskResult`` exposing the
    ``.ready()`` / ``.failed()`` / ``.result`` surface used by the API poll
    endpoints. ``None`` means the backend has no record of the id (treated as
    still-pending by callers)."""

    def __init__(self, task_result: Any | None) -> None:
        self._tr = task_result

    def ready(self) -> bool:
        return self._tr is not None and self._tr.is_finished

    def failed(self) -> bool:
        return self._tr is not None and self._tr.status == TaskResultStatus.FAILED

    @property
    def result(self) -> Any:
        if self._tr is None or self._tr.status != TaskResultStatus.SUCCESSFUL:
            return None
        return self._tr.return_value

    @property
    def errors(self) -> list:
        return list(getattr(self._tr, "errors", []) or []) if self._tr else []


def fetch_job(task_id: str | None) -> JobResult:
    """Look up a task's result by id; never raises for an unknown id."""
    if not task_id:
        return JobResult(None)
    try:
        return JobResult(default_task_backend.get_result(task_id))
    except Exception:
        return JobResult(None)
