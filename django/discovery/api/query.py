"""Search endpoints: find-similar and the combined multi-criterion query."""

import logging

from ninja.errors import HttpError

from discovery.api._common import (
    DASHBOARD_RESULT_CAP,
    cache_ibgc_idset,
    ibgc_member_facts,
    ibgc_to_roster_item,
    make_router,
    paginate,
)
from discovery.api_schemas import (
    CombinedQueryAccepted,
    CombinedQueryRequest,
    CombinedRosterItem,
    CombinedRosterResponse,
    CombinedScoreRow,
    CombinedScoresResponse,
    CriterionColumn,
    CriterionMetricSchema,
    CriterionScore,
    PaginatedIbgcRosterResponse,
    PaginationMeta,
    SimilarIbgcRequest,
)
from discovery.models import (
    IntegratedBgc,
)
from discovery.security import first_party_gate
from discovery.throttling import (
    search_throttle,
)

router = make_router()


logger = logging.getLogger(__name__)


@router.post(
    "/query/similar-ibgc/",
    response=PaginatedIbgcRosterResponse,
    include_in_schema=False,
    auth=first_party_gate,
    throttle=search_throttle,
)
def similar_ibgc_query(
    request,
    body: SimilarIbgcRequest,
    page: int = 1,
    page_size: int = 25,
):
    """Top-K iBGCs by composite similarity to ``body.ibgc_id``.

    The composite (the run's similarity metric: IDF × enrichment weighted
    cosine, or Dice on older runs) is computed on demand against the per-iBGC
    signature matrices of the active ClusteringRun. The full N×N similarity matrix
    is no longer materialised; the result is cached for 24h keyed
    on the run's sha256 so a new clustering run invalidates the cache by
    orphaning the previous keys.

    Delegates scoring to ``discovery.services.query.similar_top`` — the
    canonical resolver shared with the combined query engine.
    """
    from discovery.services.query import (
        CriterionError,
        build_params,
        similar_top,
    )

    try:
        top_ids, top_sims = similar_top(build_params("similar", body))
    except CriterionError as exc:
        raise HttpError(exc.status, exc.message) from exc
    sim_lookup = dict(zip(top_ids, top_sims))

    if not top_ids:
        return PaginatedIbgcRosterResponse(
            items=[],
            pagination=PaginationMeta(
                page=1, page_size=page_size, total_count=0, total_pages=0
            ),
        )

    total_count = len(top_ids)
    pg, ps, tp, offset = paginate(page, page_size, total_count)
    page_ids = top_ids[offset : offset + ps]

    ibgcs = {n.id: n for n in IntegratedBgc.objects.filter(id__in=page_ids)}
    facts = ibgc_member_facts(page_ids)
    items = [
        ibgc_to_roster_item(
            ibgcs[nid],
            facts[nid],
            similarity_score=round(sim_lookup[nid], 4),
        )
        for nid in page_ids
        if nid in ibgcs
    ]
    return PaginatedIbgcRosterResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg,
            page_size=ps,
            total_count=total_count,
            total_pages=tp,
        ),
    )


_COMBINED_DB_SORT = {
    "id": "id",
    "novelty_score": "novelty_score",
    "domain_novelty": "domain_novelty",
    "classification_path": "gene_cluster_family",
    "bgc_class": "bgc_class",
}


_MAX_COMBINED_CRITERIA = 12


def _clean_protein_sequence(sequence: str) -> str:
    """Strip FASTA headers/whitespace from a pasted protein sequence."""
    lines = (sequence or "").strip().splitlines()
    return "".join(line.strip() for line in lines if not line.startswith(">"))


def _validate_criterion_params(ctype: str, params) -> dict:
    """Per-type synchronous validation; returns the (possibly normalised) params dict.

    Mirrors the checks the single-criterion POST handlers do so obvious user
    errors fail fast with 400 instead of a failed background task. The sequence
    criterion's FASTA input is cleaned here so the worker receives bare residues.
    """
    if ctype == "domain":
        if not (params.domains_text or "").strip():
            raise HttpError(400, "domain criterion requires domains_text")
        if not (0.0 <= params.threshold <= 1.0):
            raise HttpError(400, "domain threshold must be between 0 and 1")
    elif ctype == "architecture":
        if not params.architecture:
            raise HttpError(
                400, "architecture criterion requires at least one accession"
            )
    elif ctype == "sequence":
        cleaned = _clean_protein_sequence(params.sequence)
        if not cleaned:
            raise HttpError(400, "sequence criterion requires a protein sequence")
        if len(cleaned) > 5000:
            raise HttpError(400, "Sequence exceeds maximum length of 5,000 amino acids")
        if not (0.0 <= params.min_bitscore <= 10_000.0):
            raise HttpError(400, "min_bitscore must be between 0 and 10000")
        if not (0.0 <= params.min_pident <= 100.0):
            raise HttpError(400, "min_pident must be between 0 and 100")
        if not (0.0 <= params.min_qcov <= 100.0):
            raise HttpError(400, "min_qcov must be between 0 and 100")
        return {
            "sequence": cleaned,
            "min_bitscore": params.min_bitscore,
            "min_pident": params.min_pident,
            "min_qcov": params.min_qcov,
        }
    elif ctype == "similar" and not params.ibgc_id:
        raise HttpError(400, "similar criterion requires an ibgc_id")
    return None


