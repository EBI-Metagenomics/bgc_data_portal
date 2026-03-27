"""Unit tests for discovery scoring service."""

import pytest
from discovery.services.scoring import compute_composite_priority


class TestComputeCompositePriority:
    def test_equal_weights(self):
        scores = {"a": 0.8, "b": 0.6, "c": 0.4}
        weights = {"a": 1.0, "b": 1.0, "c": 1.0}
        result = compute_composite_priority(scores, weights)
        assert abs(result - 0.6) < 1e-9

    def test_unequal_weights(self):
        scores = {"novelty": 1.0, "diversity": 0.0}
        weights = {"novelty": 0.8, "diversity": 0.2}
        # (1.0 * 0.8 + 0.0 * 0.2) / (0.8 + 0.2) = 0.8
        result = compute_composite_priority(scores, weights)
        assert abs(result - 0.8) < 1e-9

    def test_single_weight_dominates(self):
        scores = {"a": 0.5, "b": 0.9}
        weights = {"a": 0.0, "b": 1.0}
        result = compute_composite_priority(scores, weights)
        assert abs(result - 0.9) < 1e-9

    def test_zero_weights_returns_zero(self):
        scores = {"a": 0.8, "b": 0.6}
        weights = {"a": 0.0, "b": 0.0}
        assert compute_composite_priority(scores, weights) == 0.0

    def test_empty_scores(self):
        assert compute_composite_priority({}, {"a": 1.0}) == 0.0

    def test_empty_weights(self):
        assert compute_composite_priority({"a": 0.8}, {}) == 0.0

    def test_both_empty(self):
        assert compute_composite_priority({}, {}) == 0.0

    def test_mismatched_keys_ignored(self):
        scores = {"a": 0.5}
        weights = {"a": 1.0, "b": 1.0}  # b has no score
        result = compute_composite_priority(scores, weights)
        assert abs(result - 0.5) < 1e-9

    def test_genome_mode_defaults(self):
        scores = {
            "diversity": 0.7,
            "novelty": 0.3,
            "density": 0.5,
            "taxonomic": 0.8,
            "quality": 0.9,
        }
        weights = {
            "diversity": 0.25,
            "novelty": 0.40,
            "density": 0.15,
            "taxonomic": 0.10,
            "quality": 0.10,
        }
        result = compute_composite_priority(scores, weights)
        expected = (
            0.7 * 0.25 + 0.3 * 0.40 + 0.5 * 0.15 + 0.8 * 0.10 + 0.9 * 0.10
        ) / 1.0
        assert abs(result - expected) < 1e-9

    def test_result_bounded_zero_one(self):
        scores = {"a": 0.0, "b": 1.0}
        weights = {"a": 0.5, "b": 0.5}
        result = compute_composite_priority(scores, weights)
        assert 0.0 <= result <= 1.0
