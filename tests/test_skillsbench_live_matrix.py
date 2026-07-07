from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path

import pytest
import jsonschema

import hermes_skilleval.live_agent_skillsbench as live_agent_skillsbench
from hermes_skilleval.cli import main
from hermes_skilleval.live_agent_runtime import (
    AgentRequest,
    FakeAgentRunner,
    FakeVerifier,
    RunnerOutput,
    VerifierResult,
)
from hermes_skilleval.live_agent_skillsbench import (
    SkillsBenchAdapter,
    build_stage2_real_pilot_input_package,
    write_stage2_pilot_routed_prediction_artifacts,
    _canonical_hash,
    _validate_real_runner_preflight,
    run_skillsbench_matrix,
    write_skillsbench_plan,
)


FIXTURE = Path("tests/fixtures/live_agent/skillsbench_tiny")
SKILLROUTER_FIXTURE = Path("tests/fixtures/external/skillrouter_eval_core_tiny")
UPSTREAM_SHA = "a" * 40
STAGE2_APPROVED_ROUTER_CONFIG_SCHEMA = "v0.3.stage2-routed-prediction-router-config.v1"


class _RecordingRunner:
    def __init__(self, *, events: list[dict] | None = None) -> None:
        self.events = events or [_real_preflight()]
        self.requests: list[AgentRequest] = []

    def run(self, request: AgentRequest) -> RunnerOutput:
        self.requests.append(request)
        return RunnerOutput(
            exit_code=0,
            timed_out=False,
            stdout="",
            stderr="",
            events=self.events,
        )


class _PassingDeterministicVerifier:
    def verify(self, request: AgentRequest, output: RunnerOutput) -> VerifierResult:
        return VerifierResult(
            passed=True,
            details={"source": "unit-test-deterministic-verifier"},
        )


