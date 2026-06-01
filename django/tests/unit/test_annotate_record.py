"""Tests for the legacy mgnify_bgcs SeqAnnotator.

Embedding/UMAP annotation has been removed (replaced by the Discovery
Dashboard's phmmer-based search). The annotator now exists purely to load and
gene-call sequence inputs — these tests cover that surface.
"""

import types
import sys
from pathlib import Path


# Ensure the `django` package directory is on sys.path so tests can import the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import types as _types

# Provide a lightweight fake `pyrodigal` module so test collection doesn't need the real one.
fake_pyrodigal = _types.ModuleType("pyrodigal")
fake_pyrodigal.GeneFinder = lambda meta=True: _types.SimpleNamespace(
    find_genes=lambda seq: iter(())
)
import sys as _sys

_sys.modules.setdefault("pyrodigal", fake_pyrodigal)
# Some project modules import third-party libs at import-time (e.g. pgvector). Provide lightweight fakes.
fake_pgvector = _types.ModuleType("pgvector")
fake_pgvector.django = _types.SimpleNamespace(
    VectorField=lambda *a, **k: object, HnswIndex=lambda *a, **k: object
)
_sys.modules.setdefault("pgvector", fake_pgvector)
_sys.modules.setdefault("pgvector.django", fake_pgvector.django)

from mgnify_bgcs.services.annotate_record import (
    SeqAnnotator,
    detect_format_from_string,
)


def test_detect_format_from_string_fasta():
    data = [">seq1", "ATGC"]
    assert detect_format_from_string(data) == "fasta"


def test_detect_format_from_string_gbk():
    data = ["LOCUS       SCU49845     5028 bp    DNA             PLN       21-JUN-1999"]
    assert detect_format_from_string(data) == "gbk"


def test_detect_format_from_string_unknown():
    data = ["", "   ", "something else"]
    assert detect_format_from_string(data) == "unknown"


def make_fake_pred(begin, end, strand, aa):
    """Minimal stand-in for the prediction objects returned by pyrodigal."""
    class P:
        def __init__(self, begin, end, strand, aa):
            self.begin = begin
            self.end = end
            self.strand = strand

        def translate(self):
            return aa

    return P(begin, end, strand, aa)


def test_load_fasta_nucleotide_predicts_genes(monkeypatch):
    fasta = ">contig1\nATGAAATTTGGGCCCTTTAAATAG\n"

    fake_finder = types.SimpleNamespace()
    fake_preds = [make_fake_pred(0, 9, 1, "MKF"), make_fake_pred(9, 21, 1, "GL*")]

    def fake_find_genes(seq_bytes):
        assert isinstance(seq_bytes, (bytes, bytearray))
        for p in fake_preds:
            yield p

    fake_finder.find_genes = fake_find_genes

    monkeypatch.setattr(
        "mgnify_bgcs.services.annotate_record.pyrodigal.GeneFinder",
        lambda meta=True: fake_finder,
    )

    class DummyRec:
        def __init__(self, seq_bytes, id):
            self.seq = seq_bytes
            self.id = id
            self.features = []
            self.annotations = {}

    class FakeSeq:
        def __init__(self, s: str):
            self._s = s

        def __str__(self):
            return self._s

        def __bytes__(self):
            return self._s.encode("ascii")

    monkeypatch.setattr(
        "mgnify_bgcs.services.annotate_record.SeqIO.read",
        lambda fasta_io, fmt: DummyRec(FakeSeq("ATGAAATTTGGGCCCTTTAAATAG"), "contig1"),
    )

    annotator = SeqAnnotator()
    rec = annotator.annotate_sequence_file(fasta, molecule_type="nucleotide")

    cds = [f for f in rec.features if f.type == "CDS"]
    assert len(cds) == 2
    for f in cds:
        assert "translation" in f.qualifiers
        # Embedding annotation was removed; nothing else should appear here.
        assert "embedding" not in f.qualifiers

    assert "bgc_embedding" not in rec.annotations
    assert "umap_x_coord" not in rec.annotations
    assert "umap_y_coord" not in rec.annotations


def test_load_fasta_protein_backtranslate(monkeypatch):
    fasta = ">prot1\nMKT\n"

    monkeypatch.setattr(
        "mgnify_bgcs.services.annotate_record.pyrodigal.GeneFinder",
        lambda meta=True: types.SimpleNamespace(find_genes=lambda seq: iter(())),
    )

    class DummyProtRec:
        def __init__(self, seq_str, id):
            self.seq = seq_str
            self.id = id
            self.features = []
            self.annotations = {}

    monkeypatch.setattr(
        "mgnify_bgcs.services.annotate_record.SeqIO.read",
        lambda fasta_io, fmt: DummyProtRec("MKT", "prot1"),
    )

    annotator = SeqAnnotator()
    rec = annotator.annotate_sequence_file(fasta, molecule_type="protein")

    cds = [f for f in rec.features if f.type == "CDS"]
    assert len(cds) == 1
    f = cds[0]
    assert "translation" in f.qualifiers
    assert f.qualifiers["translation"][0] == "MKT"
    assert "embedding" not in f.qualifiers
    assert "bgc_embedding" not in rec.annotations


def test_annotate_record_no_proteins_is_passthrough():
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord

    rec = SeqRecord(Seq("ATG"), id="empty")
    rec.features = []

    annot = SeqAnnotator()
    out = annot._annotate_record(rec)
    assert out is rec
    assert "bgc_embedding" not in out.annotations
