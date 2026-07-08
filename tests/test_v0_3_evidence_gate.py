from __future__ import annotations

import json
import shutil
from pathlib import Path

from hermes_skilleval.cli import main
from hermes_skilleval.evidence_gate import write_evidence_decision_report
from hermes_skilleval.external.skillrouter_matrix import (
    run_skillrouter_matrix,
    write_skillrouter_matrix_plan,
)
from hermes_skilleval.live_agent_runtime import FakeAgentRunner, FakeVerifier
from hermes_skilleval.live_agent_skillsbench import (
    _derived_hashes,
    run_skillsbench_matrix,
    write_skillsbench_plan,
)
from hermes_skilleval.release_manifest import sha256_file


SKILLROUTER_FIXTURE = Path("tests/fixtures/external/skillrouter_eval_core_tiny")
SKILLROUTER_PREDICTIONS = SKILLROUTER_FIXTURE / "predictions.json"
SKILLSBENCH_FIXTURE = Path("tests/fixtures/live_agent/skillsbench_tiny")
UPSTREAM_SHA = "b" * 40
STAGE2_FROZEN_PLAN = Path(
    "artifacts/v0.3/skillsbench-pilot/v0.3-stage2-pilot-freeze-20260707T025315Z/"
    "stage2-pilot-plan.frozen.json"
)
STAGE2_REAL_CODEX_EXECUTION = Path(
    "artifacts/v0.3/skillsbench-pilot/"
    "v0.3-stage2-real-codex-12-run-execution-20260707T072652Z/"
    "stage2-real-codex-12-run-execution.json"
)


def test_evidence_gate_validates_full_packet_and_keeps_baseline(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        markdown_output_path=tmp_path / "evidence.md",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["schema_version"] == "v0.3.evidence-decision-report.v1"
    assert report["benchmark_validity_gate"]["status"] == "VALID_EVIDENCE"
    assert report["router_promotion_gate"]["decision"] == "KEEP_BASELINE"
    assert report["router_promotion_gate"]["blocked_by_validity"] is False
    assert report["router_promotion_gate"]["baseline_router"]["status"] == "UNAVAILABLE"
    assert report["router_promotion_gate"]["candidate_router"]["status"] == "UNAVAILABLE"
    assert report["field_markers"]["external_routing"]["status"] == "PRESENT"
    assert report["field_markers"]["live_agent"]["status"] == "PRESENT"
    assert "UNAVAILABLE" not in {
        report["benchmark_validity_gate"]["status"],
        report["router_promotion_gate"]["decision"],
    }
    assert report["external_routing"]["official_metric_configs"]
    assert report["external_routing"]["hermes_diagnostics_present"] is True
    assert report["live_agent"]["condition_summary"]["oracle-skill"]["run_count"] == 1
    assert report["live_agent"]["routed_vs_no_skill_delta"]["task_success_delta"] == 0.0
    assert report["live_agent"]["oracle_gap"]["routed_minus_oracle_success_delta"] == 0.0
    assert (tmp_path / "evidence.md").is_file()


def test_evidence_gate_promotion_uses_evaluated_configs_not_hardcoded_names(tmp_path):
    external_plan, external_report = _write_external_artifacts(
        tmp_path,
        routers=[
            {
                "router_id": "fixture-router-a",
                "field_view": "name_only",
                "predictions_path": str(SKILLROUTER_PREDICTIONS),
                "version": "fixture",
            },
            {
                "router_id": "fixture-router-b",
                "field_view": "full_body",
                "predictions_path": str(SKILLROUTER_PREDICTIONS),
                "version": "fixture",
            },
        ],
    )
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    evaluated = report["router_promotion_gate"]["evaluated_router_configs"]
    assert [config["router_id"] for config in evaluated] == [
        "fixture-router-a",
        "fixture-router-b",
    ]
    assert "baseline-minilm" not in json.dumps(report["router_promotion_gate"])
    assert "finetuned-embedding" not in json.dumps(report["router_promotion_gate"])


def test_evidence_gate_accepts_frozen_external_data_root_provenance_when_data_root_unmaterialized(
    tmp_path,
):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    plan = json.loads(external_plan.read_text(encoding="utf-8"))
    plan["data_root"] = str(tmp_path / "not-materialized" / "skillrouter_eval_core")
    external_plan.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "VALID_EVIDENCE"
    assert _check_by_id(report, "external.input_hashes")["status"] == "PASS"


def test_evidence_gate_accepts_stage2_real_codex_execution_schema(tmp_path):
    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        live_plan_path=STAGE2_FROZEN_PLAN,
        live_report_path=STAGE2_REAL_CODEX_EXECUTION,
    )

    assert report["benchmark_validity_gate"]["status"] == "REVIEW_REQUIRED"
    assert report["router_promotion_gate"]["decision"] == "KEEP_BASELINE"
    assert report["router_promotion_gate"]["blocked_by_validity"] is False
    assert report["live_agent"]["mode"] == "stage2-real-codex"
    assert report["live_agent"]["condition_summary"]["no-skill"]["run_count"] == 4
    assert report["live_agent"]["condition_summary"]["routed-skill"]["run_count"] == 4
    assert report["live_agent"]["condition_summary"]["oracle-skill"]["run_count"] == 4
    assert report["live_agent"]["condition_summary"]["no-skill"]["verifier_pass_count"] == 2
    assert report["live_agent"]["condition_summary"]["routed-skill"]["verifier_pass_count"] == 2
    assert report["live_agent"]["condition_summary"]["oracle-skill"]["verifier_pass_count"] == 2

    live_failures = [
        check
        for check in report["benchmark_validity_gate"]["checks"]
        if check["id"].startswith("live_agent.") and check["status"] == "FAIL"
    ]
    assert live_failures == []
    assert _check_by_id(report, "live_agent.stage2_schema_adapter")["status"] == "PASS"
    assert _check_by_id(report, "live_agent.verifier_evidence")["status"] == "PASS"
    assert _check_by_id(report, "live_agent.no_skill_leakage")["status"] == "PASS"
    assert _check_by_id(report, "live_agent.trace_completeness")["status"] == "PASS"


