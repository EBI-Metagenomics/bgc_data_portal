"""Filter-option and stats endpoints that feed the dashboard chips."""

import logging

from django.db.models import (
    Count,
)

from discovery.api._common import (
    make_router,
    paginate,
)
from discovery.api_schemas import (
    BgcClassOption,
    DetectorOption,
    DiscoveryStatsResponse,
    GcfOption,
    NpcTreeNode,
    PaginatedDetectorResponse,
    PaginatedGcfResponse,
    PaginatedSourceResponse,
    PaginationMeta,
    SourceOption,
    TaxonomyNode,
)
from discovery.models import (
    AssemblySource,
    ClusteringRun,
    DashboardBgcClass,
    DashboardDetector,
    DashboardGCF,
    DiscoveryStats,
)
from discovery.security import first_party_gate
from discovery.services.npc import npc_tree

router = make_router()


logger = logging.getLogger(__name__)


@router.get(
    "/filters/taxonomy/",
    response=list[TaxonomyNode],
    include_in_schema=False,
    auth=first_party_gate,
)
def taxonomy_tree(request):
    from discovery.models import DashboardContig
    from discovery.services.taxonomy import ranked_labels, ranked_labels_by_taxon

    rows = list(
        DashboardContig.objects.exclude(taxonomy_path="")
        .values_list("taxonomy_path", "taxon_id")
        .annotate(n=Count("id"))
        .order_by()
    )
    lookup = ranked_labels_by_taxon(r[1] for r in rows)

    tree: dict = {}
    for path, taxon_id, n in rows:
        node = tree
        prefix: list[str] = []
        for rank, label in ranked_labels(path, taxon_id, lookup):
            prefix.append(label)
            if label not in node:
                node[label] = {
                    "_rank": rank,
                    "_path": ".".join(prefix),
                    "_count": 0,
                    "_children": {},
                }
            node[label]["_count"] += n
            node = node[label]["_children"]

    def _build_nodes(level: dict) -> list[TaxonomyNode]:
        return [
            TaxonomyNode(
                name=name,
                rank=data["_rank"],
                path=data["_path"],
                count=data["_count"],
                children=_build_nodes(data["_children"]),
            )
            for name, data in sorted(level.items())
        ]

    return _build_nodes(tree)


@router.get(
    "/filters/bgc-classes/",
    response=list[BgcClassOption],
    include_in_schema=False,
    auth=first_party_gate,
)
def bgc_classes(request):
    return [
        BgcClassOption(name=row.name, count=row.bgc_count)
        for row in DashboardBgcClass.objects.filter(bgc_count__gt=0).order_by(
            "-bgc_count"
        )
    ]


@router.get(
    "/filters/npc-tree/",
    response=list[NpcTreeNode],
    include_in_schema=False,
    auth=first_party_gate,
)
def npc_tree_endpoint(request):
    """NPClassifier ontology (pathway → superclass → class) with iBGC counts.

    ``count`` / ``confident_count`` are iBGCs carrying that exact term; the
    ``npc_terms`` filter also matches descendants of a selected term. Served
    from a short cache: the ontology is fixed and counts change only on load.
    """
    from django.core.cache import cache

    key = "discovery:npc-tree:v1"
    tree = cache.get(key)
    if tree is None:
        tree = npc_tree()
        cache.set(key, tree, 300)
    return tree


@router.get(
    "/filters/gcfs/",
    response=PaginatedGcfResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def gcf_list(
    request,
    search: str | None = None,
    level: int | None = None,
    page: int = 1,
    page_size: int = 50,
):
    # Scope to the latest ClusteringRun — IntegratedBgc.gene_cluster_family is
    # rewritten on every successful run, so this is the only set whose paths
    # match the live iBGC rows that ``leaf_path_prefix`` filters against.
    run = ClusteringRun.objects.order_by("-created_at").first()
    if run is None:
        return PaginatedGcfResponse(
            items=[],
            pagination=PaginationMeta(
                page=1, page_size=page_size, total_count=0, total_pages=0
            ),
        )

    from django.db.models.expressions import RawSQL

    qs = DashboardGCF.objects.filter(clustering_run=run, member_count__gt=0)
    if search:
        qs = qs.filter(family_path__icontains=search)
    if level is not None:
        qs = qs.filter(level=level)

    total_count = qs.count()
    pg, ps, tp, offset = paginate(page, page_size, total_count)

    # Paths are unpadded (e.g. "42.7.3"), so a plain string sort would order
    # "10" before "2". Cast the dot-path to an int[] for hierarchical numeric
    # ordering as the final tiebreaker.
    qs = qs.annotate(_path_key=RawSQL("string_to_array(family_path, '.')::int[]", []))
    items = [
        GcfOption(
            family_path=g.family_path,
            level=g.level,
            member_count=g.member_count,
            validated_count=g.validated_count,
            mean_novelty=g.mean_novelty,
        )
        for g in qs.order_by("-member_count", "level", "_path_key")[
            offset : offset + ps
        ]
    ]

    return PaginatedGcfResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


@router.get(
    "/filters/sources/",
    response=PaginatedSourceResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def source_list(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    qs = AssemblySource.objects.filter(assemblies__isnull=False).annotate(
        assembly_count=Count("assemblies", distinct=True)
    )
    if search:
        qs = qs.filter(name__icontains=search)
    total_count = qs.count()
    pg, ps, tp, offset = paginate(page, page_size, total_count)
    items = [
        SourceOption(name=s.name, count=s.assembly_count)
        for s in qs.order_by("-assembly_count")[offset : offset + ps]
    ]
    return PaginatedSourceResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


@router.get(
    "/filters/detectors/",
    response=PaginatedDetectorResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def detector_list(
    request,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    qs = (
        DashboardDetector.objects.values("tool")
        .annotate(count=Count("source_bgcs"))
        .filter(count__gt=0)
    )
    if search:
        qs = qs.filter(tool__icontains=search)
    total_count = qs.count()
    pg, ps, tp, offset = paginate(page, page_size, total_count)
    items = [
        DetectorOption(tool=d["tool"], count=d["count"])
        for d in qs.order_by("-count")[offset : offset + ps]
    ]
    return PaginatedDetectorResponse(
        items=items,
        pagination=PaginationMeta(
            page=pg, page_size=ps, total_count=total_count, total_pages=tp
        ),
    )


@router.get(
    "/stats/",
    response=DiscoveryStatsResponse,
    include_in_schema=False,
    auth=first_party_gate,
)
def discovery_stats(request):
    """Latest Discovery Platform overview counts for the Run Query card."""
    latest = DiscoveryStats.objects.order_by("-created_at").first()
    if latest is None:
        return DiscoveryStatsResponse()
    known = {
        k: v
        for k, v in latest.stats.items()
        if k in DiscoveryStatsResponse.model_fields
    }
    return DiscoveryStatsResponse(**known, updated_at=latest.updated_at)
