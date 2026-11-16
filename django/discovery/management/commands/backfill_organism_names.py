"""Fill empty ``DashboardAssembly.organism_name`` values from a TSV.

The input is a TSV with ``assembly_accession`` and ``organism_name`` columns
(extra columns are ignored). Only rows whose stored name is empty are
updated, so curated names are never overwritten; ``--source`` restricts the
update to one AssemblySource. Written for the BacDive 2026-03-23 rows, whose
enrichment step looked names up by the FNA basename and left them all empty.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from discovery.models import DashboardAssembly


class Command(BaseCommand):
    help = "Fill empty assembly organism names from a TSV (assembly_accession, organism_name)."

    def add_arguments(self, parser):
        parser.add_argument("tsv", type=Path)
        parser.add_argument(
            "--source",
            default="",
            help="Only update assemblies of this AssemblySource name.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Report counts, write nothing."
        )

    def handle(self, *args, tsv: Path, source: str, dry_run: bool, **options):
        if not tsv.exists():
            raise CommandError(f"TSV not found: {tsv}")
        names: dict[str, str] = {}
        with tsv.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            missing = {"assembly_accession", "organism_name"} - set(
                reader.fieldnames or []
            )
            if missing:
                raise CommandError(f"TSV lacks columns: {sorted(missing)}")
            for row in reader:
                acc = (row["assembly_accession"] or "").strip()
                name = (row["organism_name"] or "").strip()
                if acc and name:
                    names[acc] = name

        qs = DashboardAssembly.objects.filter(
            organism_name="", assembly_accession__in=names
        )
        if source:
            qs = qs.filter(source__name=source)
        to_update = list(qs.only("id", "assembly_accession"))
        for asm in to_update:
            asm.organism_name = names[asm.assembly_accession][:255]

        empty_left = DashboardAssembly.objects.filter(organism_name="")
        if source:
            empty_left = empty_left.filter(source__name=source)
        self.stdout.write(
            f"{len(names)} names in TSV; {len(to_update)} empty assemblies to fill; "
            f"{empty_left.count() - len(to_update)} would stay empty"
            + (f" (source {source})" if source else "")
        )
        if dry_run or not to_update:
            return
        with transaction.atomic():
            DashboardAssembly.objects.bulk_update(
                to_update, ["organism_name"], batch_size=1000
            )
        self.stdout.write(self.style.SUCCESS(f"Updated {len(to_update)} assemblies"))
