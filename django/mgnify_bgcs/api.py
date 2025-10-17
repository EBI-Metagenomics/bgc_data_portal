from io import StringIO
import os
from pathlib import Path
from urllib.parse import urlencode
import uuid
from typing import Any, Optional, cast

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.db import connection
from ninja import NinjaAPI, File as NinjaFile, UploadedFile, Router
from ninja.errors import HttpError
from ninja.security import HttpBearer


from . import tasks as task_module
from .cache_utils import get_job_status
from .utils.helpers import to_post_dict, mgyb_converter
from .utils.seqrecord_utils import EnhancedSeqRecord
from .api_schemas import (
    TaskResponse,
    KeywordSearchIn,
    AdvancedSearchIn,
    SequenceSearchIn,
    ChemicalSearchIn,
    DownloadBGCIn,
    DownloadResultsTSVIn,
)

api = NinjaAPI(title="MGnify BGCs API", version="2.0")

DB_OPERATIONS_TEMP_DIR = Path("/data/packages")
DB_OPERATIONS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
MAX_INGEST_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB – tweak via env if needed


@api.get("/health")
def health(request):
    """Lightweight service and database health check.

    Returns
    - 200 OK with {"status": "ok"} if the API can reach the database.
    - 500 on failure with a brief diagnostic string in the payload.

    This endpoint is intended for monitoring/automation; it does not require
    authentication.
    """
    # Example: check DB connection
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
    except Exception as e:
        return JsonResponse({"status": "fail", "detail": str(e)}, status=500)
    return JsonResponse({"status": "ok"}, status=200)


class AdminBearerAuth(HttpBearer):
    """Administrative bearer authentication.

    Usage
    - Send an HTTP header: `Authorization: Bearer <ADMIN_API_TOKEN>`
    - The token is configured server-side via `settings.ADMIN_API_TOKEN`.

    Grants access to protected database operation endpoints intended for
    deployment/maintenance. Not for general users.
    """

    def authenticate(self, request, token: str | None):
        admin_token = getattr(settings, "ADMIN_API_TOKEN", None)
        if admin_token and token == admin_token:
            return "admin"
        return None


class ProjectUserBearerAuth(HttpBearer):
    """Project-user bearer authentication.

    Usage
    - Send an HTTP header: `Authorization: Bearer <PROJECT_USER_TOKEN>`
    - Token comes from `settings.PROJECT_USER_TOKEN`.

    Grants limited access to specific endpoints (e.g. ingestion). It does not
    confer admin privileges.
    """

    def authenticate(self, request, token: str | None):
        project_token = getattr(settings, "PROJECT_USER_TOKEN", None)
        if project_token and token == project_token:
            return "project-user"
        return None


### PUBLIC ENDPOINTS


@api.post("/search/keyword", response={202: TaskResponse})
def keyword_search(request, query: KeywordSearchIn):
    """Search BGCs with a free‑text keyword across metadata fields.

    Parameters (body)
    - keyword (string): Free text term; matches across BGC annotations and related metadata.

    Behavior
    - Enqueues an asynchronous search and returns a task identifier.
    - Poll the job status endpoint used by the web UI to retrieve results.

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.

    Example
    - Search for glycosyltransferase related regions.
    """
    clean_params = query.dict()
    post_params = to_post_dict(clean_params)
    search_key = urlencode(post_params, doseq=True)
    async_result = cast(Any, task_module.keyword_search).delay(search_key, clean_params)
    return JsonResponse({"task_id": async_result.id}, status=202)


