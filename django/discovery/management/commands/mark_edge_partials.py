"""Recompute ``SourceBgcPrediction.is_partial`` with the gene-margin edge rule.

``build_integrated_bgcs`` runs this first with the default margin, so a normal
load → build cycle needs no extra step. Use the command to preview
(``--dry-run``) or to apply a different margin before exporting a clustering run.
See ``discovery/services/ingestion/edge_partial.py`` for the rule.
"""

from django.core.management.base import BaseCommand

from discovery.services.ingestion.edge_partial import (
    DEFAULT_GENE_MARGIN,
    mark_edge_partials,
)


class Command(BaseCommand):
    help = (
        "Recompute source-prediction contig-edge (is_partial) flags from gene geometry"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--gene-margin",
            type=int,
            default=DEFAULT_GENE_MARGIN,
            help=(
                "Complete genes of slack still counted as edge "
                f"(default {DEFAULT_GENE_MARGIN}; 0 = only when no complete gene fits)."
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Report counts, change nothing."
        )

    def handle(self, *args, **options):
        r = mark_edge_partials(
            gene_margin=options["gene_margin"], dry_run=options["dry_run"]
        )
        self.stdout.write(
            f"gene_margin={r['gene_margin']} dry_run={r['dry_run']} changed={r['changed']:,}"
        )
        self.stdout.write("tool\tcalls\tpartial_before\tpartial_after\tset\tcleared")
        for tool, c in r["by_tool"].items():
            self.stdout.write(
                f"{tool}\t{c['calls']}\t{c['partial_before']}\t{c['partial_after']}"
                f"\t{c['set']}\t{c['cleared']}"
            )
