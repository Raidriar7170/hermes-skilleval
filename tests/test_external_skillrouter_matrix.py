import gzip
import json
import shutil
import math
from pathlib import Path

from hermes_skilleval.cli import main
from hermes_skilleval.external.skillrouter import SkillRouterAdapter
from hermes_skilleval.external.skillrouter_matrix import (
    build_field_view,
    candidate_subset,
    held_out_skill_split,
    held_out_source_split,
    overlap_scaffold,
    paired_bootstrap_ci,
    run_skillrouter_matrix,
    write_skillrouter_matrix_plan,
)
from hermes_skilleval.external.skillrouter import ExternalTask


FIXTURE = Path(__file__).parent / "fixtures" / "external" / "skillrouter_eval_core_tiny"
PREDICTIONS = FIXTURE / "predictions.json"


def test_skillrouter_matrix_plan_freezes_inputs_before_scoring(tmp_path):
    plan_path = tmp_path / "frozen-plan.json"
    matrix_output = tmp_path / "matrix.json"

    plan = write_skillrouter_matrix_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="matrix-fixture-run",
        routers=[
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(PREDICTIONS),
                "version": "frozen-fixture",
            }
        ],
        field_views=("name_only", "metadata", "full_body"),
        tiers=("easy", "hard"),
        stress_candidate_sizes=(1, 3, 10),
        matrix_output_path=matrix_output,
        bootstrap_iterations=200,
    )

    assert plan_path.exists()
    assert not matrix_output.exists()
    written = json.loads(plan_path.read_text(encoding="utf-8"))
    assert written == plan
    assert written["schema_version"] == "v0.3.skillrouter-matrix-plan.v1"
    assert written["run_id"] == "matrix-fixture-run"
    assert written["seed"] == 20260625
    assert written["benchmark_id"] == "skillrouter"
    assert written["adapter_provenance"]["upstream_ref"] == "fixture-ref"
    assert written["adapter_provenance"]["license_note"] == "fixture-only"
    assert written["frozen_routers"][0]["config_id"] == "baseline-minilm__name_only"
    assert written["frozen_routers"][0]["router_id"] == "baseline-minilm"
    assert written["frozen_routers"][0]["field_view"] == "name_only"
    assert written["frozen_routers"][0]["prediction_file"]["size_bytes"] > 0
    assert written["frozen_routers"][0]["prediction_file"]["sha256"]
    assert written["field_views"] == ["name_only", "metadata", "full_body"]
    assert written["tiers"] == ["easy", "hard"]
    assert written["stress_candidate_sizes"] == [1, 3, 10]
    assert written["bootstrap"]["iterations"] == 200
    assert written["bootstrap"]["confidence"] == 0.95
    assert written["matrix_output_path"] == str(matrix_output)
    assert written["git"]["commit"]
    assert "dirty" in written["git"]


def test_skillrouter_field_views_are_deterministic():
    skill = next(SkillRouterAdapter(data_root=FIXTURE).iter_skills("easy"))

    assert build_field_view(skill, "name_only") == {
        "schema_version": "v0.3.skillrouter-field-view.v1",
        "view": "name_only",
        "builder_version": "v0.3.pr3.field-view.v1",
        "skill_id": "gt/browser-login",
        "text": "Browser Login",
    }
    assert build_field_view(skill, "metadata")["text"] == (
        "Browser Login\nSubmit login forms"
    )
    assert build_field_view(skill, "full_body")["text"] == (
        "Browser Login\nSubmit login forms\n"
        "Use browser automation to fill credentials and submit forms."
    )


def test_skillrouter_matrix_uses_plan_and_separates_official_from_diagnostics(tmp_path):
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillrouter_matrix_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="matrix-run",
        routers=[
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(PREDICTIONS),
                "version": "frozen-fixture",
            },
            {
                "router_id": "finetuned-embedding",
                "field_view": "full_body",
                "predictions_path": str(PREDICTIONS),
                "version": "frozen-fixture",
            },
        ],
        stress_candidate_sizes=(1, 3),
        matrix_output_path=output_path,
        bootstrap_iterations=200,
    )

    report = run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)

    assert output_path.exists()
    assert report["schema_version"] == "v0.3.skillrouter-matrix-report.v1"
    assert report["plan_path"] == str(plan_path)
    assert set(report["official"]) == {
        "baseline-minilm__name_only",
        "finetuned-embedding__full_body",
    }
    easy = report["official"]["baseline-minilm__name_only"]["by_tier"]["easy"]
    hard = report["official"]["baseline-minilm__name_only"]["by_tier"]["hard"]
    assert easy["aggregates"]["all"]["task_count"] == 2
    assert hard["aggregates"]["all"]["task_count"] == 1
    assert "hermes_diagnostics" in report
    assert "negative_hit_rate" not in json.dumps(report).lower()
    assert report["hermes_diagnostics"]["stress_candidate_subsets"]["easy"]["1"][
        "status"
    ] == "UNAVAILABLE"
    assert report["hermes_diagnostics"]["stress_candidate_subsets"]["easy"]["3"][
        "status"
    ] == "PASS"