def _real_preflight() -> dict:
    return {
        "type": "preflight",
        "codex_home_mode": "isolated",
        "evidence_mode": "final-evidence",
        "global_capability_inventory": {
            "home_isolated": True,
            "user_skill_dir": {"status": "ISOLATED_HOME", "entry_count": 0},
            "admin_skill_dirs": [{"status": "ABSENT", "entry_count": 0}],
            "workspace_skill_dirs": {
                "workspace_status": "CLEAR",
                "mounted_entry_count": 0,
                "parent_skill_dirs_checked": 1,
                "empty_parent_skill_dirs": 0,
            },
            "bundled_skills": {"status": "SYSTEM_MANAGED_UNKNOWN"},
        },
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage2_expected_registry_hash(skills: list[dict]) -> str:
    records = {}
    for skill in skills:
        description = skill["description"]
        body = skill["body"]
        records[skill["skill_id"]] = {
            "skill_id": skill["skill_id"],
            "name": skill["name"],
            "description": description,
            "body": body,
            "skill_hash": _canonical_hash(
                {
                    "skill_id": skill["skill_id"],
                    "name": skill["name"],
                    "description": description,
                    "body": body,
                }
            ),
            "name_hash": _sha256_text(skill["name"]),
            "description_hash": _sha256_text(description),
            "body_hash": _sha256_text(body),
            "public_skill_text_leakage_guard": "PASS",
        }
    return _canonical_hash(dict(sorted(records.items())))


def _write_real_like_pilot_inputs(root: Path) -> dict[str, Path]:
    root.mkdir()
    verifier_dir = root / "verifiers"
    verifier_dir.mkdir()
    (verifier_dir / "check.py").write_text("def verify(): return True\n", encoding="utf-8")
    (verifier_dir / "config.json").write_text('{"mode":"deterministic"}\n', encoding="utf-8")
    (verifier_dir / "input.json").write_text('{"fixture":"unit"}\n', encoding="utf-8")

    skills = []
    tasks = []
    oracle_records = []
    predictions: dict[str, list[str]] = {}
    for index in range(4):
        task_id = f"sb-real-{index + 1}"
        skill_id = f"skill/real-{index + 1}"
        skill = {
            "skill_id": skill_id,
            "name": f"Real Pilot Skill {index + 1}",
            "description": f"Deterministic helper for pilot task {index + 1}.",
            "body": f"Follow the deterministic procedure for pilot task {index + 1}.",
        }
        verifier = {
            "type": "deterministic",
            "name": f"real-verifier-{index + 1}",
            "code_path": "verifiers/check.py",
            "config_path": "verifiers/config.json",
            "input_path": "verifiers/input.json",
            "expected_output_format": {
                "type": "json",
                "required_fields": ["passed", "details"],
            },
            "constraints": {
                "credentials": "none",
                "network": "none",
                "local_execution": True,
            },
            "deterministic_assumptions": {
                "network": "disabled",
                "clock": "not_used",
                "randomness": "not_used",
            },
        }
        task = {
            "task_id": task_id,
            "prompt": f"Complete the deterministic pilot activity number {index + 1}.",
            "verifier": verifier,
            "requires_private_credentials": False,
            "network": "none",
            "oracle_skill_ids": [skill_id],
            "source": "approved-unit-real-pilot-source",
            "provenance": {"upstream_task_id": f"upstream-{index + 1}"},
        }
        metadata = {
            "source": task["source"],
            "provenance": task["provenance"],
        }
        task_hash = _canonical_hash(
            {
                "task_id": task_id,
                "prompt": task["prompt"],
                "verifier": verifier,
                "oracle_skill_ids": [skill_id],
                "network": "none",
                "requires_private_credentials": False,
                "metadata": metadata,
            }
        )
        skill_hash = _canonical_hash(
            {
                "skill_id": skill_id,
                "name": skill["name"],
                "description": skill["description"],
                "body": skill["body"],
            }
        )
        oracle_records.append(
            {
                "task_id": task_id,
                "condition": "oracle-skill",
                "verifier_passed": True,
                "task_hash": task_hash,
                "verifier_hash": _canonical_hash(verifier),
                "skill_hash": skill_hash,
                "skill_id": skill_id,
                "trials": 1,
                "pass_rate": 1.0,
                "constraints": {
                    "credentials": "none",
                    "network": "none",
                    "verifier": "deterministic",
                },
                "qualification_command": "python verifiers/check.py --qualification",
                "output_hash": "d" * 64,
            }
        )
        skills.append(skill)
        tasks.append(task)
        predictions[task_id] = [skill_id]

    (root / "tasks.jsonl").write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    (root / "skills.jsonl").write_text(
        "".join(json.dumps(skill, sort_keys=True) + "\n" for skill in skills),
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": "approved-unit-real-pilot-source",
                "license_note": "approved-real-pilot-unit",
                "upstream_ref": UPSTREAM_SHA,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "oracle_qualification.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in oracle_records),
        encoding="utf-8",
    )
    registry_hash = _stage2_expected_registry_hash(skills)
    (root / "routed_predictions.json").write_text(
        json.dumps(
            {
                "schema_version": "v0.3.routed-predictions.v1",
                "router": {
                    "router_id": "unit-router",
                    "config_id": "unit-router-config",
                    "config_hash": "c" * 64,
                    "top_k": 1,
                    "global_skill_registry_hash": registry_hash,
                    "generation_command": "python -m hermes_skilleval.cli route-skills",
                    "oracle_labels_read": False,
                    "label_source": "router_predictions",
                },
                "predictions": predictions,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "data_root": root,
        "routed_predictions": root / "routed_predictions.json",
        "oracle_qualification": root / "oracle_qualification.jsonl",
    }


def _export_stage2_routed_predictions(paths: dict[str, Path], output_dir: Path) -> dict:
    return write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills.jsonl",
        output_path=output_dir / "routed_predictions.json",
        manifest_output_path=output_dir / "routed_predictions.manifest.json",
        router_id="keyword",
        config_id="stage2-keyword-unit",
        top_k=1,
        generation_command=[
            "python",
            "-m",
            "hermes_skilleval.cli",
            "skillsbench-export-routed-predictions",
        ],
    )


def _write_stage2_approved_router_config(
    paths: dict[str, Path],
    output_path: Path,
    *,
    router_id: str = "keyword",
    config_id: str = "stage2-keyword-unit",
    top_k: int = 1,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    skills = _read_jsonl_file(paths["data_root"] / "skills.jsonl")
    config = {
        "schema_version": STAGE2_APPROVED_ROUTER_CONFIG_SCHEMA,
        "config_id": config_id,
        "router_id": router_id,
        "top_k": top_k,
        "global_skill_registry_hash": _stage2_expected_registry_hash(skills),
        "approval": {
            "source": "unit-test-approved-router-config",
            "approved_for": "stage2-routed-prediction-export",
        },
    }
    output_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _patch_stage2_clean_code_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        live_agent_skillsbench,
        "_stage2_export_code_provenance",
        lambda *args, **kwargs: {
            "commit": "d" * 40,
            "tag": "v0.3-test",
            "dirty": False,
            "dirty_paths": [],
        },
        raising=False,
    )


def _write_real_like_pilot_plan(tmp_path: Path) -> tuple[Path, Path]:
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    plan_path = tmp_path / "plan.json"
    matrix_path = tmp_path / "matrix.json"
    write_skillsbench_plan(
        data_root=paths["data_root"],
        output_path=plan_path,
        upstream_ref=UPSTREAM_SHA,
        license_note="approved-real-pilot-unit",
        run_id="stage2-real-pilot-prep",
        mode="pilot",
        selected_task_ids=[f"sb-real-{index}" for index in range(1, 5)],
        routed_predictions_path=paths["routed_predictions"],
        oracle_qualification_path=paths["oracle_qualification"],
        matrix_output_path=matrix_path,
        workspace_root=tmp_path / "workspaces",
        router_top_k=1,
    )
    return plan_path, matrix_path


def _rewrite_plan_digest(plan_path: Path) -> None:
    import hashlib

    digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    (plan_path.parent / f"{plan_path.name}.sha256").write_text(
        f"{digest}  {plan_path.name}\n",
        encoding="utf-8",
    )


def _mutate_plan(plan_path: Path, mutator) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    mutator(plan)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _rewrite_plan_digest(plan_path)


def _read_jsonl_file(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl_file(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _build_real_like_pilot_input_package(paths: dict[str, Path]) -> dict:
    return build_stage2_real_pilot_input_package(
        data_root=paths["data_root"],
        upstream_ref=UPSTREAM_SHA,
        license_note="approved-real-pilot-unit",
        run_id="stage2-real-pilot-input-package-unit",
        selected_task_ids=[f"sb-real-{index}" for index in range(1, 5)],
        routed_predictions_path=paths["routed_predictions"],
        oracle_qualification_path=paths["oracle_qualification"],
        router_top_k=1,
    )


def test_skillsbench_adapter_validates_tiny_fixture():
    adapter = SkillsBenchAdapter(
        data_root=FIXTURE,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
    )

    validation = adapter.validate()

    assert validation["status"] == "PASS"
    assert validation["task_count"] == 2
    assert validation["skill_count"] == 3


def test_skillsbench_adapter_fails_closed_for_unselectable_task(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
    with (root / "tasks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "task_id": "bad-private",
                    "prompt": "Do private work",
                    "verifier": {"type": "deterministic", "name": "fixture"},
                    "requires_private_credentials": True,
                    "network": "none",
                    "oracle_skill_ids": ["skill/browser-login"],
                },
                sort_keys=True,
            )
            + "\n"
        )

    validation = SkillsBenchAdapter(
        data_root=root,
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
    ).validate()

    assert validation["status"] == "INVALID"
    assert any("private credentials" in error for error in validation["errors"])


def test_frozen_plan_requires_oracle_qualification(tmp_path):
    with pytest.raises(ValueError, match="oracle qualification"):
        write_skillsbench_plan(
            data_root=FIXTURE,
            output_path=tmp_path / "plan.json",
            upstream_ref="fixture-ref",
            license_note="fixture-only",
            run_id="skillsbench-run",
            mode="frozen",
            selected_task_ids=["sb-task-login"],
            routed_predictions_path=FIXTURE / "routed_predictions.json",
            oracle_qualification_path=None,
        )


def test_plan_builds_global_registry_and_three_conditions(tmp_path):
    plan = write_skillsbench_plan(
        data_root=FIXTURE,
        output_path=tmp_path / "plan.json",
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login", "sb-task-edit"],
        routed_predictions_path=FIXTURE / "routed_predictions.json",
        oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
        matrix_output_path=tmp_path / "matrix.json",
        router_top_k=1,
        skillrouter_data_root=SKILLROUTER_FIXTURE,
    )

    assert plan["mode"] == "frozen"
    assert plan["router_top_k"] == 1
    assert set(plan["global_skill_registry"]) == {
        "skill/browser-login",
        "skill/file-edit",
        "skill/network-check",
    }
    assert len(plan["matrix"]) == 6
    by_task: dict[str, set[str]] = {}
    hashes_by_task: dict[str, set[str]] = {}
    workspaces = []
    for entry in plan["matrix"]:
        by_task.setdefault(entry["task_id"], set()).add(entry["condition"])
        hashes_by_task.setdefault(entry["task_id"], set()).add(entry["prompt_hash"])
        workspaces.append(entry["workspace_run_id"])
    assert all(conditions == {"no-skill", "routed-skill", "oracle-skill"} for conditions in by_task.values())
    assert all(len(hashes) == 1 for hashes in hashes_by_task.values())
    assert len(workspaces) == len(set(workspaces))
    assert plan["scope_guards"]["no_router_training"] is True
    assert plan["overlap_report"]["exact_id_overlap"] == []
    assert plan["overlap_report"]["declared_metadata_links"] == [
        "task-multi-hard",
        "task-single-easy",
    ]
    assert plan["overlap_report"]["decision"] == "LINKED_TRANSFER"
    assert plan["overlap_report"]["independent_generalization_claim"] is False
    assert (tmp_path / "plan.json.sha256").is_file()


def test_matrix_execution_records_traces_and_uses_verifier_success(tmp_path):
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillsbench_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=FIXTURE / "routed_predictions.json",
        oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
        matrix_output_path=output_path,
        workspace_root=tmp_path / "workspaces",
        router_top_k=1,
    )

    report = run_skillsbench_matrix(
        plan_path=plan_path,
        output_path=output_path,
        runner=FakeAgentRunner(exit_code=0, events=[{"type": "final", "message": "ok"}]),
        verifier=FakeVerifier(pass_=False, details={"reason": "fixture failure"}),
    )

    assert report["schema_version"] == "v0.3.skillsbench-live-matrix-report.v1"
    assert len(report["runs"]) == 3
    assert set(report["skill_inventory"]) == {"skill/browser-login", "skill/file-edit"}
    assert all(run["task_success"] is False for run in report["runs"])
    assert all(run["verifier"]["passed"] is False for run in report["runs"])
    assert all(run["verifier"]["source"] == "deterministic" for run in report["runs"])
    assert all(Path(run["trace_path"]).is_file() for run in report["runs"])
    assert any(run["mounted_skill_ids"] == ["skill/browser-login"] for run in report["runs"])
    assert report["summary"]["task_success_source"] == "verifier_pass_fail"
    schema = json.loads(Path("schemas/live-agent-trace.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(
        json.loads(Path(report["runs"][0]["trace_path"]).read_text(encoding="utf-8")),
        schema,
    )


def test_matrix_fails_when_frozen_task_input_changes(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillsbench_plan(
        data_root=root,
        output_path=plan_path,
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=root / "routed_predictions.json",
        oracle_qualification_path=root / "oracle_qualification.jsonl",
        matrix_output_path=output_path,
    )
    with (root / "tasks.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    with pytest.raises(ValueError, match="frozen input changed"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=output_path,
            runner=FakeAgentRunner(),
            verifier=FakeVerifier(pass_=True),
        )


def test_matrix_fails_when_frozen_skill_input_changes(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillsbench_plan(
        data_root=root,
        output_path=plan_path,
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=root / "routed_predictions.json",
        oracle_qualification_path=root / "oracle_qualification.jsonl",
        matrix_output_path=output_path,
    )
    with (root / "skills.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    with pytest.raises(ValueError, match="frozen input changed"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=output_path,
            runner=FakeAgentRunner(),
            verifier=FakeVerifier(pass_=True),
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda plan: plan["selected_tasks"][0].__setitem__("prompt", "tampered prompt"),
            "selected_tasks",
        ),
        (
            lambda plan: plan["selected_tasks"][0].__setitem__(
                "verifier",
                {"type": "deterministic", "name": "tampered"},
            ),
            "selected_tasks",
        ),
        (
            lambda plan: plan["global_skill_registry"]["skill/browser-login"].__setitem__(
                "name",
                "Tampered Skill",
            ),
            "global_skill_registry",
        ),
        (
            lambda plan: plan["global_skill_registry"]["skill/browser-login"].__setitem__(
                "description",
                "Tampered description",
            ),
            "global_skill_registry",
        ),
        (
            lambda plan: plan["global_skill_registry"]["skill/browser-login"].__setitem__(
                "body",
                "Tampered body",
            ),
            "global_skill_registry",
        ),
        (
            lambda plan: plan["matrix"][0].__setitem__("condition", "oracle-skill"),
            "matrix",
        ),
        (
            lambda plan: plan["matrix"][1].__setitem__(
                "mounted_skill_ids",
                ["skill/browser-login", "skill/file-edit"],
            ),
            "matrix",
        ),
    ],
)
def test_matrix_fails_when_plan_derived_fields_are_mutated(tmp_path, mutator, message):
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillsbench_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=FIXTURE / "routed_predictions.json",
        oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
        matrix_output_path=output_path,
        router_top_k=1,
    )
    _mutate_plan(plan_path, mutator)

    with pytest.raises(ValueError, match=message):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=output_path,
            runner=FakeAgentRunner(),
            verifier=FakeVerifier(pass_=True),
        )


def test_matrix_fails_when_plan_digest_sidecar_changes(tmp_path):
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillsbench_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=FIXTURE / "routed_predictions.json",
        oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
        matrix_output_path=output_path,
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["selected_tasks"][0]["prompt"] = "tampered prompt"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="plan digest changed"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=output_path,
            runner=FakeAgentRunner(),
            verifier=FakeVerifier(pass_=True),
        )