def _normalise_combined_criteria(criteria) -> list[dict]:
    """Validate + normalise combined criteria into the dicts the task consumes.

    Enforces unique non-empty ids and a sane criterion count, builds each typed
    params (catching unknown types), and runs per-type validation. Returns a
    list of ``{"id", "type", "params"}`` dicts ready to enqueue.
    """
    from discovery.services.query import CriterionError, build_params

    if not criteria:
        raise HttpError(400, "At least one criterion is required")
    if len(criteria) > _MAX_COMBINED_CRITERIA:
        raise HttpError(400, f"Too many criteria (max {_MAX_COMBINED_CRITERIA})")

    seen: set[str] = set()
    out: list[dict] = []
    for c in criteria:
        cid = (c.id or "").strip()
        if not cid:
            raise HttpError(400, "Each criterion needs a non-empty id")
        if cid in seen:
            raise HttpError(400, f"Duplicate criterion id: {cid!r}")
        seen.add(cid)
        raw_params = c.params or {}
        try:
            params = build_params(c.type, raw_params)
        except CriterionError as exc:
            raise HttpError(exc.status, exc.message) from exc
        normalised = _validate_criterion_params(c.type, params)
        out.append({"id": cid, "type": c.type, "params": normalised or raw_params})
    return out


def _load_combined_result(task_id: str) -> dict:
    """Poll the combined-query task; raise 503 (pending) / 500 (failed).

    A criterion error the task returned (see ``tasks.combined_query``) is raised
    with its own status and message, e.g. 400 for a partial similarity seed. A
    criterion 503 (index not available) becomes 500: 503 here means "poll again".
    """
    from discovery.cache_utils import fetch_job

    res = fetch_job(task_id)
    if res.failed():
        logger.error("Combined query task %s failed: %s", task_id, res.errors)
        raise HttpError(500, "Combined query failed")
    if not res.ready():
        raise HttpError(503, "Combined query still running")
    result = res.result or {}
    if error := result.get("error"):
        status = error["status"]
        raise HttpError(500 if status == 503 else status, error["message"])
    return result


def _criterion_columns(result: dict) -> list[CriterionColumn]:
    return [
        CriterionColumn(
            id=c["id"],
            type=c["type"],
            label=c["label"],
            metrics=[CriterionMetricSchema(**m) for m in c.get("metrics", [])],
        )
        for c in result.get("criteria", [])
    ]


def _combined_scores_map(scores_by_id: dict, ibgc_id: int) -> dict[str, CriterionScore]:
    raw = scores_by_id.get(str(ibgc_id), {})
    return {
        cid: CriterionScore(
            value=p.get("value"),
            pident=p.get("pident"),
            qcoverage=p.get("qcoverage"),
            best_hit_protein_id=p.get("best_hit_protein_id"),
        )
        for cid, p in raw.items()
    }


def _combined_sorted_ids(
    ordered_ids: list[int],
    scores_by_id: dict,
    ibgcs: dict,
    *,
    sort_by: str,
    order: str,
    primary_cid: str | None,
) -> list[int]:
    """Sort the result ids by a ``score:<id>[:metric]`` key or an iBGC column.

    Nulls always sort last (matching the DB roster's ``nulls_last``). An empty
    ``sort_by`` defaults to the primary criterion's value; an unknown key keeps
    the task's primary-best-first order.
    """
    reverse = order != "asc"
    if not sort_by:
        sort_by = f"score:{primary_cid}" if primary_cid else "id"

    if sort_by.startswith("score:"):
        _, _, rest = sort_by.partition(":")
        cid, _, metric = rest.partition(":")
        metric = metric or "value"

        def valuefn(i):
            return scores_by_id.get(str(i), {}).get(cid, {}).get(metric)

    elif sort_by == "size_kb":

        def valuefn(i):
            n = ibgcs.get(i)
            return (n.end_position - n.start_position) if n else None

    elif sort_by in _COMBINED_DB_SORT:
        col = _COMBINED_DB_SORT[sort_by]

        def valuefn(i):
            n = ibgcs.get(i)
            return getattr(n, col, None) if n else None

    else:
        return ordered_ids

    present = [i for i in ordered_ids if valuefn(i) is not None]
    missing = [i for i in ordered_ids if valuefn(i) is None]
    present.sort(key=valuefn, reverse=reverse)
    return present + missing