def test_skillrouter_matrix_emits_pairwise_ci_for_all_router_pairs(tmp_path):
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillrouter_matrix_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="matrix-run",
        routers=[
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(PREDICTIONS),
                "version": "frozen-fixture",
            },
            {
                "router_id": "finetuned-embedding",
                "field_view": "metadata",
                "predictions_path": str(PREDICTIONS),
                "version": "frozen-fixture",
            },
            {
                "router_id": "lexical-control",
                "field_view": "full_body",
                "predictions_path": str(PREDICTIONS),
                "version": "frozen-fixture",
            },
        ],
        matrix_output_path=output_path,
        bootstrap_iterations=200,
    )

    report = run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)

    ci_keys = report["hermes_diagnostics"]["paired_bootstrap_confidence_intervals"]
    assert {
        "baseline-minilm__name_only__minus__finetuned-embedding__metadata__easy__MRR@10",
        "baseline-minilm__name_only__minus__lexical-control__full_body__easy__MRR@10",
        "finetuned-embedding__metadata__minus__lexical-control__full_body__easy__MRR@10",
        "baseline-minilm__name_only__minus__finetuned-embedding__metadata__hard__MRR@10",
        "baseline-minilm__name_only__minus__lexical-control__full_body__hard__MRR@10",
        "finetuned-embedding__metadata__minus__lexical-control__full_body__hard__MRR@10",
    } <= set(ci_keys)
    assert ci_keys[
        "baseline-minilm__name_only__minus__finetuned-embedding__metadata__easy__MRR@10"
    ]["iterations"] == 200


def test_skillrouter_matrix_refuses_missing_plan(tmp_path):
    try:
        run_skillrouter_matrix(
            plan_path=tmp_path / "missing-plan.json",
            output_path=tmp_path / "matrix.json",
        )
    except ValueError as exc:
        assert "frozen plan" in str(exc)
    else:
        raise AssertionError("missing frozen plan should fail closed")


def test_skillrouter_matrix_fails_when_predictions_change_after_plan(tmp_path):
    root, plan_path, output_path = _frozen_fixture_plan(tmp_path)
    predictions = root / "predictions.json"
    payload = json.loads(predictions.read_text(encoding="utf-8"))
    payload["task-single-easy"] = ["gt/browser-login"]
    predictions.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    try:
        run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)
    except ValueError as exc:
        assert "prediction file changed" in str(exc)
    else:
        raise AssertionError("mutated predictions must fail closed")


def test_skillrouter_matrix_fails_when_relevance_changes_after_plan(tmp_path):
    root, plan_path, output_path = _frozen_fixture_plan(tmp_path)
    relevance = root / "relevance.json"
    payload = json.loads(relevance.read_text(encoding="utf-8"))
    payload["task-single-easy"]["relevance"]["gt/browser-login"] = 2
    relevance.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    try:
        run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)
    except ValueError as exc:
        assert "adapter provenance changed" in str(exc)
    else:
        raise AssertionError("mutated relevance must fail closed")


def test_skillrouter_matrix_fails_when_skill_shard_changes_after_plan(tmp_path):
    root, plan_path, output_path = _frozen_fixture_plan(tmp_path)
    with gzip.open(root / "easy" / "shard-000.jsonl.gz", "at", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "id": "gt/new-distractor",
                    "name": "New Distractor",
                    "description": "Changes frozen easy pool",
                    "body": "This should invalidate the frozen plan.",
                    "tier": "easy",
                },
                sort_keys=True,
            )
            + "\n"
        )

    try:
        run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)
    except ValueError as exc:
        assert "adapter provenance changed" in str(exc)
    else:
        raise AssertionError("mutated shard must fail closed")


