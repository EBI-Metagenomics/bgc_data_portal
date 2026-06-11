"""Rebuild the on-demand similarity scoring cache for a ClusteringRun.

The cache (``<CLUSTERING_ARTIFACTS_DIR>/<sha[:12]>/scoring_cache/``) feeds
``/query/similar-ibgc/`` (Find similar iBGCs) and ``/query/ibgc-architecture/``
(ARCH search). It is written as a side effect of the in-portal pipeline, but
NOT by ``import_clustering_results`` (HPC handoff) — so an imported run has no
cache and those endpoints 503. This command reconstructs it from DB state.

Usage:
    manage.py rebuild_scoring_cache              # active (latest) run
    manage.py rebuild_scoring_cache --sha <sha>  # a specific run
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild the on-demand similarity scoring cache for a ClusteringRun."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sha",
            help="ClusteringRun sha256 (prefix accepted). Defaults to the "
            "latest run (the one similarity queries resolve to).",
        )

    def handle(self, *args, **options):
        from discovery.models import ClusteringRun
        from discovery.services.clustering.pipeline import (
            rebuild_scoring_cache_from_db,
        )

        sha = options.get("sha")
        if sha:
            run = ClusteringRun.objects.filter(sha256__startswith=sha).first()
            if run is None:
                raise CommandError(f"No ClusteringRun matching sha={sha}")
        else:
            run = ClusteringRun.objects.order_by("-created_at").first()
            if run is None:
                raise CommandError("No ClusteringRun exists.")

        self.stdout.write(f"Rebuilding scoring cache for run sha={run.sha256[:12]}…")
        cache_dir = rebuild_scoring_cache_from_db(run)
        if cache_dir is None:
            self.stdout.write(
                self.style.WARNING("No clusterable iBGCs — nothing written.")
            )
            return
        self.stdout.write(self.style.SUCCESS(f"Wrote scoring cache: {cache_dir}"))
