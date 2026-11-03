"""Uniform criterion resolvers for the Discovery query engine.

Every scoring criterion (domain containment, domain architecture, sequence
search, similar-iBGC) is resolved by a function returning a
:class:`CriterionResult` — a mapping of ``iBGC id → score payload`` plus a column
descriptor (:class:`CriterionMetric` list) and pre-cap counters. This is the
single source of truth: the legacy single-criterion endpoints/tasks delegate
here, and the combined multi-criterion query intersects several
``CriterionResult`` score maps under AND semantics.

A score payload is a dict ``{"value": float, ...}``. ``value`` is the criterion's
primary, sortable metric (bitscore, composite similarity, or — for
domain containment — the *fraction of include tokens matched*). Sequence search
additionally carries ``pident`` / ``qcoverage`` / ``best_hit_protein_id``.

Nothing here imports the web layer (Django Ninja). User-facing failures raise
:class:`CriterionError` carrying an HTTP status; the API/task layer translates it.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Mirrors ``api.DASHBOARD_RESULT_CAP`` — the in-memory sort/intersection of a
# combined query needs a hard bound. Kept local so this module stays free of an
# ``api`` import (which would be circular).
RESULT_CAP = 5_000

_VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


# ── Result / column descriptors ──────────────────────────────────────────────


@dataclass(frozen=True)
class CriterionMetric:
    """One sortable column a criterion contributes to the roster / Variables map.

    ``key`` indexes into a row's score payload (``"value"``, ``"pident"``, …).
    ``label`` is the human column header. ``sortable`` gates header-click sort.
    """

    key: str
    label: str
    sortable: bool = True


@dataclass
class CriterionResult:
    """Resolved scores for a single criterion instance.

    ``scores`` maps iBGC id → payload dict (always contains ``"value"``).
    ``total_matched`` is the pre-cap match count; ``capped`` flags that lower
    matches may be hidden by ``RESULT_CAP``. ``metrics`` describes the columns
    this criterion contributes. ``warnings`` carries non-fatal feedback (e.g.
    accessions dropped because they were outside the scoring vocabulary).
    """

    scores: dict[int, dict[str, float | str | None]]
    metrics: list[CriterionMetric]
    total_matched: int
    capped: bool = False
    warnings: list[str] = field(default_factory=list)


class CriterionError(Exception):
    """A user-facing criterion failure carrying an HTTP status for the API layer."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# Column descriptors keyed by criterion type. Sequence contributes three
# columns (the user's "pident, etc."); the rest contribute a single score.
CRITERION_METRICS: dict[str, list[CriterionMetric]] = {
    "domain": [CriterionMetric("value", "Match frac.")],
    "architecture": [CriterionMetric("value", "Arch. similarity")],
    "similar": [CriterionMetric("value", "Similarity")],
    "sequence": [
        CriterionMetric("value", "Bitscore"),
        CriterionMetric("pident", "Identity %"),
        CriterionMetric("qcoverage", "Query cov. %"),
    ],
}


# ── Typed params (decoupled from the Ninja request schemas) ──────────────────


@dataclass
class DomainParams:
    domains_text: str = ""
    logic: str = "and"
    threshold: float = 1.0


@dataclass
class ArchitectureParams:
    architecture: list[str] = field(default_factory=list)
    weight: float = 0.5
    k: int = 100
    threshold: float = 0.25


@dataclass
class SequenceParams:
    sequence: str = ""
    min_bitscore: float = 30.0
    min_pident: float = 70.0
    min_qcov: float = 70.0


@dataclass
class SimilarParams:
    ibgc_id: int = 0
    k: int = 25


_PARAM_TYPES = {
    "domain": DomainParams,
    "architecture": ArchitectureParams,
    "sequence": SequenceParams,
    "similar": SimilarParams,
}


