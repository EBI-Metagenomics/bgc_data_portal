"""Build or update the on-disk phmmer protein search index.

Usage::

    # Full rebuild from scratch (truncates the existing FASTA).
    python manage.py build_protein_search_index --rebuild

    # Incremental append of new proteins only (default).
    python manage.py build_protein_search_index

The artifacts land at ``settings.PROTEIN_SEARCH_INDEX_DIR``:

    proteins.faa       FASTA, sha256 as record id
    VERSION            monotonic integer; workers reload when it changes
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from discovery.services.protein_search.build import rebuild_index, update_index

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Build or update the on-disk phmmer protein search index."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            "--rebuild",
            action="store_true",
            help="Truncate the FASTA and re-emit every protein from the DB.",
        )
        mode.add_argument(
            "--append",
            action="store_true",
            help="Append-only update (default). Only writes proteins not already indexed.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "PROTEIN_SEARCH_INDEX_DIR", None):
            raise CommandError("PROTEIN_SEARCH_INDEX_DIR is not configured in settings.")

        if options["rebuild"]:
            self.stdout.write("Rebuilding protein search index from scratch...")
            stats = rebuild_index()
        else:
            self.stdout.write("Updating protein search index (append-only)...")
            stats = update_index()

        self.stdout.write(self.style.SUCCESS(
            f"Done in {stats.elapsed_seconds:.1f}s — "
            f"total={stats.total_in_db} added={stats.newly_added} version={stats.version}"
        ))
