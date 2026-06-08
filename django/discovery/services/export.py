"""Export builders for iBGCs — FNA, FAA, JSON, and TSV formats.

GBK format is handled by ``gbk.py``. All functions take an ``IntegratedBgc``
and reach CDS / domains via genomic range overlap on the contig:
``ContigCds.cds_range && IntegratedBgc.bgc_range``.
"""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import TYPE_CHECKING

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

if TYPE_CHECKING:
    from discovery.models import IntegratedBgc

FLANKING_WINDOW = 2000


def build_report_ibgc_tsv(ibgc_rows: list[dict]) -> str:
    """Tab-separated rendering of a Report shortlist, one row per iBGC.

    Columns mirror the per-iBGC block of the analyst JSON (``ibgcs``) so the
    TSV and JSON stay in lock-step: identity + parent assembly, taxonomy,
    biome, genomic span (start/end/size), novelty scores, GCF, predicted
    class, source tools, and the completeness/validation flags. Caller passes
    the cached payload's ``ibgc_rows``.
    """
    buf = StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
    writer.writerow([
        "ibgc_accession",
        "assembly",
        "organism",
        "phylum",
        "biome",
        "contig",
        "start",
        "end",
        "size_kb",
        "novelty",
        "domain_novelty",
        "gcf",
        "class",
        "sources",
        "is_partial",
        "is_validated",
        "is_type_strain",
    ])
    for r in ibgc_rows:
        novelty = r.get("novelty_score")
        dom_nov = r.get("domain_novelty")
        size_kb = r.get("size_kb")
        writer.writerow([
            r.get("label") or r.get("accession") or "",
            r.get("parent_assembly_accession") or "",
            r.get("organism_name") or "",
            r.get("taxonomy_phylum") or "",
            r.get("biome_path") or "",
            r.get("contig_accession") or "",
            "" if r.get("start") is None else r.get("start"),
            "" if r.get("end") is None else r.get("end"),
            "" if size_kb is None else f"{size_kb:.3f}",
            "" if novelty is None else f"{novelty:.6f}",
            "" if dom_nov is None else f"{dom_nov:.6f}",
            r.get("classification_path") or "",
            r.get("bgc_class") or "",
            ", ".join(r.get("source_tools") or []),
            "true" if r.get("is_partial") else "false",
            "true" if r.get("is_validated") else "false",
            "true" if r.get("is_type_strain") else "false",
        ])
    return buf.getvalue()


# ── Internal helpers ─────────────────────────────────────────────────────────


def _ibgc_cds_qs(ibgc: "IntegratedBgc"):
    """Return CDS overlapping the iBGC's range on its contig, ordered by start."""
    from discovery.models import ContigCds

    return (
        ContigCds.objects
        .filter(contig_id=ibgc.contig_id, cds_range__overlap=ibgc.bgc_range)
        .order_by("cds_range")
    )


def _ibgc_domain_qs(ibgc: "IntegratedBgc"):
    from discovery.models import ContigDomain

    return ContigDomain.objects.filter(
        contig_id=ibgc.contig_id,
        cds__cds_range__overlap=ibgc.bgc_range,
    )


def _claimed_by_tools(ibgc: "IntegratedBgc", cds) -> list[str]:
    """Tools whose source-BGC prediction range covers this CDS in this iBGC."""
    from discovery.models import SourceBgcPrediction

    tools = (
        SourceBgcPrediction.objects
        .filter(integrated_bgc_id=ibgc.id, bgc_range__overlap=cds.cds_range)
        .values_list("detector__tool", flat=True)
        .distinct()
    )
    return sorted(t for t in tools if t)


# ── Public builders (iBGC-level) ─────────────────────────────────────────────


