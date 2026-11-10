"""Build the ``IntegratedBgc`` table from latest-version source predictions.

iBGCs are strictly disjoint within their containing ``ConsensusBgc``. Each
iBGC's accession is minted via the stable-forever accession registry
(``MGYB-XXXXXX-YY``) and never reused.

Construction rules (per contig, applied within each contig's source
predictions):

  1. Pull all latest-version source predictions via
     :func:`discovery.querysets.latest_version_bgcs`.
  2. Emit one standalone iBGC per ``is_validated=True`` row regardless of
     tool or ``is_partial``. Validated rows are ground truth — never merged
     into prediction iBGCs, never absorbed.
  3. Merge non-validated GECCO and SanntiS predictions via transitive
     interval overlap (any positive intersection joins a component).
     Each component becomes one iBGC spanning ``min(starts) → max(ends)``
     and carries a sorted ``source_tools`` list. For each chain iBGC, if
     any non-validated antiSMASH prediction overlaps it, ``'antiSMASH'`` is
     added to ``source_tools`` — antiSMASH coordinates are *never* used
     to widen a chain interval.
  4. For each non-validated antiSMASH prediction:
       * if it overlaps any iBGC from steps 2–3, the prediction's
         ``integrated_bgc`` FK is set to that iBGC (so ``claimed_by_tools``
         attribution survives) — the iBGC's coords are NOT widened.
       * otherwise it becomes its own standalone iBGC inside the same cBGC.
  5. Mint each iBGC's accession; set ``cbgc`` FK from any member's cbgc_id;
     set ``contig`` FK; set source predictions' ``integrated_bgc`` FK.

This service is idempotent — calling it again wipes and rebuilds the table
(including tombstoning registry rows for iBGCs that no longer exist).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from django.db import transaction
from django.utils import timezone

from discovery.models import (
    AccessionEntityType,
    AccessionRegistry,
    ConsensusBgc,
    IntegratedBgc,
    SourceBgcPrediction,
)
from discovery.querysets import latest_version_bgcs
from discovery.services.accession_registry import (
    mint_ibgc_accession,
    tombstone_unused,
)
from discovery.services.ingestion.ranges import int4range

log = logging.getLogger(__name__)

# Tool names as stored in DashboardDetector.tool (case-sensitive).
TOOL_GECCO = "GECCO"
TOOL_SANNTIS = "SanntiS"
TOOL_ANTISMASH = "antiSMASH"

MERGE_TOOLS = (TOOL_GECCO, TOOL_SANNTIS)


# iBGC rows (and their registry / member updates) are flushed in batches of
# this size; each flush is three statements regardless of the batch's size.
_FLUSH_BATCH = 2_000
_PROGRESS_EVERY = 1000


def build_integrated_bgcs(
    *,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Rebuild the IntegratedBgc table from the latest-version source predictions.

    Runs in one transaction, so readers keep the previous iBGC set until the
    new one (including classes, catalog tables and NPClassifier labels) is
    committed. Accessions are stable across rebuilds through the registry;
    only never-seen coordinates mint a new one. Clustering snapshots are
    keyed on the accession, so a rebuild does not break rollback.

    Returns counts: ``n_ibgcs``, ``n_source_bgcs``, ``n_absorbed_antismash``
    (non-validated antiSMASH predictions that overlapped an iBGC and were
    attributed to it without widening it), ``n_validated_standalone``,
    ``by_tool`` and ``n_npc_labels``.

    ``progress_cb(phase, processed, total)`` is called per contig; when the
    cache lives in the same database the updates become visible at commit.
    """
    counts: dict[str, Any] = {
        "n_ibgcs": 0,
        "n_source_bgcs": 0,
        "n_absorbed_antismash": 0,
        "n_validated_standalone": 0,
        "by_tool": {TOOL_GECCO: 0, TOOL_SANNTIS: 0, TOOL_ANTISMASH: 0},
    }
    with transaction.atomic():
        log.info("Wiping existing IntegratedBgc table")
        IntegratedBgc.objects.all().delete()
        SourceBgcPrediction.objects.exclude(integrated_bgc=None).update(
            integrated_bgc=None
        )
        rows_by_contig = _latest_predictions_by_contig()
        total_contigs = len(rows_by_contig)
        log.info("Building iBGCs for %d contigs", total_contigs)

        cbgc_accessions = dict(ConsensusBgc.objects.values_list("id", "accession"))
        # (contig_accession, start, end) -> accession for every iBGC ever seen.
        registry = {
            (c, s, e): acc
            for c, s, e, acc in AccessionRegistry.objects.filter(
                entity_type=AccessionEntityType.IBGC
            ).values_list("contig_accession", "start_pos", "end_pos", "accession")
        }

        pending: list[tuple[IntegratedBgc, list[int]]] = []
        for processed, (contig_id, rows) in enumerate(rows_by_contig.items(), 1):
            ibgcs, absorbed_anti, validated_standalone = _build_ibgcs_for_contig(rows)
            counts["n_absorbed_antismash"] += absorbed_anti
            counts["n_validated_standalone"] += validated_standalone
            contig_accession = rows[0][7]
            cbgc_of_sbgc = {sbgc_id: cbgc_id for sbgc_id, cbgc_id, *_ in rows}

            for start, end, source_tools, member_ids, absorbed_ids in ibgcs:
                # Every member shares the same cBGC (overlapping predictions on
                # a contig land in the same cBGC envelope in the loader).
                cbgc_id = next(
                    (cbgc_of_sbgc[i] for i in member_ids if cbgc_of_sbgc.get(i)),
                    None,
                )
                if cbgc_id is None:
                    log.warning(
                        "iBGC at contig=%s [%d,%d] has no cBGC; skipping",
                        contig_id,
                        start,
                        end,
                    )
                    continue
                key = (contig_accession, start, end)
                accession = registry.get(key)
                if accession is None:
                    accession = mint_ibgc_accession(
                        cbgc_accession=cbgc_accessions[cbgc_id],
                        contig_accession=contig_accession,
                        start_pos=start,
                        end_pos=end,
                    ).accession
                    registry[key] = accession
                pending.append(
                    (
                        IntegratedBgc(
                            accession=accession,
                            cbgc_id=cbgc_id,
                            contig_id=contig_id,
                            bgc_range=int4range(start, end),
                            source_tools=sorted(source_tools),
                        ),
                        list(member_ids) + list(absorbed_ids),
                    )
                )
                counts["n_ibgcs"] += 1
                counts["n_source_bgcs"] += len(member_ids) + len(absorbed_ids)
                for tool in source_tools:
                    counts["by_tool"][tool] = counts["by_tool"].get(tool, 0) + 1

            if len(pending) >= _FLUSH_BATCH:
                _flush(pending)
                pending = []
            # Throttled: each report is a DatabaseCache write (SELECT COUNT(*)
            # cull check + UPDATE) inside this one long transaction, whose dead
            # row versions cannot be pruned until commit; per-contig reports
            # made the build quadratic (2026-11 exp rebuild, 346k contigs).
            if progress_cb is not None and (
                processed % _PROGRESS_EVERY == 0 or processed == total_contigs
            ):
                progress_cb("contigs", processed, total_contigs)
        _flush(pending)

        tombstoned = tombstone_unused(AccessionEntityType.IBGC)
        log.info("Tombstoned %d stale iBGC registry rows", tombstoned)

        # Product classes, the BGC-class / domain catalog tables and the
        # NPClassifier label union all derive from the new rows; rebuild them
        # in the same transaction so filters never see a half-built state.
        from discovery.services.npc import aggregate_ibgc_npc_labels
        from discovery.services.scores import (
            _rebuild_catalog_tables,
            recompute_ibgc_classes,
        )

        recompute_ibgc_classes()
        _rebuild_catalog_tables()
        counts["n_npc_labels"] = aggregate_ibgc_npc_labels()

    log.info("iBGC build complete: %s", counts)
    return counts


