from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermes_skilleval.external.skillrouter import SkillRouterAdapter
from hermes_skilleval.external.skillrouter_matrix import (
    PLAN_SCHEMA as EXTERNAL_PLAN_SCHEMA,
    REPORT_SCHEMA as EXTERNAL_REPORT_SCHEMA,
    _validate_frozen_plan as _validate_external_plan,
    _verify_adapter_provenance as _verify_external_adapter_provenance,
    _verify_frozen_predictions,
)
from hermes_skilleval.live_agent_skillsbench import (
    PLAN_SCHEMA as LIVE_PLAN_SCHEMA,
    REPORT_SCHEMA as LIVE_REPORT_SCHEMA,
    _verify_derived_fields as _verify_live_derived_fields,
    _verify_plan_digest as _verify_live_plan_digest,
    _verify_plan_inputs as _verify_live_plan_inputs,
)
from hermes_skilleval.release_manifest import sha256_file


REPORT_SCHEMA = "v0.3.evidence-decision-report.v1"
ARTIFACT_TYPE = "v0.3-evidence-validity-release-gate"
STAGE2_FROZEN_PLAN_SCHEMA = "v0.3.stage2-pilot-plan-freeze.v1"
STAGE2_REAL_CODEX_EXECUTION_SCHEMA = "v0.3.stage2-real-codex-12-run-execution.v1"
VALID_EVIDENCE = "VALID_EVIDENCE"
INVALID_EVIDENCE = "INVALID_EVIDENCE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
KEEP_BASELINE = "KEEP_BASELINE"
UNAVAILABLE = "UNAVAILABLE"
PASS = "PASS"
FAIL = "FAIL"
REVIEW = "REVIEW"
PRESENT = "PRESENT"
BLOCKING = "blocking"
REVIEW_SEVERITY = "review"
INFO = "info"
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._-]+|api[_-]?key\s*=|password\s*=)",
    re.IGNORECASE,
)


def write_evidence_decision_report(
    *,
    output_path: Path | str,
    markdown_output_path: Path | str | None = None,
    external_plan_path: Path | str | None = None,
    external_report_path: Path | str | None = None,
    live_plan_path: Path | str | None = None,
    live_report_path: Path | str | None = None,
) -> dict[str, Any]:
    report = build_evidence_decision_report(
        external_plan_path=external_plan_path,
        external_report_path=external_report_path,
        live_plan_path=live_plan_path,
        live_report_path=live_report_path,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if markdown_output_path is not None:
        markdown = Path(markdown_output_path)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_evidence_markdown(report), encoding="utf-8")
    return report


