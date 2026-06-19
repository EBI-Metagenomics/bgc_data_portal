"""Combined multi-criterion query orchestration.

``run_combined_query`` resolves every scoring criterion (via the canonical
resolvers in :mod:`discovery.services.query.criteria`), **intersects** their iBGC
id sets under AND semantics, applies the non-scoring narrowing filters to that
intersection, and returns a JSON-serialisable result dict the API status/scores
endpoints render. Each criterion instance keeps its own score payload, so the
roster and Variables map can surface one (or more) sortable column per criterion.

This runs inside the ``combined_query`` worker task. It is deliberately free of
any Ninja/web-layer types; ``_apply_ibgc_filters`` is imported lazily from the
API module at call time (the only runtime coupling, and not an import cycle since
that import is function-local on both sides).
"""

from __future__ import annotations

import logging

from .criteria import (
    CRITERION_METRICS,
    RESULT_CAP,
    build_params,
    resolve_criterion,
)

log = logging.getLogger(__name__)

# Filter kwargs accepted by ``api._apply_ibgc_filters`` (minus ``ibgc_ids``,
# which the orchestrator sets itself). Mirrors that function's signature; keep
# in sync if a new narrowing filter is added there.
FILTER_KEYS = (
    "include_partials",
    "validated_only",
    "min_length_kb",
    "max_length_kb",
    "min_novelty",
    "max_novelty",
    "min_domain_novelty",
    "max_domain_novelty",
    "detector_tools",
    "source_tools",
    "source_names",
    "assembly_type",
    "leaf_path_prefix",
    "bgc_class",
    "chemont_ids",
    "np_classes",
    "accession",
    "bgc_accession",
    "assembly_accession",
    "assembly_ids",
    "organism",
    "biome_lineage",
    "taxonomy_path",
    "domain_text",
)


def criterion_label(ctype: str, params, index_within_type: int, type_count: int) -> str:
    """Human column header for a criterion instance, auto-derived from its params.

    A ``#n`` suffix disambiguates multiple criteria of the same type (e.g. two
    domain filters). The per-instance id remains the stable key; the label is
    cosmetic.
    """
    if ctype == "domain":
        base = "Domain sim."
    elif ctype == "architecture":
        base = "Architecture sim."
    elif ctype == "sequence":
        base = "Sequence"
    elif ctype == "chemical":
        base = "Chemical sim."
    elif ctype == "similar":
        base = f"Similar to iBGC-{params.ibgc_id}"
    else:
        base = ctype.capitalize()
    if type_count > 1:
        return f"{base} #{index_within_type + 1}"
    return base


def _filter_candidate_ids(candidate_ids: list[int], filters: dict) -> set[int]:
    """Narrow ``candidate_ids`` through ``api._apply_ibgc_filters``.

    Applied to the (bounded) candidate set rather than the whole table, so the
    join-heavy filters stay cheap. Returns the surviving id set.
    """
    from discovery.api import _apply_ibgc_filters
    from discovery.models import IntegratedBgc

    kwargs = {k: filters[k] for k in FILTER_KEYS if k in filters and filters[k] is not None}
    base = IntegratedBgc.objects.filter(id__in=candidate_ids)
    qs = _apply_ibgc_filters(base, ibgc_ids=None, **kwargs)
    return set(qs.values_list("id", flat=True))


def _filter_all_ids(filters: dict, cap: int) -> list[int]:
    """Filter-only fallback (no scoring criteria): apply filters across the table."""
    from discovery.api import _apply_ibgc_filters
    from discovery.models import IntegratedBgc

    kwargs = {k: filters[k] for k in FILTER_KEYS if k in filters and filters[k] is not None}
    qs = _apply_ibgc_filters(IntegratedBgc.objects.all(), ibgc_ids=None, **kwargs)
    return list(qs.values_list("id", flat=True)[: cap + 1])


def run_combined_query(
    criteria: list[dict], filters: dict | None = None, *, cap: int = RESULT_CAP
) -> dict:
    """Resolve, intersect, filter, and serialise a combined multi-criterion query.

    ``criteria`` is a list of ``{"id", "type", "params"}`` dicts. Returns a dict::

        {
          "criteria": [{"id","type","label","metrics":[{key,label,sortable}]}],
          "scores_by_id": {"<ibgc_id>": {"<cid>": {"value", ...}}},
          "ordered_ids": [ibgc_id, ...],   # capped, primary-criterion best-first
          "total_matched": int,            # full intersection size (pre-cap)
          "capped": bool,
          "cap": int,
          "warnings": [str, ...],
        }

    Raises :class:`CriterionError` for an unknown/invalid criterion or an
    unavailable backing index (the task fails; the API status endpoint maps it).
    """
    filters = filters or {}
    cap = max(1, min(int(cap), RESULT_CAP))
    warnings: list[str] = []

    # Resolve each criterion instance. Track per-type counts so duplicate types
    # get disambiguated labels.
    type_counts: dict[str, int] = {}
    for c in criteria:
        type_counts[c["type"]] = type_counts.get(c["type"], 0) + 1

    columns: list[dict] = []
    resolved: list[tuple[str, dict[int, dict]]] = []  # (cid, scores)
    seen_type_idx: dict[str, int] = {}

    for c in criteria:
        cid = c["id"]
        ctype = c["type"]
        params = build_params(ctype, c.get("params") or {})
        result = resolve_criterion(ctype, params)
        warnings.extend(result.warnings)

        idx = seen_type_idx.get(ctype, 0)
        seen_type_idx[ctype] = idx + 1
        columns.append(
            {
                "id": cid,
                "type": ctype,
                "label": criterion_label(ctype, params, idx, type_counts[ctype]),
                "metrics": [
                    {"key": m.key, "label": m.label, "sortable": m.sortable}
                    for m in (result.metrics or CRITERION_METRICS.get(ctype, []))
                ],
            }
        )
        resolved.append((cid, result.scores))

    # Intersect id sets across criteria (AND). With no criteria, fall back to a
    # filter-only candidate set.
    if resolved:
        id_sets = [set(scores) for _, scores in resolved]
        candidate = set.intersection(*id_sets) if id_sets else set()
        if filters:
            candidate = _filter_candidate_ids(list(candidate), filters)
        candidate_ids = list(candidate)
    else:
        candidate_ids = _filter_all_ids(filters, cap)

    total_matched = len(candidate_ids)

    # Order by the primary (first) criterion's value, best-first, so the cap
    # drops the lowest-scoring hits rather than an arbitrary slice.
    if resolved:
        primary_scores = resolved[0][1]
        candidate_ids.sort(
            key=lambda i: _as_float(primary_scores.get(i, {}).get("value")),
            reverse=True,
        )
    if total_matched > cap:
        candidate_ids = candidate_ids[:cap]
        capped = True
    else:
        capped = False

    # Build the per-id score payloads (string keys — JSON-serialisable for the
    # task result backend).
    scores_by_id: dict[str, dict[str, dict]] = {}
    keep = set(candidate_ids)
    for cid, scores in resolved:
        for nid, payload in scores.items():
            if nid in keep:
                scores_by_id.setdefault(str(nid), {})[cid] = payload

    log.info(
        "Combined query: criteria=%d total_matched=%d capped=%s",
        len(criteria),
        total_matched,
        capped,
    )
    return {
        "criteria": columns,
        "scores_by_id": scores_by_id,
        "ordered_ids": candidate_ids,
        "total_matched": total_matched,
        "capped": capped,
        "cap": cap,
        "warnings": warnings,
    }


def _as_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("-inf")
