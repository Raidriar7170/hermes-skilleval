from hermes_skilleval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
)


def test_recall_at_k_detects_gold_hit():
    assert recall_at_k(["a", "b", "c"], ["b"], 1) == 0.0
    assert recall_at_k(["a", "b", "c"], ["b"], 2) == 1.0


def test_precision_at_k_counts_gold_fraction():
    assert precision_at_k(["a", "b", "c"], ["a", "c"], 3) == 2 / 3


def test_mrr_uses_first_gold_rank():
    assert mean_reciprocal_rank(["x", "gold", "other"], ["gold"]) == 0.5
    assert mean_reciprocal_rank(["x", "y"], ["gold"]) == 0.0


def test_ndcg_at_k_rewards_better_ordering():
    good = ndcg_at_k(["a", "b", "c"], ["a", "c"], 3)
    bad = ndcg_at_k(["b", "c", "a"], ["a", "c"], 3)

    assert good > bad


def test_negative_hit_rate_detects_bad_skills():
    assert negative_hit_rate(["a", "bad"], ["bad"], 2) == 1.0
    assert negative_hit_rate(["a", "b"], ["bad"], 2) == 0.0


def test_at_k_metrics_ignore_non_positive_k():
    assert recall_at_k(["gold", "other"], ["gold"], -1) == 0.0
    assert precision_at_k(["gold"], ["gold"], 0) == 0.0
    assert ndcg_at_k(["gold", "other"], ["gold"], -1) == 0.0
    assert negative_hit_rate(["bad", "other"], ["bad"], -1) == 0.0