def _latest_predictions_by_contig() -> dict[int, list[tuple]]:
    """Group latest-version predictions per contig.

    Each row is ``(sbgc_id, cbgc_id, start, end_inclusive, tool, is_partial,
    is_validated, contig_accession)``.
    """
    qs = (
        latest_version_bgcs()
        .select_related("detector", "contig")
        .only(
            "id",
            "contig_id",
            "contig__accession",
            "cbgc_id",
            "bgc_range",
            "is_partial",
            "is_validated",
            "detector__tool",
        )
    )
    rows_by_contig: dict[int, list[tuple]] = defaultdict(list)
    for sbgc in qs.iterator():
        rng = sbgc.bgc_range
        if rng is None or rng.lower is None or rng.upper is None:
            continue
        rows_by_contig[sbgc.contig_id].append(
            (
                sbgc.id,
                sbgc.cbgc_id,
                int(rng.lower),
                int(rng.upper) - 1,
                sbgc.detector.tool if sbgc.detector_id else None,
                bool(sbgc.is_partial),
                bool(sbgc.is_validated),
                sbgc.contig.accession or "",
            )
        )
    return rows_by_contig


def _flush(pending: list[tuple[IntegratedBgc, list[int]]]) -> None:
    """Insert a batch of iBGCs and point their registry rows and members at them."""
    if not pending:
        return
    IntegratedBgc.objects.bulk_create([ibgc for ibgc, _ in pending], batch_size=5_000)
    now = timezone.now()
    AccessionRegistry.objects.bulk_update(
        [
            AccessionRegistry(
                accession=ibgc.accession, current_ibgc_id=ibgc.id, last_seen_at=now
            )
            for ibgc, _ in pending
        ],
        ["current_ibgc", "last_seen_at"],
        batch_size=5_000,
    )
    SourceBgcPrediction.objects.bulk_update(
        [
            SourceBgcPrediction(id=sbgc_id, integrated_bgc_id=ibgc.id)
            for ibgc, member_ids in pending
            for sbgc_id in member_ids
        ],
        ["integrated_bgc"],
        batch_size=5_000,
    )


