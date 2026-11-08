"""Discovery data loader — bulk ingest TSV files into the iBGC-first schema.

Pipeline phases (in dependency order):

  1. Detectors            → DashboardDetector
  2. Assemblies           → DashboardAssembly
  3. Contigs              → DashboardContig
  3.5 Contig sequences    → ContigSequence
  4. Source predictions   → SourceBgcPrediction + ConsensusBgc (via CbgcAssigner)
  5. CDS                  → ContigCds (deduped on contig + range + strand)
  5.5 CDS sequences       → CdsSequence
  6. Domains              → ContigDomain (FK to ContigCds + denormalised contig FK)

  4b. NPClassifier labels  → SourceBgcNpcLabel (bgc_np_classes.tsv, optional; the
      ontology is upserted first from ``common_core.npc``)

iBGCs, their per-iBGC NPClassifier label union, assembly scores and catalog
counts are built downstream by ``build_integrated_bgcs``. Curated natural
products (``natural_products.tsv``) have no loader step in the staged path.

Every ``load_*`` step maps TSV rows to model instances and streams them
through :func:`_bulk_upsert`.

Expected directory layout::

    data_dir/
      detectors.tsv
      assemblies.tsv
      contigs.tsv
      contig_sequences.tsv      (optional)
      bgcs.tsv                  (source predictions)
      cds.tsv                   (optional)
      cds_sequences.tsv         (optional)
      domains.tsv               (optional)
      bgc_np_classes.tsv        (optional; NPClassifier labels per BGC)
      natural_products.tsv      (optional; not read by the staged loader)

Legacy files from pre-removal staged tarballs (``cds_chemont.tsv``,
``embeddings_bgc.tsv``, ``embeddings_protein.tsv``) and the ``umap_x`` /
``umap_y`` columns of ``bgcs.tsv`` are ignored: they are never read, so old
tarballs still load.
"""

from __future__ import annotations

import base64
import csv
import json
import logging
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from discovery.models import (
    AssemblySource,
    CdsSequence,
    ContigCds,
    ContigDomain,
    ContigSequence,
    DashboardAssembly,
    DashboardContig,
    DashboardDetector,
    SourceBgcPrediction,
    Taxon,
)
from discovery.services.go_slim import go_slim_for_terms
from discovery.services.taxonomy import RANKS

from .cbgc_assigner import CbgcAssigner
from .ranges import int4range
from .tsv_copy import truncate_tables

logger = logging.getLogger(__name__)

BATCH_SIZE = 10_000
SEQUENCE_INSERT_BATCH_SIZE = 500  # smaller SQL batches for large binary payloads

# Truncation order (FK CASCADE would handle it, but explicit is safer).
ALL_DISCOVERY_TABLES = [
    "discovery_accession_alias",
    "discovery_ibgc_npc_label",
    "discovery_source_bgc_npc_label",
    "discovery_ibgc_clustering_snapshot",
    "discovery_gcf",
    "discovery_domain_hit",
    "discovery_cds_sequence",
    "discovery_cds",
    "discovery_source_bgc",
    "discovery_ibgc",
    "discovery_cbgc",
    "discovery_accession_registry",
    "discovery_contig_sequence",
    "discovery_contig",
    "discovery_taxon",
    "discovery_assembly",
    "discovery_detector",
    "discovery_assembly_source",
    "discovery_bgc_class",
    "discovery_domain",
    "discovery_clustering_run",
]


def _version_sort_key(version_str: str) -> int:
    """Convert a semver-ish string to a sortable integer."""
    parts = []
    for segment in version_str.split("."):
        digits = "".join(c for c in segment if c.isdigit())
        parts.append(int(digits) if digits else 0)
    parts = (parts + [0, 0, 0])[:3]
    return parts[0] * 1_000_000 + parts[1] * 1_000 + parts[2]