def build_params(ctype: str, raw: dict | object):
    """Build the typed params dataclass for ``ctype`` from a dict or attr-bag.

    Accepts either a plain dict (combined-query request body) or any object with
    matching attributes (a Ninja schema instance), keeping only the fields the
    dataclass declares so unknown keys are ignored rather than raising.
    """
    cls = _PARAM_TYPES.get(ctype)
    if cls is None:
        raise CriterionError(400, f"Unknown criterion type: {ctype!r}")
    fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    if isinstance(raw, dict):
        kwargs = {k: v for k, v in raw.items() if k in fields}
    else:
        kwargs = {k: getattr(raw, k) for k in fields if hasattr(raw, k)}
    return cls(**kwargs)


# ── Domain token helpers (shared with the legacy domain endpoint) ─────────────


def parse_domain_tokens(text: str) -> tuple[list[str], list[str]]:
    """Split free-text domain input into ``(include, exclude)`` token lists.

    Tokens are comma / whitespace separated and upper-cased so pasted input
    is matched case-insensitively against ``domain_acc`` / ``interpro_entry_acc``
    (both stored upper-case). A leading ``-`` or ``!`` marks a token excluded.
    Order-preserving and de-duplicated within each list.
    """
    include: list[str] = []
    exclude: list[str] = []
    for raw in re.split(r"[,\s]+", text or ""):
        tok = raw.strip()
        if not tok:
            continue
        bucket = include
        if tok[0] in "-!":
            bucket = exclude
            tok = tok[1:].strip()
        if not tok:
            continue
        tok = tok.upper()
        if tok not in bucket:
            bucket.append(tok)
    return include, exclude


# ── Domain containment ────────────────────────────────────────────────────────


def resolve_domain(params: DomainParams) -> CriterionResult:
    """Resolve a domain-containment criterion to graded per-iBGC scores.

    Tokens may be InterPro entries or raw signature accessions; both columns are
    matched. ``value`` is the *fraction of distinct include tokens present* in
    the iBGC (``matched / N_include``) so the column sorts meaningfully — strict
    AND yields 1.0 for every hit, partial-AND / OR grade by coverage.

    A token "is present" in an iBGC iff some CDS whose ``cds_range`` overlaps
    the iBGC's ``bgc_range`` on the same contig carries a domain hit matching
    the token (via ``domain_acc`` or ``interpro_entry_acc``). Contig-wide
    presence is *not* sufficient: multiple iBGCs share a contig and their
    ranges are disjoint, so restricting to overlapping CDS is required to
    avoid false positives from unrelated regions of the contig.

    AND keeps iBGCs carrying ``ceil(threshold × N_include)`` distinct include
    tokens; OR keeps any iBGC carrying at least one. Excluded tokens drop an
    iBGC if any overlapping CDS carries them.
    """
    from django.db import connection

    include, exclude = parse_domain_tokens(params.domains_text)
    metrics = CRITERION_METRICS["domain"]
    if not include:
        return CriterionResult(scores={}, metrics=metrics, total_matched=0)

    n_include = len(include)

    # Per-iBGC count of distinct include tokens present within the iBGC's
    # bgc_range. A token counts once even if matched by both columns or by
    # multiple domain hits.
    include_sql = """
        WITH tokens(tok) AS (SELECT unnest(%s::text[])),
             matches AS (
                 SELECT DISTINCT i.id AS ibgc_id, t.tok
                 FROM discovery_ibgc i
                 JOIN discovery_cds c
                   ON c.contig_id = i.contig_id
                  AND c.cds_range && i.bgc_range
                 JOIN discovery_domain_hit d
                   ON d.cds_id = c.id
                 JOIN tokens t
                   ON t.tok = d.domain_acc
                   OR t.tok = d.interpro_entry_acc
             )
        SELECT ibgc_id, COUNT(*) AS n_matched
        FROM matches
        GROUP BY ibgc_id
    """
    with connection.cursor() as cur:
        cur.execute(include_sql, [include])
        hit_counts = {int(iid): int(n) for iid, n in cur.fetchall()}

    if (params.logic or "and") == "and":
        threshold = max(0.0, min(1.0, params.threshold))
        need = max(1, math.ceil(threshold * n_include))
    else:
        need = 1
    matched = {nid: c for nid, c in hit_counts.items() if c >= need}

    if exclude and matched:
        exclude_sql = """
            SELECT DISTINCT i.id
            FROM discovery_ibgc i
            JOIN discovery_cds c
              ON c.contig_id = i.contig_id
             AND c.cds_range && i.bgc_range
            JOIN discovery_domain_hit d
              ON d.cds_id = c.id
             AND (d.domain_acc = ANY(%s) OR d.interpro_entry_acc = ANY(%s))
            WHERE i.id = ANY(%s)
        """
        with connection.cursor() as cur:
            cur.execute(exclude_sql, [exclude, exclude, list(matched)])
            excluded_ids = {int(r[0]) for r in cur.fetchall()}
        matched = {nid: c for nid, c in matched.items() if nid not in excluded_ids}

    scores = {
        nid: {"value": round(c / n_include, 4)} for nid, c in matched.items()
    }
    return CriterionResult(
        scores=scores, metrics=metrics, total_matched=len(scores)
    )


