"""Celery tasks for the Evaluate Asset mode.

Each task dispatches to the assessment service, caches the result
in Redis with a 24-hour TTL, and follows the existing set_job_cache
/ get_job_status polling pattern.
"""

from __future__ import annotations

import logging

from celery import shared_task

from discovery.cache_utils import set_job_cache

log = logging.getLogger(__name__)

ASSESSMENT_TTL = 86_400  # 24 hours
KEYWORD_TTL = 300  # 5 minutes
UPLOAD_ASSESSMENT_TTL = 14_400  # 4 hours
CHEMICAL_QUERY_TTL = 3_600  # 1 hour


@shared_task(name="discovery.tasks.keyword_resolve", bind=True, acks_late=True)
def keyword_resolve(self, search_key: str, keyword: str) -> bool:
    """Resolve a landing-page keyword to a dashboard filter and cache the redirect URL."""
    task_id = self.request.id
    set_job_cache(search_key=search_key, task_id=task_id, timeout=KEYWORD_TTL)

    from discovery.services.keyword_resolver import resolve_keyword

    result = resolve_keyword(keyword)

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=KEYWORD_TTL,
    )
    log.info("Keyword resolved: %r → %s (task %s)", keyword, result.get("match_type"), task_id)
    return True


@shared_task(name="discovery.tasks.assess_assembly", bind=True, acks_late=True)
def assess_assembly(self, assembly_id: int) -> bool:
    """Run a full assembly assessment and cache the result."""
    task_id = self.request.id
    search_key = f"assess_assembly:{assembly_id}"

    # Mark as pending
    set_job_cache(search_key=search_key, task_id=task_id, timeout=ASSESSMENT_TTL)

    from discovery.services.assessment import compute_assembly_assessment

    result = compute_assembly_assessment(assembly_id)

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=ASSESSMENT_TTL,
    )
    log.info("Assembly assessment completed for assembly %s (task %s)", assembly_id, task_id)
    return True


@shared_task(name="discovery.tasks.assess_bgc", bind=True, acks_late=True)
def assess_bgc(self, bgc_id: int) -> bool:
    """Run a full BGC assessment and cache the result."""
    task_id = self.request.id
    search_key = f"assess_bgc:{bgc_id}"

    # Mark as pending
    set_job_cache(search_key=search_key, task_id=task_id, timeout=ASSESSMENT_TTL)

    from discovery.services.assessment import compute_bgc_assessment

    result = compute_bgc_assessment(bgc_id)

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=ASSESSMENT_TTL,
    )
    log.info("BGC assessment completed for BGC %s (task %s)", bgc_id, task_id)
    return True


@shared_task(name="discovery.tasks.assess_uploaded_bgc", bind=True, acks_late=True)
def assess_uploaded_bgc(self, upload_key: str) -> bool:
    """Run a full BGC assessment on uploaded (cached) data."""
    from django.core.cache import cache

    task_id = self.request.id
    search_key = f"assess_upload_bgc:{upload_key}"

    set_job_cache(search_key=search_key, task_id=task_id, timeout=UPLOAD_ASSESSMENT_TTL)

    uploaded_data = cache.get(upload_key)
    if not uploaded_data:
        set_job_cache(
            search_key=search_key,
            results={"error": "Upload expired — please re-upload"},
            task_id=task_id,
            timeout=UPLOAD_ASSESSMENT_TTL,
        )
        log.warning("Upload key %s expired before assessment (task %s)", upload_key, task_id)
        return False

    from discovery.services.uploaded_assessment import compute_uploaded_bgc_assessment

    result = compute_uploaded_bgc_assessment(uploaded_data)

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=UPLOAD_ASSESSMENT_TTL,
    )
    log.info("Uploaded BGC assessment completed (task %s)", task_id)
    return True


