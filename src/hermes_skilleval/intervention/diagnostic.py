"""Bounded development diagnosis; no learned controller and no synthetic results."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import xml.etree.ElementTree as ET

from .functional_outcomes import outcomes, transition
from .records import verify_artifacts
from .rollouts import GENERIC
from .session import Session, dump, inventory
from .state import is_test_command
from .study import check_once, read, run_once


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Discovered by independent request/checker review after sampling began.
# Frozen checkers and raw labels remain unchanged. These tests overconstrain
# error wording/type; wording-only failures cannot establish task difficulty.
AMBIGUOUS_ASSERTIONS = {
    "sqlite-utils-diagnostic-548a886": (
        "test_extract_bad_column_clean_error",
        "test_insert_invalid_pk_clean_error",
    ),
    "sqlite-utils-diagnostic-fcfccea": (
        "test_extract_strict_any_rejects_non_strict_lookup",
    ),
    "sqlite-utils-diagnostic-57192ef": ("test_transform_rename_complex_index_errors",),
}


def acceptance_audit(row, target_junit=None):
    """Conservative records-only validity overlay; never upgrade raw failures."""
    raw = row["y_functional"]
    result = {
        "raw_y_functional": raw,
        "interpretable_y_functional": raw,
        "status": "NO_KNOWN_ACCEPTANCE_AMBIGUITY",
        "failures": [],
    }
    names = AMBIGUOUS_ASSERTIONS.get(row["task_id"], ())
    if raw != 0 or not names:
        return result
    # A separately verified regression failure establishes real failure even
    # when one target assertion is ambiguous.
    if row.get("y_regression") == 0:
        return result
    path = (
        Path(target_junit)
        if target_junit is not None
        else Path(row["checks_root"]) / "target" / "junit.xml"
    )
    result["target_junit_sha256"] = sha(path)
    root = ET.parse(path).getroot()
    failed = [
        c
        for c in root.iter("testcase")
        if c.find("failure") is not None or c.find("error") is not None
    ]
    result["failures"] = [c.get("name", "") for c in failed]
    ambiguous = []
    for case in failed:
        name = case.get("name", "").split("[", 1)[0]
        if name not in names:
            continue
        text = " ".join(case.itertext())
        wording_only = "Regex pattern did not match" in text
        if row["task_id"].endswith("548a886"):
            wording_only = "assert result.output.startswith" in text
        if wording_only:
            ambiguous.append(case)
    if ambiguous and len(ambiguous) == len(failed):
        result.update(
            interpretable_y_functional=None,
            status="UNKNOWN_ACCEPTANCE_CONTRACT_AMBIGUITY",
        )
    return result


# Public mechanism words frozen before native probes. Infrastructure-only errors
# cannot trigger E1. Selection never receives a terminal checker result.
TERMS = {
    "548a886": ("invalidcolumn", "primary key", "extract", "clean_error"),
    "fcfccea": ("any", "strict", "extract"),
    "80437fd": ("range", "column_identifier", "ignore_unknown"),
    "19810a3": ("bom", "utf", "in2csv", "csvformat"),
    "2b52b5e": ("autoincrement", "sequence", "transform"),
    "57192ef": ("index", "rename", "transform"),
    "29ca9d2": ("foreign", "mixed"),
    "8e015d0": ("primary", "compound", "foreign", "declaration"),
}


def visible_opportunity(state, seen, events, done, terms):
    if not seen:
        return "E0"
    # First completed boundary with a functional-looking public contradiction.
    # Keep its evidence even when E1 and delivery coincide.
    if "E1" not in seen and "E2" not in seen:
        for event in events:
            item = event.get("params", {}).get("item", {})
            if (
                event.get("method") != "item/completed"
                or item.get("type") != "commandExecution"
            ):
                continue
            text = (item.get("aggregatedOutput") or "").lower()
            command = item.get("command", "").lower()
            functional = any(
                x in text
                for x in (
                    "assertionerror",
                    "integrityerror",
                    "transformerror",
                    "invalidcolumns",
                    "columnidentifiererror",
                )
            )
            # A pytest assertion summary is also observable; missing modules,
            # collection-only errors and shell failures alone do not qualify.
            functional = functional or (
                " failed" in text and "assert " in text and is_test_command(command)
            )
            if (
                item.get("exitCode") not in (None, 0)
                and functional
                and any(t in text + command for t in terms)
            ):
                return "E1"
    if done and "E2" not in seen:
        return "E2"
    return None


def select_checkpoint(execution, minimum=90):
    available = [Path(p) for p in execution.get("checkpoints", [])]
    for stage in ("E1", "E2"):
        for p in available:
            meta = read(p / "checkpoint.json")
            if (
                meta["state"]["stage"] == stage
                and meta["remaining_seconds"] >= minimum
                and meta.get("thread_id")
                and meta.get("last_turn_id")
            ):
                return str(p)
    return None


def select_panel(tasks, native_rows, minimum=90):
    selected, control = [], None
    for task in tasks:
        rows = sorted(
            [r for r in native_rows if r["task_id"] == task["task_id"]],
            key=lambda r: r["repeat"],
        )
        if len(rows) != 2:
            continue
        cp = next(
            (c for r in rows if (c := select_checkpoint(r["execution"], minimum))), None
        )
        if cp is None:
            continue
        if any(r["y_functional"] == 0 for r in rows) and len(selected) < 3:
            selected.append(
                {
                    "task_id": task["task_id"],
                    "stratum": "native_failure",
                    "checkpoint": cp,
                }
            )
        elif all(r["y_functional"] == 1 for r in rows) and control is None:
            control = {
                "task_id": task["task_id"],
                "stratum": "native_success_control",
                "checkpoint": cp,
            }
    # Unknowns do not establish an all-pass stopping condition.
    if (
        native_rows
        and len(native_rows) == 2 * len(tasks)
        and all(r["y_functional"] == 1 for r in native_rows)
    ):
        return {"status": "NO_NATIVE_FAILURE_OBSERVED", "states": []}
    if control is not None:
        selected.append(control)
    return {"status": "PANEL_SELECTED", "states": selected}


def counts(values, planned):
    if len(values) > planned:
        raise ValueError("more results than planned")
    passed, failed = values.count(1), values.count(0)
    unknown = planned - passed - failed
    return {
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "planned": planned,
        "rate_bounds": [passed / planned, (passed + unknown) / planned]
        if planned
        else None,
    }


def compare_state(rows, repeats=2, has_skill=True):
    lookup = {}
    for row in rows:
        key = row["arm"], row["repeat"]
        if key in lookup:
            raise ValueError("duplicate same-state cell")
        lookup[key] = row
    if not has_skill and any(r["arm"] == "K" for r in rows):
        raise ValueError("K execution without supported skill")
    result = {
        "arms": {
            a: counts(
                [r["y_functional"] for r in rows if r["arm"] == a],
                repeats if a != "K" or has_skill else 0,
            )
            for a in ("N", "G", "K")
        }
    }
    if not has_skill:
        result["arms"]["K"]["status"] = "NOT_RUN_NO_SUPPORTED_EXISTING_SKILL"
        result["K_minus_N"] = result["K_minus_G"] = {"status": "NOT_TESTED"}
        return result
    for base in ("N", "G"):
        pairs = []
        for repeat in range(1, repeats + 1):
            a, b = lookup.get((base, repeat)), lookup.get(("K", repeat))
            pairs.append(transition(a, b) if a and b else "unknown")
        x, y = result["arms"]["K"]["rate_bounds"], result["arms"][base]["rate_bounds"]
        result["K_minus_" + base] = {
            "transitions": pairs,
            "difference_bounds": [x[0] - y[1], x[1] - y[0]],
            "observed_difference": x[0] - y[0]
            if x[0] == x[1] and y[0] == y[1]
            else None,
        }
    return result


def inventory_digest(root):
    return hashlib.sha256(
        json.dumps(inventory(root), sort_keys=True).encode()
    ).hexdigest()


def verify_plan(plan, tasks, skills, payloads):
    if (
        plan["model"],
        plan["effort"],
        plan["codex_version"],
        plan["total_seconds"],
    ) != ("gpt-5.6-sol", "medium", "0.154.0", 600):
        raise ValueError("inherited executor contract drift")
    if plan["status"] != "FROZEN":
        raise ValueError("plan not frozen")
    for key, root in [("skills", skills), ("payloads", payloads)]:
        if inventory_digest(root) != plan["assets"][key]:
            raise ValueError("frozen asset drift: " + key)
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    if image_id != plan["image_id"]:
        raise ValueError("executor image drift")
    for row in plan["tasks"]:
        task = tasks / row["task_id"]
        for key in ("base", "trusted", "reference", "public-docs"):
            if inventory_digest(task / key) != row["files"][key]:
                raise ValueError("task asset drift: " + row["task_id"] + "/" + key)
        if (
            sha(task / "request.txt") != row["request_sha256"]
            or sha(task / "task.json") != row["task_sha256"]
        ):
            raise ValueError("task contract drift")


def label(task, run, execution):
    checks_root = run.parent / (run.name + "-checks")
    checks = check_once(task, run, checks_root, execution)
    row = dict(
        run=str(run),
        checks_root=str(checks_root),
        execution=execution,
        checks=checks,
        quality=None,
    )
    verification = verify_artifacts(row)
    row.update(
        outcomes(execution, checks, integrity=verification["status"]),
        verification=verification,
    )
    return row


def home_auth(output):
    home = output / "session-home"
    home.mkdir(mode=0o700, exist_ok=True)
    auth = home / "auth.json"
    shutil.copyfile(Path.home() / ".codex/auth.json", auth)
    auth.chmod(0o600)
    return home, auth


def preflight(tasks, output, skills, plan):
    """Official model discovery only; no turn/start and no research sample."""
    output.mkdir(parents=True, exist_ok=False)
    home, auth = home_auth(output)
    task = tasks / plan["tasks"][0]["task_id"]
    try:
        with Session(
            task / "base", output / "scratch", home, skills, output / "server"
        ) as session:
            result = session.rpc("model/list", {"includeHidden": True})
            rows = result.get("data", [])
            models = [r.get("model") or r.get("id") for r in rows]
            value = {
                "model": plan["model"],
                "advertised": plan["model"] in models,
                "models": models,
                "research_executions": 0,
                "model_sampling_calls": 0,
            }
            dump(output / "preflight.json", value)
            return value
    finally:
        auth.unlink(missing_ok=True)


def probe(plan_path, tasks, output, skills, payloads):
    plan = read(plan_path)
    verify_plan(plan, tasks, skills, payloads)
    output.mkdir(parents=True, exist_ok=True)
    identity = {"plan_sha256": sha(plan_path)}
    if (output / "identity.json").exists() and read(
        output / "identity.json"
    ) != identity:
        raise ValueError("resume plan changed")
    dump(output / "identity.json", identity)
    home, auth = home_auth(output)
    rows = []
    try:
        for info in plan["tasks"]:
            task = tasks / info["task_id"]
            terms = TERMS[info["fix_commit"][:7]]
            for repeat in (1, 2):
                run = output / info["task_id"] / f"r{repeat}"
                print(
                    json.dumps({"starting": info["task_id"], "repeat": repeat}),
                    flush=True,
                )
                previously_attempted = run.exists()
                execution = run_once(
                    task,
                    run,
                    home,
                    skills,
                    total=plan["total_seconds"],
                    public_docs=task / "public-docs",
                    checkpoint_selector=lambda s, seen, e, done: visible_opportunity(
                        s, seen, e, done, terms
                    ),
                )
                row = label(task, run, execution)
                row.update(
                    task_id=info["task_id"],
                    family=info["mechanism"],
                    split="dev",
                    repeat=repeat,
                    arm="N",
                    action="NO_INTERVENTION",
                    phase="native",
                )
                rows.append(row)
                dump(
                    output / "records.json",
                    {
                        "identity": identity,
                        "planned": len(plan["tasks"]) * 2,
                        "rows": rows,
                    },
                )
                print(
                    json.dumps(
                        {
                            "completed": info["task_id"],
                            "repeat": repeat,
                            "status": execution["status"],
                            "y_functional": row["y_functional"],
                        }
                    ),
                    flush=True,
                )
                if not previously_attempted and execution["status"] not in (
                    "COMPLETED",
                    "TIMEOUT",
                ):
                    dump(
                        output / "blocked.json",
                        {
                            "reason": execution["status"],
                            "run": str(run),
                            "remaining_samples": "NOT_STARTED",
                        },
                    )
                    return {"status": "PARTIAL", "rows": len(rows)}
    finally:
        auth.unlink(missing_ok=True)
    panel = select_panel(plan["tasks"], rows, plan["min_remaining_seconds"])
    dump(output / "panel.json", panel)
    return {"status": "COMPLETE", "rows": len(rows), "panel": panel}


def freeze_roster(selections, seed):
    cells = []
    for selected in selections:
        arms = ["N", "G"] + (["K"] if selected.get("skill_id") else [])
        block = [
            {"task_id": selected["task_id"], "arm": a, "repeat": r}
            for r in (1, 2)
            for a in arms
        ]
        random.Random(str(seed) + ":" + selected["task_id"]).shuffle(block)
        cells.extend(block)
    return cells


def freeze_selection(plan_path, native, choices_path, output, payloads):
    """Choices come from a separately preserved public-only analysis input."""
    plan = read(plan_path)
    if read(native / "identity.json") != {"plan_sha256": sha(plan_path)}:
        raise ValueError("native plan identity mismatch")
    panel = read(native / "panel.json")
    audit_path = native / "acceptance-audit.json"
    if panel.get("acceptance_audit_sha256") != sha(audit_path):
        raise ValueError("panel lacks current acceptance validity audit")
    if read(audit_path)["records_sha256"] != sha(native / "records.json"):
        raise ValueError("native records changed after acceptance audit")
    if not {e["task_id"] for e in panel["states"]} <= {
        t["task_id"] for t in plan["tasks"]
    }:
        raise ValueError("panel task outside plan")
    choices = read(choices_path)
    if output.exists():
        raise ValueError("selection already frozen")
    states = []
    manifest = read(payloads / "manifest.json")
    valid = {r["skill_id"]: r for r in manifest["skills"]}
    if set(choices) != {r["task_id"] for r in panel["states"]}:
        raise ValueError("choices do not match preregistered ordered panel")
    for entry in panel["states"]:
        choice = choices[entry["task_id"]]
        skill = choice.get("skill_id")
        payload = None
        if skill is not None:
            if skill not in valid:
                raise ValueError("not an existing skill")
            payload = (payloads / valid[skill]["path"]).read_text()
            if (
                hashlib.sha256(payload.encode()).hexdigest()
                != valid[skill]["payload_sha256"]
            ):
                raise ValueError("payload changed")
            passage = choice.get("relevant_actual_payload_passage")
            if not passage or passage not in payload:
                raise ValueError("selection passage absent from actual payload")
        elif choice.get("status") != "NO_SUPPORTED_EXISTING_SKILL":
            raise ValueError("missing no-skill reason")
        cp = Path(entry["checkpoint"])
        meta = read(cp / "checkpoint.json")
        if meta["remaining_seconds"] < plan["min_remaining_seconds"]:
            raise ValueError("insufficient original remaining budget")
        states.append(
            {
                **entry,
                "skill_id": skill,
                "choice": choice,
                "checkpoint_sha256": sha(cp / "checkpoint.json"),
                "payload": payload,
                "payload_tokens": valid[skill]["tokens"] if skill else 0,
            }
        )
    result = {
        "status": "FROZEN",
        "plan_sha256": sha(plan_path),
        "choices_sha256": sha(choices_path),
        "generic": GENERIC,
        "generic_tokens": manifest["generic_tokens"],
        "states": states,
        "roster": freeze_roster(states, plan["order_seed"]),
    }
    dump(output, result)
    return {"states": len(states), "tails": len(result["roster"])}


def tails(plan_path, tasks, output, skills, payloads, native, selection_path):
    plan = read(plan_path)
    verify_plan(plan, tasks, skills, payloads)
    if read(native / "identity.json") != {"plan_sha256": sha(plan_path)}:
        raise ValueError("native plan identity mismatch")
    selection = read(selection_path)
    if selection["status"] != "FROZEN" or selection["plan_sha256"] != sha(plan_path):
        raise ValueError("selection identity mismatch")
    if selection["roster"] != freeze_roster(selection["states"], plan["order_seed"]):
        raise ValueError("tail roster drift")
    output.mkdir(parents=True, exist_ok=True)
    identity = {"plan_sha256": sha(plan_path), "selection_sha256": sha(selection_path)}
    if (output / "identity.json").exists() and read(
        output / "identity.json"
    ) != identity:
        raise ValueError("tail resume identity changed")
    dump(output / "identity.json", identity)
    home, auth = home_auth(
        native
    )  # official parent history, never private-format edits
    rows = []
    try:
        for selected in selection["states"]:
            tid = selected["task_id"]
            task = tasks / tid
            cp = Path(selected["checkpoint"])
            if sha(cp / "checkpoint.json") != selected["checkpoint_sha256"]:
                raise ValueError("checkpoint metadata drift")
            meta = read(cp / "checkpoint.json")
            for scope in ("source", "scratch"):
                if inventory(cp / scope) != meta["files"][scope]:
                    raise ValueError("checkpoint filesystem drift")
            raw = []
            for cell in (r for r in selection["roster"] if r["task_id"] == tid):
                arm = cell["arm"]
                run = output / tid / (arm + "-r" + str(cell["repeat"]))
                payload = (
                    None
                    if arm == "N"
                    else selection["generic"]
                    if arm == "G"
                    else selected["payload"]
                )
                tokens = (
                    0
                    if arm == "N"
                    else selection["generic_tokens"]
                    if arm == "G"
                    else selected["payload_tokens"]
                )
                print(json.dumps({"starting_tail": cell}), flush=True)
                existed = run.exists()
                execution = run_once(
                    task,
                    run,
                    home,
                    skills,
                    from_checkpoint=cp,
                    payload=payload,
                    payload_tokens=tokens,
                    public_docs=task / "public-docs",
                    checkpoint_selector=lambda s, seen, e, done: visible_opportunity(
                        s,
                        seen,
                        e,
                        done,
                        TERMS[
                            next(
                                r["fix_commit"][:7]
                                for r in plan["tasks"]
                                if r["task_id"] == tid
                            )
                        ],
                    ),
                )
                # Bind actual restored state to the selected common state, even
                # for UNKNOWN. Never substitute the screening native result.
                if (run / "started.json").exists():
                    start = read(run / "started.json")
                    if (
                        start["initial_files"] != meta["files"]["source"]
                        or start["initial_remaining"] != meta["remaining_seconds"]
                    ):
                        raise ValueError("tail start state mismatch")
                raw.append((cell, run, execution))
                if not existed and execution["status"] not in ("COMPLETED", "TIMEOUT"):
                    dump(
                        output / "blocked.json",
                        {
                            "cell": cell,
                            "reason": execution["status"],
                            "release": "state labels withheld until all registered tails finish",
                        },
                    )
                    return {"status": "PARTIAL", "released": len(rows)}
            # Only now expose target/protected-regression outcomes for this state.
            for cell, run, execution in raw:
                row = label(task, run, execution)
                row.update(
                    **cell,
                    phase="tail",
                    state_id=tid + ":" + meta["state"]["stage"],
                    stratum=selected["stratum"],
                    family=next(
                        r["mechanism"] for r in plan["tasks"] if r["task_id"] == tid
                    ),
                    split="dev",
                    action="NO_INTERVENTION"
                    if cell["arm"] == "N"
                    else "GENERIC_REMINDER"
                    if cell["arm"] == "G"
                    else selected["skill_id"],
                )
                rows.append(row)
            dump(
                output / "records.json",
                {
                    "identity": identity,
                    "planned": len(selection["roster"]),
                    "rows": rows,
                },
            )
    finally:
        auth.unlink(missing_ok=True)
    return {"status": "COMPLETE", "rows": len(rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["preflight", "probe", "freeze-selection", "tails"]
    )
    for name in ("plan", "tasks", "output", "skills", "payloads"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--native", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--choices", type=Path)
    a = parser.parse_args()
    if a.command == "preflight":
        result = preflight(a.tasks, a.output, a.skills, read(a.plan))
    elif a.command == "probe":
        result = probe(a.plan, a.tasks, a.output, a.skills, a.payloads)
    elif a.command == "freeze-selection":
        result = freeze_selection(a.plan, a.native, a.choices, a.output, a.payloads)
    else:
        result = tails(
            a.plan, a.tasks, a.output, a.skills, a.payloads, a.native, a.selection
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
