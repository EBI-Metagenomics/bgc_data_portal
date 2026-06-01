"""Legacy mgnify_bgcs HMMER-based BGC search.

Embedding/cosine search has been removed; the Discovery Dashboard now serves
all protein similarity queries via discovery.services.protein_search (phmmer
against an on-disk reference DB). The functions below back the legacy
``/search/`` form and are kept HMMER-only.
"""

from __future__ import annotations

from typing import Dict
from django.conf import settings
from Bio.SeqRecord import SeqRecord

from ..models import Bgc

from ..utils.helpers import sorensen_dice
from .hmmer_utils import (
    global_bgc_sequence_block,
    global_protein_sequence_block,
    create_block_from_tuples,
    iter_protein_tuples_from_bgcs,
)

from pyhmmer.hmmer import phmmer, nhmmer

import logging

log = logging.getLogger(__name__)
numeric_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
log.setLevel(numeric_level)


# --------------------------------------------------------------
# BGC-level sequence search (HMMER/pairwise) -------------------
# --------------------------------------------------------------
def _bgc_hmmer_search(record: SeqRecord, threshold: float) -> Dict[int, float]:
    similarity_results: Dict[int, float] = {}
    seq_query = str(record.seq)
    if len(seq_query) < 50:
        raise ValueError(
            "Insufficient data for search: Query sequence is too short for HMMER search (must be at least 50 bp)."
        )

    subject_sequences = global_bgc_sequence_block()
    query_sequence = create_block_from_tuples([(record.id, seq_query)], alphabet="dna")

    for query_tophits in nhmmer(
        query_sequence,
        subject_sequences,
        cpus=1,  # use 1 thread to avoid parallelism issues
    ):
        for hit in query_tophits:
            if hit.score > threshold:
                try:
                    bgc_id = int(hit.name.decode())
                except Exception:
                    continue
                similarity_results[bgc_id] = max(
                    similarity_results.get(bgc_id, 0.0), hit.score
                )
    return similarity_results


# --------------------------------------------------------------
# Protein-set HMMER search -------------------------------------
# --------------------------------------------------------------
def _proteins_set_hmmer_search(
    record: SeqRecord, similarity_threshold: float, set_similarity_threshold: float
) -> Dict[int, float]:
    """Translated CDS sequences; treat a *protein* as intersecting when pairwise
    similarity ≥ threshold, then fall back to Sørensen-Dice across the set.
    """
    similarity_results: Dict[int, float] = {}

    query_proteins = [
        (f"query_{ix}", feat.qualifiers["translation"][0])
        for ix, feat in enumerate(record.features)
        if feat.type.upper() == "CDS" and "translation" in feat.qualifiers
    ]
    if not query_proteins:
        raise ValueError(
            "Insufficient data for search: No CDS features with translations found in the record for protein HMMER search."
        )
    query_block = create_block_from_tuples(query_proteins, alphabet="amino")

    bgc_queryset = (
        Bgc.objects.filter(is_aggregated_region=True).select_related("contig").all()
    )
    for bgc in bgc_queryset:
        bgc_proteins = list(iter_protein_tuples_from_bgcs(bgc_queryset=[bgc]))
        if not bgc_proteins:
            continue
        subject_block = create_block_from_tuples(bgc_proteins, alphabet="amino")

        query_set = {str(x[0]) for x in query_proteins}
        subject_set = {
            str(x[0]) if isinstance(x, (list, tuple)) else str(getattr(x, "id", x))
            for x in bgc_proteins
        }

        for query_tophits in phmmer(
            query_block,
            subject_block,
            cpus=1,
        ):
            for hit in query_tophits:
                if hit.score > similarity_threshold:
                    query_prot = query_tophits.query.name.decode()
                    query_set.discard(query_prot)

                    subject_prot = hit.name.decode()
                    subject_set.discard(subject_prot)

                    new_element = f"{min(query_prot, subject_prot)}-{max(query_prot, subject_prot)}"

                    query_set.add(new_element)
                    subject_set.add(new_element)

        dice = sorensen_dice(query_set, subject_set)
        if dice >= set_similarity_threshold:
            similarity_results[bgc.id] = max(similarity_results.get(bgc.id, 0), dice)

    return similarity_results


# --------------------------------------------------------------
# Single-protein HMMER search ----------------------------------
# --------------------------------------------------------------
def _protein_hmmer_search(record: SeqRecord, threshold: float) -> Dict[int, float]:
    similarity_results: Dict[int, float] = {}

    query_proteins = [
        (f"query_{ix}", feat.qualifiers["translation"][0])
        for ix, feat in enumerate(record.features)
        if feat.type.upper() == "CDS" and "translation" in feat.qualifiers
    ]
    if not query_proteins:
        raise ValueError(
            "Insufficient data for search: No CDS features with translations found in the record for protein HMMER search."
        )
    query_block = create_block_from_tuples(query_proteins, alphabet="amino")

    bgcs_queryset = (
        Bgc.objects.filter(is_aggregated_region=True).select_related("contig").all()
    )
    prots_in_bgc = {}
    for bgc in bgcs_queryset:
        prot_objs = list(
            iter_protein_tuples_from_bgcs(bgc_queryset=[bgc], yield_objects=True)
        )
        prots_in_bgc[bgc.id] = [
            prot[0] if isinstance(prot, (list, tuple)) else getattr(prot, "id", None)
            for prot in prot_objs
            if (
                isinstance(prot, (list, tuple)) or getattr(prot, "id", None) is not None
            )
        ]
    prots_to_bgc = {
        prot: bgc_id for bgc_id, prots in prots_in_bgc.items() for prot in prots
    }

    all_proteins_block = global_protein_sequence_block()

    for query_tophits in phmmer(
        query_block,
        all_proteins_block,
        cpus=1,
    ):
        for hit in query_tophits:
            if hit.score > threshold:
                subject_prot = hit.name.decode()
                try:
                    subject_int = int(subject_prot)
                except Exception:
                    continue
                bgc_id = prots_to_bgc.get(subject_int)
                if bgc_id is None:
                    continue
                similarity_results[bgc_id] = max(
                    similarity_results.get(bgc_id, 0.0), hit.score
                )

    return similarity_results