# ── Domain architecture (composite similarity) ────────────────────────────────


def architecture_top(params: ArchitectureParams) -> tuple[list[int], list[float]]:
    """Resolve an architecture query to ``(top_ids, top_scores)`` (best-first).

    Scores ``weight·S(domain set) + (1-weight)·S(adjacency pairs)`` against the
    cached primary-iBGC matrices of the latest ClusteringRun, ``S`` being the
    run's similarity metric (weighted cosine, or Dice on older runs). ``k`` is bounded
    by :data:`RESULT_CAP`. Raises :class:`CriterionError` when the input is empty,
    the scoring cache is unavailable, or no accession matched the vocabulary.
    """
    from discovery.services.clustering.architecture_search import (
        architecture_search,
        normalize_architecture_input,
    )
    from discovery.services.clustering.similarity_on_demand import (
        cache_key_architecture,
        cache_similarity_query,
        get_active_scoring_cache,
    )

    accs = normalize_architecture_input(params.architecture)
    if not accs:
        raise CriterionError(400, "architecture must contain at least one accession")

    try:
        scoring = get_active_scoring_cache()
    except FileNotFoundError:
        # Log the path-bearing detail server-side; never leak it to the client.
        log.exception("Scoring cache unavailable for architecture query")
        raise CriterionError(503, "Similarity index is not available yet")

    k = max(1, min(int(params.k), RESULT_CAP))

    def _compute():
        result = architecture_search(accs, weight=params.weight, k=k, cache=scoring)
        return {"ids": result["ibgc_ids"], "scores": result["scores"]}

    cache_key = cache_key_architecture(
        sha256=scoring.sha256,
        accs_ordered=accs,
        weight=float(params.weight),
        k=k,
    )
    cached = cache_similarity_query(cache_key=cache_key, compute=_compute)
    top_ids: list[int] = list(cached["ids"])
    top_scores: list[float] = [float(s) for s in cached["scores"]]
    if not top_ids:
        raise CriterionError(
            400,
            "No supplied accession matched the scoring cache vocabulary — "
            "check the input or rerun clustering against a broader source set.",
        )
    # Post-filter by the minimum composite score. Applied after the cache
    # (keyed on accs/weight/k only) so the threshold stays a cheap, cache-friendly
    # cut. May legitimately return nothing — not an error.
    threshold = float(params.threshold or 0.0)
    if threshold > 0:
        filtered = [(i, s) for i, s in zip(top_ids, top_scores) if s >= threshold]
        top_ids = [i for i, _ in filtered]
        top_scores = [s for _, s in filtered]
    return top_ids, top_scores


