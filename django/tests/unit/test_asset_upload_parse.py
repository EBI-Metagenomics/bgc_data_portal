"""TSV → AssetData parsing tests for the asset-upload pipeline."""

from __future__ import annotations

import io
import tarfile

import pytest

from discovery.services.asset_upload.parse import parse_asset_tar
from discovery.services.asset_upload.validate import (
    AssetValidationError,
    inspect_tarball,
)


def _pack(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _full_tarball() -> bytes:
    members = {
        "assemblies.tsv": (
            b"assembly_accession\torganism_name\tsource\tassembly_type\tbiome_path\n"
            b"A1\tFoo bar\tdemo\t2\troot.Env\n"
        ),
        "contigs.tsv": (
            b"assembly_accession\tsequence_sha256\taccession\tlength\n"
            b"A1\taa\taa_acc\t1000\n"
        ),
        "detectors.tsv": (
            b"name\ttool\tversion\n"
            b"antiSMASH:1\tantiSMASH\t1.0\n"
            b"GECCO v1\tGECCO\t1.0\n"
        ),
        "bgcs.tsv": (
            b"contig_sha256\tdetector_name\tstart_position\tend_position\t"
            b"classification_path\tsize_kb\tis_partial\tis_validated\n"
            b"aa\tantiSMASH:1\t0\t1000\tterpene\t1.0\tfalse\tfalse\n"
            b"aa\tGECCO v1\t100\t500\tterpene\t0.4\tfalse\tfalse\n"
        ),
        "cds.tsv": (
            b"contig_sha256\tbgc_start\tbgc_end\tdetector_name\t"
            b"protein_id_str\tstart_position\tend_position\tstrand\tprotein_length\n"
            b"aa\t0\t1000\tantiSMASH:1\tA_1\t0\t300\t1\t100\n"
            b"aa\t0\t1000\tantiSMASH:1\tA_2\t300\t600\t1\t100\n"
        ),
        "cds_sequences.tsv": (
            b"contig_sha256\tbgc_start\tbgc_end\tdetector_name\t"
            b"protein_id_str\tsequence_base64\n"
            b"aa\t0\t1000\tantiSMASH:1\tA_1\tBASE64==\n"
        ),
        "domains.tsv": (
            b"contig_sha256\tbgc_start\tbgc_end\tdetector_name\t"
            b"protein_id_str\tdomain_acc\tdomain_name\tref_db\tstart_position\tend_position\n"
            b"aa\t0\t1000\tantiSMASH:1\tA_1\tPF00001\tDom1\tPfam\t0\t100\n"
            b"aa\t0\t1000\tantiSMASH:1\tA_2\tPF00002\tDom2\tPfam\t0\t100\n"
        ),
        "natural_products.tsv": (
            b"contig_sha256\tbgc_start\tbgc_end\tdetector_name\tname\tsmiles\n"
            b"aa\t0\t1000\tantiSMASH:1\tFooMycin\tCCO\n"
        ),
    }
    return _pack(members)


def test_parses_full_tarball_round_trip():
    raw = _full_tarball()
    validated = inspect_tarball(raw)
    data = parse_asset_tar(validated)

    assert [a.assembly_accession for a in data.assemblies] == ["A1"]
    assert data.assemblies[0].organism_name == "Foo bar"
    assert [c.sequence_sha256 for c in data.contigs] == ["aa"]
    assert [(b.start_position, b.end_position) for b in data.bgcs] == [
        (0, 1000),
        (100, 500),
    ]
    assert [c.protein_id_str for c in data.cds] == ["A_1", "A_2"]
    assert data.cds[0].sequence_zlib_b64 == "BASE64=="
    # CDS without a sequence row stays empty (silent — matches loader.py).
    assert data.cds[1].sequence_zlib_b64 == ""
    assert {d.domain_acc for d in data.domains} == {"PF00001", "PF00002"}
    assert data.natural_products[0].name == "FooMycin"


def test_rejects_bgc_referencing_unknown_contig():
    members = {
        "assemblies.tsv": b"assembly_accession\nA1\n",
        "contigs.tsv": b"assembly_accession\tsequence_sha256\nA1\taa\n",
        "detectors.tsv": b"name\ttool\tversion\nantiSMASH:1\tantiSMASH\t1.0\n",
        "bgcs.tsv": (
            b"contig_sha256\tdetector_name\tstart_position\tend_position\n"
            b"ghost\tantiSMASH:1\t0\t100\n"
        ),
    }
    raw = _pack(members)
    validated = inspect_tarball(raw)
    with pytest.raises(AssetValidationError, match="unknown contig"):
        parse_asset_tar(validated)


def test_rejects_bgc_referencing_unknown_detector():
    members = {
        "assemblies.tsv": b"assembly_accession\nA1\n",
        "contigs.tsv": b"assembly_accession\tsequence_sha256\nA1\taa\n",
        "detectors.tsv": b"name\ttool\tversion\nantiSMASH:1\tantiSMASH\t1.0\n",
        "bgcs.tsv": (
            b"contig_sha256\tdetector_name\tstart_position\tend_position\n"
            b"aa\tGhostDetector\t0\t100\n"
        ),
    }
    raw = _pack(members)
    validated = inspect_tarball(raw)
    with pytest.raises(AssetValidationError, match="unknown detector"):
        parse_asset_tar(validated)


def test_rejects_invalid_interval():
    members = {
        "assemblies.tsv": b"assembly_accession\nA1\n",
        "contigs.tsv": b"assembly_accession\tsequence_sha256\nA1\taa\n",
        "detectors.tsv": b"name\ttool\tversion\nantiSMASH:1\tantiSMASH\t1.0\n",
        "bgcs.tsv": (
            b"contig_sha256\tdetector_name\tstart_position\tend_position\n"
            b"aa\tantiSMASH:1\t500\t100\n"
        ),
    }
    raw = _pack(members)
    validated = inspect_tarball(raw)
    with pytest.raises(AssetValidationError, match="invalid interval"):
        parse_asset_tar(validated)


def test_dedups_bgc_rows():
    members = {
        "assemblies.tsv": b"assembly_accession\nA1\n",
        "contigs.tsv": b"assembly_accession\tsequence_sha256\nA1\taa\n",
        "detectors.tsv": b"name\ttool\tversion\nantiSMASH:1\tantiSMASH\t1.0\n",
        "bgcs.tsv": (
            b"contig_sha256\tdetector_name\tstart_position\tend_position\n"
            b"aa\tantiSMASH:1\t0\t100\n"
            b"aa\tantiSMASH:1\t0\t100\n"
        ),
    }
    raw = _pack(members)
    validated = inspect_tarball(raw)
    data = parse_asset_tar(validated)
    assert len(data.bgcs) == 1


def test_parses_real_fixture_tarball():
    """Sanity: the canonical Ga0181741 fixture parses cleanly."""
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parents[3]
        / "input_test_files"
        / "files"
        / "Ga0181741_assembly_upload.tar.gz"
    )
    if not fixture.exists():
        pytest.skip(f"Fixture not present at {fixture}")
    raw = fixture.read_bytes()
    validated = inspect_tarball(raw)
    data = parse_asset_tar(validated)
    assert len(data.assemblies) == 1
    assert len(data.bgcs) > 0
    assert len(data.cds) > 0
    assert len(data.domains) > 0
