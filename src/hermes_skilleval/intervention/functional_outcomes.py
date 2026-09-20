"""Versioned functional labels. Policy and cost never participate in supervision."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

UNKNOWN = None
REQUIRED_OBJECTIVE = {
    "research_target": "FUNCTIONAL_REPAIR_GAIN",
    "primary_outcome": "target_pass_and_no_new_protected_regression",
    "primary_contrast": "H_full_v2_minus_N0_v2",
    "label_inputs": ["valid_target_verdict", "valid_regression_verdict"],
    "forbidden_label_inputs": [
        "file_policy",
        "billing",
        "wall_time",
        "skill_count",
        "ci_status",
    ],
    "gain_target": "paired_delta_functional",
    "wait_target": "future_functional_gain_relative_to_no_further_intervention",
    "cost_in_gain_or_wait_training": False,
    "policy_in_gain_or_wait_training": False,
    "same_state_candidate_list_shared": True,
    "representation_ablation_retrieves_again": False,
    "final_selector_uses_future_or_judge_feedback": False,
    "max_external_interventions_per_trajectory": 1,
    "old_test_reuse_as_fresh_test": False,
    "primary_metric_may_be_replaced": False,
}


def load_objective(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    for key, expected in REQUIRED_OBJECTIVE.items():
        if type(value.get(key)) is not type(expected) or value[key] != expected:
            raise ValueError("objective drift: " + key)
    return {**value, "sha256": hashlib.sha256(raw).hexdigest()}


def verdict(check):
    if check.get("valid") is True and type(check.get("passed")) is bool:
        return int(check["passed"])
    return UNKNOWN


def outcomes(execution, checks, *, integrity):
    """Integrity is independently supplied, never inferred from file policy.

    A timeout may retain a verified complete candidate. Absent execution or
    unobserved injected input is not a valid paired intervention observation.
    """
    executable = execution.get("status") in ("COMPLETED", "TIMEOUT") and bool(
        execution.get("thread_id")
    )
    observed = (
        not execution.get("injected") or execution.get("model_input_observed") is True
    )
    valid = integrity == "VERIFIED" and executable and observed
    target = verdict(checks.get("target", {})) if valid else UNKNOWN
    regression = verdict(checks.get("regression", {})) if valid else UNKNOWN
    functional = (
        int(target == regression == 1)
        if target is not None and regression is not None
        else UNKNOWN
    )
    policy = verdict(checks.get("policy", {}))
    qualified = (
        UNKNOWN
        if functional is None or policy is None
        else int(functional == policy == 1)
    )
    return {
        "execution_status": execution.get("status", "UNKNOWN"),
        "verifier_integrity_status": integrity,
        "y_target": target,
        "y_regression": regression,
        "y_functional": functional,
        "file_policy_status": "UNKNOWN"
        if policy is None
        else "PASS"
        if policy
        else "FAIL",
        "file_policy_reason": checks.get("policy", {}).get("error"),
        "qualified_delivery": qualified,
    }


def paired_delta(baseline, intervention):
    a, b = baseline["y_functional"], intervention["y_functional"]
    return UNKNOWN if a is None or b is None else b - a


def transition(baseline, intervention):
    delta = paired_delta(baseline, intervention)
    if delta is None:
        return "unknown"
    if delta:
        return "functional_rescue" if delta > 0 else "functional_damage"
    return "tie_pass" if baseline["y_functional"] else "tie_fail"


def decompose(records_path, objective_path, output):
    """Historical train/dev diagnosis only; never opens old final records."""
    from .records import verify_public_artifacts

    objective = load_objective(objective_path)
    records_path, output = Path(records_path), Path(output)
    source = json.loads(records_path.read_text())
    if any(r.get("split") not in ("train", "dev") for r in source["rows"]):
        raise ValueError("G0 accepts train/dev records only")
    rows, identities = [], set()
    for row in source["rows"]:
        identity = (row["task_id"], row["state_id"], row["repeat"], row["action"])
        if identity in identities:
            raise ValueError("duplicate historical sample")
        identities.add(identity)
        verification = verify_public_artifacts(row, records_path.parent)
        checks_file = records_path.parent / row["evidence_path"] / "checks.json"
        if (
            checks_file.exists()
            and json.loads(checks_file.read_text()) != row["checks"]
        ):
            raise ValueError("historical row differs from captured checks")
        label = outcomes(row["execution"], row["checks"], integrity="VERIFIED")
        rows.append(
            {
                **{
                    k: row[k]
                    for k in (
                        "task_id",
                        "split",
                        "stage",
                        "state_id",
                        "repeat",
                        "action",
                        "candidates",
                        "evidence_path",
                    )
                },
                **label,
                "source_artifacts": verification,
                # Public v1 export does not contain a fork/source/scratch identity.
                "same_prefix_identity_available": False,
                "same_prefix_identity_note": "historical state_id pairing; private checkpoint identity not verified by G0",
            }
        )
    by_key = {(r["task_id"], r["state_id"], r["repeat"], r["action"]): r for r in rows}
    pairs = []
    for row in rows:
        if row["action"] == "NO_INTERVENTION":
            continue
        base = by_key.get(
            (row["task_id"], row["state_id"], row["repeat"], "NO_INTERVENTION")
        )
        label = transition(base, row) if base else "unknown"
        pairs.append(
            {
                **row,
                "transition": label,
                "delta_functional": paired_delta(base, row) if base else UNKNOWN,
                "baseline_evidence_path": base["evidence_path"] if base else None,
                "policy_only_transition": bool(
                    base
                    and label in ("tie_pass", "tie_fail")
                    and {base["file_policy_status"], row["file_policy_status"]}
                    == {"PASS", "FAIL"}
                ),
            }
        )
    counts = Counter(r["transition"] for r in pairs)
    report = {
        "purpose": "DERIVED_LEGACY_TRAIN_DEV_DIAGNOSTIC_ONLY",
        "objective_sha256": objective["sha256"],
        "source_sha256": hashlib.sha256(records_path.read_bytes()).hexdigest(),
        "planned_record_count": len(rows),
        "paired_action_count": len(pairs),
        "functional_counts": dict(Counter(str(r["y_functional"]) for r in rows)),
        "transitions": dict(counts),
        "policy_only_transitions": sum(r["policy_only_transition"] for r in pairs),
        "wait_sensitive_state_count": None,
        "wait_diagnostic_note": "UNAVAILABLE: collection export contains no saved gain/wait scores; no model inference performed",
        "new_agent_calls": 0,
        "old_records_modified": False,
        "training_reuse": False,
        "rows": rows,
        "pairs": pairs,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "legacy-decomposition.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    lines = [
        "# v1 train/dev functional diagnosis",
        "",
        "Derived historical diagnostics, not v2 training or new experimental evidence.",
        "",
        f"Records: {len(rows)}; pairs (including reminder): {len(pairs)}; transitions: {dict(counts)}.",
        f"Policy-only transitions: {report['policy_only_transitions']}.",
        "",
        "Public captured patch and JUnit artifacts checked; same-prefix identities not available in this export. Saved-score waiting diagnostic unavailable. No old final records read.",
        "",
        "| Task | Stage | Action | Rescue | Damage | Tie pass | Tie fail | Unknown | Policy only |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    groups = sorted({(r["task_id"], r["stage"], r["action"]) for r in pairs})
    for group in groups:
        subset = [r for r in pairs if (r["task_id"], r["stage"], r["action"]) == group]
        c = Counter(r["transition"] for r in subset)
        values = [
            c[k]
            for k in (
                "functional_rescue",
                "functional_damage",
                "tie_pass",
                "tie_fail",
                "unknown",
            )
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    *group,
                    *map(str, values),
                    str(sum(r["policy_only_transition"] for r in subset)),
                ]
            )
            + " |"
        )
    (output / "legacy-decomposition.md").write_text("\n".join(lines) + "\n")
    return {k: v for k, v in report.items() if k not in ("rows", "pairs")}
