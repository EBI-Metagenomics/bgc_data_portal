"""Assign leaf family paths to non-primary BGCs against an existing ClusteringRun.

Independent of ``run_bgc_clustering``: re-run whenever new partial BGCs
land or stale assignments need refreshing. Does not reshape the hierarchy.
"""

from django.core.management.base import BaseCommand, CommandError

from discovery.models import ClusteringRun
from discovery.services.clustering import ALLOWED_SCOPES
from discovery.tasks import reclassify_bgcs_task


class Command(BaseCommand):
    help = "Assign / refresh leaf family paths for partial or non-primary BGCs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clustering-run",
            type=int,
            help="ClusteringRun pk; defaults to the most recent run",
        )
        parser.add_argument(
            "--scope",
            type=str,
            default="partial",
            choices=ALLOWED_SCOPES,
            help="Which BGCs to (re)classify (default partial)",
        )
        parser.add_argument(
            "--knn-k",
            type=int,
            default=5,
        )
        parser.add_argument(
            "--min-total-similarity",
            type=float,
            default=0.1,
            help="Minimum sum of top-K Dice required to commit an assignment",
        )
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

    def handle(self, *args, **options):
        run_pk = options.get("clustering_run")
        if run_pk is None:
            latest = ClusteringRun.objects.order_by("-created_at").first()
            if latest is None:
                raise CommandError(
                    "No ClusteringRun exists; run `run_bgc_clustering` first"
                )
            run_pk = latest.pk
            self.stdout.write(
                f"--clustering-run not given; using latest run pk={run_pk}"
            )

        kwargs = {
            "clustering_run_pk": run_pk,
            "scope": options["scope"],
            "knn_k": options["knn_k"],
            "min_total_similarity": options["min_total_similarity"],
        }
        if options["sync"]:
            self.stdout.write("Reclassifying BGCs synchronously ...")
            result = reclassify_bgcs_task.apply(kwargs=kwargs).result
            self.stdout.write(self.style.SUCCESS(f"Done: {result}"))
        else:
            res = reclassify_bgcs_task.apply_async(kwargs=kwargs, queue=options["queue"])
            self.stdout.write(
                self.style.SUCCESS(f"Dispatched reclassify_bgcs_task: {res.id}")
            )
