"""Per-feature weights for the ``cosine_idf_enrich`` similarity metric (ADR 0003).

``w = idf ** idf_exponent × enrich`` per column of the domain and adjacency-pair
matrices (``idf_exponent`` 0.5 by default since ADR 0003 Amendment 1, stored on
the run):

* ``idf`` — recomputed for every clustering run over its clusterable iBGCs,
  document frequency counted once per species (``DashboardContig.taxonomy_path``;
  a blank path is one ``"NA"`` group).
* ``enrich`` — looked up in a frozen :class:`~discovery.models.DomainEnrichment`
  version; labels absent from it weigh 0.5. A pair's enrichment is the
  geometric mean of its two domains'.

The maths lives in :mod:`common_core.clustering.weights` (shared with the
HPC ``bgc-cluster`` job); this module only gathers the inputs from the DB and
persists the result next to the run, so every consumer of a run (Find
similar, architecture search, projection, uploads) uses exactly its weights.
IDF is never recomputed for an existing run — the corpus may have changed.

Heavy imports (numpy) are deferred inside the function bodies.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import scipy.sparse as sp

log = logging.getLogger(__name__)

MISSING_TAXONOMY_GROUP = "NA"

# Under <CLUSTERING_ARTIFACTS_DIR>/<sha[:12]>/ — the run's source of truth for
# its weights. The scoring cache carries a copy aligned to its own vocab.
RUN_WEIGHTS_SUBDIR = "weights"
DOMAIN_WEIGHTS_FILE = "domain_weights.npy"
PAIR_WEIGHTS_FILE = "pair_weights.npy"
DOMAIN_ACCS_FILE = "domain_accs.npy"
PAIR_VOCAB_FILE = "pair_vocab.npy"


@dataclass
class RunWeights:
    """Weight vectors and the vocabularies they are aligned to."""

    domain_weights: np.ndarray
    pair_weights: np.ndarray
    domain_accs: np.ndarray
    pair_vocab: np.ndarray


def ibgc_taxonomy_groups(ibgc_ids: Sequence[int]) -> np.ndarray:
    """Species key (``taxonomy_path``) per iBGC, aligned to ``ibgc_ids``."""
    import numpy as np

    from discovery.models import IntegratedBgc

    ids = [int(x) for x in ibgc_ids]
    paths = dict(
        IntegratedBgc.objects.filter(id__in=ids).values_list(
            "id", "contig__taxonomy_path"
        )
    )
    groups = np.asarray(
        [(paths.get(i) or "").strip() or MISSING_TAXONOMY_GROUP for i in ids],
        dtype=object,
    )
    n_missing = int((groups == MISSING_TAXONOMY_GROUP).sum())
    log.info(
        "ibgc_taxonomy_groups: %d iBGCs, %d species groups, %d without taxonomy",
        len(ids),
        len(set(groups.tolist())),
        n_missing,
    )
    return groups


def load_enrichment_table(version: str, *, vocab: str) -> dict[str, float]:
    """``label → weight`` for one ``DomainEnrichment`` version.

    Raises ``ValueError`` when the version doesn't exist or was learned on a
    different label vocabulary than ``vocab`` (its labels would not line up).
    """
    from discovery.models import DomainEnrichment

    qs = DomainEnrichment.objects.filter(version=version)
    vocabs = set(qs.values_list("vocab", flat=True).distinct())
    if not vocabs:
        raise ValueError(
            f"DomainEnrichment version {version!r} has no rows — build it with "
            "`manage.py build_domain_enrichment` first"
        )
    if vocabs != {vocab}:
        raise ValueError(
            f"DomainEnrichment version {version!r} was learned on vocab "
            f"{sorted(vocabs)}, but the run uses {vocab!r}"
        )
    return dict(qs.values_list("label", "weight"))


def compute_run_weights(
    *,
    M_domains: sp.csr_matrix,
    M_pairs: sp.csr_matrix,
    domain_accs: np.ndarray,
    pair_vocab: np.ndarray,
    ibgc_ids: np.ndarray,
    enrichment_version: str,
    domain_vocab: str,
    idf_exponent: float = 1.0,
) -> RunWeights:
    """``idf ** idf_exponent`` over the run's clusterable rows × enrichment table."""
    from common_core.clustering import weights as W

    groups = ibgc_taxonomy_groups(ibgc_ids.tolist())
    enrich_dom = W.enrichment_vector(
        domain_accs.tolist(),
        load_enrichment_table(enrichment_version, vocab=domain_vocab),
    )
    enrich_pair = W.pair_enrichment(
        pair_vocab.tolist(), domain_accs.tolist(), enrich_dom
    )
    w_dom = W.combine(
        W.idf_weights(M_domains, groups), enrich_dom, idf_exponent=idf_exponent
    )
    w_pair = W.combine(
        W.idf_weights(M_pairs, groups), enrich_pair, idf_exponent=idf_exponent
    )
    log.info(
        "compute_run_weights: enrichment=%s idf_exponent=%g domains=%d "
        "(%d unknown to the table) pairs=%d",
        enrichment_version,
        idf_exponent,
        len(w_dom),
        int((enrich_dom == W.UNKNOWN_ENRICH).sum()),
        len(w_pair),
    )
    return RunWeights(
        domain_weights=w_dom,
        pair_weights=w_pair,
        domain_accs=domain_accs,
        pair_vocab=pair_vocab,
    )


def persist_run_weights(artifacts_dir: Path, weights: RunWeights) -> Path:
    """Write ``weights`` under ``<artifacts_dir>/weights/``; return that dir."""
    import numpy as np

    out = Path(artifacts_dir) / RUN_WEIGHTS_SUBDIR
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / DOMAIN_WEIGHTS_FILE, np.asarray(weights.domain_weights, np.float32))
    np.save(out / PAIR_WEIGHTS_FILE, np.asarray(weights.pair_weights, np.float32))
    np.save(out / DOMAIN_ACCS_FILE, np.asarray(weights.domain_accs, dtype=object))
    np.save(out / PAIR_VOCAB_FILE, np.asarray(weights.pair_vocab, dtype=object))
    log.info("Wrote run weights to %s", out)
    return out


def load_run_weights(artifacts_dir: Path) -> RunWeights | None:
    """Read the weights persisted for a run, or ``None`` (Dice runs have none)."""
    import numpy as np

    d = Path(artifacts_dir) / RUN_WEIGHTS_SUBDIR
    if not (d / DOMAIN_WEIGHTS_FILE).exists():
        return None
    return RunWeights(
        domain_weights=np.load(d / DOMAIN_WEIGHTS_FILE),
        pair_weights=np.load(d / PAIR_WEIGHTS_FILE),
        domain_accs=np.load(d / DOMAIN_ACCS_FILE, allow_pickle=True),
        pair_vocab=np.load(d / PAIR_VOCAB_FILE, allow_pickle=True),
    )
