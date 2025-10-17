import json
from types import SimpleNamespace

import pandas as pd
import pytest
from django.test import Client
from django.conf import settings


def _dummy_async_result(task_id: str = "test-task-id"):
    return SimpleNamespace(id=task_id)


@pytest.fixture(scope="module")
def client():
    return Client()


def _with_prefix(path: str) -> str:
    # When SCRIPT_NAME is set, Django combines it with PATH_INFO internally.
    # Do not prefix the path here to avoid duplicate segments.
    return path


def _extra_environ():
    base = (getattr(settings, "FORCE_SCRIPT_NAME", "") or "").rstrip("/")
    return {"SCRIPT_NAME": base} if base else {}


def test_health_ok(monkeypatch, client):
    # Avoid hitting a real database in production-like test env
    import mgnify_bgcs.api as api_module

    class _FakeCursor:
        def execute(self, *_a, **_k):
            return None

    monkeypatch.setattr(
        api_module,
        "connection",
        SimpleNamespace(cursor=lambda: _FakeCursor()),
    )

    resp = client.get(_with_prefix("/api/health"), **_extra_environ())
    assert resp.status_code == 200
    data = json.loads(resp.content.decode("utf-8"))
    assert data.get("status") == "ok"


def test_search_endpoints_return_task_ids(monkeypatch, client):
    # Patch Celery task stubs to avoid touching broker/worker
    import mgnify_bgcs.api as api_module

    class _DummyTask:
        def __init__(self, name):
            self._name = name

        def delay(self, *args, **kwargs):
            return _dummy_async_result(task_id=f"{self._name}-123")

    monkeypatch.setattr(
        api_module,
        "task_module",
        SimpleNamespace(
            keyword_search=_DummyTask("kw"),
            advanced_search=_DummyTask("adv"),
            sequence_search=_DummyTask("seq"),
            compound_search=_DummyTask("chem"),
        ),
    )

    # keyword search
    r1 = client.post(
        _with_prefix("/api/search/keyword"),
        data=json.dumps({"keyword": "glycosyltransferase"}),
        content_type="application/json",
        **_extra_environ(),
    )
    assert r1.status_code == 202
    assert json.loads(r1.content.decode("utf-8")).get("task_id").startswith("kw-")

    # advanced search (empty body is allowed; all fields optional)
    r2 = client.post(
        _with_prefix("/api/search/advanced"),
        data=json.dumps({}),
        content_type="application/json",
        **_extra_environ(),
    )
    assert r2.status_code == 202
    assert json.loads(r2.content.decode("utf-8")).get("task_id").startswith("adv-")

    # sequence search (provide minimal required field 'sequence')
    r3 = client.post(
        _with_prefix("/api/search/sequence"),
        data=json.dumps({"sequence": "ATGAAATTTGGG"}),
        content_type="application/json",
        **_extra_environ(),
    )
    assert r3.status_code == 202
    assert json.loads(r3.content.decode("utf-8")).get("task_id").startswith("seq-")

    # chemical search
    r4 = client.post(
        _with_prefix("/api/search/chemical"),
        data=json.dumps({"smiles": "CCO"}),
        content_type="application/json",
        **_extra_environ(),
    )
    assert r4.status_code == 202
    assert json.loads(r4.content.decode("utf-8")).get("task_id").startswith("chem-")


def test_download_bgc_variants(monkeypatch, client):
    # Build a minimal valid GenBank text using Biopython for robust parsing
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    from Bio.SeqFeature import SeqFeature, FeatureLocation
    from Bio import SeqIO
    from io import StringIO

    seq = Seq("ATGAAATTTGGG")
    rec = SeqRecord(seq, id="ctg1", name="ctg1")
    rec.annotations["molecule_type"] = "DNA"
    # Add a CDS with a translation so FAA export has content
    cds = SeqFeature(
        FeatureLocation(0, 9),
        type="CDS",
        qualifiers={
            "ID": ["prot1"],
            "translation": ["MKF"],
        },
    )
    rec.features.append(cds)
    buf = StringIO()
    SeqIO.write(rec, buf, "genbank")
    gbk_text = buf.getvalue()

    # Patch cache to indicate success and provide our GBK text
    import mgnify_bgcs.api as api_module

    def fake_get_job_status(*, search_key=None, task_id=None):
        return {"status": "SUCCESS", "result": {"record_genebank_text": gbk_text}}

    monkeypatch.setattr(api_module, "get_job_status", fake_get_job_status)

    # Test each output type; filename based on input id when source meta absent
    for out_type, ctype in [
        ("gbk", "application/genbank"),
        ("fna", "text/x-fasta"),
        ("faa", "text/x-fasta"),
        ("json", "application/json"),
    ]:
        body = json.dumps({"bgc_id": "5544", "output_type": out_type})
        resp = client.generic(
            "GET",
            _with_prefix("/api/download/bgc"),
            body,
            content_type="application/json",
            **_extra_environ(),
        )
        assert resp.status_code == 200
        assert resp["Content-Type"] == ctype
        # Basic content checks
        payload = resp.content.decode("utf-8")
        if out_type in ("fna", "faa"):
            assert payload.startswith(">")
        elif out_type == "gbk":
            assert "LOCUS" in payload
        else:  # json
            data = json.loads(payload)
            assert data.get("id") == "ctg1"


def test_download_results_tsv(monkeypatch, client):
    # Provide a tiny DataFrame with the expected display columns
    df = pd.DataFrame(
        [
            {
                "accession": "MGYB00000001",
                "assembly_accession": "GCA_000001",
                "contig_accession": "contig_1",
                "start_position_plus_one": 1,
                "end_position": 100,
                "detector_names": "antiSMASH",
                "class_names": "NRPS",
            }
        ]
    )

    import mgnify_bgcs.api as api_module

    def fake_get_job_status(*, task_id=None, search_key=None):
        return {"status": "SUCCESS", "result": {"df": df}}

    monkeypatch.setattr(api_module, "get_job_status", fake_get_job_status)

    body = json.dumps({"task_id": "abc123"})
    resp = client.generic(
        "GET",
        _with_prefix("/api/download/results-tsv"),
        body,
        content_type="application/json",
        **_extra_environ(),
    )
    assert resp.status_code == 200
    # Content type header for TSV
    assert resp["Content-Type"].startswith("text/tab-separated-values")
    text = resp.content.decode("utf-8")
    # Ensure known header and value are present
    assert "assembly_accession" in text
    assert "GCA_000001" in text