def test_skillrouter_matrix_passes_when_frozen_inputs_are_unchanged(tmp_path):
    _, plan_path, output_path = _frozen_fixture_plan(tmp_path)

    report = run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)

    assert output_path.exists()
    assert report["official"]["baseline-minilm__name_only"]["router_id"] == (
        "baseline-minilm"
    )


def test_skillrouter_matrix_output_must_match_frozen_plan(tmp_path):
    _, plan_path, _ = _frozen_fixture_plan(tmp_path)

    try:
        run_skillrouter_matrix(
            plan_path=plan_path,
            output_path=tmp_path / "different.json",
        )
    except ValueError as exc:
        assert "matrix output path" in str(exc)
    else:
        raise AssertionError("output path mismatch must fail closed")


def test_skillrouter_matrix_same_router_field_views_get_distinct_config_ids(tmp_path):
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillrouter_matrix_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="matrix-run",
        routers=[
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(PREDICTIONS),
            },
            {
                "router_id": "baseline-minilm",
                "field_view": "metadata",
                "predictions_path": str(PREDICTIONS),
            },
            {
                "router_id": "baseline-minilm",
                "field_view": "full_body",
                "predictions_path": str(PREDICTIONS),
            },
        ],
        matrix_output_path=output_path,
        bootstrap_iterations=200,
    )

    report = run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)

    assert set(report["official"]) == {
        "baseline-minilm__name_only",
        "baseline-minilm__metadata",
        "baseline-minilm__full_body",
    }
    for config_id, config_report in report["official"].items():
        assert config_report["router_id"] == "baseline-minilm"
        assert config_report["field_view"] in config_id


def test_skillrouter_matrix_rejects_duplicate_config_id(tmp_path):
    try:
        write_skillrouter_matrix_plan(
            data_root=FIXTURE,
            output_path=tmp_path / "plan.json",
            upstream_ref="fixture-ref",
            license_note="fixture-only",
            run_id="matrix-run",
            routers=[
                {
                    "config_id": "duplicate",
                    "router_id": "baseline-minilm",
                    "field_view": "name_only",
                    "predictions_path": str(PREDICTIONS),
                },
                {
                    "config_id": "duplicate",
                    "router_id": "baseline-minilm",
                    "field_view": "metadata",
                    "predictions_path": str(PREDICTIONS),
                },
            ],
        )
    except ValueError as exc:
        assert "duplicate config_id" in str(exc)
    else:
        raise AssertionError("duplicate config_id must fail closed")


def test_skillrouter_matrix_rejects_duplicate_config_id_in_existing_plan(tmp_path):
    _, plan_path, output_path = _frozen_fixture_plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    duplicate = dict(plan["frozen_routers"][0])
    duplicate["field_view"] = "metadata"
    plan["frozen_routers"].append(duplicate)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")

    try:
        run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)
    except ValueError as exc:
        assert "duplicate config_id" in str(exc)
    else:
        raise AssertionError("duplicate config_id in plan must fail closed")


def test_skillrouter_matrix_requires_bootstrap_settings_in_existing_plan(tmp_path):
    _, plan_path, output_path = _frozen_fixture_plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    del plan["bootstrap"]
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")

    try:
        run_skillrouter_matrix(plan_path=plan_path, output_path=output_path)
    except ValueError as exc:
        assert "bootstrap settings" in str(exc)
    else:
        raise AssertionError("missing bootstrap settings must fail closed")


def test_skillrouter_matrix_default_bootstrap_iterations_are_formal(tmp_path):
    plan_path = tmp_path / "plan.json"
    write_skillrouter_matrix_plan(
        data_root=FIXTURE,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="matrix-run",
        routers=[
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(PREDICTIONS),
            }
        ],
    )

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert plan["bootstrap"]["iterations"] == 10000
    assert plan["bootstrap"]["confidence"] == 0.95


def test_candidate_subset_includes_gt_before_deterministic_distractors():
    subset = candidate_subset(
        all_skill_ids=[
            "distractor/b",
            "gt/medium-easy",
            "distractor/a",
            "gt/browser-login",
        ],
        gt_skill_ids=["gt/browser-login", "gt/medium-easy"],
        target_size=3,
    )

    assert subset["status"] == "PASS"
    assert subset["seed"] == 20260625
    assert subset["selected_skill_ids"][:2] == ["gt/browser-login", "gt/medium-easy"]
    assert len(subset["selected_skill_ids"]) == 3
    assert subset["candidate_hash"]


