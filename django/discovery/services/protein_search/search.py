"""phmmer query against the on-disk protein DB."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from pyhmmer.easel import Alphabet, DigitalSequence, DigitalSequenceBlock, TextSequence
from pyhmmer.hmmer import phmmer

from .index import _split_block, protein_search_index

log = logging.getLogger(__name__)

QUERY_NAME = b"query"

# Permissive E-value passed to phmmer itself. We do not filter on e-value;
# the real cutoffs are applied below via bitscore / %identity / query coverage.
_PHMMER_E = 10.0


@dataclass(slots=True, frozen=True)
class ProteinHitMetrics:
    """Per-target-protein metrics extracted from a phmmer hit.

    ``pident`` and ``qcoverage`` are expressed as percentages in [0, 100].
    They are aggregated across **all domains of the hit** — coverage is the
    fraction of the query covered by the union of non-overlapping domain
    envelopes; identity is the identity-count-weighted average across those
    same domain alignments.
    """

    bitscore: float
    pident: float
    qcoverage: float


def _union_length(intervals: list[tuple[int, int]]) -> int:
    """Length of the union of inclusive 1-indexed integer intervals."""
    if not intervals:
        return 0
    sorted_iv = sorted(intervals)
    total = 0
    cur_lo, cur_hi = sorted_iv[0]
    for lo, hi in sorted_iv[1:]:
        if lo > cur_hi + 1:
            total += cur_hi - cur_lo + 1
            cur_lo, cur_hi = lo, hi
        else:
            if hi > cur_hi:
                cur_hi = hi
    total += cur_hi - cur_lo + 1
    return total


def _compute_hit_metrics(hit, query_len: int) -> ProteinHitMetrics | None:
    """Aggregate domain-level alignment stats into a single hit-level metrics
    record. Returns ``None`` if the hit has no usable alignments.
    """
    intervals: list[tuple[int, int]] = []
    sum_identities = 0
    sum_aligned = 0
    for dom in hit.domains:
        aln = dom.alignment
        if aln is None:
            continue
        # For phmmer, the query is internally wrapped as an HMM, so
        # hmm_from / hmm_to are the query coordinates (1-indexed, inclusive).
        hmm_from = int(aln.hmm_from)
        hmm_to = int(aln.hmm_to)
        if hmm_to < hmm_from:
            continue
        intervals.append((hmm_from, hmm_to))

        identity_str = aln.identity_sequence or ""
        # pyhmmer convention for the midline:
        #   letter  → identical residue
        #   '+'     → conservative substitution (similar, but not identical)
        #   ' '     → mismatch / gap
        sum_identities += sum(1 for c in identity_str if c.isalpha())
        sum_aligned += len(identity_str)

    if not intervals or query_len <= 0 or sum_aligned == 0:
        return None

    pident = (sum_identities / sum_aligned) * 100.0
    qcoverage = (_union_length(intervals) / query_len) * 100.0
    return ProteinHitMetrics(
        bitscore=float(hit.score),
        pident=pident,
        qcoverage=qcoverage,
    )


def _scan_block(
    query_seq: DigitalSequence,
    target_block: DigitalSequenceBlock,
    query_len: int,
    *,
    min_bitscore: float,
    min_pident: float,
    min_qcov: float,
) -> dict[str, ProteinHitMetrics]:
    """Run phmmer for a single query against one target block and return the
    passing hits as ``{sha256: ProteinHitMetrics}``. Used per-chunk so the
    work fans out across threads (pyhmmer releases the GIL during the search).
    """
    results: dict[str, ProteinHitMetrics] = {}
    # phmmer yields one TopHits per query; we always pass a single query so this
    # loop iterates exactly once. cpus=1 here: parallelism is across blocks, not
    # within a single phmmer call (which only parallelises across queries).
    for top_hits in phmmer((query_seq,), target_block, cpus=1, E=_PHMMER_E):
        for hit in top_hits:
            if float(hit.score) < min_bitscore:
                continue
            metrics = _compute_hit_metrics(hit, query_len)
            if metrics is None:
                continue
            if metrics.pident < min_pident or metrics.qcoverage < min_qcov:
                continue
            sha256 = hit.name.decode("ascii")
            existing = results.get(sha256)
            if existing is None or metrics.bitscore > existing.bitscore:
                results[sha256] = metrics
    return results


def phmmer_search(
    sequence: str,
    *,
    min_bitscore: float = 30.0,
    min_pident: float = 70.0,
    min_qcov: float = 70.0,
    cpus: int = 1,
    block: DigitalSequenceBlock | None = None,
) -> dict[str, ProteinHitMetrics]:
    """Run phmmer with ``sequence`` against the on-disk protein DB and return
    per-target metrics for hits that pass all three thresholds.

    Parameters
    ----------
    sequence
        Amino-acid query (single protein).
    min_bitscore
        Drop hits whose full-sequence bit score is below this. Default 30
        (HMMER's conventional weak-significance cut).
    min_pident
        Drop hits whose aggregate percent identity (across all aligned
        domains) is below this. 0–100.
    min_qcov
        Drop hits whose query coverage (union of domain envelopes / query
        length) is below this. 0–100.
    cpus
        Number of threads to split the scan across. The target DB is divided
        into ``cpus`` slices, each scanned on its own thread; results are
        merged. Default 1 (no split). One phmmer search at a time is assumed
        (Celery ``--concurrency=1``), so these threads have the pod to
        themselves.
    block
        Override the target block (used by tests). When omitted, loads the
        shared worker-local index. When passed, it is split on the fly; the
        index path uses the singleton's cached split.

    Returns
    -------
    ``{sha256: ProteinHitMetrics}`` — for each matched protein, the metrics
    of the hit. If a target appears more than once (it should not, since the
    FASTA is deduplicated by sha256), the higher-bitscore record wins.
    """
    seq = sequence.strip().upper()
    query_len = len(seq)
    alphabet = Alphabet.amino()

    # Target slices for the (optionally parallel) scan. Prefer the index's
    # cached split; fall back to splitting a test-supplied block on the fly.
    if block is not None:
        target_blocks = _split_block(block, cpus)
    elif cpus > 1:
        target_blocks = protein_search_index.get_blocks(cpus)
    else:
        target_blocks = [protein_search_index.get_block()]

    query_seq = TextSequence(name=QUERY_NAME, sequence=seq).digitize(alphabet)

    def scan(b: DigitalSequenceBlock) -> dict[str, ProteinHitMetrics]:
        return _scan_block(
            query_seq,
            b,
            query_len,
            min_bitscore=min_bitscore,
            min_pident=min_pident,
            min_qcov=min_qcov,
        )

    if len(target_blocks) == 1:
        partials = [scan(target_blocks[0])]
    else:
        with ThreadPoolExecutor(max_workers=len(target_blocks)) as ex:
            partials = list(ex.map(scan, target_blocks))

    # Merge per-chunk results, keeping the higher-bitscore record per sha256.
    results: dict[str, ProteinHitMetrics] = {}
    for partial in partials:
        for sha256, metrics in partial.items():
            existing = results.get(sha256)
            if existing is None or metrics.bitscore > existing.bitscore:
                results[sha256] = metrics

    log.info(
        "phmmer_search: query_len=%d min_bitscore=%g min_pident=%g min_qcov=%g hits=%d",
        query_len,
        min_bitscore,
        min_pident,
        min_qcov,
        len(results),
    )
    return results
