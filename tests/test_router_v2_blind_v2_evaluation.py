from __future__ import annotations

from typing import Any

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation as evaluation


SEEDS = (7170, 7171, 7172)
PREFIX = "TEST_ONLY_DO_NOT_USE"


def _route_rows(arm: str, seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(64):
        baseline_rank = 2 if index % 4 == 0 else 1
        gold_rank = baseline_rank if arm == "A" else 1
        has_negative = index % 4 < 3
        negative_ordinal = (index // 4) * 3 + (index % 4)
        negative_rank = (2 if arm == "A" else 6) if has_negative else None
        rows.append(
            {
                "arm": arm,
                "seed": seed,
                "task_id": f"{PREFIX}_TASK_{index:02d}",
                "gold_skill_id": f"{PREFIX}_SKILL_{index // 4:02d}",
                "tempting_negative_skill_id": (
                    f"{PREFIX}_NEGATIVE_{negative_ordinal % 12:02d}"
                    if has_negative
                    else None
                ),
                "semantic_family_id": f"{PREFIX}_FAMILY_{index:02d}",
                "gold_rank": gold_rank,
                "tempting_negative_rank": negative_rank,
                "latency_ns": 10_000_000 if arm == "A" else 11_000_000,
            }
        )
    return rows


def _all_routes() -> list[dict[str, Any]]:
    return [
        row for seed in SEEDS for arm in ("A", "C") for row in _route_rows(arm, seed)
    ]


def _per_seed() -> list[dict[str, Any]]:
    return [
        evaluation.build_per_seed_result(_route_rows(arm, seed))
        for seed in SEEDS
        for arm in ("A", "C")
    ]


def test_preregistered_contract_freezes_64_48_a_c_gate_and_non_actions() -> None:
    contract = evaluation.preregistered_evaluation_contract()

    assert evaluation.POSITIVE_TASK_COUNT == 64
    assert evaluation.TEMPTING_NEGATIVE_COUNT == 48
    assert evaluation.CANONICAL_SKILL_COUNT == 16
    assert evaluation.SEMANTIC_FAMILY_COUNT == 64
    assert evaluation.ARMS == ("A", "C")
    assert evaluation.SEEDS == (7170, 7171, 7172)
    assert evaluation.BOOTSTRAP_RESAMPLES == 10_000
    assert evaluation.BOOTSTRAP_SEED == 7170
    assert contract["schema_version"] == "router-v2-blind-v2-evaluation-contract-v1"
    assert contract["arms"] == ["A", "C"]
    assert contract["seeds"] == [7170, 7171, 7172]
    assert contract["counts"] == {
        "positive_tasks": 64,
        "tempting_negative_labels": 48,
        "canonical_skills": 16,
        "semantic_families": 64,
        "tasks_per_gold_skill": 4,
        "negative_labeled_per_gold_skill": 3,
        "positive_only_per_gold_skill": 1,
    }
    assert contract["statistics"] == {
        "mcnemar": "exact_two_sided",
        "bootstrap_method": "paired_task_resampling",
        "bootstrap_resamples": 10_000,
        "bootstrap_seed": 7170,
        "confidence_level": "0.95000000",
        "repeated_seed_samples_independent": False,
    }
    assert contract["gate"] == {
        "comparison_scope": "A_VS_C_ONLY",
        "recall_at_5_mean_delta_min": "0.00000000",
        "recall_at_5_each_seed_delta_min": "0.00000000",
        "mrr_mean_delta_min": "-0.01000000",
        "mrr_each_seed_delta_min": "-0.01000000",
        "ndcg_at_5_mean_delta_min": "-0.01000000",
        "ndcg_at_5_each_seed_delta_min": "-0.01000000",
        "negative_hit_rate_at_5_mean_delta_max": "-0.05000000",
        "negative_hit_rate_at_5_each_seed_delta_max": "0.00000000",
        "latency_p95_mean_ratio_max": "1.20000000",
        "latency_p95_each_seed_ratio_max": "1.20000000",
    }
    assert contract["single_attempt"] == {
        "attempt_number": 1,
        "maximum_attempts": 1,
        "retry_allowed": False,
        "replacement_namespace_allowed": False,
    }
    assert contract["prohibited_actions"] == {
        "training": False,
        "optimization": False,
        "mining": False,
        "relabeling": False,
        "tuning": False,
        "threshold_changes": False,
        "gate_changes": False,
        "seed_changes": False,
        "best_seed_selection": False,
        "hard_task_deletion": False,
        "failure_artifact_deletion": False,
        "later_attempt_creation": False,
        "replacement_blind_set_creation": False,
        "default_router_modification": False,
        "merge": False,
        "tag": False,
        "release": False,
        "deploy": False,
        "archive": False,
    }

    preregistration = {
        "schema_version": "router-v2-blind-v2-preregistration-v1",
        "blind_v2_data_seen": False,
        "default_router_unchanged": True,
        "single_attempt": contract["single_attempt"],
        "non_actions": contract["prohibited_actions"],
    }
    assert evaluation.validate_preregistration_truth(preregistration) is preregistration

    with pytest.raises(ValueError, match="blind_v2_data_seen"):
        evaluation.validate_preregistration_truth(
            {**preregistration, "blind_v2_data_seen": True}
        )

    tampered_non_actions = {
        **preregistration,
        "non_actions": {**preregistration["non_actions"], "training": True},
    }
    with pytest.raises(ValueError, match="non_actions"):
        evaluation.validate_preregistration_truth(tampered_non_actions)


def test_per_seed_metrics_are_raw_count_first_with_fixed_denominators() -> None:
    baseline = evaluation.build_per_seed_result(_route_rows("A", 7170))
    candidate = evaluation.build_per_seed_result(_route_rows("C", 7170))

    assert baseline["arm"] == "A"
    assert baseline["positive_task_count"] == 64
    assert baseline["tempting_negative_count"] == 48
    assert baseline["recall_at_1"] == {
        "count": 48,
        "denominator": 64,
        "rate": "0.75000000",
    }
    assert baseline["recall_at_5"] == {
        "count": 64,
        "denominator": 64,
        "rate": "1.00000000",
    }
    assert baseline["mrr"] == "0.87500000"
    assert baseline["ndcg_at_5"] == "0.90773244"
    assert baseline["negative_hit_at_1"] == {
        "count": 0,
        "denominator": 48,
        "rate": "0.00000000",
    }
    assert baseline["negative_hit_at_5"] == {
        "count": 48,
        "denominator": 48,
        "rate": "1.00000000",
    }
    assert baseline["first_negative_rank_mean"] == "2.00000000"
    assert baseline["latency_p50_ms"] == "10.00000000"
    assert baseline["latency_p95_ms"] == "10.00000000"
    assert baseline["tasks"][0] == {
        "task_id": f"{PREFIX}_TASK_00",
        "gold_skill_id": f"{PREFIX}_SKILL_00",
        "tempting_negative_skill_id": f"{PREFIX}_NEGATIVE_00",
        "semantic_family_id": f"{PREFIX}_FAMILY_00",
        "gold_rank": 2,
        "tempting_negative_rank": 2,
        "latency_ms": "10.00000000",
    }
    assert candidate["recall_at_1"]["count"] == 64
    assert candidate["negative_hit_at_5"]["count"] == 0

    variable_latency = _route_rows("A", 7170)
    for index, row in enumerate(variable_latency, start=1):
        row["latency_ns"] = index * 1_000_000
    percentiles = evaluation.build_per_seed_result(variable_latency)
    assert percentiles["latency_p50_ms"] == "32.00000000"
    assert percentiles["latency_p95_ms"] == "61.00000000"

    with pytest.raises(ValueError, match="Arm A or C"):
        evaluation.build_per_seed_result(_route_rows("B", 7170))
    with pytest.raises(ValueError, match="64 tasks"):
        evaluation.build_per_seed_result(_route_rows("A", 7170)[:-1])

    wrong_negative_count = _route_rows("A", 7170)
    wrong_negative_count[0] = {
        **wrong_negative_count[0],
        "tempting_negative_skill_id": None,
        "tempting_negative_rank": None,
    }
    with pytest.raises(ValueError, match="48 tempting negatives"):
        evaluation.build_per_seed_result(wrong_negative_count)

    invalid = _route_rows("A", 7170)
    invalid[-1] = {
        **invalid[-1],
        "semantic_family_id": invalid[0]["semantic_family_id"],
    }
    with pytest.raises(ValueError, match="64 semantic families"):
        evaluation.build_per_seed_result(invalid)

    wrong_skills = _route_rows("A", 7170)
    wrong_skills[-1] = {
        **wrong_skills[-1],
        "gold_skill_id": f"{PREFIX}_SKILL_EXTRA",
    }
    with pytest.raises(ValueError, match="16 gold skills"):
        evaluation.build_per_seed_result(wrong_skills)


def test_aggregate_gate_and_conclusion_use_only_complete_a_c_seed_grid() -> None:
    per_seed = _per_seed()

    aggregate = evaluation.build_aggregate_results(per_seed)
    gate = evaluation.apply_preregistered_gate(per_seed)

    assert [row["arm"] for row in aggregate["arms"]] == ["A", "C"]
    assert aggregate["arms"][0]["metrics"]["mrr"] == {
        "mean": "0.87500000",
        "sample_std": "0.00000000",
    }
    assert aggregate["deltas"]["comparison"] == "C_MINUS_A"
    assert aggregate["deltas"]["per_seed"][0]["metrics"] == {
        "recall_at_1_rate": "0.25000000",
        "recall_at_5_rate": "0.00000000",
        "mrr": "0.12500000",
        "ndcg_at_5": "0.09226756",
        "negative_hit_rate_at_1": "0.00000000",
        "negative_hit_rate_at_5": "-1.00000000",
        "first_negative_rank_mean": "4.00000000",
        "latency_p50_ms": "1.00000000",
        "latency_p95_ms": "1.00000000",
    }
    assert aggregate["deltas"]["metrics"]["mrr"] == {
        "mean": "0.12500000",
        "sample_std": "0.00000000",
    }
    assert aggregate["pooled_repeated_counts"] == {
        "warning": "REPEATED_SEED_EVALUATIONS_ARE_NOT_INDEPENDENT",
        "independent_samples": False,
        "arms": [
            {
                "arm": "A",
                "positive_observations": 192,
                "tempting_negative_observations": 144,
                "recall_at_1_count": 144,
                "recall_at_5_count": 192,
                "negative_hit_at_1_count": 0,
                "negative_hit_at_5_count": 144,
            },
            {
                "arm": "C",
                "positive_observations": 192,
                "tempting_negative_observations": 144,
                "recall_at_1_count": 192,
                "recall_at_5_count": 192,
                "negative_hit_at_1_count": 0,
                "negative_hit_at_5_count": 0,
            },
        ],
    }
    assert gate["gate_passed"] is True
    assert gate["research_conclusion"] == "BLIND_V2_GENERALIZATION_SUPPORTED"
    assert gate["router_decision"] == "KEEP_BASELINE"
    assert gate["default_router_unchanged"] is True
    assert gate["production_ready"] is False
    assert gate["release_eligible"] is False

    with pytest.raises(ValueError, match="A/C seed grid"):
        evaluation.build_aggregate_results(per_seed[:-1])

    arm_b = {**per_seed[0], "arm": "B"}
    with pytest.raises(ValueError, match="A/C seed grid"):
        evaluation.build_aggregate_results([arm_b, *per_seed[1:]])

    failing_per_seed: list[dict[str, Any]] = []
    for seed in SEEDS:
        for arm in ("A", "C"):
            rows = _route_rows(arm, seed)
            if arm == "C" and seed == 7170:
                rows = [
                    {
                        **row,
                        "gold_rank": 6,
                        "tempting_negative_rank": (
                            7 if row["tempting_negative_rank"] is not None else None
                        ),
                    }
                    for row in rows
                ]
            failing_per_seed.append(evaluation.build_per_seed_result(rows))
    failed_gate = evaluation.apply_preregistered_gate(failing_per_seed)
    assert failed_gate["gate_passed"] is False
    assert failed_gate["research_conclusion"] == "BLIND_V2_NOT_SUPPORTED"
    assert failed_gate["router_decision"] == "KEEP_BASELINE"


def test_paired_statistics_are_exact_deterministic_and_warn_non_independence() -> None:
    routes = _all_routes()

    paired = evaluation.build_paired_results(routes)
    first = evaluation.build_statistics(routes)
    second = evaluation.build_statistics(routes)

    assert first == second
    assert paired["comparison_scope"] == "A_VS_C_ONLY"
    assert paired["seeds"][0]["metrics"]["recall_at_1"] == {
        "wins": 16,
        "losses": 0,
        "ties": 48,
        "task_count": 64,
    }
    assert first["mcnemar"]["recall_at_1"]["per_seed"][0] == {
        "seed": 7170,
        "a_only_success": 0,
        "c_only_success": 16,
        "discordant_pairs": 16,
        "exact_two_sided_p_value": "0.00003052",
    }
    assert (
        first["mcnemar"]["negative_hit_at_5"]["per_seed"][0]["discordant_pairs"] == 48
    )
    assert first["bootstrap"]["resamples"] == 10_000
    assert first["bootstrap"]["seed"] == 7170
    assert first["bootstrap"]["method"] == "paired_task_resampling"
    assert first["bootstrap"]["mrr_delta"]["observed"] == "0.12500000"
    assert first["bootstrap"]["ndcg_at_5_delta"]["observed"] == "0.09226756"
    assert (
        first["bootstrap"]["negative_hit_rate_at_5_delta"]["observed"] == "-1.00000000"
    )
    for metric in (
        "mrr_delta",
        "ndcg_at_5_delta",
        "negative_hit_rate_at_5_delta",
    ):
        interval = first["bootstrap"][metric]
        assert set(interval) == {
            "observed",
            "lower_95",
            "upper_95",
            "task_units",
        }
        assert float(interval["lower_95"]) <= float(interval["observed"])
        assert float(interval["observed"]) <= float(interval["upper_95"])
    assert first["repeated_seed_samples_independent"] is False


def test_failure_slices_and_lineage_are_pure_complete_builders() -> None:
    routes = _all_routes()
    changed_routes = [dict(row) for row in routes]
    failed = next(
        row
        for row in changed_routes
        if row["arm"] == "C"
        and row["seed"] == 7170
        and row["task_id"] == f"{PREFIX}_TASK_00"
    )
    failed.update(gold_rank=6, tempting_negative_rank=1, latency_ns=13_000_000)
    slices = evaluation.build_failure_slices(changed_routes)
    lineage = evaluation.build_lineage_manifest(
        commit_a="a" * 40,
        commit_b="b" * 40,
        evaluator_commit="c" * 40,
        attempt_token_sha256="d" * 64,
        frozen_bindings={"skill_index_sha256": "e" * 64},
        artifacts={
            f"{PREFIX}_aggregate.json": b"{}\n",
            f"{PREFIX}_per-seed.json": b"[]\n",
        },
    )

    dimensions = {row["dimension"] for row in slices["slices"]}
    assert dimensions == {
        "ALL",
        "gold_skill_id",
        "tempting_negative_skill_id",
        "semantic_family_id",
    }
    assert slices["comparison_scope"] == "A_VS_C_ONLY"
    task_failure = next(
        row
        for row in slices["task_flags"]
        if row["seed"] == 7170 and row["task_id"] == f"{PREFIX}_TASK_00"
    )
    assert task_failure["flags"] == [
        "TOP1_MISS",
        "GOLD_MISS_AT_5",
        "NEGATIVE_HIT_AT_1",
        "NEGATIVE_HIT_AT_5",
        "NEGATIVE_MOVED_EARLIER",
        "GOLD_RANK_REGRESSION",
        "TASK_LATENCY_RATIO_GT_1_20",
    ]
    assert lineage["commit_a"] == "a" * 40
    assert lineage["commit_b"] == "b" * 40
    assert [row["path"] for row in lineage["artifacts"]] == sorted(
        row["path"] for row in lineage["artifacts"]
    )
    assert all(len(row["sha256"]) == 64 for row in lineage["artifacts"])
    assert len(lineage["lineage_sha256"]) == 64
    assert lineage["lineage_sha256"] == evaluation.canonical_sha256(
        {key: value for key, value in lineage.items() if key != "lineage_sha256"}
    )
    assert evaluation.quantize8("1.005000005") == "1.00500000"