def test_evidence_gate_fails_when_external_report_missing_frozen_configs(tmp_path):
    routers = [
        {
            "router_id": "fixture-router-a",
            "field_view": "name_only",
            "predictions_path": str(SKILLROUTER_PREDICTIONS),
            "version": "fixture",
        },
        {
            "router_id": "fixture-router-b",
            "field_view": "metadata",
            "predictions_path": str(SKILLROUTER_PREDICTIONS),
            "version": "fixture",
        },
        {
            "router_id": "fixture-router-c",
            "field_view": "full_body",
            "predictions_path": str(SKILLROUTER_PREDICTIONS),
            "version": "fixture",
        },
    ]
    external_plan, external_report = _write_external_artifacts(tmp_path, routers=routers)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(external_report.read_text(encoding="utf-8"))
    first_config = sorted(payload["official"])[0]
    payload["official"] = {first_config: payload["official"][first_config]}
    external_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    check = _check_by_id(report, "external.report_completeness")
    assert check["status"] == "FAIL"
    assert check["details"]["missing_config_ids"]


def test_evidence_gate_fails_when_external_report_has_unknown_config(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(external_report.read_text(encoding="utf-8"))
    payload["official"]["unknown-config"] = next(iter(payload["official"].values()))
    external_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    check = _check_by_id(report, "external.report_completeness")
    assert check["status"] == "FAIL"
    assert check["details"]["unexpected_config_ids"] == ["unknown-config"]


def test_evidence_gate_passes_when_external_report_covers_all_configs(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert _check_by_id(report, "external.report_completeness")["status"] == "PASS"


def test_evidence_gate_missing_live_agent_is_review_required_field_unavailable(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "REVIEW_REQUIRED"
    assert report["field_markers"]["live_agent"] == {
        "status": "UNAVAILABLE",
        "reason": "live-agent plan/report paths were not provided",
    }
    assert report["router_promotion_gate"]["decision"] == "KEEP_BASELINE"


def test_evidence_gate_missing_artifact_path_writes_invalid_report(tmp_path):
    external_plan, _external_report = _write_external_artifacts(tmp_path)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=tmp_path / "missing-external-report.json",
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert report["router_promotion_gate"]["decision"] == "KEEP_BASELINE"
    assert any(
        check["id"] == "external.report_load" and check["status"] == "FAIL"
        for check in report["benchmark_validity_gate"]["checks"]
    )


def test_evidence_gate_invalid_live_plan_digest_blocks_promotion(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    plan = json.loads(live_plan.read_text(encoding="utf-8"))
    plan["selected_tasks"][0]["prompt"] = "tampered prompt"
    live_plan.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert report["router_promotion_gate"]["decision"] == "KEEP_BASELINE"
    assert report["router_promotion_gate"]["blocked_by_validity"] is True
    assert any(
        check["id"] == "live_agent.plan_digest"
        and check["status"] == "FAIL"
        for check in report["benchmark_validity_gate"]["checks"]
    )


def test_evidence_gate_fails_when_oracle_record_present_but_failed(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    plan = json.loads(live_plan.read_text(encoding="utf-8"))
    plan["oracle_qualification_records"]["sb-task-login"]["verifier_passed"] = False
    _write_json(live_plan, plan)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    check = _check_by_id(report, "live_agent.oracle_qualification")
    assert check["status"] == "FAIL"
    assert any("did not pass" in failure["reason"] for failure in check["details"]["failures"])


def test_evidence_gate_fails_when_oracle_pass_rate_below_one(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    plan = json.loads(live_plan.read_text(encoding="utf-8"))
    plan["oracle_qualification_records"]["sb-task-login"]["pass_rate"] = 0.5
    _write_json(live_plan, plan)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    check = _check_by_id(report, "live_agent.oracle_qualification")
    assert check["status"] == "FAIL"
    assert any("pass_rate" in failure["reason"] for failure in check["details"]["failures"])


def test_evidence_gate_passes_when_oracle_records_are_qualified(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    plan = json.loads(live_plan.read_text(encoding="utf-8"))
    record = plan["oracle_qualification_records"]["sb-task-login"]
    record["pass_rate"] = 1.0
    record["passes"] = 3
    record["trials"] = 3
    record["verifier_stable"] = True
    _write_json(live_plan, plan, update_digest=True)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert _check_by_id(report, "live_agent.oracle_qualification")["status"] == "PASS"


def test_evidence_gate_detects_no_skill_leakage_and_trace_loss(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    no_skill_run = next(run for run in payload["runs"] if run["condition"] == "no-skill")
    no_skill_run["mounted_skill_count"] = 1
    Path(no_skill_run["trace_path"]).unlink()
    live_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    failing_ids = {
        check["id"]
        for check in report["benchmark_validity_gate"]["checks"]
        if check["status"] == "FAIL"
    }
    assert "live_agent.no_skill_leakage" in failing_ids
    assert "live_agent.trace_completeness" in failing_ids


def test_evidence_gate_detects_mounted_only_no_skill_leakage(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    no_skill_run = next(run for run in payload["runs"] if run["condition"] == "no-skill")
    no_skill_run["skill_use"] = {"skill/browser-login": {"state": "MOUNTED_ONLY"}}
    live_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert any(
        check["id"] == "live_agent.no_skill_leakage" and check["status"] == "FAIL"
        for check in report["benchmark_validity_gate"]["checks"]
    )


def test_evidence_gate_fails_on_user_global_skill_inventory_leakage(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    _append_preflight_to_first_trace(
        live_report,
        _preflight_inventory(user_entries=1),
    )

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert _check_by_id(report, "live_agent.global_capability_inventory")["status"] == "FAIL"


def test_evidence_gate_passes_with_clean_isolated_capability_inventory(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    _append_preflight_to_first_trace(live_report, _preflight_inventory())

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert _check_by_id(report, "live_agent.global_capability_inventory")["status"] == "PASS"
    assert report["benchmark_validity_gate"]["status"] == "VALID_EVIDENCE"


def test_evidence_gate_inherit_mode_is_not_valid_final_evidence(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    _append_preflight_to_first_trace(
        live_report,
        _preflight_inventory(codex_home_mode="inherit", evidence_mode="smoke-only"),
    )

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "REVIEW_REQUIRED"
    assert _check_by_id(report, "live_agent.global_capability_inventory")["status"] == "REVIEW"


def test_evidence_gate_missing_global_capability_inventory_requires_review(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    _strip_capability_inventory_surfaces(live_report)
    output = tmp_path / "evidence.json"

    exit_code = main(
        [
            "v0.3-evidence-gate",
            "--output",
            str(output),
            "--external-plan",
            str(external_plan),
            "--external-report",
            str(external_report),
            "--live-plan",
            str(live_plan),
            "--live-report",
            str(live_report),
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["benchmark_validity_gate"]["status"] == "REVIEW_REQUIRED"
    check = _check_by_id(report, "live_agent.global_capability_inventory")
    assert check["status"] == "REVIEW"
    assert check["details"]["inventory_count"] == 0
    assert "missing" in check["summary"]


def test_evidence_gate_missing_frozen_live_run_is_invalid(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    payload["runs"] = [run for run in payload["runs"] if run["condition"] != "no-skill"]
    live_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    matrix_check = next(
        check
        for check in report["benchmark_validity_gate"]["checks"]
        if check["id"] == "live_agent.matrix_completeness"
    )
    assert matrix_check["status"] == "FAIL"
    assert matrix_check["details"]["missing_run_ids"]


def test_evidence_gate_linked_transfer_requires_review_not_independent_claim(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=False)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "REVIEW_REQUIRED"
    assert report["live_agent"]["overlap_report"]["decision"] == "LINKED_TRANSFER"
    assert report["live_agent"]["overlap_report"]["independent_generalization_claim"] is False
    assert any(
        check["id"] == "live_agent.overlap_status" and check["status"] == "REVIEW"
        for check in report["benchmark_validity_gate"]["checks"]
    )


def test_evidence_gate_fails_linked_transfer_with_independent_claim(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=False)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    payload["overlap_report"]["independent_generalization_claim"] = True
    _write_json(live_report, payload)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert _check_by_id(report, "live_agent.overlap_status")["status"] == "FAIL"


def test_evidence_gate_fails_unavailable_overlap_with_independent_claim(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    payload["overlap_report"] = {
        "decision": "UNAVAILABLE",
        "independent_generalization_claim": True,
        "reason": "missing SkillRouter input",
    }
    _write_json(live_report, payload)

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert _check_by_id(report, "live_agent.overlap_status")["status"] == "FAIL"


def test_evidence_gate_verifier_conflict_is_invalid_and_regression_is_reported(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    no_skill_run = next(run for run in payload["runs"] if run["condition"] == "no-skill")
    routed_run = next(run for run in payload["runs"] if run["condition"] == "routed-skill")
    no_skill_run["task_success"] = True
    no_skill_run["verifier_passed"] = True
    no_skill_run["verifier"]["passed"] = True
    routed_run["task_success"] = False
    routed_run["verifier_passed"] = True
    routed_run["verifier"]["passed"] = True
    routed_run["timed_out"] = True
    live_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    assert report["live_agent"]["per_task_regressions"] == [
        {
            "task_id": "sb-task-login",
            "no_skill_success": True,
            "routed_skill_success": False,
        }
    ]
    checks = {
        check["id"]: check["status"]
        for check in report["benchmark_validity_gate"]["checks"]
    }
    assert checks["live_agent.verifier_evidence"] == "FAIL"
    assert checks["live_agent.timeout_process_errors"] == "REVIEW"
    assert checks["live_agent.per_task_regressions"] == "REVIEW"


def test_evidence_gate_detects_top_level_verifier_passed_inconsistency(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    run = payload["runs"][0]
    run["verifier_passed"] = not run["verifier"]["passed"]
    live_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    failing_ids = {
        check["id"]
        for check in report["benchmark_validity_gate"]["checks"]
        if check["status"] == "FAIL"
    }
    assert "live_agent.verifier_evidence" in failing_ids
    assert "live_agent.trace_completeness" in failing_ids


def test_evidence_gate_detects_trace_report_divergence(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    run = payload["runs"][0]
    run["process_exit_code"] = 99
    live_report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = write_evidence_decision_report(
        output_path=tmp_path / "evidence.json",
        external_plan_path=external_plan,
        external_report_path=external_report,
        live_plan_path=live_plan,
        live_report_path=live_report,
    )

    assert report["benchmark_validity_gate"]["status"] == "INVALID_EVIDENCE"
    trace_check = next(
        check
        for check in report["benchmark_validity_gate"]["checks"]
        if check["id"] == "live_agent.trace_completeness"
    )
    assert trace_check["status"] == "FAIL"
    assert any(
        failure.get("field") == "process_exit_code"
        for failure in trace_check["details"]["failures"]
    )


def test_evidence_gate_cli_writes_json_and_markdown(tmp_path):
    external_plan, external_report = _write_external_artifacts(tmp_path)
    live_plan, live_report = _write_live_artifacts(tmp_path, disjoint_overlap=True)
    output = tmp_path / "cli-evidence.json"
    markdown = tmp_path / "cli-evidence.md"

    exit_code = main(
        [
            "v0.3-evidence-gate",
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
            "--external-plan",
            str(external_plan),
            "--external-report",
            str(external_report),
            "--live-plan",
            str(live_plan),
            "--live-report",
            str(live_report),
        ]
    )

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["router_promotion_gate"][
        "decision"
    ] == "KEEP_BASELINE"
    assert "KEEP_BASELINE" in markdown.read_text(encoding="utf-8")


def _write_external_artifacts(
    tmp_path: Path,
    *,
    routers: list[dict[str, str]] | None = None,
) -> tuple[Path, Path]:
    plan_path = tmp_path / "external-plan.json"
    report_path = tmp_path / "external-report.json"
    write_skillrouter_matrix_plan(
        data_root=SKILLROUTER_FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="external-evidence-fixture",
        routers=routers
        or [
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(SKILLROUTER_PREDICTIONS),
                "version": "fixture",
            },
            {
                "router_id": "finetuned-embedding",
                "field_view": "full_body",
                "predictions_path": str(SKILLROUTER_PREDICTIONS),
                "version": "fixture",
            },
        ],
        stress_candidate_sizes=(1, 3),
        matrix_output_path=report_path,
        bootstrap_iterations=200,
    )
    run_skillrouter_matrix(plan_path=plan_path, output_path=report_path)
    return plan_path, report_path


def _write_live_artifacts(
    tmp_path: Path,
    *,
    disjoint_overlap: bool,
) -> tuple[Path, Path]:
    root = tmp_path / "skillsbench"
    shutil.copytree(SKILLSBENCH_FIXTURE, root)
    if disjoint_overlap:
        tasks = [
            json.loads(line)
            for line in (root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for task in tasks:
            task.pop("skillrouter_task_id", None)
        (root / "tasks.jsonl").write_text(
            "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
            encoding="utf-8",
        )
    plan_path = tmp_path / "live-plan.json"
    report_path = tmp_path / "live-report.json"
    write_skillsbench_plan(
        data_root=root,
        output_path=plan_path,
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
        run_id="live-evidence-fixture",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=root / "routed_predictions.json",
        oracle_qualification_path=root / "oracle_qualification.jsonl",
        matrix_output_path=report_path,
        workspace_root=tmp_path / "workspaces",
        router_top_k=1,
        skillrouter_data_root=SKILLROUTER_FIXTURE,
    )
    run_skillsbench_matrix(
        plan_path=plan_path,
        output_path=report_path,
        runner=FakeAgentRunner(exit_code=0, events=[{"type": "final", "message": "ok"}]),
        verifier=FakeVerifier(pass_=True, details={"reason": "fixture pass"}),
    )
    _append_preflight_to_first_trace(report_path, _preflight_inventory())
    return plan_path, report_path


def _check_by_id(report: dict[str, object], check_id: str) -> dict[str, object]:
    return next(
        check
        for check in report["benchmark_validity_gate"]["checks"]
        if check["id"] == check_id
    )


def _write_json(path: Path, payload: dict[str, object], *, update_digest: bool = False) -> None:
    if update_digest and "derived_hashes" in payload:
        payload["derived_hashes"] = _derived_hashes(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if update_digest:
        path.with_name(f"{path.name}.sha256").write_text(
            f"{sha256_file(path)}  {path.name}\n",
            encoding="utf-8",
        )


def _append_preflight_to_first_trace(live_report: Path, preflight: dict[str, object]) -> None:
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    trace_path = Path(payload["runs"][0]["trace_path"])
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace.setdefault("events", []).insert(0, preflight)
    _write_json(trace_path, trace)


def _strip_capability_inventory_surfaces(live_report: Path) -> None:
    payload = json.loads(live_report.read_text(encoding="utf-8"))
    payload.pop("global_capability_inventory", None)
    payload.pop("skill_inventory", None)
    payload.pop("preflight", None)
    for run in payload["runs"]:
        trace_path = Path(run["trace_path"])
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["events"] = [
            _event_without_capability_inventory(event)
            for event in trace.get("events", [])
            if not (isinstance(event, dict) and event.get("type") == "preflight")
        ]
        _write_json(trace_path, trace)
    _write_json(live_report, payload)


def _event_without_capability_inventory(event: object) -> object:
    if not isinstance(event, dict):
        return event
    event = dict(event)
    event.pop("global_capability_inventory", None)
    event.pop("skill_inventory", None)
    event.pop("preflight", None)
    return event


def _preflight_inventory(
    *,
    user_entries: int = 0,
    codex_home_mode: str = "isolated",
    evidence_mode: str = "final-evidence",
) -> dict[str, object]:
    return {
        "type": "preflight",
        "codex_home_mode": codex_home_mode,
        "evidence_mode": evidence_mode,
        "global_capability_inventory": {
            "home_isolated": codex_home_mode == "isolated",
            "user_skill_dir": {
                "status": "ISOLATED_HOME" if codex_home_mode == "isolated" else "SMOKE_ONLY",
                "entry_count": user_entries,
            },
            "admin_skill_dirs": [
                {
                    "status": "ABSENT",
                    "entry_count": 0,
                }
            ],
            "workspace_skill_dirs": {
                "workspace_status": "CLEAR",
                "mounted_entry_count": 0,
                "parent_skill_dirs_checked": 3,
                "empty_parent_skill_dirs": 0,
            },
            "bundled_skills": {"status": "SYSTEM_MANAGED_UNKNOWN"},
        },
    }