@shared_task(name="discovery.tasks.assess_uploaded_assembly", bind=True, acks_late=True)
def assess_uploaded_assembly(self, upload_key: str) -> bool:
    """Run a full assembly assessment on uploaded (cached) data."""
    from django.core.cache import cache

    task_id = self.request.id
    search_key = f"assess_upload_assembly:{upload_key}"

    set_job_cache(search_key=search_key, task_id=task_id, timeout=UPLOAD_ASSESSMENT_TTL)

    uploaded_data = cache.get(upload_key)
    if not uploaded_data:
        set_job_cache(
            search_key=search_key,
            results={"error": "Upload expired — please re-upload"},
            task_id=task_id,
            timeout=UPLOAD_ASSESSMENT_TTL,
        )
        log.warning("Upload key %s expired before assessment (task %s)", upload_key, task_id)
        return False

    from discovery.services.uploaded_assessment import compute_uploaded_assembly_assessment

    result = compute_uploaded_assembly_assessment(uploaded_data)

    set_job_cache(
        search_key=search_key,
        results=result,
        task_id=task_id,
        timeout=UPLOAD_ASSESSMENT_TTL,
    )
    log.info("Uploaded assembly assessment completed (task %s)", task_id)
    return True


@shared_task(name="discovery.tasks.recompute_scores", bind=True, acks_late=True)
def recompute_scores_task(self) -> bool:
    """Recompute all discovery scores (novelty, assembly, GCF, catalogs, UMAP)."""
    from discovery.services.scores import recompute_all_scores

    recompute_all_scores()
    log.info("Score recomputation complete (task %s)", self.request.id)
    return True


@shared_task(name="discovery.tasks.chemical_similarity_search", bind=True, acks_late=True)
def chemical_similarity_search(self, smiles: str, similarity_threshold: float) -> dict[int, float]:
    """Compute ChemOnt ontology-based semantic similarity of a SMILES query.

    Classifies the query SMILES into ChemOnt terms, then computes
    IC-based (Resnik / Best Match Average) similarity against each BGC's
    natural product ChemOnt annotations.

    Returns a dict mapping BGC id → max similarity score.
    Runs in the Celery worker where RDKit is available.
    """
    from collections import defaultdict

    from common_core.chemont.classifier import classify_smiles
    from common_core.chemont.ontology import get_ontology
    from common_core.chemont.similarity import best_match_average, normalize_similarity

    from discovery.models import NaturalProductChemOntClass, PrecomputedStats

    ont = get_ontology()

    # Step 1: Classify query SMILES into ChemOnt terms.
    query_classes = classify_smiles(smiles.strip(), ontology=ont)
    if not query_classes:
        log.warning("No ChemOnt matches for SMILES: %s", smiles[:50])
        return {}
    query_term_ids = [c.chemont_id for c in query_classes]

    # Step 2: Load precomputed IC values.
    ic_row = PrecomputedStats.objects.filter(key="chemont_ic").first()
    if not ic_row or not ic_row.data:
        log.warning("No precomputed ChemOnt IC values — run recompute_all_scores first")
        return {}
    ic_values: dict[str, float] = ic_row.data

    # Step 3: Load all NP ChemOnt annotations grouped by BGC.
    np_chemont = (
        NaturalProductChemOntClass.objects
        .filter(natural_product__bgc__isnull=False)
        .values_list("natural_product__bgc_id", "chemont_id")
    )
    bgc_terms: dict[int, set[str]] = defaultdict(set)
    for bgc_id, cid in np_chemont:
        bgc_terms[bgc_id].add(cid)

    # Step 4: Compute similarity per BGC.
    bgc_similarities: dict[int, float] = {}
    for bgc_id, np_terms in bgc_terms.items():
        raw = best_match_average(query_term_ids, list(np_terms), ic_values, ont)
        score = normalize_similarity(raw, ic_values)
        if score >= similarity_threshold:
            bgc_similarities[bgc_id] = round(score, 4)

    log.info(
        "Chemical query (ChemOnt): SMILES=%s threshold=%.2f matches=%d",
        smiles[:50], similarity_threshold, len(bgc_similarities),
    )
    return bgc_similarities