@api.post("/search/advanced", response={202: TaskResponse})
def advanced_search(request, query: AdvancedSearchIn):
    """Advanced, faceted BGC search.

    Parameters (body, all optional)
    - bgc_class_name: High‑level class label (e.g. NRPS, PKS, RiPP).
    - mgyb: BGC accession (e.g. MGYB00000123) to restrict results.
    - assembly_accession: ENA/GenBank assembly accession.
    - contig_accession: Contig accession within an assembly.
    - biome_lineage: MGnify biome lineage string (e.g. root:Environmental:Marine).
    - completeness: List of integers denoting completeness category: 0=Complete,
      1=Single bounded, 2=Double bounded.
    - protein_domain: Domain name or identifier to filter by.
    - domain_strategy: intersection (AND) or union (OR) when multiple domains are implied.
    - detectors: List of detector names (e.g. ["antiSMASH", "GECCO"]). Server resolves to latest versions.

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.
    """
    clean_params = query.dict()
    post_params = to_post_dict(clean_params)
    search_key = urlencode(post_params, doseq=True)
    async_result = cast(Any, task_module.advanced_search).delay(
        search_key, clean_params
    )
    return JsonResponse({"task_id": async_result.id}, status=202)


@api.post("/search/sequence", response={202: TaskResponse})
def sequence_search(request, query: SequenceSearchIn):
    """Sequence‑based search against BGCs or their protein coding sequences.

    Parameters (body)
    - sequence: FASTA text or bare sequence string.
    - sequence_type: "nucleotide" or "protein"; defaults to nucleotide.
    - unit_of_comparison: "bgc" (region‑level) or "proteins" (CDS set similarity).
    - similarity_measure: "hmmer" (profile HMM) or "cosine" (embedding similarity).
    - similarity_threshold: Numeric threshold; typical ranges depend on the measure:
        • hmmer: 0–100 (default ~32)
        • cosine: 0–1 (default ~0.85)
    - set_similarity_threshold: When unit_of_comparison == "proteins", the set‑level
      similarity threshold. Defaults to 0.5 if omitted in that mode.

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.
    """
    clean_params = query.dict()
    set_thr = clean_params.get("set_similarity_threshold")
    if (
        clean_params.get("unit_of_comparison") or "bgc"
    ) == "proteins" and set_thr is None:
        # Ensure downstream tasks receive the expected parameter name
        clean_params["set_similarity_threshold"] = 0.5
    post_params = to_post_dict(clean_params)
    search_key = urlencode(post_params, doseq=True)
    async_result = cast(Any, task_module.sequence_search).delay(
        search_key, clean_params
    )
    return JsonResponse({"task_id": async_result.id}, status=202)


@api.post("/search/chemical", response={202: TaskResponse})
def chemical_search(request, query: ChemicalSearchIn):
    """Chemical structure search using SMILES.

    Parameters (body)
    - smiles or smiles_text: A SMILES string representing the query structure.
    - similarity_threshold: For fingerprint/embedding similarity (0–1, default 0.85).

    Notes
    - If both `smiles_text` and `smiles` are provided, `smiles_text` takes precedence.

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.
    """
    smiles = (query.smiles_text or query.smiles or "").strip()
    if not smiles:
        raise HttpError(400, "Provide a SMILES string via 'smiles' or 'smiles_text'")
    clean_params = query.dict()
    # Normalize to 'smiles' for downstream tasks
    clean_params["smiles"] = smiles
    post_params = to_post_dict(clean_params)
    search_key = urlencode(post_params, doseq=True)
    async_result = cast(Any, task_module.compound_search).delay(
        search_key, clean_params
    )
    return JsonResponse({"task_id": async_result.id}, status=202)


