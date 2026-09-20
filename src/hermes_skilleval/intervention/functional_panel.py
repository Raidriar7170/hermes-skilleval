"""Outcome-blind checkpoint selection and prospective common-state decisions."""

from pathlib import Path

from .functional_collection import bind_checkpoint, digest
from .functional_policy import FunctionalController
from .state import State
from .study import read


def verify_panel_lock(lock):
    if (
        digest({k: v for k, v in lock.items() if k != "lock_sha256"})
        != lock["lock_sha256"]
    ):
        raise ValueError("prospective panel lock changed")


def verify_panel_rows(rows, panel_locks):
    locks = dict(panel_locks)
    for row in rows:
        lock = locks[row["task_id"]]
        if (
            row["panel_lock_sha256"] != lock["lock_sha256"]
            or row["binding_sha256"] != lock["binding"]["binding_sha256"]
            or row["state"] != lock["state"]
            or row["candidate_payloads"] != lock["binding"]["candidates"]
        ):
            raise ValueError("mechanism row differs from prospective panel lock")


def verified_delay_plan(panel_locks, saved_rows):
    for _, lock in panel_locks:
        verify_panel_lock(lock)
    expected = delay_roster(panel_locks)
    if saved_rows is not None and saved_rows != expected:
        raise ValueError("delay roster differs from prospective panels")
    return expected, saved_rows is not None


def select_checkpoint(execution):
    """First actual E1, else E2, else E0; never consult verifier outcomes."""
    checkpoints = [
        (Path(p), read(Path(p) / "checkpoint.json"))
        for p in execution.get("checkpoints", [])
    ]
    for stage in ("E1", "E2", "E0"):
        for path, meta in checkpoints:
            if meta["state"]["stage"] == stage:
                return path
    return None


def immediate_action(candidates, gains):
    """Gain-only choice used to isolate representation from the waiting policy."""
    best = max(candidates, key=lambda k: gains[k])
    return best if gains[best] > 0 else "NO_INTERVENTION"


def lock_panel(checkpoint, payloads, predictors):
    """Save this result BEFORE any common-action hidden functional labels."""
    binding = bind_checkpoint(checkpoint, payloads)
    meta = read(Path(checkpoint) / "checkpoint.json")
    state = State(**meta["state"])
    candidates = meta["candidates"]
    methods = {}
    for method in ("H-full-v2", "H-task-fixedC-v2", "P1-v2"):
        gains, wait = predictors[method](state, candidates)
        decision = FunctionalController(method).decide(
            state.stage, candidates, gains, wait, has_future=state.stage != "E2"
        )
        if decision["action"] == "UNAVAILABLE":
            raise ValueError("METHOD_UNAVAILABLE in common-state freeze")
        methods[method] = {
            "gains": gains,
            "wait": wait,
            "immediate_gain_action": immediate_action(candidates, gains),
            "stopping_policy_decision": decision,
            "stopping_action_panel_identification": "NOT_IDENTIFIED_BY_IMMEDIATE_ACTION_PANEL"
            if decision["action"] == "WAIT"
            else "DIRECT_ACTION_OBSERVED_AFTER_COLLECTION",
        }
    full = methods["H-full-v2"]
    now_skill = max(candidates, key=lambda k: full["gains"][k])
    result = {
        "checkpoint": str(checkpoint),
        "binding": binding,
        "state": meta["state"],
        "methods": methods,
        "now_skill": now_skill,
        "representation_identifiable": state.stage != "E0",
        "delay_eligible": state.stage != "E2",
        "wait_sensitive": bool(
            state.stage != "E2"
            and 0 < full["gains"][now_skill] <= max(0.0, full["wait"])
        ),
        "action_roster": [
            {"repeat": r, "action": a}
            for r in (1, 2)
            for a in ("NO_INTERVENTION", *candidates, "GENERIC_REMINDER")
        ],
        "representation_contrast": "prelocked immediate gain actions on same C; full stopping policy WAIT is not relabeled as never-intervene",
        "sample_reuse": "NEVER and NOW reference these action/repeat IDs; no additional calls",
    }
    return {**result, "lock_sha256": digest(result)}


def delay_roster(panel_locks):
    """First four nonterminal panels in registered task order, no outcome input."""
    selected = [(tid, lock) for tid, lock in panel_locks if lock["delay_eligible"]][:4]
    return [
        {
            "task_id": tid,
            "panel_lock_sha256": lock["lock_sha256"],
            "repeat": r,
            "action": action,
            "fixed_skill": lock["now_skill"] if action == "DEFER_SAME-v2" else None,
        }
        for tid, lock in selected
        for r in (1, 2)
        for action in ("DEFER_SAME-v2", "WAIT_THEN_FULL-v2")
    ]