SEQUENCE_QUERY_TTL = 3_600  # 1 hour

_VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


@shared_task(name="discovery.tasks.train_umap_model", bind=True, acks_late=True)
def train_umap_model_task(
    self,
    n_samples: int = 50_000,
    stratify_by_gcf: bool = False,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    metric: str = "cosine",
    pca_components: int | None = 50,
    apply: bool = False,
) -> dict:
    """Train a UMAP model from BGC embeddings and optionally apply it.

    Runs in the Celery worker where sklearn + umap-learn are available.
    Returns a summary dict with the created UMAPTransform pk, sha256, and
    the number of embeddings used for fitting / transformed.
    """
    import hashlib
    import pickle

    import numpy as np
    import sklearn
    import umap

    from discovery.models import BgcEmbedding

    task_id = self.request.id
    log.info(
        "train_umap_model starting (task %s, n_samples=%d, stratify=%s)",
        task_id, n_samples, stratify_by_gcf,
    )

    if stratify_by_gcf:
        sample_ids = _stratified_sample_bgc_ids(n_samples)
    else:
        total = BgcEmbedding.objects.count()
        if total <= n_samples:
            sample_ids = list(BgcEmbedding.objects.values_list("bgc_id", flat=True))
        else:
            sample_ids = list(
                BgcEmbedding.objects.order_by("?").values_list("bgc_id", flat=True)[:n_samples]
            )

    vectors = [
        vector.to_list()
        for _, vector in BgcEmbedding.objects.filter(bgc_id__in=sample_ids).values_list("bgc_id", "vector")
    ]

    if not vectors:
        log.error("train_umap_model: no embeddings found (task %s)", task_id)
        return {"error": "no embeddings found"}

    embeddings = np.array(vectors, dtype=np.float32)
    log.info("Collected %d embeddings, shape %s", embeddings.shape[0], embeddings.shape)

    pca_k = min(pca_components or embeddings.shape[1], embeddings.shape[1], embeddings.shape[0])
    if pca_k < embeddings.shape[1]:
        from sklearn.decomposition import PCA

        log.info("Running PCA to %d components", pca_k)
        pca = PCA(n_components=pca_k)
        reduced = pca.fit_transform(embeddings)
    else:
        reduced = embeddings
        pca = None

    log.info(
        "Training UMAP (n_neighbors=%d, min_dist=%.3f, metric=%s)",
        n_neighbors, min_dist, metric,
    )
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric=metric,
        n_components=2,
        random_state=42,
    )
    reducer.fit_transform(reduced)
    log.info("UMAP training complete")

    model_bundle = {"pca": pca, "umap": reducer}
    model_blob = pickle.dumps(model_bundle)
    model_hash = hashlib.sha256(model_blob).hexdigest()

    result: dict = {
        "task_id": task_id,
        "n_samples_fit": len(vectors),
        "pca_components": pca_k,
        "sha256": model_hash,
    }

    try:
        from mgnify_bgcs.models import UMAPTransform

        obj, created = UMAPTransform.objects.update_or_create(
            sha256=model_hash,
            defaults={
                "n_samples_fit": len(vectors),
                "pca_components": pca_k,
                "n_neighbors": n_neighbors,
                "min_dist": min_dist,
                "metric": metric,
                "sklearn_version": sklearn.__version__,
                "umap_version": umap.__version__,
                "model_blob": model_blob,
            },
        )
        result["umap_transform_pk"] = obj.pk
        result["created"] = created
        log.info(
            "%s UMAPTransform pk=%s sha256=%s (task %s)",
            "Created" if created else "Updated", obj.pk, model_hash[:12], task_id,
        )
    except ImportError:
        log.warning("mgnify_bgcs app not available — model not saved to DB")
        result["umap_transform_pk"] = None
        result["created"] = False

    if apply:
        log.info("Applying UMAP transform to all embeddings")
        applied = _apply_umap_transform(model_bundle)
        result["applied_count"] = applied
        log.info("UMAP coordinates updated for %d BGCs", applied)

    return result


