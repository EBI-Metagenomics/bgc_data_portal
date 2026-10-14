"""Rank-aware contig taxonomy: ``apply_taxonomy_mapping`` + its consumers.

Legacy ``taxonomy_path`` values are rank-less (absent ranks skipped), so
position does not identify rank — e.g. ``Bacteria.Pseudomonadati...`` puts
the kingdom where the report expected the phylum. These tests seed legacy
paths, apply a resolver-style mapping TSV, and check that the command is
idempotent/reversible and that the taxonomy tree, sunburst, report phylum
and loader read ranks from ``Taxon`` instead of position.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pytest
from discovery.models import DashboardContig, Taxon
from discovery.services.ingestion.loader import load_contigs
from discovery.services.stats import build_taxonomy_sunburst
from discovery.services.taxonomy import phylum_label, ranked_labels_by_taxon
from tests.factories.discovery_models import (
    DashboardAssemblyFactory,
    DashboardContigFactory,
)

from django.core.management import CommandError, call_command
from django.test import Client

pytestmark = pytest.mark.django_db

KINGDOM_FIRST = "Bacteria.Pseudomonadati.Pseudomonadota.Gammaproteobacteria"
OLD_NAMES = "Bacteria.Proteobacteria.Gammaproteobacteria"
JUNK = "uncultured_prokaryote"

COLS = [
    "old_taxonomy_path",
    "contig_count",
    "status",
    "canonical_taxonomy_path",
    "leaf_taxid",
    "leaf_rank",
    "leaf_name",
    "deepest_informative_rank",
]
COLS += [c for r in "dkpcofgs" for c in (r, f"{r}_taxid")]

GAMMA = {
    "d": ("Bacteria", 2),
    "k": ("Pseudomonadati", 3379134),
    "p": ("Pseudomonadota", 1224),
    "c": ("Gammaproteobacteria", 1236),
}
CANONICAL = "Bacteria.Pseudomonadati.Pseudomonadota.Gammaproteobacteria"


def _row(old, status, canonical="", leaf=None, ranks=None):
    row = dict.fromkeys(COLS, "")
    row.update(old_taxonomy_path=old, contig_count="1", status=status)
    if leaf is not None:
        row.update(
            canonical_taxonomy_path=canonical,
            leaf_taxid=str(leaf),
            leaf_rank="class",
            leaf_name="Gammaproteobacteria",
            deepest_informative_rank="c",
        )
        for col, (name, taxid) in (ranks or {}).items():
            row[col], row[f"{col}_taxid"] = name, str(taxid)
    return row


@pytest.fixture
def mapping(tmp_path) -> Path:
    path = tmp_path / "paths_resolved.tsv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t")
        w.writeheader()
        w.writerow(_row(KINGDOM_FIRST, "resolved", CANONICAL, 1236, GAMMA))
        w.writerow(_row(OLD_NAMES, "resolved", CANONICAL, 1236, GAMMA))
        w.writerow(_row(JUNK, "junk"))
    return path


@pytest.fixture
def legacy_contigs():
    asm = DashboardAssemblyFactory()
    return {
        "kingdom_first": DashboardContigFactory(
            assembly=asm, taxonomy_path=KINGDOM_FIRST
        ),
        "old_names": DashboardContigFactory(assembly=asm, taxonomy_path=OLD_NAMES),
        "junk": DashboardContigFactory(assembly=asm, taxonomy_path=JUNK),
        "empty": DashboardContigFactory(assembly=asm, taxonomy_path=""),
    }


def _apply(mapping, *extra):
    out = StringIO()
    call_command(
        "apply_taxonomy_mapping",
        str(mapping),
        "--taxdump-version",
        "test",
        *extra,
        stdout=out,
    )
    return out.getvalue()


def _refresh(contigs):
    for c in contigs.values():
        c.refresh_from_db()


# ── apply_taxonomy_mapping ───────────────────────────────────────────────


def test_dry_run_writes_nothing(mapping, legacy_contigs):
    out = _apply(mapping, "--dry-run")
    assert "Pending contigs matched: 3" in out
    _refresh(legacy_contigs)
    assert legacy_contigs["kingdom_first"].taxon_id is None
    assert legacy_contigs["old_names"].taxonomy_path == OLD_NAMES
    assert not Taxon.objects.exists()


def test_apply_canonicalises_links_and_keeps_legacy(mapping, legacy_contigs):
    _apply(mapping)
    _refresh(legacy_contigs)

    for key, old in (("kingdom_first", KINGDOM_FIRST), ("old_names", OLD_NAMES)):
        c = legacy_contigs[key]
        assert c.taxonomy_path == CANONICAL
        assert c.taxon_id == 1236
        assert c.taxonomy_path_legacy == old

    junk = legacy_contigs["junk"]
    assert (junk.taxonomy_path, junk.taxon_id, junk.taxonomy_path_legacy) == (
        "",
        None,
        JUNK,
    )
    empty = legacy_contigs["empty"]
    assert (empty.taxonomy_path, empty.taxonomy_path_legacy) == ("", "")

    # Leaf + every canonical-rank ancestor, chained by parent.
    assert set(Taxon.objects.values_list("taxid", flat=True)) == {
        2,
        3379134,
        1224,
        1236,
    }
    phylum = Taxon.objects.get(taxid=1224)
    assert (phylum.rank, phylum.parent_taxid, phylum.ltree_path) == (
        "phylum",
        3379134,
        "Bacteria.Pseudomonadati.Pseudomonadota",
    )
    assert phylum.class_taxid is None
    assert Taxon.objects.get(taxid=1236).taxdump_version == "test"


def test_apply_is_idempotent(mapping, legacy_contigs):
    _apply(mapping)
    out = _apply(mapping)
    assert "Updated 0 contigs" in out
    _refresh(legacy_contigs)
    assert legacy_contigs["old_names"].taxonomy_path_legacy == OLD_NAMES


def test_unmapped_paths_block_apply(mapping, legacy_contigs):
    DashboardContigFactory(taxonomy_path="Bacteria.Unknownia")
    with pytest.raises(CommandError, match="Unmapped paths"):
        _apply(mapping)
    assert not DashboardContig.objects.filter(taxon__isnull=False).exists()

    _apply(mapping, "--allow-unmapped")
    assert (
        DashboardContig.objects.get(taxonomy_path="Bacteria.Unknownia").taxon_id is None
    )


def test_export_pending_lists_unapplied_paths(mapping, legacy_contigs, tmp_path):
    _apply(mapping)
    DashboardContigFactory(taxonomy_path="Bacteria.Unknownia")
    out = tmp_path / "pending.tsv"
    call_command(
        "apply_taxonomy_mapping", "--export-pending", str(out), stdout=StringIO()
    )
    assert out.read_text() == "Bacteria.Unknownia\t1\n"


def test_revert_restores_legacy_paths(mapping, legacy_contigs):
    _apply(mapping)
    call_command("apply_taxonomy_mapping", "--revert", stdout=StringIO())
    _refresh(legacy_contigs)
    assert legacy_contigs["kingdom_first"].taxonomy_path == KINGDOM_FIRST
    assert legacy_contigs["junk"].taxonomy_path == JUNK
    assert not DashboardContig.objects.filter(taxon__isnull=False).exists()
    assert not DashboardContig.objects.exclude(taxonomy_path_legacy="").exists()


def test_invalid_ltree_in_mapping_is_rejected(tmp_path, legacy_contigs):
    path = tmp_path / "bad.tsv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t")
        w.writeheader()
        w.writerow(_row(OLD_NAMES, "resolved", "Bacteria.Pseudo monadota", 1236, GAMMA))
    with pytest.raises(CommandError, match="invalid ltree"):
        _apply(path)


# ── consumers ────────────────────────────────────────────────────────────


def test_phylum_comes_from_taxon_not_position(mapping, legacy_contigs):
    c = legacy_contigs["kingdom_first"]
    # Before: positional guess reads the kingdom as the phylum.
    assert phylum_label(c.taxonomy_path, None, {}) == "Pseudomonadati"
    _apply(mapping)
    c.refresh_from_db()
    lookup = ranked_labels_by_taxon([c.taxon_id])
    assert phylum_label(c.taxonomy_path, c.taxon_id, lookup) == "Pseudomonadota"


def test_sunburst_merges_naming_eras_with_real_ranks(mapping, legacy_contigs):
    _apply(mapping)
    rows = DashboardContig.objects.exclude(taxonomy_path="").values_list(
        "taxonomy_path", "taxon_id"
    )
    nodes = {n["id"]: n for n in build_taxonomy_sunburst((p, t, 1) for p, t in rows)}
    assert set(nodes) == {
        "domain:Bacteria",
        "kingdom:Pseudomonadati",
        "phylum:Pseudomonadota",
        "class:Gammaproteobacteria",
    }
    assert nodes["phylum:Pseudomonadota"]["count"] == 2
    assert nodes["phylum:Pseudomonadota"]["parent"] == "kingdom:Pseudomonadati"


def test_taxonomy_tree_endpoint_returns_ranks_and_paths(mapping, legacy_contigs):
    _apply(mapping)
    resp = Client().get("/api/discovery/filters/taxonomy/")
    assert resp.status_code == 200
    (domain,) = resp.json()
    assert (domain["name"], domain["rank"], domain["path"], domain["count"]) == (
        "Bacteria",
        "domain",
        "Bacteria",
        2,
    )
    phylum = domain["children"][0]["children"][0]
    assert (phylum["rank"], phylum["path"]) == (
        "phylum",
        "Bacteria.Pseudomonadati.Pseudomonadota",
    )


def test_loader_keeps_canonical_path_of_linked_contigs(
    mapping, legacy_contigs, tmp_path
):
    _apply(mapping)
    c = legacy_contigs["old_names"]
    asm = c.assembly
    (tmp_path / "contigs.tsv").write_text(
        "assembly_accession\tsequence_sha256\taccession\tlength\ttaxonomy_path\n"
        f"{asm.assembly_accession}\t{c.sequence_sha256}\t{c.accession}\t1\t{OLD_NAMES}\n"
    )
    lookup = {asm.assembly_accession: asm.id}

    load_contigs(tmp_path, lookup)
    c.refresh_from_db()
    assert (c.taxonomy_path, c.taxon_id) == (CANONICAL, 1236)

    load_contigs(tmp_path, lookup, retaxonomy=True)
    c.refresh_from_db()
    assert (c.taxonomy_path, c.taxon_id, c.taxonomy_path_legacy) == (
        OLD_NAMES,
        None,
        "",
    )
