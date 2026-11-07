"""Helpers for bulk-loading TSV data into PostgreSQL via COPY FROM."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from django.db import connection

logger = logging.getLogger(__name__)


def truncate_tables(tables: Sequence[str]) -> None:
    """TRUNCATE the given tables with CASCADE."""
    if not tables:
        return
    joined = ", ".join(tables)
    with connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE {joined} CASCADE")
    logger.info("TRUNCATED: %s", joined)
