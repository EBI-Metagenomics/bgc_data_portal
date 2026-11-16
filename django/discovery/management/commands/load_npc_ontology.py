"""Load (or refresh) the NPClassifier ontology into the portal tables."""

from django.core.management.base import BaseCommand

from discovery.services.npc import load_npc_ontology


class Command(BaseCommand):
    help = (
        "Upsert the NPClassifier ontology vendored in common_core.npc "
        "into NpcTerm / NpcTermEdge."
    )

    def handle(self, *args, **options):
        counts = load_npc_ontology()
        self.stdout.write(self.style.SUCCESS(f"NPClassifier ontology loaded: {counts}"))
