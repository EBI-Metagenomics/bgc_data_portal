"""Catalog tables with precomputed iBGC counts and the platform-overview snapshots."""

from django.db import models


class DashboardBgcClass(models.Model):
    """BGC classification label with precomputed iBGC count."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    bgc_count = models.IntegerField(
        default=0,
        help_text="Number of iBGCs in this class (column name kept for API parity)",
    )

    class Meta:
        db_table = "discovery_bgc_class"

    def __str__(self):
        return self.name


class DashboardDomain(models.Model):
    """Domain catalog entry with precomputed iBGC count."""

    id = models.AutoField(primary_key=True)
    acc = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    ref_db = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True, default="")
    bgc_count = models.IntegerField(
        default=0,
        help_text="Number of iBGCs whose domains include this acc (column name kept for API parity)",
    )

    class Meta:
        db_table = "discovery_domain"
        indexes = [
            models.Index(fields=["-bgc_count"], name="idx_dd_count_desc"),
        ]

    def __str__(self):
        return f"{self.acc} ({self.name})"


class DiscoveryStats(models.Model):
    """Append-only snapshot of high-level Discovery Platform counts."""

    id = models.AutoField(primary_key=True)
    stats = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovery_stats"
        ordering = ["-created_at"]

    def __str__(self):
        return f"DiscoveryStats id={self.pk} at {self.created_at.isoformat()}"
