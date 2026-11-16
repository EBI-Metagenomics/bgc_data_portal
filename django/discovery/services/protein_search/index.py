"""Streaming reader for the on-disk protein DB.

The DB lives at ``settings.PROTEIN_SEARCH_INDEX_DIR/proteins.faa``. Each search
reads it in fixed-size blocks instead of keeping it resident: a resident block of
the full index (5.04 M proteins, 2 GB FASTA in 2026-11) holds ~5.3 GiB per worker
process, while streaming peaks at a few blocks. Every search sees the FASTA as it
is on disk, so an index rebuild or append needs no reload step.
"""

from __future__ import annotations

from collections.abc import Iterator
from os import PathLike

from pyhmmer.easel import Alphabet, DigitalSequenceBlock, SequenceFile

from .build import index_paths

# Sequences per streamed block. ~100 MB of digitised sequences at the 2026-11
# index's mean length; small enough that a few blocks in flight stay well under
# 1 GiB, large enough that per-block phmmer setup is negligible.
DEFAULT_BLOCK_SIZE = 100_000


class IndexNotBuiltError(RuntimeError):
    """Raised when callers try to search before the FASTA has been built."""


def iter_index_blocks(
    block_size: int = DEFAULT_BLOCK_SIZE,
    base_dir: str | PathLike | None = None,
) -> Iterator[DigitalSequenceBlock]:
    """Yield the protein DB as consecutive ``DigitalSequenceBlock``s of at most
    ``block_size`` sequences, in file order.

    Raises :class:`IndexNotBuiltError` (on the first ``next()``) if no FASTA
    exists yet.
    """
    paths = index_paths(base_dir)
    if not paths.fasta.exists():
        raise IndexNotBuiltError(
            f"Protein search index not built at {paths.fasta}. "
            "Run `python manage.py build_protein_search_index --rebuild`."
        )
    with SequenceFile(
        str(paths.fasta),
        format="fasta",
        digital=True,
        alphabet=Alphabet.amino(),
    ) as sf:
        while True:
            block = sf.read_block(sequences=block_size)
            if not block:
                return
            yield block


def _split_block(
    block: DigitalSequenceBlock, n_chunks: int
) -> list[DigitalSequenceBlock]:
    """Split ``block`` into at most ``n_chunks`` contiguous sub-blocks.

    Returns ``[block]`` unchanged when splitting would be pointless (≤1 chunk
    or ≤1 sequence). Sub-blocks share the parent's sequences by reference.
    Used when a caller passes an in-memory block (tests) instead of the index.
    """
    n = len(block)
    if n_chunks <= 1 or n <= 1:
        return [block]
    seqs = list(block)
    size = (n + n_chunks - 1) // n_chunks
    return [
        DigitalSequenceBlock(block.alphabet, seqs[i : i + size])
        for i in range(0, n, size)
    ]
