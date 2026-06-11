"""End-to-end clustering: ingest → build iBGCs → cluster → reclassify partials.

Builds a deterministic two-family corpus (5 iBGCs sharing one PFAM signature
set, 5 sharing a disjoint set, plus 3 partial iBGCs) through the real loader,
then drives the domain+adjacency hierarchical-CPM-Leiden pipeline and the KNN
partial-projection step. Asserts the contract the dashboard relies on:

  * a ``ClusteringRun`` is persisted and every clusterable iBGC gets a leaf
    ``gene_cluster_family`` path + UMAP coords
  * the run's artifacts + scoring cache land under ``CLUSTERING_ARTIFACTS_DIR``
  * partial-only iBGCs are excluded from community detection, then projected
    onto a family by ``reclassify_bgcs`` (``umap_projected=True``)

Requires igraph/leidenalg/umap, so it skips in the plain web image and runs
in the worker/ml image.
"""

from __future__ import annotations

import pytest

pytest.importorskip("igraph")
pytest.importorskip("leidenalg")

from pathlib import Path

from discovery.models import (
    ClusteringRun,
    DashboardGCF,
    IntegratedBgc,
    SourceBgcPrediction,
)
from discovery.services.clustering.integrated import build_integrated_bgcs
from discovery.services.clustering.pipeline import run_clustering_pipeline
from discovery.services.clustering.reclassify import (
    SCOPE_ALL_NON_PRIMARY,
    reclassify_bgcs,
)
from discovery.services.ingestion.loader import run_pipeline

from django.db.models import Q
from django.test import override_settings

FAMILY_A = ["PF0A001", "PF0A002", "PF0A003"]
FAMILY_B = ["PF0B001", "PF0B002", "PF0B003"]

# (contig index, family domains, is_partial, is_validated)
_CORPUS = (
    [(i, FAMILY_A, False, i == 0) for i in range(0, 5)]  # 5 family-A (one validated)
    + [(i, FAMILY_B, False, False) for i in range(5, 10)]  # 5 family-B
    + [(i, FAMILY_A, True, False) for i in range(10, 13)]  # 3 partial (family-A)
)


def _bool(v: bool) -> str:
    return "true" if v else "false"


def _write_corpus(data_dir: Path) -> None:
    """Write a TSV package: one antiSMASH iBGC per contig, 3 CDS + 3 domains."""
    (data_dir / "detectors.tsv").write_text(
        "name\ttool\tversion\nantiSMASH v1\tantiSMASH\t1.0\n"
    )
    (data_dir / "assemblies.tsv").write_text(
        "assembly_accession\torganism_name\tsource\tassembly_type\tbiome_path\n"
        "GCA_000001.1\tTest organism\tdemo\t2\troot.Environmental\n"
    )

    contigs = ["assembly_accession\tsequence_sha256\taccession\tlength\n"]
    bgcs = [
        "contig_sha256\tdetector_name\tstart_position\tend_position\t"
        "is_partial\tis_validated\n"
    ]
    cds = [
        "contig_sha256\tstart_position\tend_position\tstrand\t"
        "protein_id_str\tprotein_length\n"
    ]
    domains = [
        "contig_sha256\tprotein_id_str\tdomain_acc\tdomain_name\tref_db\t"
        "start_position\tend_position\tscore\n"
    ]

    cds_spans = [(1100, 1400), (1600, 1900), (2100, 2400)]
    for idx, fam, is_partial, is_validated in _CORPUS:
        sha = f"{idx:064x}"
        acc = f"contig_{idx}"
        contigs.append(f"GCA_000001.1\t{sha}\t{acc}\t20000\n")
        bgcs.append(
            f"{sha}\tantiSMASH v1\t1000\t5000\t{_bool(is_partial)}\t"
            f"{_bool(is_validated)}\n"
        )
        for j, (start, end) in enumerate(cds_spans):
            pid = f"{acc}_p{j}"
            cds.append(f"{sha}\t{start}\t{end}\t1\t{pid}\t100\n")
            domains.append(
                f"{sha}\t{pid}\t{fam[j]}\t{fam[j]} domain\tPFAM\t1\t100\t1e-30\n"
            )

    (data_dir / "contigs.tsv").write_text("".join(contigs))
    (data_dir / "bgcs.tsv").write_text("".join(bgcs))
    (data_dir / "cds.tsv").write_text("".join(cds))
    (data_dir / "domains.tsv").write_text("".join(domains))


