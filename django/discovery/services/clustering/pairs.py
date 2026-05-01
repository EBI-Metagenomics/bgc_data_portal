"""Build the ``ProteinSimilarPair`` table via batched pgvector HNSW ANN.

Iterates over **unique** ``protein_sha256`` keys in the embedding table; for
each batch issues a single SQL statement using the existing HNSW index on
``discovery_protein_embedding`` to retrieve up to ``top_k`` neighbours at
cosine ≥ ``floor``. Both directions ``(a, b)`` and ``(b, a)`` are inserted
so threshold scans from a single sha256 are a single index seek.

Resumable: skips proteins already represented as a left-side (``a``)
sha256 with at least one row in the pair table.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.db import connection, transaction

log = logging.getLogger(__name__)


DEFAULT_TOP_K = 64


def build_protein_similar_pairs(
    *,
    floor: float = 0.7,
    batch_size: int = 1024,
    top_k: int = DEFAULT_TOP_K,
    ef_search: int = 200,
    resume: bool = True,
    progress_cb: Any | None = None,
) -> dict:
    """Recompute (or extend) the ``ProteinSimilarPair`` table.

    Parameters
    ----------
    floor:
        Minimum cosine to keep. The pair table can serve any threshold ≥
        floor at runtime; raising the floor requires a recompute.
    batch_size:
        Number of sha256s queried per round-trip.
    top_k:
        Maximum neighbours requested per protein from the HNSW index.
    ef_search:
        ``hnsw.ef_search`` setting for this session — higher values trade
        latency for recall.
    resume:
        Skip sha256s that already have at least one ``protein_a_sha256``
        entry in the table. Useful for resuming an interrupted run.
    progress_cb:
        Optional callable invoked as ``progress_cb({"processed": N,
        "inserted": M, "skipped": K})`` after each batch — the Celery task
        wires this to the Redis job cache.
    """
    from discovery.models import ProteinEmbedding, ProteinSimilarPair

    if not 0.0 <= floor <= 1.0:
        raise ValueError(f"floor must be in [0, 1], got {floor}")

    total = ProteinEmbedding.objects.count()
    if total == 0:
        log.warning("build_protein_similar_pairs: no ProteinEmbedding rows")
        return {"processed": 0, "inserted": 0, "skipped": 0, "total": 0}

    if resume:
        already = set(
            ProteinSimilarPair.objects.values_list(
                "protein_a_sha256", flat=True
            ).distinct()
        )
    else:
        already = set()
        ProteinSimilarPair.objects.all().delete()

    processed = 0
    inserted = 0
    skipped = 0
    started = time.monotonic()

    qs = ProteinEmbedding.objects.values_list("protein_sha256", flat=True)

    batch: list[str] = []
    for sha in qs.iterator(chunk_size=batch_size * 8):
        if sha in already:
            skipped += 1
            processed += 1
            continue
        batch.append(sha)
        if len(batch) >= batch_size:
            inserted += _flush_batch(batch, floor, top_k, ef_search)
            processed += len(batch)
            if progress_cb is not None:
                progress_cb(
                    {
                        "processed": processed,
                        "inserted": inserted,
                        "skipped": skipped,
                        "total": total,
                        "elapsed_s": round(time.monotonic() - started, 2),
                    }
                )
            batch.clear()

    if batch:
        inserted += _flush_batch(batch, floor, top_k, ef_search)
        processed += len(batch)

    elapsed = time.monotonic() - started
    log.info(
        "build_protein_similar_pairs: processed=%d inserted=%d skipped=%d total=%d elapsed=%.1fs",
        processed, inserted, skipped, total, elapsed,
    )
    if progress_cb is not None:
        progress_cb(
            {
                "processed": processed,
                "inserted": inserted,
                "skipped": skipped,
                "total": total,
                "elapsed_s": round(elapsed, 2),
                "done": True,
            }
        )
    return {
        "processed": processed,
        "inserted": inserted,
        "skipped": skipped,
        "total": total,
        "elapsed_s": round(elapsed, 2),
    }


def _flush_batch(
    sha_batch: list[str],
    floor: float,
    top_k: int,
    ef_search: int,
) -> int:
    """Run one round-trip ANN query for ``sha_batch`` and insert pairs both ways.

    Returns the number of rows inserted (counting both directions).
    """
    from discovery.models import EMBEDDING_DIM, ProteinSimilarPair

    max_distance = 1.0 - floor
    sql = f"""
        SELECT a.protein_sha256, b.protein_sha256, 1 - (a.vector <=> b.vector)
        FROM discovery_protein_embedding a
        JOIN LATERAL (
            SELECT protein_sha256, vector
            FROM discovery_protein_embedding b_inner
            WHERE b_inner.protein_sha256 <> a.protein_sha256
              AND (a.vector <=> b_inner.vector) <= %s
            ORDER BY a.vector <=> b_inner.vector
            LIMIT %s
        ) b ON true
        WHERE a.protein_sha256 = ANY(%s)
    """
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL hnsw.ef_search = %s;", [ef_search])
        cursor.execute(sql, [max_distance, top_k, list(sha_batch)])
        rows = cursor.fetchall()

    if not rows:
        return 0

    pairs: list[ProteinSimilarPair] = []
    seen: set[tuple[str, str]] = set()
    for a, b, cos in rows:
        cos = float(cos)
        if cos < floor:
            continue
        if (a, b) not in seen:
            pairs.append(
                ProteinSimilarPair(
                    protein_a_sha256=a, protein_b_sha256=b, cosine=cos
                )
            )
            seen.add((a, b))
        if (b, a) not in seen:
            pairs.append(
                ProteinSimilarPair(
                    protein_a_sha256=b, protein_b_sha256=a, cosine=cos
                )
            )
            seen.add((b, a))

    if not pairs:
        return 0
    with transaction.atomic():
        ProteinSimilarPair.objects.bulk_create(pairs, ignore_conflicts=True, batch_size=5_000)
    return len(pairs)


def pair_table_etag() -> str:
    """Return a cheap fingerprint of the current pair table state.

    Used by the clustering run dedup hash so repeating ``run_bgc_clustering``
    against an unchanged pair table reuses the existing ClusteringRun. The
    fingerprint is ``"<count>:<max_id>"`` — both queries hit indexes and
    don't scan the table.
    """
    from discovery.models import ProteinSimilarPair

    count = ProteinSimilarPair.objects.count()
    max_id = ProteinSimilarPair.objects.values_list("id", flat=True).order_by("-id").first() or 0
    return f"{count}:{max_id}"
