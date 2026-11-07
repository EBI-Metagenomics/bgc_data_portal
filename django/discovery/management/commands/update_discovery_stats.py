from django.core.management.base import BaseCommand
from django.db import transaction

from discovery.models import DiscoveryStats
from discovery.services.stats import generate_discovery_stats


class Command(BaseCommand):
    help = "Recompute Discovery Platform stats and append a new DiscoveryStats entry."

    def handle(self, *args, **options):
        self.stdout.write("Generating new discovery stats…", ending="\n")
        stats = generate_discovery_stats()

        with transaction.atomic():
            ds = DiscoveryStats.objects.create(stats=stats)

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ Created DiscoveryStats id={ds.pk} at {ds.created_at.isoformat()}"
            )
        )
