"""Convert per-level community labels into ltree dot-paths.

A leaf path looks like ``cluster.0042.0007.0003`` — one segment per level.
Each segment is the *parent-scoped* index of the community at that level
(stable-sorted by descending size; ties broken by smallest member index).

Because Leiden labels are globally unique within a level (see ``leiden.py``)
*and* nesting is enforced top-down, we can derive the parent of every level-d
label by reading the level-(d-1) label of any of its members.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

log = logging.getLogger(__name__)


CLUSTER_SEGMENT = "cluster"


@dataclass
class GcfNode:
    """One node in the hierarchical GCF tree, ready to upsert into DashboardGCF."""

    family_path: str
    parent_path: str
    level: int
    member_indices: list[int]


def build_ltree_paths(
    levels: list[list[int]],
    bgc_ids,
) -> tuple[dict[int, str], list[GcfNode]]:
    """Map per-level Leiden labels to ltree paths and node records.

    Parameters
    ----------
    levels:
        Output of ``run_hierarchical_leiden`` — ``levels[d][v]`` is the label
        for vertex v at depth d.
    bgc_ids:
        Sequence of BGC ids in the same vertex order as ``levels``.

    Returns
    -------
    paths_per_bgc:
        ``{bgc_id: leaf_family_path}`` for every vertex.
    nodes:
        Flat list of ``GcfNode`` covering every node of the tree (roots,
        internals, leaves) at every level — ready to bulk-create
        ``DashboardGCF`` rows. ``member_indices`` are vertex indices into
        ``bgc_ids`` (not BGC ids), useful for the medoid step.
    """
    import numpy as np

    n_levels = len(levels)
    n = len(bgc_ids) if hasattr(bgc_ids, "__len__") else 0
    if n == 0 or n_levels == 0:
        return {}, []

    bgc_ids_arr = (
        bgc_ids if isinstance(bgc_ids, np.ndarray) else np.asarray(list(bgc_ids))
    )

    # ── Group vertices by (level, label) so we can size them. ───────────
    label_to_vertices: dict[tuple[int, int], list[int]] = defaultdict(list)
    for d in range(n_levels):
        for v, lbl in enumerate(levels[d]):
            label_to_vertices[(d, lbl)].append(v)

    # ── Assign parent-scoped indices per (parent_path, level) bucket. ───
    # Each parent's children are stable-sorted by (descending size, smallest
    # member index) and numbered 0, 1, 2, ... — this is the segment that
    # ends up in the path string.
    parent_children: dict[tuple[int, str], list[tuple[int, int]]] = defaultdict(list)
    # Maps (level, label) -> parent_path so we can resolve recursively.
    label_parent_path: dict[tuple[int, int], str] = {}
    label_path: dict[tuple[int, int], str] = {}

    # Process level 0 first (parent_path = "").
    level0 = sorted(
        {lbl for lbl in levels[0]},
        key=lambda lbl: (
            -len(label_to_vertices[(0, lbl)]),
            min(label_to_vertices[(0, lbl)]),
        ),
    )
    for idx, lbl in enumerate(level0):
        path = f"{CLUSTER_SEGMENT}.{idx:04d}"
        label_parent_path[(0, lbl)] = ""
        label_path[(0, lbl)] = path
        parent_children[(0, "")].append((idx, lbl))

    # Subsequent levels.
    for d in range(1, n_levels):
        # For each parent (d-1 label), collect the d-level children.
        parent_to_children: dict[int, set[int]] = defaultdict(set)
        for v in range(n):
            parent_to_children[levels[d - 1][v]].add(levels[d][v])

        for parent_lbl, child_lbls in parent_to_children.items():
            parent_path = label_path[(d - 1, parent_lbl)]
            ordered = sorted(
                child_lbls,
                key=lambda lbl: (
                    -len(label_to_vertices[(d, lbl)]),
                    min(label_to_vertices[(d, lbl)]),
                ),
            )
            for idx, lbl in enumerate(ordered):
                path = f"{parent_path}.{idx:04d}"
                label_parent_path[(d, lbl)] = parent_path
                label_path[(d, lbl)] = path
                parent_children[(d, parent_path)].append((idx, lbl))

    # ── Assemble GcfNode records and per-BGC leaf paths. ────────────────
    nodes: list[GcfNode] = []
    for (d, lbl), members_v in sorted(label_to_vertices.items()):
        nodes.append(
            GcfNode(
                family_path=label_path[(d, lbl)],
                parent_path=label_parent_path[(d, lbl)],
                level=d,
                member_indices=list(members_v),
            )
        )

    leaf_level = n_levels - 1
    paths_per_bgc: dict[int, str] = {}
    for v in range(n):
        leaf_lbl = levels[leaf_level][v]
        paths_per_bgc[int(bgc_ids_arr[v])] = label_path[(leaf_level, leaf_lbl)]

    log.info(
        "build_ltree_paths: %d nodes across %d levels (leaf paths assigned to %d BGCs)",
        len(nodes), n_levels, len(paths_per_bgc),
    )
    return paths_per_bgc, nodes
