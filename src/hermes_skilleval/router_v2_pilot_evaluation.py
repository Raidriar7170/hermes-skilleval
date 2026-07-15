from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any, Iterable, cast

from hermes_skilleval.router_v2_pilot_runtime import TRUTH_FIELDS, canonical_sha256
from hermes_skilleval.router_v2_training_pilot import (
    SKILL_INDEX_SHA256,
    SOURCE_CANDIDATES_SHA256,
    SOURCE_MANIFEST_SHA256,
)


ARMS = ("A", "B", "C")
SEEDS = (7170, 7171, 7172)
FAILURE_FLAGS = (
    "TOP1_MISS",
    "GOLD_MISS_AT_5",
    "NEGATIVE_HIT_AT_1",
    "NEGATIVE_HIT_AT_5",
    "NEGATIVE_MOVED_EARLIER",
    "GOLD_RANK_REGRESSION",
    "TASK_LATENCY_RATIO_GT_1_20",
)
METRIC_FIELDS = (
    "recall_at_1",
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate_at_1",
    "negative_hit_rate_at_5",
    "first_negative_rank_mean",
    "latency_p50_ms",
    "latency_p95_ms",
)
RATE_FIELDS = {
    "recall_at_1",
    "recall_at_5",
    "negative_hit_rate_at_1",
    "negative_hit_rate_at_5",
}
PAIR_METRICS = (
    "recall_at_1",
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "first_negative_rank",
    "negative_hit_rate_at_1",
    "negative_hit_rate_at_5",
    "latency_ms",
)
LOWER_IS_BETTER = {
    "negative_hit_rate_at_1",
    "negative_hit_rate_at_5",
    "latency_ms",
}
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_EIGHT_DECIMAL = re.compile(r"-?\d+\.\d{8}\Z")
_QUANTUM = Decimal("0.00000001")

TASK_BINDING_FIELDS = {
    "task_id",
    "source_record_id",
    "source_record_exact_bytes_sha256",
    "query_sha256",
    "gold_skill_id",
    "category",
    "supported_negative_skill_id",
    "heldout_label_row_sha256",
    "heldout_usage",
}
ROUTE_FIELDS = {
    "schema_version",
    "plan_sha256",
    "arm",
    "seed",
    *TASK_BINDING_FIELDS,
    "skill_index_sha256",
    "ranked_skill_ids",
    "ranked_scores",
    "gold_rank",
    "supported_negative_rank",
    "raw_latency_ns",
    "latency_ms",
    "row_sha256",
}


def contract_sha256(value: Any) -> str:
    return canonical_sha256(value)


def _exact(actual: Any, expected: Any) -> bool:
    return type(actual) is type(expected) and actual == expected


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sha(value: Any) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be finite")
    try:
        result = Decimal(value) if isinstance(value, str) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be finite") from exc
    _require(result.is_finite(), f"{label} must be finite")
    return result


def quantize8(value: Any) -> str:
    return format(
        _decimal(value, "number").quantize(_QUANTUM, rounding=ROUND_HALF_EVEN), "f"
    )


def _serialized(value: Any, label: str) -> Decimal:
    _require(
        type(value) is str and _EIGHT_DECIMAL.fullmatch(value) is not None,
        f"{label} must be an eight-decimal string",
    )
    number = _decimal(value, label)
    _require(quantize8(number) == value, f"{label} must be canonical")
    return number


