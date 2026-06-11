"""Rewrite GCF ltree paths to the compact canonical form.

``cluster.0042.0007.0003`` → ``42.7.3``: drop the ``cluster`` prefix and the
zero-padding so the same string the UI shows is the one stored everywhere.
The clustering pipeline now emits this form directly (see
``services/clustering/paths.py`` and ``common_core.clustering.scoring``); this
migration brings any already-clustered rows in line.

Both directions are idempotent — they only touch rows still in the other
format — so re-running, or running against a half-migrated DB, is safe.
"""

from __future__ import annotations

from django.db import migrations

BATCH = 5_000

# (model, field) pairs holding a GCF ltree path.
TARGETS = [
    ("IntegratedBgc", "gene_cluster_family"),
    ("DashboardGCF", "family_path"),
    ("DashboardGCF", "parent_path"),
    ("IbgcClusteringSnapshot", "gene_cluster_family"),
]


def _compact(path: str) -> str:
    """``cluster.0042.0007.0003`` → ``42.7.3`` (no-op if already compact)."""
    if not path:
        return path
    if path == "cluster":
        return ""
    if path.startswith("cluster."):
        path = path[len("cluster.") :]
    segs = path.split(".")
    return ".".join(str(int(p)) if p.isdigit() else p for p in segs)


def _expand(path: str) -> str:
    """``42.7.3`` → ``cluster.0042.0007.0003`` (no-op if already prefixed)."""
    if not path:
        return path
    if path.startswith("cluster"):
        return path
    segs = path.split(".")
    padded = ".".join(f"{int(p):04d}" if p.isdigit() else p for p in segs)
    return f"cluster.{padded}"


def _rewrite(apps, transform, only_prefixed: bool):
    for model_name, field in TARGETS:
        Model = apps.get_model("discovery", model_name)
        qs = Model.objects.exclude(**{field: ""})
        # Touch only rows still in the source format.
        qs = qs.filter(**{f"{field}__startswith": "cluster"}) if only_prefixed \
            else qs.exclude(**{f"{field}__startswith": "cluster"})

        batch = []
        for obj in qs.only("pk", field).iterator(chunk_size=BATCH):
            new = transform(getattr(obj, field))
            if new != getattr(obj, field):
                setattr(obj, field, new)
                batch.append(obj)
            if len(batch) >= BATCH:
                Model.objects.bulk_update(batch, [field], batch_size=BATCH)
                batch = []
        if batch:
            Model.objects.bulk_update(batch, [field], batch_size=BATCH)


def forward(apps, schema_editor):
    _rewrite(apps, _compact, only_prefixed=True)


def backward(apps, schema_editor):
    _rewrite(apps, _expand, only_prefixed=False)


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