def test_routed_condition_mounts_deduped_top_k_and_unknown_predictions_fail(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
    predictions = {
        "sb-task-login": [
            "skill/browser-login",
            "skill/browser-login",
            "skill/file-edit",
            "skill/network-check",
        ],
        "sb-task-edit": ["skill/file-edit", "skill/network-check"],
    }
    predictions_path = root / "routed_predictions.json"
    predictions_path.write_text(json.dumps(predictions, sort_keys=True), encoding="utf-8")

    plan = write_skillsbench_plan(
        data_root=root,
        output_path=tmp_path / "plan.json",
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=predictions_path,
        oracle_qualification_path=root / "oracle_qualification.jsonl",
        router_top_k=2,
    )

    routed_entry = next(entry for entry in plan["matrix"] if entry["condition"] == "routed-skill")
    assert routed_entry["mounted_skill_ids"] == ["skill/browser-login", "skill/file-edit"]
    assert plan["routing_diagnostics"]["sb-task-login"]["full_prediction_count"] == 4
    assert plan["routing_diagnostics"]["sb-task-login"]["mounted_top_k"] == [
        "skill/browser-login",
        "skill/file-edit",
    ]

    predictions["sb-task-login"] = ["skill/missing"]
    predictions_path.write_text(json.dumps(predictions, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="missing skill definition"):
        write_skillsbench_plan(
            data_root=root,
            output_path=tmp_path / "bad-plan.json",
            upstream_ref=UPSTREAM_SHA,
            license_note="fixture-only",
            run_id="skillsbench-run",
            mode="frozen",
            selected_task_ids=["sb-task-login"],
            routed_predictions_path=predictions_path,
            oracle_qualification_path=root / "oracle_qualification.jsonl",
            router_top_k=2,
        )


def test_overlap_report_marks_unavailable_without_skillrouter_inputs(tmp_path):
    plan = write_skillsbench_plan(
        data_root=FIXTURE,
        output_path=tmp_path / "plan.json",
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=FIXTURE / "routed_predictions.json",
        oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
    )

    assert plan["overlap_report"]["decision"] == "UNAVAILABLE"
    assert plan["overlap_report"]["independent_generalization_claim"] is False


def test_overlap_report_marks_disjoint_with_skillrouter_inputs(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
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

    plan = write_skillsbench_plan(
        data_root=root,
        output_path=tmp_path / "plan.json",
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=root / "routed_predictions.json",
        oracle_qualification_path=root / "oracle_qualification.jsonl",
        skillrouter_data_root=SKILLROUTER_FIXTURE,
    )

    assert plan["overlap_report"]["decision"] == "DISJOINT"
    assert plan["overlap_report"]["independent_generalization_claim"] is True


def test_overlap_report_uses_skillrouter_tasks_instruction_text(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
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
    skillrouter_tasks = tmp_path / "skillrouter-tasks.jsonl"
    skillrouter_tasks.write_text(
        json.dumps(
            {
                "task_id": "sr-text-match",
                "instruction_text": "Log in to the fixture app and verify the dashboard text.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    plan = write_skillsbench_plan(
        data_root=root,
        output_path=tmp_path / "plan.json",
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
        run_id="skillsbench-run",
        mode="frozen",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=root / "routed_predictions.json",
        oracle_qualification_path=root / "oracle_qualification.jsonl",
        skillrouter_tasks_path=skillrouter_tasks,
    )

    assert plan["overlap_report"]["decision"] == "LINKED_TRANSFER"
    assert plan["overlap_report"]["normalized_text_hash_overlap"]
    assert plan["overlap_report"]["normalized_text_hash_overlap_records"][0][
        "skillrouter_task_ids"
    ] == ["sr-text-match"]
    assert plan["overlap_report"]["normalized_text_hash_overlap_records"][0][
        "skillsbench_task_ids"
    ] == ["sb-task-login"]


def test_skillrouter_overlap_inputs_are_mutually_exclusive(tmp_path):
    with pytest.raises(ValueError, match="mutually exclusive"):
        write_skillsbench_plan(
            data_root=FIXTURE,
            output_path=tmp_path / "plan.json",
            upstream_ref="fixture-ref",
            license_note="fixture-only",
            run_id="skillsbench-run",
            mode="frozen",
            selected_task_ids=["sb-task-login"],
            routed_predictions_path=FIXTURE / "routed_predictions.json",
            oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
            skillrouter_data_root=SKILLROUTER_FIXTURE,
            skillrouter_tasks_path=SKILLROUTER_FIXTURE / "tasks.jsonl",
        )


def test_leakage_scan_rejects_oracle_labels_in_prompt_or_skill_name(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)
    tasks = [
        json.loads(line)
        for line in (root / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tasks[0]["prompt"] = "Use skill/browser-login for this task"
    (root / "tasks.jsonl").write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    validation = SkillsBenchAdapter(
        data_root=root,
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
    ).validate()
    assert validation["status"] == "INVALID"
    assert any("leakage" in error for error in validation["errors"])

    root = tmp_path / "skillsbench-name"
    shutil.copytree(FIXTURE, root)
    skills = [
        json.loads(line)
        for line in (root / "skills.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    skills[0]["name"] = "gold oracle skill/browser-login"
    (root / "skills.jsonl").write_text(
        "".join(json.dumps(skill, sort_keys=True) + "\n" for skill in skills),
        encoding="utf-8",
    )
    validation = SkillsBenchAdapter(
        data_root=root,
        upstream_ref=UPSTREAM_SHA,
        license_note="fixture-only",
    ).validate()
    assert validation["status"] == "INVALID"
    assert any("leakage" in error for error in validation["errors"])


def test_frozen_upstream_ref_requires_commit_sha_outside_fixture_or_pilot(tmp_path):
    root = tmp_path / "skillsbench"
    shutil.copytree(FIXTURE, root)

    validation = SkillsBenchAdapter(
        data_root=root,
        upstream_ref="branch-name",
        license_note="fixture-only",
    ).validate()

    assert validation["status"] == "INVALID"
    assert any("commit SHA" in error for error in validation["errors"])
    with pytest.raises(ValueError, match="SkillsBench validation failed"):
        write_skillsbench_plan(
            data_root=root,
            output_path=tmp_path / "bad-frozen-plan.json",
            upstream_ref="fixture-ref",
            license_note="fixture-only",
            run_id="skillsbench-run",
            mode="frozen",
            selected_task_ids=["sb-task-login"],
            routed_predictions_path=root / "routed_predictions.json",
            oracle_qualification_path=root / "oracle_qualification.jsonl",
        )

    write_skillsbench_plan(
        data_root=root,
        output_path=tmp_path / "pilot-plan.json",
        upstream_ref="branch-name",
        license_note="fixture-only",
        run_id="skillsbench-pilot",
        mode="pilot",
        selected_task_ids=["sb-task-login"],
        routed_predictions_path=root / "routed_predictions.json",
    )


def test_real_evidence_mode_rejects_fake_runner_and_verifier(tmp_path):
    plan_path, matrix_path = _write_real_like_pilot_plan(tmp_path)

    with pytest.raises(ValueError, match="FakeAgentRunner"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=matrix_path,
            runner=FakeAgentRunner(),
            verifier=_PassingDeterministicVerifier(),
            evidence_mode="real",
        )

    with pytest.raises(ValueError, match="FakeVerifier"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=matrix_path,
            runner=_RecordingRunner(),
            verifier=FakeVerifier(pass_=True),
            evidence_mode="real",
        )


def test_real_evidence_mode_rejects_fixture_only_skillsbench_data(tmp_path):
    plan_path = tmp_path / "fixture-plan.json"
    matrix_path = tmp_path / "fixture-matrix.json"
    write_skillsbench_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="fixture-pilot",
        mode="pilot",
        selected_task_ids=["sb-task-login", "sb-task-edit"],
        routed_predictions_path=FIXTURE / "routed_predictions.json",
        oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
        matrix_output_path=matrix_path,
    )

    with pytest.raises(ValueError, match="fixture-only SkillsBench data"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=matrix_path,
            runner=_RecordingRunner(),
            verifier=_PassingDeterministicVerifier(),
            evidence_mode="real",
        )


def test_real_evidence_mode_requires_no_skill_preflight(tmp_path):
    plan_path, matrix_path = _write_real_like_pilot_plan(tmp_path)

    with pytest.raises(ValueError, match="missing real runner preflight"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=matrix_path,
            runner=_RecordingRunner(events=[{"type": "final", "message": "ok"}]),
            verifier=_PassingDeterministicVerifier(),
            evidence_mode="real",
        )


def test_real_evidence_mode_defaults_workspace_root_outside_output_tree(
    tmp_path, monkeypatch
):
    plan_path, matrix_path = _write_real_like_pilot_plan(tmp_path)
    _mutate_plan(plan_path, lambda plan: plan.__setitem__("workspace_root", None))
    runtime_root = tmp_path / "external-runtime"
    monkeypatch.setenv(
        "HERMES_SKILLEVAL_REAL_WORKSPACE_ROOT",
        str(runtime_root),
    )
    runner = _RecordingRunner()

    report = run_skillsbench_matrix(
        plan_path=plan_path,
        output_path=matrix_path,
        runner=runner,
        verifier=_PassingDeterministicVerifier(),
        evidence_mode="real",
    )

    assert report["workspace_root"].startswith(str(runtime_root))
    assert all(
        request.workspace_path.is_relative_to(runtime_root)
        for request in runner.requests
    )
    assert not (matrix_path.parent / "workspaces").exists()


def test_real_evidence_mode_rejects_workspace_parent_skill_leakage(tmp_path):
    plan_path, matrix_path = _write_real_like_pilot_plan(tmp_path)
    unsafe_parent = tmp_path / "unsafe-parent"
    leaked_skill = unsafe_parent / ".agents" / "skills" / "leaked-skill"
    leaked_skill.mkdir(parents=True)
    _mutate_plan(
        plan_path,
        lambda plan: plan.__setitem__(
            "workspace_root",
            str(unsafe_parent / "workspaces"),
        ),
    )

    with pytest.raises(ValueError, match="workspace parent skill leakage"):
        run_skillsbench_matrix(
            plan_path=plan_path,
            output_path=matrix_path,
            runner=_RecordingRunner(),
            verifier=_PassingDeterministicVerifier(),
            evidence_mode="real",
        )


@pytest.mark.parametrize(
    "events",
    [
        [],
        [{"type": "final", "message": "ok"}],
        ["malformed"],
    ],
)
def test_real_runner_preflight_requires_preflight_record(events):
    with pytest.raises(ValueError, match="missing real runner preflight"):
        _validate_real_runner_preflight(events)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda preflight: preflight.__setitem__("evidence_mode", "smoke-only"),
            "final-evidence",
        ),
        (
            lambda preflight: preflight.__setitem__("codex_home_mode", "inherit"),
            "isolated CODEX_HOME",
        ),
        (
            lambda preflight: preflight.pop("global_capability_inventory"),
            "global_capability_inventory",
        ),
        (
            lambda preflight: preflight.__setitem__(
                "global_capability_inventory",
                ["malformed"],
            ),
            "global_capability_inventory",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"].__setitem__(
                "home_isolated",
                False,
            ),
            "home_isolated",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "user_skill_dir"
            ].__setitem__("status", "CLEAR"),
            "user_skill_dir",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "user_skill_dir"
            ].__setitem__("entry_count", 1),
            "user_skill_dir",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"].__setitem__(
                "admin_skill_dirs",
                {"status": "CLEAR", "entry_count": 0},
            ),
            "admin_skill_dirs",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "admin_skill_dirs"
            ][0].__setitem__("status", "LEAKED"),
            "admin_skill_dirs",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "admin_skill_dirs"
            ][0].__setitem__("entry_count", 1),
            "admin_skill_dirs",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"].pop(
                "workspace_skill_dirs"
            ),
            "workspace_skill_dirs",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "workspace_skill_dirs"
            ].__setitem__("workspace_status", "LEAKED"),
            "workspace_skill_dirs",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "workspace_skill_dirs"
            ].__setitem__("parent_skill_dirs_checked", "many"),
            "workspace_skill_dirs",
        ),
        (
            lambda preflight: preflight["global_capability_inventory"][
                "workspace_skill_dirs"
            ].__setitem__("empty_parent_skill_dirs", 2),
            "workspace_skill_dirs",
        ),
    ],
)
def test_real_runner_preflight_rejects_malformed_or_leaky_records(
    mutator,
    message,
):
    preflight = json.loads(json.dumps(_real_preflight()))
    mutator(preflight)

    with pytest.raises(ValueError, match=message):
        _validate_real_runner_preflight([preflight])