def _build_ibgcs_for_contig(
    rows: list[tuple[int, int, int, int, str | None, bool, bool, str]],
) -> tuple[
    list[tuple[int, int, list[str], list[int], list[int]]],
    int,
    int,
]:
    """Return ``(iBGCs, n_absorbed_antismash, n_validated_standalone)``.

    Row format: ``(sbgc_id, cbgc_id, start, end, tool, is_partial, is_validated, contig_accession)``.
    Each iBGC tuple: ``(start, end, sorted_source_tools, member_sbgc_ids, absorbed_sbgc_ids)``.
    Members widen the interval; absorbed predictions do not but their FK is
    still set to the iBGC.
    """
    validated_rows = [r for r in rows if r[6]]
    non_validated = [r for r in rows if not r[6]]
    merge_rows = [r for r in non_validated if r[4] in MERGE_TOOLS]
    antismash_rows = [r for r in non_validated if r[4] == TOOL_ANTISMASH]

    ibgcs: list[tuple[int, int, list[str], list[int], list[int]]] = []

    # 1. Validated → one standalone iBGC each.
    n_validated_standalone = 0
    for sbgc_id, _cbgc_id, start, end, tool, _, _, _ in validated_rows:
        tools = [tool] if tool else []
        ibgcs.append((start, end, tools, [sbgc_id], []))
        n_validated_standalone += 1

    # 2. Transitive sort-and-sweep merge for GECCO/SanntiS (partial-agnostic).
    merge_rows.sort(key=lambda r: (r[2], r[3]))
    current: dict[str, Any] | None = None
    for sbgc_id, _cbgc_id, start, end, tool, _, _, _ in merge_rows:
        if current is None or start > current["end"]:
            if current is not None:
                ibgcs.append(
                    (
                        current["start"],
                        current["end"],
                        sorted(set(current["tools"])),
                        current["sbgc_ids"],
                        [],
                    )
                )
            current = {
                "start": start,
                "end": end,
                "tools": [tool],
                "sbgc_ids": [sbgc_id],
            }
        else:
            current["end"] = max(current["end"], end)
            current["tools"].append(tool)
            current["sbgc_ids"].append(sbgc_id)
    if current is not None:
        ibgcs.append(
            (
                current["start"],
                current["end"],
                sorted(set(current["tools"])),
                current["sbgc_ids"],
                [],
            )
        )

    # 3. & 4. antiSMASH: tag chain source_tools where overlapping; set
    # integrated_bgc FK (absorbed_sbgc_ids) for predictions that overlap any
    # existing iBGC; else emit as their own standalone iBGC.
    n_absorbed = 0
    for sbgc_id, _cbgc_id, start, end, _tool, _, _, _ in antismash_rows:
        overlapping_idx = _find_overlapping_idx(start, end, ibgcs)
        if overlapping_idx is not None:
            c_start, c_end, c_tools, c_members, c_absorbed = ibgcs[overlapping_idx]
            new_tools = sorted(set(c_tools) | {TOOL_ANTISMASH})
            ibgcs[overlapping_idx] = (
                c_start,
                c_end,
                new_tools,
                c_members,
                c_absorbed + [sbgc_id],
            )
            n_absorbed += 1
            continue
        ibgcs.append((start, end, [TOOL_ANTISMASH], [sbgc_id], []))

    # 5. Dedup by (start, end) — defensive against rare duplicate intervals
    # from validated + chain mergers.
    ibgcs = _dedup_ibgcs_by_interval(ibgcs)

    return ibgcs, n_absorbed, n_validated_standalone


def _dedup_ibgcs_by_interval(
    ibgcs: list[tuple[int, int, list[str], list[int], list[int]]],
) -> list[tuple[int, int, list[str], list[int], list[int]]]:
    by_key: dict[tuple[int, int], tuple[list[str], list[int], list[int]]] = {}
    for start, end, tools, members, absorbed in ibgcs:
        key = (start, end)
        if key in by_key:
            t, m, a = by_key[key]
            by_key[key] = (
                sorted(set(t) | set(tools)),
                m + list(members),
                a + list(absorbed),
            )
        else:
            by_key[key] = (sorted(set(tools)), list(members), list(absorbed))
    return [(s, e, t, m, a) for (s, e), (t, m, a) in by_key.items()]


def _find_overlapping_idx(
    start: int,
    end: int,
    ibgcs: Iterable[tuple[int, int, list[str], list[int], list[int]]],
) -> int | None:
    for idx, (ibgc_start, ibgc_end, _t, _m, _a) in enumerate(ibgcs):
        if start <= ibgc_end and end >= ibgc_start:
            return idx
    return None