@api.get("/download/bgc")
def download_bgc(request, query: DownloadBGCIn):
    """Download a single BGC in GenBank, FASTA nucleotide/protein, or JSON format.

    Parameters (query)
    - bgc_id: Integer database id or MGYB accession (e.g. MGYB00001234).
    - output_type: One of gbk, fna, faa, json (default gbk).

    Behavior
    - Uses a stable cache key to reuse previously computed records.
    - If cache miss, constructs the BGC record synchronously before streaming.

    Responses
    - 200 OK with file content and Content-Disposition filename.
    - 400 for invalid identifiers or output types.
    """
    # Validate output type
    output_type = (query.output_type or "gbk").lower()
    if output_type not in {"gbk", "fna", "faa", "json"}:
        raise HttpError(400, "Invalid output_type; choose gbk, fna, faa, or json")

    # Normalize/clean bgc_id (accept MGYB accession or integer string)
    raw_id = query.bgc_id.strip()
    try:
        if raw_id.upper().startswith("MGYB"):
            bgc_pk = int(mgyb_converter(raw_id, text_to_int=True))
        else:
            bgc_pk = int(raw_id)
    except Exception:
        raise HttpError(400, "Invalid bgc_id; provide an integer id or MGYB accession")

    # Build a stable cache key like other endpoints do
    clean_params = {"bgc_id": bgc_pk}
    post_params = to_post_dict(clean_params)
    search_key = urlencode(post_params, doseq=True)

    # 1) Try cache first
    status = get_job_status(search_key=search_key)
    if status.get("status") != "SUCCESS":
        cast(Any, task_module.collect_bgc_data).apply(args=(search_key, clean_params))
        status = get_job_status(search_key=search_key)
    try:
        record_genebank_text = status.get("result", {}).get("record_genebank_text")
        record_obj = EnhancedSeqRecord.from_genbank_text(record_genebank_text)
    except:
        raise RuntimeError("Synchronous task did not populate cache")

    source_meta = record_obj.annotations.get("source", {})
    if isinstance(source_meta, dict):
        bgc_acc = source_meta.get("bgc_accession") or str(raw_id)
    else:
        bgc_acc = str(raw_id)

    # Serialize by type
    if output_type == "gbk":
        content = record_obj.to_gbk()
        content_type = "application/genbank"
        ext = "gbk"
    elif output_type == "fna":
        content = record_obj.to_fna()
        content_type = "text/x-fasta"
        ext = "fna"
    elif output_type == "faa":
        content = record_obj.to_faa()
        content_type = "text/x-fasta"
        ext = "faa"
    else:  # json
        content = record_obj.to_json()
        content_type = "application/json"
        ext = "json"

    filename = f"{bgc_acc}.{ext}"
    resp = HttpResponse(content, content_type=content_type)
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@api.get("/download/results-tsv")
def download_results_tsv(request, query: DownloadResultsTSVIn):
    """Download search results as a TSV using the previously returned task id.

        Parameters (query)
        - task_id: The Celery/worker task identifier returned by a search endpoint.

        Behavior
        - Loads the cached results and emits a tab‑separated file with the primary
            columns used in the web interface. If those columns are missing, falls
            back to writing the full table.

    Responses
    - 200 OK with a TSV attachment.
    - 400 if results are not available or the task is not completed successfully.
    """
    status = get_job_status(task_id=query.task_id)
    if not status or status.get("status") != "SUCCESS":
        return HttpResponse("No results available", status=400)

    payload = status.get("result") or {}
    df = payload.get("df")
    display_columns = [
        "accession",
        "assembly_accession",
        "contig_accession",
        "start_position_plus_one",
        "end_position",
        "detector_names",
        "class_names",
    ]

    filename = f"bgc_search_results_{query.task_id}.tsv"
    response = HttpResponse(content_type="text/tab-separated-values")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    buf = StringIO()
    try:
        cast(Any, df)[display_columns].to_csv(buf, sep="\t", index=False)
    except Exception:
        cast(Any, df).to_csv(buf, sep="\t", index=False)

    response.write(buf.getvalue())
    buf.close()
    return response


# Allow either Admin or ProjectUser to ingest packages
@api.post(
    "/upload/ingest_bgc", response={202: TaskResponse}, auth=ProjectUserBearerAuth()
)
def ingest(
    request,
    file: UploadedFile = cast(Any, NinjaFile(..., description="gzipped NDJSON package")),  # type: ignore[misc]
):
    """Ingest a BGC package (.ndjson.gz) into the portal database.

    Authentication
    - Requires header `Authorization: Bearer <PROJECT_USER_TOKEN>`.

    Expected file
    - A gzip‑compressed NDJSON file produced by the MGnify BGCs pipeline.
    - Maximum size: 5 GB (configurable via environment variable).

    Behavior
    - Reads with a hard size cap, verifies gzip signature, writes to a secure
      temporary directory, and enqueues an asynchronous ingestion task.

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.
    """
    # guardrail: read + size-cap
    contents = file.read(MAX_INGEST_FILE_SIZE + 1)
    if len(contents) > MAX_INGEST_FILE_SIZE:
        raise HttpError(413, "File too large")

    # quick syntactic sniff – bail early if not GZIP
    if contents[:2] != b"\x1f\x8b":
        raise HttpError(400, "File must be gzip compressed")

    pkg_path = DB_OPERATIONS_TEMP_DIR / file.name
    # synchronous write is fine for Django view
    with open(pkg_path, "wb") as f:
        f.write(contents)
    os.chmod(pkg_path, 0o664)

    async_result = cast(Any, task_module.ingest_package).delay(str(pkg_path))
    return JsonResponse({"task_id": async_result.id}, status=202)


