"""
Runtime scoring for the Discovery Platform.

All BGC-level and assembly-level sub-scores are precomputed and stored in
AssemblyScore / BgcScore.  Only the composite priority score is computed at
query time, because its weights are user-tunable via dashboard sliders.
"""


def compute_composite_priority(
    scores: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Weighted sum of sub-scores, normalized by weight sum.

    Parameters
    ----------
    scores : dict
        Mapping of score names to their [0, 1] values.
        In Explore Assemblies mode these come from AssemblyScore:
            bgc_diversity_score, bgc_novelty_score, bgc_density
        In Query mode these come from BgcScore:
            query_similarity, novelty_score, domain_novelty
    weights : dict
        Mapping of the same score names to user-selected weights.
        Keys not present in *scores* are silently ignored.

    Returns
    -------
    float
        Composite priority in [0, 1].  Returns 0.0 when no matching
        score-weight pairs exist or when total weight is zero.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for key, weight in weights.items():
        if key in scores and weight > 0:
            weighted_sum += scores[key] * weight
            total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return weighted_sum / total_weight
