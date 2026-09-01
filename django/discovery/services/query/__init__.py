"""Combined Discovery query engine.

Houses the framework-independent criterion resolvers shared by the legacy
single-criterion ``/query/*`` endpoints/tasks and the combined multi-criterion
query. Each resolver maps iBGC ids to a per-criterion score payload; the
combined-query task intersects those across criteria (AND semantics) and the
roster/Variables-map layers render one (or more) sortable column per criterion.
"""

from .combined import criterion_label, run_combined_query
from .criteria import (
    CRITERION_METRICS,
    RESULT_CAP,
    ArchitectureParams,
    ChemicalParams,
    CriterionError,
    CriterionMetric,
    CriterionResult,
    DomainParams,
    SequenceParams,
    SimilarParams,
    architecture_top,
    build_params,
    parse_domain_tokens,
    resolve_architecture,
    resolve_chemical,
    resolve_criterion,
    resolve_domain,
    resolve_sequence,
    resolve_similar,
    run_chemical_search,
    run_sequence_search,
    similar_top,
)

__all__ = [
    "CRITERION_METRICS",
    "RESULT_CAP",
    "ArchitectureParams",
    "ChemicalParams",
    "CriterionError",
    "CriterionMetric",
    "CriterionResult",
    "DomainParams",
    "SequenceParams",
    "SimilarParams",
    "architecture_top",
    "build_params",
    "criterion_label",
    "parse_domain_tokens",
    "resolve_architecture",
    "resolve_chemical",
    "resolve_criterion",
    "resolve_domain",
    "resolve_sequence",
    "resolve_similar",
    "run_chemical_search",
    "run_combined_query",
    "run_sequence_search",
    "similar_top",
]