def build_evidence_decision_report(
    *,
    external_plan_path: Path | str | None = None,
    external_report_path: Path | str | None = None,
    live_plan_path: Path | str | None = None,
    live_report_path: Path | str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    field_markers: dict[str, dict[str, Any]] = {}
    inputs: dict[str, Any] = {}

    external = _evaluate_external(
        external_plan_path=external_plan_path,
        external_report_path=external_report_path,
        checks=checks,
        field_markers=field_markers,
        inputs=inputs,
    )
    live = _evaluate_live_agent(
        live_plan_path=live_plan_path,
        live_report_path=live_report_path,
        checks=checks,
        field_markers=field_markers,
        inputs=inputs,
    )

    validity_status = _validity_status(checks)
    promotion = _promotion_gate(validity_status, external)
    return {
        "schema_version": REPORT_SCHEMA,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "inputs": inputs,
        "field_markers": field_markers,
        "benchmark_validity_gate": {
            "status": validity_status,
            "checks": checks,
        },
        "router_promotion_gate": promotion,
        "external_routing": external,
        "live_agent": live,
        "claim_boundaries": {
            "benchmark_validity_gate_statuses": [
                VALID_EVIDENCE,
                INVALID_EVIDENCE,
                REVIEW_REQUIRED,
            ],
            "unavailable_is_field_level_only": True,
            "promotion_requires_valid_evidence": True,
            "default_router_promotion_decision": KEEP_BASELINE,
            "no_new_model_runs": True,
            "no_training_or_threshold_tuning": True,
            "deterministic_verifier_is_live_agent_success_source": True,
        },
    }


def render_evidence_markdown(report: dict[str, Any]) -> str:
    checks = report["benchmark_validity_gate"]["checks"]
    failing = [check for check in checks if check["status"] == FAIL]
    review = [check for check in checks if check["status"] in {REVIEW, UNAVAILABLE}]
    lines = [
        "# Hermes SkillEval v0.3 Evidence Gate",
        "",
        f"- Benchmark Validity Gate: {report['benchmark_validity_gate']['status']}",
        f"- Router Promotion Gate: {report['router_promotion_gate']['decision']}",
        f"- Invalid evidence blocks promotion: {report['router_promotion_gate']['blocked_by_validity']}",
        f"- Blocking failures: {len(failing)}",
        f"- Review or unavailable fields: {len(review)}",
        "",
        "## Field Markers",
    ]
    for field, marker in sorted(report["field_markers"].items()):
        reason = f" - {marker['reason']}" if marker.get("reason") else ""
        lines.append(f"- {field}: {marker['status']}{reason}")
    lines.extend(["", "## Checks"])
    for check in checks:
        lines.append(f"- {check['status']} {check['id']}: {check['summary']}")
    lines.append("")
    return "\n".join(lines)


def _evaluate_external(
    *,
    external_plan_path: Path | str | None,
    external_report_path: Path | str | None,
    checks: list[dict[str, Any]],
    field_markers: dict[str, dict[str, Any]],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    if external_plan_path is None and external_report_path is None:
        field_markers["external_routing"] = {
            "status": UNAVAILABLE,
            "reason": "external routing plan/report paths were not provided",
        }
        _check(
            checks,
            "external.available",
            UNAVAILABLE,
            REVIEW_SEVERITY,
            "external routing evidence was not provided",
        )
        return {"status": UNAVAILABLE, "reason": field_markers["external_routing"]["reason"]}
    if external_plan_path is None or external_report_path is None:
        field_markers["external_routing"] = {
            "status": UNAVAILABLE,
            "reason": "both external plan and report paths are required",
        }
        _check(
            checks,
            "external.available",
            FAIL,
            BLOCKING,
            "external routing evidence is incomplete",
        )
        return {"status": UNAVAILABLE, "reason": field_markers["external_routing"]["reason"]}

    plan_path = Path(external_plan_path)
    report_path = Path(external_report_path)
    inputs["external_plan"] = _input_record(plan_path)
    inputs["external_report"] = _input_record(report_path)
    field_markers["external_routing"] = {"status": PRESENT}
    plan = _read_json_for_gate(checks, "external.plan_load", plan_path)
    report = _read_json_for_gate(checks, "external.report_load", report_path)

    _schema_check(checks, "external.plan_schema", plan, EXTERNAL_PLAN_SCHEMA)
    _schema_check(checks, "external.report_schema", report, EXTERNAL_REPORT_SCHEMA)
    _call_check(
        checks,
        "external.frozen_plan",
        "external frozen plan is internally valid",
        lambda: _validate_external_plan(plan),
    )
    _call_check(
        checks,
        "external.input_hashes",
        "external frozen data and prediction hashes match the plan",
        lambda: _verify_external_inputs(plan),
    )
    _check_report_plan_path(
        checks,
        "external.report_plan_path",
        report.get("plan_path"),
        plan_path,
    )
    official = report.get("official") if isinstance(report, dict) else None
    diagnostics = report.get("hermes_diagnostics") if isinstance(report, dict) else None
    _check(
        checks,
        "external.official_metrics_present",
        PASS if isinstance(official, dict) and bool(official) else FAIL,
        BLOCKING,
        "official SkillRouter metrics are present"
        if isinstance(official, dict) and bool(official)
        else "official SkillRouter metrics are missing",
    )
    _check_external_report_completeness(checks, plan, report)
    _check(
        checks,
        "external.hermes_diagnostics_separate",
        PASS if isinstance(diagnostics, dict) else FAIL,
        BLOCKING,
        "Hermes diagnostics are present separately from official metrics"
        if isinstance(diagnostics, dict)
        else "Hermes diagnostics are missing",
    )
    paired = diagnostics.get("paired_bootstrap_ci", {}) if isinstance(diagnostics, dict) else {}
    return {
        "status": PRESENT,
        "run_id": report.get("run_id"),
        "official_metric_configs": sorted(official) if isinstance(official, dict) else [],
        "official_metrics": official if isinstance(official, dict) else {},
        "hermes_diagnostics_present": isinstance(diagnostics, dict),
        "paired_bootstrap_keys": sorted(paired) if isinstance(paired, dict) else [],
        "negative_hit_rate": {
            "status": UNAVAILABLE,
            "reason": "explicit negative labels are not present for SkillRouter",
        },
        "evaluated_router_configs": _external_router_configs(plan),
    }


def _evaluate_live_agent(
    *,
    live_plan_path: Path | str | None,
    live_report_path: Path | str | None,
    checks: list[dict[str, Any]],
    field_markers: dict[str, dict[str, Any]],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    if live_plan_path is None and live_report_path is None:
        field_markers["live_agent"] = {
            "status": UNAVAILABLE,
            "reason": "live-agent plan/report paths were not provided",
        }
        _check(
            checks,
            "live_agent.available",
            UNAVAILABLE,
            REVIEW_SEVERITY,
            "live-agent evidence was not provided",
        )
        return {"status": UNAVAILABLE, "reason": field_markers["live_agent"]["reason"]}
    if live_plan_path is None or live_report_path is None:
        field_markers["live_agent"] = {
            "status": UNAVAILABLE,
            "reason": "both live-agent plan and report paths are required",
        }
        _check(
            checks,
            "live_agent.available",
            FAIL,
            BLOCKING,
            "live-agent evidence is incomplete",
        )
        return {"status": UNAVAILABLE, "reason": field_markers["live_agent"]["reason"]}

    plan_path = Path(live_plan_path)
    report_path = Path(live_report_path)
    inputs["live_plan"] = _input_record(plan_path)
    digest_path = plan_path.with_name(f"{plan_path.name}.sha256")
    if digest_path.exists():
        inputs["live_plan_digest"] = _input_record(digest_path)
    inputs["live_report"] = _input_record(report_path)
    field_markers["live_agent"] = {"status": PRESENT}

    plan = _read_json_for_gate(checks, "live_agent.plan_load", plan_path)
    report = _read_json_for_gate(checks, "live_agent.report_load", report_path)
    if _is_stage2_real_codex_packet(plan, report):
        return _evaluate_stage2_real_codex_live_agent(
            plan_path=plan_path,
            report_path=report_path,
            plan=plan,
            report=report,
            checks=checks,
        )

    _call_check(
        checks,
        "live_agent.plan_digest",
        "SkillsBench plan digest matches its sidecar",
        lambda: _verify_live_plan_digest(plan_path),
    )
    _schema_check(checks, "live_agent.plan_schema", plan, LIVE_PLAN_SCHEMA)
    _schema_check(checks, "live_agent.report_schema", report, LIVE_REPORT_SCHEMA)
    _call_check(
        checks,
        "live_agent.input_hashes",
        "SkillsBench source, router, oracle, and overlap input hashes match the plan",
        lambda: _verify_live_plan_inputs(plan),
    )
    _call_check(
        checks,
        "live_agent.derived_hashes",
        "SkillsBench derived plan fields match frozen source inputs",
        lambda: _verify_live_derived_fields(plan),
    )
    _check_report_plan_path(
        checks,
        "live_agent.report_plan_path",
        report.get("plan_path"),
        plan_path,
    )
    _check_live_matrix_completeness(checks, plan, report)
    _check_prompt_hash_equality(checks, plan, report)
    _check_oracle_qualification(checks, plan)
    _check_verifier_evidence(checks, report)
    _check_no_skill_leakage(checks, report)
    _check_global_capability_inventory(checks, report, report_path.parent)
    _check_trace_completeness(checks, report, report_path.parent)
    _check_overlap_status(checks, report)
    _check_secret_redaction(checks, report, report_path.parent)

    runs = report.get("runs") if isinstance(report, dict) else []
    run_records = runs if isinstance(runs, list) else []
    condition_summary = _condition_summary(run_records)
    no_skill_rate = _success_rate(condition_summary.get("no-skill"))
    routed_rate = _success_rate(condition_summary.get("routed-skill"))
    oracle_rate = _success_rate(condition_summary.get("oracle-skill"))
    timeout_process_errors = _timeout_process_errors(run_records)
    per_task_regressions = _per_task_regressions(run_records)
    _check_live_runtime_anomalies(checks, timeout_process_errors)
    _check_live_task_regressions(checks, per_task_regressions)
    return {
        "status": PRESENT,
        "run_id": report.get("run_id"),
        "mode": report.get("mode"),
        "condition_summary": condition_summary,
        "routed_vs_no_skill_delta": {
            "task_success_delta": _nullable_delta(routed_rate, no_skill_rate),
        },
        "oracle_gap": {
            "routed_minus_oracle_success_delta": _nullable_delta(routed_rate, oracle_rate),
        },
        "timeout_process_errors": timeout_process_errors,
        "skill_use_evidence": _skill_use_summary(run_records),
        "per_task_regressions": per_task_regressions,
        "overlap_report": report.get("overlap_report"),
        "negative_hit_rate": {
            "status": UNAVAILABLE,
            "reason": "explicit negative labels are not present for SkillsBench",
        },
    }


def _is_stage2_real_codex_packet(plan: dict[str, Any], report: dict[str, Any]) -> bool:
    return (
        isinstance(plan, dict)
        and isinstance(report, dict)
        and plan.get("schema_version") == STAGE2_FROZEN_PLAN_SCHEMA
        and report.get("schema_version") == STAGE2_REAL_CODEX_EXECUTION_SCHEMA
    )


def _evaluate_stage2_real_codex_live_agent(
    *,
    plan_path: Path,
    report_path: Path,
    plan: dict[str, Any],
    report: dict[str, Any],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    adapter_failures = _stage2_adapter_failures(plan_path, report_path, plan, report)
    _check(
        checks,
        "live_agent.stage2_schema_adapter",
        PASS if not adapter_failures else FAIL,
        BLOCKING,
        "Stage 2 real Codex execution schema was adapted for live-agent evidence checks"
        if not adapter_failures
        else "Stage 2 real Codex execution schema cannot be adapted for live-agent evidence checks",
        {"failures": adapter_failures},
    )
    normalized_plan, normalized_report = _stage2_live_agent_view(
        plan_path=plan_path,
        report_path=report_path,
        plan=plan,
        report=report,
    )

    _check_live_matrix_completeness(checks, normalized_plan, normalized_report)
    _check_prompt_hash_equality(checks, normalized_plan, normalized_report)
    _check_oracle_qualification(checks, normalized_plan)
    _check_verifier_evidence(checks, normalized_report)
    _check_no_skill_leakage(checks, normalized_report)
    _check_global_capability_inventory(checks, normalized_report, report_path.parent)
    _check_trace_completeness(checks, normalized_report, report_path.parent)
    _check_overlap_status(checks, normalized_report)
    _check_secret_redaction(checks, normalized_report, report_path.parent)

    run_records = normalized_report["runs"]
    condition_summary = _condition_summary(run_records)
    no_skill_rate = _success_rate(condition_summary.get("no-skill"))
    routed_rate = _success_rate(condition_summary.get("routed-skill"))
    oracle_rate = _success_rate(condition_summary.get("oracle-skill"))
    timeout_process_errors = _timeout_process_errors(run_records)
    per_task_regressions = _per_task_regressions(run_records)
    _check_live_runtime_anomalies(checks, timeout_process_errors)
    _check_live_task_regressions(checks, per_task_regressions)
    return {
        "status": PRESENT,
        "run_id": normalized_report.get("run_id"),
        "mode": normalized_report.get("mode"),
        "condition_summary": condition_summary,
        "routed_vs_no_skill_delta": {
            "task_success_delta": _nullable_delta(routed_rate, no_skill_rate),
        },
        "oracle_gap": {
            "routed_minus_oracle_success_delta": _nullable_delta(routed_rate, oracle_rate),
        },
        "timeout_process_errors": timeout_process_errors,
        "skill_use_evidence": _skill_use_summary(run_records),
        "per_task_regressions": per_task_regressions,
        "overlap_report": normalized_report.get("overlap_report"),
        "negative_hit_rate": {
            "status": UNAVAILABLE,
            "reason": "explicit negative labels are not present for SkillsBench",
        },
        "stage2_schema_adapter": {
            "status": PASS if not adapter_failures else FAIL,
            "source_plan_schema": plan.get("schema_version"),
            "source_report_schema": report.get("schema_version"),
        },
    }


def _stage2_adapter_failures(
    plan_path: Path,
    report_path: Path,
    plan: dict[str, Any],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    expected_runs = plan.get("pilot_shape", {}).get("runs")
    actual_runs = report.get("run_records")
    if not isinstance(expected_runs, list):
        failures.append({"reason": "stage2 frozen plan pilot_shape.runs is missing"})
        expected_runs = []
    if not isinstance(actual_runs, list):
        failures.append({"reason": "stage2 execution run_records is missing"})
        actual_runs = []
    expected_ids = [str(run.get("run_id")) for run in expected_runs if isinstance(run, dict)]
    actual_ids = [str(run.get("run_id")) for run in actual_runs if isinstance(run, dict)]
    if expected_ids != actual_ids:
        failures.append(
            {
                "reason": "stage2 execution run order does not match frozen plan",
                "expected_run_ids": expected_ids,
                "actual_run_ids": actual_ids,
            }
        )
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("runs_planned") != len(expected_ids):
        failures.append({"reason": "runs_planned does not match frozen run count"})
    if summary.get("runs_completed_with_verifier_output") != len(expected_ids):
        failures.append({"reason": "not every frozen run has verifier output"})
    if summary.get("pass_fail_counts_are_verifier_output_facts_only") is not True:
        failures.append({"reason": "pass/fail counts are not marked as verifier-output facts"})
    boundaries = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    forbidden_true = {
        "process_exit_code_used_as_task_success",
        "llm_judge_used",
        "llm_judge_used_as_task_success",
        "performance_claim_made",
        "router_promoted",
        "evidence_gate_rerun",
        "oracle_qualification_rerun",
        "routed_predictions_changed",
        "verifier_outputs_rewritten",
        "task_manifests_or_public_prompts_changed",
        "scorer_matrix_router_evidence_gate_semantics_modified",
    }
    for key in sorted(forbidden_true):
        if boundaries.get(key) is not False:
            failures.append({"reason": f"stage2 boundary {key} is not false"})
    input_package = _stage2_input_package(plan)
    if input_package is None:
        failures.append({"reason": "stage2 input package cannot be loaded"})
    for run in actual_runs:
        if not isinstance(run, dict):
            failures.append({"reason": "stage2 run record is not an object"})
            continue
        verifier = run.get("verifier")
        if not isinstance(verifier, dict) or not isinstance(verifier.get("passed"), bool):
            failures.append({"run_id": run.get("run_id"), "reason": "missing verifier.passed"})
        if run.get("success_source", {}).get("task_success_source") != "deterministic verifier output only":
            failures.append(
                {"run_id": run.get("run_id"), "reason": "task success source is not deterministic verifier"}
            )
        if run.get("codex", {}).get("process_exit_code_is_task_success") is not False:
            failures.append(
                {"run_id": run.get("run_id"), "reason": "Codex process exit code is marked as task success"}
            )
        if not isinstance(verifier, dict) or verifier.get("llm_judge_used") is not False:
            failures.append({"run_id": run.get("run_id"), "reason": "LLM judge use is not false"})
        trace = run.get("trace") if isinstance(run.get("trace"), dict) else {}
        trace_path = _stage2_relative_to_report_dir(report_path, trace.get("path"))
        if trace_path is None:
            failures.append({"run_id": run.get("run_id"), "reason": "trace path is not under report directory"})
        reward = verifier.get("reward") if isinstance(verifier, dict) else None
        ctrf = verifier.get("ctrf") if isinstance(verifier, dict) else None
        if not isinstance(reward, dict) and not isinstance(ctrf, dict):
            failures.append({"run_id": run.get("run_id"), "reason": "missing reward or CTRF verifier artifact"})
    return failures


def _stage2_live_agent_view(
    *,
    plan_path: Path,
    report_path: Path,
    plan: dict[str, Any],
    report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    input_package = _stage2_input_package(plan) or {}
    selected_tasks = input_package.get("data_root_package", {}).get("selected_tasks", [])
    oracle_records = input_package.get("oracle_qualification_package", {}).get("records", {})
    run_records = [run for run in report.get("run_records", []) if isinstance(run, dict)]
    prompt_hashes = {
        str(run.get("run_id")): run.get("inputs", {}).get("task_prompt_sha256")
        for run in run_records
    }
    matrix = []
    for entry in plan.get("pilot_shape", {}).get("runs", []):
        if not isinstance(entry, dict):
            continue
        run_id = str(entry.get("run_id"))
        matching_run = next((run for run in run_records if run.get("run_id") == run_id), {})
        mounted_skills = matching_run.get("workspace", {}).get("mounted_skills", [])
        matrix.append(
            {
                "run_id": run_id,
                "task_id": entry.get("task_id"),
                "condition": entry.get("condition_id"),
                "prompt_hash": prompt_hashes.get(run_id),
                "mounted_skill_ids": _skill_ids(mounted_skills),
            }
        )
    normalized_plan = {
        "schema_version": LIVE_PLAN_SCHEMA,
        "matrix": matrix,
        "selected_tasks": selected_tasks,
        "oracle_qualification_records": oracle_records,
    }
    normalized_report = {
        "schema_version": LIVE_REPORT_SCHEMA,
        "run_id": report.get("artifact_timestamp"),
        "mode": "stage2-real-codex",
        "plan_path": str(plan_path),
        "summary": {"task_success_source": "verifier_pass_fail"},
        "overlap_report": {
            "decision": "UNAVAILABLE",
            "independent_generalization_claim": False,
        },
        "runs": [
            _stage2_run_view(run, report_path)
            for run in run_records
        ],
    }
    return normalized_plan, normalized_report


def _stage2_input_package(plan: dict[str, Any]) -> dict[str, Any] | None:
    ref = plan.get("artifact_refs", {}).get("stage2_real_pilot_input_package")
    if not isinstance(ref, dict):
        return None
    path = ref.get("path")
    if not isinstance(path, str):
        return None
    package_path = Path(path)
    if not package_path.exists():
        return None
    if ref.get("sha256") and sha256_file(package_path) != ref.get("sha256"):
        return None
    try:
        payload = _read_json(package_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _stage2_run_view(run: dict[str, Any], report_path: Path) -> dict[str, Any]:
    trace_meta = run.get("trace") if isinstance(run.get("trace"), dict) else {}
    trace_path = _stage2_relative_to_report_dir(report_path, trace_meta.get("path"))
    trace_file = report_path.parent / trace_path if trace_path else None
    trace = _read_json(trace_file) if trace_file is not None and trace_file.exists() else {}
    mounted_skills = trace.get("mounted_skills") if isinstance(trace.get("mounted_skills"), list) else []
    skill_use = trace.get("skill_use") if isinstance(trace.get("skill_use"), dict) else {}
    verifier = run.get("verifier") if isinstance(run.get("verifier"), dict) else {}
    codex = run.get("codex") if isinstance(run.get("codex"), dict) else {}
    passed = verifier.get("passed")
    return {
        "run_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "condition": run.get("condition"),
        "prompt_hash": run.get("inputs", {}).get("task_prompt_sha256"),
        "mounted_skill_ids": _skill_ids(mounted_skills),
        "mounted_skill_count": len(mounted_skills),
        "skill_use": skill_use,
        "process_exit_code": codex.get("process_exit_code"),
        "timed_out": codex.get("timed_out"),
        "task_success": passed,
        "verifier_passed": passed,
        "verifier": {"passed": passed},
        "trace_path": str(trace_path) if trace_path else None,
        "trace_sha256": trace_meta.get("sha256"),
    }


def _stage2_relative_to_report_dir(report_path: Path, raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return None
    report_dir = report_path.parent
    try:
        return path.resolve().relative_to(report_dir.resolve())
    except (OSError, ValueError):
        return None


def _skill_ids(records: Any) -> list[str]:
    if not isinstance(records, list):
        return []
    return [
        str(record.get("skill_id"))
        for record in records
        if isinstance(record, dict) and record.get("skill_id")
    ]


def _verify_external_inputs(plan: dict[str, Any]) -> None:
    adapter = SkillRouterAdapter(
        data_root=plan["data_root"],
        upstream_ref=plan["adapter_provenance"]["upstream_ref"],
        license_note=plan["adapter_provenance"]["license_note"],
        tiers=tuple(plan.get("tiers") or ("easy", "hard")),
    )
    if Path(plan["data_root"]).exists():
        _verify_external_adapter_provenance(adapter, plan)
    else:
        _verify_frozen_external_data_root_provenance(plan)
    _verify_frozen_predictions(plan)


def _verify_frozen_external_data_root_provenance(plan: dict[str, Any]) -> None:
    validation = plan.get("validation")
    provenance = plan.get("adapter_provenance")
    if not isinstance(validation, dict) or validation.get("status") != PASS:
        raise ValueError("frozen external validation is not PASS")
    if not isinstance(provenance, dict) or provenance.get("validation_status") != PASS:
        raise ValueError("frozen external adapter provenance is not PASS")
    files = provenance.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("frozen external adapter provenance has no files")

    by_role: dict[str, list[dict[str, Any]]] = {}
    for record in files:
        if not isinstance(record, dict):
            raise ValueError("frozen external adapter provenance file record is invalid")
        role = record.get("role")
        if not isinstance(role, str) or not role:
            raise ValueError("frozen external adapter provenance file role is missing")
        if not isinstance(record.get("path"), str) or not record["path"]:
            raise ValueError("frozen external adapter provenance file path is missing")
        if not isinstance(record.get("sha256"), str) or len(record["sha256"]) != 64:
            raise ValueError("frozen external adapter provenance file sha256 is invalid")
        if not isinstance(record.get("size_bytes"), int) or record["size_bytes"] <= 0:
            raise ValueError("frozen external adapter provenance file size is invalid")
        by_role.setdefault(role, []).append(record)

    required_roles = {"tasks", "relevance", "manifest"}
    required_roles.update(f"skills:{tier}" for tier in plan.get("tiers", ("easy", "hard")))
    missing_roles = sorted(required_roles - set(by_role))
    if missing_roles:
        raise ValueError(f"frozen external adapter provenance missing roles: {missing_roles}")

    _verify_external_record_count(by_role["tasks"], validation.get("task_count"), "task_count")
    _verify_external_positive_count(validation.get("relevance_count"), "relevance_count")
    _verify_external_provenance_counts_are_positive(by_role["relevance"], "relevance")
    skill_counts = validation.get("skill_count_by_tier")
    if not isinstance(skill_counts, dict):
        raise ValueError("frozen external validation skill counts are missing")
    for tier in plan.get("tiers", ("easy", "hard")):
        role = f"skills:{tier}"
        _verify_external_record_count(by_role[role], skill_counts.get(tier), f"skills:{tier}")


def _verify_external_record_count(
    records: list[dict[str, Any]],
    expected: Any,
    label: str,
) -> None:
    if not isinstance(expected, int) or expected <= 0:
        raise ValueError(f"frozen external validation {label} is invalid")
    counts = [record.get("record_count") for record in records]
    if not all(isinstance(count, int) and count > 0 for count in counts):
        raise ValueError(f"frozen external adapter provenance {label} count is invalid")
    if sum(counts) != expected:
        raise ValueError(f"frozen external adapter provenance {label} count changed")


def _verify_external_positive_count(value: Any, label: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"frozen external validation {label} is invalid")


def _verify_external_provenance_counts_are_positive(
    records: list[dict[str, Any]],
    label: str,
) -> None:
    counts = [record.get("record_count") for record in records]
    if not all(isinstance(count, int) and count > 0 for count in counts):
        raise ValueError(f"frozen external adapter provenance {label} count is invalid")


def _promotion_gate(validity_status: str, external: dict[str, Any]) -> dict[str, Any]:
    unavailable = {
        "status": UNAVAILABLE,
        "reason": "no preregistered promotion artifact was provided",
    }
    return {
        "decision": KEEP_BASELINE,
        "blocked_by_validity": validity_status == INVALID_EVIDENCE,
        "reasons": _promotion_reasons(validity_status),
        "evaluated_router_configs": external.get("evaluated_router_configs", []),
        "baseline_router": unavailable,
        "candidate_router": unavailable,
    }


def _external_router_configs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    configs = plan.get("frozen_routers") if isinstance(plan, dict) else []
    if not isinstance(configs, list):
        return []
    return [
        {
            "config_id": config.get("config_id"),
            "router_id": config.get("router_id"),
            "field_view": config.get("field_view"),
            "version": config.get("version"),
        }
        for config in configs
        if isinstance(config, dict)
    ]


def _check_external_report_completeness(
    checks: list[dict[str, Any]],
    plan: dict[str, Any],
    report: dict[str, Any],
) -> None:
    expected = [
        str(config.get("config_id"))
        for config in plan.get("frozen_routers", [])
        if isinstance(config, dict) and config.get("config_id")
    ]
    official = report.get("official") if isinstance(report, dict) else None
    actual = sorted(official) if isinstance(official, dict) else []
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    structure_errors = []
    tiers = [str(tier) for tier in plan.get("tiers", ("easy", "hard"))]
    if isinstance(official, dict):
        for config_id in sorted(set(expected) & set(actual)):
            structure_errors.extend(
                _official_config_structure_errors(config_id, official[config_id], tiers)
            )
    _check(
        checks,
        "external.report_completeness",
        PASS if not missing and not extra and not structure_errors else FAIL,
        BLOCKING,
        "external official report covers exactly the frozen configs and tiers"
        if not missing and not extra and not structure_errors
        else "external official report does not match frozen config/tier structure",
        {
            "expected_config_ids": expected,
            "actual_config_ids": actual,
            "missing_config_ids": missing,
            "unexpected_config_ids": extra,
            "structure_errors": structure_errors,
        },
    )


def _official_config_structure_errors(
    config_id: str,
    payload: Any,
    tiers: list[str],
) -> list[dict[str, Any]]:
    errors = []
    if not isinstance(payload, dict):
        return [{"config_id": config_id, "reason": "config report is not an object"}]
    score = payload
    if score.get("schema_version") != "v0.3.skillrouter-official-scorer.v1":
        errors.append({"config_id": config_id, "reason": "missing official scorer schema"})
    by_tier = score.get("by_tier")
    if not isinstance(by_tier, dict):
        return errors + [{"config_id": config_id, "reason": "missing by_tier object"}]
    missing_tiers = sorted(set(tiers) - set(by_tier))
    extra_tiers = sorted(set(by_tier) - set(tiers))
    for tier in missing_tiers:
        errors.append({"config_id": config_id, "tier": tier, "reason": "missing tier"})
    for tier in extra_tiers:
        errors.append({"config_id": config_id, "tier": tier, "reason": "unexpected tier"})
    for tier in sorted(set(tiers) & set(by_tier)):
        tier_report = by_tier[tier]
        if not isinstance(tier_report, dict):
            errors.append({"config_id": config_id, "tier": tier, "reason": "tier is not object"})
            continue
        aggregates = tier_report.get("aggregates")
        if not isinstance(aggregates, dict):
            errors.append({"config_id": config_id, "tier": tier, "reason": "missing aggregates"})
        else:
            for slice_name in ("all", "single", "multi"):
                if not isinstance(aggregates.get(slice_name), dict):
                    errors.append(
                        {
                            "config_id": config_id,
                            "tier": tier,
                            "slice": slice_name,
                            "reason": "missing aggregate slice",
                        }
                    )
        if not isinstance(tier_report.get("tasks"), list):
            errors.append({"config_id": config_id, "tier": tier, "reason": "missing tasks"})
        if not isinstance(tier_report.get("task_count"), int):
            errors.append(
                {"config_id": config_id, "tier": tier, "reason": "missing task_count"}
            )
    return errors


def _schema_check(
    checks: list[dict[str, Any]],
    check_id: str,
    payload: dict[str, Any],
    expected: str,
) -> None:
    actual = payload.get("schema_version") if isinstance(payload, dict) else None
    _check(
        checks,
        check_id,
        PASS if actual == expected else FAIL,
        BLOCKING,
        f"{check_id} matches {expected}"
        if actual == expected
        else f"{check_id} expected {expected}, got {actual}",
        {"expected": expected, "actual": actual},
    )


def _check_report_plan_path(
    checks: list[dict[str, Any]],
    check_id: str,
    actual_path: Any,
    expected_path: Path,
) -> None:
    try:
        matches = Path(str(actual_path)).resolve() == expected_path.resolve()
    except OSError:
        matches = False
    _check(
        checks,
        check_id,
        PASS if matches else FAIL,
        BLOCKING,
        "report points at the validated frozen plan"
        if matches
        else "report plan_path does not match the validated plan",
        {"expected": str(expected_path), "actual": actual_path},
    )


def _check_prompt_hash_equality(
    checks: list[dict[str, Any]],
    plan: dict[str, Any],
    report: dict[str, Any],
) -> None:
    plan_mismatches = _prompt_hash_mismatches(plan.get("matrix", []))
    report_mismatches = _prompt_hash_mismatches(report.get("runs", []))
    mismatches = sorted(set(plan_mismatches + report_mismatches))
    _check(
        checks,
        "live_agent.prompt_hash_equality",
        PASS if not mismatches else FAIL,
        BLOCKING,
        "all conditions use the same prompt hash per task"
        if not mismatches
        else "prompt hash mismatch across live-agent conditions",
        {"task_ids": mismatches},
    )


def _check_live_matrix_completeness(
    checks: list[dict[str, Any]],
    plan: dict[str, Any],
    report: dict[str, Any],
) -> None:
    matrix = plan.get("matrix") if isinstance(plan, dict) else []
    runs = report.get("runs") if isinstance(report, dict) else []
    if not isinstance(matrix, list) or not isinstance(runs, list):
        _check(
            checks,
            "live_agent.matrix_completeness",
            FAIL,
            BLOCKING,
            "live-agent matrix or runs are malformed",
        )
        return

    expected: dict[str, dict[str, Any]] = {}
    duplicate_expected = []
    for entry in matrix:
        if not isinstance(entry, dict):
            continue
        run_id = str(entry.get("run_id"))
        if run_id in expected:
            duplicate_expected.append(run_id)
        expected[run_id] = entry

    actual: dict[str, dict[str, Any]] = {}
    duplicate_actual = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_id = str(run.get("run_id"))
        if run_id in actual:
            duplicate_actual.append(run_id)
        actual[run_id] = run

    mismatches = []
    for run_id in sorted(set(expected) & set(actual)):
        entry = expected[run_id]
        run = actual[run_id]
        for field in ("task_id", "condition", "prompt_hash"):
            if run.get(field) != entry.get(field):
                mismatches.append(
                    {
                        "run_id": run_id,
                        "field": field,
                        "expected": entry.get(field),
                        "actual": run.get(field),
                    }
                )
        if list(run.get("mounted_skill_ids") or []) != list(entry.get("mounted_skill_ids") or []):
            mismatches.append(
                {
                    "run_id": run_id,
                    "field": "mounted_skill_ids",
                    "expected": entry.get("mounted_skill_ids"),
                    "actual": run.get("mounted_skill_ids"),
                }
            )

    failures = {
        "missing_run_ids": sorted(set(expected) - set(actual)),
        "extra_run_ids": sorted(set(actual) - set(expected)),
        "duplicate_expected_run_ids": sorted(duplicate_expected),
        "duplicate_actual_run_ids": sorted(duplicate_actual),
        "mismatches": mismatches,
    }
    is_complete = not any(failures.values())
    _check(
        checks,
        "live_agent.matrix_completeness",
        PASS if is_complete else FAIL,
        BLOCKING,
        "live-agent report contains exactly the frozen matrix runs"
        if is_complete
        else "live-agent report does not match the frozen matrix",
        failures,
    )


def _prompt_hash_mismatches(records: Any) -> list[str]:
    by_task: dict[str, set[str]] = {}
    if not isinstance(records, list):
        return ["<malformed>"]
    for record in records:
        if not isinstance(record, dict):
            return ["<malformed>"]
        task_id = str(record.get("task_id"))
        by_task.setdefault(task_id, set()).add(str(record.get("prompt_hash")))
    return [task_id for task_id, hashes in by_task.items() if len(hashes) > 1]


def _check_oracle_qualification(checks: list[dict[str, Any]], plan: dict[str, Any]) -> None:
    selected_tasks = [
        task for task in plan.get("selected_tasks", []) if isinstance(task, dict)
    ]
    selected = {task.get("task_id") for task in selected_tasks}
    records = plan.get("oracle_qualification_records", {})
    qualified = set(records) if isinstance(records, dict) else set()
    missing = sorted(str(task_id) for task_id in selected - qualified)
    failures = [{"task_id": task_id, "reason": "missing oracle qualification"} for task_id in missing]
    if isinstance(records, dict):
        for task in selected_tasks:
            task_id = str(task.get("task_id"))
            if task_id not in records:
                continue
            failures.extend(_oracle_record_failures(task, records[task_id]))
    else:
        failures.append({"reason": "oracle_qualification_records is not an object"})
    _check(
        checks,
        "live_agent.oracle_qualification",
        PASS if not failures else FAIL,
        BLOCKING,
        "oracle qualification passed for every selected live task"
        if not failures
        else "selected live tasks failed oracle qualification requirements",
        {"failures": failures},
    )


def _oracle_record_failures(
    task: dict[str, Any],
    record: Any,
) -> list[dict[str, Any]]:
    task_id = str(task.get("task_id"))
    failures = []
    if not isinstance(record, dict):
        return [{"task_id": task_id, "reason": "oracle record is not an object"}]
    if record.get("condition") not in {None, "oracle-skill"}:
        failures.append({"task_id": task_id, "reason": "oracle record condition is not oracle-skill"})
    passed = record.get("verifier_passed", record.get("passed"))
    if passed is not True:
        failures.append({"task_id": task_id, "reason": "oracle verifier did not pass"})
    pass_rate = record.get("pass_rate", record.get("oracle_pass_rate"))
    if pass_rate is not None:
        parsed_rate = _float_value(pass_rate)
        if parsed_rate is None or parsed_rate < 1.0:
            failures.append({"task_id": task_id, "reason": "oracle pass_rate is below 1.0"})
    passes = record.get("passes", record.get("pass_count"))
    trials = record.get("trials", record.get("trial_count"))
    if passes is not None and trials is not None:
        parsed_passes = _int_or_none(passes)
        parsed_trials = _int_or_none(trials)
        if (
            parsed_passes is None
            or parsed_trials is None
            or parsed_passes != parsed_trials
        ):
            failures.append({"task_id": task_id, "reason": "oracle passes do not equal trials"})
    for field in ("verifier_stable", "stable", "deterministic", "verifier_deterministic"):
        if field in record and record[field] is not True:
            failures.append({"task_id": task_id, "reason": f"oracle {field} is not true"})
    verifier = task.get("verifier")
    if not isinstance(verifier, dict) or verifier.get("type") != "deterministic":
        failures.append({"task_id": task_id, "reason": "task verifier is not deterministic"})
    if task.get("requires_private_credentials") is True:
        failures.append({"task_id": task_id, "reason": "task requires private credentials"})
    if task.get("network", "none") not in {"none", "controlled"}:
        failures.append({"task_id": task_id, "reason": "task network requirement is uncontrolled"})
    return failures


def _check_verifier_evidence(checks: list[dict[str, Any]], report: dict[str, Any]) -> None:
    failures = []
    for run in _runs(report):
        verifier = run.get("verifier")
        if not isinstance(verifier, dict) or not isinstance(verifier.get("passed"), bool):
            failures.append({"run_id": run.get("run_id"), "reason": "missing verifier.passed"})
            continue
        if run.get("task_success") is not verifier.get("passed"):
            failures.append(
                {"run_id": run.get("run_id"), "reason": "task_success differs from verifier.passed"}
            )
        if run.get("verifier_passed") is not verifier.get("passed"):
            failures.append(
                {
                    "run_id": run.get("run_id"),
                    "reason": "verifier_passed differs from verifier.passed",
                }
            )
    source_ok = report.get("summary", {}).get("task_success_source") == "verifier_pass_fail"
    if not source_ok:
        failures.append({"run_id": "<summary>", "reason": "task success source is not verifier"})
    _check(
        checks,
        "live_agent.verifier_evidence",
        PASS if not failures else FAIL,
        BLOCKING,
        "deterministic verifier records are complete and source task success"
        if not failures
        else "verifier evidence is incomplete or not the success source",
        {"failures": failures},
    )


def _check_no_skill_leakage(checks: list[dict[str, Any]], report: dict[str, Any]) -> None:
    failures = []
    for run in _runs(report):
        if run.get("condition") != "no-skill":
            continue
        if run.get("mounted_skill_count") != 0 or run.get("mounted_skill_ids"):
            failures.append({"run_id": run.get("run_id"), "reason": "benchmark skills mounted"})
        for skill_id, evidence in (run.get("skill_use") or {}).items():
            state = evidence.get("state") if isinstance(evidence, dict) else None
            if state in {"MOUNTED_ONLY", "READ"}:
                failures.append(
                    {
                        "run_id": run.get("run_id"),
                        "skill_id": skill_id,
                        "reason": f"no-skill evidence state {state}",
                    }
                )
    _check(
        checks,
        "live_agent.no_skill_leakage",
        PASS if not failures else FAIL,
        BLOCKING,
        "no-skill condition mounted no benchmark skills"
        if not failures
        else "no-skill condition shows benchmark skill leakage",
        {"failures": failures},
    )


def _check_global_capability_inventory(
    checks: list[dict[str, Any]],
    report: dict[str, Any],
    report_dir: Path,
) -> None:
    failures = []
    reviews = []
    inventories = _capability_inventories(report, report_dir)
    for source, inventory in inventories:
        failures.extend(_capability_inventory_failures(source, inventory))
        reviews.extend(_capability_inventory_reviews(source, inventory))
    if not inventories:
        status = REVIEW
        severity = REVIEW_SEVERITY
        summary = "global capability inventory is missing"
    elif failures:
        status = FAIL
        severity = BLOCKING
        summary = "global capability inventory shows skill leakage"
    elif reviews:
        status = REVIEW
        severity = REVIEW_SEVERITY
        summary = "global capability inventory requires review"
    else:
        status = PASS
        severity = INFO
        summary = "global capability inventory has no detected user/admin/repo leakage"
    _check(
        checks,
        "live_agent.global_capability_inventory",
        status,
        severity,
        summary,
        {
            "inventory_count": len(inventories),
            "failures": failures,
            "reviews": reviews,
        },
    )


def _capability_inventories(
    report: dict[str, Any],
    report_dir: Path,
) -> list[tuple[str, dict[str, Any]]]:
    inventories = []
    for key in ("global_capability_inventory", "preflight"):
        value = report.get(key)
        if isinstance(value, dict):
            inventory = value.get("global_capability_inventory", value)
            if isinstance(inventory, dict):
                inventories.append((f"report.{key}", _inventory_with_preflight_mode(inventory, value)))
    for run in _runs(report):
        trace_path = _trace_path_for_run(run, report_dir)
        if trace_path is None or not trace_path.exists():
            continue
        try:
            trace = _read_json(trace_path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        for event in trace.get("events", []):
            if not isinstance(event, dict) or event.get("type") != "preflight":
                continue
            inventory = event.get("global_capability_inventory") or event.get("skill_inventory")
            if isinstance(inventory, dict):
                inventories.append(
                    (
                        f"trace.{run.get('run_id')}.preflight",
                        _inventory_with_preflight_mode(inventory, event),
                    )
                )
    return inventories


def _inventory_with_preflight_mode(
    inventory: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(inventory)
    for key in ("codex_home_mode", "evidence_mode"):
        if key in preflight and key not in merged:
            merged[key] = preflight[key]
    return merged


def _capability_inventory_failures(
    source: str,
    inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    failures = []
    user = inventory.get("user_skill_dir")
    if isinstance(user, dict) and _entry_count(user) > 0:
        failures.append({"source": source, "surface": "user_skill_dir", "reason": "non-empty"})
    admin_dirs = inventory.get("admin_skill_dirs", [])
    if isinstance(admin_dirs, list):
        for index, item in enumerate(admin_dirs):
            if isinstance(item, dict) and _entry_count(item) > 0:
                failures.append(
                    {
                        "source": source,
                        "surface": f"admin_skill_dirs[{index}]",
                        "reason": "non-empty",
                    }
                )
    workspace = inventory.get("workspace_skill_dirs")
    if isinstance(workspace, dict):
        for key, value in workspace.items():
            if "parent" in str(key) and str(key).endswith("count") and _int_value(value) > 0:
                failures.append(
                    {
                        "source": source,
                        "surface": f"workspace_skill_dirs.{key}",
                        "reason": "workspace-parent skills are non-empty",
                    }
                )
        for key in ("unexpected_entry_count", "leaked_entry_count", "parent_leak_count"):
            if _int_value(workspace.get(key)) > 0:
                failures.append(
                    {
                        "source": source,
                        "surface": f"workspace_skill_dirs.{key}",
                        "reason": "workspace skills are not run-created",
                    }
                )
    return failures


def _capability_inventory_reviews(
    source: str,
    inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    reviews = []
    user = inventory.get("user_skill_dir")
    if isinstance(user, dict) and user.get("status") == "SMOKE_ONLY":
        reviews.append({"source": source, "surface": "user_skill_dir", "reason": "smoke-only"})
    for key in ("codex_home_mode", "evidence_mode"):
        value = inventory.get(key)
        if value in {"inherit", "smoke-only"}:
            reviews.append({"source": source, "surface": key, "reason": str(value)})
    return reviews


def _entry_count(value: dict[str, Any]) -> int:
    for key in ("entry_count", "entries", "skill_count", "count"):
        count = _int_value(value.get(key))
        if count:
            return count
    return 0


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_trace_completeness(
    checks: list[dict[str, Any]],
    report: dict[str, Any],
    report_dir: Path,
) -> None:
    failures = []
    for run in _runs(report):
        trace_path = _trace_path_for_run(run, report_dir)
        if trace_path is None:
            failures.append({"run_id": run.get("run_id"), "reason": "trace path escapes artifact directory"})
            continue
        if not trace_path.exists():
            failures.append({"run_id": run.get("run_id"), "reason": "trace file is missing"})
            continue
        expected_hash = _trace_hash_from_run(run)
        if expected_hash and sha256_file(trace_path) != expected_hash:
            failures.append({"run_id": run.get("run_id"), "reason": "trace hash mismatch"})
            continue
        try:
            trace = _read_json(trace_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append({"run_id": run.get("run_id"), "reason": str(exc)})
            continue
        required = {"schema_version", "request", "result", "mounted_skills", "skill_use", "events"}
        missing = sorted(required - set(trace))
        if trace.get("schema_version") != "live-agent.v1" or missing:
            failures.append(
                {
                    "run_id": run.get("run_id"),
                    "reason": "trace schema or required fields are incomplete",
                    "missing": missing,
                }
            )
            continue
        failures.extend(_trace_report_mismatches(run, trace))
    _check(
        checks,
        "live_agent.trace_completeness",
        PASS if not failures else FAIL,
        BLOCKING,
        "all live-agent runs have complete trace files"
        if not failures
        else "live-agent trace files are missing, incomplete, or inconsistent with report rows",
        {"failures": failures},
    )


def _trace_path_for_run(run: dict[str, Any], report_dir: Path) -> Path | None:
    raw = run.get("trace_path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = report_dir / path
    try:
        resolved = path.resolve()
        resolved.relative_to(report_dir.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _trace_hash_from_run(run: dict[str, Any]) -> str | None:
    for key in ("trace_sha256", "trace_hash", "trace_file_sha256"):
        value = run.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    trace_file = run.get("trace_file")
    if isinstance(trace_file, dict):
        value = trace_file.get("sha256")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _trace_report_mismatches(run: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    result = trace.get("result") if isinstance(trace.get("result"), dict) else {}
    verifier = result.get("verifier") if isinstance(result.get("verifier"), dict) else {}
    comparisons = {
        "process_exit_code": (run.get("process_exit_code"), result.get("process_exit_code")),
        "timed_out": (run.get("timed_out"), result.get("timed_out")),
        "task_success": (run.get("task_success"), result.get("task_success")),
        "verifier.passed": (run.get("verifier_passed"), verifier.get("passed")),
    }
    failures = [
        {
            "run_id": run.get("run_id"),
            "reason": "trace/report field mismatch",
            "field": field,
            "report": report_value,
            "trace": trace_value,
        }
        for field, (report_value, trace_value) in comparisons.items()
        if report_value != trace_value
    ]
    trace_skill_ids = [
        record.get("skill_id")
        for record in trace.get("mounted_skills", [])
        if isinstance(record, dict)
    ]
    if list(run.get("mounted_skill_ids") or []) != trace_skill_ids:
        failures.append(
            {
                "run_id": run.get("run_id"),
                "reason": "trace/report mounted_skill_ids mismatch",
                "report": run.get("mounted_skill_ids"),
                "trace": trace_skill_ids,
            }
        )
    if _canonical_json(run.get("skill_use") or {}) != _canonical_json(trace.get("skill_use") or {}):
        failures.append(
            {
                "run_id": run.get("run_id"),
                "reason": "trace/report skill_use mismatch",
            }
        )
    return failures


def _check_overlap_status(checks: list[dict[str, Any]], report: dict[str, Any]) -> None:
    overlap = report.get("overlap_report")
    decision = overlap.get("decision") if isinstance(overlap, dict) else None
    independent_claim = (
        overlap.get("independent_generalization_claim")
        if isinstance(overlap, dict)
        else None
    )
    if decision != "DISJOINT" and independent_claim is True:
        status = FAIL
        severity = BLOCKING
        summary = "overlap independent_generalization_claim conflicts with overlap decision"
    elif decision == "INVALID":
        status = FAIL
        severity = BLOCKING
        summary = "overlap report is invalid"
    elif decision in {"LINKED_TRANSFER", "UNAVAILABLE"}:
        status = REVIEW
        severity = REVIEW_SEVERITY
        summary = "overlap report requires caveated generalization claims"
    elif decision == "DISJOINT":
        status = PASS
        severity = INFO
        summary = "overlap report supports independent generalization framing"
    else:
        status = FAIL
        severity = BLOCKING
        summary = "overlap report decision is missing or unsupported"
    _check(
        checks,
        "live_agent.overlap_status",
        status,
        severity,
        summary,
        {
            "decision": decision,
            "independent_generalization_claim": independent_claim,
        },
    )


def _check_secret_redaction(
    checks: list[dict[str, Any]],
    report: dict[str, Any],
    report_dir: Path,
) -> None:
    leaks = []
    if SECRET_RE.search(json.dumps(report, sort_keys=True, default=str)):
        leaks.append({"artifact": "live_report"})
    for run in _runs(report):
        trace_path = _trace_path_for_run(run, report_dir)
        if trace_path is None:
            continue
        if not trace_path.exists():
            continue
        text = trace_path.read_text(encoding="utf-8")
        if SECRET_RE.search(text):
            leaks.append({"artifact": "trace", "run_id": run.get("run_id")})
    _check(
        checks,
        "live_agent.secret_redaction",
        PASS if not leaks else FAIL,
        BLOCKING,
        "live-agent report and traces do not contain obvious secret tokens"
        if not leaks
        else "live-agent report or traces contain secret-like strings",
        {"leaks": leaks},
    )


def _check_live_runtime_anomalies(
    checks: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
) -> None:
    _check(
        checks,
        "live_agent.timeout_process_errors",
        REVIEW if anomalies else PASS,
        REVIEW_SEVERITY if anomalies else INFO,
        "live-agent timeout or process errors require review"
        if anomalies
        else "no live-agent timeout or process errors were reported",
        {"errors": anomalies},
    )


def _check_live_task_regressions(
    checks: list[dict[str, Any]],
    regressions: list[dict[str, Any]],
) -> None:
    _check(
        checks,
        "live_agent.per_task_regressions",
        REVIEW if regressions else PASS,
        REVIEW_SEVERITY if regressions else INFO,
        "routed-skill regressions versus no-skill require review"
        if regressions
        else "no routed-skill per-task regressions versus no-skill were reported",
        {"regressions": regressions},
    )


def _condition_summary(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for condition in ("no-skill", "routed-skill", "oracle-skill"):
        selected = [run for run in runs if run.get("condition") == condition]
        summary[condition] = {
            "run_count": len(selected),
            "verifier_pass_count": sum(1 for run in selected if run.get("verifier_passed") is True),
            "task_success_count": sum(1 for run in selected if run.get("task_success") is True),
            "timeout_count": sum(1 for run in selected if run.get("timed_out") is True),
            "process_error_count": sum(
                1
                for run in selected
                if run.get("process_exit_code") not in (0, None)
            ),
        }
    return summary


def _success_rate(summary: dict[str, Any] | None) -> float | None:
    if not summary or not summary.get("run_count"):
        return None
    return float(summary["task_success_count"]) / float(summary["run_count"])


def _nullable_delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _timeout_process_errors(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run.get("run_id"),
            "task_id": run.get("task_id"),
            "condition": run.get("condition"),
            "timed_out": run.get("timed_out"),
            "process_exit_code": run.get("process_exit_code"),
        }
        for run in runs
        if run.get("timed_out") or run.get("process_exit_code") not in (0, None)
    ]


def _skill_use_summary(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"MOUNTED": 0, "READ": 0, "UNKNOWN": 0, "DECLARED": 0}
    for run in runs:
        for evidence in (run.get("skill_use") or {}).values():
            if isinstance(evidence, dict):
                state = str(evidence.get("state"))
                counts[state] = counts.get(state, 0) + 1
    return counts


def _per_task_regressions(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, dict[str, bool]] = {}
    for run in runs:
        by_task.setdefault(str(run.get("task_id")), {})[str(run.get("condition"))] = bool(
            run.get("task_success")
        )
    regressions = []
    for task_id, outcomes in sorted(by_task.items()):
        if outcomes.get("no-skill") is True and outcomes.get("routed-skill") is False:
            regressions.append(
                {
                    "task_id": task_id,
                    "no_skill_success": True,
                    "routed_skill_success": False,
                }
            )
    return regressions


def _validity_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == FAIL and check["severity"] == BLOCKING for check in checks):
        return INVALID_EVIDENCE
    if any(check["status"] in {REVIEW, UNAVAILABLE} for check in checks):
        return REVIEW_REQUIRED
    return VALID_EVIDENCE


def _promotion_reasons(validity_status: str) -> list[str]:
    if validity_status == INVALID_EVIDENCE:
        return ["invalid benchmark evidence blocks promotion"]
    if validity_status == REVIEW_REQUIRED:
        return ["benchmark evidence requires review; promotion defaults to baseline"]
    return ["no preregistered promotion artifact was provided; defaulting to baseline"]


def _runs(report: dict[str, Any]) -> list[dict[str, Any]]:
    runs = report.get("runs") if isinstance(report, dict) else []
    return [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []


def _call_check(
    checks: list[dict[str, Any]],
    check_id: str,
    pass_summary: str,
    callback: Any,
) -> None:
    try:
        callback()
    except Exception as exc:  # noqa: BLE001 - gate must preserve failure details.
        _check(
            checks,
            check_id,
            FAIL,
            BLOCKING,
            str(exc),
            {"exception_type": exc.__class__.__name__},
        )
    else:
        _check(checks, check_id, PASS, INFO, pass_summary)


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    status: str,
    severity: str,
    summary: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": status,
            "severity": severity,
            "summary": summary,
            "details": details or {},
        }
    )


def _input_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_json_for_gate(
    checks: list[dict[str, Any]],
    check_id: str,
    path: Path,
) -> dict[str, Any]:
    try:
        payload = _read_json(path)
    except Exception as exc:  # noqa: BLE001 - missing/malformed inputs become gate checks.
        _check(
            checks,
            check_id,
            FAIL,
            BLOCKING,
            f"could not load JSON artifact: {exc}",
            {"path": str(path), "exception_type": exc.__class__.__name__},
        )
        return {}
    _check(checks, check_id, PASS, INFO, "JSON artifact loaded", {"path": str(path)})
    return payload


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
