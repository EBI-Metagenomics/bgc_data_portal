"""phmmer query against the on-disk protein DB."""

from __future__ import annotations

import logging
from typing import Optional

from pyhmmer.easel import Alphabet, DigitalSequenceBlock, TextSequence
from pyhmmer.hmmer import phmmer

from .index import protein_search_index

log = logging.getLogger(__name__)

QUERY_NAME = b"query"


def phmmer_search(
    sequence: str,
    max_evalue: float = 1e-5,
    cpus: int = 1,
    *,
    block: Optional[DigitalSequenceBlock] = None,
) -> dict[str, float]:
    """Run phmmer with ``sequence`` against the on-disk protein DB.

    Parameters
    ----------
    sequence
        Amino-acid query (single protein).
    max_evalue
        Drop hits with E-value greater than this. Maps to phmmer's ``E`` arg.
    cpus
        Worker threads. Default 1 to match ``--concurrency=1``.
    block
        Override the target block (used by tests). When omitted, loads the
        shared worker-local index.

    Returns
    -------
    ``{sha256: best_evalue}`` — the best (smallest) E-value among phmmer hits
    matching each protein sha256.
    """
    alphabet = Alphabet.amino()
    target_block = block if block is not None else protein_search_index.get_block()

    query_seq = (
        TextSequence(name=QUERY_NAME, sequence=sequence.strip().upper())
        .digitize(alphabet)
    )

    results: dict[str, float] = {}
    # phmmer yields one TopHits per query; we always pass a single query so this
    # loop iterates exactly once.
    for top_hits in phmmer(
        (query_seq,),
        target_block,
        cpus=cpus,
        E=max_evalue,
    ):
        for hit in top_hits:
            if hit.evalue > max_evalue:
                continue
            sha256 = hit.name.decode("ascii")
            existing = results.get(sha256)
            if existing is None or hit.evalue < existing:
                results[sha256] = float(hit.evalue)

    log.info(
        "phmmer_search: query_len=%d max_evalue=%g hits=%d",
        len(sequence), max_evalue, len(results),
    )
    return results
