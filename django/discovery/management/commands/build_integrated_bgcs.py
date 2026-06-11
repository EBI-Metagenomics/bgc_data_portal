"""Rebuild the IntegratedBgc table.

This is the pre-clustering step that consolidates latest-version
``SourceBgcPrediction`` rows into the integrated set: validated standalones,
GECCO + SanntiS predictions merged on transitive interval overlap, and
antiSMASH calls (absorbed when they overlap an existing iBGC, standalone
otherwise).
"""

from django.core.management.base import BaseCommand

from discovery.tasks import build_integrated_bgcs_task, update_discovery_stats_task


class Command(BaseCommand):
    help = "Rebuild the IntegratedBgc table from latest-version source predictions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously in the current process instead of dispatching to Celery",
        )
        parser.add_argument(
            "--queue",
            type=str,
            default="scores",
        )
        parser.add_argument(
            "--skip-discovery-stats",
            action="store_true",
            help="Skip enqueueing the platform-overview DiscoveryStats refresh afterwards.",
        )

    def handle(self, *args, **options):
        queue = options["queue"]
        skip_discovery_stats = options["skip_discovery_stats"]

        if options["sync"]:
            self.stdout.write("Building IntegratedBgc table synchronously ...")
            result = build_integrated_bgcs_task.apply().result
            self.stdout.write(self.style.SUCCESS(f"Done: {result}"))
            # The sync build raised on failure, so reaching here means success;
            # dispatch the stats refresh asynchronously as requested.
            if not skip_discovery_stats:
                self._enqueue_stats(queue)
        else:
            # Chain stats onto the build task so it only fires on its success.
            stats_link = (
                None if skip_discovery_stats
                else update_discovery_stats_task.si().set(queue=queue)
            )
            res = build_integrated_bgcs_task.apply_async(queue=queue, link=stats_link)
            self.stdout.write(
                self.style.SUCCESS(f"Dispatched build_integrated_bgcs_task: {res.id}")
            )
            if stats_link is not None:
                self.stdout.write(
                    "Chained DiscoveryStats refresh (runs on build success)"
                )

    def _enqueue_stats(self, queue):
        try:
            res = update_discovery_stats_task.apply_async(queue=queue)
            self.stdout.write(
                self.style.SUCCESS(f"Enqueued DiscoveryStats refresh: {res.id}")
            )
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Could not enqueue DiscoveryStats refresh: {exc}"
            ))
