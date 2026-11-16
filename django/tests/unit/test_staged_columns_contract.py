"""The loader only reads columns the ETL writes (docs/staged_columns.json).

``tests/fixtures/staged_columns/staged_columns.json`` is a copy of the ETL's
contract file. The columns read here are taken from the source of
``loader.py`` and ``apply_taxonomy_mapping.py`` (``row["x"]`` and
``row.get("x")``), so a new read of an unknown column fails without anyone
updating a list.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from discovery.management.commands import apply_taxonomy_mapping as atm
from discovery.services.ingestion import loader

CONTRACT = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures/staged_columns/staged_columns.json"
    ).read_text()
)
# contigs.tsv and taxa.tsv reach the loader as harmonise_contigs rewrote them.
BUNDLE = {**CONTRACT["collector"], **CONTRACT["harmonised"]}


def _row_keys(node: ast.AST) -> set[str]:
    """Constant keys read as ``row[...]`` or ``row.get(...)`` under *node*."""
    keys: set[str] = set()
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Subscript)
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "row"
            and isinstance(sub.slice, ast.Constant)
            and isinstance(sub.slice.value, str)
        ):
            keys.add(sub.slice.value)
        elif (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "get"
            and isinstance(sub.func.value, ast.Name)
            and sub.func.value.id == "row"
            and sub.args
            and isinstance(sub.args[0], ast.Constant)
            and isinstance(sub.args[0].value, str)
        ):
            keys.add(sub.args[0].value)
    return keys


def _loader_reads() -> dict[str, set[str]]:
    """{tsv name: columns read} for each loader function that opens one TSV."""
    tree = ast.parse(Path(loader.__file__).read_text())
    reads: dict[str, set[str]] = {}
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        files = {
            c.value
            for c in ast.walk(fn)
            if isinstance(c, ast.Constant)
            and isinstance(c.value, str)
            and c.value in BUNDLE
        }
        if len(files) == 1:
            reads.setdefault(files.pop(), set()).update(_row_keys(fn))
    return reads


LOADER_READS = _loader_reads()


def test_the_main_bundle_files_are_found_in_the_loader():
    for name in (
        "assemblies.tsv",
        "contigs.tsv",
        "bgcs.tsv",
        "cds.tsv",
        "domains.tsv",
        "taxa.tsv",
    ):
        assert LOADER_READS.get(name), f"no loader function reads {name}"


@pytest.mark.parametrize("name", sorted(LOADER_READS))
def test_loader_reads_only_written_columns(name):
    unknown = LOADER_READS[name] - set(BUNDLE[name])
    assert not unknown, (
        f"loader reads {sorted(unknown)} from {name}; the ETL does not write them"
    )


def test_apply_taxonomy_mapping_reads_only_written_columns():
    columns = set(CONTRACT["taxonomy_mapping"]["columns"])
    read = _row_keys(ast.parse(Path(atm.__file__).read_text()))
    read |= {f"{c}_taxid" for c in atm.RANK_COLS.values()} | set(atm.RANK_COLS.values())
    assert read <= columns, sorted(read - columns)


def test_applied_statuses_are_written_by_the_etl():
    assert set(CONTRACT["taxonomy_mapping"]["status_values"]) >= atm.APPLIED_STATUSES


@pytest.mark.parametrize("dropped", ["length", "accession"])
def test_load_contigs_refuses_a_header_without(tmp_path, dropped):
    header = [c for c in CONTRACT["harmonised"]["contigs.tsv"] if c != dropped]
    (tmp_path / "contigs.tsv").write_text("\t".join(header) + "\n")
    with pytest.raises(ValueError, match=dropped):
        loader.load_contigs(tmp_path, {})
