from django.core.management.base import BaseCommand
from mgnify_bgcs.tasks import calculate_aggregated_bgcs


class Command(BaseCommand):
    help = "Trigger calculation of aggregated BGCs (all contigs)"

    def handle(self, *args, **options):
        self.stdout.write("Triggering aggregated BGCs calculation for all contigs...")
        result = calculate_aggregated_bgcs.delay()
        self.stdout.write(f"Task queued with ID: {result.id}")
