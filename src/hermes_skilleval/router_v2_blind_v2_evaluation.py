from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter
from decimal import Decimal, DecimalException
from typing import Any, Callable, Iterable, cast

from hermes_skilleval.router_v2_pilot_evaluation import (
    contract_sha256 as canonical_sha256,
)
from hermes_skilleval.router_v2_pilot_evaluation import (
    nearest_rank,
    quantize8,
    sample_std,
)


POSITIVE_TASK_COUNT = 128
TEMPTING_NEGATIVE_COUNT = 96
CANONICAL_SKILL_COUNT = 16
SEMANTIC_FAMILY_COUNT = 128
TASKS_PER_GOLD_SKILL = 8
NEGATIVE_LABELED_PER_GOLD_SKILL = 6
POSITIVE_ONLY_PER_GOLD_SKILL = 2
PER_SEED_SCHEMA_VERSION = "router-v2-agent-blind-v2-per-seed-v1"
ARMS = ("A", "C")
SEEDS = (7170, 7171, 7172)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 7170

TERMINAL_STATES = {
    "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
    "AGENT_BLIND_V2_PROTOCOL_INVALID",
    "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
    "AGENT_BLIND_V2_GATES_PASSED",
    "AGENT_BLIND_V2_GATES_NOT_PASSED",
}

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_EIGHT_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{8}\Z")
_I_JSON_SAFE_INTEGER_MAX = 2**53 - 1
_MAX_FROZEN_BINDING_DEPTH = 100
_FROZEN_BINDINGS_ERROR = "frozen bindings must be canonical JSON"
_RATE_NAMES = (
    "recall_at_1",
    "recall_at_5",
    "negative_hit_at_1",
    "negative_hit_at_5",
)
_DELTA_FIELDS = (
    "recall_at_1_rate",
    "recall_at_5_rate",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate_at_1",
    "negative_hit_rate_at_5",
    "first_negative_rank_mean",
    "latency_p50_ms",
    "latency_p95_ms",
)
_FAILURE_FLAGS = (
    "TOP1_MISS",
    "GOLD_MISS_AT_5",
    "NEGATIVE_HIT_AT_1",
    "NEGATIVE_HIT_AT_5",
    "NEGATIVE_MOVED_EARLIER",
    "GOLD_RANK_REGRESSION",
    "TASK_LATENCY_RATIO_GT_1_20",
)
_PROHIBITED_ACTIONS = {
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
_GATE = {
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def terminal_posture(research_conclusion: str) -> dict[str, Any]:
    if type(research_conclusion) is not str:
        raise ValueError("terminal state must be a string")
    _require(research_conclusion in TERMINAL_STATES, "terminal state mismatch")
    return {
        "research_conclusion": research_conclusion,
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "release_authorized": False,
        "default_router_unchanged": True,
    }


def _number(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - Decimal owns exact error types
        raise ValueError(f"{label} must be numeric") from exc
    _require(result.is_finite(), f"{label} must be finite")
    return result


def _validate_frozen_binding_value(
    value: Any,
    *,
    depth: int,
    active_container_ids: set[int],
) -> None:
    if value is None or type(value) is bool or type(value) is str:
        return
    if type(value) is int:
        if not -_I_JSON_SAFE_INTEGER_MAX <= value <= _I_JSON_SAFE_INTEGER_MAX:
            raise ValueError(
                f"{_FROZEN_BINDINGS_ERROR}: integer exceeds I-JSON safe integer range"
            )
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{_FROZEN_BINDINGS_ERROR}: float must be finite")
        return
    if depth > _MAX_FROZEN_BINDING_DEPTH:
        raise ValueError(f"{_FROZEN_BINDINGS_ERROR}: maximum nesting depth exceeded")
    children: Iterable[Any]
    if type(value) is dict:
        mapping = cast(dict[Any, Any], value)
        if not all(type(key) is str for key in mapping):
            raise ValueError(f"{_FROZEN_BINDINGS_ERROR}: keys must be strings")
        children = mapping.values()
    elif type(value) is list:
        children = cast(list[Any], value)
    else:
        raise ValueError(f"{_FROZEN_BINDINGS_ERROR}: unsupported value")
    container_id = id(value)
    if container_id in active_container_ids:
        raise ValueError(f"{_FROZEN_BINDINGS_ERROR}: cycle detected")
    active_container_ids.add(container_id)
    try:
        for child in children:
            _validate_frozen_binding_value(
                child,
                depth=depth + 1,
                active_container_ids=active_container_ids,
            )
    finally:
        active_container_ids.remove(container_id)


def preregistered_evaluation_contract() -> dict[str, Any]:
    return {
        "schema_version": "router-v2-agent-blind-v2-evaluation-contract-v1",
        "arms": list(ARMS),
        "seeds": list(SEEDS),
        "counts": {
            "positive_tasks": POSITIVE_TASK_COUNT,
            "tempting_negative_labels": TEMPTING_NEGATIVE_COUNT,
            "canonical_skills": CANONICAL_SKILL_COUNT,
            "semantic_families": SEMANTIC_FAMILY_COUNT,
            "tasks_per_gold_skill": TASKS_PER_GOLD_SKILL,
            "negative_labeled_per_gold_skill": NEGATIVE_LABELED_PER_GOLD_SKILL,
            "positive_only_per_gold_skill": POSITIVE_ONLY_PER_GOLD_SKILL,
        },
        "task_order": "ascending_task_id",
        "warmup_repeats": 1,
        "timed_repeats": 1,
        "ranking": {
            "candidate_count": 16,
            "rounding": "ROUND_HALF_EVEN",
            "score_decimals": 8,
            "tie_break": "skill_id",
        },
        "latency": {
            "device": "cpu",
            "timer": "time.perf_counter_ns",
            "percentile_method": "nearest_rank",
            "percentiles": ["0.50", "0.95"],
        },
        "statistics": {
            "mcnemar": "exact_two_sided",
            "bootstrap_method": "paired_task_resampling",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "confidence_level": "0.95000000",
            "repeated_seed_samples_independent": False,
        },
        "gate": dict(_GATE),
        "single_attempt": {
            "attempt_number": 1,
            "maximum_attempts": 1,
            "retry_allowed": False,
            "replacement_namespace_allowed": False,
        },
        "prohibited_actions": dict(_PROHIBITED_ACTIONS),
    }


def validate_preregistration_truth(value: dict[str, Any]) -> dict[str, Any]:
    _require(type(value) is dict, "preregistration must be an object")
    _require(
        value.get("schema_version") == "router-v2-blind-v2-preregistration-v1",
        "preregistration schema mismatch",
    )
    _require(
        value.get("blind_v2_data_seen") is False, "blind_v2_data_seen must be false"
    )
    _require(
        value.get("default_router_unchanged") is True,
        "default_router_unchanged must be true",
    )
    contract = preregistered_evaluation_contract()
    _require(
        value.get("single_attempt") == contract["single_attempt"],
        "single_attempt mismatch",
    )
    _require(value.get("non_actions") == _PROHIBITED_ACTIONS, "non_actions mismatch")
    return value


def _validate_route_group(
    rows: list[dict[str, Any]],
) -> tuple[str, int, list[dict[str, Any]]]:
    _require(
        type(rows) is list and len(rows) == POSITIVE_TASK_COUNT,
        f"route group must contain {POSITIVE_TASK_COUNT} tasks",
    )
    _require(all(type(row) is dict for row in rows), "route rows must be objects")
    for field in ("tempting_negative_skill_id", "tempting_negative_rank"):
        if not all(field in row for row in rows):
            raise ValueError(f"route row missing {field}")
    arm = rows[0].get("arm")
    seed = rows[0].get("seed")
    _require(arm in ARMS, "route arm must be Arm A or C")
    _require(type(seed) is int and seed in SEEDS, "route seed mismatch")
    _require(
        all(
            row.get("arm") == arm
            and type(row.get("seed")) is int
            and row.get("seed") == seed
            for row in rows
        ),
        "route group identity mismatch",
    )
    ordered = sorted(rows, key=lambda row: str(row.get("task_id")))
    task_ids = [row.get("task_id") for row in ordered]
    _require(
        all(type(task_id) is str and task_id for task_id in task_ids)
        and len(set(task_ids)) == POSITIVE_TASK_COUNT,
        f"{POSITIVE_TASK_COUNT} task ids must be unique",
    )
    families = [row.get("semantic_family_id") for row in ordered]
    _require(
        all(type(family) is str and family for family in families)
        and len(set(families)) == SEMANTIC_FAMILY_COUNT,
        f"route group must contain {SEMANTIC_FAMILY_COUNT} semantic families",
    )
    gold_ids = [row.get("gold_skill_id") for row in ordered]
    _require(
        all(type(gold_id) is str and gold_id for gold_id in gold_ids),
        "route group gold skill ids must be non-empty strings",
    )
    gold_counts = Counter(gold_ids)
    _require(
        len(gold_counts) == CANONICAL_SKILL_COUNT
        and set(gold_counts.values()) == {TASKS_PER_GOLD_SKILL},
        "route group must contain 16 gold skills with eight tasks each",
    )
    canonical_skill_ids = set(gold_counts)
    negative_rows = [
        row for row in ordered if row.get("tempting_negative_skill_id") is not None
    ]
    _require(
        len(negative_rows) == TEMPTING_NEGATIVE_COUNT,
        f"route group must contain {TEMPTING_NEGATIVE_COUNT} tempting negatives",
    )
    negative_counts = Counter(row.get("gold_skill_id") for row in negative_rows)
    positive_only_counts = Counter(
        row.get("gold_skill_id")
        for row in ordered
        if row.get("tempting_negative_skill_id") is None
    )
    _require(
        set(negative_counts) == set(gold_counts)
        and set(negative_counts.values()) == {NEGATIVE_LABELED_PER_GOLD_SKILL}
        and set(positive_only_counts) == set(gold_counts)
        and set(positive_only_counts.values()) == {POSITIVE_ONLY_PER_GOLD_SKILL},
        "each gold skill must contain six negative-labeled and two positive-only tasks",
    )
    for row in ordered:
        gold_id = row["gold_skill_id"]
        gold_rank = row.get("gold_rank")
        negative_id = row.get("tempting_negative_skill_id")
        negative_rank = row.get("tempting_negative_rank")
        latency_ns = row.get("latency_ns")
        _require(type(gold_rank) is int and 1 <= gold_rank <= 16, "gold rank mismatch")
        if negative_id is None:
            _require(negative_rank is None, "positive-only task has a negative rank")
        else:
            _require(
                type(negative_id) is str
                and bool(negative_id)
                and negative_id in canonical_skill_ids
                and negative_id != gold_id,
                "tempting negative skill mismatch",
            )
            _require(
                type(negative_rank) is int and 1 <= negative_rank <= 16,
                "tempting negative rank mismatch",
            )
        _require(type(latency_ns) is int and latency_ns >= 0, "latency_ns mismatch")
    if type(seed) is not int:
        raise ValueError("route seed mismatch")
    return str(arm), seed, ordered


def _rate(count: int, denominator: int) -> dict[str, Any]:
    return {
        "count": count,
        "denominator": denominator,
        "rate": quantize8(Decimal(count) / Decimal(denominator)),
    }


def build_per_seed_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    arm, seed, ordered = _validate_route_group(rows)
    gold_ranks = [int(row["gold_rank"]) for row in ordered]
    negative_ranks = [
        int(row["tempting_negative_rank"])
        for row in ordered
        if row["tempting_negative_skill_id"] is not None
    ]
    try:
        latencies = [int(row["latency_ns"]) / 1_000_000 for row in ordered]
        tasks = [
            {
                "task_id": row["task_id"],
                "gold_skill_id": row["gold_skill_id"],
                "tempting_negative_skill_id": row["tempting_negative_skill_id"],
                "semantic_family_id": row["semantic_family_id"],
                "gold_rank": row["gold_rank"],
                "tempting_negative_rank": row["tempting_negative_rank"],
                "latency_ms": quantize8(int(row["latency_ns"]) / 1_000_000),
            }
            for row in ordered
        ]
        latency_p50_ms = quantize8(nearest_rank(latencies, 0.50))
        latency_p95_ms = quantize8(nearest_rank(latencies, 0.95))
    except (OverflowError, DecimalException) as exc:
        raise ValueError("route latency cannot be represented") from exc
    return {
        "schema_version": PER_SEED_SCHEMA_VERSION,
        "arm": arm,
        "seed": seed,
        "positive_task_count": POSITIVE_TASK_COUNT,
        "tempting_negative_count": TEMPTING_NEGATIVE_COUNT,
        "recall_at_1": _rate(
            sum(rank <= 1 for rank in gold_ranks), POSITIVE_TASK_COUNT
        ),
        "recall_at_5": _rate(
            sum(rank <= 5 for rank in gold_ranks), POSITIVE_TASK_COUNT
        ),
        "mrr": quantize8(sum(1 / rank for rank in gold_ranks) / POSITIVE_TASK_COUNT),
        "ndcg_at_5": quantize8(
            sum(1 / math.log2(rank + 1) if rank <= 5 else 0 for rank in gold_ranks)
            / POSITIVE_TASK_COUNT
        ),
        "negative_hit_at_1": _rate(
            sum(rank <= 1 for rank in negative_ranks), TEMPTING_NEGATIVE_COUNT
        ),
        "negative_hit_at_5": _rate(
            sum(rank <= 5 for rank in negative_ranks), TEMPTING_NEGATIVE_COUNT
        ),
        "first_negative_rank_mean": quantize8(
            sum(negative_ranks) / TEMPTING_NEGATIVE_COUNT
        ),
        "latency_p50_ms": latency_p50_ms,
        "latency_p95_ms": latency_p95_ms,
        "tasks": tasks,
    }


def _validate_rate_contract(
    result: dict[str, Any], name: str, denominator: int, expected_count: int
) -> None:
    rate_value = result.get(name)
    if type(rate_value) is not dict:
        raise ValueError(f"{name} contract mismatch")
    rate = cast(dict[str, Any], rate_value)
    count_value = rate.get("count")
    if type(count_value) is not int or count_value != expected_count:
        raise ValueError(f"{name} count mismatch")
    count = cast(int, count_value)
    _require(
        type(rate.get("denominator")) is int and rate.get("denominator") == denominator,
        f"{name} denominator mismatch",
    )
    _require(
        rate.get("rate") == _rate(count, denominator)["rate"],
        f"{name} rate mismatch",
    )


def _validate_per_seed_result_contract(
    result: dict[str, Any],
) -> tuple[tuple[Any, ...], ...]:
    _require(type(result) is dict, "per-seed result must be an object")
    _require(
        result.get("schema_version") == PER_SEED_SCHEMA_VERSION,
        "per-seed schema mismatch",
    )
    _require(
        type(result.get("positive_task_count")) is int
        and result["positive_task_count"] == POSITIVE_TASK_COUNT,
        "per-seed positive task count mismatch",
    )
    _require(
        type(result.get("tempting_negative_count")) is int
        and result["tempting_negative_count"] == TEMPTING_NEGATIVE_COUNT,
        "per-seed tempting negative count mismatch",
    )
    tasks_value = result.get("tasks")
    if type(tasks_value) is not list:
        raise ValueError(f"per-seed tasks must contain {POSITIVE_TASK_COUNT} rows")
    raw_tasks = cast(list[Any], tasks_value)
    if len(raw_tasks) != POSITIVE_TASK_COUNT:
        raise ValueError(f"per-seed tasks must contain {POSITIVE_TASK_COUNT} rows")
    if not all(type(task) is dict for task in raw_tasks):
        raise ValueError("per-seed tasks must be objects")
    tasks = cast(list[dict[str, Any]], raw_tasks)
    for field in ("tempting_negative_skill_id", "tempting_negative_rank"):
        if not all(field in task for task in tasks):
            raise ValueError(f"per-seed task missing {field}")
    task_id_values = [task.get("task_id") for task in tasks]
    if not all(type(task_id) is str and task_id for task_id in task_id_values):
        raise ValueError("per-seed task ids mismatch")
    task_ids = cast(list[str], task_id_values)
    if task_ids != sorted(task_ids) or len(set(task_ids)) != POSITIVE_TASK_COUNT:
        raise ValueError("per-seed task ids mismatch")
    families = [task.get("semantic_family_id") for task in tasks]
    _require(
        all(type(family) is str and family for family in families)
        and len(set(families)) == SEMANTIC_FAMILY_COUNT,
        "per-seed semantic families mismatch",
    )
    gold_ids = [task.get("gold_skill_id") for task in tasks]
    _require(
        all(type(gold_id) is str and gold_id for gold_id in gold_ids),
        "per-seed gold skill ids must be non-empty strings",
    )
    gold_counts = Counter(gold_ids)
    _require(
        len(gold_counts) == CANONICAL_SKILL_COUNT
        and set(gold_counts.values()) == {TASKS_PER_GOLD_SKILL},
        "per-seed gold skill distribution mismatch",
    )
    canonical_skill_ids = set(gold_counts)
    negative_tasks = [
        task for task in tasks if task.get("tempting_negative_skill_id") is not None
    ]
    _require(
        len(negative_tasks) == TEMPTING_NEGATIVE_COUNT,
        "per-seed negative task count mismatch",
    )
    negative_counts = Counter(task.get("gold_skill_id") for task in negative_tasks)
    positive_only_counts = Counter(
        task.get("gold_skill_id")
        for task in tasks
        if task.get("tempting_negative_skill_id") is None
    )
    _require(
        set(negative_counts) == set(gold_counts)
        and set(negative_counts.values()) == {NEGATIVE_LABELED_PER_GOLD_SKILL}
        and set(positive_only_counts) == set(gold_counts)
        and set(positive_only_counts.values()) == {POSITIVE_ONLY_PER_GOLD_SKILL},
        "per-seed gold skill label distribution mismatch",
    )
    latency_ns_values: list[int] = []
    for task in tasks:
        gold_id = task["gold_skill_id"]
        gold_rank = task.get("gold_rank")
        negative_id = task.get("tempting_negative_skill_id")
        negative_rank = task.get("tempting_negative_rank")
        latency_ms = task.get("latency_ms")
        _require(
            type(gold_rank) is int and 1 <= gold_rank <= CANONICAL_SKILL_COUNT,
            "per-seed gold rank mismatch",
        )
        if negative_id is None:
            _require(
                negative_rank is None,
                "per-seed positive-only task has a negative rank",
            )
        else:
            _require(
                type(negative_id) is str
                and bool(negative_id)
                and negative_id in canonical_skill_ids
                and negative_id != gold_id,
                "per-seed tempting negative skill mismatch",
            )
            _require(
                type(negative_rank) is int
                and 1 <= negative_rank <= CANONICAL_SKILL_COUNT,
                "per-seed tempting negative rank mismatch",
            )
        if type(latency_ms) is not str:
            raise ValueError(
                "per-seed task latency must be a canonical eight-decimal string"
            )
        latency_text = cast(str, latency_ms)
        latency = _number(latency_text, "per-seed task latency")
        _require(latency >= 0, "per-seed task latency must be non-negative")
        try:
            canonical_latency = quantize8(latency)
            latency_ns = latency * Decimal(1_000_000)
            integral_latency_ns = latency_ns.to_integral_value()
            latency_ns_value = int(latency_ns)
        except (OverflowError, DecimalException) as exc:
            raise ValueError("per-seed task latency cannot be represented") from exc
        _require(
            _EIGHT_DECIMAL.fullmatch(latency_text) is not None
            and latency_text == canonical_latency,
            "per-seed task latency must be a canonical eight-decimal string",
        )
        _require(
            latency_ns == integral_latency_ns,
            "per-seed task latency is not representable in nanoseconds",
        )
        latency_ns_values.append(latency_ns_value)
    gold_ranks = [int(task["gold_rank"]) for task in tasks]
    negative_ranks = [int(task["tempting_negative_rank"]) for task in negative_tasks]
    _validate_rate_contract(
        result,
        "recall_at_1",
        POSITIVE_TASK_COUNT,
        sum(rank <= 1 for rank in gold_ranks),
    )
    _validate_rate_contract(
        result,
        "recall_at_5",
        POSITIVE_TASK_COUNT,
        sum(rank <= 5 for rank in gold_ranks),
    )
    _validate_rate_contract(
        result,
        "negative_hit_at_1",
        TEMPTING_NEGATIVE_COUNT,
        sum(rank <= 1 for rank in negative_ranks),
    )
    _validate_rate_contract(
        result,
        "negative_hit_at_5",
        TEMPTING_NEGATIVE_COUNT,
        sum(rank <= 5 for rank in negative_ranks),
    )
    recomputed = build_per_seed_result(
        [
            {
                "arm": ARMS[0],
                "seed": SEEDS[0],
                "task_id": task["task_id"],
                "gold_skill_id": task["gold_skill_id"],
                "tempting_negative_skill_id": task["tempting_negative_skill_id"],
                "semantic_family_id": task["semantic_family_id"],
                "gold_rank": task["gold_rank"],
                "tempting_negative_rank": task["tempting_negative_rank"],
                "latency_ns": latency_ns,
            }
            for task, latency_ns in zip(tasks, latency_ns_values, strict=True)
        ]
    )
    for field in (
        "mrr",
        "ndcg_at_5",
        "first_negative_rank_mean",
        "latency_p50_ms",
        "latency_p95_ms",
    ):
        _require(result.get(field) == recomputed[field], f"{field} mismatch")
    return tuple(
        (
            task["task_id"],
            task["gold_skill_id"],
            task["tempting_negative_skill_id"],
            task["semantic_family_id"],
        )
        for task in tasks
    )


def _per_seed_grid(
    results: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    _require(
        type(results) is list and len(results) == 6,
        "A/C seed grid must contain six rows",
    )
    grid: dict[tuple[str, int], dict[str, Any]] = {}
    identities: dict[tuple[str, int], tuple[tuple[Any, ...], ...]] = {}
    for result in results:
        identity = _validate_per_seed_result_contract(result)
        arm, seed = result.get("arm"), result.get("seed")
        if arm not in ARMS or type(seed) is not int or seed not in SEEDS:
            raise ValueError("A/C seed grid mismatch")
        typed_key = (cast(str, arm), cast(int, seed))
        _require(typed_key not in grid, "A/C seed grid contains duplicate")
        grid[typed_key] = result
        identities[typed_key] = identity
    _require(
        set(grid) == {(arm, seed) for seed in SEEDS for arm in ARMS},
        "A/C seed grid mismatch",
    )
    reference_identity = identities[(ARMS[0], SEEDS[0])]
    _require(
        all(identity == reference_identity for identity in identities.values()),
        "A/C seed task identity mismatch",
    )
    return grid


def _metric_value(result: dict[str, Any], field: str) -> Decimal:
    if field == "recall_at_1_rate":
        return _number(result["recall_at_1"]["rate"], field)
    if field == "recall_at_5_rate":
        return _number(result["recall_at_5"]["rate"], field)
    if field == "negative_hit_rate_at_1":
        return _number(result["negative_hit_at_1"]["rate"], field)
    if field == "negative_hit_rate_at_5":
        return _number(result["negative_hit_at_5"]["rate"], field)
    return _number(result[field], field)


def build_aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    grid = _per_seed_grid(results)
    arms: list[dict[str, Any]] = []
    for arm in ARMS:
        metrics: dict[str, dict[str, str]] = {}
        for field in _DELTA_FIELDS:
            values = [float(_metric_value(grid[(arm, seed)], field)) for seed in SEEDS]
            metrics[field] = {
                "mean": quantize8(sum(values) / 3),
                "sample_std": quantize8(sample_std(values)),
            }
        arms.append({"arm": arm, "seed_count": 3, "metrics": metrics})
    per_seed_deltas: list[dict[str, Any]] = []
    for seed in SEEDS:
        baseline, candidate = grid[("A", seed)], grid[("C", seed)]
        delta_row_metrics: dict[str, str] = {
            field: quantize8(
                _metric_value(candidate, field) - _metric_value(baseline, field)
            )
            for field in _DELTA_FIELDS
        }
        per_seed_deltas.append({"seed": seed, "metrics": delta_row_metrics})
    delta_metrics: dict[str, dict[str, str]] = {}
    for field in _DELTA_FIELDS:
        values = [float(row["metrics"][field]) for row in per_seed_deltas]
        delta_metrics[field] = {
            "mean": quantize8(sum(values) / 3),
            "sample_std": quantize8(sample_std(values)),
        }
    pooled: list[dict[str, Any]] = []
    for arm in ARMS:
        arm_rows = [grid[(arm, seed)] for seed in SEEDS]
        pooled.append(
            {
                "arm": arm,
                "positive_observations": POSITIVE_TASK_COUNT * len(SEEDS),
                "tempting_negative_observations": TEMPTING_NEGATIVE_COUNT * len(SEEDS),
                "recall_at_1_count": sum(
                    row["recall_at_1"]["count"] for row in arm_rows
                ),
                "recall_at_5_count": sum(
                    row["recall_at_5"]["count"] for row in arm_rows
                ),
                "negative_hit_at_1_count": sum(
                    row["negative_hit_at_1"]["count"] for row in arm_rows
                ),
                "negative_hit_at_5_count": sum(
                    row["negative_hit_at_5"]["count"] for row in arm_rows
                ),
            }
        )
    return {
        "schema_version": "router-v2-agent-blind-v2-aggregate-v1",
        "arms": arms,
        "deltas": {
            "comparison": "C_MINUS_A",
            "per_seed": per_seed_deltas,
            "metrics": delta_metrics,
        },
        "pooled_repeated_counts": {
            "warning": "REPEATED_SEED_EVALUATIONS_ARE_NOT_INDEPENDENT",
            "independent_samples": False,
            "arms": pooled,
        },
    }


def apply_preregistered_gate(results: list[dict[str, Any]]) -> dict[str, Any]:
    grid = _per_seed_grid(results)
    rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        baseline, candidate = grid[("A", seed)], grid[("C", seed)]
        baseline_latency = _number(baseline["latency_p95_ms"], "baseline latency")
        _require(baseline_latency > 0, "baseline p95 latency must be positive")
        rows.append(
            {
                "seed": seed,
                "recall_at_5_delta": _metric_value(candidate, "recall_at_5_rate")
                - _metric_value(baseline, "recall_at_5_rate"),
                "mrr_delta": _metric_value(candidate, "mrr")
                - _metric_value(baseline, "mrr"),
                "ndcg_at_5_delta": _metric_value(candidate, "ndcg_at_5")
                - _metric_value(baseline, "ndcg_at_5"),
                "negative_hit_rate_at_5_delta": _metric_value(
                    candidate, "negative_hit_rate_at_5"
                )
                - _metric_value(baseline, "negative_hit_rate_at_5"),
                "latency_p95_ratio": _metric_value(candidate, "latency_p95_ms")
                / baseline_latency,
            }
        )
    means: dict[str, Decimal] = {
        field: sum((cast(Decimal, row[field]) for row in rows), Decimal(0)) / Decimal(3)
        for field in (
            "recall_at_5_delta",
            "mrr_delta",
            "ndcg_at_5_delta",
            "negative_hit_rate_at_5_delta",
            "latency_p95_ratio",
        )
    }
    passed = (
        means["recall_at_5_delta"] >= Decimal(_GATE["recall_at_5_mean_delta_min"])
        and all(
            cast(Decimal, row["recall_at_5_delta"])
            >= Decimal(_GATE["recall_at_5_each_seed_delta_min"])
            for row in rows
        )
        and means["mrr_delta"] >= Decimal(_GATE["mrr_mean_delta_min"])
        and all(
            cast(Decimal, row["mrr_delta"]) >= Decimal(_GATE["mrr_each_seed_delta_min"])
            for row in rows
        )
        and means["ndcg_at_5_delta"] >= Decimal(_GATE["ndcg_at_5_mean_delta_min"])
        and all(
            cast(Decimal, row["ndcg_at_5_delta"])
            >= Decimal(_GATE["ndcg_at_5_each_seed_delta_min"])
            for row in rows
        )
        and means["negative_hit_rate_at_5_delta"]
        <= Decimal(_GATE["negative_hit_rate_at_5_mean_delta_max"])
        and all(
            cast(Decimal, row["negative_hit_rate_at_5_delta"])
            <= Decimal(_GATE["negative_hit_rate_at_5_each_seed_delta_max"])
            for row in rows
        )
        and means["latency_p95_ratio"] <= Decimal(_GATE["latency_p95_mean_ratio_max"])
        and all(
            cast(Decimal, row["latency_p95_ratio"])
            <= Decimal(_GATE["latency_p95_each_seed_ratio_max"])
            for row in rows
        )
    )
    conclusion = (
        "AGENT_BLIND_V2_GATES_PASSED" if passed else "AGENT_BLIND_V2_GATES_NOT_PASSED"
    )
    return {
        "schema_version": "router-v2-agent-blind-v2-gate-v1",
        "comparison_scope": "A_VS_C_ONLY",
        "per_seed": [
            {
                "seed": row["seed"],
                **{
                    key: quantize8(value) for key, value in row.items() if key != "seed"
                },
            }
            for row in rows
        ],
        "mean": {key: quantize8(value) for key, value in means.items()},
        "gate": dict(_GATE),
        "gate_passed": passed,
        **terminal_posture(conclusion),
    }


def _route_matrix(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, int, str], dict[str, Any]]:
    _require(
        type(rows) is list
        and len(rows) == len(ARMS) * len(SEEDS) * POSITIVE_TASK_COUNT,
        "route matrix must contain 768 rows",
    )
    if not all(type(row) is dict for row in rows):
        raise ValueError("route matrix rows must be objects")
    grid: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in rows:
        arm, seed, task_id = row.get("arm"), row.get("seed"), row.get("task_id")
        if arm not in ARMS or type(seed) is not int or type(task_id) is not str:
            raise ValueError("route matrix identity mismatch")
        key = (cast(str, arm), seed, task_id)
        _require(key not in grid, "route matrix contains duplicate")
        grid[key] = row
    for seed in SEEDS:
        for arm in ARMS:
            _validate_route_group(
                [row for (a, s, _), row in grid.items() if a == arm and s == seed]
            )
    task_ids = {key[2] for key in grid}
    _require(len(task_ids) == POSITIVE_TASK_COUNT, "route matrix task set mismatch")
    _require(
        set(grid)
        == {
            (arm, seed, task_id)
            for arm in ARMS
            for seed in SEEDS
            for task_id in task_ids
        },
        "route matrix A/C seed grid mismatch",
    )
    identity_fields = (
        "gold_skill_id",
        "tempting_negative_skill_id",
        "semantic_family_id",
    )
    for task_id in sorted(task_ids):
        reference = tuple(
            grid[(ARMS[0], SEEDS[0], task_id)][field] for field in identity_fields
        )
        _require(
            all(
                tuple(grid[(arm, seed, task_id)][field] for field in identity_fields)
                == reference
                for arm in ARMS
                for seed in SEEDS
            ),
            "route matrix task identity mismatch",
        )
    return grid


def _task_metric(row: dict[str, Any], metric: str) -> Decimal:
    gold_rank = int(row["gold_rank"])
    negative_rank = row["tempting_negative_rank"]
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
    if metric == "negative_hit_at_1":
        _require(type(negative_rank) is int, "negative metric requires a label")
        return Decimal(negative_rank <= 1)
    if metric == "negative_hit_at_5":
        _require(type(negative_rank) is int, "negative metric requires a label")
        return Decimal(negative_rank <= 5)
    if metric == "first_negative_rank":
        _require(type(negative_rank) is int, "negative metric requires a label")
        return Decimal(negative_rank)
    if metric == "latency_ms":
        return Decimal(int(row["latency_ns"])) / Decimal(1_000_000)
    raise ValueError("unknown paired metric")


def build_paired_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grid = _route_matrix(rows)
    task_ids = sorted({key[2] for key in grid})
    metric_names = (
        "recall_at_1",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "negative_hit_at_1",
        "negative_hit_at_5",
        "first_negative_rank",
        "latency_ms",
    )
    lower_is_better = {"negative_hit_at_1", "negative_hit_at_5", "latency_ms"}
    seeds = []
    for seed in SEEDS:
        metrics = {}
        for metric in metric_names:
            eligible = [
                task_id
                for task_id in task_ids
                if metric
                not in {"negative_hit_at_1", "negative_hit_at_5", "first_negative_rank"}
                or grid[("A", seed, task_id)]["tempting_negative_skill_id"] is not None
            ]
            wins = losses = ties = 0
            for task_id in eligible:
                baseline = _task_metric(grid[("A", seed, task_id)], metric)
                candidate = _task_metric(grid[("C", seed, task_id)], metric)
                delta = candidate - baseline
                if metric in lower_is_better:
                    delta = -delta
                if delta > 0:
                    wins += 1
                elif delta < 0:
                    losses += 1
                else:
                    ties += 1
            metrics[metric] = {
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "task_count": len(eligible),
            }
        seeds.append({"seed": seed, "metrics": metrics})
    return {
        "schema_version": "router-v2-agent-blind-v2-paired-v1",
        "comparison_scope": "A_VS_C_ONLY",
        "seeds": seeds,
    }


def _exact_mcnemar(a_only: int, c_only: int) -> str:
    discordant = a_only + c_only
    if discordant == 0:
        return "1.00000000"
    tail = min(a_only, c_only)
    probability = (
        2
        * sum(math.comb(discordant, index) for index in range(tail + 1))
        / (2**discordant)
    )
    return quantize8(min(1.0, probability))


def _mcnemar_metric(
    grid: dict[tuple[str, int, str], dict[str, Any]],
    metric: str,
    success: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    task_ids = sorted({key[2] for key in grid})
    per_seed = []
    for seed in SEEDS:
        eligible = [
            task_id
            for task_id in task_ids
            if metric == "recall_at_1"
            or grid[("A", seed, task_id)]["tempting_negative_skill_id"] is not None
        ]
        a_only = sum(
            success(grid[("A", seed, task_id)])
            and not success(grid[("C", seed, task_id)])
            for task_id in eligible
        )
        c_only = sum(
            success(grid[("C", seed, task_id)])
            and not success(grid[("A", seed, task_id)])
            for task_id in eligible
        )
        per_seed.append(
            {
                "seed": seed,
                "a_only_success": a_only,
                "c_only_success": c_only,
                "discordant_pairs": a_only + c_only,
                "exact_two_sided_p_value": _exact_mcnemar(a_only, c_only),
            }
        )
    return {"method": "exact_two_sided", "per_seed": per_seed}


def _bootstrap_interval(
    values: list[Decimal], rng: random.Random
) -> dict[str, str | int]:
    observed = sum(values, Decimal(0)) / Decimal(len(values))
    resamples = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        resamples.append(sum(sample, Decimal(0)) / Decimal(len(sample)))
    resamples.sort()
    lower = resamples[math.ceil(0.025 * len(resamples)) - 1]
    upper = resamples[math.ceil(0.975 * len(resamples)) - 1]
    return {
        "observed": quantize8(observed),
        "lower_95": quantize8(lower),
        "upper_95": quantize8(upper),
        "task_units": len(values),
    }


def build_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grid = _route_matrix(rows)
    task_ids = sorted({key[2] for key in grid})
    negative_ids = [
        task_id
        for task_id in task_ids
        if grid[("A", SEEDS[0], task_id)]["tempting_negative_skill_id"] is not None
    ]
    mrr_values = []
    ndcg_values = []
    negative_values = []
    for task_id in task_ids:
        mrr_values.append(
            sum(
                _task_metric(grid[("C", seed, task_id)], "mrr")
                - _task_metric(grid[("A", seed, task_id)], "mrr")
                for seed in SEEDS
            )
            / Decimal(3)
        )
        ndcg_values.append(
            sum(
                _task_metric(grid[("C", seed, task_id)], "ndcg_at_5")
                - _task_metric(grid[("A", seed, task_id)], "ndcg_at_5")
                for seed in SEEDS
            )
            / Decimal(3)
        )
    for task_id in negative_ids:
        negative_values.append(
            sum(
                _task_metric(grid[("C", seed, task_id)], "negative_hit_at_5")
                - _task_metric(grid[("A", seed, task_id)], "negative_hit_at_5")
                for seed in SEEDS
            )
            / Decimal(3)
        )
    rng = random.Random(BOOTSTRAP_SEED)
    return {
        "schema_version": "router-v2-agent-blind-v2-statistics-v1",
        "mcnemar": {
            "recall_at_1": _mcnemar_metric(
                grid, "recall_at_1", lambda row: int(row["gold_rank"]) <= 1
            ),
            "negative_hit_at_5": _mcnemar_metric(
                grid,
                "negative_hit_at_5",
                lambda row: int(row["tempting_negative_rank"]) > 5,
            ),
        },
        "bootstrap": {
            "method": "paired_task_resampling",
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "mrr_delta": _bootstrap_interval(mrr_values, rng),
            "ndcg_at_5_delta": _bootstrap_interval(ndcg_values, rng),
            "negative_hit_rate_at_5_delta": _bootstrap_interval(negative_values, rng),
        },
        "repeated_seed_samples_independent": False,
    }


def _flags(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    flags = []
    candidate_gold = int(candidate["gold_rank"])
    baseline_gold = int(baseline["gold_rank"])
    candidate_negative = candidate["tempting_negative_rank"]
    baseline_negative = baseline["tempting_negative_rank"]
    if candidate_gold > 1:
        flags.append("TOP1_MISS")
    if candidate_gold > 5:
        flags.append("GOLD_MISS_AT_5")
    if type(candidate_negative) is int and candidate_negative <= 1:
        flags.append("NEGATIVE_HIT_AT_1")
    if type(candidate_negative) is int and candidate_negative <= 5:
        flags.append("NEGATIVE_HIT_AT_5")
    if (
        type(candidate_negative) is int
        and type(baseline_negative) is int
        and candidate_negative < baseline_negative
    ):
        flags.append("NEGATIVE_MOVED_EARLIER")
    if candidate_gold > baseline_gold:
        flags.append("GOLD_RANK_REGRESSION")
    baseline_latency = int(baseline["latency_ns"])
    candidate_latency = int(candidate["latency_ns"])
    if (baseline_latency == 0 and candidate_latency > 0) or (
        baseline_latency > 0 and candidate_latency / baseline_latency > 1.20
    ):
        flags.append("TASK_LATENCY_RATIO_GT_1_20")
    return [flag for flag in _FAILURE_FLAGS if flag in flags]


def build_failure_slices(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grid = _route_matrix(rows)
    task_ids = sorted({key[2] for key in grid})
    task_flags = []
    for seed in SEEDS:
        for task_id in task_ids:
            row = grid[("C", seed, task_id)]
            task_flags.append(
                {
                    "seed": seed,
                    "task_id": task_id,
                    "gold_skill_id": row["gold_skill_id"],
                    "tempting_negative_skill_id": row["tempting_negative_skill_id"],
                    "semantic_family_id": row["semantic_family_id"],
                    "flags": _flags(grid[("A", seed, task_id)], row),
                }
            )
    slices = []
    dimensions: tuple[tuple[str, Iterable[Any]], ...] = (
        ("ALL", ("ALL",)),
        ("gold_skill_id", sorted({row["gold_skill_id"] for row in task_flags})),
        (
            "tempting_negative_skill_id",
            sorted(
                {
                    row["tempting_negative_skill_id"]
                    for row in task_flags
                    if row["tempting_negative_skill_id"] is not None
                }
            ),
        ),
        (
            "semantic_family_id",
            sorted({row["semantic_family_id"] for row in task_flags}),
        ),
    )
    for seed in SEEDS:
        seed_rows = [row for row in task_flags if row["seed"] == seed]
        for dimension, values in dimensions:
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
    return {
        "schema_version": "router-v2-agent-blind-v2-failure-slices-v1",
        "comparison_scope": "A_VS_C_ONLY",
        "task_flags": task_flags,
        "slices": slices,
    }


def build_lineage_manifest(
    *,
    commit_a: str,
    commit_b: str,
    evaluator_commit: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    artifacts: dict[str, bytes],
) -> dict[str, Any]:
    for label, value in (
        ("commit_a", commit_a),
        ("commit_b", commit_b),
        ("evaluator_commit", evaluator_commit),
    ):
        _require(
            type(value) is str and _HEX40.fullmatch(value) is not None,
            f"{label} mismatch",
        )
    _require(
        type(attempt_token_sha256) is str
        and _HEX64.fullmatch(attempt_token_sha256) is not None,
        "attempt token hash mismatch",
    )
    _require(type(frozen_bindings) is dict, "frozen bindings mismatch")
    _require(
        "human_review" not in frozen_bindings,
        "human_review lineage is superseded by agent_construction",
    )
    _validate_frozen_binding_value(
        frozen_bindings,
        depth=0,
        active_container_ids=set(),
    )
    try:
        canonical_sha256(frozen_bindings)
    except (TypeError, ValueError) as exc:
        raise ValueError(_FROZEN_BINDINGS_ERROR) from exc
    _require(
        type(artifacts) is dict
        and all(
            type(path) is str and type(payload) is bytes
            for path, payload in artifacts.items()
        ),
        "artifact bindings mismatch",
    )
    document = {
        "schema_version": "router-v2-agent-blind-v2-lineage-v1",
        "commit_a": commit_a,
        "commit_b": commit_b,
        "evaluator_commit": evaluator_commit,
        "attempt_token_sha256": attempt_token_sha256,
        "frozen_bindings": frozen_bindings,
        "artifacts": [
            {
                "path": path,
                "sha256": hashlib.sha256(artifacts[path]).hexdigest(),
                "size": len(artifacts[path]),
            }
            for path in sorted(artifacts)
        ],
    }
    return {**document, "lineage_sha256": canonical_sha256(document)}
