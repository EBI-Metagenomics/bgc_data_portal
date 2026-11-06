"""Rebuild the per-iBGC NPClassifier labels from the source predictions."""

from django.core.management.base import BaseCommand

from discovery.services.npc import aggregate_ibgc_npc_labels


class Command(BaseCommand):
    help = "Rebuild IbgcNpcLabel (union of each iBGC's source-prediction labels)."

    def handle(self, *args, **options):
        n = aggregate_ibgc_npc_labels()
        self.stdout.write(self.style.SUCCESS(f"{n} iBGC NPClassifier labels written"))