def _partition_ibgc_ids():
    """Return (primary_ids, partial_ids) by source-prediction membership."""
    primary = set(
        SourceBgcPrediction.objects.filter(integrated_bgc__isnull=False)
        .filter(Q(is_partial=False) | Q(is_validated=True))
        .values_list("integrated_bgc_id", flat=True)
    )
    everything = set(IntegratedBgc.objects.values_list("id", flat=True))
    return primary, everything - primary


@pytest.mark.django_db
def test_clustering_classifies_primaries_then_projects_partials(tmp_path):
    artifacts_root = tmp_path / "clustering_artifacts"

    _write_corpus(tmp_path)
    run_pipeline(tmp_path, truncate=False, skip_stats=True)
    build_result = build_integrated_bgcs()

    # 13 iBGCs total (10 primary, 3 partial), all standalone antiSMASH.
    assert build_result["n_ibgcs"] == 13
    primary_ids, partial_ids = _partition_ibgc_ids()
    assert len(primary_ids) == 10
    assert len(partial_ids) == 3

    with override_settings(CLUSTERING_ARTIFACTS_DIR=artifacts_root):
        result = run_clustering_pipeline(
            domain_sources=["PFAM"],
            apply=True,
            score_ibgcs=True,
            seed=42,
        )

        # ── Run row + counts ──────────────────────────────────────────────
        assert "error" not in result, result
        assert result["n_ibgcs"] == 10
        assert ClusteringRun.objects.count() == 1
        run = ClusteringRun.objects.get(pk=result["run_pk"])
        assert run.sha256 == result["sha256"]
        assert result["n_leaf_communities"] >= 1

        # ── Every clusterable iBGC got a leaf path + coords ───────────────
        primaries = IntegratedBgc.objects.filter(id__in=primary_ids)
        assert primaries.count() == 10
        for ibgc in primaries:
            assert ibgc.gene_cluster_family, ibgc.accession
            assert ibgc.umap_x is not None and ibgc.umap_y is not None
            assert ibgc.classification_run_id == run.pk
            assert ibgc.umap_projected is False

        # Domain-family separation: the two disjoint signature sets must land
        # in different leaf GCFs. Derive family from each iBGC's domains via
        # the contig→CDS→domain join.
        fam_a_leaves = set(
            IntegratedBgc.objects.filter(
                id__in=primary_ids, contig__cds_list__domains__domain_acc="PF0A001"
            ).values_list("gene_cluster_family", flat=True)
        )
        fam_b_leaves = set(
            IntegratedBgc.objects.filter(
                id__in=primary_ids, contig__cds_list__domains__domain_acc="PF0B001"
            ).values_list("gene_cluster_family", flat=True)
        )
        assert fam_a_leaves and fam_b_leaves
        assert fam_a_leaves.isdisjoint(fam_b_leaves)

        # ── GCF hierarchy persisted ───────────────────────────────────────
        assert DashboardGCF.objects.filter(clustering_run=run).exists()

        # ── Artifacts + scoring cache on disk ─────────────────────────────
        artifacts_dir = Path(result["artifacts_dir"])
        assert artifacts_dir.is_dir()
        assert (artifacts_dir / "scoring_cache" / "M_domains.npz").exists()

        # ── Partials excluded from clustering, then projected ─────────────
        partials_pre = IntegratedBgc.objects.filter(id__in=partial_ids)
        assert all(p.classification_run_id is None for p in partials_pre)

        rc = reclassify_bgcs(
            clustering_run_pk=run.pk,
            scope=SCOPE_ALL_NON_PRIMARY,
        )
        assert rc["classified"] >= 1

        partials_post = IntegratedBgc.objects.filter(id__in=partial_ids)
        projected = [p for p in partials_post if p.umap_projected]
        assert projected, "no partial iBGC was projected"
        for p in projected:
            assert p.gene_cluster_family
            assert p.umap_x is not None and p.umap_y is not None