def build_ibgc_fna(ibgc: "IntegratedBgc") -> str:
    """Nucleotide FASTA for the iBGC genomic span (with flanking window).

    Falls back to an N-filled placeholder if contig sequence is unavailable.
    """
    contig = ibgc.contig
    contig_seq_obj = getattr(contig, "seq", None) if contig else None

    start, end = ibgc.start_position, ibgc.end_position

    if contig_seq_obj is None:
        length = max(1, end - start)
        seq = "N" * length
        description = f"iBGC {ibgc.accession} (sequence unavailable)"
        contig_acc = (contig.accession if contig else None) or "unknown"
    else:
        contig_seq = contig_seq_obj.get_sequence()
        contig_len = len(contig_seq)
        window_start = max(0, start - FLANKING_WINDOW)
        window_end = min(contig_len, end + FLANKING_WINDOW)
        seq = contig_seq[window_start:window_end]
        contig_acc = contig.accession or contig.sequence_sha256
        description = (
            f"Region {window_start}-{window_end} on "
            f"{contig_acc} (iBGC {ibgc.accession})"
        )

    record = SeqRecord(
        Seq(seq),
        id=contig_acc,
        name=contig_acc[:16],
        description=description,
    )

    handle = StringIO()
    SeqIO.write([record], handle, "fasta")
    return handle.getvalue()


def build_ibgc_faa(ibgc: "IntegratedBgc") -> str:
    """Amino-acid FASTA for all CDS overlapping the iBGC's range."""
    records = []
    for cds in _ibgc_cds_qs(ibgc).select_related("seq"):
        seq_obj = getattr(cds, "seq", None)
        aa_seq = seq_obj.get_sequence() if seq_obj else ""
        if not aa_seq:
            continue
        record = SeqRecord(
            Seq(aa_seq),
            id=cds.protein_id_str,
            name=cds.protein_id_str[:16],
            description=(
                f"CDS {cds.start_position}-{cds.end_position} "
                f"strand={cds.strand} iBGC={ibgc.accession}"
            ),
        )
        records.append(record)

    if not records:
        records.append(SeqRecord(
            Seq(""),
            id=ibgc.accession,
            description="No CDS sequences available",
        ))

    handle = StringIO()
    SeqIO.write(records, handle, "fasta")
    return handle.getvalue()


def build_ibgc_json(ibgc: "IntegratedBgc") -> dict:
    """JSON metadata dict for a single iBGC.

    Includes contig context, classification, scores, CDS list with
    per-CDS ``claimed_by_tools`` provenance, and domain annotations.
    """
    contig = ibgc.contig
    assembly = contig.assembly if contig else None

    cds_items = []
    cds_rows = list(_ibgc_cds_qs(ibgc))
    for cds in cds_rows:
        cds_items.append({
            "protein_id": cds.protein_id_str,
            "start_position": cds.start_position,
            "end_position": cds.end_position,
            "strand": cds.strand,
            "protein_length": cds.protein_length,
            "gene_caller": cds.gene_caller,
            "cluster_representative": cds.cluster_representative,
            "claimed_by_tools": _claimed_by_tools(ibgc, cds),
        })

    domain_items = []
    for dom in _ibgc_domain_qs(ibgc).select_related("cds"):
        domain_items.append({
            "domain_acc": dom.domain_acc,
            "domain_name": dom.domain_name,
            "description": dom.domain_description,
            "ref_db": dom.ref_db,
            "start_position": dom.start_position,
            "end_position": dom.end_position,
            "score": dom.score,
            "parent_protein_id": dom.cds.protein_id_str,
        })

    return {
        "ibgc_accession": ibgc.accession,
        "cbgc_accession": ibgc.cbgc.accession if ibgc.cbgc_id else None,
        "assembly_accession": assembly.assembly_accession if assembly else None,
        "organism_name": assembly.organism_name if assembly else None,
        "contig_accession": contig.accession if contig else None,
        "start_position": ibgc.start_position,
        "end_position": ibgc.end_position,
        "size_kb": ibgc.size_kb,
        "source_tools": ibgc.source_tools or [],
        "scores": {
            "novelty_score": ibgc.novelty_score,
            "domain_novelty": ibgc.domain_novelty,
        },
        "umap_projected": ibgc.umap_projected,
        "gene_cluster_family": ibgc.gene_cluster_family,
        "umap": {"x": ibgc.umap_x, "y": ibgc.umap_y},
        "cds": cds_items,
        "domains": domain_items,
    }
