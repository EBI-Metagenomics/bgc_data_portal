"""Discovery Platform models — iBGC-first, contig-anchored CDS/domains.

Core entity hierarchy (top-down):

    DashboardAssembly
        └─ DashboardContig
            ├─ ContigCds                 (CDS on contig; range-indexed)
            │     └─ ContigDomain        (domain hits; denormalised contig FK)
            ├─ ConsensusBgc (cBGC)       (chained-overlap region; MGYB-XXXXXX)
            │     └─ IntegratedBgc (iBGC) (core operational unit; MGYB-XXXXXX-YY)
            │           ├─ SourceBgcPrediction (per-tool prediction)
            │           └─ IbgcNaturalProduct  (NP claim, deduped at ingest)
            └─ (sequences on demand)

Hierarchical fields (taxonomy_path, biome_path, classification_path,
np_class_path, gene_cluster_family) store dot-delimited ltree paths.

The migration installs ``ltree`` and ``btree_gist`` extensions and creates
GiST indexes on the int4range columns so ``contig_id WITH =, *_range WITH &&``
exclusion constraints enforce iBGC disjointness and cBGC disjointness in
the database, and so range overlap queries hit a GiST index.

iBGCs are strictly disjoint within a cBGC; CDS membership in an iBGC is
decided by range overlap (``ContigCds.cds_range && IntegratedBgc.bgc_range``)
on the same contig.
"""

from .accessions import (
    AccessionAlias,
    AccessionEntityType,
    AccessionRegistry,
)
from .annotation import (
    CdsSequence,
    ContigCds,
    ContigDomain,
)
from .assembly import (
    AssemblySource,
    AssemblyType,
    ContigSequence,
    DashboardAssembly,
    DashboardContig,
    Taxon,
)
from .bgc import (
    ConsensusBgc,
    DashboardDetector,
    IntegratedBgc,
    SourceBgcPrediction,
)
from .catalog import (
    DashboardBgcClass,
    DashboardDomain,
    DiscoveryStats,
)
from .clustering import (
    ClusteringRun,
    DashboardGCF,
    DomainEnrichment,
    IbgcClusteringSnapshot,
)
from .mixins import (
    RangeFieldMixin,
    ZlibSequenceMixin,
)
from .npc import (
    IbgcNpcLabel,
    NpcTerm,
    NpcTermEdge,
    SourceBgcNpcLabel,
)

__all__ = [
    "AccessionAlias",
    "AccessionEntityType",
    "AccessionRegistry",
    "AssemblySource",
    "AssemblyType",
    "CdsSequence",
    "ClusteringRun",
    "ConsensusBgc",
    "ContigCds",
    "ContigDomain",
    "ContigSequence",
    "DashboardAssembly",
    "DashboardBgcClass",
    "DashboardContig",
    "DashboardDetector",
    "DashboardDomain",
    "DashboardGCF",
    "DiscoveryStats",
    "DomainEnrichment",
    "IbgcClusteringSnapshot",
    "IbgcNpcLabel",
    "IntegratedBgc",
    "NpcTerm",
    "NpcTermEdge",
    "RangeFieldMixin",
    "SourceBgcNpcLabel",
    "SourceBgcPrediction",
    "Taxon",
    "ZlibSequenceMixin",
]
