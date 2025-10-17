from __future__ import annotations

from pathlib import Path
from typing import Union, Any

try:
    import json
except Exception:  # pragma: no cover - fallback for analyzer
    import json

import pandas as pd
from django.core.exceptions import ObjectDoesNotExist

from ...models import UMAPTransform, Bgc
from ...ingestion_schemas import UMAPManifest


def register_umap_transform(
    model_file: Union[str, Path],
    coords_file: Union[str, Path],
    manifest_file: Union[str, Path],
) -> int:
    model_file = Path(model_file)
    coords_file = Path(coords_file)
    manifest_file = Path(manifest_file)

    with open(manifest_file, "r") as f:
        _manifest = json.loads(f.read())

    manifest = UMAPManifest(**_manifest).model_dump()

    coords_df = pd.read_parquet(coords_file)
    if coords_df.empty:
        return 0

    def _to_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    def _to_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    for _, row in coords_df.iterrows():
        bid = _to_int(
            row.get("id") if "id" in row else (row[0] if len(row) > 0 else None)
        )
        x = _to_float(row.get("x") if "x" in row else row.get("umap_x_coord", 0.0))
        y = _to_float(row.get("y") if "y" in row else row.get("umap_y_coord", 0.0))
        try:
            bgc = Bgc.objects.get(pk=bid)
        except ObjectDoesNotExist:
            continue
        meta = bgc.metadata or {}
        meta.update({"umap_x_coord": x, "umap_y_coord": y})
        # metadata field may be a Combinable/JSONField; assign dict works at runtime
        bgc.metadata = meta  # type: ignore[assignment]
        bgc.save(update_fields=["metadata"])

    with open(model_file, "rb") as f:
        model_bytes = f.read()

    ut = UMAPTransform.objects.create(
        n_samples_fit=manifest["n_samples_fit"],
        pca_components=manifest["pca_components"],
        n_neighbors=manifest["n_neighbors"],
        min_dist=manifest["min_dist"],
        metric=manifest["metric"],
        sklearn_version=manifest["sklearn_version"],
        umap_version=manifest["umap_version"],
        model_blob=model_bytes,
        sha256=manifest["sha256"],
    )

    return ut.pk
