"""Pure-function tests for ltree path encoding."""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")

from discovery.services.clustering.paths import build_ltree_paths  # noqa: E402


def test_two_level_paths_produce_expected_format():
    # 4 vertices: two coarse communities, each with two finer children.
    levels = [
        [10, 10, 20, 20],          # level 0: communities 10 and 20
        [100, 200, 300, 300],      # level 1: nested split inside each parent
    ]
    bgc_ids = [1001, 1002, 1003, 1004]
    paths_per_bgc, nodes = build_ltree_paths(levels, bgc_ids)
    # Level 0 communities are sized 2 each → numbered 0000, 0001 (stable by min idx).
    # Level 1 inside community 10: {100} (1 vertex) and {200} (1 vertex).
    # Level 1 inside community 20: {300} (2 vertices).
    leaves = set(paths_per_bgc.values())
    # 4 BGCs but two share level-1 → 3 distinct leaf paths.
    assert len(leaves) == 3
    # Each leaf path has the form cluster.NNNN.NNNN
    for path in leaves:
        parts = path.split(".")
        assert parts[0] == "cluster"
        assert len(parts) == 3
        assert all(p.isdigit() and len(p) == 4 for p in parts[1:])


def test_parent_path_consistency():
    levels = [
        [0, 0, 1, 1],
        [0, 1, 2, 2],
    ]
    bgc_ids = [10, 11, 12, 13]
    _, nodes = build_ltree_paths(levels, bgc_ids)
    # Every node with a non-empty parent_path must have a matching entry whose
    # family_path equals that parent_path.
    paths = {n.family_path for n in nodes}
    for n in nodes:
        if n.parent_path:
            assert n.parent_path in paths
            # Path is the parent's path plus a 4-digit segment.
            assert n.family_path.startswith(n.parent_path + ".")


def test_stability_across_re_runs_same_input():
    levels = [
        [0, 0, 1, 1, 1],
        [0, 1, 2, 3, 3],
    ]
    bgc_ids = [501, 502, 503, 504, 505]
    p1, _ = build_ltree_paths(levels, bgc_ids)
    p2, _ = build_ltree_paths(levels, bgc_ids)
    assert p1 == p2


def test_descending_size_numbering():
    # One large community (3 members) and one small (1 member). Large gets 0000.
    levels = [[0, 0, 0, 1]]
    bgc_ids = [1, 2, 3, 4]
    paths_per_bgc, _ = build_ltree_paths(levels, bgc_ids)
    assert paths_per_bgc[1] == "cluster.0000"
    assert paths_per_bgc[4] == "cluster.0001"


def test_empty_input():
    p, n = build_ltree_paths([], [])
    assert p == {}
    assert n == []
