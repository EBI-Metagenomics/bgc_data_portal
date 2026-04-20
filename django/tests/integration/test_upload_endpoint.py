"""Integration tests for the ephemeral upload-for-assessment endpoint.

Covers the filename-suffix validation added so users can submit archives
named either ``.tar.gz`` or ``.tgz`` with a clear error for anything else.
The Celery dispatch is patched out — these tests assert only request
validation and the 202/400 response contract.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from tests.unit.test_upload_parser import _bgc_archive


UPLOAD_URL = "/api/dashboard/assess/upload/"


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def archive_bytes():
    return _bgc_archive()


@pytest.fixture
def mock_celery():
    """Stub out the Celery .delay() call so the test doesn't touch a broker."""
    with patch("discovery.tasks.assess_uploaded_bgc") as bgc_task, patch(
        "discovery.tasks.assess_uploaded_assembly"
    ) as asm_task:
        bgc_task.delay.return_value.id = "task-bgc-123"
        asm_task.delay.return_value.id = "task-asm-456"
        yield bgc_task, asm_task


@pytest.mark.django_db
def test_upload_accepts_tar_gz_filename(api_client, archive_bytes, mock_celery):
    response = api_client.post(
        UPLOAD_URL,
        {
            "type": "bgc",
            "file": SimpleUploadedFile(
                "sample.tar.gz", archive_bytes, content_type="application/gzip"
            ),
        },
    )

    assert response.status_code == 202, response.content
    body = response.json()
    assert body["task_id"] == "task-bgc-123"
    assert body["asset_type"] == "bgc"


@pytest.mark.django_db
def test_upload_accepts_tgz_filename(api_client, archive_bytes, mock_celery):
    response = api_client.post(
        UPLOAD_URL,
        {
            "type": "bgc",
            "file": SimpleUploadedFile(
                "sample.tgz", archive_bytes, content_type="application/gzip"
            ),
        },
    )

    assert response.status_code == 202, response.content
    assert response.json()["task_id"] == "task-bgc-123"


@pytest.mark.django_db
def test_upload_rejects_zip_filename(api_client, archive_bytes):
    response = api_client.post(
        UPLOAD_URL,
        {
            "type": "bgc",
            "file": SimpleUploadedFile(
                "sample.zip", archive_bytes, content_type="application/zip"
            ),
        },
    )

    assert response.status_code == 400
    assert "File must be a .tar.gz or .tgz archive" in response.json()["detail"]


@pytest.mark.django_db
def test_upload_rejects_missing_file(api_client):
    response = api_client.post(UPLOAD_URL, {"type": "bgc"})

    assert response.status_code == 400
    assert "No file provided" in response.json()["detail"]