def _generate_tool_name_code(tool: str, existing_codes: set[str]) -> str:
    base = tool.strip().upper()[:3] if tool and tool.strip() else "UNK"
    if len(base) < 3:
        base = base.ljust(3, "X")

    if base not in existing_codes:
        existing_codes.add(base)
        return base

    for i in range(2, 100):
        candidate = f"{base[:2]}{i}"
        if candidate not in existing_codes:
            existing_codes.add(candidate)
            return candidate

    raise ValueError(f"Cannot generate unique tool_name_code for {tool!r}")


def _bulk_upsert(
    model,
    rows: Iterable,
    *,
    unique_fields: list[str] | None = None,
    update_fields: list[str] | None = None,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Write ``rows`` in batches: upsert on ``unique_fields``, or insert-ignore.

    With ``update_fields`` each batch is deduplicated on ``unique_fields``
    (last occurrence wins) so a repeated key never makes ``ON CONFLICT DO
    UPDATE`` touch the same row twice in one statement. Without it, rows are
    inserted with ``ignore_conflicts``. Returns the number of rows written.
    """
    key_attrs = [model._meta.get_field(f).attname for f in unique_fields or ()]
    total = 0
    batch: list = []

    def _flush() -> None:
        nonlocal total
        if not batch:
            return
        if update_fields is None:
            written = list(batch)
            model.objects.bulk_create(
                written, batch_size=batch_size, ignore_conflicts=True
            )
        else:
            written = list(
                {tuple(getattr(o, a) for a in key_attrs): o for o in batch}.values()
            )
            model.objects.bulk_create(
                written,
                batch_size=batch_size,
                update_conflicts=True,
                unique_fields=unique_fields,
                update_fields=update_fields,
            )
        total += len(written)
        batch.clear()

    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            _flush()
    _flush()
    return total


def _tsv_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield the rows of a staged TSV as dicts (no field-size cap)."""
    csv.field_size_limit(sys.maxsize)
    with open(path, newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def _require_columns(path: Path, required: set[str]) -> None:
    """Raise ValueError when the TSV header lacks any of *required*."""
    with open(path, newline="") as f:
        header = next(csv.reader(f, delimiter="\t"), [])
    missing = required - set(header)
    if missing:
        raise ValueError(f"{path.name} lacks columns {sorted(missing)}")


# Without these a contig would load with length 0 or an empty accession.
CONTIGS_REQUIRED_COLUMNS = {
    "assembly_accession",
    "sequence_sha256",
    "accession",
    "length",
}


# ── Pipeline steps ───────────────────────────────────────────────────────────


def load_detectors(data_dir: Path) -> dict[str, tuple[int, str]]:
    """Load detectors.tsv → DashboardDetector.

    Returns ``{name: (detector_id, tool_name_code)}``.
    """
    path = data_dir / "detectors.tsv"
    if not path.exists():
        logger.warning("detectors.tsv not found, skipping")
        return {}

    existing_codes: set[str] = set()

    def rows() -> Iterator[DashboardDetector]:
        for row in _tsv_rows(path):
            tool, version = row["tool"], row["version"]
            yield DashboardDetector(
                name=row["name"],
                tool=tool,
                version=version,
                tool_name_code=_generate_tool_name_code(tool, existing_codes),
                version_sort_key=_version_sort_key(version),
            )

    _bulk_upsert(
        DashboardDetector,
        rows(),
        unique_fields=["tool", "version"],
        update_fields=["name", "tool_name_code", "version_sort_key"],
    )
    lookup = {d.name: (d.id, d.tool_name_code) for d in DashboardDetector.objects.all()}
    logger.info("Loaded %d detectors", len(lookup))
    return lookup


def load_assemblies(data_dir: Path) -> dict[str, int]:
    """Load assemblies.tsv → DashboardAssembly. Returns ``{accession: id}``."""
    path = data_dir / "assemblies.tsv"
    if not path.exists():
        logger.warning("assemblies.tsv not found, skipping")
        return {}

    source_cache: dict[str, AssemblySource] = {}

    def _get_source(name: str) -> AssemblySource | None:
        if not name:
            return None
        if name not in source_cache:
            obj, _ = AssemblySource.objects.get_or_create(name=name)
            source_cache[name] = obj
        return source_cache[name]

    def rows() -> Iterator[DashboardAssembly]:
        for row in _tsv_rows(path):
            yield DashboardAssembly(
                assembly_accession=row["assembly_accession"],
                organism_name=row.get("organism_name", ""),
                source=_get_source(row.get("source", "")),
                assembly_type=int(row.get("assembly_type", 2)),
                biome_path=row.get("biome_path", ""),
                is_type_strain=row.get("is_type_strain", "").lower() in ("true", "1"),
                type_strain_catalog_url=row.get("type_strain_catalog_url", ""),
                assembly_size_mb=(
                    float(row["assembly_size_mb"])
                    if row.get("assembly_size_mb")
                    else None
                ),
                url=row.get("url", ""),
            )

    _bulk_upsert(
        DashboardAssembly,
        rows(),
        unique_fields=["assembly_accession"],
        update_fields=[
            "organism_name",
            "source",
            "assembly_type",
            "biome_path",
            "is_type_strain",
            "type_strain_catalog_url",
            "assembly_size_mb",
            "url",
        ],
    )
    lookup = dict(DashboardAssembly.objects.values_list("assembly_accession", "id"))
    logger.info("Loaded %d assemblies", len(lookup))
    return lookup


LTREE_PATH_RE = re.compile(r"[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*")
TAXA_REQUIRED_COLUMNS = {"taxid", "name", "rank", "ltree_path", "taxdump_version"}
TAXON_IDENTITY = ("name", "rank", "parent_taxid", "ltree_path")


def _int_or_none(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def load_taxa(data_dir: Path, *, allow_taxon_changes: bool = False) -> int:
    """Load taxa.tsv → Taxon (upsert on taxid). Returns the number of rows.

    ``taxa.tsv`` comes from the ETL's ``etl.taxonomy.harmonise_contigs`` and
    holds every taxon that ``contigs.tsv`` points at (leaf + canonical-rank
    ancestors). Blank rank columns are NULL.

    A Taxon row is a function of (taxid, taxdump). If an incoming row differs
    in name, rank, parent or lineage path from the stored one, the data was
    harmonised against a different taxdump: the stored contigs still carry the
    old ``taxonomy_path`` labels, so silently updating the Taxon would make the
    taxonomy tree and the rank labels disagree. That aborts the load unless
    ``allow_taxon_changes`` (a deliberate taxdump bump, followed by
    re-harmonising the existing contigs).
    """
    path = data_dir / "taxa.tsv"
    if not path.exists():
        logger.info("taxa.tsv not found, skipping")
        return 0

    taxa: dict[int, Taxon] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = TAXA_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"taxa.tsv lacks columns {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            if not LTREE_PATH_RE.fullmatch(row["ltree_path"]):
                raise ValueError(
                    f"taxa.tsv line {line_no}: invalid ltree_path {row['ltree_path']!r}"
                )
            fields: dict[str, object] = {
                "taxid": int(row["taxid"]),
                "name": row["name"],
                "rank": row["rank"],
                "parent_taxid": _int_or_none(row.get("parent_taxid")),
                "ltree_path": row["ltree_path"],
                "deepest_informative_rank": row.get("deepest_informative_rank") or "",
                "taxdump_version": row["taxdump_version"],
            }
            for rank in RANKS:
                fields[f"{rank}_name"] = row.get(f"{rank}_name") or ""
                fields[f"{rank}_taxid"] = _int_or_none(row.get(f"{rank}_taxid"))
            taxa[int(row["taxid"])] = Taxon(**fields)
    if not taxa:
        return 0

    if not allow_taxon_changes:
        ids = list(taxa)
        changed: list[int] = []
        for i in range(0, len(ids), 1000):
            for stored in Taxon.objects.filter(taxid__in=ids[i : i + 1000]):
                new = taxa[stored.taxid]
                if any(getattr(stored, a) != getattr(new, a) for a in TAXON_IDENTITY):
                    changed.append(stored.taxid)
        if changed:
            raise ValueError(
                f"taxa.tsv redefines {len(changed)} stored taxon(s) "
                f"(e.g. {sorted(changed)[:10]}): harmonised against a different "
                "taxdump? Re-harmonise the existing contigs, or pass "
                "--allow-taxon-changes for a deliberate taxdump bump."
            )

    _bulk_upsert(
        Taxon,
        taxa.values(),
        unique_fields=["taxid"],
        update_fields=[
            f.name for f in Taxon._meta.concrete_fields if f.name != "taxid"
        ],
    )
    logger.info("Loaded %d taxa", len(taxa))
    return len(taxa)


def load_contigs(
    data_dir: Path,
    assembly_lookup: dict[str, int],
    *,
    retaxonomy: bool = False,
) -> dict[str, int]:
    """Load contigs.tsv → DashboardContig. Returns ``{sequence_sha256: contig_id}``.

    Rows with a ``taxid`` (harmonised by the ETL; ``taxonomy_path`` is already
    canonical) set ``taxon`` and ``taxonomy_path`` as given. The taxid must
    exist in ``Taxon`` — load ``taxa.tsv`` first.

    Rows without one are legacy: their rank-less ``taxonomy_path`` would
    silently undo a canonical path, so contigs already linked to a ``Taxon``
    keep theirs. ``retaxonomy=True`` takes the TSV path instead and unlinks the
    taxon so the contig is picked up by the next ``apply_taxonomy_mapping`` run.
    """
    path = data_dir / "contigs.tsv"
    if not path.exists():
        logger.warning("contigs.tsv not found, skipping")
        return {}
    _require_columns(path, CONTIGS_REQUIRED_COLUMNS)

    by_sha: dict[str, DashboardContig] = {}
    for row in _tsv_rows(path):
        assembly_acc = row["assembly_accession"]
        assembly_id = assembly_lookup.get(assembly_acc)
        if assembly_id is None:
            logger.warning(
                "Unknown assembly %s for contig %s, skipping",
                assembly_acc,
                row.get("accession", row["sequence_sha256"]),
            )
            continue
        by_sha[row["sequence_sha256"]] = DashboardContig(
            assembly_id=assembly_id,
            sequence_sha256=row["sequence_sha256"],
            accession=row.get("accession", ""),
            length=int(row.get("length", 0)),
            taxonomy_path=row.get("taxonomy_path", ""),
            taxon_id=_int_or_none(row.get("taxid")),
        )

    harmonised = [o for o in by_sha.values() if o.taxon_id is not None]
    legacy = [o for o in by_sha.values() if o.taxon_id is None]

    if harmonised:
        unknown = {o.taxon_id for o in harmonised} - set(
            Taxon.objects.values_list("taxid", flat=True)
        )
        if unknown:
            raise ValueError(
                f"contigs.tsv references {len(unknown)} taxid(s) absent from Taxon "
                f"(e.g. {sorted(unknown)[:10]}): load taxa.tsv with them first."
            )
        _bulk_upsert(
            DashboardContig,
            harmonised,
            unique_fields=["sequence_sha256"],
            update_fields=["assembly", "accession", "length", "taxonomy_path", "taxon"],
        )
        logger.info("Loaded %d contigs with a taxid", len(harmonised))

    if legacy:
        update_fields = ["assembly", "accession", "length", "taxonomy_path"]
        if retaxonomy:
            update_fields += ["taxon", "taxonomy_path_legacy"]
        else:
            linked: dict[str, str] = {}
            shas = [o.sequence_sha256 for o in legacy]
            for i in range(0, len(shas), BATCH_SIZE):
                linked.update(
                    DashboardContig.objects.filter(
                        sequence_sha256__in=shas[i : i + BATCH_SIZE],
                        taxon__isnull=False,
                    ).values_list("sequence_sha256", "taxonomy_path")
                )
            for o in legacy:
                if o.sequence_sha256 in linked:
                    o.taxonomy_path = linked[o.sequence_sha256]
            if linked:
                logger.info(
                    "Kept canonical taxonomy_path for %d taxon-linked contigs",
                    len(linked),
                )
        _bulk_upsert(
            DashboardContig,
            legacy,
            unique_fields=["sequence_sha256"],
            update_fields=update_fields,
        )

    lookup = dict(DashboardContig.objects.values_list("sequence_sha256", "id"))
    logger.info("Loaded %d contigs", len(lookup))
    return lookup


def load_contig_sequences(data_dir: Path, contig_lookup: dict[str, int]) -> int:
    """Load contig_sequences.tsv → ContigSequence."""
    path = data_dir / "contig_sequences.tsv"
    if not path.exists():
        logger.info("contig_sequences.tsv not found, skipping")
        return 0

    def rows() -> Iterator[ContigSequence]:
        for row in _tsv_rows(path):
            contig_sha = row["contig_sha256"]
            contig_id = contig_lookup.get(contig_sha)
            if contig_id is None:
                logger.warning("Unknown contig %s for sequence, skipping", contig_sha)
                continue
            yield ContigSequence(
                contig_id=contig_id, data=base64.b64decode(row["sequence_base64"])
            )

    total = _bulk_upsert(
        ContigSequence,
        rows(),
        unique_fields=["contig"],
        update_fields=["data"],
        batch_size=SEQUENCE_INSERT_BATCH_SIZE,
    )
    logger.info("Loaded %d contig sequences", total)
    return total


# ── Source predictions + cBGC assignment ─────────────────────────────────────


def _float_or_none(value: str | None) -> float | None:
    """Optional float column of the staged TSVs (``""`` / missing → None)."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _json_or_none(value: str | None):
    """Optional JSON column of the staged TSVs (``""`` / missing / invalid → None)."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def load_bgc_np_classes(
    data_dir: Path,
    source_bgc_lookup: dict[tuple[str, int, int, str], int],
) -> int:
    """Load the optional ``bgc_np_classes.tsv`` → ``SourceBgcNpcLabel``.

    Rows name a source prediction by ``(contig_sha256, bgc_start, bgc_end,
    detector_name)`` and an ontology term by ``np_term_id``; rows whose BGC or
    term is unknown are skipped with a warning. The ontology must be loaded
    first (``load_npc_ontology``).
    """
    path = data_dir / "bgc_np_classes.tsv"
    if not path.exists():
        return 0
    from discovery.models import NpcTerm, SourceBgcNpcLabel

    known_terms = set(NpcTerm.objects.values_list("term_id", flat=True))
    skipped_bgc = skipped_term = 0

    def rows() -> Iterator[SourceBgcNpcLabel]:
        nonlocal skipped_bgc, skipped_term
        for row in _tsv_rows(path):
            key = (
                row["contig_sha256"],
                int(row["bgc_start"]),
                int(row["bgc_end"]),
                row["detector_name"],
            )
            sbgc_id = source_bgc_lookup.get(key)
            if sbgc_id is None:
                skipped_bgc += 1
                continue
            term_id = (row.get("np_term_id") or "").strip()
            if term_id not in known_terms:
                skipped_term += 1
                continue
            yield SourceBgcNpcLabel(
                source_bgc_id=sbgc_id,
                term_id=term_id,
                rank=int(row.get("rank") or 1),
                score=_float_or_none(row.get("score")),
                confident=(row.get("confident") or "").lower() in ("true", "1"),
                source=(row.get("source") or SourceBgcNpcLabel.SOURCE_PREDICTED)[:16],
            )

    total = _bulk_upsert(SourceBgcNpcLabel, rows())
    if skipped_bgc or skipped_term:
        logger.warning(
            "bgc_np_classes.tsv: skipped %d rows with unknown BGC "
            "and %d with unknown term",
            skipped_bgc,
            skipped_term,
        )
    logger.info("Loaded %d source-prediction NPClassifier labels", total)
    return total


def _build_source_bgc_lookup() -> dict[tuple[str, int, int, str], int]:
    """Return ``{(contig_sha256, start, end, detector_name): source_bgc_id}``."""
    lookup: dict[tuple[str, int, int, str], int] = {}
    qs = SourceBgcPrediction.objects.select_related("contig", "detector").only(
        "id",
        "contig__sequence_sha256",
        "bgc_range",
        "detector__name",
    )
    for sbgc in qs.iterator():
        rng = sbgc.bgc_range
        if rng is None:
            continue
        start = int(rng.lower)
        end_inclusive = int(rng.upper) - 1
        key = (
            sbgc.contig.sequence_sha256,
            start,
            end_inclusive,
            sbgc.detector.name if sbgc.detector_id else "",
        )
        lookup[key] = sbgc.id
    return lookup


def load_source_bgcs(
    data_dir: Path,
    contig_lookup: dict[str, int],
    detector_lookup: dict[str, tuple[int, str]],
    assembly_lookup: dict[str, int],
) -> dict[tuple[str, int, int, str], int]:
    """Load bgcs.tsv → SourceBgcPrediction + ConsensusBgc (via CbgcAssigner).

    Returns ``{(contig_sha256, start, end, detector_name): source_bgc_id}``.
    """
    path = data_dir / "bgcs.tsv"
    if not path.exists():
        logger.warning("bgcs.tsv not found, skipping")
        return {}

    contig_to_assembly: dict[int, int] = dict(
        DashboardContig.objects.values_list("id", "assembly_id")
    )
    contig_accession_by_id: dict[int, str] = dict(
        DashboardContig.objects.values_list("id", "accession")
    )

    batch: list[SourceBgcPrediction] = []
    total = 0

    def _flush_batch() -> None:
        # Nested-function bulk_create used both by the size-triggered flushes
        # in the loop and by the assigner's pre-merge hook — the hook needs
        # to persist any in-flight rows before their cbgc_id references get
        # invalidated by a cBGC merge/delete downstream.
        nonlocal total
        if not batch:
            return
        SourceBgcPrediction.objects.bulk_create(batch, ignore_conflicts=True)
        total += len(batch)
        batch.clear()

    assigner = CbgcAssigner(on_pre_merge=_flush_batch)

    for row in _tsv_rows(path):
        contig_sha = row["contig_sha256"]
        contig_id = contig_lookup.get(contig_sha)
        if contig_id is None:
            logger.warning("Unknown contig %s, skipping source prediction", contig_sha)
            continue

        detector_name = row["detector_name"]
        det_info = detector_lookup.get(detector_name)
        if det_info is None:
            logger.warning(
                "Unknown detector %s, skipping source prediction", detector_name
            )
            continue
        detector_id, tool_code = det_info

        start = int(row["start_position"])
        end = int(row["end_position"])

        cbgc_id, bgc_number, prediction_accession = assigner.assign(
            contig_id=contig_id,
            contig_accession=contig_accession_by_id.get(contig_id, "") or contig_sha,
            start=start,
            end=end,
            detector_id=detector_id,
            tool_code=tool_code,
        )

        assembly_id = contig_to_assembly.get(contig_id)

        batch.append(
            SourceBgcPrediction(
                assembly_id=assembly_id,
                contig_id=contig_id,
                prediction_accession=prediction_accession,
                bgc_range=int4range(start, end),
                classification_path=(row.get("classification_path") or "").strip()[
                    :255
                ],
                is_partial=row.get("is_partial", "").lower() in ("true", "1"),
                is_validated=row.get("is_validated", "").lower() in ("true", "1"),
                score=_float_or_none(row.get("score")),
                probability=_float_or_none(row.get("probability")),
                attributes=_json_or_none(row.get("attributes_json")),
                detector_id=detector_id,
                cbgc_id=cbgc_id,
                bgc_number=bgc_number,
            )
        )

        if len(batch) >= BATCH_SIZE:
            _flush_batch()

    _flush_batch()

    lookup = _build_source_bgc_lookup()
    logger.info(
        "Loaded %d source predictions across %d cBGCs",
        total,
        len(
            {
                sbgc.cbgc_id
                for sbgc in SourceBgcPrediction.objects.only("cbgc_id").iterator()
            }
        ),
    )
    return lookup


# ── CDS / domains ──────────────────────────────────────────────────────────


def load_cds(
    data_dir: Path,
    contig_lookup: dict[str, int],
) -> dict[tuple[int, str], int]:
    """Load cds.tsv → ContigCds. CDS are contig-anchored and deduped on
    ``(contig, cds_range, strand)`` — the same gene called by two BGC tools
    is stored once.

    Alternative transcripts of one eukaryotic gene (``.t1`` / ``.t2``) with the
    same outer span also collapse: the first row in the file (``.t1``) is kept,
    and the other isoform's sequence and domains are not loaded. In the
    2026-11-08 marine-eukaryote E2E the 9 such pairs had identical Pfam /
    NCBIfam domain sets. The number dropped is logged.

    Returns ``{(contig_id, protein_id_str): cds_id}``.
    """
    path = data_dir / "cds.tsv"
    if not path.exists():
        logger.info("cds.tsv not found, skipping")
        return {}

    # (contig_id, lower, upper, strand) → protein_id_str of the kept row
    seen: dict[tuple[int, int, int, int], str] = {}
    collapsed: list[str] = []  # distinct proteins dropped onto a kept span

    def rows() -> Iterator[ContigCds]:
        for row in _tsv_rows(path):
            contig_id = contig_lookup.get(row["contig_sha256"])
            if contig_id is None:
                continue
            strand = int(row["strand"])
            cds_range = int4range(int(row["start_position"]), int(row["end_position"]))
            dedup_key = (contig_id, cds_range.lower, cds_range.upper, strand)
            kept = seen.get(dedup_key)
            if kept is not None:
                if kept != row["protein_id_str"]:
                    collapsed.append(row["protein_id_str"])
                continue
            seen[dedup_key] = row["protein_id_str"]
            yield ContigCds(
                contig_id=contig_id,
                cds_range=cds_range,
                strand=strand,
                protein_id_str=row["protein_id_str"],
                protein_length=int(row.get("protein_length", 0)),
                gene_caller=row.get("gene_caller", ""),
                cluster_representative=row.get("cluster_representative", ""),
                protein_sha256=row.get("protein_sha256", ""),
            )

    total = _bulk_upsert(ContigCds, rows())
    logger.info("Loaded %d CDS rows", total)
    if collapsed:
        logger.warning(
            "%d CDS shared a (contig, span, strand) with an earlier, different "
            "protein (e.g. alternative transcripts) and were not loaded; first: %s",
            len(collapsed),
            collapsed[:5],
        )

    # Lookup keyed by (contig_id, protein_id_str) — the natural per-gene key.
    cds_lookup: dict[tuple[int, str], int] = {}
    for cds_id, contig_id, protein_id in ContigCds.objects.values_list(
        "id",
        "contig_id",
        "protein_id_str",
    ):
        cds_lookup[(contig_id, protein_id)] = cds_id
    return cds_lookup


def load_cds_sequences(
    data_dir: Path,
    contig_lookup: dict[str, int],
    cds_lookup: dict[tuple[int, str], int],
) -> int:
    """Load cds_sequences.tsv → CdsSequence."""
    path = data_dir / "cds_sequences.tsv"
    if not path.exists():
        logger.info("cds_sequences.tsv not found, skipping")
        return 0

    def rows() -> Iterator[CdsSequence]:
        for row in _tsv_rows(path):
            contig_id = contig_lookup.get(row.get("contig_sha256", ""))
            if contig_id is None:
                continue
            cds_id = cds_lookup.get((contig_id, row["protein_id_str"]))
            if cds_id is None:
                continue
            yield CdsSequence(
                cds_id=cds_id, data=base64.b64decode(row["sequence_base64"])
            )

    total = _bulk_upsert(
        CdsSequence,
        rows(),
        unique_fields=["cds"],
        update_fields=["data"],
        batch_size=SEQUENCE_INSERT_BATCH_SIZE,
    )
    logger.info("Loaded %d CDS sequences", total)
    return total


def load_domains(
    data_dir: Path,
    contig_lookup: dict[str, int],
    cds_lookup: dict[tuple[int, str], int],
) -> int:
    """Load domains.tsv → ContigDomain (FK to ContigCds + denormalised contig FK).

    All ref_db values ingested unchanged — downstream callers apply their own
    PFAM/NCBIFAM filter. Domain rows are deduped per (cds, acc, start, end).
    """
    path = data_dir / "domains.tsv"
    if not path.exists():
        logger.info("domains.tsv not found, skipping")
        return 0

    seen: set[tuple[int, str, int, int]] = set()

    def rows() -> Iterator[ContigDomain]:
        for row in _tsv_rows(path):
            contig_id = contig_lookup.get(row.get("contig_sha256", ""))
            if contig_id is None:
                continue
            cds_id = cds_lookup.get((contig_id, row.get("protein_id_str", "")))
            if cds_id is None:
                continue
            domain_acc = row["domain_acc"]
            d_start = int(row.get("start_position", 0))
            d_end = int(row.get("end_position", 0))
            dedup_key = (cds_id, domain_acc, d_start, d_end)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            go_terms_raw = (row.get("go_terms") or "").strip()
            go_terms = [t for t in go_terms_raw.split("|") if t] if go_terms_raw else []
            yield ContigDomain(
                cds_id=cds_id,
                contig_id=contig_id,
                domain_acc=domain_acc,
                domain_name=row.get("domain_name", ""),
                domain_description=row.get("domain_description", ""),
                ref_db=row.get("ref_db", ""),
                start_position=d_start,
                end_position=d_end,
                score=float(row["score"]) if row.get("score") else None,
                url=row.get("url", ""),
                go_slim=go_slim_for_terms(go_terms),
                interpro_entry_acc=row.get("interpro_entry_acc", ""),
                interpro_entry_description=row.get("interpro_entry_description", ""),
                go_terms=go_terms,
            )

    total = _bulk_upsert(ContigDomain, rows())
    logger.info("Loaded %d domain rows", total)
    return total


LEGACY_IGNORED_FILES = (
    "cds_chemont.tsv",
    "embeddings_bgc.tsv",
    "embeddings_protein.tsv",
)


def _log_ignored_legacy_files(data_dir: Path) -> list[str]:
    """Note (and skip) files from removed features in a pre-removal tarball."""
    present = [name for name in LEGACY_IGNORED_FILES if (data_dir / name).exists()]
    if present:
        logger.info("Ignoring legacy files from a pre-removal tarball: %s", present)
    return present


# ── Main entry point ─────────────────────────────────────────────────────────


def run_pipeline(
    data_dir: str | Path,
    *,
    truncate: bool = False,
    retaxonomy: bool = False,
    allow_taxon_changes: bool = False,
) -> None:
    """Execute the full discovery data loading pipeline.

    iBGCs (with their NPClassifier label union), assembly scores and catalog
    counts are NOT created here — ``build_integrated_bgcs`` builds them next.
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    if truncate:
        logger.info("Truncating all discovery tables ...")
        truncate_tables(ALL_DISCOVERY_TABLES)

    detector_lookup = load_detectors(data_dir)
    assembly_lookup = load_assemblies(data_dir)
    load_taxa(data_dir, allow_taxon_changes=allow_taxon_changes)
    contig_lookup = load_contigs(data_dir, assembly_lookup, retaxonomy=retaxonomy)
    load_contig_sequences(data_dir, contig_lookup)

    # NPClassifier ontology (idempotent) → source predictions + cBGC envelopes
    # (with stable accessions) → their NPClassifier labels.
    from discovery.services.npc import load_npc_ontology

    load_npc_ontology()
    source_bgc_lookup = load_source_bgcs(
        data_dir, contig_lookup, detector_lookup, assembly_lookup
    )
    load_bgc_np_classes(data_dir, source_bgc_lookup)

    # CDS / domains — contig-anchored, deduped at insert.
    cds_lookup = load_cds(data_dir, contig_lookup)
    load_cds_sequences(data_dir, contig_lookup, cds_lookup)
    load_domains(data_dir, contig_lookup, cds_lookup)
    _log_ignored_legacy_files(data_dir)

    logger.info(
        "Loader complete. Next step (operator): python manage.py build_integrated_bgcs "
        "(rebuilds iBGCs, classes, catalog counts and NPClassifier labels; "
        "data dir %s)",
        data_dir,
    )