### DB OPERATION ENDPOINTS
dbops = Router(auth=AdminBearerAuth())


@dbops.post(
    "/db_op/register_umap_transform",
    response={202: TaskResponse},
    include_in_schema=False,
    auth=AdminBearerAuth(),
)
def register_umap_transform(
    request,
    model_file: UploadedFile = cast(Any, NinjaFile(..., description="UMAP model file")),  # type: ignore[misc]
    coords_file: UploadedFile = cast(Any, NinjaFile(..., description="Coordinates file")),  # type: ignore[misc]
    manifest_file: UploadedFile = cast(Any, NinjaFile(..., description="Manifest file")),  # type: ignore[misc]
):
    """Register a UMAP transform (admin‑only).

    Parameters (multipart/form‑data)
    - model_file: Serialized UMAP model.
    - coords_file: Coordinates matrix associated with the model.
    - manifest_file: Small manifest/metadata file describing the transform.

    Behavior
    - Writes files to a controlled temp area and passes filesystem paths to a background task.
    - Endpoint hidden from public schema; requires admin bearer token.
    """

    # helper to read+cap+write an uploaded file
    def _write_upload(upload: UploadedFile) -> str:
        contents = upload.read(MAX_INGEST_FILE_SIZE + 1)
        if len(contents) > MAX_INGEST_FILE_SIZE:
            raise HttpError(413, "File too large")
        # prefix with uuid to avoid name collisions
        dest = DB_OPERATIONS_TEMP_DIR / f"{uuid.uuid4().hex}_{upload.name}"
        with open(dest, "wb") as f:
            f.write(contents)
        os.chmod(dest, 0o664)
        return str(dest)

    model_path = _write_upload(model_file)
    coords_path = _write_upload(coords_file)
    manifest_path = _write_upload(manifest_file)

    async_result = cast(Any, task_module.register_umap_transform).delay(
        model_path, coords_path, manifest_path
    )
    return JsonResponse({"task_id": async_result.id}, status=202)


@dbops.post(
    "/db_op/calculate_aggregated_bgcs",
    response={202: TaskResponse},
    include_in_schema=False,
    auth=AdminBearerAuth(),
)
def calculate_aggregated_bgcs(request, contig_ids: Optional[list[int]] = None):  # type: ignore[misc]
    """Recalculate aggregated BGCs (admin‑only).

    Parameters (body)
    - contig_ids: Optional list of contig integer ids to restrict the recalculation scope.

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.
    """
    async_result = cast(Any, task_module.calculate_aggregated_bgcs).delay(contig_ids)
    return JsonResponse({"task_id": async_result.id}, status=202)


@dbops.post(
    "/db_op/export_bgc_embeddings_base64",
    response={202: TaskResponse},
    include_in_schema=False,
    auth=AdminBearerAuth(),
)
def export_bgc_embeddings_base64(request):  # type: ignore[misc]
    """Export BGC embeddings as a base64‑encoded Parquet blob (admin‑only).

    Response
    - 202 Accepted with `{ "task_id": "<uuid>" }`.
    - Retrieve the resulting payload via the job‑status mechanism.
    """
    async_result = cast(Any, task_module.export_bgc_embeddings_base64).delay()
    return JsonResponse({"task_id": async_result.id}, status=202)


# Mount protected DB operations router
api.add_router("", dbops)