def test_candidate_subset_unavailable_when_target_smaller_than_gt_union():
    subset = candidate_subset(
        all_skill_ids=["gt/browser-login", "gt/medium-easy"],
        gt_skill_ids=["gt/browser-login", "gt/medium-easy"],
        target_size=1,
    )

    assert subset == {
        "status": "UNAVAILABLE",
        "reason": "target_size 1 is smaller than selected GT union 2",
        "seed": 20260625,
        "target_size": 1,
        "required_gt_count": 2,
    }


def test_paired_bootstrap_ci_is_deterministic_over_task_deltas():
    rows_a = [
        {"task_id": "t1", "metrics": {"MRR@10": 0.0}},
        {"task_id": "t2", "metrics": {"MRR@10": 0.5}},
        {"task_id": "t3", "metrics": {"MRR@10": 1.0}},
    ]
    rows_b = [
        {"task_id": "t1", "metrics": {"MRR@10": 1.0}},
        {"task_id": "t2", "metrics": {"MRR@10": 0.5}},
        {"task_id": "t3", "metrics": {"MRR@10": 0.0}},
    ]

    ci = paired_bootstrap_ci(
        rows_a,
        rows_b,
        metric="MRR@10",
        iterations=200,
        seed=20260625,
    )

    assert ci["schema_version"] == "v0.3.paired-bootstrap-ci.v1"
    assert ci["paired_task_count"] == 3
    assert ci["metric"] == "MRR@10"
    assert math.isclose(ci["point_estimate"], 0.0)
    assert ci["lower"] <= ci["point_estimate"] <= ci["upper"]
    assert ci == paired_bootstrap_ci(
        rows_a,
        rows_b,
        metric="MRR@10",
        iterations=200,
        seed=20260625,
    )


def test_paired_bootstrap_ci_skips_rows_missing_metric_on_either_side():
    rows_a = [
        {"task_id": "t1", "metrics": {"MRR@10": 1.0}},
        {"task_id": "t2", "metrics": {"MRR@10": 0.5}},
    ]
    rows_b = [
        {"task_id": "t1", "metrics": {}},
        {"task_id": "t2", "metrics": {"MRR@10": 0.0}},
    ]

    ci = paired_bootstrap_ci(rows_a, rows_b, metric="MRR@10", iterations=20)

    assert ci["status"] == "PASS"
    assert ci["paired_task_count"] == 1
    assert math.isclose(ci["point_estimate"], 0.5)


def test_held_out_skill_split_uses_connected_components():
    tasks = SkillRouterAdapter(data_root=FIXTURE).load_tasks()

    split = held_out_skill_split(tasks)

    assert split["schema_version"] == "v0.3.held-out-skill-split.v1"
    assert split["status"] == "PASS"
    components = split["components"]
    assert len(components) >= 3
    for component in components:
        assert component["task_ids"]
        assert component["skill_ids"] or component["task_type"] == "generic_only"
        assert component["split"] in {"train", "held_out"}
    assert split["overlap_assertions"]["task_overlap"] == []
    assert split["overlap_assertions"]["skill_overlap"] == []


def test_held_out_skill_split_uses_selected_gt_not_auxiliary_relevance():
    tasks = [
        ExternalTask(
            benchmark_id="skillrouter",
            task_id="task-a",
            query="A",
            task_type="single_skill",
            graded_relevance={"gt/a": 3, "degraded/shared": 1},
            tier="easy",
            metadata={
                "core_gt_ids": ["gt/a"],
                "gt_skill_ids": ["gt/a"],
                "auxiliary_gt_ids": ["degraded/shared"],
            },
        ),
        ExternalTask(
            benchmark_id="skillrouter",
            task_id="task-b",
            query="B",
            task_type="single_skill",
            graded_relevance={"gt/b": 3, "degraded/shared": 1},
            tier="easy",
            metadata={
                "core_gt_ids": ["gt/b"],
                "gt_skill_ids": ["gt/b"],
                "auxiliary_gt_ids": ["degraded/shared"],
            },
        ),
    ]

    split = held_out_skill_split(tasks)

    component_skills = [component["skill_ids"] for component in split["components"]]
    assert ["degraded/shared"] not in component_skills
    assert sorted(component_skills) == [["gt/a"], ["gt/b"]]