def resolve_architecture(params: ArchitectureParams) -> CriterionResult:
    """Resolve a domain-architecture criterion to per-iBGC composite scores."""
    top_ids, top_scores = architecture_top(params)
    scores = {
        nid: {"value": round(s, 4)} for nid, s in zip(top_ids, top_scores)
    }
    return CriterionResult(
        scores=scores,
        metrics=CRITERION_METRICS["architecture"],
        total_matched=len(scores),
    )


# ── Similar-iBGC (composite similarity to a seed) ─────────────────────────────


def similar_top(params: SimilarParams) -> tuple[list[int], list[float]]:
    """Resolve a similar-iBGC query to ``(top_ids, top_scores)`` (best-first).

    Composite similarity of the seed iBGC against all other primaries of the active
    ClusteringRun, computed on demand and cached for 24h keyed on the run sha256.
    Raises :class:`CriterionError` if the cache is missing or the seed is not a
    primary in the latest run.
    """
    import numpy as np

    from discovery.services.clustering.similarity_on_demand import (
        cache_key_find_similar,
        cache_similarity_query,
        get_active_scoring_cache,
        score_against_all,
        top_k,
    )

    try:
        scoring = get_active_scoring_cache()
    except FileNotFoundError:
        log.exception("Scoring cache unavailable for similar-iBGC query")
        raise CriterionError(503, "Similarity index is not available yet")

    row_ix = scoring.row_index_for(params.ibgc_id)
    if row_ix is None:
        raise CriterionError(
            400,
            "Seed iBGC is not a primary in the latest ClusteringRun — "
            "similar-iBGC requires a primary seed in v1.",
        )

    k = max(1, min(int(params.k), 500))

    def _compute():
        q_dom = scoring.M_domains.getrow(row_ix)
        q_pair = scoring.M_pairs.getrow(row_ix)
        scores = score_against_all(q_dom, q_pair, scoring)
        scores[row_ix] = -np.inf  # exclude self
        rows, vals = top_k(scores, k)
        ids = [int(scoring.ibgc_ids[r]) for r in rows]
        return {"ids": ids, "scores": vals}

    cache_key = cache_key_find_similar(
        sha256=scoring.sha256, ibgc_id=params.ibgc_id, k=k
    )
    cached = cache_similarity_query(cache_key=cache_key, compute=_compute)
    top_ids: list[int] = list(cached["ids"])
    top_scores: list[float] = [float(v) for v in cached["scores"]]
    return top_ids, top_scores


def resolve_similar(params: SimilarParams) -> CriterionResult:
    """Resolve a similar-iBGC criterion to per-iBGC composite scores."""
    top_ids, top_scores = similar_top(params)
    scores = {
        nid: {"value": round(s, 4)} for nid, s in zip(top_ids, top_scores)
    }
    return CriterionResult(
        scores=scores,
        metrics=CRITERION_METRICS["similar"],
        total_matched=len(scores),
    )


# ── Sequence search (phmmer) ──────────────────────────────────────────────────


