"""Stable-forever accession ledger for cBGCs / iBGCs and historical aliases."""

from django.db import models


class AccessionEntityType(models.TextChoices):
    CBGC = "cbgc", "Consensus BGC"
    IBGC = "ibgc", "Integrated BGC"


class AccessionRegistry(models.Model):
    """Stable-forever accession ledger for cBGCs and iBGCs.

    One row per ever-assigned accession. Identity tuple is
    ``(entity_type, contig_accession, start_pos, end_pos)`` — the same
    entity reproduced after a rebuild reuses its accession. Accessions
    never get reassigned; when an entity disappears between rebuilds,
    ``current_cbgc`` / ``current_ibgc`` is NULLed and the accession is
    tombstoned (the resolve endpoint returns 410 for it).

    cBGC accessions: ``MGYB-XXXXXX`` (6 Crockford base32 chars).
    iBGC accessions: ``MGYB-XXXXXX-YY`` (cBGC accession + 2-char suffix).
    """

    accession = models.CharField(max_length=20, primary_key=True)
    entity_type = models.CharField(
        max_length=10,
        choices=AccessionEntityType.choices,
        db_index=True,
    )
    contig_accession = models.CharField(max_length=255, db_index=True)
    start_pos = models.IntegerField()
    end_pos = models.IntegerField()

    current_cbgc = models.ForeignKey(
        "ConsensusBgc",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registry_entries",
    )
    current_ibgc = models.ForeignKey(
        "IntegratedBgc",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registry_entries",
    )

    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_accession_registry"
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "contig_accession", "start_pos", "end_pos"],
                name="uniq_registry_identity",
            ),
        ]
        indexes = [
            models.Index(
                fields=["entity_type", "contig_accession", "start_pos", "end_pos"],
                name="idx_registry_identity",
            ),
        ]

    @property
    def is_tombstoned(self) -> bool:
        if self.entity_type == AccessionEntityType.CBGC:
            return self.current_cbgc_id is None
        return self.current_ibgc_id is None

    def __str__(self):
        return self.accession


class AccessionAlias(models.Model):
    """Historical accession aliases — old → current registry entry.

    Populated when (a) a pre-refactor ``MGYB{id:08}`` cBGC accession must
    map to a new ``MGYB-XXXXXX`` accession, and (b) any future renames.
    """

    id = models.AutoField(primary_key=True)
    alias_accession = models.CharField(max_length=50, unique=True, db_index=True)
    registry = models.ForeignKey(
        AccessionRegistry,
        on_delete=models.CASCADE,
        related_name="aliases",
    )

    class Meta:
        db_table = "discovery_accession_alias"

    def __str__(self):
        return f"{self.alias_accession} → {self.registry_id}"