def _stratified_sample_bgc_ids(n_samples: int) -> list[int]:
    """Sample BGC embedding ids stratified by gene_cluster_family."""
    from django.db.models import Count

    from discovery.models import BgcEmbedding, DashboardBgc

    families = (
        DashboardBgc.objects.exclude(gene_cluster_family="")
        .filter(embedding__isnull=False)
        .values("gene_cluster_family")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")
    )
    family_list = list(families)
    total_with_family = sum(f["cnt"] for f in family_list)

    no_family_count = BgcEmbedding.objects.filter(bgc__gene_cluster_family="").count()
    total = total_with_family + no_family_count

    if total <= n_samples:
        return list(BgcEmbedding.objects.values_list("bgc_id", flat=True))

    sample_ids: list[int] = []
    for fam in family_list:
        proportion = fam["cnt"] / total
        n_from_family = max(1, int(proportion * n_samples))
        ids = list(
            DashboardBgc.objects.filter(
                gene_cluster_family=fam["gene_cluster_family"],
                embedding__isnull=False,
            )
            .order_by("?")
            .values_list("id", flat=True)[:n_from_family]
        )
        sample_ids.extend(ids)

    remaining = n_samples - len(sample_ids)
    if remaining > 0 and no_family_count > 0:
        ids = list(
            BgcEmbedding.objects.filter(bgc__gene_cluster_family="")
            .order_by("?")
            .values_list("bgc_id", flat=True)[:remaining]
        )
        sample_ids.extend(ids)

    return sample_ids[:n_samples]


def _apply_umap_transform(model_bundle: dict) -> int:
    """Transform all embeddings and bulk-update DashboardBgc umap_x/umap_y. Returns count."""
    import numpy as np

    from discovery.models import BgcEmbedding, DashboardBgc

    BATCH = 10_000

    bgc_ids: list[int] = []
    vectors: list = []
    for bgc_id, vector in BgcEmbedding.objects.values_list("bgc_id", "vector"):
        bgc_ids.append(bgc_id)
        vectors.append(vector.to_list())

    if not vectors:
        return 0

    embeddings = np.array(vectors, dtype=np.float32)

    pca = model_bundle.get("pca")
    if pca is not None:
        embeddings = pca.transform(embeddings)

    reducer = model_bundle["umap"]
    coords = reducer.transform(embeddings)

    objs = DashboardBgc.objects.in_bulk(bgc_ids)
    updated = 0
    batch: list = []
    for i, bgc_id in enumerate(bgc_ids):
        bgc = objs.get(bgc_id)
        if bgc is None:
            continue
        bgc.umap_x = float(coords[i, 0])
        bgc.umap_y = float(coords[i, 1])
        batch.append(bgc)
        updated += 1

        if len(batch) >= BATCH:
            DashboardBgc.objects.bulk_update(batch, ["umap_x", "umap_y"], batch_size=BATCH)
            batch.clear()

    if batch:
        DashboardBgc.objects.bulk_update(batch, ["umap_x", "umap_y"], batch_size=BATCH)

    return updated


