"""
Management command: seed_data

Populates the database with synthetic test data using the factory_boy-based
DatasetBuilder and YAML manifests.

Usage:
    python manage.py seed_data                      # uses small.yaml
    python manage.py seed_data --manifest medium    # uses medium.yaml
    python manage.py seed_data --manifest /abs/path/to/custom.yaml
    python manage.py seed_data --clear              # wipe relevant tables first
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from tests.factories.builders import DatasetBuilder, resolve_manifest


class Command(BaseCommand):
    help = "Seed the database with synthetic BGC data from a YAML manifest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            default="small",
            metavar="NAME_OR_PATH",
            help=(
                "Manifest name ('small', 'medium') or absolute path to a YAML file. "
                "Defaults to 'small'."
            ),
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all BGC-related data before seeding.",
        )

    def handle(self, *args, **options):
        manifest = options["manifest"]

        try:
            manifest_path = resolve_manifest(manifest)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        if options["clear"]:
            self._clear_data()

        self.stdout.write(f"Seeding database from manifest: {manifest_path.name}")

        counts = DatasetBuilder(manifest_path).build()

        self.stdout.write(self.style.SUCCESS("\nSeed complete — summary:"))
        self.stdout.write(f"  Studies:    {counts['studies']}")
        self.stdout.write(f"  Assemblies: {counts['assemblies']}")
        self.stdout.write(f"  Contigs:    {counts['contigs']}")
        self.stdout.write(f"  BGCs:       {counts['bgcs']}")
        self.stdout.write(f"  Proteins:   {counts['proteins']}")
        self.stdout.write(f"  Domains:    {counts['domains']}")

    def _clear_data(self):
        from mgnify_bgcs.models import (
            Assembly,
            Bgc,
            BgcClass,
            BgcDetector,
            Biome,
            Cds,
            Contig,
            Domain,
            GeneCaller,
            Protein,
            ProteinDomain,
            Study,
        )

        self.stdout.write("Clearing existing data...")
        for model in [
            ProteinDomain,
            Cds,
            Bgc,
            Contig,
            Assembly,
            Study,
            Biome,
            BgcClass,
            BgcDetector,
            Domain,
            Protein,
            GeneCaller,
        ]:
            count, _ = model.objects.all().delete()
            self.stdout.write(f"  Deleted {count} {model.__name__} rows")