def test_held_out_skill_split_uses_adapter_selected_gt_not_auxiliary_gt(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    shutil.copytree(FIXTURE, root)
    relevance_path = root / "relevance.json"
    relevance = json.loads(relevance_path.read_text(encoding="utf-8"))
    relevance["task-single-easy"]["auxiliary_gt_ids"].append("gt/aux-easy")
    relevance["task-single-easy"]["relevance"]["gt/aux-easy"] = 2
    relevance_path.write_text(
        json.dumps(relevance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with gzip.open(root / "easy" / "shard-000.jsonl.gz", "at", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "id": "gt/aux-easy",
                    "name": "Auxiliary Easy Skill",
                    "description": "Auxiliary positive relevance only",
                    "body": "Should not define held-out-skill component edges.",
                    "tier": "easy",
                },
                sort_keys=True,
            )
            + "\n"
        )

    tasks = SkillRouterAdapter(data_root=root).load_tasks()
    split = held_out_skill_split(tasks)

    assert "gt/aux-easy" not in {
        skill_id
        for component in split["components"]
        for skill_id in component["skill_ids"]
    }


def test_held_out_source_unavailable_when_metadata_is_insufficient():
    tasks = SkillRouterAdapter(data_root=FIXTURE).load_tasks()

    result = held_out_source_split(tasks)

    assert result["status"] == "UNAVAILABLE"
    assert "source metadata" in result["reason"]


def test_held_out_source_unavailable_for_single_distinct_source():
    tasks = [
        ExternalTask(
            benchmark_id="skillrouter",
            task_id="task-a",
            query="A",
            task_type="single_skill",
            graded_relevance={"gt/a": 3},
            tier="easy",
            metadata={"source": "one-source"},
        ),
        ExternalTask(
            benchmark_id="skillrouter",
            task_id="task-b",
            query="B",
            task_type="single_skill",
            graded_relevance={"gt/b": 3},
            tier="easy",
            metadata={"source": "one-source"},
        ),
    ]

    result = held_out_source_split(tasks)

    assert result["status"] == "UNAVAILABLE"
    assert "at least two distinct sources" in result["reason"]


def test_overlap_scaffold_allows_missing_skillsbench_tasks():
    tasks = SkillRouterAdapter(data_root=FIXTURE).load_tasks()

    report = overlap_scaffold(skillrouter_tasks=tasks, skillsbench_tasks=None)

    assert report["schema_version"] == "v0.3.skillrouter-skillsbench-overlap.v1"
    assert report["skillrouter_task_count"] == 4
    assert report["skillsbench_task_count"] == {
        "status": "UNAVAILABLE",
        "reason": "SkillsBench live tasks not selected in PR-3",
    }
    assert report["exact_id_overlap"] == []
    assert report["normalized_text_hash_overlap"] == []
    assert report["high_similarity_diagnostics"]["status"] == "UNAVAILABLE"


def test_cli_external_plan_and_matrix_write_outputs(tmp_path):
    plan_path = tmp_path / "plan.json"
    matrix_path = tmp_path / "matrix.json"

    plan_exit = main(
        [
            "external-plan",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(FIXTURE),
            "--output",
            str(plan_path),
            "--upstream-ref",
            "fixture-ref",
            "--license-note",
            "fixture-only",
            "--run-id",
            "cli-matrix-run",
            "--router-config",
            f"baseline-minilm:name_only:{PREDICTIONS}",
            "--router-config",
            f"finetuned-embedding:full_body:{PREDICTIONS}",
            "--matrix-output",
            str(matrix_path),
            "--stress-candidate-size",
            "1",
            "--stress-candidate-size",
            "3",
            "--bootstrap-iterations",
            "200",
        ]
    )
    assert plan_exit == 0
    matrix_exit = main(
        [
            "external-matrix",
            "--benchmark",
            "skillrouter",
            "--plan",
            str(plan_path),
            "--output",
            str(matrix_path),
        ]
    )
    assert matrix_exit == 0

    report = json.loads(matrix_path.read_text(encoding="utf-8"))
    assert set(report["official"]) == {
        "baseline-minilm__name_only",
        "finetuned-embedding__full_body",
    }


def _frozen_fixture_plan(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "skillrouter_eval_core"
    shutil.copytree(FIXTURE, root)
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "matrix.json"
    write_skillrouter_matrix_plan(
        data_root=root,
        output_path=plan_path,
        upstream_ref="fixture-ref",
        license_note="fixture-only",
        run_id="matrix-run",
        routers=[
            {
                "router_id": "baseline-minilm",
                "field_view": "name_only",
                "predictions_path": str(root / "predictions.json"),
            }
        ],
        stress_candidate_sizes=(3,),
        matrix_output_path=output_path,
        bootstrap_iterations=200,
    )
    return root, plan_path, output_path
