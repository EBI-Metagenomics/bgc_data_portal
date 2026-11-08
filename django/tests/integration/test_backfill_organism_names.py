"""``backfill_organism_names`` fills only empty names, optionally per source."""

from __future__ import annotations

from io import StringIO

import pytest
from discovery.models import DashboardAssembly
from django.core.management import call_command
from django.core.management.base import CommandError
from tests.factories.discovery_models import (
    AssemblySourceFactory,
    DashboardAssemblyFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def assemblies():
    bacdive = AssemblySourceFactory(name="bacdive_v2026-03-23")
    other = AssemblySourceFactory(name="mibig_v4.0")
    return {
        "empty": DashboardAssemblyFactory(
            assembly_accession="GCA_1.1_ASM1", organism_name="", source=bacdive
        ),
        "named": DashboardAssemblyFactory(
            assembly_accession="GCA_2.1_ASM2", organism_name="Curated", source=bacdive
        ),
        "other_source": DashboardAssemblyFactory(
            assembly_accession="GCA_3.1_ASM3", organism_name="", source=other
        ),
    }


def _tsv(tmp_path):
    p = tmp_path / "names.tsv"
    p.write_text(
        "assembly_accession\torganism_name\n"
        "GCA_1.1_ASM1\tSalinispora tropica CNB-440\n"
        "GCA_2.1_ASM2\tShould not overwrite\n"
        "GCA_3.1_ASM3\tOther source\n"
    )
    return p


def _name(acc):
    return DashboardAssembly.objects.get(assembly_accession=acc).organism_name


def test_fills_empty_names_for_the_source_only(assemblies, tmp_path):
    out = StringIO()
    call_command(
        "backfill_organism_names",
        str(_tsv(tmp_path)),
        "--source",
        "bacdive_v2026-03-23",
        stdout=out,
    )
    assert _name("GCA_1.1_ASM1") == "Salinispora tropica CNB-440"
    assert _name("GCA_2.1_ASM2") == "Curated"
    assert _name("GCA_3.1_ASM3") == ""
    assert "1 empty assemblies to fill; 0 would stay empty" in out.getvalue()


def test_dry_run_writes_nothing(assemblies, tmp_path):
    call_command(
        "backfill_organism_names", str(_tsv(tmp_path)), "--dry-run", stdout=StringIO()
    )
    assert _name("GCA_1.1_ASM1") == ""
    assert _name("GCA_3.1_ASM3") == ""


def test_rejects_a_tsv_without_the_columns(tmp_path):
    p = tmp_path / "bad.tsv"
    p.write_text("accession\tname\nGCA_1.1\tx\n")
    with pytest.raises(CommandError, match="lacks columns"):
        call_command("backfill_organism_names", str(p))
