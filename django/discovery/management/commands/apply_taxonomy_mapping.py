"""Rewrite contig taxonomy to canonical, rank-aware NCBI lineages.

``DashboardContig.taxonomy_path`` arrives from the ETL rank-less (prefixes
stripped, absent ranks skipped) and in mixed NCBI naming eras. The mapping
TSV — produced offline by the lineage resolver against a pinned NCBI
taxdump, one row per distinct legacy path — gives each path its canonical
dot-path and leaf taxid plus the 8-rank lineage. This command:

  1. upserts ``Taxon`` rows (leaf + every canonical-rank ancestor);
  2. for every *pending* contig (no taxon, no legacy path, non-empty path),
     copies ``taxonomy_path`` into ``taxonomy_path_legacy`` and sets the
     canonical path and ``taxon``. Junk paths become ``''`` with no taxon.

Idempotent: applied contigs are no longer pending, so re-runs only touch
contigs ingested since. Refuses to run while pending contigs carry paths
missing from the mapping (``--export-pending`` writes them out for the
resolver) unless ``--allow-unmapped``. ``--revert`` restores legacy paths.

    manage.py apply_taxonomy_mapping --export-pending /data/pending_paths.tsv
    manage.py apply_taxonomy_mapping paths_resolved.tsv \\
        --taxdump-version "new_taxdump 2026-10-13 md5:0456ea42" --dry-run
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from discovery.models import Taxon
from discovery.services.taxonomy import RANKS
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

# Resolver column prefix per rank.
RANK_COLS = dict(zip(RANKS, ("d", "k", "p", "c", "o", "f", "g", "s")))
COL_RANKS = {v: k for k, v in RANK_COLS.items()}
APPLIED_STATUSES = {"resolved", "resolved_partial"}
LTREE_RE = re.compile(r"[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*")

PENDING = "c.taxon_id IS NULL AND c.taxonomy_path_legacy = '' AND c.taxonomy_path <> ''"


def _sanitize(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-zA-Z0-9_]", "_", s)).strip("_")


def _informative(present: list[str]) -> str:
    """Deepest rank, skipping a genus-less placeholder species."""
    if present and present[-1] == "species" and "genus" not in present:
        present = present[:-1]
    return present[-1] if present else ""


def parse_mapping(path: Path) -> tuple[list[tuple[str, str, int | None]], list[dict]]:
    """Return ``(old_path, new_path, leaf_taxid)`` rows and the lineage rows."""
    mapping: list[tuple[str, str, int | None]] = []
    lineages: list[dict] = []
    seen: set[str] = set()
    with path.open(newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh, delimiter="\t"), start=2):
            old = row["old_taxonomy_path"]
            if old in seen:
                raise CommandError(f"line {i}: duplicate old_taxonomy_path {old!r}")
            seen.add(old)
            if row["status"] in APPLIED_STATUSES:
                new = row["canonical_taxonomy_path"]
                if not LTREE_RE.fullmatch(new):
                    raise CommandError(f"line {i}: invalid ltree path {new!r}")
                if not row["leaf_taxid"]:
                    raise CommandError(
                        f"line {i}: {row['status']} row has no leaf_taxid"
                    )
                mapping.append((old, new, int(row["leaf_taxid"])))
                lineages.append(row)
            else:
                mapping.append((old, "", None))
    return mapping, lineages


def build_taxa(lineages: list[dict], version: str) -> dict[int, Taxon]:
    """Taxon per leaf and per canonical-rank ancestor, deduplicated by taxid."""
    taxa: dict[int, Taxon] = {}
    for row in lineages:
        present = [r for r in RANKS if row[f"{RANK_COLS[r]}_taxid"]]
        labels = row["canonical_taxonomy_path"].split(".")
        if len(labels) != len(present):
            raise CommandError(
                f"{row['old_taxonomy_path']!r}: {len(labels)} path labels for "
                f"{len(present)} ranks"
            )
        cols: dict = {}
        parent = None
        for k, rank in enumerate(present):
            taxid = int(row[f"{RANK_COLS[rank]}_taxid"])
            cols[f"{rank}_name"] = row[RANK_COLS[rank]]
            cols[f"{rank}_taxid"] = taxid
            if taxid not in taxa:
                taxa[taxid] = Taxon(
                    taxid=taxid,
                    name=row[RANK_COLS[rank]],
                    rank=rank,
                    parent_taxid=parent,
                    ltree_path=".".join(labels[: k + 1]),
                    deepest_informative_rank=_informative(present[: k + 1]),
                    taxdump_version=version,
                    **cols,
                )
            parent = taxid
        leaf = int(row["leaf_taxid"])
        if leaf not in taxa:
            # Leaf below the canonical ranks (strain, no rank, ...).
            taxa[leaf] = Taxon(
                taxid=leaf,
                name=row["leaf_name"],
                rank=row["leaf_rank"],
                parent_taxid=parent,
                ltree_path=row["canonical_taxonomy_path"],
                deepest_informative_rank=COL_RANKS.get(
                    row["deepest_informative_rank"], ""
                ),
                taxdump_version=version,
                **cols,
            )
    return taxa


class Command(BaseCommand):
    help = (
        "Rewrite DashboardContig.taxonomy_path to canonical NCBI lineages and "
        "link contigs to Taxon, from a resolver mapping TSV."
    )

    def add_arguments(self, parser):
        parser.add_argument("mapping", nargs="?", type=Path, help="Resolver TSV")
        parser.add_argument(
            "--taxdump-version",
            default="",
            help="Provenance stored on Taxon rows (e.g. taxdump date + md5). "
            "Required when applying.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--allow-unmapped",
            action="store_true",
            help="Apply even if pending contigs have paths missing from the mapping "
            "(those contigs stay pending).",
        )
        parser.add_argument(
            "--export-pending",
            type=Path,
            help="Write distinct pending paths + contig counts (the resolver's "
            "input) and exit.",
        )
        parser.add_argument(
            "--revert",
            action="store_true",
            help="Restore taxonomy_path from taxonomy_path_legacy and unlink taxa.",
        )

    def handle(self, *args, **opts):
        if opts["export_pending"]:
            return self._export_pending(opts["export_pending"])
        if opts["revert"]:
            return self._revert(opts["dry_run"])
        if not opts["mapping"]:
            raise CommandError("mapping TSV is required")
        if not opts["taxdump_version"]:
            raise CommandError("--taxdump-version is required")
        self._apply(opts["mapping"], opts["taxdump_version"], opts)

    # ── export / revert ──────────────────────────────────────────────────

    def _export_pending(self, out: Path):
        with connection.cursor() as cur:
            cur.execute(
                f"SELECT c.taxonomy_path, count(*) FROM discovery_contig c "
                f"WHERE {PENDING} GROUP BY 1 ORDER BY 2 DESC"
            )
            rows = cur.fetchall()
        with out.open("w") as fh:
            for path, n in rows:
                fh.write(f"{path}\t{n}\n")
        total = sum(n for _, n in rows)
        self.stdout.write(
            f"Wrote {len(rows):,} pending paths ({total:,} contigs) → {out}"
        )

    def _revert(self, dry_run: bool):
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute(
                "UPDATE discovery_contig SET taxonomy_path = taxonomy_path_legacy, "
                "taxonomy_path_legacy = '', taxon_id = NULL "
                "WHERE taxonomy_path_legacy <> ''"
            )
            n = cur.rowcount
            if dry_run:
                transaction.set_rollback(True)
        prefix = "[dry-run] would revert" if dry_run else "Reverted"
        self.stdout.write(self.style.SUCCESS(f"{prefix} {n:,} contigs"))

    # ── apply ────────────────────────────────────────────────────────────

    def _apply(self, mapping_path: Path, version: str, opts):
        mapping, lineages = parse_mapping(mapping_path)
        taxa = build_taxa(lineages, version)
        self.stdout.write(
            f"Mapping: {len(mapping):,} paths ({len(lineages):,} resolvable), "
            f"{len(taxa):,} taxa"
        )

        with transaction.atomic(), connection.cursor() as cur:
            # ON COMMIT DROP only fires on a real commit; inside an outer
            # transaction (tests, nested calls) the table would survive.
            cur.execute("DROP TABLE IF EXISTS _taxmap")
            cur.execute(
                "CREATE TEMP TABLE _taxmap (old_path text PRIMARY KEY, "
                "new_path text NOT NULL, taxid integer) ON COMMIT DROP"
            )
            with cur.cursor.copy(
                "COPY _taxmap (old_path, new_path, taxid) FROM STDIN"
            ) as copy:
                for row in mapping:
                    copy.write_row(row)

            cur.execute(
                f"SELECT c.taxonomy_path, count(*) FROM discovery_contig c "
                f"LEFT JOIN _taxmap m ON m.old_path = c.taxonomy_path "
                f"WHERE {PENDING} AND m.old_path IS NULL GROUP BY 1 ORDER BY 2 DESC"
            )
            unmapped = cur.fetchall()
            if unmapped:
                n_un = sum(n for _, n in unmapped)
                self.stdout.write(
                    self.style.WARNING(
                        f"{len(unmapped):,} pending paths ({n_un:,} contigs) "
                        "are not in the mapping, e.g.:"
                    )
                )
                for path, n in unmapped[:20]:
                    self.stdout.write(f"  {n:>8,}  {path}")
                if not opts["allow_unmapped"]:
                    raise CommandError(
                        "Unmapped paths: run --export-pending, resolve them, and "
                        "retry (or pass --allow-unmapped)."
                    )

            cur.execute(
                f"SELECT count(*), count(*) FILTER (WHERE m.taxid IS NULL), "
                f"count(*) FILTER (WHERE m.new_path <> c.taxonomy_path) "
                f"FROM discovery_contig c JOIN _taxmap m "
                f"ON m.old_path = c.taxonomy_path WHERE {PENDING}"
            )
            n_match, n_junk, n_changed = cur.fetchone()
            self.stdout.write(
                f"Pending contigs matched: {n_match:,} — path changes: "
                f"{n_changed:,}, linked to a taxon: {n_match - n_junk:,}, "
                f"junk → empty path: {n_junk:,}"
            )
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("[dry-run] no changes written"))
                return

            Taxon.objects.bulk_create(
                list(taxa.values()),
                batch_size=5000,
                update_conflicts=True,
                unique_fields=["taxid"],
                update_fields=[
                    f.name for f in Taxon._meta.concrete_fields if f.name != "taxid"
                ],
            )
            cur.execute(
                f"UPDATE discovery_contig c SET "
                f"taxonomy_path_legacy = c.taxonomy_path, "
                f"taxonomy_path = m.new_path, taxon_id = m.taxid "
                f"FROM _taxmap m WHERE m.old_path = c.taxonomy_path AND {PENDING}"
            )
            n_updated = cur.rowcount

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {n_updated:,} contigs; upserted {len(taxa):,} taxa"
            )
        )
