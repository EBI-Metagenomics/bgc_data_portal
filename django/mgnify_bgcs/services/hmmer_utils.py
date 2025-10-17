# -*- coding: utf-8 -*-
from functools import lru_cache
from django.db.models import Q
import logging

from pyhmmer.easel import TextSequence, DigitalSequenceBlock, Alphabet

from ..models import Bgc, Cds, Protein

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def create_block_from_tuples(seq_iter, alphabet="dna"):
    alphabet = Alphabet.dna() if alphabet == "dna" else Alphabet.amino()
    text_seqs = []
    for name, seq_str in seq_iter:
        # name_bytes must be a bytes object (e.g. b"MGYB000000000123")
        # seq_str must be the full sequence (DNA or protein)
        text_seq = TextSequence(name=f"{name}".encode(), sequence=seq_str)
        text_seqs.append(text_seq.digitize(alphabet))
    return DigitalSequenceBlock(alphabet, iterable=text_seqs)
    # return text_seqs


def iter_bgc_nucleotide_tuples(bgc_queryset=None):
    # select_related contig for fewer queries
    if bgc_queryset is None:
        bgc_queryset = (
            Bgc.objects.filter(is_aggregated_region=True).select_related("contig").all()
        )
    for bgc in bgc_queryset.select_related("contig"):
        contig = bgc.contig
        if not contig or not contig.sequence:
            continue

        # Convert 1-based inclusive (start_position, end_position) → Python slice:
        start = max(bgc.start_position - 1, 0)
        end = min(bgc.end_position, len(contig.sequence))
        if start >= end:
            continue

        subseq = contig.sequence[start:end]
        name = bgc.id
        yield name, subseq


def iter_protein_tuples_from_bgcs(bgc_queryset=None, yield_objects=False):
    # 1. Collect all (contig_id, start, end) tuples for the given BGCs:
    if bgc_queryset is None:
        bgc_queryset = (
            Bgc.objects.filter(is_aggregated_region=True).select_related("contig").all()
        )
    regions = []
    for bgc in bgc_queryset:
        if bgc.contig_id:
            regions.append((bgc.contig_id, bgc.start_position, bgc.end_position))

    if not regions:
        return  # nothing to yield

    # 2. Build a single Q object that OR‐chains all region tests:
    region_q = Q()
    for contig_id, start_pos, end_pos in regions:
        region_q |= (
            Q(contig_id=contig_id)
            & Q(start_position__gte=start_pos)
            & Q(end_position__lte=end_pos)
        )

    # 3. Find all unique protein IDs via matching Cds:
    protein_ids = (
        Cds.objects.filter(region_q).values_list("protein_id", flat=True).distinct()
    )
    if not protein_ids:
        return

    # 4. Fetch each Protein exactly once, yield (sha256, sequence):
    for prot in Protein.objects.filter(id__in=protein_ids).only("id", "sequence"):
        if yield_objects:
            yield prot
        else:
            name = prot.id
            yield name, prot.sequence


bgc_nucleotide_sequences_block = None


@lru_cache(maxsize=1)
def global_bgc_sequence_block():
    """
    Construct a DigitalSequenceBlock containing every BGC nucleotide sequence in the db.
    """

    global bgc_nucleotide_sequences_block
    if bgc_nucleotide_sequences_block is None:
        nucleotides_iterable = iter_bgc_nucleotide_tuples()
        bgc_nucleotide_sequences_block = create_block_from_tuples(
            nucleotides_iterable, alphabet="dna"
        )
    return bgc_nucleotide_sequences_block


bgc_protein_sequences_block = None


@lru_cache(maxsize=1)
def global_protein_sequence_block():
    global bgc_protein_sequences_block
    if bgc_protein_sequences_block is None:
        protein_iterable = iter_protein_tuples_from_bgcs()
        bgc_protein_sequences_block = create_block_from_tuples(
            protein_iterable, alphabet="amino"
        )
    return bgc_protein_sequences_block
