from hermes_skilleval.metrics import (
    abstention_rate,
    accepted_count,
    accepted_recall_at_k,
    coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_accepted_rate,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
    selection_rate_at_k,
)


def test_recall_at_k_detects_gold_hit():
    assert recall_at_k(["a", "b", "c"], ["b"], 1) == 0.0
    assert recall_at_k(["a", "b", "c"], ["b"], 2) == 1.0


def test_precision_at_k_counts_gold_fraction():
    assert precision_at_k(["a", "b", "c"], ["a", "c"], 3) == 2 / 3


def test_precision_at_k_uses_requested_k_as_denominator():
    assert precision_at_k(["gold"], ["gold"], 5) == 0.2


def test_mrr_uses_first_gold_rank():
    assert mean_reciprocal_rank(["x", "gold", "other"], ["gold"]) == 0.5
    assert mean_reciprocal_rank(["x", "y"], ["gold"]) == 0.0


def test_ndcg_at_k_rewards_better_ordering():
    good = ndcg_at_k(["a", "b", "c"], ["a", "c"], 3)
    bad = ndcg_at_k(["b", "c", "a"], ["a", "c"], 3)

    assert good > bad


def test_ndcg_at_k_does_not_double_count_duplicate_selected_gold():
    score = ndcg_at_k(["gold", "gold", "gold"], ["gold"], 3)

    assert 0.0 <= score <= 1.0
    assert score == 1.0


def test_negative_hit_rate_detects_bad_skills():
    assert negative_hit_rate(["a", "bad"], ["bad"], 2) == 1.0
    assert negative_hit_rate(["a", "b"], ["bad"], 2) == 0.0


def test_metrics_return_zero_for_empty_inputs():
    assert recall_at_k([], ["gold"], 1) == 0.0
    assert recall_at_k(["gold"], [], 1) == 0.0
    assert precision_at_k([], ["gold"], 1) == 0.0
    assert precision_at_k(["gold"], [], 1) == 0.0
    assert mean_reciprocal_rank([], ["gold"]) == 0.0
    assert mean_reciprocal_rank(["gold"], []) == 0.0
    assert ndcg_at_k([], ["gold"], 1) == 0.0
    assert ndcg_at_k(["gold"], [], 1) == 0.0
    assert negative_hit_rate([], ["bad"], 1) == 0.0
    assert negative_hit_rate(["bad"], [], 1) == 0.0


def test_duplicate_gold_labels_are_collapsed():
    gold = ["gold", "gold"]

    assert recall_at_k(["gold"], gold, 1) == 1.0
    assert precision_at_k(["gold"], gold, 1) == 1.0
    assert mean_reciprocal_rank(["gold"], gold) == 1.0
    assert ndcg_at_k(["gold"], gold, 1) == 1.0


def test_at_k_metrics_ignore_non_positive_k():
    assert recall_at_k(["gold", "other"], ["gold"], -1) == 0.0
    assert precision_at_k(["gold"], ["gold"], 0) == 0.0
    assert ndcg_at_k(["gold", "other"], ["gold"], -1) == 0.0
    assert negative_hit_rate(["bad", "other"], ["bad"], -1) == 0.0


def test_selective_metrics_measure_accepted_outputs():
    selected = ["gold", "helper"]

    assert accepted_count(selected) == 2
    assert coverage(selected) == 1.0
    assert abstention_rate(selected) == 0.0
    assert selection_rate_at_k(selected, 5) == 0.4
    assert accepted_recall_at_k(selected, ["gold"], 5) == 1.0
    assert negative_accepted_rate(selected, ["bad"], 5) == 0.0


def test_selective_metrics_measure_full_abstention():
    selected = []

    assert accepted_count(selected) == 0
    assert coverage(selected) == 0.0
    assert abstention_rate(selected) == 1.0
    assert selection_rate_at_k(selected, 5) == 0.0
    assert accepted_recall_at_k(selected, ["gold"], 5) == 0.0
    assert negative_accepted_rate(selected, ["bad"], 5) == 0.0
