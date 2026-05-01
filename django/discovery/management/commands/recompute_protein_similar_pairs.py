"""Build / extend the ProteinSimilarPair table via batched pgvector ANN.

Re-run this whenever new ProteinEmbedding rows land or when the floor
needs to drop. Threshold filtering at runtime (e.g. ``dice_threshold=0.9``
on a ``floor=0.7`` table) does **not** require a recompute.
"""

from django.core.management.base import BaseCommand

from discovery.tasks import recompute_protein_similar_pairs_task


class Command(BaseCommand):
    help = "Build / extend the ProteinSimilarPair table"

    def add_arguments(self, parser):
        parser.add_argument(
            "--floor",
            type=float,
            default=0.7,
            help="Minimum cosine to keep (default 0.7)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1024,
            help="Number of sha256s queried per round-trip (default 1024)",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=64,
            help="Maximum neighbours requested per protein from HNSW (default 64)",
        )
        parser.add_argument(
            "--ef-search",
            type=int,
            default=200,
            help="hnsw.ef_search session setting (default 200; higher = better recall, slower)",
        )
        parser.add_argument(
            "--no-resume",
            action="store_false",
            dest="resume",
            default=True,
            help="Wipe the table and start fresh instead of resuming",
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
        kwargs = {
            "floor": options["floor"],
            "batch_size": options["batch_size"],
            "top_k": options["top_k"],
            "ef_search": options["ef_search"],
            "resume": options["resume"],
        }
        if options["sync"]:
            self.stdout.write("Building protein pair table synchronously ...")
            result = recompute_protein_similar_pairs_task.apply(kwargs=kwargs).result
            self.stdout.write(self.style.SUCCESS(f"Done: {result}"))
        else:
            res = recompute_protein_similar_pairs_task.apply_async(
                kwargs=kwargs, queue=options["queue"]
            )
            self.stdout.write(
                self.style.SUCCESS(f"Dispatched recompute_protein_similar_pairs_task: {res.id}")
            )
