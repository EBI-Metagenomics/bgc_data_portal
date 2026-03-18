from functools import lru_cache
from joblib import load
import io
from ..models import UMAPTransform
import logging
from packaging.version import parse
from mgnify_bgcs.models import BgcDetector

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class DummyUMAP:
    def transform(self, x):
        return [("nan", "nan")]


_umap_cache = None


@lru_cache(maxsize=1)
def umap_model():
    """
    Caches so we only ever load one joblib per worker.
    if None exist return None
    """
    global _umap_cache
    if _umap_cache is None or type(_umap_cache) is DummyUMAP:
        umap_record = UMAPTransform.objects.order_by("-created_at").first()
        if umap_record is None:
            log.warning("No UMAPTransform found in database. Loading dummy model.")
            return DummyUMAP()
        buffer = io.BytesIO(umap_record.model_blob)
        _umap_cache = load(buffer)
    return _umap_cache


_esm_cache = None


@lru_cache(maxsize=1)
def protein_embedder():
    """
    Caches so we only ever load one embedder per worker.
    """
    from ..services.protein_embeddings import ESMEmbedder

    global _esm_cache
    if _esm_cache is None:
        _esm_cache = ESMEmbedder()
    return _esm_cache


# Adjust the import to your app structure


highest_tool_version = None


@lru_cache(maxsize=1)
def get_highest_versions_by_tool():
    """
    Returns a dictionary with the highest version of each detector tool.
    """
    global highest_tool_version
    if highest_tool_version is None:
        highest_by_tool = {}

        # Filter out entries with missing tool or version
        detectors = (
            BgcDetector.objects.exclude(tool__isnull=True)
            .exclude(tool__exact="")
            .exclude(version__isnull=True)
            .exclude(version__exact="")
        )

        for detector in detectors:
            try:
                version_obj = parse(detector.version)
            except Exception:
                continue  # Skip invalid version strings

            current = highest_by_tool.get(detector.tool)

            if not current or version_obj > current[0]:
                highest_by_tool[detector.tool] = (version_obj, detector.pk)

        highest_tool_version = {tool: pk for tool, (_, pk) in highest_by_tool.items()}
    return highest_tool_version
