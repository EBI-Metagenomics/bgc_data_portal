"""Lock the PFAM/NCBIFAM clustering filter contract.

The Discovery dashboard ingests domains from every ref_db that
InterProScan + Pfam scans emit, but the composite-Dice clustering, the
pooled positional architecture, the asset-upload similarity projection,
and the architecture-based query path all restrict to ``PFAM`` +
``NCBIFAM``. Loosening that filter would silently change clustering
membership, similarity scores, and the surfaced architecture. This test
pins the default at the four canonical entry points so the next refactor
trips over it before users do.
"""

from __future__ import annotations

from discovery.services.asset_upload.matrices import (
    DEFAULT_DOMAIN_SOURCES as ASSET_DEFAULTS,
)
from discovery.services.clustering.membership import (
    DEFAULT_DOMAIN_SOURCES as MEMBERSHIP_DEFAULTS,
)
from discovery.services.clustering.pipeline import (
    DEFAULT_DOMAIN_SOURCES as PIPELINE_DEFAULTS,
)

PFAM_NCBIFAM = ("PFAM", "NCBIFAM", "TIGRFAM")


def test_clustering_pipeline_default_sources_unchanged():
    assert tuple(PIPELINE_DEFAULTS) == PFAM_NCBIFAM


def test_clustering_membership_default_sources_unchanged():
    assert tuple(MEMBERSHIP_DEFAULTS) == PFAM_NCBIFAM


def test_asset_matrix_default_sources_unchanged():
    assert tuple(ASSET_DEFAULTS) == PFAM_NCBIFAM


def test_architecture_module_default_sources_unchanged():
    """Pooled positional architecture (used by ibgc_detail / bgc_detail and
    the architecture-search query) imports its default from the
    clustering.membership module."""
    from discovery.services import architecture as arch_mod

    assert tuple(arch_mod.DEFAULT_DOMAIN_SOURCES) == PFAM_NCBIFAM


# ── ADR 0003: the defaults stay the original binary-Dice behaviour ─────────
# Rollback to an older run (and any caller that doesn't opt in) must keep
# scoring exactly as before: Dice on the IPR-projected vocabulary, prune 0.05,
# projection floor 0.1.


def test_similarity_defaults_are_dice_on_ipr_projected():
    import inspect

    from discovery.models import ClusteringRun
    from discovery.services.asset_upload.matrices import (
        build_asset_adjacency_pair_matrix,
        build_asset_domain_matrix,
    )
    from discovery.services.clustering.adjacency import (
        build_ibgc_adjacency_pair_matrix,
    )
    from discovery.services.clustering.bgc_similarity import (
        compute_composite_similarity,
        compute_composite_similarity_block,
    )
    from discovery.services.clustering.membership import build_ibgc_domain_matrix
    from discovery.services.clustering.pipeline import run_clustering_pipeline

    def default(fn, name):
        return inspect.signature(fn).parameters[name].default

    for fn in (
        build_ibgc_domain_matrix,
        build_ibgc_adjacency_pair_matrix,
        build_asset_domain_matrix,
        build_asset_adjacency_pair_matrix,
    ):
        assert default(fn, "vocab") == "IPR_PROJECTED", fn.__name__
    for fn in (compute_composite_similarity, compute_composite_similarity_block):
        assert default(fn, "metric") == "dice", fn.__name__
    assert default(run_clustering_pipeline, "similarity_metric") == "dice"
    assert default(run_clustering_pipeline, "domain_vocab") == "IPR_PROJECTED"
    assert default(run_clustering_pipeline, "prune_below") == 0.05
    assert default(run_clustering_pipeline, "min_projection_similarity") == 0.1

    fields = {f.name: f for f in ClusteringRun._meta.get_fields()}
    assert fields["similarity_metric"].default == "dice"
    assert fields["prune_below"].default == 0.05
    assert fields["min_projection_similarity"].default == 0.1
