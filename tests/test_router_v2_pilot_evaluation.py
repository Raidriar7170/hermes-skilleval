from __future__ import annotations

import copy
from typing import Any

import pytest

import hermes_skilleval.router_v2_pilot_evaluation as evaluation


ARMS = ("A", "B", "C")
SEEDS = (7170, 7171, 7172)
FLAGS = (
    "TOP1_MISS",
    "GOLD_MISS_AT_5",
    "NEGATIVE_HIT_AT_1",
    "NEGATIVE_HIT_AT_5",
    "NEGATIVE_MOVED_EARLIER",
    "GOLD_RANK_REGRESSION",
    "TASK_LATENCY_RATIO_GT_1_20",
)


def _sha(char: str) -> str:
    return char * 64


def _bindings() -> list[dict[str, Any]]:
    rows = []
    for index in range(16):
        negative = f"skill-{(index + 1) % 16:02d}" if index < 9 else None
        rows.append(
            {
                "task_id": f"task-{index:02d}",
                "source_record_id": f"source-{index:02d}",
                "source_record_exact_bytes_sha256": f"{index + 1:064x}",
                "query_sha256": f"{index + 101:064x}",
                "gold_skill_id": f"skill-{index:02d}",
                "category": "cat-a" if index < 8 else "cat-b",
                "supported_negative_skill_id": negative,
                "heldout_label_row_sha256": (
                    f"{index + 201:064x}" if negative is not None else None
                ),
                "heldout_usage": (
                    "HELD_OUT_EVAL_ONLY" if negative is not None else None
                ),
            }
        )
    return rows


def _plan() -> dict[str, Any]:
    artifacts = [
        {
            "arm": arm,
            "seed": seed,
            "config_sha256": f"{arm.lower()}{seed}".encode().hex().ljust(64, "0")[:64],
            "run_summary_sha256": f"{seed}{arm}".encode().hex().ljust(64, "1")[:64],
            "model_manifest_sha256": f"{arm}{seed}".encode().hex().ljust(64, "2")[:64],
            "model_file_manifest_sha256": f"m{arm}{seed}".encode()
            .hex()
            .ljust(64, "3")[:64],
        }
        for arm in ARMS
        for seed in SEEDS
    ]
    return evaluation.build_evaluation_plan_contract(
        run_pack_manifest_sha256=_sha("a"),
        heldout_labels_sha256=_sha("b"),
        training_artifacts=artifacts,
        training_code_git_commit="c" * 40,
        evaluation_code_git_commit="d" * 40,
        expected_task_bindings=_bindings(),
        attempt_token_sha256=_sha("e"),
    )


def _ranked(
    binding: dict[str, Any], *, gold_rank: int = 1, negative_rank: int = 6
) -> list[str]:
    gold = binding["gold_skill_id"]
    negative = binding["supported_negative_skill_id"]
    remaining = [f"skill-{index:02d}" for index in range(16)]
    remaining.remove(gold)
    if negative is not None:
        remaining.remove(negative)
    slots: list[str | None] = [None] * 16
    slots[gold_rank - 1] = gold
    if negative is not None:
        assert negative_rank != gold_rank
        slots[negative_rank - 1] = negative
    iterator = iter(remaining)
    return [next(iterator) if item is None else item for item in slots]


def _route_rows(
    *,
    plan: dict[str, Any] | None = None,
    arm: str = "A",
    seed: int = 7170,
    latency_ms: float = 10.0,
    candidate_failure: bool = False,
) -> list[dict[str, Any]]:
    plan = plan or _plan()
    rows = []
    for index, binding in enumerate(plan["expected_task_bindings"]):
        negative_rank = 2 if arm == "A" and index == 0 else 6
        gold_rank = 1
        if candidate_failure and arm == "C" and index == 0:
            gold_rank = 6
            negative_rank = 1
        ranked = _ranked(binding, gold_rank=gold_rank, negative_rank=negative_rank)
        rows.append(
            evaluation.build_route_row(
                plan=plan,
                arm=arm,
                seed=seed,
                task_id=binding["task_id"],
                ranked_skill_ids=ranked,
                ranked_scores=[evaluation.quantize8(16 - rank) for rank in range(16)],
                latency_ms=latency_ms,
                raw_latency_ns=int(latency_ms * 1_000_000),
            )
        )
    return rows


def _matrix(
    plan: dict[str, Any],
    *,
    candidate_failure: bool = False,
    latencies: dict[tuple[str, int], float] | None = None,
) -> list[dict[str, Any]]:
    latencies = latencies or {}
    return [
        row
        for arm in ARMS
        for seed in SEEDS
        for row in _route_rows(
            plan=plan,
            arm=arm,
            seed=seed,
            latency_ms=latencies.get((arm, seed), 10.0),
            candidate_failure=candidate_failure,
        )
    ]


