from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import jsonschema

from hermes_skilleval.cli import main
from hermes_skilleval.live_agent_runtime import FakeAgentRunner, FakeVerifier
from hermes_skilleval.live_agent_skillsbench import (
    SkillsBenchAdapter,
    run_skillsbench_matrix,
    write_skillsbench_plan,
)


FIXTURE = Path("tests/fixtures/live_agent/skillsbench_tiny")
SKILLROUTER_FIXTURE = Path("tests/fixtures/external/skillrouter_eval_core_tiny")
UPSTREAM_SHA = "a" * 40


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