@shared_task(name="discovery.tasks.run_bgc_clustering", bind=True, acks_late=True)
def run_bgc_clustering_task(
    self,
    n_samples: int = 100_000,
    pca_components: int = 50,
    umap_n_neighbors: int = 30,
    umap_min_dist: float = 0.0,
    umap_n_components: int = 20,
    umap_metric: str = "euclidean",
    hdbscan_min_cluster_size: int = 20,
    hdbscan_min_samples: int = 5,
    knn_k: int = 5,
    apply: bool = False,
) -> dict:
    """Full PCA → UMAP-20d → HDBSCAN → KNN → UMAP-2d clustering pipeline.

    Supersedes train_umap_model_task. This is the primary mechanism for GCF
    annotation and for generating DashboardBgc.umap_x/y visualization coordinates.
    """
    import pickle

    import hdbscan as hdbscan_lib
    import numpy as np
    import sklearn
    import umap as umap_lib

    from discovery.models import (
        BgcCluster,
        ClusterAssignment,
        ClusteringRun,
        DashboardBgc,
    )
    from discovery.services.clustering import (
        build_training_sample,
        classify_remaining,
        compute_bundle_sha256,
        pick_representative,
        run_hdbscan,
        run_pca,
        run_umap,
        run_umap_2d,
        train_knn,
    )

    task_id = self.request.id
    log.info("run_bgc_clustering starting (task %s, n_samples=%d)", task_id, n_samples)

    # ── 1. Sample embeddings ─────────────────────────────────────────────
    bgc_ids, embeddings = build_training_sample(n_samples)
    if not bgc_ids:
        log.error("run_bgc_clustering: no embeddings found (task %s)", task_id)
        return {"error": "no embeddings found"}

    # ── 2. PCA ───────────────────────────────────────────────────────────
    pca_reduced, pca = run_pca(embeddings, n_components=pca_components)

    # ── 3. UMAP-20d ──────────────────────────────────────────────────────
    umap_20d, umap_reducer = run_umap(
        pca_reduced,
        n_neighbors=umap_n_neighbors,
        min_dist=umap_min_dist,
        n_components=umap_n_components,
        metric=umap_metric,
    )

    # ── 4. HDBSCAN ───────────────────────────────────────────────────────
    labels, hdbscan_model = run_hdbscan(
        umap_20d,
        min_cluster_size=hdbscan_min_cluster_size,
        min_samples=hdbscan_min_samples,
    )

    # ── 5. KNN ───────────────────────────────────────────────────────────
    knn = train_knn(umap_20d, labels, k=knn_k)

    # ── 6. UMAP-2d for visualization ─────────────────────────────────────
    umap_2d, umap2d_reducer = run_umap_2d(umap_20d)

    # ── 7. Pickle + sha256 ───────────────────────────────────────────────
    pca_blob = pickle.dumps(pca)
    umap_blob = pickle.dumps(umap_reducer)
    hdbscan_blob = pickle.dumps(hdbscan_model)
    knn_blob = pickle.dumps(knn)
    umap2d_blob = pickle.dumps(umap2d_reducer)
    sha = compute_bundle_sha256(pca_blob, umap_blob, hdbscan_blob, knn_blob, umap2d_blob)

    n_clusters = int(len(set(labels)) - (1 if -1 in labels else 0))
    n_noise = int((labels == -1).sum())

    # ── 8. Persist ClusteringRun ─────────────────────────────────────────
    run, created = ClusteringRun.objects.update_or_create(
        sha256=sha,
        defaults={
            "n_samples": n_samples,
            "pca_components": pca_components,
            "umap_n_neighbors": umap_n_neighbors,
            "umap_min_dist": umap_min_dist,
            "umap_n_components": umap_n_components,
            "umap_metric": umap_metric,
            "hdbscan_min_cluster_size": hdbscan_min_cluster_size,
            "hdbscan_min_samples": hdbscan_min_samples,
            "knn_k": knn_k,
            "sklearn_version": sklearn.__version__,
            "umap_version": umap_lib.__version__,
            "hdbscan_version": hdbscan_lib.__version__,
            "n_bgcs_sampled": len(bgc_ids),
            "n_clusters_found": n_clusters,
            "n_noise_points": n_noise,
            "pca_blob": pca_blob,
            "umap_blob": umap_blob,
            "hdbscan_blob": hdbscan_blob,
            "knn_blob": knn_blob,
            "umap2d_blob": umap2d_blob,
        },
    )
    log.info("%s ClusteringRun pk=%s (task %s)", "Created" if created else "Updated", run.pk, task_id)

    # ── 9. Create BgcCluster records ─────────────────────────────────────
    unique_labels = sorted(set(labels))
    label_to_cluster: dict[int, BgcCluster] = {}

    # Build per-cluster bgc_id lists and 20d coord arrays
    label_bgc_ids: dict[int, list[int]] = {lbl: [] for lbl in unique_labels}
    label_coords: dict[int, list] = {lbl: [] for lbl in unique_labels}
    for i, (bgc_id, lbl) in enumerate(zip(bgc_ids, labels)):
        label_bgc_ids[int(lbl)].append(bgc_id)
        label_coords[int(lbl)].append(umap_20d[i])

    BgcCluster.objects.filter(clustering_run=run).delete()
    cluster_objects = []
    for lbl in unique_labels:
        lbl_int = int(lbl)
        ids_in_cluster = label_bgc_ids[lbl_int]
        coords_in_cluster = np.array(label_coords[lbl_int])
        validated_count = DashboardBgc.objects.filter(
            pk__in=ids_in_cluster, is_validated=True
        ).count()
        rep_id = pick_representative(ids_in_cluster, coords_in_cluster)
        rep_bgc = DashboardBgc.objects.filter(pk=rep_id).first()
        label_str = "cluster.noise" if lbl_int == -1 else f"cluster.{lbl_int:04d}"
        cluster_objects.append(
            BgcCluster(
                clustering_run=run,
                cluster_id=lbl_int,
                label=label_str,
                n_bgcs=len(ids_in_cluster),
                n_validated=validated_count,
                representative_bgc=rep_bgc,
            )
        )

    BgcCluster.objects.bulk_create(cluster_objects)
    for c in BgcCluster.objects.filter(clustering_run=run):
        label_to_cluster[c.cluster_id] = c

    # ── 10. ClusterAssignment for training sample ─────────────────────────
    ClusterAssignment.objects.filter(run=run).delete()
    assignment_batch: list[ClusterAssignment] = []
    BATCH = 10_000
    for bgc_id, lbl, xy in zip(bgc_ids, labels, umap_2d):
        lbl_int = int(lbl)
        cluster = label_to_cluster.get(lbl_int)
        if cluster is None:
            continue
        bgc_obj = DashboardBgc.objects.filter(pk=bgc_id).first()
        if bgc_obj is None:
            continue
        assignment_batch.append(
            ClusterAssignment(
                run=run,
                bgc=bgc_obj,
                cluster=cluster,
                is_noise=(lbl_int == -1),
                assigned_by_knn=False,
            )
        )
        bgc_obj.umap_x = float(xy[0])
        bgc_obj.umap_y = float(xy[1])
        if len(assignment_batch) >= BATCH:
            ClusterAssignment.objects.bulk_create(assignment_batch, ignore_conflicts=True)
            DashboardBgc.objects.bulk_update(
                [a.bgc for a in assignment_batch], ["umap_x", "umap_y"], batch_size=BATCH
            )
            assignment_batch.clear()

    if assignment_batch:
        ClusterAssignment.objects.bulk_create(assignment_batch, ignore_conflicts=True)
        DashboardBgc.objects.bulk_update(
            [a.bgc for a in assignment_batch], ["umap_x", "umap_y"], batch_size=BATCH
        )

    # ── 11-14. Classify + update remaining BGCs via KNN ──────────────────
    excluded_ids = set(bgc_ids)
    knn_results = classify_remaining(
        knn, pca, umap_reducer, umap2d_reducer, excluded_ids
    )
    run.n_bgcs_classified = len(knn_results)
    run.save(update_fields=["n_bgcs_classified"])

    knn_batch: list[ClusterAssignment] = []
    bgc_umap_batch: list[DashboardBgc] = []
    for bgc_id, (lbl_int, x, y) in knn_results.items():
        cluster = label_to_cluster.get(lbl_int)
        if cluster is None:
            continue
        bgc_obj = DashboardBgc.objects.filter(pk=bgc_id).first()
        if bgc_obj is None:
            continue
        knn_batch.append(
            ClusterAssignment(
                run=run,
                bgc=bgc_obj,
                cluster=cluster,
                is_noise=(lbl_int == -1),
                assigned_by_knn=True,
            )
        )
        bgc_obj.umap_x = x
        bgc_obj.umap_y = y
        bgc_umap_batch.append(bgc_obj)
        if len(knn_batch) >= BATCH:
            ClusterAssignment.objects.bulk_create(knn_batch, ignore_conflicts=True)
            DashboardBgc.objects.bulk_update(bgc_umap_batch, ["umap_x", "umap_y"], batch_size=BATCH)
            knn_batch.clear()
            bgc_umap_batch.clear()

    if knn_batch:
        ClusterAssignment.objects.bulk_create(knn_batch, ignore_conflicts=True)
        DashboardBgc.objects.bulk_update(bgc_umap_batch, ["umap_x", "umap_y"], batch_size=BATCH)

    # ── 15. Apply GCF assignments if requested ────────────────────────────
    gcf_updated = 0
    if apply:
        gcf_updated = _apply_gcf_assignments(run)
        log.info("GCF annotation: %d BGCs updated", gcf_updated)

    result = {
        "task_id": task_id,
        "run_pk": run.pk,
        "sha256": sha,
        "n_bgcs_sampled": len(bgc_ids),
        "n_clusters_found": n_clusters,
        "n_noise_points": n_noise,
        "n_bgcs_classified": len(knn_results),
        "gcf_updated": gcf_updated,
    }
    log.info("run_bgc_clustering complete: %s", result)
    return result


