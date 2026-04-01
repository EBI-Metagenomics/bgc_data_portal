"""GenBank record builder for discovery BGCs.

Generates multi-record GBK files from DashboardBgc data, using contig
sequences and CDS translations stored in the discovery schema's on-demand
sequence tables (ContigSequence, CdsSequence).
"""

import json
from io import StringIO
from typing import List

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from discovery.models import DashboardBgc

FLANKING_WINDOW = 2000


def _crop(val: int, lo: int, hi: int) -> int:
    return max(lo, min(val, hi))


def build_bgc_genbank_record(bgc: DashboardBgc) -> SeqRecord:
    """Build a single SeqRecord for a BGC with flanking window.

    Expects ``bgc.contig`` and ``bgc.contig.seq`` to be prefetched.
    CDS entries should have ``seq`` prefetched via ``cds_list`` + ``cds_list__seq``.
    """
    contig = bgc.contig
    contig_seq_obj = getattr(contig, "seq", None) if contig else None

    if contig_seq_obj is None:
        return _build_placeholder_record(bgc)

    contig_seq = contig_seq_obj.get_sequence()
    contig_len = len(contig_seq)

    window_start = max(0, bgc.start_position - FLANKING_WINDOW)
    window_end = min(contig_len, bgc.end_position + FLANKING_WINDOW)
    region_seq = contig_seq[window_start:window_end]

    contig_acc = bgc.contig_accession or contig.accession
    genome = bgc.genome

    record = SeqRecord(
        Seq(region_seq),
        id=contig_acc,
        name=contig_acc[:16],  # GenBank LOCUS name max 16 chars
        description=(
            f"Region {window_start}-{window_end} on "
            f"{contig_acc} (BGC {bgc.bgc_accession})"
        ),
    )

    record.annotations["molecule_type"] = "DNA"
    record.annotations["topology"] = "linear"
    record.annotations["organism"] = genome.organism_name if genome else "Unknown"
    record.annotations["source"] = json.dumps({
        "contig_accession": contig_acc,
        "assembly_accession": genome.assembly_accession if genome else "",
        "bgc_accession": bgc.bgc_accession,
        "start_position": bgc.start_position + 1,
        "end_position": bgc.end_position,
    })

    features: List[SeqFeature] = []

    # ── CLUSTER feature ──────────────────────────────────────────────────────
    bgc_rel_start = bgc.start_position - window_start
    bgc_rel_end = bgc.end_position - window_start

    classification = "/".join(
        filter(None, [bgc.classification_l1, bgc.classification_l2, bgc.classification_l3])
    )
    cluster_feat = SeqFeature(
        FeatureLocation(bgc_rel_start, bgc_rel_end),
        type="CLUSTER",
        qualifiers={
            "ID": [bgc.bgc_accession],
            "BGC_CLASS": [bgc.classification_l1 or "Unknown"],
            "classification": [classification or "Unknown"],
            "detector": [bgc.detector_names or "Unknown"],
            "contig_edge": ["True" if bgc.is_partial else "False"],
        },
    )
    features.append(cluster_feat)

    # ── CDS features ─────────────────────────────────────────────────────────
    for cds in bgc.cds_list.all():
        cds_start = _crop(cds.start_position, window_start, window_end)
        cds_end = _crop(cds.end_position, window_start, window_end)
        rel_start = cds_start - window_start
        rel_end = cds_end - window_start

        seq_obj = getattr(cds, "seq", None)
        aa_seq = seq_obj.get_sequence() if seq_obj else ""

        qualifiers = {
            "ID": [cds.protein_id_str],
            "gene_caller": [cds.gene_caller or ""],
        }
        if aa_seq:
            qualifiers["translation"] = [aa_seq]
            qualifiers["protein_id"] = [cds.protein_id_str]
        if cds.cluster_representative:
            qualifiers["cluster_representative"] = [cds.cluster_representative]

        cds_feat = SeqFeature(
            FeatureLocation(rel_start, rel_end, strand=cds.strand),
            type="CDS",
            qualifiers=qualifiers,
        )
        features.append(cds_feat)

    record.features = features
    return record


def _build_placeholder_record(bgc: DashboardBgc) -> SeqRecord:
    """Build a minimal record when contig sequence is unavailable."""
    length = max(1, bgc.end_position - bgc.start_position)
    record = SeqRecord(
        Seq("N" * length),
        id=bgc.contig_accession or "unknown",
        name=bgc.bgc_accession[:16],
        description=f"BGC {bgc.bgc_accession} (sequence unavailable)",
    )
    record.annotations["molecule_type"] = "DNA"
    return record


def build_multi_bgc_gbk(bgc_ids: List[int]) -> str:
    """Build a multi-record GBK string for a list of dashboard BGC IDs."""
    bgcs = (
        DashboardBgc.objects.filter(id__in=bgc_ids)
        .select_related("genome", "contig", "contig__seq")
        .prefetch_related("cds_list", "cds_list__seq")
    )

    records = [build_bgc_genbank_record(bgc) for bgc in bgcs]

    handle = StringIO()
    SeqIO.write(records, handle, "genbank")
    return handle.getvalue()