def _per_seed(
    plan: dict[str, Any], routes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        evaluation.build_per_seed_result(
            plan=plan,
            arm=arm,
            seed=seed,
            route_rows=[
                row for row in routes if row["arm"] == arm and row["seed"] == seed
            ],
        )
        for arm in ARMS
        for seed in SEEDS
    ]


def _resign(value: dict[str, Any], field: str) -> None:
    value[field] = evaluation.contract_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def test_plan_freezes_task_set_flags_attempt_ledger_and_forbidden_inputs() -> None:
    plan = _plan()
    assert evaluation.validate_evaluation_plan(plan) == plan
    assert plan["expected_task_bindings_sha256"] == evaluation.contract_sha256(
        plan["expected_task_bindings"]
    )
    assert tuple(plan["failure_flags"]) == FLAGS
    assert plan["attempt_ledger"] == {
        "schema_version": "router-v2-evaluation-attempt-ledger-v1",
        "attempt_number": 1,
        "maximum_attempts": 1,
        "attempt_token_field": "evaluation_attempt_token",
        "attempt_token_sha256": _sha("e"),
        "started_marker_required_before_input_parse": True,
        "terminal_marker_required": True,
    }
    assert plan["input_policy"]["repeated_attempt_allowed"] is False
    assert plan["input_policy"]["blind_v2_allowed"] is False
    assert plan["lineage"]["evaluation_code_git_commit"] == "d" * 40
    assert plan["gate"] == {
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

    for mutation in (
        lambda value: value["attempt_ledger"].update(maximum_attempts=2),
        lambda value: value["input_policy"].update(blind_v2_allowed=True),
        lambda value: value["failure_flags"].append("POST_HOC_FLAG"),
        lambda value: value["expected_task_bindings"][0].update(task_id="forbidden"),
    ):
        tampered = copy.deepcopy(plan)
        mutation(tampered)
        _resign(tampered, "plan_sha256")
        with pytest.raises(ValueError, match="plan"):
            evaluation.validate_evaluation_plan(tampered)


def test_route_validator_recomputes_ranks_hash_and_frozen_binding() -> None:
    plan = _plan()
    row = _route_rows(plan=plan)[0]
    assert evaluation.validate_route_row(row, plan=plan) == row
    assert row["source_record_id"] == "source-00"
    assert row["skill_index_sha256"] == plan["lineage"]["skill_index_sha256"]
    assert row["heldout_usage"] == "HELD_OUT_EVAL_ONLY"
    assert row["raw_latency_ns"] == 10_000_000

    for field, value in (
        ("gold_rank", 9),
        ("supported_negative_rank", 9),
        ("source_record_id", "other-source"),
        ("query_sha256", _sha("f")),
        ("heldout_label_row_sha256", _sha("f")),
        ("seed", 7170.0),
    ):
        tampered = copy.deepcopy(row)
        tampered[field] = value
        _resign(tampered, "row_sha256")
        with pytest.raises(ValueError, match="route"):
            evaluation.validate_route_row(tampered, plan=plan)

    forbidden = copy.deepcopy(row)
    forbidden["task_id"] = "unregistered-task"
    _resign(forbidden, "row_sha256")
    with pytest.raises(ValueError, match="route"):
        evaluation.validate_route_row(forbidden, plan=plan)


def test_metrics_enforce_domains_denominators_percentile_and_sample_std() -> None:
    routes = _route_rows()
    metrics = evaluation.compute_seed_metrics(routes)
    assert metrics["task_count"] == 16
    assert metrics["supported_negative_count"] == 9
    assert metrics["negative_hit_rate_at_5"] == evaluation.quantize8(1 / 9)
    assert metrics["latency_p95_ms"] == "10.00000000"
    assert evaluation.nearest_rank(list(range(1, 21)), 0.95) == 19
    assert evaluation.sample_std([1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert evaluation.quantize8("1.005000005") == "1.00500000"
    with pytest.raises(ValueError):
        evaluation.quantize8(float("inf"))

    forged = copy.deepcopy(routes)
    forged[1]["gold_rank"] = 1 if forged[1]["gold_rank"] != 1 else 2
    _resign(forged[1], "row_sha256")
    with pytest.raises(ValueError, match="gold rank differs"):
        evaluation.compute_seed_metrics(forged)


def test_per_seed_validator_rederives_metrics_and_rejects_resigned_tamper() -> None:
    plan = _plan()
    routes = _route_rows(plan=plan)
    result = evaluation.build_per_seed_result(
        plan=plan, arm="A", seed=7170, route_rows=routes
    )
    assert (
        evaluation.validate_per_seed_result(result, plan=plan, route_rows=routes)
        == result
    )
    altered_recall_at_5 = (
        "0.00000000" if result["recall_at_5"] != "0.00000000" else "1.00000000"
    )
    for field, value in (("recall_at_5", altered_recall_at_5), ("seed", 7170.0)):
        tampered = copy.deepcopy(result)
        tampered[field] = value
        _resign(tampered, "result_sha256")
        with pytest.raises(ValueError, match="per-seed"):
            evaluation.validate_per_seed_result(tampered, plan=plan, route_rows=routes)


def test_aggregate_paired_failure_and_summary_validate_content_not_hash_shape() -> None:
    plan = _plan()
    routes = _matrix(plan, candidate_failure=True)
    per_seed = _per_seed(plan, routes)
    aggregate = evaluation.build_aggregate_results(
        plan=plan, per_seed_results=per_seed, route_rows=routes
    )
    paired = evaluation.build_paired_results(plan=plan, route_rows=routes)
    failures = evaluation.build_failure_slices(plan=plan, route_rows=routes)
    summary = evaluation.build_evaluation_summary(
        plan=plan,
        route_rows=routes,
        per_seed_results=per_seed,
        aggregate_results=aggregate,
        paired_results=paired,
        failure_slices=failures,
    )
    assert (
        evaluation.validate_aggregate_results(
            aggregate, plan=plan, per_seed_results=per_seed, route_rows=routes
        )
        == aggregate
    )
    assert (
        evaluation.validate_paired_results(paired, plan=plan, route_rows=routes)
        == paired
    )
    assert (
        evaluation.validate_failure_slices(failures, plan=plan, route_rows=routes)
        == failures
    )
    assert (
        evaluation.validate_evaluation_summary(
            summary,
            plan=plan,
            route_rows=routes,
            per_seed_results=per_seed,
            aggregate_results=aggregate,
            paired_results=paired,
            failure_slices=failures,
        )
        == summary
    )
    metric = next(row for row in paired["seeds"] if row["seed"] == 7170)["metrics"]
    assert metric["recall_at_5"]["loss_task_ids"] == ["task-00"]
    assert any(
        row["flag"] == "GOLD_RANK_REGRESSION" and row["task_count"] == 1
        for row in failures["flag_slices"]
    )
    assert any(
        row["flag"] == "TASK_LATENCY_RATIO_GT_1_20" and row["task_count"] == 0
        for row in failures["flag_slices"]
    )

    fake = copy.deepcopy(aggregate)
    fake["arms"][0]["metrics"]["recall_at_5"]["mean"] = "0.00000000"
    _resign(fake, "document_sha256")
    with pytest.raises(ValueError, match="aggregate"):
        evaluation.validate_aggregate_results(
            fake, plan=plan, per_seed_results=per_seed, route_rows=routes
        )


def test_gate_uses_only_validated_per_seed_and_b_is_decision_irrelevant() -> None:
    plan = _plan()
    routes = _matrix(plan)
    per_seed = _per_seed(plan, routes)
    improved = evaluation.apply_serialized_gate(
        plan=plan, per_seed_results=per_seed, route_rows=routes
    )
    assert improved["gate_valid"] is True
    assert improved["pilot_evaluation_conclusion"] == "ROUTER_V2_PILOT_IMPROVED"
    assert improved["router_decision"] == "KEEP_BASELINE"

    b_rows = [row for row in routes if row["arm"] == "B"]
    for row in b_rows:
        row["latency_ms"] = "999.00000000"
        row["raw_latency_ns"] = 999_000_000
        _resign(row, "row_sha256")
    b_changed = _per_seed(plan, routes)
    assert (
        evaluation.apply_serialized_gate(
            plan=plan, per_seed_results=b_changed, route_rows=routes
        )
        == improved
    )

    unbound = copy.deepcopy(per_seed)
    unbound[0]["plan_sha256"] = _sha("f")
    _resign(unbound[0], "result_sha256")
    failed = evaluation.apply_serialized_gate(
        plan=plan, per_seed_results=unbound, route_rows=routes
    )
    assert failed["gate_valid"] is False
    assert failed["pilot_evaluation_conclusion"] == "KEEP_BASELINE"


def test_latency_mean_is_arithmetic_mean_of_three_paired_ratios() -> None:
    plan = _plan()
    latencies = {
        ("A", 7170): 1.0,
        ("C", 7170): 2.0,
        ("A", 7171): 100.0,
        ("C", 7171): 100.0,
        ("A", 7172): 100.0,
        ("C", 7172): 100.0,
    }
    routes = _matrix(plan, latencies=latencies)
    result = evaluation.apply_serialized_gate(
        plan=plan, per_seed_results=_per_seed(plan, routes), route_rows=routes
    )
    assert result["mean_gate_values"]["latency_p95_ratio"] == evaluation.quantize8(
        (2.0 + 1.0 + 1.0) / 3
    )
    assert result["pilot_evaluation_conclusion"] == "KEEP_BASELINE"
