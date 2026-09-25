"""Finite N/MMR/R matched-prefix study; historical studies remain read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random

from .linked_context_study import read
from .relation_store import atomic_json

STUDY = "repair-knowledge-functional-closeout-v1"
SEED = 20260924
BASELINE = "b6d9316d6edd84d1a70543f290aaf3f00f7f5b90"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def matrix(tasks):
    rng = random.Random(SEED)
    cells = []
    for task in tasks:
        for repeat in (1, 2):
            arms = ["N", "M", "R"]
            rng.shuffle(arms)
            cells.extend(
                dict(task_id=task["instance_id"], arm=a, repeat=repeat) for a in arms
            )
    return cells


def prepare(repo, assets, output):
    """Register public metadata before qualification; never inspect repair outcomes."""
    roster_path = output / "task_roster.json"
    if roster_path.exists():
        return read(roster_path)
    source = repo / "configs/repair-knowledge-composition-v1/source-pool.json"
    pool = read(source)
    rows = sorted(pool["rows"], key=lambda t: t["instance_id"])
    random.Random(SEED).shuffle(rows)
    prior = read(repo / "configs/repair-knowledge-composition-v1/plan.json")
    used = {t["instance_id"]: t["split"] for t in prior["tasks"]}
    candidates = []
    for position, row in enumerate(rows, 1):
        task = assets / "hermes-repair-knowledge-private/tasks" / row["instance_id"]
        candidates.append(
            {
                "instance_id": row["instance_id"],
                "repo": row["repo"],
                "base_commit": row["base_commit"],
                "mechanism": row["mechanism"],
                "queue_position": position,
                "public_problem": row["problem_statement"],
                "public_requirements": row.get("requirements", ""),
                "public_interface": row.get("interface", ""),
                "prior_use": "EXPLORATORY_REUSE_" + used[row["instance_id"]].upper()
                if row["instance_id"] in used
                else "PREVIOUSLY_REGISTERED_RESOURCE_CANDIDATE",
                "materialized": all(
                    (task / n).exists()
                    for n in (
                        "base",
                        "task.json",
                        "request.txt",
                        "evaluation/selectors.json",
                        "reference",
                    )
                ),
                "eligibility": "PENDING_PUBLIC_AND_TRUSTED_PREFLIGHT",
            }
        )
    roster = {
        "study": STUDY,
        "seed": SEED,
        "source": pool["source"],
        "dataset_revision": pool["dataset_revision"],
        "source_sha256": sha(source),
        "ordering": "sorted instance_id then Python Random(20260924).shuffle",
        "finite_queue": candidates,
        "target": 4,
        "reserve_max": 2,
        "selection_excludes_agent_outcomes_and_package_differences": True,
    }
    atomic_json(roster_path, roster)
    return roster


def qualify(tasks, overlays, output, roster, version="qualification-v2"):
    """Trusted side: only eligibility escapes; raw checks stay in private output."""
    import runpy
    from .repair_checks import check_source

    build = runpy.run_path("scripts/repair_knowledge_composition/revalidate.py")[
        "build_overlay"
    ]
    rows = []
    for entry in roster["finite_queue"][:6]:
        if sum(r["eligible"] for r in rows) >= 6:
            break
        tid = entry["instance_id"]
        task = tasks / tid
        result = {"instance_id": tid, "eligible": False}
        if not entry["materialized"]:
            result["reason"] = "INCOMPLETE_EXISTING_TASK_ASSETS"
        else:
            overlay = overlays / tid
            build(task, overlay)
            checks = {
                variant: check_source(
                    task,
                    task / variant,
                    output / version / tid / variant,
                    image="hermes-repair-knowledge-executor:v1",
                    trusted_overlay=overlay,
                )
                for variant in ("base", "reference")
            }
            eligible = (
                all(c.get("valid") for v in checks.values() for c in v.values())
                and not checks["base"]["target"]["passed"]
                and checks["base"]["regression"]["passed"]
                and all(c["passed"] for c in checks["reference"].values())
            )
            result.update(
                eligible=eligible,
                reason="DISCRIMINATING_CHECKS"
                if eligible
                else "TRUSTED_QUALIFICATION_UNAVAILABLE",
            )
        rows.append(result)
        atomic_json(
            output / "qualification-summary.json", {"rows": rows, "agent_calls": 0}
        )
        print(json.dumps(result), flush=True)
    return rows


def compose_common(task, output, encoder_path):
    """Lock N/M before independent R; all online preparation is charged."""
    from dataclasses import asdict
    from .evidence_linked_state import analyze
    from .local_retrieval import retrieve
    from .repair_composer import CompleteEncoder, render_pack, select_mmr
    from .repair_content_study import first_checkpoint, verify_checkpoint
    from .method_budget import MethodBudget, boot_identity
    from .value import Encoder

    tid = task["instance_id"]
    root = output / "selection" / tid
    lock = root / "common.json"
    if lock.exists():
        return read(lock)
    execution = read(output / "prefixes" / tid / "execution.json")
    cp = first_checkpoint(execution)
    if cp is None:
        result = {"task_id": tid, "status": "NO_PREFIX", "checkpoint": None}
        atomic_json(lock, result)
        return result
    meta = verify_checkpoint(cp)
    budget = MethodBudget(
        root / "common-cost.json",
        meta["remaining_seconds"],
        identity=sha(cp / "checkpoint.json"),
        host_clock=boot_identity(),
    )
    state = {
        "task_id": tid,
        "checkpoint": str(cp),
        "checkpoint_sha256": sha(cp / "checkpoint.json"),
        "prefix_remaining_seconds": meta["remaining_seconds"],
        "prefix_seconds": 600 - meta["remaining_seconds"],
        "N": {"message": None, "cost": 0.0},
        "status": "N_READY",
    }
    atomic_json(root / "N.json", state)
    try:
        with budget.stage("public_ledger_and_index_load"):
            ledger = analyze(
                meta["state"]["request"],
                meta["visible_events"],
                checkpoint_event_count=len(meta["visible_events"]),
                initial_source_version=task["base_commit"],
            )
            index = read(
                output / "public-knowledge" / task["base_commit"] / "index.json"
            )
            atomic_json(root / "ledger.json", ledger)
        with budget.stage("encoder_initialization"):
            encoder = CompleteEncoder(Encoder(encoder_path))
        with budget.stage("local_candidates_mmr_render"):
            pool, diag = retrieve(
                index,
                ledger,
                encoder=encoder,
                visible_text="\n".join(o["output"] for o in ledger["observations"]),
                read_symbols=tuple(
                    p
                    for o in ledger["observations"]
                    if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
                    for p in o["paths"]
                ),
            )
            pack = select_mmr(pool)
            atomic_json(root / "pool.json", asdict(pool))
            atomic_json(root / "retrieval.json", diag)
            m = {"pack": pack.to_dict(), "message": render_pack(pack)}
            atomic_json(root / "M-pack.json", m)
        state.update(M={**m, "cost": budget.spent}, status="M_READY")
        atomic_json(lock, state)
        return state
    except (ValueError, RuntimeError, TimeoutError) as exc:
        state.update(status="M_UNAVAILABLE", error=str(exc))
        atomic_json(lock, state)
        return state


def compose_r(task, repeat, output, encoder_path, cost_model):
    """Each repeated R owns an empty relation store and its measured preparation."""
    from .linked_context_study import load_pool
    from .method_budget import MethodBudget, boot_identity
    from .pair_applicability import build_features
    from .relation_query_study import run_public_policy
    from .repair_composer import CompleteEncoder
    from .repair_knowledge import RepairKnowledgeUnit, render_units
    from .value import Encoder

    root = output / "selection" / task["instance_id"]
    common = read(root / "common.json")
    lock = root / f"R-r{repeat}.json"
    if lock.exists():
        return read(lock)
    if "M" not in common:
        result = {"status": "UNAVAILABLE", "reason": "COMMON_CANDIDATES_UNAVAILABLE"}
        atomic_json(lock, result)
        return result
    remaining = max(0, common["prefix_remaining_seconds"] - common["M"]["cost"])
    budget = MethodBudget(
        root / f"R-r{repeat}-cost.json",
        remaining,
        identity=common["checkpoint_sha256"] + f"/R/{repeat}",
        host_clock=boot_identity(),
    )
    acquisition = root / f"R-r{repeat}"
    result = {
        "message": common["M"]["message"],
        "pack": common["M"]["pack"],
        "status": "MMR_FALLBACK",
        "fallback_reason": "NO_AVAILABLE_RELATION_BUDGET",
        "acquisition_started": False,
    }
    try:
        with budget.stage("pair_feature_inputs_encoder_and_features"):
            ledger, pool = read(root / "ledger.json"), load_pool(root / "pool.json")
            index = read(
                output / "public-knowledge" / task["base_commit"] / "index.json"
            )
            encoder = CompleteEncoder(Encoder(encoder_path))
            features = build_features(ledger, pool, encoder, index["nodes"])
            atomic_json(root / f"R-r{repeat}-features.json", features)
        # The inherited transport reserves five seconds for termination itself.
        limit = min(60.0, max(0.0, budget.remaining - 1.0))
        if limit > 5:
            with budget.stage("relation_acquisition_and_render"):
                result["acquisition_started"] = True
                acquired = run_public_policy(
                    ledger,
                    pool,
                    features,
                    cost_model,
                    acquisition,
                    seconds=limit,
                    name=task["mechanism"],
                )
                message = render_units(
                    [
                        RepairKnowledgeUnit.from_dict(u)
                        for u in acquired["pack"]["units"]
                    ]
                )
                changed = message != common["M"]["message"]
                result.update(
                    pack=acquired["pack"],
                    message=message,
                    status="RELATION_SELECTED" if changed else "MMR_FALLBACK",
                    fallback_reason=None if changed else acquired["stop_reason"],
                    acquisition_seconds=acquired["seconds"],
                    relation_limit=limit,
                    acquisition_sha256=sha(acquisition / "final.json"),
                )
    except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
        result.update(
            status="MMR_FALLBACK", fallback_reason=type(exc).__name__ + ": " + str(exc)
        )
    result.update(
        cost=common["M"]["cost"] + budget.spent,
        extra_cost=budget.spent,
        same_as_mmr=result["message"] == common["M"]["message"],
        payload_sha256=hashlib.sha256((result["message"] or "").encode()).hexdigest(),
    )
    atomic_json(lock, result)
    return result


def cell_path(output, cell):
    return output / "tails" / cell["task_id"] / f"{cell['arm']}-r{cell['repeat']}"


def run_study(plan, tasks, skills, output, phase):
    from .diagnostic import home_auth
    from .linked_context_study import early_checkpoint
    from .repair_content_study import verify_checkpoint
    from .repair_knowledge import token_count
    from .study import run_once

    home, auth = home_auth(output)
    try:
        if phase == "prefix":
            for task in plan["tasks"]:
                dest = output / "prefixes" / task["instance_id"]
                result = run_once(
                    tasks / task["instance_id"],
                    dest,
                    home,
                    skills,
                    total=600,
                    image=plan["image"],
                    public_docs=output / "public-knowledge" / task["base_commit"],
                    checkpoint_selector=early_checkpoint,
                    stop_at_checkpoint=True,
                )
                if not (dest / "execution.json").exists():
                    atomic_json(dest / "execution.json", result)
                print(task["mechanism"], result["status"], flush=True)
            return
        by_id = {t["instance_id"]: t for t in plan["tasks"]}
        for cell in matrix(plan["tasks"]):
            dest = cell_path(output, cell)
            if (dest / "execution.json").exists():
                continue
            root = output / "selection" / cell["task_id"]
            common_path = root / "common.json"
            common = (
                read(common_path)
                if common_path.exists()
                else (read(root / "N.json") if (root / "N.json").exists() else {})
            )
            r_path = root / f"R-r{cell['repeat']}.json"
            selected = (
                (read(r_path) if r_path.exists() else None)
                if cell["arm"] == "R"
                else common.get(cell["arm"])
            )
            if (
                not common
                or (cell["arm"] == "R" and not r_path.exists())
                or (cell["arm"] == "M" and common.get("status") == "N_READY")
            ):
                # Readiness is not a terminated attempt; N/M can run before R.
                atomic_json(
                    output / "pending" / cell["task_id"] / (dest.name + ".json"),
                    {**cell, "status": "PREPARATION_PENDING"},
                )
                continue
            if not common.get("checkpoint") or not selected or "cost" not in selected:
                atomic_json(
                    dest / "execution.json",
                    {
                        "status": "NOT_RUN_UNAVAILABLE",
                        "research_execution_started": False,
                    },
                )
                continue
            cp = Path(common["checkpoint"])
            if sha(cp / "checkpoint.json") != common["checkpoint_sha256"]:
                raise ValueError("Common prefix changed")
            verify_checkpoint(cp)
            payload = selected["message"]
            binding = {
                **cell,
                "charged_seconds": selected["cost"],
                "initial_remaining": common["prefix_remaining_seconds"],
                "payload_sha256": hashlib.sha256((payload or "").encode()).hexdigest(),
                "plan_digest": plan["plan_digest"],
            }
            binding_path = (
                output / "cell-budgets" / cell["task_id"] / (dest.name + ".json")
            )
            if not binding_path.exists():
                atomic_json(binding_path, binding)
            elif read(binding_path) != binding:
                raise ValueError("Attempt budget binding changed")
            result = run_once(
                tasks / cell["task_id"],
                dest,
                home,
                skills,
                from_checkpoint=cp,
                payload=payload,
                payload_tokens=token_count(payload or ""),
                initialization_seconds=selected["cost"],
                image=plan["image"],
                public_docs=output
                / "public-knowledge"
                / by_id[cell["task_id"]]["base_commit"],
            )
            if not (dest / "execution.json").exists():
                atomic_json(dest / "execution.json", result)
            print(cell, result["status"], flush=True)
    finally:
        auth.unlink(missing_ok=True)


def configure(repo, assets, output, encoder):
    """Choose the first qualified mechanisms and build offline warm indexes."""
    from .budgeted_study_assets import prepare as build_indexes

    summary = read(output / "qualification-summary.json")
    qualified = {r["instance_id"] for r in summary["rows"] if r["eligible"]}
    roster = read(output / "task_roster.json")
    selected = [t for t in roster["finite_queue"] if t["instance_id"] in qualified][:4]
    prior = read(repo / "configs/budgeted-relation-selection-v1/plan.json")
    tasks = [
        {
            k: t[k]
            for k in (
                "instance_id",
                "repo",
                "base_commit",
                "mechanism",
                "prior_use",
                "queue_position",
            )
        }
        for t in selected
    ]
    path = repo / "configs" / STUDY / "plan.json"
    if path.exists() and read(path).get("status") == "FROZEN":
        raise ValueError("Cannot reconfigure a frozen study")
    plan = {
        "study": STUDY,
        "status": "DEVELOPMENT_NOT_FROZEN",
        "baseline": BASELINE,
        "scope": "preregistered_small_sample_matched_prefix_study",
        "primary_outcome": "target_and_protected_regression",
        "primary_contrast": "R_minus_M",
        "secondary_contrast": "R_minus_N",
        "arms": ["N", "M", "R"],
        "tasks": tasks,
        "tasks_target": 4,
        "tasks_max_before_sampling": 6,
        "repeats_per_task_arm": 2,
        "public_prefixes_per_task": 1,
        "repair_total_active_seconds": 600,
        "index_scenario": "warm_index",
        "preprocessing_accounting": "own_method_cost",
        "candidate_cap": 24,
        "guidance_token_cap": 1200,
        "max_pack_units": 4,
        "explicit_interventions_per_tail_max": 1,
        "R_query_method": "PR55_R_weighted_pair_relevance_with_requirement_round_robin",
        "R_relation_budget_seconds_max": 60,
        "R_unique_pair_cap": 48,
        "R_transport": "final_PR55_fixed_startup_guard_and_frozen_cost_envelope",
        "reference_QJ_preload": False,
        "exclude_same_pack_tasks": False,
        "exclude_native_success_tasks": False,
        "new_training": False,
        "generic_reminder_arm": False,
        "seed": SEED,
        "default_policy": "UNCHANGED",
        **{
            k: prior[k]
            for k in (
                "model",
                "effort",
                "codex_version",
                "image",
                "image_id",
                "representation",
            )
        },
    }
    build_indexes(
        plan,
        output / "tasks",
        assets / "hermes-repair-knowledge-private/knowledge",
        output,
    )
    cost_source = (
        assets / "hermes-relation-applicability-private/study-v1/cost-model.json"
    )
    # Only transport measurements, never the old Q/J or best semantic package.
    atomic_json(output / "cost-model.json", read(cost_source))
    plan["cost_model_sha256"] = sha(output / "cost-model.json")
    plan["task_roster_sha256"] = sha(output / "task_roster.json")
    plan["qualification_summary_sha256"] = sha(output / "qualification-summary.json")
    plan["coverage_limits"] = [
        "Exploratory reuse of prior registered mechanisms",
        "Python 3 runtime only; no Python 2 execution claim",
    ]
    atomic_json(path, plan)
    atomic_json(
        output / "selected-tasks.json", {"tasks": tasks, "planned_cells": matrix(tasks)}
    )
    return plan


def preflight(repo, assets, output):
    """One old-state rehearsal; never create a development repair sample."""
    from .linked_context_study import load_pool
    from .relation_query_study import run_public_policy
    from .repair_composer import render_pack, select_mmr
    from .repair_knowledge import token_count
    from .session import NEUTRAL

    target = output / "preflight"
    if (target / "result.json").exists():
        return read(target / "result.json")
    old = assets / "hermes-relation-applicability-private/study-v1"
    source = old / "inputs/empty-keyed-group-naming"
    ledger, pool = read(source / "ledger.json"), load_pool(source / "pool.json")
    features, costs = read(source / "features.json"), read(old / "cost-model.json")
    m = select_mmr(pool)
    message = render_pack(m)
    if token_count(message) > 1200 or len(m.units) > 4:
        raise ValueError("MMR pack exceeds frozen contract")
    # Creating this directory reserves the one permitted rehearsal, even on interruption.
    result = run_public_policy(
        ledger,
        pool,
        features,
        costs,
        target / "acquisition",
        seconds=60,
        name="old-empty-keyed-group-development-state",
    )
    value = {
        "status": "ENTRYPOINT_VERIFIED",
        "repair_calls": 0,
        "relation_rehearsals": 1,
        "relation_seconds": result["seconds"],
        "relation_stop_reason": result["stop_reason"],
        "mmr_tokens": token_count(message),
        "mmr_units": len(m.units),
        "continuation_neutral_sha256": hashlib.sha256(NEUTRAL.encode()).hexdigest(),
        "formal_relation_preload": False,
        "result_sha256": sha(target / "acquisition/final.json"),
    }
    atomic_json(target / "result.json", value)
    return value


def freeze(repo, output, skills, encoder):
    import subprocess
    from .session import inventory

    path = repo / "configs" / STUDY / "plan.json"
    plan = read(path)
    if plan["status"] != "DEVELOPMENT_NOT_FROZEN":
        raise ValueError("Already frozen")
    if read(output / "preflight/result.json")["status"] != "ENTRYPOINT_VERIFIED":
        raise ValueError("Missing wiring preflight")
    actual = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    version = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            plan["image"],
            "codex",
            "--version",
        ],
        text=True,
    ).strip()
    if actual != plan["image_id"] or version != plan["codex_version"]:
        raise ValueError("Frozen runtime identity mismatch")
    for name, digest in plan["representation"]["files"].items():
        if sha(encoder / name) != digest:
            raise ValueError("Encoder identity mismatch")
    plan["skills"] = inventory(skills)
    files = list((repo / "src/hermes_skilleval/intervention").glob("*.py"))
    files += [
        repo / "src/hermes_skilleval/repo_routing/advisory_capture.py",
        repo / "scripts/budgeted_relation_selection/continue_acceptance.py",
    ]
    plan["algorithm_files"] = {str(p.relative_to(repo)): sha(p) for p in files}
    for task in plan["tasks"]:
        root = output / "tasks" / task["instance_id"]
        task["task_sha256"] = sha(root / "task.json")
        task["request_sha256"] = sha(root / "request.txt")
        task["asset_inventory_sha256"] = {
            kind: hashlib.sha256(
                json.dumps(inventory(root / kind), sort_keys=True).encode()
            ).hexdigest()
            for kind in ("base", "evaluation")
        }
        task["overlay_inventory"] = inventory(output / "overlays" / task["instance_id"])
        task["public_knowledge_inventory"] = inventory(
            output / "public-knowledge" / task["base_commit"]
        )
    plan.update(
        status="FROZEN",
        execution_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
    )
    plan["plan_digest"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()
    ).hexdigest()
    atomic_json(path, plan)
    return plan


def verify(plan, repo, output, skills, encoder):
    from .session import inventory
    import subprocess

    actual_image = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    if actual_image != plan["image_id"]:
        raise ValueError("Executor image changed")
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    if (
        plan["status"] != "FROZEN"
        or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        != plan["plan_digest"]
    ):
        raise ValueError("Unfrozen or changed plan")
    for name, digest in plan["algorithm_files"].items():
        if sha(repo / name) != digest:
            raise ValueError("Method source changed: " + name)
    for name, digest in plan["representation"]["files"].items():
        if sha(encoder / name) != digest:
            raise ValueError("Encoder changed")
    if (
        inventory(skills) != plan["skills"]
        or sha(output / "cost-model.json") != plan["cost_model_sha256"]
    ):
        raise ValueError("Skills or cost envelope changed")
    for task in plan["tasks"]:
        root = output / "tasks" / task["instance_id"]
        if (
            sha(root / "request.txt") != task["request_sha256"]
            or sha(root / "task.json") != task["task_sha256"]
        ):
            raise ValueError("Public task input changed")
        for kind, expected in task["asset_inventory_sha256"].items():
            actual = hashlib.sha256(
                json.dumps(inventory(root / kind), sort_keys=True).encode()
            ).hexdigest()
            if actual != expected:
                raise ValueError("Frozen task assets changed")
        if (
            inventory(output / "overlays" / task["instance_id"])
            != task["overlay_inventory"]
        ):
            raise ValueError("Trusted overlay changed")
        if (
            inventory(output / "public-knowledge" / task["base_commit"])
            != task["public_knowledge_inventory"]
        ):
            raise ValueError("Public knowledge mount changed")


def accept(plan, output):
    import runpy
    from .linked_context_study import functional_label
    from .repair_checks import accept_candidate

    cells = matrix(plan["tasks"])
    if not all((cell_path(output, c) / "execution.json").exists() for c in cells):
        raise ValueError(
            "Do not release functional labels before all fixed attempts end"
        )
    recover = runpy.run_path(
        "scripts/budgeted_relation_selection/continue_acceptance.py"
    )["recover"]
    rows = []
    for cell in cells:
        root = cell_path(output, cell)
        execution = read(root / "execution.json")
        task = output / "tasks" / cell["task_id"]
        overlay = output / "overlays" / cell["task_id"]
        integrity, target, protected = "UNCONFIRMED", "UNKNOWN", "UNKNOWN"
        error = None
        if (root / "source").exists():
            try:
                try:
                    accepted = accept_candidate(
                        task,
                        root,
                        root / "acceptance",
                        image=plan["image"],
                        trusted_overlay=overlay,
                    )
                except ValueError as exc:
                    if str(exc) != "reconstructed candidate differs":
                        raise
                    atomic_json(
                        root / "acceptance/reconstruction-error.json",
                        {"error": str(exc)},
                    )
                    recover(task, root, overlay, plan["image"])
                    accepted = read(root / "acceptance/acceptance.json")
                integrity = (
                    "CONFIRMED"
                    if accepted["integrity"] == "VERIFIED"
                    else "UNCONFIRMED"
                )

                def label(check):
                    return (
                        ("PASS" if check["passed"] else "FAIL")
                        if check.get("valid")
                        else "UNKNOWN"
                    )

                target = label(accepted["checks"]["target"])
                protected = label(accepted["checks"]["regression"])
            except (ValueError, OSError, RuntimeError) as exc:
                error = type(exc).__name__ + ": " + str(exc)
        rows.append(
            {
                **cell,
                "integrity": integrity,
                "target": target,
                "protected": protected,
                "functional": functional_label(
                    integrity=integrity, target=target, protected=protected
                ),
                "execution_status": execution["status"],
                "acceptance_error": error,
            }
        )
        atomic_json(
            output / "functional-results.json", {"rows": rows, "planned": len(cells)}
        )
        print(cell, rows[-1]["functional"], flush=True)
    return rows


def summarize_rows(tasks, rows):
    """Task-equal contrasts, complete outcomes only, with missing-value bounds."""
    expected = {(c["task_id"], c["arm"], c["repeat"]) for c in matrix(tasks)}
    actual = [(r["task_id"], r["arm"], r["repeat"]) for r in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Missing or duplicate planned cells")
    groups = []
    for task in tasks:
        for arm in ("N", "M", "R"):
            values = [
                r["functional"]
                for r in rows
                if r["task_id"] == task["instance_id"] and r["arm"] == arm
            ]
            if len(values) != 2 or any(
                v not in {"PASS", "FAIL", "UNKNOWN"} for v in values
            ):
                raise ValueError("Every planned cell must be represented exactly once")
            groups.append(
                {
                    "task_id": task["instance_id"],
                    "mechanism": task["mechanism"],
                    "arm": arm,
                    **{v: values.count(v) for v in ("PASS", "FAIL", "UNKNOWN")},
                    "planned": 2,
                }
            )
    contrasts = {}
    lookup = {(g["task_id"], g["arm"]): g for g in groups}
    for other in ("M", "N"):
        differences, bounds, outcomes = [], [], []
        for task in tasks:
            r, b = lookup[task["instance_id"], "R"], lookup[task["instance_id"], other]
            bounds.append(
                (
                    (r["PASS"] - b["PASS"] - b["UNKNOWN"]) / 2,
                    (r["PASS"] + r["UNKNOWN"] - b["PASS"]) / 2,
                )
            )
            if r["UNKNOWN"] or b["UNKNOWN"]:
                outcomes.append("UNKNOWN")
            else:
                delta = (r["PASS"] - b["PASS"]) / 2
                differences.append(delta)
                outcomes.append("WIN" if delta > 0 else "LOSS" if delta < 0 else "TIE")
        n = len(tasks)
        contrasts["R_minus_" + other] = {
            "task_counts": {
                v: outcomes.count(v) for v in ("WIN", "LOSS", "TIE", "UNKNOWN")
            },
            "task_mean_difference": sum(differences) / n
            if n and len(differences) == n
            else None,
            "missing_bounds": [sum(b[i] for b in bounds) / n for i in (0, 1)]
            if n
            else [None, None],
            "independent_mechanisms": n,
        }
    return groups, contrasts


def observed_behavior(output, cell, common, selected):
    commands = []
    root = cell_path(output, cell)
    for path in sorted(root.glob("turn-*/events.jsonl")):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            item = event.get("params", {}).get("item", {})
            if (
                event.get("method") == "item/completed"
                and item.get("type") == "commandExecution"
            ):
                commands.append(
                    {"command": item.get("command"), "exit_code": item.get("exitCode")}
                )
    capture_path = root / "acceptance/acceptance.json"
    changed = (
        read(capture_path).get("capture", {}).get("changed_files", [])
        if capture_path.exists()
        else None
    )
    prefix = (
        read(Path(common["checkpoint"]) / "checkpoint.json")
        if common.get("checkpoint")
        else None
    )
    visible = (
        [
            e.get("params", {}).get("item", {}).get("aggregatedOutput", "")
            for e in prefix.get("visible_events", [])
            if e.get("method") == "item/completed"
        ]
        if prefix
        else []
    )
    visibility = []
    for unit in selected.get("pack", {}).get("units", []):
        text = unit.get("statement", "")
        visibility.append(
            {
                "unit_id": unit["unit_id"],
                "role": unit.get("claim_role"),
                "visibility": "visibility_unknown"
                if not any(visible)
                else "already_visible_in_prefix"
                if text and any(text in value for value in visible)
                else "not_observed_in_visible_prefix",
                "criterion": "exact source excerpt in recorded visible prefix; not a model-knowledge claim",
            }
        )
    return {
        "completed_commands": commands,
        "changed_files": changed,
        "source_visibility": visibility,
    }


def report(plan, output):
    rows = read(output / "functional-results.json")["rows"]
    groups, contrasts = summarize_rows(plan["tasks"], rows)
    costs, cases = [], []
    for row in rows:
        root = output / "selection" / row["task_id"]
        common = read(root / "common.json")
        selected = (
            read(root / f"R-r{row['repeat']}.json")
            if row["arm"] == "R"
            else common.get(row["arm"], {})
        )
        execution = read(cell_path(output, row) / "execution.json")
        charge, remaining = selected.get("cost"), common.get("prefix_remaining_seconds")
        spent = execution.get("tail_seconds")
        valid = (
            charge is not None
            and remaining is not None
            and isinstance(spent, (int, float))
            and execution.get("policy_initialization_seconds") == charge
            and execution.get("initial_remaining") == remaining
        )
        budget_status = (
            ("VALID" if spent <= remaining else "OVER_BUDGET") if valid else "UNKNOWN"
        )
        costs.append(
            {
                **{k: row[k] for k in ("task_id", "arm", "repeat")},
                "prefix_seconds": common.get("prefix_seconds"),
                "common_preparation_seconds": common.get("M", {}).get("cost")
                if row["arm"] != "N"
                else 0,
                "preparation_seconds": charge,
                "R_extra_seconds": selected.get("extra_cost"),
                "R_acquisition_seconds": selected.get("acquisition_seconds"),
                "R_acquisition_started": selected.get("acquisition_started", False),
                "same_as_mmr": selected.get("same_as_mmr"),
                "fallback_reason": selected.get("fallback_reason"),
                "tail_budget_seconds": max(0, remaining - charge)
                if remaining is not None and charge is not None
                else None,
                "actual_including_preparation_seconds": spent,
                "tokens": selected.get("pack", {}).get("tokens", 0),
                "units": len(selected.get("pack", {}).get("units", [])),
                "injection_observed": execution.get("model_input_observed")
                if selected.get("message")
                else None,
                "budget_status": budget_status,
                "protocol_deviation": "INJECTION_NOT_OBSERVED"
                if selected.get("message") and not execution.get("model_input_observed")
                else None,
            }
        )
        cases.append(
            {
                **{k: row[k] for k in ("task_id", "arm", "repeat", "functional")},
                "actual_payload": selected.get("message"),
                "units": selected.get("pack", {}).get("units", []),
                "observed_behavior": observed_behavior(output, row, common, selected),
                "usage_claim": "Visible input/read/code evidence only; internal causal usage unknown",
            }
        )
    starts = sum((cell_path(output, r) / "started.json").exists() for r in rows)
    terminal = {
        "study": STUDY,
        "integration": "COMPLETE"
        if (output / "preflight/result.json").exists()
        and starts == len(matrix(plan["tasks"]))
        and starts > 0
        and all(
            (output / "selection" / t["instance_id"] / "common.json").exists()
            for t in plan["tasks"]
        )
        else "PARTIAL",
        "R_identity": "PR55_QUERY_AND_EXISTING_PACK_SELECTION",
        "algorithm_change": "NONE_EXCEPT_DECLARED_INTEGRATION_FIXES",
        "protocol": "MATCHED_PUBLIC_PREFIX_OWN_COST_600S_WARM_INDEX",
        "tasks_preregistered": len(plan["tasks"]),
        "public_prefixes_completed": sum(
            read(output / "prefixes" / t["instance_id"] / "execution.json")["status"]
            == "PREFIX_SAVED"
            for t in plan["tasks"]
        ),
        "repair_tails_planned": len(matrix(plan["tasks"])),
        "repair_tails_started": starts,
        "repair_tails_budget_protocol_valid": sum(
            c["budget_status"] == "VALID" and c["protocol_deviation"] is None
            for c in costs
        ),
        "R_acquisitions_started": sum(c["R_acquisition_started"] for c in costs),
        "R_non_MMR_payloads": sum(
            c["arm"] == "R" and c["same_as_mmr"] is False for c in costs
        ),
        "R_fallbacks": sum(
            c["arm"] == "R" and bool(c["fallback_reason"]) for c in costs
        ),
        "functional_comparison": "COMPLETE"
        if rows and all(r["functional"] != "UNKNOWN" for r in rows)
        else "PARTIAL",
        "causal_attribution": "MATCHED_PREFIX_OBSERVATION_NOT_EXACT_INDIVIDUAL_CAUSAL_EFFECT",
        "new_training": "NONE",
        "default_policy": "UNCHANGED",
        "historical_results": "PRESERVED",
        "publication": "DRAFT_PR_ONLY",
        "next_automatic_experiment": "NONE",
    }
    for arm in ("M", "N"):
        contrast = contrasts["R_minus_" + arm]
        delta = contrast["task_mean_difference"]
        protocol_valid = all(
            c["budget_status"] == "VALID" and c["protocol_deviation"] is None
            for c in costs
            if c["arm"] in {"R", arm}
        )
        contrast["protocol_valid_for_gain_claim"] = protocol_valid
        terminal["functional_gain_over_" + arm] = (
            "UNKNOWN"
            if delta is None or not protocol_valid
            else "OBSERVED_WITH_LIMITATIONS"
            if delta > 0
            else "NOT_ESTABLISHED"
        )
    value = {
        "functional_table": groups,
        "contrasts": contrasts,
        "cost_table": costs,
        "knowledge_behavior_table": cases,
        "terminal": terminal,
        "replay_model_calls": 0,
        "replay_acceptance_calls": 0,
    }
    atomic_json(output / "report.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "prepare",
            "qualify",
            "configure",
            "preflight",
            "freeze",
            "prefix",
            "compose",
            "run",
            "accept",
            "report",
            "replay",
        ],
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", type=Path)
    parser.add_argument("--overlays", type=Path)
    parser.add_argument("--encoder", type=Path)
    parser.add_argument(
        "--skills",
        type=Path,
        default=Path("configs/conditional-applicability-v1/skills"),
    )
    args = parser.parse_args()
    if args.action == "prepare":
        roster = prepare(args.repo, args.assets, args.output)
        print(json.dumps({"candidates": len(roster["finite_queue"]), "model_calls": 0}))
    elif args.action == "qualify":
        qualify(
            args.tasks,
            args.overlays,
            args.output,
            read(args.output / "task_roster.json"),
        )
    elif args.action == "configure":
        configure(args.repo, args.assets, args.output, args.encoder)
    elif args.action == "preflight":
        print(json.dumps(preflight(args.repo, args.assets, args.output)))
    elif args.action == "freeze":
        freeze(args.repo, args.output, args.skills, args.encoder)
    else:
        plan = read(args.repo / "configs" / STUDY / "plan.json")
        if args.action in {"report", "replay"}:
            print(json.dumps(report(plan, args.output)["terminal"]))
            return
        verify(plan, args.repo, args.output, args.skills, args.encoder)
        if args.action in {"prefix", "run"}:
            run_study(
                plan,
                args.output / "tasks",
                args.skills,
                args.output,
                "prefix" if args.action == "prefix" else "tails",
            )
        elif args.action == "compose":
            for task in plan["tasks"]:
                compose_common(task, args.output, args.encoder)
                for repeat in (1, 2):
                    compose_r(
                        task,
                        repeat,
                        args.output,
                        args.encoder,
                        read(args.output / "cost-model.json"),
                    )
        elif args.action == "accept":
            accept(plan, args.output)


if __name__ == "__main__":
    main()
