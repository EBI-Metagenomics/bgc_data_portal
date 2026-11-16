"""Artifacts produced before the CHAMOIS / ESM / UMAP removal must still load.

Two frozen fixtures under ``tests/fixtures/`` — never regenerate them with
newer code:

* ``legacy_staged/MGYG000296006_pre_removal_staged_files.tgz`` — a real staged
  bundle from the ETL before the removal (MGnify Marine Catalogue v2.0 genome
  MGYG000296006, 2026-10-16 smoke run) carrying ``cds_chemont.tsv`` and
  ``umap_x`` / ``umap_y`` columns in ``bgcs.tsv``, plus ``embeddings_bgc.tsv`` /
  ``embeddings_protein.tsv`` in the removed aggregator's format.
* ``clustering/output_v2_cosine.tar.gz`` — a schema-v2 ``bgc-cluster`` output
  tarball written by common-core before the layout was removed (with
  ``coords.parquet`` and ``umap_*`` partial columns); 24 primaries with ids
  1000–1023 and 4 partials with ids 5000–5003.
"""

from __future__ import annotations

import io
import shutil
import tarfile
from pathlib import Path

import pytest
from discovery.models import (
    ClusteringRun,
    ContigCds,
    ContigDomain,
    DashboardAssembly,
    DashboardContig,
    DashboardGCF,
    IntegratedBgc,
    SourceBgcPrediction,
)
from discovery.services.ingestion.loader import run_pipeline
from django.core.management import call_command
from django.test import override_settings

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
LEGACY_STAGED = (
    FIXTURES / "legacy_staged" / "MGYG000296006_pre_removal_staged_files.tgz"
)
V2_CLUSTERING = FIXTURES / "clustering" / "output_v2_cosine.tar.gz"
LEGACY_FILES = {"cds_chemont.tsv", "embeddings_bgc.tsv", "embeddings_protein.tsv"}


def _extract(tgz: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgz) as tf:
        tf.extractall(dest)
    return dest


def _strip_legacy(src: Path, dest: Path) -> Path:
    """Copy a staged dir without the removed files and ``umap_*`` columns."""
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.name in LEGACY_FILES:
            continue
        if f.name == "bgcs.tsv":
            lines = f.read_text().splitlines()
            header = lines[0].split("\t")
            keep = [i for i, c in enumerate(header) if c not in ("umap_x", "umap_y")]
            out = ["\t".join(row.split("\t")[i] for i in keep) for row in lines]
            (dest / f.name).write_text("\n".join(out) + "\n")
        else:
            shutil.copy2(f, dest / f.name)
    return dest


def _counts() -> dict[str, int]:
    return {
        "assemblies": DashboardAssembly.objects.count(),
        "contigs": DashboardContig.objects.count(),
        "source_bgcs": SourceBgcPrediction.objects.count(),
        "cds": ContigCds.objects.count(),
        "domains": ContigDomain.objects.count(),
    }


def test_fixtures_are_pre_removal_artifacts():
    """Guard: the fixtures really carry the removed parts."""
    with tarfile.open(LEGACY_STAGED) as tf:
        names = {Path(n).name for n in tf.getnames()}
        bgcs_header = tf.extractfile("bgcs.tsv").readline().decode()
    assert names >= LEGACY_FILES
    assert "umap_x" in bgcs_header and "umap_y" in bgcs_header
    with tarfile.open(V2_CLUSTERING) as tf:
        assert "coords.parquet" in tf.getnames()


# transaction=True: the second load TRUNCATEs, which Postgres refuses inside
# the default per-test transaction (deferred FK trigger events are pending).
@pytest.mark.django_db(transaction=True)
def test_pre_removal_staged_tarball_loads_like_a_stripped_one(tmp_path):
    legacy = _extract(LEGACY_STAGED, tmp_path / "legacy")
    stripped = _strip_legacy(legacy, tmp_path / "stripped")

    run_pipeline(legacy, truncate=False)
    legacy_counts = _counts()
    assert legacy_counts["assemblies"] == 1
    assert legacy_counts["source_bgcs"] >= 1 and legacy_counts["cds"] >= 1

    run_pipeline(stripped, truncate=True)
    assert _counts() == legacy_counts


@pytest.mark.django_db
def test_v2_clustering_tarball_imports(tmp_path):
    pytest.importorskip("pyarrow")
    from tests.factories.discovery_models import IntegratedBgcFactory

    primary_ids = list(range(1000, 1024))
    partial_ids = list(range(5000, 5004))
    for ibgc_id in primary_ids + partial_ids:
        IntegratedBgcFactory(id=ibgc_id)

    with override_settings(CLUSTERING_ARTIFACTS_DIR=tmp_path):
        out = io.StringIO()
        call_command(
            "import_clustering_results",
            str(V2_CLUSTERING),
            skip_discovery_stats=True,
            stdout=out,
        )

    run = ClusteringRun.objects.get()
    assert run.similarity_metric == "cosine_idf_enrich"
    assert DashboardGCF.objects.filter(clustering_run=run).exists()

    primaries = IntegratedBgc.objects.filter(id__in=primary_ids)
    assert primaries.count() == 24
    for ibgc in primaries:
        assert ibgc.gene_cluster_family, ibgc.id
        assert ibgc.is_partial is False
        assert ibgc.classification_run_id == run.pk

    partials = IntegratedBgc.objects.filter(id__in=partial_ids)
    assert all(p.is_partial and p.gene_cluster_family for p in partials)

    # Rollback snapshots were written with the new column set.
    assert run.ibgc_snapshots.count() == 28
