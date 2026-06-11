"""Integration tests for the ephemeral asset-upload endpoint.

The v2 endpoint (``POST /api/discovery/assets/upload/``) accepts a single
gzip-compressed tarball in a ``file`` field, validates it by magic bytes and
size, stashes the raw bytes in Redis under a content-hash token, and dispatches
a Celery projection task — returning ``202 {token, task_id}``. The Celery
dispatch and the Redis cache are patched out here; these tests assert only the
request-validation and response contract, not the downstream projection.
"""

from __future__ import annotations

import gzip
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

UPLOAD_URL = "/api/discovery/assets/upload/"


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def gzip_bytes():
    """Minimal gzip payload — the endpoint only checks the magic bytes; the
    tarball contents are parsed later in the (mocked) Celery worker."""
    return gzip.compress(b"dummy-tarball-contents")


@pytest.fixture
def mock_pipeline():
    """Stub the Celery dispatch and the Redis-backed asset cache."""
    with patch("discovery.tasks.process_asset_upload_task") as task, patch(
        "discovery.services.asset_upload.cache.stash_upload"
    ), patch(
        "discovery.services.asset_upload.cache.mark_pending"
    ), patch(
        "discovery.services.asset_upload.cache.read_status", return_value=None
    ):
        task.delay.return_value.id = "task-asset-123"
        yield task


@pytest.mark.django_db
def test_upload_accepts_gzip_tarball(api_client, gzip_bytes, mock_pipeline):
    response = api_client.post(
        UPLOAD_URL,
        {
            "file": SimpleUploadedFile(
                "sample.tar.gz", gzip_bytes, content_type="application/gzip"
            ),
        },
    )

    assert response.status_code == 202, response.content
    body = response.json()
    assert body["task_id"] == "task-asset-123"
    # Token is the content hash (24 hex chars), deterministic for these bytes.
    assert len(body["token"]) == 24


@pytest.mark.django_db
def test_upload_rejects_non_gzip(api_client, mock_pipeline):
    response = api_client.post(
        UPLOAD_URL,
        {
            "file": SimpleUploadedFile(
                "sample.zip", b"PK\x03\x04 not gzip", content_type="application/zip"
            ),
        },
    )

    assert response.status_code == 400
    assert "gzip-compressed tarball" in response.json()["detail"]


@pytest.mark.django_db
def test_upload_rejects_missing_file(api_client, mock_pipeline):
    response = api_client.post(UPLOAD_URL, {})

    assert response.status_code == 400
    assert "Missing 'file' field" in response.json()["detail"]
