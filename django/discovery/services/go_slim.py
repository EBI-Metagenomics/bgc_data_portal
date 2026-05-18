"""Pfam → GO slim mapping, shared between ingestion and asset projection.

Single source of truth for the rule ``load_pfam_go_slim`` previously embedded:
pick the first ``molecular_function`` term per Pfam accession, capitalise it,
dedup. The mapping is loaded once per process and cached in memory.

Callers should populate ``BgcDomain.go_slim`` (or its asset-side equivalent)
inline at write time using :func:`go_slim_for`. The
``load_pfam_go_slim`` management command remains for backfilling existing
rows after a mapping refresh.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

log = logging.getLogger(__name__)

_DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "management",
    "commands",
    "data",
    "pfam2goSlim.json",
)


@lru_cache(maxsize=1)
def _pfam_to_slim() -> dict[str, str]:
    """Return ``{pfam_acc: first molecular_function GO slim term (capitalised)}``.

    Missing or malformed file → empty mapping (logged once); callers then get
    ``""`` from :func:`go_slim_for` and the CDS just renders without colour.
    """
    try:
        with open(_DATA_FILE) as f:
            raw = json.load(f)
    except FileNotFoundError:
        log.warning("pfam2goSlim.json not found at %s — GO slims will be empty", _DATA_FILE)
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Failed to load pfam2goSlim.json (%s) — GO slims will be empty", exc)
        return {}

    result: dict[str, str] = {}
    for pfam_acc, go_slims in raw.items():
        seen: list[str] = []
        for desc, go_type in go_slims:
            if go_type != "molecular_function":
                continue
            term = desc.capitalize()
            if term not in seen:
                seen.append(term)
        if seen:
            result[pfam_acc] = seen[0]
    return result


def go_slim_for(domain_acc: str) -> str:
    """Return the GO slim term for ``domain_acc`` (or ``""`` if unmapped)."""
    if not domain_acc:
        return ""
    return _pfam_to_slim().get(domain_acc, "")
