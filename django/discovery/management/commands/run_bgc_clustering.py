"""Dispatch a BGC clustering run (pair-based hierarchical Leiden).

Operates only on complete BGCs (``is_partial=False``); use
``reclassify_bgcs`` for the partial / late ones.
"""

from django.core.management.base import BaseCommand

from discovery.tasks import run_bgc_clustering_task


class Command(BaseCommand):
    help = "Dispatch a pair-based hierarchical Leiden BGC clustering job to Celery"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dice-threshold",
            type=float,
            default=0.9,
            help="Cosine threshold filtered at runtime when computing Sørensen–Dice (default 0.9)",
        )
        parser.add_argument(
            "--knn-k",
            type=int,
            default=5,
            help="Top-K neighbours per BGC in the KNN graph (default 5)",
        )
        parser.add_argument(
            "--leiden-resolutions",
            type=float,
            nargs="+",
            default=[0.4, 0.8, 1.4, 2.0],
            help="Leiden resolution_parameter per nesting level (coarsest first)",
        )
        parser.add_argument(
            "--metric",
            type=str,
            default="dice",
            choices=("dice", "jaccard", "overlap"),
            help="BGC similarity metric (default dice)",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
        )
        parser.add_argument(
            "--pair-floor",
            type=float,
            default=0.7,
            help="Floor used when building ProteinSimilarPair (informational only)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Update DashboardBgc.gene_cluster_family / umap_x/y and DashboardGCF after clustering",
        )
        parser.add_argument(
            "--auto-reclassify",
            action="store_true",
            default=True,
            help="Chain reclassify_bgcs for non-primary BGCs after applying (default true)",
        )
        parser.add_argument(
            "--no-auto-reclassify",
            action="store_false",
            dest="auto_reclassify",
            help="Skip the post-clustering reclassification chain",
        )
        parser.add_argument(
            "--reclassify-scope",
            type=str,
            default="all_non_primary",
            choices=("partial", "stale", "all_non_primary"),
            help="Scope passed to reclassify_bgcs when auto-chaining",
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
            help="Celery queue name (default scores)",
        )

    def handle(self, *args, **options):
        kwargs = {
            "dice_threshold": options["dice_threshold"],
            "knn_k": options["knn_k"],
            "leiden_resolutions": options["leiden_resolutions"],
            "metric": options["metric"],
            "seed": options["seed"],
            "pair_floor": options["pair_floor"],
            "apply": options["apply"],
            "auto_reclassify": options["auto_reclassify"],
            "reclassify_scope": options["reclassify_scope"],
        }
        if options["sync"]:
            self.stdout.write("Running BGC clustering synchronously ...")
            result = run_bgc_clustering_task.apply(kwargs=kwargs).result
            self.stdout.write(self.style.SUCCESS(f"Done: {result}"))
        else:
            res = run_bgc_clustering_task.apply_async(kwargs=kwargs, queue=options["queue"])
            self.stdout.write(
                self.style.SUCCESS(f"Dispatched run_bgc_clustering_task: {res.id}")
            )
