"""Unit tests for discovery.services.upload_parser.

Covers the shared decode path used by both .tar.gz and .tgz uploads
(the parser works on raw bytes, so extension handling lives at the
endpoint layer in discovery/api.py).
"""

from __future__ import annotations

import base64
import io
import struct
import tarfile

import pytest

from discovery.services.upload_parser import (
    EMBEDDING_DIM,
    MAX_TAR_SIZE,
    UploadValidationError,
    _extract_tar,
    parse_assembly_upload,
    parse_bgc_upload,
)


def _encode_embedding(values: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode("ascii")


def _tsv(rows: list[dict[str, object]], columns: list[str]) -> bytes:
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(str(row.get(c, "")) for c in columns))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _build_archive(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


SAMPLE_CONTIG_SHA = "a" * 64
SAMPLE_EMBEDDING = _encode_embedding([0.0] * EMBEDDING_DIM)


def _bgc_archive() -> bytes:
    bgcs = _tsv(
        [
            {
                "contig_sha256": SAMPLE_CONTIG_SHA,
                "detector_name": "sanntis",
                "start_position": 100,
                "end_position": 2000,
                "classification_path": "Polyketide",
                "size_kb": 1.9,
            }
        ],
        ["contig_sha256", "detector_name", "start_position", "end_position", "classification_path", "size_kb"],
    )
    domains = _tsv(
        [
            {
                "contig_sha256": SAMPLE_CONTIG_SHA,
                "bgc_start": 100,
                "bgc_end": 2000,
                "detector_name": "sanntis",
                "domain_acc": "PF00001",
                "domain_name": "Example",
                "ref_db": "Pfam",
                "start_position": 150,
                "end_position": 300,
            }
        ],
        [
            "contig_sha256",
            "bgc_start",
            "bgc_end",
            "detector_name",
            "domain_acc",
            "domain_name",
            "ref_db",
            "start_position",
            "end_position",
        ],
    )
    embeddings = _tsv(
        [
            {
                "contig_sha256": SAMPLE_CONTIG_SHA,
                "bgc_start": 100,
                "bgc_end": 2000,
                "detector_name": "sanntis",
                "vector_base64": SAMPLE_EMBEDDING,
            }
        ],
        ["contig_sha256", "bgc_start", "bgc_end", "detector_name", "vector_base64"],
    )
    return _build_archive(
        {
            "bgcs.tsv": bgcs,
            "domains.tsv": domains,
            "embeddings_bgc.tsv": embeddings,
        }
    )


def _assembly_archive() -> bytes:
    assemblies = _tsv(
        [{"assembly_accession": "GCA_000001", "organism_name": "Example sp.", "assembly_size_mb": "4.2"}],
        ["assembly_accession", "organism_name", "assembly_size_mb"],
    )
    contigs = _tsv(
        [{"sequence_sha256": SAMPLE_CONTIG_SHA, "accession": "CONTIG_1", "length": 10_000}],
        ["sequence_sha256", "accession", "length"],
    )
    bgcs = _tsv(
        [
            {
                "contig_sha256": SAMPLE_CONTIG_SHA,
                "detector_name": "sanntis",
                "start_position": 100,
                "end_position": 2000,
            }
        ],
        ["contig_sha256", "detector_name", "start_position", "end_position"],
    )
    domains = _tsv(
        [
            {
                "contig_sha256": SAMPLE_CONTIG_SHA,
                "bgc_start": 100,
                "bgc_end": 2000,
                "detector_name": "sanntis",
                "domain_acc": "PF00001",
            }
        ],
        ["contig_sha256", "bgc_start", "bgc_end", "detector_name", "domain_acc"],
    )
    embeddings = _tsv(
        [
            {
                "contig_sha256": SAMPLE_CONTIG_SHA,
                "bgc_start": 100,
                "bgc_end": 2000,
                "detector_name": "sanntis",
                "vector_base64": SAMPLE_EMBEDDING,
            }
        ],
        ["contig_sha256", "bgc_start", "bgc_end", "detector_name", "vector_base64"],
    )
    return _build_archive(
        {
            "assemblies.tsv": assemblies,
            "contigs.tsv": contigs,
            "bgcs.tsv": bgcs,
            "domains.tsv": domains,
            "embeddings_bgc.tsv": embeddings,
        }
    )


def test_parse_bgc_upload_accepts_valid_archive():
    result = parse_bgc_upload(_bgc_archive())

    assert result["contig_sha256"] == SAMPLE_CONTIG_SHA
    assert result["detector_name"] == "sanntis"
    assert result["start_position"] == 100
    assert result["end_position"] == 2000
    assert result["classification_path"] == "Polyketide"
    assert len(result["embedding"]) == EMBEDDING_DIM
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain_acc"] == "PF00001"


def test_parse_assembly_upload_accepts_valid_archive():
    result = parse_assembly_upload(_assembly_archive())

    assert result["accession"] == "GCA_000001"
    assert len(result["contigs"]) == 1
    assert result["contigs"][0]["sequence_sha256"] == SAMPLE_CONTIG_SHA
    assert len(result["bgcs"]) == 1
    bgc = result["bgcs"][0]
    assert bgc["detector_name"] == "sanntis"
    assert len(bgc["embedding"]) == EMBEDDING_DIM
    assert len(bgc["domains"]) == 1


def test_extract_tar_rejects_non_gzip():
    with pytest.raises(UploadValidationError, match=r"\.tar\.gz / \.tgz"):
        _extract_tar(b"not a gzip file at all")


def test_extract_tar_rejects_oversized():
    # Payload must exceed MAX_TAR_SIZE; any bytes work since size is checked first.
    with pytest.raises(UploadValidationError, match="too large"):
        _extract_tar(b"\x1f\x8b" + b"\x00" * MAX_TAR_SIZE)


def test_extract_tar_ignores_non_tsv_members():
    archive = _build_archive(
        {
            "bgcs.tsv": b"col\nval\n",
            "readme.txt": b"ignore me",
            "nested/path/notes.md": b"skip",
        }
    )

    members = _extract_tar(archive)

    assert set(members.keys()) == {"bgcs.tsv"}
