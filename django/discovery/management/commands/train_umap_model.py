"""DEPRECATED: Use ``run_bgc_clustering`` instead.

This command only trained a 2D UMAP for visualization. The new
``run_bgc_clustering`` command runs the full PCA → UMAP-20d → HDBSCAN →
KNN → UMAP-2d pipeline and is the primary mechanism for GCF annotation
and visualization coordinate generation.
"""

import warnings

warnings.warn(
    "train_umap_model is deprecated. Use 'run_bgc_clustering' instead.",
    DeprecationWarning,
    stacklevel=1,
)

from django.core.management.base import BaseCommand

from discovery.tasks import train_umap_model_task


class Command(BaseCommand):
    help = "Dispatch a UMAP training job to the Celery worker"

    def add_arguments(self, parser):
        parser.add_argument(
            "--n-samples",
            type=int,
            default=50_000,
            help="Number of BGC embeddings to sample for training (default: 50000)",
        )
        parser.add_argument(
            "--stratify-by-gcf",
            action="store_true",
            help="Stratified sampling across gene_cluster_family groups",
        )
        parser.add_argument(
            "--n-neighbors",
            type=int,
            default=15,
            help="UMAP n_neighbors parameter (default: 15)",
        )
        parser.add_argument(
            "--min-dist",
            type=float,
            default=0.1,
            help="UMAP min_dist parameter (default: 0.1)",
        )
        parser.add_argument(
            "--metric",
            type=str,
            default="cosine",
            help="UMAP metric (default: cosine)",
        )
        parser.add_argument(
            "--pca-components",
            type=int,
            default=50,
            help="PCA components for dimensionality reduction before UMAP (default: 50)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="After training, transform all embeddings and update UMAP coordinates",
        )

    def handle(self, *args, **options):
        result = train_umap_model_task.apply_async(
            kwargs={
                "n_samples": options["n_samples"],
                "stratify_by_gcf": options["stratify_by_gcf"],
                "n_neighbors": options["n_neighbors"],
                "min_dist": options["min_dist"],
                "metric": options["metric"],
                "pca_components": options["pca_components"],
                "apply": options["apply"],
            },
            queue="scores",
        )
        self.stdout.write(
            self.style.SUCCESS(f"Dispatched train_umap_model_task: {result.id}")
        )
