"""Build a frozen ``DomainEnrichment`` table version (ADR 0003).

Run deliberately, never as part of ingestion: a new version means a new
clustering run and a fresh benchmark check. Learn it on genome catalogues
(and BacDive); MIBiG and ``MGnify_Assemblies_v5`` are refused.

    manage.py build_domain_enrichment --enrichment-version v1 \\
        --datasets <catalogue source> [<catalogue source> …] [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from discovery.services.clustering.membership import (
    DEFAULT_DOMAIN_SOURCES,
    VOCAB_IPR_GAPFILLED,
    VOCABS,
)


class Command(BaseCommand):
    help = (
        "Learn the BGC-core vs flank domain enrichment weights on the given "
        "assembly sources and store them as a new DomainEnrichment version."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            # Not ``--version``: BaseCommand reserves it.
            "--enrichment-version",
            dest="enrichment_version",
            required=True,
            help="Version label for the new table, e.g. v1 (must not exist yet).",
        )
        parser.add_argument(
            "--datasets",
            nargs="+",
            required=True,
            help="AssemblySource names to learn on (genome catalogues).",
        )
        parser.add_argument(
            "--domain-sources",
            nargs="+",
            default=list(DEFAULT_DOMAIN_SOURCES),
            help="Base-vocabulary ref_db sources (default PFAM NCBIFAM TIGRFAM).",
        )
        parser.add_argument(
            "--vocab",
            choices=VOCABS,
            default=VOCAB_IPR_GAPFILLED,
            help="Label vocabulary; must match the clustering runs that use it.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count and print the weight distribution; write nothing.",
        )

    def handle(self, *args, **options):
        import numpy as np

        from discovery.models import AssemblySource, DomainEnrichment
        from discovery.services.clustering.enrichment import (
            build_enrichment_counts,
            check_datasets,
            save_enrichment_table,
        )

        version = options["enrichment_version"]
        try:
            datasets = check_datasets(options["datasets"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        known = set(
            AssemblySource.objects.filter(name__in=datasets).values_list(
                "name", flat=True
            )
        )
        missing = sorted(set(datasets) - known)
        if missing:
            raise CommandError(f"Unknown assembly sources: {missing}")
        if DomainEnrichment.objects.filter(version=version).exists():
            raise CommandError(
                f"DomainEnrichment version {version!r} already exists; "
                "versions are frozen — choose a new one."
            )

        try:
            counts = build_enrichment_counts(
                datasets=datasets,
                sources=[s.upper() for s in options["domain_sources"]],
                vocab=options["vocab"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        table = counts.table()
        w = np.asarray([row[3] for row in table])
        q = np.round(np.quantile(w, [0.05, 0.25, 0.5, 0.75, 0.95]), 3).tolist()
        self.stdout.write(
            f"version={version} vocab={options['vocab']} datasets={list(datasets)}\n"
            f"  core CDS:  {counts.n_core}\n"
            f"  flank CDS: {counts.n_flank}\n"
            f"  labels:    {len(table)}\n"
            f"  weight quantiles (5/25/50/75/95%): {q}\n"
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: nothing written."))
            return

        n = save_enrichment_table(
            version, counts, vocab=options["vocab"], datasets=datasets
        )
        self.stdout.write(
            self.style.SUCCESS(f"Saved DomainEnrichment {version}: {n} labels")
        )