@router.post(
    "/query/combined/",
    response={202: CombinedQueryAccepted},
    tags=["Query"],
    auth=first_party_gate,
    throttle=search_throttle,
)
def combined_query_endpoint(request, body: CombinedQueryRequest):
    """Dispatch a combined multi-criterion query.

    Accepts a list of scoring ``criteria`` (each with a stable per-instance
    ``id``) plus the standard narrowing ``filters``. The criteria are
    AND-intersected server-side; slow sub-searches (sequence) make this
    always-async. Returns ``202`` with a ``task_id``; poll
    ``GET /query/combined/status/{task_id}/`` (roster) and ``…/scores/``
    (Variables map).
    """
    criteria = _normalise_combined_criteria(body.criteria)
    filters = dict(body.filters) if body.filters else {}

    from discovery.tasks import combined_query

    try:
        result = combined_query.enqueue(criteria, filters)
    except Exception as e:
        logger.error("Failed to dispatch combined query task: %s", e)
        raise HttpError(503, "Search service temporarily unavailable") from e

    return 202, CombinedQueryAccepted(task_id=result.id)


@router.get(
    "/query/combined/status/{task_id}/",
    response=CombinedRosterResponse,
    tags=["Query"],
    auth=first_party_gate,
)
def combined_query_status(
    request,
    task_id: str,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "",
    order: str = "desc",
):
    """Poll a combined query and return a paginated roster with per-criterion columns.

    ``sort_by`` accepts ``score:<criterion_id>`` / ``score:<criterion_id>:<metric>``
    (e.g. a sequence criterion's ``pident``) or an iBGC column (``novelty_score``,
    ``size_kb``, ``bgc_class``, …). Empty sorts by the primary criterion.
    PENDING raises 503 so the client can poll; FAILURE raises 500.
    """
    result = _load_combined_result(task_id)
    columns = _criterion_columns(result)
    ordered_ids = [int(i) for i in result.get("ordered_ids", [])]
    scores_by_id = result.get("scores_by_id", {})
    primary_cid = result["criteria"][0]["id"] if result.get("criteria") else None

    if not ordered_ids:
        return CombinedRosterResponse(
            items=[],
            pagination=PaginationMeta(
                page=1, page_size=page_size, total_count=0, total_pages=0
            ),
            criteria=columns,
        )

    ibgcs = {n.id: n for n in IntegratedBgc.objects.filter(id__in=ordered_ids)}
    sorted_ids = _combined_sorted_ids(
        ordered_ids,
        scores_by_id,
        ibgcs,
        sort_by=sort_by,
        order=order,
        primary_cid=primary_cid,
    )
    total_count = len(sorted_ids)
    pg, ps, tp, offset = paginate(page, page_size, total_count)
    page_ids = sorted_ids[offset : offset + ps]
    facts = ibgc_member_facts(page_ids)

    items = []
    for nid in page_ids:
        n = ibgcs.get(nid)
        if n is None:
            continue
        base = ibgc_to_roster_item(
            n,
            facts[nid],
        )
        items.append(
            CombinedRosterItem(
                **dict(base), scores=_combined_scores_map(scores_by_id, nid)
            )
        )
    return CombinedRosterResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
        criteria=columns,
    )


@router.get(
    "/query/combined/status/{task_id}/scores/",
    response=CombinedScoresResponse,
    tags=["Query"],
    auth=first_party_gate,
)
def combined_query_scores(request, task_id: str):
    """Compact, full (capped) combined-query payload for the Variables map.

    Returns every result id with its per-criterion scores, the criteria column
    descriptors, and an ``ibgc_ids_token`` scoping the result set for the
    scatter / count / roster GET endpoints. PENDING raises 503; FAILURE 500.
    """
    result = _load_combined_result(task_id)
    columns = _criterion_columns(result)
    ordered_ids = [int(i) for i in result.get("ordered_ids", [])]
    scores_by_id = result.get("scores_by_id", {})
    token, _ = cache_ibgc_idset(ordered_ids)
    items = [
        CombinedScoreRow(id=i, scores=_combined_scores_map(scores_by_id, i))
        for i in ordered_ids
    ]
    return CombinedScoresResponse(
        items=items,
        criteria=columns,
        total_matched=result.get("total_matched", len(ordered_ids)),
        capped=result.get("capped", False),
        cap=result.get("cap", DASHBOARD_RESULT_CAP),
        ibgc_ids_token=token,
        warnings=result.get("warnings", []),
    )
