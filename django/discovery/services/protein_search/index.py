"""Worker-local cache of the on-disk protein DB.

The DB lives at ``settings.PROTEIN_SEARCH_INDEX_DIR/proteins.faa``. Each Celery
worker process loads it lazily on first use into a ``DigitalSequenceBlock`` and
keeps it resident. A ``VERSION`` file next to the FASTA is consulted at every
search call; when the stamp changes, the worker reloads.

Workers should run ``--concurrency=1`` so one block lives per pod; scaling is
done via replicas.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from pyhmmer.easel import Alphabet, DigitalSequenceBlock, SequenceFile

from .build import IndexPaths, index_paths, read_version

log = logging.getLogger(__name__)


class IndexNotBuiltError(RuntimeError):
    """Raised when callers try to search before the FASTA has been built."""


class ProteinSearchIndex:
    """Singleton-style holder for the worker-local DigitalSequenceBlock.

    Threadsafe — load and version-check are guarded by an RLock. The block
    itself is not mutated after load.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._paths: Optional[IndexPaths] = None
        self._block: Optional[DigitalSequenceBlock] = None
        self._loaded_version: int = -1

    def _resolve_paths(self) -> IndexPaths:
        if self._paths is None:
            self._paths = index_paths()
        return self._paths

    def reset(self) -> None:
        """Force the next get_block() to reload from disk. For tests + admin tools."""
        with self._lock:
            self._block = None
            self._loaded_version = -1
            self._paths = None

    def current_version(self) -> int:
        """Return the on-disk VERSION stamp (does not load the block)."""
        return read_version(self._resolve_paths())

    def loaded_version(self) -> int:
        return self._loaded_version

    def get_block(self) -> DigitalSequenceBlock:
        """Return a loaded ``DigitalSequenceBlock``, reloading if VERSION changed.

        Raises :class:`IndexNotBuiltError` if no FASTA exists yet.
        """
        paths = self._resolve_paths()
        disk_version = read_version(paths)

        # Fast path — already loaded and version unchanged.
        if self._block is not None and disk_version == self._loaded_version:
            return self._block

        with self._lock:
            # Re-check inside the lock.
            disk_version = read_version(paths)
            if self._block is not None and disk_version == self._loaded_version:
                return self._block

            if not paths.fasta.exists():
                raise IndexNotBuiltError(
                    f"Protein search index not built at {paths.fasta}. "
                    "Run `python manage.py build_protein_search_index --rebuild`."
                )

            t0 = time.perf_counter()
            alphabet = Alphabet.amino()
            with SequenceFile(
                str(paths.fasta),
                format="fasta",
                digital=True,
                alphabet=alphabet,
            ) as sf:
                block = sf.read_block()
            elapsed = time.perf_counter() - t0

            log.info(
                "protein_search loaded %d proteins from %s in %.1fs (version=%d)",
                len(block), paths.fasta, elapsed, disk_version,
            )
            self._block = block
            self._loaded_version = disk_version
            return block


# Process-wide singleton used by the Celery search task.
protein_search_index = ProteinSearchIndex()
