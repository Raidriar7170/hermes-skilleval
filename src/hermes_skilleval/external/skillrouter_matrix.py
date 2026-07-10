from __future__ import annotations

import hashlib
import json
import math
import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from hermes_skilleval.external.skillrouter import (
    ExternalSkill,
    ExternalTask,
    SkillRouterAdapter,
)
from hermes_skilleval.external.skillrouter_scorer import score_skillrouter_predictions
from hermes_skilleval.provenance import _reject_sensitive_values
from hermes_skilleval.release_manifest import sha256_file


SEED = 20260625
FIELD_VIEW_VERSION = "v0.3.pr3.field-view.v1"
PLAN_SCHEMA = "v0.3.skillrouter-matrix-plan.v1"
REPORT_SCHEMA = "v0.3.skillrouter-matrix-report.v1"
UNAVAILABLE = "UNAVAILABLE"


def write_skillrouter_matrix_plan(
    *,
    data_root: Path | str,
    output_path: Path | str,
    upstream_ref: str,
    license_note: str,
    run_id: str,
    routers: Iterable[dict[str, Any]],
    field_views: Iterable[str] = ("name_only", "metadata", "full_body"),
    tiers: Iterable[str] = ("easy", "hard"),
    stress_candidate_sizes: Iterable[int] = (1000, 10000),
    matrix_output_path: Path | str | None = None,
    bootstrap_iterations: int = 10000,
    bootstrap_confidence: float = 0.95,
) -> dict[str, Any]:
    router_configs = [_frozen_router_config(router) for router in routers]
    if not router_configs:
        raise ValueError("at least one frozen router config is required")
    _assert_unique_config_ids(router_configs)
    selected_field_views = [_field_view_name(view) for view in field_views]
    selected_tiers = [str(tier) for tier in tiers]
    selected_sizes = [int(size) for size in stress_candidate_sizes]
    if any(size <= 0 for size in selected_sizes):
        raise ValueError("stress candidate sizes must be positive")
    if bootstrap_iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    if not 0.0 < bootstrap_confidence < 1.0:
        raise ValueError("bootstrap confidence must be between 0 and 1")

    adapter = SkillRouterAdapter(
        data_root=data_root,
        upstream_ref=upstream_ref,
        license_note=license_note,
    )
    validation = adapter.validate()
    if validation["status"] != "PASS":
        raise ValueError("external validation failed")
    plan = {
        "schema_version": PLAN_SCHEMA,
        "benchmark_id": "skillrouter",
        "run_id": _non_empty(run_id, "run_id"),
        "seed": SEED,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "git": _git_state(),
        "data_root": str(data_root),
        "adapter_provenance": adapter.provenance(validation),
        "validation": validation,
        "frozen_routers": router_configs,
        "field_views": selected_field_views,
        "field_view_builder_version": FIELD_VIEW_VERSION,
        "tiers": selected_tiers,
        "stress_candidate_sizes": selected_sizes,
        "bootstrap": {
            "iterations": bootstrap_iterations,
            "confidence": bootstrap_confidence,
        },
        "matrix_output_path": str(matrix_output_path) if matrix_output_path else None,
        "scope_guards": {
            "prediction_inputs_only": True,
            "no_training": True,
            "no_threshold_tuning": True,
            "no_hard_negative_mining": True,
            "no_model_inference": True,
            "no_embeddings": True,
            "no_rerankers": True,
            "no_live_agents": True,
            "no_release_promotion": True,
            "no_skillrouter_negative_hit_rate_without_negative_labels": True,
        },
    }
    _reject_sensitive_values(plan)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def run_skillrouter_matrix(*, plan_path: Path | str, output_path: Path | str) -> dict[str, Any]:
    plan_file = Path(plan_path)
    if not plan_file.exists():
        raise ValueError(f"frozen plan does not exist: {plan_file}")
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("unsupported frozen plan schema")
    _validate_frozen_plan(plan)
    _verify_matrix_output_path(plan, output_path)
    data_root = Path(_non_empty(plan.get("data_root"), "data_root"))
    tiers = tuple(plan.get("tiers") or ("easy", "hard"))
    adapter = SkillRouterAdapter(
        data_root=data_root,
        upstream_ref=plan["adapter_provenance"]["upstream_ref"],
        license_note=plan["adapter_provenance"]["license_note"],
        tiers=tiers,
    )
    _verify_adapter_provenance(adapter, plan)
    _verify_frozen_predictions(plan)

    official: dict[str, Any] = {}
    for router in plan["frozen_routers"]:
        config_id = router["config_id"]
        official[config_id] = {
            "config_id": config_id,
            "router_id": router["router_id"],
            "field_view": router["field_view"],
            "version": router.get("version"),
            "score": score_skillrouter_predictions(
                data_root=data_root,
                predictions_path=router["predictions_path"],
                mode="core",
                tiers=tiers,
            ),
        }

    diagnostics = _hermes_diagnostics(adapter, plan, official)
    report = {
        "schema_version": REPORT_SCHEMA,
        "benchmark_id": "skillrouter",
        "run_id": plan["run_id"],
        "plan_path": str(plan_file),
        "seed": plan["seed"],
        "official": {
            config_id: router_report["score"] | {
                "config_id": router_report["config_id"],
                "router_id": router_report["router_id"],
                "field_view": router_report["field_view"],
                "version": router_report["version"],
            }
            for config_id, router_report in official.items()
        },
        "hermes_diagnostics": diagnostics,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_field_view(skill: ExternalSkill, view: str) -> dict[str, Any]:
    selected_view = _field_view_name(view)
    parts = [skill.name]
    if selected_view in {"metadata", "full_body"} and skill.description:
        parts.append(skill.description)
    if selected_view == "full_body" and skill.body:
        parts.append(skill.body)
    return {
        "schema_version": "v0.3.skillrouter-field-view.v1",
        "view": selected_view,
        "builder_version": FIELD_VIEW_VERSION,
        "skill_id": skill.skill_id,
        "text": "\n".join(parts),
    }


def candidate_subset(
    *,
    all_skill_ids: Iterable[str],
    gt_skill_ids: Iterable[str],
    target_size: int,
    seed: int = SEED,
) -> dict[str, Any]:
    gt_ids = _unique(gt_skill_ids)
    if target_size < len(gt_ids):
        return {
            "status": UNAVAILABLE,
            "reason": (
                f"target_size {target_size} is smaller than selected GT union "
                f"{len(gt_ids)}"
            ),
            "seed": seed,
            "target_size": target_size,
            "required_gt_count": len(gt_ids),
        }
    gt_set = set(gt_ids)
    distractors = sorted(
        (skill_id for skill_id in _unique(all_skill_ids) if skill_id not in gt_set),
        key=lambda skill_id: hashlib.sha256(f"{seed}:{skill_id}".encode()).hexdigest(),
    )
    selected = gt_ids + distractors[: max(0, target_size - len(gt_ids))]
    return {
        "status": "PASS",
        "seed": seed,
        "target_size": target_size,
        "required_gt_count": len(gt_ids),
        "selected_skill_ids": selected,
        "candidate_hash": _hash_json(selected),
    }


def paired_bootstrap_ci(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    *,
    metric: str,
    iterations: int = 1000,
    seed: int = SEED,
    confidence: float = 0.95,
) -> dict[str, Any]:
    by_task_b = {row["task_id"]: row for row in rows_b}
    deltas = [
        float(row["metrics"][metric])
        - float(by_task_b[row["task_id"]]["metrics"][metric])
        for row in rows_a
        if row["task_id"] in by_task_b
        and metric in row.get("metrics", {})
        and metric in by_task_b[row["task_id"]].get("metrics", {})
    ]
    if not deltas:
        return {
            "schema_version": "v0.3.paired-bootstrap-ci.v1",
            "status": UNAVAILABLE,
            "reason": "no paired task metric rows",
            "metric": metric,
            "paired_task_count": 0,
        }
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        estimates.append(sum(sample) / len(sample))
    estimates.sort()
    alpha = 1.0 - confidence
    lower = estimates[max(0, int(math.floor((alpha / 2) * (iterations - 1))))]
    upper = estimates[min(iterations - 1, int(math.ceil((1 - alpha / 2) * (iterations - 1))))]
    return {
        "schema_version": "v0.3.paired-bootstrap-ci.v1",
        "status": "PASS",
        "metric": metric,
        "seed": seed,
        "iterations": iterations,
        "confidence": confidence,
        "paired_task_count": len(deltas),
        "point_estimate": sum(deltas) / len(deltas),
        "lower": lower,
        "upper": upper,
    }


def held_out_skill_split(tasks: list[ExternalTask]) -> dict[str, Any]:
    graph: dict[str, set[str]] = {}
    node_kind: dict[str, str] = {}
    for task in tasks:
        task_node = f"task:{task.task_id}"
        graph.setdefault(task_node, set())
        node_kind[task_node] = "task"
        for skill_id in _selected_task_gt_ids(task):
            skill_node = f"skill:{skill_id}"
            graph.setdefault(skill_node, set())
            node_kind[skill_node] = "skill"
            graph[task_node].add(skill_node)
            graph[skill_node].add(task_node)

    components = []
    seen: set[str] = set()
    for node in sorted(graph):
        if node in seen:
            continue
        stack = [node]
        component: set[str] = set()
        seen.add(node)
        while stack:
            current = stack.pop()
            component.add(current)
            for neighbor in graph[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        task_ids = sorted(item.removeprefix("task:") for item in component if item.startswith("task:"))
        skill_ids = sorted(item.removeprefix("skill:") for item in component if item.startswith("skill:"))
        task_type = "generic_only" if task_ids and not skill_ids else "scored"
        components.append(
            {
                "component_id": f"component-{len(components):03d}",
                "task_ids": task_ids,
                "skill_ids": skill_ids,
                "task_type": task_type,
                "split": "held_out" if len(components) % 2 else "train",
            }
        )
    train_tasks = {
        task_id
        for component in components
        if component["split"] == "train"
        for task_id in component["task_ids"]
    }
    held_out_tasks = {
        task_id
        for component in components
        if component["split"] == "held_out"
        for task_id in component["task_ids"]
    }
    train_skills = {
        skill_id
        for component in components
        if component["split"] == "train"
        for skill_id in component["skill_ids"]
    }
    held_out_skills = {
        skill_id
        for component in components
        if component["split"] == "held_out"
        for skill_id in component["skill_ids"]
    }
    return {
        "schema_version": "v0.3.held-out-skill-split.v1",
        "status": "PASS",
        "components": components,
        "overlap_assertions": {
            "task_overlap": sorted(train_tasks & held_out_tasks),
            "skill_overlap": sorted(train_skills & held_out_skills),
        },
    }


def held_out_source_split(tasks: list[ExternalTask]) -> dict[str, Any]:
    sources_by_task = {}
    for task in tasks:
        source = (
            task.metadata.get("source")
            or task.metadata.get("source_path")
            or task.metadata.get("path")
        )
        if not isinstance(source, str) or not source.strip():
            return {
                "schema_version": "v0.3.held-out-source-split.v1",
                "status": UNAVAILABLE,
                "reason": "source metadata is insufficient for held-out-source split",
            }
        sources_by_task[task.task_id] = source
    sources = sorted(set(sources_by_task.values()))
    if len(sources) < 2:
        return {
            "schema_version": "v0.3.held-out-source-split.v1",
            "status": UNAVAILABLE,
            "reason": (
                "source metadata is insufficient for held-out-source split: "
                "at least two distinct sources are required"
            ),
        }
    held_out_sources = set(sources[1::2])
    return {
        "schema_version": "v0.3.held-out-source-split.v1",
        "status": "PASS",
        "held_out_sources": sorted(held_out_sources),
        "assignments": {
            task_id: "held_out" if source in held_out_sources else "train"
            for task_id, source in sorted(sources_by_task.items())
        },
    }


def overlap_scaffold(
    *,
    skillrouter_tasks: list[ExternalTask],
    skillsbench_tasks: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if skillsbench_tasks is None:
        return {
            "schema_version": "v0.3.skillrouter-skillsbench-overlap.v1",
            "skillrouter_task_count": len(skillrouter_tasks),
            "skillsbench_task_count": {
                "status": UNAVAILABLE,
                "reason": "SkillsBench live tasks not selected in PR-3",
            },
            "exact_id_overlap": [],
            "normalized_text_hash_overlap": [],
            "high_similarity_diagnostics": {
                "status": UNAVAILABLE,
                "reason": "high-similarity diagnostics require selected live tasks",
            },
        }
    skillrouter_by_id = {task.task_id: task for task in skillrouter_tasks}
    skillsbench_by_id = {
        str(task["task_id"]): task for task in skillsbench_tasks if "task_id" in task
    }
    sr_hashes = {_normalized_hash(task.query): task.task_id for task in skillrouter_tasks}
    sb_hashes = {
        _normalized_hash(str(task.get("query", ""))): task_id
        for task_id, task in skillsbench_by_id.items()
    }
    return {
        "schema_version": "v0.3.skillrouter-skillsbench-overlap.v1",
        "skillrouter_task_count": len(skillrouter_tasks),
        "skillsbench_task_count": len(skillsbench_tasks),
        "exact_id_overlap": sorted(set(skillrouter_by_id) & set(skillsbench_by_id)),
        "normalized_text_hash_overlap": sorted(set(sr_hashes) & set(sb_hashes)),
        "high_similarity_diagnostics": {
            "status": UNAVAILABLE,
            "reason": "high-similarity diagnostics not selected in PR-3",
        },
    }


def _hermes_diagnostics(
    adapter: SkillRouterAdapter,
    plan: dict[str, Any],
    official: dict[str, Any],
) -> dict[str, Any]:
    stress: dict[str, dict[str, Any]] = {}
    for tier in plan["tiers"]:
        skills = list(adapter.iter_skills(tier))
        all_skill_ids = [skill.skill_id for skill in skills]
        gt_skill_ids = _selected_gt_union(adapter, tier)
        stress[tier] = {
            str(size): candidate_subset(
                all_skill_ids=all_skill_ids,
                gt_skill_ids=gt_skill_ids,
                target_size=int(size),
                seed=int(plan["seed"]),
            )
            for size in plan["stress_candidate_sizes"]
        }

    ci: dict[str, Any] = {}
    router_ids = list(official)
    if len(router_ids) >= 2:
        for first_index, first in enumerate(router_ids):
            for second in router_ids[first_index + 1 :]:
                for tier in plan["tiers"]:
                    rows_a = official[first]["score"]["by_tier"][tier]["tasks"]
                    rows_b = official[second]["score"]["by_tier"][tier]["tasks"]
                    bootstrap = plan.get("bootstrap", {})
                    ci[f"{first}__minus__{second}__{tier}__MRR@10"] = paired_bootstrap_ci(
                        rows_a,
                        rows_b,
                        metric="MRR@10",
                        iterations=int(bootstrap.get("iterations", 10000)),
                        seed=int(plan["seed"]),
                        confidence=float(bootstrap.get("confidence", 0.95)),
                    )

    tasks = adapter.load_tasks()
    return {
        "schema_version": "v0.3.skillrouter-hermes-diagnostics.v1",
        "field_view_builder_version": FIELD_VIEW_VERSION,
        "candidate_count_by_tier": {
            tier: sum(1 for _ in adapter.iter_skills(tier)) for tier in plan["tiers"]
        },
        "stress_candidate_subsets": stress,
        "paired_bootstrap_confidence_intervals": ci,
        "held_out_skill": held_out_skill_split(tasks),
        "held_out_source": held_out_source_split(tasks),
        "skillrouter_skillsbench_overlap": overlap_scaffold(
            skillrouter_tasks=tasks,
            skillsbench_tasks=None,
        ),
    }


def _selected_gt_union(adapter: SkillRouterAdapter, tier: str) -> list[str]:
    relevance_entries = adapter._load_relevance_entries()
    tier_pool = {skill.skill_id for skill in adapter.iter_skills(tier)}
    gt_ids = []
    for task in adapter.load_tasks():
        entry = relevance_entries.get(task.task_id, {})
        if task.task_type == "generic_only":
            continue
        selected = _selected_gt_ids(entry)
        gt_ids.extend(skill_id for skill_id in selected if skill_id in tier_pool)
    return _unique(gt_ids)


def _selected_task_gt_ids(task: ExternalTask) -> list[str]:
    for field in ("core_gt_ids", "gt_skill_ids"):
        values = task.metadata.get(field)
        if isinstance(values, list):
            return [item for item in values if isinstance(item, str)]
    return [
        skill_id
        for skill_id, relevance in task.graded_relevance.items()
        if str(skill_id).startswith("gt/") and float(relevance) > 0
    ]


def _selected_gt_ids(entry: dict[str, Any]) -> list[str]:
    if "core_gt_ids" in entry:
        return [item for item in entry.get("core_gt_ids", []) if isinstance(item, str)]
    return [item for item in entry.get("gt_skill_ids", []) if isinstance(item, str)]


def _frozen_router_config(router: dict[str, Any]) -> dict[str, Any]:
    router_id = _non_empty(router.get("router_id"), "router_id")
    field_view = _field_view_name(router.get("field_view", "full_body"))
    predictions_path = _non_empty(router.get("predictions_path"), "predictions_path")
    prediction_file = Path(predictions_path)
    if not prediction_file.exists():
        raise ValueError(f"predictions file does not exist: {predictions_path}")
    config_id = router.get("config_id") or f"{router_id}__{field_view}"
    config = {
        "config_id": _non_empty(config_id, "config_id"),
        "router_id": router_id,
        "field_view": field_view,
        "predictions_path": predictions_path,
        "prediction_file": _file_fingerprint(prediction_file),
        "version": router.get("version", "UNSPECIFIED"),
        "top_k": router.get("top_k"),
        "threshold": router.get("threshold"),
        "normalization": router.get("normalization"),
    }
    _reject_sensitive_values(config)
    return config


def _assert_unique_config_ids(router_configs: list[dict[str, Any]]) -> None:
    seen = set()
    for config in router_configs:
        config_id = config["config_id"]
        if config_id in seen:
            raise ValueError(f"duplicate config_id: {config_id}")
        seen.add(config_id)


def _validate_frozen_plan(plan: dict[str, Any]) -> None:
    _assert_unique_config_ids(plan.get("frozen_routers", []))
    bootstrap = plan.get("bootstrap")
    if not isinstance(bootstrap, dict):
        raise ValueError("bootstrap settings must be frozen in the plan")
    iterations = bootstrap.get("iterations")
    confidence = bootstrap.get("confidence")
    if not isinstance(iterations, int) or iterations <= 0:
        raise ValueError("bootstrap settings must include positive iterations")
    if not isinstance(confidence, (int, float)) or not 0.0 < float(confidence) < 1.0:
        raise ValueError("bootstrap settings must include confidence between 0 and 1")


def _verify_matrix_output_path(plan: dict[str, Any], output_path: Path | str) -> None:
    expected = plan.get("matrix_output_path")
    if expected and str(output_path) != expected:
        raise ValueError(
            "matrix output path does not match frozen plan: "
            f"expected {expected}, got {output_path}"
        )


def _verify_adapter_provenance(
    adapter: SkillRouterAdapter,
    plan: dict[str, Any],
) -> None:
    validation = adapter.validate()
    if validation["status"] != "PASS":
        raise ValueError("external validation failed")
    current = _adapter_file_fingerprints(adapter.provenance(validation))
    frozen = _adapter_file_fingerprints(plan["adapter_provenance"])
    if current != frozen:
        raise ValueError("adapter provenance changed since frozen plan")


def _verify_frozen_predictions(plan: dict[str, Any]) -> None:
    for router in plan["frozen_routers"]:
        current = _file_fingerprint(Path(router["predictions_path"]))
        frozen = router.get("prediction_file")
        if current != frozen:
            raise ValueError(
                "prediction file changed since frozen plan: "
                f"{router['config_id']}"
            )


def _adapter_file_fingerprints(provenance: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "path": record.get("path"),
                "role": record.get("role"),
                "size_bytes": record.get("size_bytes"),
                "sha256": record.get("sha256"),
                "record_count": record.get("record_count"),
            }
            for record in provenance.get("files", [])
        ),
        key=lambda record: (str(record["role"]), str(record["path"])),
    )


def _file_fingerprint(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _field_view_name(view: Any) -> str:
    if view not in {"name_only", "metadata", "full_body"}:
        raise ValueError(f"unsupported SkillRouter field view: {view}")
    return str(view)


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _git_state() -> dict[str, Any]:
    return {
        "commit": _git_output(("rev-parse", "HEAD")) or "UNKNOWN",
        "dirty": bool(_git_output(("status", "--porcelain"))),
    }


def _git_output(args: tuple[str, ...]) -> str:
    try:
        return subprocess.check_output(("git", *args), text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _hash_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _normalized_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()