def _classify_with_knn(embedding: list[float]) -> dict:
    """Transform a single 960-d embedding through the latest ClusteringRun's models.

    Returns cluster metadata dict, or {} if no ClusteringRun exists yet.
    Importable directly (not a task) for use in assessment services.
    """
    import pickle

    import numpy as np

    from discovery.models import BgcCluster, ClusteringRun

    run = ClusteringRun.objects.order_by("-created_at").first()
    if run is None:
        return {}

    pca = pickle.loads(bytes(run.pca_blob))
    umap_20d = pickle.loads(bytes(run.umap_blob))
    knn = pickle.loads(bytes(run.knn_blob))
    umap_2d = pickle.loads(bytes(run.umap2d_blob))

    arr = np.array([embedding], dtype=np.float32)
    arr = pca.transform(arr)
    arr20 = umap_20d.transform(arr)
    arr2 = umap_2d.transform(arr20)
    label_int = int(knn.predict(arr20)[0])

    cluster = BgcCluster.objects.filter(
        clustering_run=run, cluster_id=label_int
    ).first()
    label_str = (
        cluster.label if cluster
        else ("cluster.noise" if label_int == -1 else f"cluster.{label_int:04d}")
    )

    return {
        "cluster_id": label_int,
        "cluster_label": label_str,
        "umap_x": float(arr2[0, 0]),
        "umap_y": float(arr2[0, 1]),
        "run_id": run.pk,
        "assigned_by_knn": True,
    }


