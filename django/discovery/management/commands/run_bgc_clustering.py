"""Dispatch a BGC clustering run (domain+adjacency hierarchical-CPM-Leiden).

Operates on the ``IntegratedBgc`` table (run ``build_integrated_bgcs``
first, or pass ``--rebuild-ibgc`` to chain it). Partial iBGCs are
projected by the chained ``reclassify_bgcs`` step.
"""

from discovery.tasks import (
    build_integrated_bgcs_task,
    run_bgc_clustering_task,
)
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Dispatch a domain+adjacency hierarchical-CPM-Leiden BGC clustering job "
        "(reads the IntegratedBgc table; emits MIBiG validation artifacts when "
        "--apply is set)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain-sources",
            type=str,
            nargs="+",
            default=["PFAM", "NCBIFAM"],
            help="ref_db sources for domain selection (case-insensitive; default PFAM NCBIFAM)",
        )
        parser.add_argument(
            "--score-weights",
            type=float,
            nargs=2,
            default=[0.5, 0.5],
            metavar=("W_DOMAIN", "W_ADJACENCY"),
            help="Weights for composite Dice (w_domain w_adjacency; default 0.5 0.5)",
        )
        parser.add_argument(
            "--knn-k",
            type=int,
            default=None,
            help=(
                "Top-K neighbours per iBGC in the union kNN graph. "
                "If omitted, auto-picks max(5, ceil(ln(n_ibgcs)))."
            ),
        )
        parser.add_argument(
            "--leiden-resolutions",
            type=float,
            nargs="+",
            default=[0.03, 0.08, 0.15, 0.25],
            help="CPM resolution_parameter per nesting level (coarsest first)",
        )
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--similarity-metric",
            choices=("dice", "cosine_idf_enrich"),
            default="dice",
            help="iBGC similarity metric (default dice; ADR 0003: cosine_idf_enrich)",
        )
        parser.add_argument(
            "--domain-vocab",
            choices=("IPR_PROJECTED", "IPR_GAPFILLED"),
            default=None,
            help=(
                "Domain label vocabulary (default IPR_GAPFILLED for "
                "cosine_idf_enrich, IPR_PROJECTED for dice)"
            ),
        )
        parser.add_argument(
            "--enrichment-version",
            default="",
            help="DomainEnrichment version (required for cosine_idf_enrich)",
        )
        parser.add_argument("--prune-below", type=float, default=0.05)
        parser.add_argument("--min-projection-similarity", type=float, default=0.1)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist results to IntegratedBgc + DashboardGCF and emit MIBiG artifacts",
        )
        parser.add_argument(
            "--auto-reclassify",
            action="store_true",
            default=True,
            help="Chain reclassify_bgcs for non-primary iBGCs after applying (default true)",
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
            "--score-ibgcs",
            action="store_true",
            default=True,
            help=(
                "Compute iBGC novelty_score and domain_novelty inline with the "
                "clustering apply step, and chain a partial-iBGC UMAP projection "
                "task after reclassify (default true)."
            ),
        )
        parser.add_argument(
            "--no-score-ibgcs",
            action="store_false",
            dest="score_ibgcs",
            help="Skip iBGC scoring and partial-iBGC projection.",
        )
        parser.add_argument(
            "--rebuild-ibgc",
            action="store_true",
            help="Rebuild the IntegratedBgc table before clustering (chains build_integrated_bgcs)",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously in the current process instead of dispatching to a worker",
        )
        parser.add_argument(
            "--queue",
            type=str,
            default="scores",
            help="Task queue name (default scores)",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        if getattr(settings, "CLUSTERING_HPC_MODE", False):
            from django.core.management.base import CommandError

            raise CommandError(
                "CLUSTERING_HPC_MODE is True — in-portal clustering is disabled. "
                "Export inputs with `manage.py export_clustering_inputs`, run "
                "`bgc-cluster` on HPC, then import results with "
                "`manage.py import_clustering_results`. To run in-portal anyway "
                "(dev only), unset the CLUSTERING_HPC_MODE env var."
            )

        metric = options["similarity_metric"]
        if metric != "dice" and not options["enrichment_version"]:
            from django.core.management.base import CommandError

            raise CommandError(
                f"--similarity-metric {metric} needs --enrichment-version"
            )
        kwargs = {
            "similarity_metric": metric,
            "domain_vocab": options["domain_vocab"]
            or ("IPR_PROJECTED" if metric == "dice" else "IPR_GAPFILLED"),
            "enrichment_version": (
                options["enrichment_version"] if metric != "dice" else ""
            ),
            "prune_below": options["prune_below"],
            "min_projection_similarity": options["min_projection_similarity"],
            "domain_sources": [s.upper() for s in options["domain_sources"]],
            "score_weights": options["score_weights"],
            "knn_k": options["knn_k"],
            "leiden_resolutions": options["leiden_resolutions"],
            "seed": options["seed"],
            "apply": options["apply"],
            "auto_reclassify": options["auto_reclassify"],
            "reclassify_scope": options["reclassify_scope"],
            "score_ibgcs": options["score_ibgcs"],
        }
        if options["score_ibgcs"] and not options["auto_reclassify"]:
            self.stdout.write(
                self.style.WARNING(
                    "--score-ibgcs is enabled but --no-auto-reclassify was passed: "
                    "primary iBGCs will be scored inline, but partial iBGCs won't be "
                    "projected (the projection step is chained after reclassify)."
                )
            )
        queue = options["queue"]

        # --sync runs both tasks in-process and sequentially, so there is no
        # race; just dispatch them one after the other.
        if options["sync"]:
            if options["rebuild_ibgc"]:
                self.stdout.write("Rebuilding IntegratedBgc table first ...")
                ibgc_result = build_integrated_bgcs_task.call()
                self.stdout.write(self.style.SUCCESS(f"iBGC rebuild: {ibgc_result}"))
            self.stdout.write("Running BGC clustering synchronously ...")
            result = run_bgc_clustering_task.call(**kwargs)
            self.stdout.write(self.style.SUCCESS(f"Done: {result}"))
            if isinstance(result, dict) and (
                artifacts_dir := result.get("artifacts_dir")
            ):
                self.stdout.write(
                    self.style.SUCCESS(f"MIBiG analysis artifacts: {artifacts_dir}")
                )
            return

        # Async + --rebuild-ibgc: the build task chains the clustering run itself
        # so it only fires once the rebuild has succeeded. Dispatching both
        # independently races on the scores queue — the clustering captures iBGC
        # ids at the start of its run, then the rebuild deletes/recreates them,
        # and the apply-step bulk_update silently no-ops against stale ids. The
        # clustering kwargs ride along as ``then_run_clustering``.
        if options["rebuild_ibgc"]:
            async_result = build_integrated_bgcs_task.using(queue_name=queue).enqueue(
                then_run_clustering=kwargs,
                clustering_queue=queue,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dispatched build_integrated_bgcs_task: {async_result.id} "
                    "(run_bgc_clustering_task will run on success)"
                )
            )
            return

        res = run_bgc_clustering_task.using(queue_name=queue).enqueue(**kwargs)
        self.stdout.write(
            self.style.SUCCESS(f"Dispatched run_bgc_clustering_task: {res.id}")
        )