def test_stage2_pilot_plan_records_task_verifier_oracle_and_routing_hashes(tmp_path):
    plan_path, _matrix_path = _write_real_like_pilot_plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert plan["mode"] == "pilot"
    assert plan["evidence_label"] == "pilot_non_final"
    assert len(plan["selected_tasks"]) == 4
    assert len(plan["matrix"]) == 12
    assert {entry["condition"] for entry in plan["matrix"]} == {
        "no-skill",
        "routed-skill",
        "oracle-skill",
    }
    assert plan["global_skill_registry_hash"] == _canonical_hash(
        plan["global_skill_registry"]
    )
    assert plan["routing_provenance"]["router"]["router_id"] == "unit-router"
    assert plan["routing_provenance"]["router"]["config_hash"] == "c" * 64
    assert plan["routing_provenance"]["router"]["top_k"] == 1

    selected_by_id = {task["task_id"]: task for task in plan["selected_tasks"]}
    assert all(task["prompt_hash"] for task in selected_by_id.values())
    assert all(task["task_hash"] for task in selected_by_id.values())
    assert all(task["verifier_hash"] for task in selected_by_id.values())
    assert all(
        set(task["verifier_artifacts"]) == {"code", "config", "input"}
        for task in selected_by_id.values()
    )

    for task_id, record in plan["oracle_qualification_records"].items():
        task = selected_by_id[task_id]
        assert record["task_hash"] == task["task_hash"]
        assert record["verifier_hash"] == task["verifier_hash"]
        assert record["skill_hash"]
        assert record["trials"] == 1
        assert record["pass_rate"] == 1.0
        assert record["constraints"]

    for task_id, record in plan["routed_prediction_records"].items():
        assert task_id in selected_by_id
        assert record["router_id"] == "unit-router"
        assert record["router_config_hash"] == "c" * 64
        assert record["router_top_k"] == 1
        assert record["global_skill_registry_hash"] == plan["global_skill_registry_hash"]
        assert record["prediction_hash"]