def _apply_gcf_assignments(run: "ClusteringRun") -> int:  # noqa: F821
    """Create/update DashboardGCF records and update DashboardBgc.gene_cluster_family."""
    from discovery.models import BgcCluster, ClusterAssignment, DashboardBgc, DashboardGCF

    BATCH = 10_000

    for cluster in BgcCluster.objects.filter(clustering_run=run).select_related(
        "representative_bgc"
    ):
        DashboardGCF.objects.update_or_create(
            family_id=cluster.label,
            defaults={
                "member_count": cluster.n_bgcs,
                "validated_count": cluster.n_validated,
                "representative_bgc": cluster.representative_bgc,
            },
        )

    bgc_batch: list[DashboardBgc] = []
    updated = 0
    for assignment in (
        ClusterAssignment.objects.filter(run=run)
        .select_related("bgc", "cluster")
        .iterator(chunk_size=BATCH)
    ):
        assignment.bgc.gene_cluster_family = assignment.cluster.label
        bgc_batch.append(assignment.bgc)
        updated += 1
        if len(bgc_batch) >= BATCH:
            DashboardBgc.objects.bulk_update(bgc_batch, ["gene_cluster_family"], batch_size=BATCH)
            bgc_batch.clear()

    if bgc_batch:
        DashboardBgc.objects.bulk_update(bgc_batch, ["gene_cluster_family"], batch_size=BATCH)

    return updated


