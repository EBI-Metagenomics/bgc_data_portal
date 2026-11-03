"""Loader support for ETL-harmonised taxonomy: ``taxa.tsv`` + ``contigs.tsv`` taxid.

``etl.taxonomy.harmonise_contigs`` ships canonical ``taxonomy_path`` plus a
``taxid`` per contig and the ``Taxon`` rows they point at. The loader upserts
the taxa first, then links contigs; legacy rows (no taxid) keep their old
behaviour, and a taxa.tsv that redefines stored taxa aborts.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from discovery.models import DashboardAssembly, DashboardContig, Taxon
from discovery.services.ingestion.loader import load_contigs, load_taxa, run_pipeline
from tests.factories.discovery_models import (
    DashboardAssemblyFactory,
    DashboardContigFactory,
)

from django.test import Client

pytestmark = pytest.mark.django_db

RANKS = ("domain", "kingdom", "phylum", "class", "order", "family", "genus", "species")
TAXA_COLUMNS = [
    "taxid",
    "name",
    "rank",
    "parent_taxid",
    "ltree_path",
    "deepest_informative_rank",
    "taxdump_version",
] + [c for r in RANKS for c in (f"{r}_name", f"{r}_taxid")]

CHAIN = [  # (taxid, name, rank)
    (2, "Bacteria", "domain"),
    (3379134, "Pseudomonadati", "kingdom"),
    (1224, "Pseudomonadota", "phylum"),
    (1236, "Gammaproteobacteria", "class"),
]
CANON = "Bacteria.Pseudomonadati.Pseudomonadota.Gammaproteobacteria"
VERSION = "NCBI new_taxdump test"


def _taxa_rows(rename: dict[int, str] | None = None) -> list[dict[str, str]]:
    rows, cols, parent = [], {}, ""
    for k, (taxid, name, rank) in enumerate(CHAIN):
        name = (rename or {}).get(taxid, name)
        cols[f"{rank}_name"], cols[f"{rank}_taxid"] = name, str(taxid)
        rows.append(
            {
                "taxid": str(taxid),
                "name": name,
                "rank": rank,
                "parent_taxid": parent,
                "ltree_path": ".".join(c[1] for c in CHAIN[: k + 1]),
                "deepest_informative_rank": rank,
                "taxdump_version": VERSION,
                **cols,
            }
        )
        parent = str(taxid)
    return rows


def _write(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=header,
            delimiter="\t",
            lineterminator="\n",
            restval="",
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows(rows)


def write_taxa(d: Path, rows: list[dict[str, str]] | None = None) -> None:
    _write(d / "taxa.tsv", TAXA_COLUMNS, rows if rows is not None else _taxa_rows())


CONTIG_COLS = [
    "assembly_accession",
    "sequence_sha256",
    "accession",
    "source_contig_id",
    "length",
    "taxonomy_path",
    "taxid",
]


def write_contigs(d: Path, rows: list[dict[str, str]], header=CONTIG_COLS) -> None:
    _write(d / "contigs.tsv", header, rows)


def _contig(asm: str, n: int, path: str = "", taxid: str = "") -> dict[str, str]:
    return {
        "assembly_accession": asm,
        "sequence_sha256": f"{asm}-{n}",
        "accession": f"{asm}_c{n}",
        "source_contig_id": "",
        "length": "1000",
        "taxonomy_path": path,
        "taxid": taxid,
    }


# ── load_taxa ────────────────────────────────────────────────────────────


def test_load_taxa_upserts_rows_and_nulls_blank_ranks(tmp_path):
    write_taxa(tmp_path)
    assert load_taxa(tmp_path) == 4
    phylum = Taxon.objects.get(taxid=1224)
    assert (phylum.name, phylum.rank, phylum.parent_taxid) == (
        "Pseudomonadota",
        "phylum",
        3379134,
    )
    assert phylum.ltree_path == "Bacteria.Pseudomonadati.Pseudomonadota"
    assert (phylum.phylum_taxid, phylum.class_taxid, phylum.class_name) == (
        1224,
        None,
        "",
    )
    assert phylum.taxdump_version == VERSION
    assert Taxon.objects.get(taxid=2).parent_taxid is None

    assert load_taxa(tmp_path) == 4  # idempotent
    assert Taxon.objects.count() == 4


def test_load_taxa_without_file_is_a_noop(tmp_path):
    assert load_taxa(tmp_path) == 0
    assert not Taxon.objects.exists()


def test_load_taxa_rejects_invalid_ltree_and_missing_columns(tmp_path):
    rows = _taxa_rows()
    rows[2]["ltree_path"] = "Bacteria.Pseudo monadota"
    write_taxa(tmp_path, rows)
    with pytest.raises(ValueError, match="invalid ltree_path"):
        load_taxa(tmp_path)
    assert not Taxon.objects.exists()

    _write(
        tmp_path / "taxa.tsv", ["taxid", "name"], [{"taxid": "2", "name": "Bacteria"}]
    )
    with pytest.raises(ValueError, match="lacks columns"):
        load_taxa(tmp_path)


def test_load_taxa_refuses_to_redefine_stored_taxa(tmp_path):
    write_taxa(tmp_path)
    load_taxa(tmp_path)
    write_taxa(tmp_path, _taxa_rows(rename={1224: "Pseudomonadota_v2"}))
    with pytest.raises(ValueError, match="redefines 1 stored taxon.*1224"):
        load_taxa(tmp_path)
    assert Taxon.objects.get(taxid=1224).name == "Pseudomonadota"

    load_taxa(tmp_path, allow_taxon_changes=True)
    assert Taxon.objects.get(taxid=1224).name == "Pseudomonadota_v2"


# ── load_contigs ─────────────────────────────────────────────────────────


@pytest.fixture
def lookup() -> dict[str, int]:
    asm = DashboardAssemblyFactory(assembly_accession="GCA1")
    return {asm.assembly_accession: asm.id}


def test_contigs_with_taxid_are_linked_to_their_taxon(tmp_path, lookup):
    write_taxa(tmp_path)
    load_taxa(tmp_path)
    write_contigs(tmp_path, [_contig("GCA1", 1, CANON, "1236"), _contig("GCA1", 2)])
    load_contigs(tmp_path, lookup)

    linked = DashboardContig.objects.get(sequence_sha256="GCA1-1")
    assert (linked.taxonomy_path, linked.taxon_id, linked.taxonomy_path_legacy) == (
        CANON,
        1236,
        "",
    )
    plain = DashboardContig.objects.get(sequence_sha256="GCA1-2")
    assert (plain.taxonomy_path, plain.taxon_id) == ("", None)


def test_unknown_taxid_aborts_before_writing_anything(tmp_path, lookup):
    write_taxa(tmp_path)
    load_taxa(tmp_path)
    write_contigs(
        tmp_path,
        [_contig("GCA1", 1, CANON, "1236"), _contig("GCA1", 2, "Bacteria.X", "424242")],
    )
    with pytest.raises(ValueError, match=r"absent from Taxon.*424242"):
        load_contigs(tmp_path, lookup)
    assert not DashboardContig.objects.exists()


def test_a_taxid_overwrites_an_existing_canonical_link(tmp_path, lookup):
    write_taxa(tmp_path)
    load_taxa(tmp_path)
    asm = DashboardAssembly.objects.get(assembly_accession="GCA1")
    DashboardContigFactory(
        assembly=asm, sequence_sha256="GCA1-1", taxonomy_path="Bacteria", taxon_id=2
    )
    write_contigs(tmp_path, [_contig("GCA1", 1, CANON, "1236")])
    load_contigs(tmp_path, lookup)
    c = DashboardContig.objects.get(sequence_sha256="GCA1-1")
    assert (c.taxonomy_path, c.taxon_id) == (CANON, 1236)


def test_legacy_rows_keep_the_old_behaviour_next_to_taxid_rows(tmp_path, lookup):
    write_taxa(tmp_path)
    load_taxa(tmp_path)
    asm = DashboardAssembly.objects.get(assembly_accession="GCA1")
    DashboardContigFactory(
        assembly=asm, sequence_sha256="GCA1-2", taxonomy_path=CANON, taxon_id=1236
    )  # already canonical
    write_contigs(
        tmp_path,
        [
            _contig("GCA1", 1, CANON, "1236"),
            _contig(
                "GCA1", 2, "Bacteria.Proteobacteria"
            ),  # legacy row: must not undo the link
            _contig(
                "GCA1", 3, "Bacteria.Proteobacteria"
            ),  # new legacy contig: stored as given
        ],
    )
    load_contigs(tmp_path, lookup)
    got = {
        c.sequence_sha256: (c.taxonomy_path, c.taxon_id)
        for c in DashboardContig.objects.all()
    }
    assert got == {
        "GCA1-1": (CANON, 1236),
        "GCA1-2": (CANON, 1236),
        "GCA1-3": ("Bacteria.Proteobacteria", None),
    }


def test_contigs_file_without_a_taxid_column_is_still_loaded(tmp_path, lookup):
    write_contigs(
        tmp_path,
        [_contig("GCA1", 1, "Bacteria.Actinomycetota")],
        header=CONTIG_COLS[:-1],
    )
    load_contigs(tmp_path, lookup)
    c = DashboardContig.objects.get()
    assert (c.taxonomy_path, c.taxon_id) == ("Bacteria.Actinomycetota", None)


# ── pipeline ─────────────────────────────────────────────────────────────


def test_run_pipeline_loads_taxa_before_contigs_and_serves_the_tree(tmp_path):
    _write(
        tmp_path / "assemblies.tsv",
        ["assembly_accession", "organism_name"],
        [{"assembly_accession": "GCA1", "organism_name": "x"}],
    )
    write_taxa(tmp_path)
    write_contigs(
        tmp_path, [_contig("GCA1", 1, CANON, "1236"), _contig("GCA1", 2, CANON, "1236")]
    )
    run_pipeline(tmp_path, skip_stats=True)

    assert Taxon.objects.count() == 4
    assert DashboardContig.objects.filter(taxon_id=1236).count() == 2
    resp = Client().get("/api/discovery/filters/taxonomy/")
    assert resp.status_code == 200
    (domain,) = resp.json()
    phylum = domain["children"][0]["children"][0]
    assert (phylum["rank"], phylum["name"], phylum["count"]) == (
        "phylum",
        "Pseudomonadota",
        2,
    )


def test_run_pipeline_truncate_also_clears_taxa(tmp_path):
    Taxon.objects.create(taxid=999, name="Stale", rank="domain", ltree_path="Stale")
    _write(
        tmp_path / "assemblies.tsv",
        ["assembly_accession"],
        [{"assembly_accession": "A"}],
    )
    run_pipeline(tmp_path, truncate=True, skip_stats=True)
    assert not Taxon.objects.exists()