def test_stage2_real_pilot_input_package_rejects_fixture_only_data_root():
    with pytest.raises(ValueError, match="fixture-only SkillsBench data"):
        build_stage2_real_pilot_input_package(
            data_root=FIXTURE,
            upstream_ref="fixture-ref",
            license_note="fixture-only",
            run_id="stage2-real-pilot-input-package-unit",
            selected_task_ids=["sb-task-login", "sb-task-edit"],
            routed_predictions_path=FIXTURE / "routed_predictions.json",
            oracle_qualification_path=FIXTURE / "oracle_qualification.jsonl",
            router_top_k=1,
        )


def test_stage2_real_pilot_input_package_requires_exactly_four_tasks(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")

    with pytest.raises(ValueError, match="exactly 4 selected tasks"):
        build_stage2_real_pilot_input_package(
            data_root=paths["data_root"],
            upstream_ref=UPSTREAM_SHA,
            license_note="approved-real-pilot-unit",
            run_id="stage2-real-pilot-input-package-unit",
            selected_task_ids=["sb-real-1", "sb-real-2", "sb-real-3"],
            routed_predictions_path=paths["routed_predictions"],
            oracle_qualification_path=paths["oracle_qualification"],
            router_top_k=1,
        )


def test_stage2_real_pilot_input_package_missing_verifier_hashes_fail_closed(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    tasks = _read_jsonl_file(paths["data_root"] / "tasks.jsonl")
    tasks[0]["verifier"].pop("code_path")
    _write_jsonl_file(paths["data_root"] / "tasks.jsonl", tasks)

    with pytest.raises(ValueError, match="missing verifier code/config/input hashes"):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_missing_source_provenance_fails_closed(
    tmp_path,
):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    tasks = _read_jsonl_file(paths["data_root"] / "tasks.jsonl")
    tasks[0].pop("source")
    tasks[0].pop("provenance")
    _write_jsonl_file(paths["data_root"] / "tasks.jsonl", tasks)

    with pytest.raises(ValueError, match="missing task source/provenance: sb-real-1"):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_missing_oracle_qualification_fail_closed(
    tmp_path,
):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    records = _read_jsonl_file(paths["oracle_qualification"])
    _write_jsonl_file(paths["oracle_qualification"], records[:-1])

    with pytest.raises(ValueError, match="missing oracle qualification: sb-real-4"):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_unknown_routed_skill_fails_closed(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    predictions = json.loads(paths["routed_predictions"].read_text(encoding="utf-8"))
    predictions["predictions"]["sb-real-2"] = ["skill/unknown"]
    paths["routed_predictions"].write_text(
        json.dumps(predictions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown routed prediction skill id"):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_missing_routing_provenance_fails_closed(
    tmp_path,
):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    routed = json.loads(paths["routed_predictions"].read_text(encoding="utf-8"))
    routed["router"].pop("generation_command")
    paths["routed_predictions"].write_text(
        json.dumps(routed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing routed prediction generation provenance"):
        _build_real_like_pilot_input_package(paths)


def test_stage2_routed_prediction_exporter_writes_validator_ready_artifacts(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    export = _export_stage2_routed_predictions(paths, tmp_path / "export")
    routed_path = Path(export["output_path"])
    manifest_path = Path(export["manifest_output_path"])

    routed = json.loads(routed_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert routed["schema_version"] == "v0.3.routed-predictions.v1"
    assert routed["router"]["router_id"] == "keyword"
    assert routed["router"]["config_id"] == "stage2-keyword-unit"
    assert routed["router"]["config_hash"]
    assert routed["router"]["global_skill_registry_hash"] == _stage2_expected_registry_hash(
        _read_jsonl_file(paths["data_root"] / "skills.jsonl")
    )
    assert routed["router"]["oracle_labels_read"] is False
    assert routed["router"]["label_source"] == "router_generated"
    assert routed["router"]["generation_artifact_hash"]
    assert manifest["output"]["sha256"]
    assert set(routed["predictions"]) == {f"sb-real-{index}" for index in range(1, 5)}
    assert all(len(prediction) == 1 for prediction in routed["predictions"].values())
    assert set(manifest["per_task_prediction_hashes"]) == set(routed["predictions"])

    package = build_stage2_real_pilot_input_package(
        data_root=paths["data_root"],
        upstream_ref=UPSTREAM_SHA,
        license_note="approved-real-pilot-unit",
        run_id="stage2-real-pilot-input-package-unit",
        selected_task_ids=[f"sb-real-{index}" for index in range(1, 5)],
        routed_predictions_path=routed_path,
        oracle_qualification_path=paths["oracle_qualification"],
        router_top_k=1,
    )

    assert package["status"] == "READY_FOR_REVIEW_NOT_EXECUTED"
    assert package["routed_predictions_package"]["label_source"] == "router_generated"
    assert package["routed_predictions_package"]["config_id"] == "stage2-keyword-unit"


def test_stage2_routed_prediction_exporter_rejects_fixture_final_evidence(tmp_path):
    with pytest.raises(ValueError, match="fixture routing cannot be exported as final evidence"):
        write_stage2_pilot_routed_prediction_artifacts(
            tasks_manifest_path=FIXTURE / "tasks.jsonl",
            global_skill_registry_path=FIXTURE / "skills.jsonl",
            output_path=tmp_path / "routed_predictions.json",
            manifest_output_path=tmp_path / "manifest.json",
            router_id="keyword",
            config_id="stage2-keyword-unit",
            top_k=1,
            final_evidence=True,
        )


def test_stage2_routed_prediction_final_evidence_requires_approved_router_config(
    tmp_path,
    monkeypatch,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")

    with pytest.raises(ValueError, match="approved router config is required"):
        write_stage2_pilot_routed_prediction_artifacts(
            tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
            global_skill_registry_path=paths["data_root"] / "skills.jsonl",
            output_path=tmp_path / "routed_predictions.json",
            manifest_output_path=tmp_path / "manifest.json",
            router_id="keyword",
            config_id="stage2-keyword-unit",
            top_k=1,
            final_evidence=True,
        )


def test_stage2_routed_prediction_final_evidence_rejects_config_id_mismatch(
    tmp_path,
    monkeypatch,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / "approved-router-config.json",
        config_id="different-approved-config",
    )

    with pytest.raises(ValueError, match="router config_id mismatch"):
        write_stage2_pilot_routed_prediction_artifacts(
            tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
            global_skill_registry_path=paths["data_root"] / "skills.jsonl",
            output_path=tmp_path / "routed_predictions.json",
            manifest_output_path=tmp_path / "manifest.json",
            router_id="keyword",
            config_id="stage2-keyword-unit",
            top_k=1,
            approved_router_config_path=config_path,
            final_evidence=True,
        )


def test_stage2_routed_prediction_final_evidence_records_config_hash_stably(
    tmp_path,
    monkeypatch,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / "approved-router-config.json",
    )

    first = write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills.jsonl",
        output_path=tmp_path / "first" / "routed_predictions.json",
        manifest_output_path=tmp_path / "first" / "manifest.json",
        router_id="keyword",
        config_id="stage2-keyword-unit",
        top_k=1,
        approved_router_config_path=config_path,
        final_evidence=True,
    )
    second = write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills.jsonl",
        output_path=tmp_path / "second" / "routed_predictions.json",
        manifest_output_path=tmp_path / "second" / "manifest.json",
        router_id="keyword",
        config_id="stage2-keyword-unit",
        top_k=1,
        approved_router_config_path=config_path,
        final_evidence=True,
    )

    routed = json.loads(Path(first["output_path"]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(first["manifest_output_path"]).read_text(encoding="utf-8"))
    expected_hash = _sha256_file(config_path)

    assert first["config_hash"] == second["config_hash"] == expected_hash
    assert routed["router"]["config_hash"] == expected_hash
    assert routed["router"]["router_config"]["sha256"] == expected_hash
    assert manifest["router_config"] == routed["router"]["router_config"]
    assert manifest["router_config"]["schema_version"] == STAGE2_APPROVED_ROUTER_CONFIG_SCHEMA
    assert manifest["router_config"]["config_id"] == "stage2-keyword-unit"
    assert manifest["router_config"]["size_bytes"] == config_path.stat().st_size


@pytest.mark.parametrize("router_id", ["keyword", "hybrid"])
def test_stage2_routed_prediction_final_evidence_allows_keyword_and_hybrid(
    tmp_path,
    monkeypatch,
    router_id,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / f"skillsbench-real-{router_id}")
    config_id = f"stage2-{router_id}-unit"
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / router_id / "approved-router-config.json",
        router_id=router_id,
        config_id=config_id,
    )

    export = write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills.jsonl",
        output_path=tmp_path / router_id / "routed_predictions.json",
        manifest_output_path=tmp_path / router_id / "manifest.json",
        router_id=router_id,
        config_id=config_id,
        top_k=1,
        approved_router_config_path=config_path,
        final_evidence=True,
    )

    manifest = json.loads(Path(export["manifest_output_path"]).read_text(encoding="utf-8"))
    assert manifest["final_evidence"]["mode"] == "strict_provenance_only"
    assert manifest["router"]["router_id"] == router_id


@pytest.mark.parametrize("router_id", ["embedding", "gated"])
def test_stage2_routed_prediction_final_evidence_rejects_unpinned_model_routers(
    tmp_path,
    monkeypatch,
    router_id,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / f"skillsbench-real-{router_id}")
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / router_id / "approved-router-config.json",
        router_id=router_id,
        config_id=f"stage2-{router_id}-unit",
    )

    with pytest.raises(ValueError, match="requires pinned model/checkpoint provenance"):
        write_stage2_pilot_routed_prediction_artifacts(
            tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
            global_skill_registry_path=paths["data_root"] / "skills.jsonl",
            output_path=tmp_path / router_id / "routed_predictions.json",
            manifest_output_path=tmp_path / router_id / "manifest.json",
            router_id=router_id,
            config_id=f"stage2-{router_id}-unit",
            top_k=1,
            approved_router_config_path=config_path,
            final_evidence=True,
        )


def test_stage2_routed_prediction_final_evidence_records_code_provenance(
    tmp_path,
    monkeypatch,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / "approved-router-config.json",
    )

    export = write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills.jsonl",
        output_path=tmp_path / "routed_predictions.json",
        manifest_output_path=tmp_path / "manifest.json",
        router_id="keyword",
        config_id="stage2-keyword-unit",
        top_k=1,
        approved_router_config_path=config_path,
        generation_command=["skilleval", "skillsbench-export-routed-predictions"],
        final_evidence=True,
    )

    manifest = json.loads(Path(export["manifest_output_path"]).read_text(encoding="utf-8"))
    assert manifest["code"] == {
        "commit": "d" * 40,
        "tag": "v0.3-test",
        "dirty": False,
        "dirty_paths": [],
    }
    assert manifest["router_implementation"] == {
        "module": "hermes_skilleval.routers.keyword",
        "class": "KeywordRouter",
    }
    assert manifest["generation_command"] == "skilleval skillsbench-export-routed-predictions"


def test_stage2_routed_prediction_final_evidence_rejects_dirty_source_config_or_tests(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        live_agent_skillsbench,
        "_stage2_export_code_provenance",
        lambda *args, **kwargs: {
            "commit": "d" * 40,
            "tag": None,
            "dirty": True,
            "dirty_paths": [
                "artifacts/v0.3/skillsbench-pilot/local-note.json",
                "src/hermes_skilleval/live_agent_skillsbench.py",
            ],
        },
        raising=False,
    )
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / "approved-router-config.json",
    )

    with pytest.raises(ValueError, match="dirty source/config/test paths"):
        write_stage2_pilot_routed_prediction_artifacts(
            tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
            global_skill_registry_path=paths["data_root"] / "skills.jsonl",
            output_path=tmp_path / "routed_predictions.json",
            manifest_output_path=tmp_path / "manifest.json",
            router_id="keyword",
            config_id="stage2-keyword-unit",
            top_k=1,
            approved_router_config_path=config_path,
            final_evidence=True,
        )


def test_stage2_routed_prediction_final_evidence_rejects_copied_fixture_like_inputs(
    tmp_path,
    monkeypatch,
):
    _patch_stage2_clean_code_provenance(monkeypatch)
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    tasks = _read_jsonl_file(paths["data_root"] / "tasks.jsonl")
    tasks[0].pop("source")
    tasks[0].pop("provenance")
    _write_jsonl_file(paths["data_root"] / "tasks.jsonl", tasks)
    config_path = _write_stage2_approved_router_config(
        paths,
        tmp_path / "approved-router-config.json",
    )

    with pytest.raises(ValueError, match="final evidence task source/provenance"):
        write_stage2_pilot_routed_prediction_artifacts(
            tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
            global_skill_registry_path=paths["data_root"] / "skills.jsonl",
            output_path=tmp_path / "routed_predictions.json",
            manifest_output_path=tmp_path / "manifest.json",
            router_id="keyword",
            config_id="stage2-keyword-unit",
            top_k=1,
            approved_router_config_path=config_path,
            final_evidence=True,
        )


def test_cli_stage2_routed_prediction_final_evidence_requires_approved_config(
    tmp_path,
):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")

    exit_code = main(
        [
            "skillsbench-export-routed-predictions",
            "--tasks-manifest",
            str(paths["data_root"] / "tasks.jsonl"),
            "--global-skill-registry",
            str(paths["data_root"] / "skills.jsonl"),
            "--output",
            str(tmp_path / "routed_predictions.json"),
            "--manifest-output",
            str(tmp_path / "manifest.json"),
            "--router-id",
            "keyword",
            "--config-id",
            "stage2-keyword-unit",
            "--top-k",
            "1",
            "--final-evidence",
        ]
    )

    assert exit_code == 2


def test_stage2_routed_prediction_exporter_orders_and_dedupes_stably(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    skills = _read_jsonl_file(paths["data_root"] / "skills.jsonl")
    skills.append(dict(skills[0]))
    _write_jsonl_file(paths["data_root"] / "skills-with-duplicate.jsonl", skills)

    first = write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills-with-duplicate.jsonl",
        output_path=tmp_path / "first" / "routed_predictions.json",
        manifest_output_path=tmp_path / "first" / "manifest.json",
        router_id="keyword",
        config_id="stage2-keyword-unit",
        top_k=2,
    )
    second = write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=paths["data_root"] / "tasks.jsonl",
        global_skill_registry_path=paths["data_root"] / "skills-with-duplicate.jsonl",
        output_path=tmp_path / "second" / "routed_predictions.json",
        manifest_output_path=tmp_path / "second" / "manifest.json",
        router_id="keyword",
        config_id="stage2-keyword-unit",
        top_k=2,
    )

    assert json.loads(Path(first["output_path"]).read_text(encoding="utf-8"))[
        "predictions"
    ] == json.loads(Path(second["output_path"]).read_text(encoding="utf-8"))[
        "predictions"
    ]
    assert all(
        len(prediction) == len(set(prediction)) == 2
        for prediction in json.loads(Path(first["output_path"]).read_text(encoding="utf-8"))[
            "predictions"
        ].values()
    )


def test_cli_stage2_routed_prediction_exporter_writes_outputs(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    output_path = tmp_path / "cli" / "routed_predictions.json"
    manifest_path = tmp_path / "cli" / "manifest.json"

    exit_code = main(
        [
            "skillsbench-export-routed-predictions",
            "--tasks-manifest",
            str(paths["data_root"] / "tasks.jsonl"),
            "--global-skill-registry",
            str(paths["data_root"] / "skills.jsonl"),
            "--output",
            str(output_path),
            "--manifest-output",
            str(manifest_path),
            "--router-id",
            "keyword",
            "--config-id",
            "stage2-keyword-unit",
            "--top-k",
            "1",
        ]
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["router"][
        "label_source"
    ] == "router_generated"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["output"]["path"] == str(
        output_path
    )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda router: router.__setitem__("oracle_labels_read", True),
            "oracle labels were read",
        ),
        (
            lambda router: router.__setitem__("label_source", "oracle"),
            "routed prediction label_source is not allowed",
        ),
        (
            lambda router: router.__setitem__("label_source", "manual"),
            "routed prediction label_source is not allowed",
        ),
        (
            lambda router: router.__setitem__("label_source", "ad_hoc"),
            "routed prediction label_source is not allowed",
        ),
    ],
)
def test_stage2_real_pilot_input_package_rejects_oracle_or_ad_hoc_routing(
    tmp_path,
    mutator,
    message,
):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    routed = json.loads(paths["routed_predictions"].read_text(encoding="utf-8"))
    mutator(routed["router"])
    paths["routed_predictions"].write_text(
        json.dumps(routed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_rejects_registry_hash_mismatch(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    routed = json.loads(paths["routed_predictions"].read_text(encoding="utf-8"))
    routed["router"]["global_skill_registry_hash"] = "e" * 64
    paths["routed_predictions"].write_text(
        json.dumps(routed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="routed prediction registry hash mismatch"):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_requires_enough_routed_top_k(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    routed = json.loads(paths["routed_predictions"].read_text(encoding="utf-8"))
    routed["router"]["top_k"] = 2
    routed["predictions"]["sb-real-1"] = ["skill/real-1", "skill/real-1"]
    paths["routed_predictions"].write_text(
        json.dumps(routed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="insufficient routed top-k"):
        build_stage2_real_pilot_input_package(
            data_root=paths["data_root"],
            upstream_ref=UPSTREAM_SHA,
            license_note="approved-real-pilot-unit",
            run_id="stage2-real-pilot-input-package-unit",
            selected_task_ids=[f"sb-real-{index}" for index in range(1, 5)],
            routed_predictions_path=paths["routed_predictions"],
            oracle_qualification_path=paths["oracle_qualification"],
            router_top_k=2,
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda routed, oracle: routed["router"].__setitem__(
                "config_hash",
                "not-a-sha",
            ),
            "malformed routed prediction config_hash",
        ),
        (
            lambda routed, oracle: routed["router"].__setitem__(
                "global_skill_registry_hash",
                "not-a-sha",
            ),
            "malformed routed prediction global_skill_registry_hash",
        ),
        (
            lambda routed, oracle: oracle[0].__setitem__(
                "output_hash",
                "not-a-sha",
            ),
            "malformed oracle qualification output hash",
        ),
    ],
)
def test_stage2_real_pilot_input_package_rejects_malformed_hash_strings(
    tmp_path,
    mutator,
    message,
):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    routed = json.loads(paths["routed_predictions"].read_text(encoding="utf-8"))
    oracle = _read_jsonl_file(paths["oracle_qualification"])
    mutator(routed, oracle)
    paths["routed_predictions"].write_text(
        json.dumps(routed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_jsonl_file(paths["oracle_qualification"], oracle)

    with pytest.raises(ValueError, match=message):
        _build_real_like_pilot_input_package(paths)


def test_stage2_real_pilot_input_package_records_required_hashes(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")

    package = _build_real_like_pilot_input_package(paths)

    assert package["schema_version"] == "v0.3.stage2-real-pilot-input-package.v1"
    assert package["status"] == "READY_FOR_REVIEW_NOT_EXECUTED"
    assert package["pilot_shape"] == {
        "task_count": 4,
        "conditions": ["no-skill", "routed-skill", "oracle-skill"],
        "trials_per_condition": 1,
        "total_runs": 12,
    }
    assert package["non_actions"]["stage2_pilot_run"] is False
    assert package["deterministic_verifier_package"]["success_source"] == (
        "deterministic_verifier_output_only"
    )
    assert package["deterministic_verifier_package"]["process_exit_code_success_source"] is False
    assert package["deterministic_verifier_package"]["llm_judge_accepted"] is False

    selected_by_id = {
        task["task_id"]: task
        for task in package["data_root_package"]["selected_tasks"]
    }
    assert set(selected_by_id) == {f"sb-real-{index}" for index in range(1, 5)}
    for task in selected_by_id.values():
        assert task["source_or_provenance"]
        assert task["license_note"] == "approved-real-pilot-unit"
        assert task["prompt_hash"]
        assert task["task_hash"]
        assert set(task["verifier_artifacts"]) == {"code", "config", "input"}

    registry = package["global_skill_registry_package"]
    assert registry["global_skill_registry_hash"] == _canonical_hash(registry["skills"])
    assert set(registry["skills"]) == {f"skill/real-{index}" for index in range(1, 5)}
    assert all(record["body_hash"] for record in registry["skills"].values())
    assert all(record["name_hash"] for record in registry["skills"].values())
    assert all(record["description_hash"] for record in registry["skills"].values())

    for task_id, record in package["deterministic_verifier_package"]["records"].items():
        assert task_id in selected_by_id
        assert record["verifier_hash"] == selected_by_id[task_id]["verifier_hash"]
        assert record["code_hash"]
        assert record["config_hash"]
        assert record["input_hash"]
        assert record["expected_output_format"]
        assert record["constraints"]
        assert record["deterministic_assumptions"]

    for task_id, record in package["oracle_qualification_package"]["records"].items():
        assert task_id in selected_by_id
        assert record["task_hash"] == selected_by_id[task_id]["task_hash"]
        assert record["verifier_hash"] == selected_by_id[task_id]["verifier_hash"]
        assert record["skill_hash"]
        assert record["trials"] == 1
        assert record["pass_rate"] == 1.0
        assert record["qualification_command"]
        assert record["output_hash"]

    routed = package["routed_predictions_package"]
    assert routed["router_id"] == "unit-router"
    assert routed["config_id"] == "unit-router-config"
    assert routed["config_hash"] == "c" * 64
    assert routed["top_k"] == 1
    assert routed["global_skill_registry_hash"] == registry["global_skill_registry_hash"]
    assert routed["generation_command"] == "python -m hermes_skilleval.cli route-skills"
    assert routed["oracle_labels_read"] is False
    assert routed["label_source"] == "router_predictions"
    for task_id, record in routed["records"].items():
        assert task_id in selected_by_id
        assert record["prediction_hash"]
        assert record["predicted_skill_ids"]


def test_stage2_real_pilot_input_package_allows_container_root_paths(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")
    tasks = _read_jsonl_file(paths["data_root"] / "tasks.jsonl")
    tasks[0]["prompt"] = "Write the deterministic answer to /root/output.json."
    tasks[0]["verifier"]["expected_output_format"]["path"] = "/root/output.json"
    _write_jsonl_file(paths["data_root"] / "tasks.jsonl", tasks)
    oracle_records = _read_jsonl_file(paths["oracle_qualification"])
    oracle_records[0]["task_hash"] = _canonical_hash(
        {
            "task_id": tasks[0]["task_id"],
            "prompt": tasks[0]["prompt"],
            "verifier": tasks[0]["verifier"],
            "oracle_skill_ids": tasks[0]["oracle_skill_ids"],
            "network": tasks[0]["network"],
            "requires_private_credentials": tasks[0]["requires_private_credentials"],
            "metadata": {
                "source": tasks[0]["source"],
                "provenance": tasks[0]["provenance"],
            },
        }
    )
    oracle_records[0]["verifier_hash"] = _canonical_hash(tasks[0]["verifier"])
    _write_jsonl_file(paths["oracle_qualification"], oracle_records)

    package = _build_real_like_pilot_input_package(paths)

    selected_task = package["data_root_package"]["selected_tasks"][0]
    assert selected_task["task_id"] == "sb-real-1"
    assert selected_task["prompt_hash"]


def test_stage2_real_pilot_input_package_still_rejects_credentials(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")

    with pytest.raises(ValueError, match="sensitive value"):
        build_stage2_real_pilot_input_package(
            data_root=paths["data_root"],
            upstream_ref=UPSTREAM_SHA,
            license_note="SECRET=not-a-real-secret",
            run_id="stage2-real-pilot-input-package-unit",
            selected_task_ids=[f"sb-real-{index}" for index in range(1, 5)],
            routed_predictions_path=paths["routed_predictions"],
            oracle_qualification_path=paths["oracle_qualification"],
            router_top_k=1,
        )


def test_stage2_real_pilot_input_package_rejects_non_container_root_paths(tmp_path):
    paths = _write_real_like_pilot_inputs(tmp_path / "skillsbench-real")

    with pytest.raises(ValueError, match="sensitive value found: /root"):
        build_stage2_real_pilot_input_package(
            data_root=paths["data_root"],
            upstream_ref=UPSTREAM_SHA,
            license_note="review cache was under /root/private-cache",
            run_id="stage2-real-pilot-input-package-unit",
            selected_task_ids=[f"sb-real-{index}" for index in range(1, 5)],
            routed_predictions_path=paths["routed_predictions"],
            oracle_qualification_path=paths["oracle_qualification"],
            router_top_k=1,
        )


def test_stage2_real_pilot_input_package_leakage_guard_catches_prompt_and_skill_text(
    tmp_path,
):
    prompt_paths = _write_real_like_pilot_inputs(tmp_path / "prompt-leak")
    tasks = _read_jsonl_file(prompt_paths["data_root"] / "tasks.jsonl")
    tasks[0]["prompt"] = "Complete sb-real-1 using the gold oracle label."
    _write_jsonl_file(prompt_paths["data_root"] / "tasks.jsonl", tasks)

    with pytest.raises(ValueError, match="leakage in prompt"):
        _build_real_like_pilot_input_package(prompt_paths)

    skill_paths = _write_real_like_pilot_inputs(tmp_path / "skill-leak")
    skills = _read_jsonl_file(skill_paths["data_root"] / "skills.jsonl")
    skills[0]["body"] = "This public skill text is the oracle path for sb-real-1."
    _write_jsonl_file(skill_paths["data_root"] / "skills.jsonl", skills)

    with pytest.raises(ValueError, match="leakage in public skill text"):
        _build_real_like_pilot_input_package(skill_paths)


def test_cli_skillsbench_plan_and_matrix_write_outputs(tmp_path):
    plan_path = tmp_path / "plan.json"
    matrix_path = tmp_path / "matrix.json"
    validation_dir = tmp_path / "validation"

    validate_exit = main(
        [
            "skillsbench-validate",
            "--data-root",
            str(FIXTURE),
            "--output-dir",
            str(validation_dir),
            "--upstream-ref",
            "fixture-ref",
            "--license-note",
            "fixture-only",
        ]
    )
    assert validate_exit == 0
    assert (validation_dir / "validation.json").is_file()

    plan_exit = main(
        [
            "skillsbench-plan",
            "--data-root",
            str(FIXTURE),
            "--output",
            str(plan_path),
            "--upstream-ref",
            "fixture-ref",
            "--license-note",
            "fixture-only",
            "--run-id",
            "cli-skillsbench-run",
            "--mode",
            "frozen",
            "--selected-task-id",
            "sb-task-login",
            "--routed-predictions",
            str(FIXTURE / "routed_predictions.json"),
            "--oracle-qualification",
            str(FIXTURE / "oracle_qualification.jsonl"),
            "--matrix-output",
            str(matrix_path),
        ]
    )
    assert plan_exit == 0

    matrix_exit = main(
        [
            "skillsbench-matrix",
            "--plan",
            str(plan_path),
            "--output",
            str(matrix_path),
        ]
    )
    assert matrix_exit == 0
    assert json.loads(matrix_path.read_text(encoding="utf-8"))["run_id"] == "cli-skillsbench-run"


def test_cli_codex_cli_runner_requires_real_evidence_mode(tmp_path, capsys):
    exit_code = main(
        [
            "skillsbench-matrix",
            "--plan",
            str(tmp_path / "plan.json"),
            "--output",
            str(tmp_path / "matrix.json"),
            "--runner",
            "codex-cli",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "--runner codex-cli requires --evidence-mode real" in captured.err