@shared_task(name="discovery.tasks.sequence_similarity_search", bind=True, acks_late=True)
def sequence_similarity_search(self, sequence: str, similarity_threshold: float) -> dict[int, float]:
    """Embed a protein sequence with ESM-C and find BGCs with similar proteins.

    Returns a dict mapping BGC id → max cosine similarity score.
    Runs in the Celery worker where torch + ESM are available.
    """
    import numpy as np
    from django.db import connection

    from discovery.models import DashboardCds

    # Validate
    seq = sequence.strip().upper()
    if not seq:
        log.warning("Empty sequence passed to sequence_similarity_search")
        return {}
    if len(seq) > 5000:
        log.warning("Sequence too long (%d AA), max 5000", len(seq))
        return {}
    invalid = set(seq) - _VALID_AA
    if invalid:
        log.warning("Invalid amino acid characters: %s", invalid)
        return {}

    # Embed
    from common_core.esmc_embedder import embed_sequences

    results = embed_sequences([seq])
    if not results or results[0] is None:
        log.error("ESM-C embedding failed for sequence (len=%d)", len(seq))
        return {}

    # Extract layer 26 → 960-dim vector
    embedding = results[0][26].astype(np.float32)
    vec_str = "[" + ",".join(str(float(v)) for v in embedding) + "]"

    # pgvector cosine distance search
    max_distance = 1.0 - similarity_threshold
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT protein_sha256, (vector <=> %s::halfvec(1152)) AS distance
            FROM discovery_protein_embedding
            WHERE (vector <=> %s::halfvec(1152)) <= %s
            """,
            [vec_str, vec_str, max_distance],
        )
        rows = cursor.fetchall()

    if not rows:
        log.info("Sequence query: no protein matches at threshold=%.2f", similarity_threshold)
        return {}

    # Map matched protein_sha256 → BGC ids via DashboardCds
    matched_sha256s = {r[0]: 1.0 - r[1] for r in rows}  # sha256 → similarity
    cds_qs = (
        DashboardCds.objects.filter(protein_sha256__in=matched_sha256s.keys())
        .values_list("bgc_id", "protein_sha256")
    )

    bgc_similarities: dict[int, float] = {}
    for bgc_id, sha256 in cds_qs:
        sim = matched_sha256s[sha256]
        existing = bgc_similarities.get(bgc_id, 0.0)
        bgc_similarities[bgc_id] = max(existing, sim)

    log.info(
        "Sequence query: len=%d threshold=%.2f protein_matches=%d bgc_matches=%d",
        len(seq), similarity_threshold, len(rows), len(bgc_similarities),
    )
    return bgc_similarities


@shared_task(name="discovery.tasks.update_discovery_stats", bind=True, acks_late=True)
def update_discovery_stats_task(self) -> bool:
    """Recompute platform-overview counts and append a new DiscoveryStats row."""
    from django.db import transaction

    from discovery.models import DiscoveryStats
    from discovery.services.stats import generate_discovery_stats

    stats = generate_discovery_stats()
    with transaction.atomic():
        ds = DiscoveryStats.objects.create(stats=stats)
    log.info("DiscoveryStats id=%s created: %s", ds.pk, stats)
    return True
