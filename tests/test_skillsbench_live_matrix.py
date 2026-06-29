from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import jsonschema

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
    _canonical_hash,
    _validate_real_runner_preflight,
    run_skillsbench_matrix,
    write_skillsbench_plan,
)


FIXTURE = Path("tests/fixtures/live_agent/skillsbench_tiny")
SKILLROUTER_FIXTURE = Path("tests/fixtures/external/skillrouter_eval_core_tiny")
UPSTREAM_SHA = "a" * 40


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
    (root / "routed_predictions.json").write_text(
        json.dumps(
            {
                "schema_version": "v0.3.routed-predictions.v1",
                "router": {
                    "router_id": "unit-router",
                    "config_hash": "c" * 64,
                    "top_k": 1,
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
    assert routed["config_hash"] == "c" * 64
    assert routed["top_k"] == 1
    assert routed["global_skill_registry_hash"] == registry["global_skill_registry_hash"]
    for task_id, record in routed["records"].items():
        assert task_id in selected_by_id
        assert record["prediction_hash"]
        assert record["predicted_skill_ids"]


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
