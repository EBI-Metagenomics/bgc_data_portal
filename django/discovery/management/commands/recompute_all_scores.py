"""Management command to recompute all discovery scores.

By default enqueues a worker task on the ``scores`` queue.
Use ``--sync`` for synchronous execution.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recompute all discovery scores (assembly aggregates, GCF, catalogs, iBGC classes)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously instead of enqueuing a worker task",
        )

    def handle(self, *args, **options):
        if options["sync"]:
            from discovery.services.scores import recompute_all_scores

            self.stdout.write("Running score recomputation synchronously ...")
            recompute_all_scores()
            self.stdout.write(self.style.SUCCESS("Done."))
        else:
            from discovery.tasks import recompute_scores_task

            result = recompute_scores_task.enqueue()
            self.stdout.write(
                self.style.SUCCESS(f"Dispatched recompute_scores_task: {result.id}")
            )