def run_sequence_search(
    sequence: str,
    min_bitscore: float = 30.0,
    min_pident: float = 70.0,
    min_qcov: float = 70.0,
) -> dict[int, dict[str, float | str]]:
    """Run phmmer for a query protein and return matching iBGCs.

    Returns ``{ibgc_id: {"bitscore": ..., "pident": ..., "qcoverage": ...,
    "protein_id": ...}}`` from the highest-bitscore matched protein within each
    iBGC. A CDS belongs to an iBGC by genomic-range overlap on its contig (iBGCs
    are disjoint within a cBGC, so each CDS overlaps at most one iBGC).

    Raises ``IndexNotBuiltError`` if the phmmer index is missing, so the failure
    is visible to the operator rather than silently returning an empty roster.
    """
    from discovery.services.protein_search import phmmer_search
    from discovery.services.protein_search.index import IndexNotBuiltError
    from django.conf import settings
    from django.db import connection

    seq = sequence.strip().upper()
    if not seq:
        log.warning("Empty sequence passed to run_sequence_search")
        return {}
    if len(seq) > 5000:
        log.warning("Sequence too long (%d AA), max 5000", len(seq))
        return {}
    invalid = set(seq) - _VALID_AA
    if invalid:
        log.warning("Invalid amino acid characters: %s", invalid)
        return {}

    try:
        sha256_metrics = phmmer_search(
            seq,
            min_bitscore=min_bitscore,
            min_pident=min_pident,
            min_qcov=min_qcov,
            cpus=getattr(settings, "PROTEIN_SEARCH_CPUS", 1),
        )
    except IndexNotBuiltError:
        log.error(
            "Protein search index not built; "
            "run `python manage.py build_protein_search_index --rebuild`."
        )
        raise

    if not sha256_metrics:
        log.info(
            "Sequence query: no protein hits (min_bitscore=%g, min_pident=%g, min_qcov=%g)",
            min_bitscore,
            min_pident,
            min_qcov,
        )
        return {}

    # Join matched CDS to their owning iBGC via contig + range overlap.
    sha_list = list(sha256_metrics.keys())
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT i.id, c.protein_sha256, c.protein_id_str
            FROM discovery_cds c
            JOIN discovery_ibgc i
              ON i.contig_id = c.contig_id
             AND i.bgc_range && c.cds_range
            WHERE c.protein_sha256 = ANY(%s::text[])
            """,
            [sha_list],
        )
        rows = cur.fetchall()

    ibgc_best: dict[int, tuple] = {}
    for ibgc_id, sha256, protein_id in rows:
        m = sha256_metrics[sha256]
        existing = ibgc_best.get(ibgc_id)
        if existing is None or m.bitscore > existing[0].bitscore:
            ibgc_best[ibgc_id] = (m, protein_id)

    ibgc_scores: dict[int, dict[str, float | str]] = {
        ibgc_id: {
            "bitscore": float(m.bitscore),
            "pident": float(m.pident),
            "qcoverage": float(m.qcoverage),
            "protein_id": protein_id,
        }
        for ibgc_id, (m, protein_id) in ibgc_best.items()
    }

    log.info(
        "Sequence query: len=%d min_bitscore=%g min_pident=%g min_qcov=%g protein_hits=%d ibgc_matches=%d",
        len(seq),
        min_bitscore,
        min_pident,
        min_qcov,
        len(sha256_metrics),
        len(ibgc_scores),
    )
    return ibgc_scores


def resolve_sequence(params: SequenceParams) -> CriterionResult:
    """Resolve a sequence-search criterion to bitscore/pident/qcoverage columns."""
    raw = run_sequence_search(
        params.sequence,
        min_bitscore=params.min_bitscore,
        min_pident=params.min_pident,
        min_qcov=params.min_qcov,
    )
    scores: dict[int, dict[str, float | str | None]] = {
        nid: {
            "value": v["bitscore"],
            "pident": v["pident"],
            "qcoverage": v["qcoverage"],
            "best_hit_protein_id": v["protein_id"],
        }
        for nid, v in raw.items()
    }
    return CriterionResult(
        scores=scores,
        metrics=CRITERION_METRICS["sequence"],
        total_matched=len(scores),
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────


_RESOLVERS = {
    "domain": resolve_domain,
    "architecture": resolve_architecture,
    "sequence": resolve_sequence,
    "similar": resolve_similar,
}


def resolve_criterion(ctype: str, params: dict | object) -> CriterionResult:
    """Resolve a criterion by type, building its typed params from ``params``.

    ``params`` may be a dict (combined-query body) or a Ninja schema instance.
    Raises :class:`CriterionError` for an unknown type.
    """
    resolver = _RESOLVERS.get(ctype)
    if resolver is None:
        raise CriterionError(400, f"Unknown criterion type: {ctype!r}")
    typed = params if isinstance(params, _PARAM_TYPES[ctype]) else build_params(ctype, params)
    return resolver(typed)
