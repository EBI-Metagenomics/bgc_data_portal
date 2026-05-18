from django.core.management.base import BaseCommand

from discovery.models import BgcDomain
from discovery.services.go_slim import go_slim_for

BATCH_SIZE = 5000


class Command(BaseCommand):
    help = (
        "Backfill BgcDomain.go_slim from the bundled pfam2goSlim.json mapping. "
        "Ingestion and asset projection now populate go_slim inline at write "
        "time; run this command after a mapping refresh or to repair rows "
        "ingested before that wiring was in place."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing to the database.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=f"Number of domains to update per batch (default: {BATCH_SIZE}).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        total = BgcDomain.objects.count()
        self.stdout.write(f"Total BgcDomain records: {total:,}")

        if dry_run:
            mismatched = 0
            for domain in BgcDomain.objects.only("domain_acc", "go_slim").iterator(
                chunk_size=batch_size
            ):
                if domain.go_slim != go_slim_for(domain.domain_acc):
                    mismatched += 1
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] Would update go_slim for {mismatched:,} / {total:,} domains"
                )
            )
            return

        updated = 0
        batch: list[BgcDomain] = []

        for domain in BgcDomain.objects.only("id", "domain_acc", "go_slim").iterator(
            chunk_size=batch_size
        ):
            slim = go_slim_for(domain.domain_acc)
            if domain.go_slim != slim:
                domain.go_slim = slim
                batch.append(domain)

            if len(batch) >= batch_size:
                BgcDomain.objects.bulk_update(batch, ["go_slim"])
                updated += len(batch)
                batch = []
                self.stdout.write(f"  … {updated:,} updated", ending="\r")

        if batch:
            BgcDomain.objects.bulk_update(batch, ["go_slim"])
            updated += len(batch)

        self.stdout.write(
            self.style.SUCCESS(f"\n✔ Updated go_slim on {updated:,} BgcDomain records")
        )