def nearest_rank(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    _require(
        len(ordered) > 0 and all(math.isfinite(value) for value in ordered),
        "nearest-rank values must be finite and non-empty",
    )
    _require(
        type(percentile) is float and math.isfinite(percentile) and 0 < percentile <= 1,
        "percentile must be in (0, 1]",
    )
    return ordered[max(1, math.ceil(percentile * len(ordered))) - 1]


def sample_std(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values]
    _require(
        len(numbers) >= 2 and all(math.isfinite(value) for value in numbers),
        "sample standard deviation requires finite n >= 2",
    )
    mean = sum(numbers) / len(numbers)
    return math.sqrt(sum((value - mean) ** 2 for value in numbers) / (len(numbers) - 1))


def _seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    unhashed = {key: item for key, item in value.items() if key != field}
    return {**unhashed, field: contract_sha256(unhashed)}


def _validate_training_artifacts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = {
        "arm",
        "seed",
        "config_sha256",
        "run_summary_sha256",
        "model_manifest_sha256",
        "model_file_manifest_sha256",
    }
    _require(
        type(rows) is list and len(rows) == 9,
        "training artifacts must contain nine rows",
    )
    seen: set[tuple[str, int]] = set()
    output = []
    for row in rows:
        _require(
            type(row) is dict and set(row) == fields,
            "training artifact schema mismatch",
        )
        arm, seed = row["arm"], row["seed"]
        _require(type(arm) is str and arm in ARMS, "training artifact arm mismatch")
        _require(type(seed) is int and seed in SEEDS, "training artifact seed mismatch")
        _require(
            all(_is_sha(row[field]) for field in fields - {"arm", "seed"}),
            "training artifact hash mismatch",
        )
        _require((arm, seed) not in seen, "duplicate training artifact")
        seen.add((arm, seed))
        output.append(dict(row))
    _require(
        seen == {(arm, seed) for arm in ARMS for seed in SEEDS},
        "training artifact grid mismatch",
    )
    return sorted(output, key=lambda row: (ARMS.index(row["arm"]), row["seed"]))


def _validate_task_bindings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _require(
        type(rows) is list and len(rows) == 16,
        "expected task bindings must contain 16 rows",
    )
    output = []
    for row in rows:
        _require(
            type(row) is dict and set(row) == TASK_BINDING_FIELDS,
            "task binding schema mismatch",
        )
        for field in ("task_id", "source_record_id", "gold_skill_id", "category"):
            _require(
                type(row[field]) is str and bool(row[field]),
                f"task binding {field} mismatch",
            )
        for field in ("source_record_exact_bytes_sha256", "query_sha256"):
            _require(_is_sha(row[field]), f"task binding {field} mismatch")
        negative = row["supported_negative_skill_id"]
        label_hash = row["heldout_label_row_sha256"]
        usage = row["heldout_usage"]
        if negative is None:
            _require(
                label_hash is None and usage is None,
                "unlabeled task carries held-out binding",
            )
        else:
            _require(
                type(negative) is str
                and len(negative) > 0
                and negative != row["gold_skill_id"],
                "supported negative mismatch",
            )
            _require(
                _is_sha(label_hash) and usage == "HELD_OUT_EVAL_ONLY",
                "held-out task binding mismatch",
            )
        output.append(dict(row))
    output.sort(key=lambda row: row["task_id"])
    _require(len({row["task_id"] for row in output}) == 16, "task ids must be unique")
    _require(
        len({row["source_record_id"] for row in output}) == 16,
        "source record ids must be unique",
    )
    gold_skills = {row["gold_skill_id"] for row in output}
    _require(len(gold_skills) == 16, "gold skill bindings must cover 16 skills")
    _require(
        sum(row["supported_negative_skill_id"] is not None for row in output) == 9,
        "held-out binding count must be 9",
    )
    _require(
        all(
            row["supported_negative_skill_id"] in gold_skills
            for row in output
            if row["supported_negative_skill_id"] is not None
        ),
        "supported negative is outside skill set",
    )
    return output


def preregistered_evaluation_contract() -> dict[str, Any]:
    return {
        "arm_order": list(ARMS),
        "seed_order": list(SEEDS),
        "task_order": "ascending_task_id",
        "expected_task_count": 16,
        "expected_supported_negative_count": 9,
        "warmup_repeats": 1,
        "timed_repeats": 1,
        "ranking": {
            "candidate_count": 16,
            "score_decimals": 8,
            "rounding": "ROUND_HALF_EVEN",
            "tie_break": "skill_id",
        },
        "latency_percentiles": {
            "method": "nearest_rank",
            "percentiles": ["0.50", "0.95"],
        },
        "metric_fields": list(METRIC_FIELDS),
        "metrics": {
            "positive_denominator": 16,
            "supported_negative_denominator": 9,
            "aggregate_mean": "arithmetic",
            "aggregate_std": "sample_n_minus_1",
        },
        "paired_metric_fields": list(PAIR_METRICS),
        "failure_slices": ["ALL", "category", "gold_skill_id", "flag"],
        "failure_flags": list(FAILURE_FLAGS),
        "gate": {
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
        },
        "input_policy": {
            "source_scope": "FROZEN_NON_BLIND_POSITIVE_ONLY",
            "heldout_usage": "HELD_OUT_EVAL_ONLY",
            "calibration_allowed": False,
            "blind_v2_allowed": False,
            "old_blind_allowed": False,
            "phase_16_allowed": False,
            "post_hoc_tuning_allowed": False,
            "best_seed_selection_allowed": False,
            "repeated_attempt_allowed": False,
        },
    }


def build_evaluation_plan_contract(
    *,
    run_pack_manifest_sha256: str,
    heldout_labels_sha256: str,
    training_artifacts: list[dict[str, Any]],
    training_code_git_commit: str,
    evaluation_code_git_commit: str,
    expected_task_bindings: list[dict[str, Any]],
    attempt_token_sha256: str,
    source_candidates_sha256: str = SOURCE_CANDIDATES_SHA256,
    source_manifest_sha256: str = SOURCE_MANIFEST_SHA256,
    skill_index_sha256: str = SKILL_INDEX_SHA256,
) -> dict[str, Any]:
    _require(
        _is_sha(run_pack_manifest_sha256) and _is_sha(heldout_labels_sha256),
        "plan lineage hash mismatch",
    )
    _require(
        type(training_code_git_commit) is str
        and _HEX40.fullmatch(training_code_git_commit) is not None,
        "training commit mismatch",
    )
    _require(
        type(evaluation_code_git_commit) is str
        and _HEX40.fullmatch(evaluation_code_git_commit) is not None,
        "evaluation commit mismatch",
    )
    _require(_is_sha(attempt_token_sha256), "attempt token hash mismatch")
    _require(
        _is_sha(source_candidates_sha256)
        and _is_sha(source_manifest_sha256)
        and _is_sha(skill_index_sha256),
        "frozen input hash mismatch",
    )
    artifacts = _validate_training_artifacts(training_artifacts)
    bindings = _validate_task_bindings(expected_task_bindings)
    contract = preregistered_evaluation_contract()
    plan = {
        "schema_version": "router-v2-final-evaluation-plan-v1",
        "attempt": 1,
        "arms": contract["arm_order"],
        "seeds": contract["seed_order"],
        "expected_task_count": contract["expected_task_count"],
        "expected_supported_negative_count": contract[
            "expected_supported_negative_count"
        ],
        "expected_task_bindings": bindings,
        "expected_task_bindings_sha256": contract_sha256(bindings),
        "warmup_repeats": contract["warmup_repeats"],
        "timed_repeats": contract["timed_repeats"],
        "ranking": contract["ranking"],
        "latency_percentiles": contract["latency_percentiles"],
        "metrics": contract["metrics"],
        "failure_slices": contract["failure_slices"],
        "failure_flags": contract["failure_flags"],
        "gate": contract["gate"],
        "input_policy": contract["input_policy"],
        "attempt_ledger": {
            "schema_version": "router-v2-evaluation-attempt-ledger-v1",
            "attempt_number": 1,
            "maximum_attempts": 1,
            "attempt_token_field": "evaluation_attempt_token",
            "attempt_token_sha256": attempt_token_sha256,
            "started_marker_required_before_input_parse": True,
            "terminal_marker_required": True,
        },
        "lineage": {
            "run_pack_manifest_sha256": run_pack_manifest_sha256,
            "heldout_labels_sha256": heldout_labels_sha256,
            "source_candidates_sha256": source_candidates_sha256,
            "source_manifest_sha256": source_manifest_sha256,
            "skill_index_sha256": skill_index_sha256,
            "training_code_git_commit": training_code_git_commit,
            "evaluation_code_git_commit": evaluation_code_git_commit,
            "training_artifacts": artifacts,
        },
        **TRUTH_FIELDS,
    }
    return _seal(plan, "plan_sha256")


def validate_evaluation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    try:
        _require(type(plan) is dict, "plan must be an object")
        expected = build_evaluation_plan_contract(
            run_pack_manifest_sha256=plan["lineage"]["run_pack_manifest_sha256"],
            heldout_labels_sha256=plan["lineage"]["heldout_labels_sha256"],
            training_artifacts=plan["lineage"]["training_artifacts"],
            training_code_git_commit=plan["lineage"]["training_code_git_commit"],
            evaluation_code_git_commit=plan["lineage"]["evaluation_code_git_commit"],
            expected_task_bindings=plan["expected_task_bindings"],
            attempt_token_sha256=plan["attempt_ledger"]["attempt_token_sha256"],
            source_candidates_sha256=plan["lineage"]["source_candidates_sha256"],
            source_manifest_sha256=plan["lineage"]["source_manifest_sha256"],
            skill_index_sha256=plan["lineage"]["skill_index_sha256"],
        )
        _require(_exact(plan, expected), "plan differs from frozen contract")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("evaluation plan differs from frozen contract") from exc
    return plan


def _binding(plan: dict[str, Any], task_id: str) -> dict[str, Any]:
    matches = [
        row for row in plan["expected_task_bindings"] if row["task_id"] == task_id
    ]
    _require(len(matches) == 1, "route task is not in frozen bindings")
    return matches[0]


def build_route_row(
    *,
    plan: dict[str, Any],
    arm: str,
    seed: int,
    task_id: str,
    ranked_skill_ids: list[str],
    ranked_scores: list[str],
    latency_ms: Any,
    raw_latency_ns: int,
) -> dict[str, Any]:
    validate_evaluation_plan(plan)
    _require(type(arm) is str and arm in ARMS, "route arm mismatch")
    _require(type(seed) is int and seed in SEEDS, "route seed mismatch")
    _require(type(task_id) is str, "route task id mismatch")
    binding = _binding(plan, task_id)
    _require(
        type(ranked_skill_ids) is list
        and len(ranked_skill_ids) == 16
        and len(set(ranked_skill_ids)) == 16,
        "route ranked skills mismatch",
    )
    expected_skills = {row["gold_skill_id"] for row in plan["expected_task_bindings"]}
    _require(
        set(ranked_skill_ids) == expected_skills, "route ranked skill set mismatch"
    )
    _require(
        type(ranked_scores) is list and len(ranked_scores) == 16,
        "route ranked scores mismatch",
    )
    scores = [_serialized(value, "route score") for value in ranked_scores]
    _require(
        sorted(range(16), key=lambda index: (-scores[index], ranked_skill_ids[index]))
        == list(range(16)),
        "route ranking order mismatch",
    )
    latency = _decimal(latency_ms, "route latency")
    _require(latency >= 0, "route latency must be non-negative")
    _require(
        type(raw_latency_ns) is int and raw_latency_ns >= 0,
        "route raw latency must be a non-negative integer",
    )
    _require(
        quantize8(Decimal(raw_latency_ns) / Decimal(1_000_000)) == quantize8(latency),
        "route raw latency does not match milliseconds",
    )
    gold_rank = ranked_skill_ids.index(binding["gold_skill_id"]) + 1
    negative = binding["supported_negative_skill_id"]
    row = {
        "schema_version": "router-v2-final-route-row-v1",
        "plan_sha256": plan["plan_sha256"],
        "arm": arm,
        "seed": seed,
        **binding,
        "skill_index_sha256": plan["lineage"]["skill_index_sha256"],
        "ranked_skill_ids": list(ranked_skill_ids),
        "ranked_scores": list(ranked_scores),
        "gold_rank": gold_rank,
        "supported_negative_rank": ranked_skill_ids.index(negative) + 1
        if negative is not None
        else None,
        "raw_latency_ns": raw_latency_ns,
        "latency_ms": quantize8(latency),
    }
    return _seal(row, "row_sha256")


def validate_route_row(row: dict[str, Any], *, plan: dict[str, Any]) -> dict[str, Any]:
    try:
        _require(
            type(row) is dict and set(row) == ROUTE_FIELDS, "route schema mismatch"
        )
        expected = build_route_row(
            plan=plan,
            arm=row["arm"],
            seed=row["seed"],
            task_id=row["task_id"],
            ranked_skill_ids=row["ranked_skill_ids"],
            ranked_scores=row["ranked_scores"],
            latency_ms=row["latency_ms"],
            raw_latency_ns=row["raw_latency_ns"],
        )
        _require(_exact(row, expected), "route row differs from derived contract")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("route row differs from frozen task contract") from exc
    return row


def _validate_route_group(
    rows: list[dict[str, Any]], *, plan: dict[str, Any], arm: str, seed: int
) -> list[dict[str, Any]]:
    _require(type(arm) is str and arm in ARMS, "route group arm mismatch")
    _require(type(seed) is int and seed in SEEDS, "route group seed mismatch")
    _require(
        type(rows) is list and len(rows) == 16, "route group task count must be 16"
    )
    for row in rows:
        validate_route_row(row, plan=plan)
    ordered = sorted(rows, key=lambda row: row["task_id"])
    _require(
        all(_exact(row["arm"], arm) and _exact(row["seed"], seed) for row in ordered),
        "route group identity mismatch",
    )
    _require(
        [row["task_id"] for row in ordered]
        == [row["task_id"] for row in plan["expected_task_bindings"]],
        "route group task alignment mismatch",
    )
    return ordered


def _validate_route_matrix(
    rows: list[dict[str, Any]], *, plan: dict[str, Any]
) -> dict[tuple[str, int, str], dict[str, Any]]:
    _require(type(rows) is list and len(rows) == 144, "route matrix count must be 144")
    grid: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in rows:
        validate_route_row(row, plan=plan)
        key = (row["arm"], row["seed"], row["task_id"])
        _require(key not in grid, "route matrix contains duplicate")
        grid[key] = row
    expected = {
        (arm, seed, binding["task_id"])
        for arm in ARMS
        for seed in SEEDS
        for binding in plan["expected_task_bindings"]
    }
    _require(set(grid) == expected, "route matrix grid mismatch")
    return grid


def compute_seed_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    _require(type(rows) is list and len(rows) == 16, "metric task count must be 16")
    _require(
        len({row.get("task_id") for row in rows}) == 16,
        "metric task ids must be unique",
    )
    gold_ranks = []
    negative_ranks = []
    latencies = []
    for row in rows:
        _require(
            type(row) is dict and set(row) == ROUTE_FIELDS,
            "metric route schema mismatch",
        )
        _require(
            row["row_sha256"]
            == contract_sha256(
                {key: value for key, value in row.items() if key != "row_sha256"}
            ),
            "metric route hash mismatch",
        )
        gold_rank = row["gold_rank"]
        _require(
            type(gold_rank) is int and 1 <= gold_rank <= 16,
            "gold rank must be in [1,16]",
        )
        _require(
            type(row["ranked_skill_ids"]) is list
            and row["gold_skill_id"] in row["ranked_skill_ids"]
            and gold_rank == row["ranked_skill_ids"].index(row["gold_skill_id"]) + 1,
            "gold rank differs from ranking",
        )
        gold_ranks.append(gold_rank)
        if row["supported_negative_skill_id"] is not None:
            rank = row["supported_negative_rank"]
            _require(
                type(rank) is int and 1 <= rank <= 16, "negative rank must be in [1,16]"
            )
            _require(
                row["supported_negative_skill_id"] in row["ranked_skill_ids"]
                and rank
                == row["ranked_skill_ids"].index(row["supported_negative_skill_id"])
                + 1,
                "negative rank differs from ranking",
            )
            negative_ranks.append(rank)
        latencies.append(float(_serialized(row["latency_ms"], "latency")))
    _require(len(negative_ranks) == 9, "supported negative count must be 9")
    metrics = {
        "task_count": 16,
        "supported_negative_count": 9,
        "recall_at_1": quantize8(sum(rank <= 1 for rank in gold_ranks) / 16),
        "recall_at_5": quantize8(sum(rank <= 5 for rank in gold_ranks) / 16),
        "mrr": quantize8(sum(1 / rank for rank in gold_ranks) / 16),
        "ndcg_at_5": quantize8(
            sum(1 / math.log2(rank + 1) if rank <= 5 else 0 for rank in gold_ranks) / 16
        ),
        "negative_hit_rate_at_1": quantize8(
            sum(rank <= 1 for rank in negative_ranks) / 9
        ),
        "negative_hit_rate_at_5": quantize8(
            sum(rank <= 5 for rank in negative_ranks) / 9
        ),
        "first_negative_rank_mean": quantize8(sum(negative_ranks) / 9),
        "latency_p50_ms": quantize8(nearest_rank(latencies, 0.50)),
        "latency_p95_ms": quantize8(nearest_rank(latencies, 0.95)),
    }
    _validate_metrics(metrics)
    return metrics


def _validate_metrics(metrics: dict[str, Any]) -> None:
    _require(
        type(metrics.get("task_count")) is int and metrics["task_count"] == 16,
        "metric task count mismatch",
    )
    _require(
        type(metrics.get("supported_negative_count")) is int
        and metrics["supported_negative_count"] == 9,
        "metric negative count mismatch",
    )
    for field in METRIC_FIELDS:
        value = _serialized(metrics.get(field), field)
        if field in RATE_FIELDS:
            _require(0 <= value <= 1, f"{field} must be in [0,1]")
        elif field.startswith("latency_"):
            _require(value >= 0, f"{field} must be non-negative")
        elif field == "first_negative_rank_mean":
            _require(1 <= value <= 16, "first-negative rank must be in [1,16]")


def build_per_seed_result(
    *, plan: dict[str, Any], arm: str, seed: int, route_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    validate_evaluation_plan(plan)
    _require(type(arm) is str and arm in ARMS, "per-seed arm mismatch")
    _require(type(seed) is int and seed in SEEDS, "per-seed seed mismatch")
    ordered = _validate_route_group(route_rows, plan=plan, arm=arm, seed=seed)
    result = {
        "schema_version": "router-v2-final-per-seed-v1",
        "plan_sha256": plan["plan_sha256"],
        "arm": arm,
        "seed": seed,
        "route_rows_sha256": contract_sha256([row["row_sha256"] for row in ordered]),
        **compute_seed_metrics(ordered),
        **TRUTH_FIELDS,
    }
    return _seal(result, "result_sha256")


def validate_per_seed_result(
    result: dict[str, Any], *, plan: dict[str, Any], route_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        _require(type(result) is dict, "per-seed result must be an object")
        expected = build_per_seed_result(
            plan=plan,
            arm=result["arm"],
            seed=result["seed"],
            route_rows=route_rows,
        )
        _require(
            _exact(result, expected), "per-seed result differs from derived metrics"
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("per-seed result differs from frozen contract") from exc
    return result


def _validated_per_seed_matrix(
    *,
    plan: dict[str, Any],
    per_seed_results: list[dict[str, Any]],
    route_rows: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    routes = _validate_route_matrix(route_rows, plan=plan)
    _require(
        type(per_seed_results) is list and len(per_seed_results) == 9,
        "per-seed result count must be 9",
    )
    grid = {}
    for result in per_seed_results:
        key = (result.get("arm"), result.get("seed"))
        _require(key not in grid, "duplicate per-seed result")
        arm, seed = key
        _require(
            type(arm) is str and arm in ARMS and type(seed) is int and seed in SEEDS,
            "per-seed identity mismatch",
        )
        typed_arm = cast(str, arm)
        typed_seed = cast(int, seed)
        group = [
            routes[(typed_arm, typed_seed, binding["task_id"])]
            for binding in plan["expected_task_bindings"]
        ]
        validate_per_seed_result(result, plan=plan, route_rows=group)
        grid[cast(tuple[str, int], key)] = result
    _require(
        set(grid) == {(arm, seed) for arm in ARMS for seed in SEEDS},
        "per-seed grid mismatch",
    )
    return grid


def build_aggregate_results(
    *,
    plan: dict[str, Any],
    per_seed_results: list[dict[str, Any]],
    route_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    grid = _validated_per_seed_matrix(
        plan=plan, per_seed_results=per_seed_results, route_rows=route_rows
    )
    arms = []
    for arm in ARMS:
        metrics = {}
        for field in METRIC_FIELDS:
            values = [
                float(_serialized(grid[(arm, seed)][field], field)) for seed in SEEDS
            ]
            metrics[field] = {
                "mean": quantize8(sum(values) / 3),
                "sample_std": quantize8(sample_std(values)),
            }
        arms.append({"arm": arm, "seed_count": 3, "metrics": metrics})
    return _seal(
        {
            "schema_version": "router-v2-final-aggregate-v1",
            "plan_sha256": plan["plan_sha256"],
            "arms": arms,
            **TRUTH_FIELDS,
        },
        "document_sha256",
    )


def validate_aggregate_results(
    document: dict[str, Any],
    *,
    plan: dict[str, Any],
    per_seed_results: list[dict[str, Any]],
    route_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        expected = build_aggregate_results(
            plan=plan, per_seed_results=per_seed_results, route_rows=route_rows
        )
        _require(_exact(document, expected), "aggregate differs from derived metrics")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("aggregate document differs from frozen contract") from exc
    return document


def _task_metric(row: dict[str, Any], metric: str) -> Decimal:
    gold_rank = row["gold_rank"]
    negative_rank = row["supported_negative_rank"]
    if metric == "recall_at_1":
        return Decimal(gold_rank <= 1)
    if metric == "recall_at_5":
        return Decimal(gold_rank <= 5)
    if metric == "mrr":
        return Decimal(1) / Decimal(gold_rank)
    if metric == "ndcg_at_5":
        return (
            Decimal(str(1 / math.log2(gold_rank + 1))) if gold_rank <= 5 else Decimal(0)
        )
    if metric == "first_negative_rank":
        _require(type(negative_rank) is int, "first-negative metric requires label")
        return Decimal(negative_rank)
    if metric == "negative_hit_rate_at_1":
        _require(type(negative_rank) is int, "negative metric requires label")
        return Decimal(negative_rank <= 1)
    if metric == "negative_hit_rate_at_5":
        _require(type(negative_rank) is int, "negative metric requires label")
        return Decimal(negative_rank <= 5)
    if metric == "latency_ms":
        return _serialized(row["latency_ms"], "latency")
    raise ValueError("unknown paired metric")


def build_paired_results(
    *, plan: dict[str, Any], route_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    grid = _validate_route_matrix(route_rows, plan=plan)
    seed_rows = []
    for seed in SEEDS:
        metrics = {}
        for metric in PAIR_METRICS:
            eligible = [
                binding["task_id"]
                for binding in plan["expected_task_bindings"]
                if metric
                not in {
                    "first_negative_rank",
                    "negative_hit_rate_at_1",
                    "negative_hit_rate_at_5",
                }
                or binding["supported_negative_skill_id"] is not None
            ]
            wins: list[str] = []
            ties: list[str] = []
            losses: list[str] = []
            for task_id in eligible:
                baseline = _task_metric(grid[("A", seed, task_id)], metric)
                candidate = _task_metric(grid[("C", seed, task_id)], metric)
                comparison = candidate.compare(baseline)
                if metric in LOWER_IS_BETTER:
                    comparison = -comparison
                (wins if comparison > 0 else losses if comparison < 0 else ties).append(
                    task_id
                )
            metrics[metric] = {
                "task_count": len(eligible),
                "wins": len(wins),
                "ties": len(ties),
                "losses": len(losses),
                "win_task_ids": wins,
                "tie_task_ids": ties,
                "loss_task_ids": losses,
            }
        seed_rows.append({"seed": seed, "metrics": metrics})
    return _seal(
        {
            "schema_version": "router-v2-final-paired-v1",
            "plan_sha256": plan["plan_sha256"],
            "comparison_scope": "A_VS_C_ONLY",
            "seeds": seed_rows,
            **TRUTH_FIELDS,
        },
        "document_sha256",
    )


def validate_paired_results(
    document: dict[str, Any], *, plan: dict[str, Any], route_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        expected = build_paired_results(plan=plan, route_rows=route_rows)
        _require(
            _exact(document, expected), "paired document differs from route matrix"
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("paired document differs from frozen contract") from exc
    return document


def _derived_flags(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    flags = []
    gold_rank = candidate["gold_rank"]
    candidate_negative = candidate["supported_negative_rank"]
    baseline_negative = baseline["supported_negative_rank"]
    if gold_rank > 1:
        flags.append("TOP1_MISS")
    if gold_rank > 5:
        flags.append("GOLD_MISS_AT_5")
    if candidate_negative is not None and candidate_negative <= 1:
        flags.append("NEGATIVE_HIT_AT_1")
    if candidate_negative is not None and candidate_negative <= 5:
        flags.append("NEGATIVE_HIT_AT_5")
    if (
        candidate_negative is not None
        and baseline_negative is not None
        and candidate_negative < baseline_negative
    ):
        flags.append("NEGATIVE_MOVED_EARLIER")
    if candidate["gold_rank"] > baseline["gold_rank"]:
        flags.append("GOLD_RANK_REGRESSION")
    baseline_latency = _serialized(baseline["latency_ms"], "latency")
    candidate_latency = _serialized(candidate["latency_ms"], "latency")
    if (baseline_latency == 0 and candidate_latency > 0) or (
        baseline_latency > 0 and candidate_latency / baseline_latency > Decimal("1.20")
    ):
        flags.append("TASK_LATENCY_RATIO_GT_1_20")
    return [flag for flag in FAILURE_FLAGS if flag in flags]


def build_failure_slices(
    *, plan: dict[str, Any], route_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    grid = _validate_route_matrix(route_rows, plan=plan)
    task_flags = []
    for seed in SEEDS:
        for binding in plan["expected_task_bindings"]:
            task_id = binding["task_id"]
            task_flags.append(
                {
                    "seed": seed,
                    "task_id": task_id,
                    "category": binding["category"],
                    "gold_skill_id": binding["gold_skill_id"],
                    "flags": _derived_flags(
                        grid[("A", seed, task_id)], grid[("C", seed, task_id)]
                    ),
                }
            )
    flag_slices = []
    for seed in SEEDS:
        for flag in FAILURE_FLAGS:
            task_ids = [
                row["task_id"]
                for row in task_flags
                if row["seed"] == seed and flag in row["flags"]
            ]
            flag_slices.append(
                {
                    "seed": seed,
                    "flag": flag,
                    "task_count": len(task_ids),
                    "task_ids": task_ids,
                }
            )
    slices = []
    categories = sorted(
        {binding["category"] for binding in plan["expected_task_bindings"]}
    )
    skills = sorted(
        {binding["gold_skill_id"] for binding in plan["expected_task_bindings"]}
    )
    for seed in SEEDS:
        seed_rows = [row for row in task_flags if row["seed"] == seed]
        for dimension, values in (
            ("ALL", ["ALL"]),
            ("category", categories),
            ("gold_skill_id", skills),
        ):
            for value in values:
                selected = (
                    seed_rows
                    if dimension == "ALL"
                    else [row for row in seed_rows if row[dimension] == value]
                )
                failed = [row["task_id"] for row in selected if row["flags"]]
                slices.append(
                    {
                        "seed": seed,
                        "dimension": dimension,
                        "value": value,
                        "task_count": len(selected),
                        "failure_count": len(failed),
                        "failed_task_ids": failed,
                    }
                )
    return _seal(
        {
            "schema_version": "router-v2-final-failure-slices-v1",
            "plan_sha256": plan["plan_sha256"],
            "comparison_scope": "A_VS_C_ONLY",
            "task_flags": task_flags,
            "flag_slices": flag_slices,
            "slices": slices,
            **TRUTH_FIELDS,
        },
        "document_sha256",
    )


def validate_failure_slices(
    document: dict[str, Any], *, plan: dict[str, Any], route_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        expected = build_failure_slices(plan=plan, route_rows=route_rows)
        _require(_exact(document, expected), "failure slices differ from route matrix")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("failure-slice document differs from frozen contract") from exc
    return document


def _fail_closed(reason: str) -> dict[str, Any]:
    return {
        "gate_valid": False,
        "gate_failure_reason": reason,
        "comparison_scope": "A_VS_C_ONLY",
        "pilot_evaluation_conclusion": "KEEP_BASELINE",
        **TRUTH_FIELDS,
    }


def apply_serialized_gate(
    *,
    plan: dict[str, Any],
    per_seed_results: list[dict[str, Any]],
    route_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        grid = _validated_per_seed_matrix(
            plan=plan, per_seed_results=per_seed_results, route_rows=route_rows
        )
        paired: list[dict[str, Any]] = []
        for seed in SEEDS:
            baseline, candidate = grid[("A", seed)], grid[("C", seed)]
            baseline_latency = _serialized(baseline["latency_p95_ms"], "latency")
            _require(baseline_latency > 0, "baseline p95 latency must be positive")
            paired.append(
                {
                    "seed": seed,
                    "recall_at_5_delta": _serialized(candidate["recall_at_5"], "recall")
                    - _serialized(baseline["recall_at_5"], "recall"),
                    "mrr_delta": _serialized(candidate["mrr"], "mrr")
                    - _serialized(baseline["mrr"], "mrr"),
                    "ndcg_at_5_delta": _serialized(candidate["ndcg_at_5"], "ndcg")
                    - _serialized(baseline["ndcg_at_5"], "ndcg"),
                    "negative_hit_rate_at_5_delta": _serialized(
                        candidate["negative_hit_rate_at_5"], "nhr"
                    )
                    - _serialized(baseline["negative_hit_rate_at_5"], "nhr"),
                    "latency_p95_ratio": _serialized(
                        candidate["latency_p95_ms"], "latency"
                    )
                    / baseline_latency,
                }
            )
        mean: dict[str, Decimal] = {
            field: sum((cast(Decimal, row[field]) for row in paired), Decimal(0))
            / Decimal(3)
            for field in (
                "recall_at_5_delta",
                "mrr_delta",
                "ndcg_at_5_delta",
                "negative_hit_rate_at_5_delta",
                "latency_p95_ratio",
            )
        }
        gate = plan["gate"]
        passes = (
            mean["recall_at_5_delta"]
            >= _serialized(gate["recall_at_5_mean_delta_min"], "gate")
            and all(
                row["recall_at_5_delta"]
                >= _serialized(gate["recall_at_5_each_seed_delta_min"], "gate")
                for row in paired
            )
            and mean["mrr_delta"] >= _serialized(gate["mrr_mean_delta_min"], "gate")
            and all(
                row["mrr_delta"] >= _serialized(gate["mrr_each_seed_delta_min"], "gate")
                for row in paired
            )
            and mean["ndcg_at_5_delta"]
            >= _serialized(gate["ndcg_at_5_mean_delta_min"], "gate")
            and all(
                row["ndcg_at_5_delta"]
                >= _serialized(gate["ndcg_at_5_each_seed_delta_min"], "gate")
                for row in paired
            )
            and mean["negative_hit_rate_at_5_delta"]
            <= _serialized(gate["negative_hit_rate_at_5_mean_delta_max"], "gate")
            and all(
                row["negative_hit_rate_at_5_delta"]
                <= _serialized(
                    gate["negative_hit_rate_at_5_each_seed_delta_max"], "gate"
                )
                for row in paired
            )
            and mean["latency_p95_ratio"]
            <= _serialized(gate["latency_p95_mean_ratio_max"], "gate")
            and all(
                row["latency_p95_ratio"]
                <= _serialized(gate["latency_p95_each_seed_ratio_max"], "gate")
                for row in paired
            )
        )
        return {
            "gate_valid": True,
            "comparison_scope": "A_VS_C_ONLY",
            "paired_seed_gate_values": [
                {
                    key: value if key == "seed" else quantize8(value)
                    for key, value in row.items()
                }
                for row in paired
            ],
            "mean_gate_values": {key: quantize8(value) for key, value in mean.items()},
            "pilot_evaluation_conclusion": "ROUTER_V2_PILOT_IMPROVED"
            if passes
            else "KEEP_BASELINE",
            **TRUTH_FIELDS,
        }
    except (
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        ZeroDivisionError,
    ) as exc:
        return _fail_closed(str(exc))


def build_evaluation_summary(
    *,
    plan: dict[str, Any],
    route_rows: list[dict[str, Any]],
    per_seed_results: list[dict[str, Any]],
    aggregate_results: dict[str, Any],
    paired_results: dict[str, Any],
    failure_slices: dict[str, Any],
) -> dict[str, Any]:
    validate_aggregate_results(
        aggregate_results,
        plan=plan,
        per_seed_results=per_seed_results,
        route_rows=route_rows,
    )
    validate_paired_results(paired_results, plan=plan, route_rows=route_rows)
    validate_failure_slices(failure_slices, plan=plan, route_rows=route_rows)
    gate = apply_serialized_gate(
        plan=plan, per_seed_results=per_seed_results, route_rows=route_rows
    )
    _require(gate["gate_valid"] is True, "summary cannot bind invalid gate inputs")
    summary = {
        "schema_version": "router-v2-final-evaluation-summary-v1",
        "lineage": {
            "evaluation_plan_sha256": plan["plan_sha256"],
            "per_seed_results_sha256": contract_sha256(
                [
                    result["result_sha256"]
                    for result in sorted(
                        per_seed_results,
                        key=lambda result: (ARMS.index(result["arm"]), result["seed"]),
                    )
                ]
            ),
            "aggregate_results_sha256": aggregate_results["document_sha256"],
            "paired_results_sha256": paired_results["document_sha256"],
            "failure_slices_sha256": failure_slices["document_sha256"],
        },
        **gate,
    }
    return _seal(summary, "summary_sha256")


def validate_evaluation_summary(
    document: dict[str, Any],
    *,
    plan: dict[str, Any],
    route_rows: list[dict[str, Any]],
    per_seed_results: list[dict[str, Any]],
    aggregate_results: dict[str, Any],
    paired_results: dict[str, Any],
    failure_slices: dict[str, Any],
) -> dict[str, Any]:
    try:
        expected = build_evaluation_summary(
            plan=plan,
            route_rows=route_rows,
            per_seed_results=per_seed_results,
            aggregate_results=aggregate_results,
            paired_results=paired_results,
            failure_slices=failure_slices,
        )
        _require(_exact(document, expected), "summary differs from derived documents")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("evaluation summary differs from frozen contract") from exc
    return document
