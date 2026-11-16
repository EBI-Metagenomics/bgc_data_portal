"""Projection tests for the asset-upload pipeline.

These exercise ``build_virtual_ibgcs`` — the step that reuses the shared
``integrated._build_ibgcs_for_contig`` overlap-chain helper. They exist to
catch call-contract drift: the helper's row shape, arity, and return tuple
have changed before without the asset path being updated, which only
surfaced at runtime as ``unexpected keyword argument`` / unpack errors.
"""

from __future__ import annotations

from discovery.services.asset_upload.parse import parse_asset_tar
from discovery.services.asset_upload.project import build_virtual_ibgcs
from discovery.services.asset_upload.validate import inspect_tarball

# Reuse the parse-test fixture builder so the two stages stay in lockstep.
from tests.unit.test_asset_upload_parse import _full_tarball


def _build_from_tarball(raw: bytes):
    return build_virtual_ibgcs(parse_asset_tar(inspect_tarball(raw)))


def test_build_virtual_ibgcs_merges_overlapping_predictions():
    """A GECCO + overlapping antiSMASH prediction collapse into one iBGC.

    The GECCO row forms a merge chain; the antiSMASH row overlaps it and is
    absorbed. The absorbed prediction must still be folded in as a member so
    its CDS / domains belong to the virtual iBGC.
    """
    vibgcs = _build_from_tarball(_full_tarball())

    assert len(vibgcs) == 1
    vb = vibgcs[0]
    assert vb.neg_id == -1
    assert set(vb.source_tools) == {"GECCO", "antiSMASH"}
    # GECCO member + absorbed antiSMASH member both present.
    assert len(vb.member_bgcs) == 2
    # Interval is the widened GECCO chain (antiSMASH is absorbed, not widening).
    assert vb.start_position == 100
    assert vb.end_position == 500


def test_build_virtual_ibgcs_assigns_unique_negative_ids():
    vibgcs = _build_from_tarball(_full_tarball())
    ids = [vb.neg_id for vb in vibgcs]
    assert all(i < 0 for i in ids)
    assert len(ids) == len(set(ids))


def test_uploaded_partial_flag_is_replaced_by_the_gene_margin_rule():
    """The upload's ``is_partial`` is ignored: an edge call that touches no
    contig base but has a truncated edge gene becomes partial, and an
    interior call flagged partial by the uploader is cleared."""
    from discovery.services.asset_upload.schemas import (
        AssetAssembly,
        AssetBgc,
        AssetCds,
        AssetContig,
        AssetData,
        AssetDetector,
    )

    sha = "a" * 64
    edge = AssetBgc(sha, "SanntiS v1", 300, 5_000, is_partial=False)
    mid = AssetBgc(sha, "SanntiS v1", 50_000, 54_000, is_partial=True)
    cds = [
        AssetCds(edge.key, f"e{i}", s, s + 899, 1)
        for i, s in enumerate((0, 1_000, 2_000, 3_000, 4_000))
    ] + [
        AssetCds(mid.key, f"m{i}", s, s + 899, 1)
        for i, s in enumerate((50_000, 51_000, 52_000, 53_000))
    ]
    data = AssetData(
        assemblies=[AssetAssembly("ASM1")],
        contigs=[AssetContig("ASM1", sha, "ctg1", length=100_000)],
        detectors=[AssetDetector("SanntiS v1", "SanntiS", "1")],
        bgcs=[edge, mid],
        cds=cds,
    )
    by_start = {vb.start_position: vb for vb in build_virtual_ibgcs(data)}
    assert by_start[300].is_partial is True
    assert by_start[50_000].is_partial is False
