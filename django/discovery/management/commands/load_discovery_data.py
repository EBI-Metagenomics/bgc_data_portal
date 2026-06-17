"""Management command to bulk-load discovery data from TSV files.

Usage::

    python manage.py load_discovery_data --data-dir /path/to/tsvs/
    python manage.py load_discovery_data --data-dir /path/to/tsvs/ --truncate
    python manage.py load_discovery_data --data-dir /path/to/tsvs/ --truncate --skip-stats
    python manage.py load_discovery_data --data-dir /path/to/tsvs/ --skip-discovery-stats

By default a platform-overview ``DiscoveryStats`` refresh is enqueued after the
load — chained onto the protein-index task so it only runs on its success.
Suppress with ``--skip-discovery-stats``. (Distinct from ``--skip-stats``, which
skips the in-process assembly-score / catalog computation inside the pipeline.)
"""

import logging
import time

from discovery.services.ingestion.loader import run_pipeline
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Bulk-load discovery platform data from a directory of TSV files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            required=True,
            help="Directory containing TSV files (detectors.tsv, assemblies.tsv, etc.)",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            default=False,
            help="TRUNCATE all discovery tables before loading (full reload).",
        )
        parser.add_argument(
            "--skip-stats",
            action="store_true",
            default=False,
            help="Skip post-load assembly score and catalog count computation.",
        )
        parser.add_argument(
            "--skip-protein-index",
            action="store_true",
            default=False,
            help="Skip enqueueing the protein search index update at the end.",
        )
        parser.add_argument(
            "--skip-discovery-stats",
            action="store_true",
            default=False,
            help="Skip enqueueing the platform-overview DiscoveryStats refresh at the end.",
        )

    def handle(self, *args, **options):
        data_dir = options["data_dir"]
        truncate = options["truncate"]
        skip_stats = options["skip_stats"]
        skip_protein_index = options["skip_protein_index"]
        skip_discovery_stats = options["skip_discovery_stats"]

        self.stdout.write(f"Loading discovery data from: {data_dir}")
        if truncate:
            self.stdout.write(
                self.style.WARNING(
                    "TRUNCATE mode: all discovery tables will be cleared first."
                )
            )

        t0 = time.perf_counter()
        run_pipeline(data_dir, truncate=truncate, skip_stats=skip_stats)
        elapsed = time.perf_counter() - t0

        self.stdout.write(self.style.SUCCESS(f"Done in {elapsed:.1f}s"))

        # Chain the DiscoveryStats refresh onto the protein-index task so it
        # only fires once that succeeds. If the protein index is skipped, the
        # stats refresh is dispatched directly after the (already-succeeded)
        # synchronous load. Both run on the default task queue.
        if not skip_protein_index:
            try:
                from discovery.tasks import update_protein_search_index_task

                # ``truncate`` means the discovery tables were wiped, so the
                # protein index must be rebuilt from scratch rather than appended.
                # The task chains the DiscoveryStats refresh itself on success
                # (no Celery canvas) when ``then_update_stats`` is set.
                async_result = update_protein_search_index_task.enqueue(
                    rebuild=truncate,
                    then_update_stats=not skip_discovery_stats,
                )
                self.stdout.write(
                    f"Enqueued protein search index update "
                    f"(task_id={async_result.id}, rebuild={truncate})"
                )
                if not skip_discovery_stats:
                    self.stdout.write(
                        "Chained DiscoveryStats refresh (runs on protein-index success)"
                    )
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not enqueue protein search index update: {exc}"
                    )
                )
        elif not skip_discovery_stats:
            try:
                from discovery.tasks import update_discovery_stats_task

                async_result = update_discovery_stats_task.enqueue()
                self.stdout.write(
                    f"Enqueued DiscoveryStats refresh (task_id={async_result.id})"
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not enqueue DiscoveryStats refresh: {exc}"
                    )
                )
