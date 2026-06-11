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
