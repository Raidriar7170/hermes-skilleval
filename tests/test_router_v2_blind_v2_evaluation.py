from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest

from hermes_skilleval import router_v2_blind_v2_evaluation as evaluation


SEEDS = (7170, 7171, 7172)
PREFIX = "TEST_ONLY_DO_NOT_USE"


def _route_rows(arm: str, seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(128):
        gold_index = index // 8
        has_negative = index % 8 < 6
        rows.append(
            {
                "arm": arm,
                "seed": seed,
                "task_id": f"{PREFIX}_TASK_{index:03d}",
                "gold_skill_id": f"test-skill-{gold_index:02d}",
                "tempting_negative_skill_id": (
                    f"test-skill-{(gold_index + 1) % 16:02d}" if has_negative else None
                ),
                "semantic_family_id": f"{PREFIX}_FAMILY_{index:03d}",
                "gold_rank": 2 if arm == "A" else 1,
                "tempting_negative_rank": (
                    5 if has_negative and arm == "A" else 6 if has_negative else None
                ),
                "latency_ns": 10_000_000,
            }
        )
    return rows


def _all_routes() -> list[dict[str, Any]]:
    return [
        row for seed in SEEDS for arm in ("A", "C") for row in _route_rows(arm, seed)
    ]


def _mixed_routes() -> list[dict[str, Any]]:
    rows = _all_routes()
    for row in rows:
        index = int(str(row["task_id"]).rsplit("_", maxsplit=1)[1])
        if index < 32:
            row["gold_rank"] = 1 if row["arm"] == "A" else 2
        elif index < 80:
            row["gold_rank"] = 2 if row["arm"] == "A" else 1
        else:
            row["gold_rank"] = 1
        if row["tempting_negative_skill_id"] is not None:
            negative_ordinal = (index // 8) * 6 + (index % 8)
            if negative_ordinal < 40:
                row["tempting_negative_rank"] = 6 if row["arm"] == "A" else 5
            else:
                row["tempting_negative_rank"] = 5 if row["arm"] == "A" else 6
        row["latency_ns"] = 10_000_000 if row["arm"] == "A" else 11_000_000
    return rows


def _per_seed() -> list[dict[str, Any]]:
    return [
        evaluation.build_per_seed_result(_route_rows(arm, seed))
        for seed in SEEDS
        for arm in ("A", "C")
    ]


def test_preregistered_contract_freezes_128_96_a_c_gate_and_non_actions() -> None:
    contract = evaluation.preregistered_evaluation_contract()

    assert evaluation.POSITIVE_TASK_COUNT == 128
    assert evaluation.TEMPTING_NEGATIVE_COUNT == 96
    assert evaluation.CANONICAL_SKILL_COUNT == 16
    assert evaluation.SEMANTIC_FAMILY_COUNT == 128
    assert evaluation.TASKS_PER_GOLD_SKILL == 8
    assert evaluation.NEGATIVE_LABELED_PER_GOLD_SKILL == 6
    assert evaluation.POSITIVE_ONLY_PER_GOLD_SKILL == 2
    assert evaluation.ARMS == ("A", "C")
    assert evaluation.SEEDS == (7170, 7171, 7172)
    assert evaluation.BOOTSTRAP_RESAMPLES == 10_000
    assert evaluation.BOOTSTRAP_SEED == 7170
    assert evaluation.PER_SEED_SCHEMA_VERSION == "router-v2-agent-blind-v2-per-seed-v1"
    assert (
        contract["schema_version"] == "router-v2-agent-blind-v2-evaluation-contract-v1"
    )
    assert contract["arms"] == ["A", "C"]
    assert contract["seeds"] == [7170, 7171, 7172]
    assert contract["counts"] == {
        "positive_tasks": 128,
        "tempting_negative_labels": 96,
        "canonical_skills": 16,
        "semantic_families": 128,
        "tasks_per_gold_skill": 8,
        "negative_labeled_per_gold_skill": 6,
        "positive_only_per_gold_skill": 2,
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


def test_terminal_posture_accepts_only_agent_blind_v2_terminal_states() -> None:
    terminal_states = {
        "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
        "AGENT_BLIND_V2_PROTOCOL_INVALID",
        "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
        "AGENT_BLIND_V2_GATES_PASSED",
        "AGENT_BLIND_V2_GATES_NOT_PASSED",
    }

    assert evaluation.TERMINAL_STATES == terminal_states
    for research_conclusion in terminal_states:
        assert evaluation.terminal_posture(research_conclusion) == {
            "research_conclusion": research_conclusion,
            "router_decision": "KEEP_BASELINE",
            "production_ready": False,
            "release_authorized": False,
            "default_router_unchanged": True,
        }

    with pytest.raises(ValueError, match="terminal state mismatch"):
        evaluation.terminal_posture("BLIND_V2_GENERALIZATION_SUPPORTED")


def test_per_seed_metrics_are_raw_count_first_with_fixed_denominators() -> None:
    rows = _route_rows("A", 7170)
    assert len(rows) == 128
    for gold_index in range(16):
        skill_rows = [
            row
            for row in rows
            if row["gold_skill_id"] == f"test-skill-{gold_index:02d}"
        ]
        assert len(skill_rows) == 8
        assert (
            sum(row["tempting_negative_skill_id"] is not None for row in skill_rows)
            == 6
        )
        assert sum(row["tempting_negative_skill_id"] is None for row in skill_rows) == 2
    assert len({row["semantic_family_id"] for row in rows}) == 128

    baseline = evaluation.build_per_seed_result(_route_rows("A", 7170))
    candidate = evaluation.build_per_seed_result(_route_rows("C", 7170))

    assert baseline["schema_version"] == "router-v2-agent-blind-v2-per-seed-v1"
    assert baseline["arm"] == "A"
    assert baseline["positive_task_count"] == 128
    assert baseline["tempting_negative_count"] == 96
    assert baseline["recall_at_1"] == {
        "count": 0,
        "denominator": 128,
        "rate": "0.00000000",
    }
    assert baseline["recall_at_5"] == {
        "count": 128,
        "denominator": 128,
        "rate": "1.00000000",
    }
    assert baseline["mrr"] == "0.50000000"
    assert baseline["ndcg_at_5"] == "0.63092975"
    assert baseline["negative_hit_at_1"] == {
        "count": 0,
        "denominator": 96,
        "rate": "0.00000000",
    }
    assert baseline["negative_hit_at_5"] == {
        "count": 96,
        "denominator": 96,
        "rate": "1.00000000",
    }
    assert baseline["first_negative_rank_mean"] == "5.00000000"
    assert baseline["latency_p50_ms"] == "10.00000000"
    assert baseline["latency_p95_ms"] == "10.00000000"
    assert baseline["tasks"][0] == {
        "task_id": f"{PREFIX}_TASK_000",
        "gold_skill_id": "test-skill-00",
        "tempting_negative_skill_id": "test-skill-01",
        "semantic_family_id": f"{PREFIX}_FAMILY_000",
        "gold_rank": 2,
        "tempting_negative_rank": 5,
        "latency_ms": "10.00000000",
    }
    assert candidate["recall_at_1"]["count"] == 128
    assert candidate["negative_hit_at_5"]["count"] == 0

    variable_latency = _route_rows("A", 7170)
    for index, row in enumerate(variable_latency, start=1):
        row["latency_ns"] = index * 1_000_000
    percentiles = evaluation.build_per_seed_result(variable_latency)
    assert percentiles["latency_p50_ms"] == "64.00000000"
    assert percentiles["latency_p95_ms"] == "122.00000000"

    with pytest.raises(ValueError, match="Arm A or C"):
        evaluation.build_per_seed_result(_route_rows("B", 7170))
    with pytest.raises(ValueError, match="128 tasks"):
        evaluation.build_per_seed_result(_route_rows("A", 7170)[:-1])

    wrong_negative_count = _route_rows("A", 7170)
    wrong_negative_count[0] = {
        **wrong_negative_count[0],
        "tempting_negative_skill_id": None,
        "tempting_negative_rank": None,
    }
    with pytest.raises(ValueError, match="96 tempting negatives"):
        evaluation.build_per_seed_result(wrong_negative_count)

    wrong_per_skill_distribution = _route_rows("A", 7170)
    wrong_per_skill_distribution[0] = {
        **wrong_per_skill_distribution[0],
        "tempting_negative_skill_id": None,
        "tempting_negative_rank": None,
    }
    wrong_per_skill_distribution[14] = {
        **wrong_per_skill_distribution[14],
        "tempting_negative_skill_id": "test-skill-02",
        "tempting_negative_rank": 5,
    }
    with pytest.raises(ValueError, match="six negative-labeled and two positive-only"):
        evaluation.build_per_seed_result(wrong_per_skill_distribution)

    invalid = _route_rows("A", 7170)
    invalid[-1] = {
        **invalid[-1],
        "semantic_family_id": invalid[0]["semantic_family_id"],
    }
    with pytest.raises(ValueError, match="128 semantic families"):
        evaluation.build_per_seed_result(invalid)

    wrong_skills = _route_rows("A", 7170)
    wrong_skills[-1] = {
        **wrong_skills[-1],
        "gold_skill_id": "test-skill-extra",
    }
    with pytest.raises(ValueError, match="16 gold skills"):
        evaluation.build_per_seed_result(wrong_skills)


@pytest.mark.parametrize(
    ("violation", "message"),
    (
        ("non_string_gold", "gold skill"),
        ("unknown_negative", "tempting negative skill"),
        ("self_negative", "tempting negative skill"),
    ),
)
def test_per_seed_builder_rejects_invalid_skill_identifiers(
    violation: str,
    message: str,
) -> None:
    rows = _route_rows("A", 7170)
    if violation == "non_string_gold":
        for row in rows[:8]:
            row["gold_skill_id"] = 17
    elif violation == "unknown_negative":
        rows[0]["tempting_negative_skill_id"] = "test-skill-17"
    else:
        rows[0]["tempting_negative_skill_id"] = rows[0]["gold_skill_id"]

    with pytest.raises(ValueError, match=message):
        evaluation.build_per_seed_result(rows)


@pytest.mark.parametrize("invalid_seed", (7170.0, True))
def test_per_seed_builder_rejects_non_integer_row_seed(invalid_seed: Any) -> None:
    rows = _route_rows("A", 7170)
    rows[1]["seed"] = invalid_seed

    with pytest.raises(ValueError, match="route group identity mismatch"):
        evaluation.build_per_seed_result(rows)


@pytest.mark.parametrize(
    "builder",
    (evaluation.build_aggregate_results, evaluation.apply_preregistered_gate),
)
def test_aggregate_and_gate_reject_stale_64_48_per_seed_results(
    builder: Any,
) -> None:
    per_seed = _per_seed()
    legacy = deepcopy(per_seed[0])
    legacy.update(
        schema_version="router-v2-blind-v2-per-seed-v1",
        positive_task_count=64,
        tempting_negative_count=48,
        tasks=legacy["tasks"][:64],
        recall_at_1={"count": 0, "denominator": 64, "rate": "0.00000000"},
        recall_at_5={"count": 64, "denominator": 64, "rate": "1.00000000"},
        negative_hit_at_1={
            "count": 0,
            "denominator": 48,
            "rate": "0.00000000",
        },
        negative_hit_at_5={
            "count": 48,
            "denominator": 48,
            "rate": "1.00000000",
        },
    )
    per_seed[0] = legacy

    with pytest.raises(ValueError, match="per-seed schema mismatch"):
        builder(per_seed)


def test_per_seed_grid_rejects_current_contract_drift_fail_closed() -> None:
    wrong_positive_count = deepcopy(_per_seed())
    wrong_positive_count[0]["positive_task_count"] = 64
    with pytest.raises(ValueError, match="positive task count mismatch"):
        evaluation.build_aggregate_results(wrong_positive_count)

    wrong_negative_count = deepcopy(_per_seed())
    wrong_negative_count[0]["tempting_negative_count"] = 48
    with pytest.raises(ValueError, match="tempting negative count mismatch"):
        evaluation.build_aggregate_results(wrong_negative_count)

    wrong_denominator = deepcopy(_per_seed())
    wrong_denominator[0]["recall_at_5"]["denominator"] = 64
    with pytest.raises(ValueError, match="recall_at_5 denominator mismatch"):
        evaluation.build_aggregate_results(wrong_denominator)

    wrong_task_length = deepcopy(_per_seed())
    wrong_task_length[0]["tasks"] = wrong_task_length[0]["tasks"][:-1]
    with pytest.raises(ValueError, match="per-seed tasks must contain 128 rows"):
        evaluation.build_aggregate_results(wrong_task_length)

    wrong_task_negative_count = deepcopy(_per_seed())
    wrong_task_negative_count[0]["tasks"][0].update(
        tempting_negative_skill_id=None,
        tempting_negative_rank=None,
    )
    with pytest.raises(ValueError, match="per-seed negative task count mismatch"):
        evaluation.build_aggregate_results(wrong_task_negative_count)

    inconsistent_identity = deepcopy(_per_seed())
    inconsistent_identity[0]["tasks"][0]["semantic_family_id"] = (
        f"{PREFIX}_FAMILY_INCONSISTENT"
    )
    with pytest.raises(ValueError, match="A/C seed task identity mismatch"):
        evaluation.build_aggregate_results(inconsistent_identity)


@pytest.mark.parametrize(
    "builder",
    (evaluation.build_aggregate_results, evaluation.apply_preregistered_gate),
)
@pytest.mark.parametrize(
    ("field", "invalid_value", "message"),
    (
        ("seed", 7170.0, "A/C seed grid mismatch"),
        ("seed", True, "A/C seed grid mismatch"),
        ("recall_at_5", 128.0, "recall_at_5 denominator mismatch"),
        ("recall_at_5", True, "recall_at_5 denominator mismatch"),
        ("negative_hit_at_5", 96.0, "negative_hit_at_5 denominator mismatch"),
        ("negative_hit_at_5", True, "negative_hit_at_5 denominator mismatch"),
    ),
)
def test_aggregate_and_gate_reject_non_integer_contract_fields(
    builder: Any,
    field: str,
    invalid_value: Any,
    message: str,
) -> None:
    per_seed = deepcopy(_per_seed())
    if field == "seed":
        per_seed[0]["seed"] = invalid_value
    else:
        per_seed[0][field]["denominator"] = invalid_value

    with pytest.raises(ValueError, match=message):
        builder(per_seed)


@pytest.mark.parametrize(
    "builder",
    (evaluation.build_aggregate_results, evaluation.apply_preregistered_gate),
)
@pytest.mark.parametrize(
    ("violation", "message"),
    (
        ("non_string_gold", "gold skill"),
        ("unknown_negative", "tempting negative skill"),
        ("self_negative", "tempting negative skill"),
    ),
)
def test_aggregate_and_gate_reject_invalid_per_seed_skill_identifiers(
    builder: Any,
    violation: str,
    message: str,
) -> None:
    per_seed = deepcopy(_per_seed())
    for result in per_seed:
        if violation == "non_string_gold":
            for task in result["tasks"][:8]:
                task["gold_skill_id"] = 17
        elif violation == "unknown_negative":
            result["tasks"][0]["tempting_negative_skill_id"] = "test-skill-17"
        else:
            result["tasks"][0]["tempting_negative_skill_id"] = result["tasks"][0][
                "gold_skill_id"
            ]

    with pytest.raises(ValueError, match=message):
        builder(per_seed)


@pytest.mark.parametrize(
    ("field", "stale_value"),
    (
        ("mrr", "0.50000001"),
        ("ndcg_at_5", "0.63092976"),
        ("first_negative_rank_mean", "5.00000001"),
        ("latency_p50_ms", "10.00000001"),
        ("latency_p95_ms", "10.00000001"),
    ),
)
def test_per_seed_grid_rejects_stale_metric_summaries(
    field: str,
    stale_value: str,
) -> None:
    per_seed = deepcopy(_per_seed())
    per_seed[0][field] = stale_value

    with pytest.raises(ValueError, match=rf"{field} mismatch"):
        evaluation.build_aggregate_results(per_seed)


@pytest.mark.parametrize(
    "latency_ms",
    ("NaN", "Infinity", "-0.00000001", "1", 1.0),
)
def test_per_seed_grid_rejects_invalid_task_latency(latency_ms: Any) -> None:
    per_seed = deepcopy(_per_seed())
    per_seed[0]["tasks"][0]["latency_ms"] = latency_ms

    with pytest.raises(ValueError, match="per-seed task latency"):
        evaluation.build_aggregate_results(per_seed)


@pytest.mark.parametrize(
    "missing_key",
    ("tempting_negative_skill_id", "tempting_negative_rank"),
)
def test_per_seed_grid_rejects_missing_negative_task_fields(
    missing_key: str,
) -> None:
    per_seed = deepcopy(_per_seed())
    del per_seed[0]["tasks"][6][missing_key]

    with pytest.raises(ValueError, match=rf"per-seed task missing {missing_key}"):
        evaluation.build_aggregate_results(per_seed)


def test_json_round_trip_preserves_zero_and_one_nanosecond_latencies() -> None:
    per_seed: list[dict[str, Any]] = []
    for seed in SEEDS:
        for arm in ("A", "C"):
            rows = _route_rows(arm, seed)
            for index, row in enumerate(rows):
                row["latency_ns"] = index % 2
            per_seed.append(evaluation.build_per_seed_result(rows))

    round_tripped = json.loads(json.dumps(per_seed))
    aggregate = evaluation.build_aggregate_results(round_tripped)

    assert round_tripped[0]["tasks"][0]["latency_ms"] == "0.00000000"
    assert round_tripped[0]["tasks"][1]["latency_ms"] == "0.00000100"
    assert aggregate["schema_version"] == "router-v2-agent-blind-v2-aggregate-v1"


def test_gate_rejects_tampered_metric_bypass() -> None:
    honest: list[dict[str, Any]] = []
    for seed in SEEDS:
        for arm in ("A", "C"):
            rows = _route_rows(arm, seed)
            for row in rows:
                row["gold_rank"] = 1 if arm == "A" else 2
            honest.append(evaluation.build_per_seed_result(rows))

    assert evaluation.apply_preregistered_gate(honest)["gate_passed"] is False

    tampered = deepcopy(honest)
    for result in tampered:
        if result["arm"] != "C":
            continue
        result["mrr"] = "1.00000000"
        result["ndcg_at_5"] = "1.00000000"

    with pytest.raises(ValueError, match="mrr mismatch"):
        evaluation.apply_preregistered_gate(tampered)


def test_gate_rejects_stale_latency_summary() -> None:
    tampered = deepcopy(_per_seed())
    for result in tampered:
        if result["arm"] != "C":
            continue
        for task in result["tasks"]:
            task["latency_ms"] = "99.00000000"

    with pytest.raises(ValueError, match="latency_p50_ms mismatch"):
        evaluation.apply_preregistered_gate(tampered)


def test_aggregate_gate_and_conclusion_use_only_complete_a_c_seed_grid() -> None:
    per_seed = _per_seed()

    aggregate = evaluation.build_aggregate_results(per_seed)
    gate = evaluation.apply_preregistered_gate(per_seed)

    assert aggregate["schema_version"] == "router-v2-agent-blind-v2-aggregate-v1"
    assert gate["schema_version"] == "router-v2-agent-blind-v2-gate-v1"
    assert [row["arm"] for row in aggregate["arms"]] == ["A", "C"]
    assert aggregate["arms"][0]["metrics"]["mrr"] == {
        "mean": "0.50000000",
        "sample_std": "0.00000000",
    }
    assert aggregate["deltas"]["comparison"] == "C_MINUS_A"
    assert aggregate["deltas"]["per_seed"][0]["metrics"] == {
        "recall_at_1_rate": "1.00000000",
        "recall_at_5_rate": "0.00000000",
        "mrr": "0.50000000",
        "ndcg_at_5": "0.36907025",
        "negative_hit_rate_at_1": "0.00000000",
        "negative_hit_rate_at_5": "-1.00000000",
        "first_negative_rank_mean": "1.00000000",
        "latency_p50_ms": "0.00000000",
        "latency_p95_ms": "0.00000000",
    }
    assert aggregate["deltas"]["metrics"]["mrr"] == {
        "mean": "0.50000000",
        "sample_std": "0.00000000",
    }
    assert aggregate["pooled_repeated_counts"] == {
        "warning": "REPEATED_SEED_EVALUATIONS_ARE_NOT_INDEPENDENT",
        "independent_samples": False,
        "arms": [
            {
                "arm": "A",
                "positive_observations": 384,
                "tempting_negative_observations": 288,
                "recall_at_1_count": 0,
                "recall_at_5_count": 384,
                "negative_hit_at_1_count": 0,
                "negative_hit_at_5_count": 288,
            },
            {
                "arm": "C",
                "positive_observations": 384,
                "tempting_negative_observations": 288,
                "recall_at_1_count": 384,
                "recall_at_5_count": 384,
                "negative_hit_at_1_count": 0,
                "negative_hit_at_5_count": 0,
            },
        ],
    }
    assert gate["gate_passed"] is True
    assert gate["research_conclusion"] == "AGENT_BLIND_V2_GATES_PASSED"
    assert gate["router_decision"] == "KEEP_BASELINE"
    assert gate["default_router_unchanged"] is True
    assert gate["production_ready"] is False
    assert gate["release_authorized"] is False
    assert "release_eligible" not in gate
    assert "router_promotion_requires_separate_human_decision" not in gate

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
    assert failed_gate["research_conclusion"] == "AGENT_BLIND_V2_GATES_NOT_PASSED"
    assert {
        key: failed_gate[key]
        for key in (
            "router_decision",
            "production_ready",
            "release_authorized",
            "default_router_unchanged",
        )
    } == {
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "release_authorized": False,
        "default_router_unchanged": True,
    }


@pytest.mark.parametrize(
    "builder",
    (
        evaluation.build_paired_results,
        evaluation.build_statistics,
        evaluation.build_failure_slices,
    ),
)
@pytest.mark.parametrize(
    "drift",
    ("semantic_family_id", "tempting_negative_skill_id", "swapped_gold_skill_id"),
)
def test_route_matrix_rejects_cross_group_task_identity_drift(
    builder: Any,
    drift: str,
) -> None:
    routes = _all_routes()
    changed_group = {
        row["task_id"]: row
        for row in routes
        if row["arm"] == "C" and row["seed"] == 7170
    }
    first = changed_group[f"{PREFIX}_TASK_000"]
    if drift == "semantic_family_id":
        first["semantic_family_id"] = f"{PREFIX}_FAMILY_DRIFT"
    elif drift == "tempting_negative_skill_id":
        first["tempting_negative_skill_id"] = "test-skill-02"
    else:
        other = changed_group[f"{PREFIX}_TASK_016"]
        first["gold_skill_id"], other["gold_skill_id"] = (
            other["gold_skill_id"],
            first["gold_skill_id"],
        )

    with pytest.raises(ValueError, match="route matrix task identity mismatch"):
        builder(routes)


def test_paired_statistics_are_exact_deterministic_and_warn_non_independence() -> None:
    routes = _all_routes()

    paired = evaluation.build_paired_results(routes)
    first = evaluation.build_statistics(routes)
    second = evaluation.build_statistics(routes)

    assert first == second
    assert paired["schema_version"] == "router-v2-agent-blind-v2-paired-v1"
    assert first["schema_version"] == "router-v2-agent-blind-v2-statistics-v1"
    assert paired["comparison_scope"] == "A_VS_C_ONLY"
    assert paired["seeds"][0]["metrics"]["recall_at_1"] == {
        "wins": 128,
        "losses": 0,
        "ties": 0,
        "task_count": 128,
    }
    assert first["mcnemar"]["recall_at_1"]["per_seed"][0] == {
        "seed": 7170,
        "a_only_success": 0,
        "c_only_success": 128,
        "discordant_pairs": 128,
        "exact_two_sided_p_value": "0.00000000",
    }
    assert (
        first["mcnemar"]["negative_hit_at_5"]["per_seed"][0]["discordant_pairs"] == 96
    )
    assert first["bootstrap"]["resamples"] == 10_000
    assert first["bootstrap"]["seed"] == 7170
    assert first["bootstrap"]["method"] == "paired_task_resampling"
    assert first["bootstrap"]["mrr_delta"]["observed"] == "0.50000000"
    assert first["bootstrap"]["ndcg_at_5_delta"]["observed"] == "0.36907025"
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


def test_mixed_outcomes_protect_statistics_bootstrap_and_latency_gate() -> None:
    routes = _mixed_routes()
    paired = evaluation.build_paired_results(routes)
    first = evaluation.build_statistics(routes)
    second = evaluation.build_statistics(routes)
    per_seed = [
        evaluation.build_per_seed_result(
            [row for row in routes if row["arm"] == arm and row["seed"] == seed]
        )
        for seed in SEEDS
        for arm in ("A", "C")
    ]
    gate = evaluation.apply_preregistered_gate(per_seed)

    assert first == second
    assert paired["seeds"][0]["metrics"]["recall_at_1"] == {
        "wins": 48,
        "losses": 32,
        "ties": 48,
        "task_count": 128,
    }
    assert first["mcnemar"]["recall_at_1"]["per_seed"][0] == {
        "seed": 7170,
        "a_only_success": 32,
        "c_only_success": 48,
        "discordant_pairs": 80,
        "exact_two_sided_p_value": "0.09291188",
    }
    assert first["mcnemar"]["negative_hit_at_5"]["per_seed"][0] == {
        "seed": 7170,
        "a_only_success": 40,
        "c_only_success": 56,
        "discordant_pairs": 96,
        "exact_two_sided_p_value": "0.12534570",
    }
    assert first["bootstrap"]["mrr_delta"]["observed"] == "0.06250000"
    assert first["bootstrap"]["ndcg_at_5_delta"]["observed"] == "0.04613378"
    assert (
        first["bootstrap"]["negative_hit_rate_at_5_delta"]["observed"] == "-0.16666667"
    )
    for metric in (
        "mrr_delta",
        "ndcg_at_5_delta",
        "negative_hit_rate_at_5_delta",
    ):
        interval = first["bootstrap"][metric]
        assert float(interval["lower_95"]) < float(interval["upper_95"])
        assert float(interval["lower_95"]) <= float(interval["observed"])
        assert float(interval["observed"]) <= float(interval["upper_95"])
    assert gate["per_seed"][0]["latency_p95_ratio"] == "1.10000000"
    assert gate["mean"]["latency_p95_ratio"] == "1.10000000"
    assert gate["gate_passed"] is True
    assert gate["research_conclusion"] == "AGENT_BLIND_V2_GATES_PASSED"


def test_failure_slices_and_lineage_are_pure_complete_builders() -> None:
    routes = _all_routes()
    changed_routes = [dict(row) for row in routes]
    failed = next(
        row
        for row in changed_routes
        if row["arm"] == "C"
        and row["seed"] == 7170
        and row["task_id"] == f"{PREFIX}_TASK_000"
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

    assert slices["schema_version"] == "router-v2-agent-blind-v2-failure-slices-v1"
    assert lineage["schema_version"] == "router-v2-agent-blind-v2-lineage-v1"
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
        if row["seed"] == 7170 and row["task_id"] == f"{PREFIX}_TASK_000"
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
