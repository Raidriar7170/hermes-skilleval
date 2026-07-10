import json
import math
from pathlib import Path

from hermes_skilleval.cli import main
from hermes_skilleval.external.skillrouter_scorer import (
    score_skillrouter_predictions,
    write_skillrouter_score_report,
)


FIXTURE = Path(__file__).parent / "fixtures" / "external" / "skillrouter_eval_core_tiny"
PREDICTIONS = FIXTURE / "predictions.json"


def test_skillrouter_official_scorer_computes_hand_checkable_core_metrics():
    easy_report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        mode="core",
        tier="easy",
    )
    hard_report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        mode="core",
        tier="hard",
    )

    assert easy_report["schema_version"] == "v0.3.skillrouter-official-scorer.v1"
    assert easy_report["mode"] == "core"
    assert easy_report["tier"] == "easy"
    assert "negative_hit_rate" not in json.dumps(easy_report)
    assert easy_report["task_count"] == 2
    assert {row["task_id"] for row in easy_report["tasks"]} == {
        "task-single-easy",
        "task-medium-easy-pool",
    }

    single = _task(easy_report, "task-single-easy")
    assert single["task_type"] == "single_skill"
    assert single["evaluation_tier"] == "easy"
    assert single["task_difficulty"] == "easy"
    assert single["gt_ids"] == ["gt/browser-login"]
    assert single["tier_relevance"] == {
        "gt/browser-login": 3,
        "degraded/browser-login": 1,
    }
    assert set(single["metrics"]) == {
        "nDCG@1",
        "nDCG@3",
        "nDCG@10",
        "Hit@1",
        "Precision@3",
        "MRR@10",
        "Recall@10",
        "Recall@20",
        "Recall@50",
        "FullCoverage@3",
        "FullCoverage@5",
        "FullCoverage@10",
    }
    assert math.isclose(single["metrics"]["nDCG@1"], 1 / 3)
    assert math.isclose(single["metrics"]["nDCG@3"], 0.7967075809905066)
    assert single["metrics"]["Hit@1"] == 0.0
    assert math.isclose(single["metrics"]["Precision@3"], 1 / 3)
    assert math.isclose(single["metrics"]["MRR@10"], 1 / 2)
    assert single["metrics"]["Recall@10"] == 1.0
    assert single["metrics"]["Recall@20"] == 1.0
    assert single["metrics"]["Recall@50"] == 1.0
    assert single["metrics"]["FullCoverage@3"] == 1.0
    assert single["metrics"]["FullCoverage@5"] == 1.0
    assert single["metrics"]["FullCoverage@10"] == 1.0

    medium = _task(easy_report, "task-medium-easy-pool")
    assert medium["task_difficulty"] == "medium"
    assert medium["evaluation_tier"] == "easy"
    assert medium["gt_ids"] == ["gt/medium-easy"]
    assert medium["metrics"]["Hit@1"] == 1.0

    multi = _task(hard_report, "task-multi-hard")
    assert multi["task_type"] == "multi_skill"
    assert multi["evaluation_tier"] == "hard"
    assert multi["task_difficulty"] == "hard"
    assert multi["gt_ids"] == ["gt/workflow-debugging", "gt/tdd-helper"]
    assert multi["tier_relevance"] == {
        "gt/workflow-debugging": 3,
        "gt/tdd-helper": 3,
        "degraded/workflow-debugging": 1,
    }
    assert multi["metrics"]["nDCG@1"] == 1.0
    assert math.isclose(multi["metrics"]["nDCG@3"], 0.9514426589878557)
    assert multi["metrics"]["Hit@1"] == 1.0
    assert math.isclose(multi["metrics"]["Precision@3"], 2 / 3)
    assert multi["metrics"]["MRR@10"] == 1.0
    assert multi["metrics"]["Recall@10"] == 1.0
    assert multi["metrics"]["FullCoverage@3"] == 1.0

    easy_aggregate = easy_report["aggregates"]["all"]
    assert easy_aggregate["task_count"] == 2
    assert math.isclose(
        easy_aggregate["metrics"]["nDCG@3"],
        (0.7967075809905066 + 1.0) / 2,
    )
    assert math.isclose(easy_aggregate["metrics"]["Precision@3"], 1 / 3)
    assert math.isclose(easy_aggregate["metrics"]["MRR@10"], 0.75)


def test_skillrouter_official_scorer_aggregates_type_slices_per_tier():
    easy_report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        mode="core",
        tier="easy",
    )
    hard_report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        mode="core",
        tier="hard",
    )

    assert set(easy_report["aggregates"]) == {"all", "single", "multi"}
    assert easy_report["aggregates"]["single"]["task_count"] == 2
    assert easy_report["aggregates"]["multi"]["task_count"] == 0
    assert set(hard_report["aggregates"]) == {"all", "single", "multi"}
    assert hard_report["aggregates"]["single"]["task_count"] == 0
    assert hard_report["aggregates"]["multi"]["task_count"] == 1


def test_skillrouter_official_scorer_combined_report_uses_by_tier():
    report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        mode="core",
        tiers=("easy", "hard"),
    )

    assert set(report["by_tier"]) == {"easy", "hard"}
    assert report["by_tier"]["easy"]["aggregates"]["all"]["task_count"] == 2
    assert report["by_tier"]["hard"]["aggregates"]["all"]["task_count"] == 1
    assert "easy" not in report.get("aggregates", {})
    assert "hard" not in report.get("aggregates", {})


def test_skillrouter_official_scorer_single_mode_keeps_one_gt_task_only():
    report = score_skillrouter_predictions(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        mode="single",
        tier="easy",
    )

    assert report["task_count"] == 2
    assert [row["task_id"] for row in report["tasks"]] == [
        "task-single-easy",
        "task-medium-easy-pool",
    ]
    assert report["aggregates"]["all"]["task_count"] == 2
    assert report["aggregates"]["multi"]["task_count"] == 0
    assert report["aggregates"]["multi"]["metrics"] is None


def test_skillrouter_official_scorer_core_mode_uses_empty_core_gt_ids_as_is(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    relevance = json.loads((root / "relevance.json").read_text(encoding="utf-8"))
    relevance["task-medium-easy-pool"]["core_gt_ids"] = []
    (root / "relevance.json").write_text(
        json.dumps(relevance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = score_skillrouter_predictions(
        data_root=root,
        predictions_path=root / "predictions.json",
        mode="core",
        tier="easy",
    )

    assert "task-medium-easy-pool" not in {row["task_id"] for row in report["tasks"]}


def test_skillrouter_official_scorer_core_mode_falls_back_when_core_gt_ids_missing(
    tmp_path,
):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    relevance = json.loads((root / "relevance.json").read_text(encoding="utf-8"))
    del relevance["task-medium-easy-pool"]["core_gt_ids"]
    (root / "relevance.json").write_text(
        json.dumps(relevance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = score_skillrouter_predictions(
        data_root=root,
        predictions_path=root / "predictions.json",
        mode="core",
        tier="easy",
    )

    assert _task(report, "task-medium-easy-pool")["gt_ids"] == ["gt/medium-easy"]


def test_skillrouter_official_scorer_missing_predictions_are_skipped(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    (root / "predictions.json").write_text(
        json.dumps({"task-multi-hard": ["gt/tdd-helper"]}) + "\n",
        encoding="utf-8",
    )

    report = score_skillrouter_predictions(
        data_root=root,
        predictions_path=root / "predictions.json",
        mode="core",
        tier="hard",
    )

    assert [row["task_id"] for row in report["tasks"]] == ["task-multi-hard"]
    assert report["aggregates"]["all"]["task_count"] == 1


def test_skillrouter_official_scorer_type_slices_use_gt_cardinality(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    relevance = json.loads((root / "relevance.json").read_text(encoding="utf-8"))
    relevance["task-multi-hard"]["core_gt_ids"] = ["gt/tdd-helper"]
    relevance["task-multi-hard"]["relevance"] = {"gt/tdd-helper": 3}
    (root / "relevance.json").write_text(
        json.dumps(relevance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = score_skillrouter_predictions(
        data_root=root,
        predictions_path=root / "predictions.json",
        mode="core",
        tier="easy",
    )

    assert report["aggregates"]["single"]["task_count"] == 2
    assert report["aggregates"]["multi"]["task_count"] == 0


def test_skillrouter_official_scorer_multi_slice_uses_unfiltered_gt_count(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    _add_cross_tier_multi_task(root)
    output = tmp_path / "easy.json"

    exit_code = main(
        [
            "external-score",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(root),
            "--predictions",
            str(root / "predictions.json"),
            "--output",
            str(output),
            "--tier",
            "easy",
            "--mode",
            "core",
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    task = _task(report, "task-cross-tier-multi")
    assert task["gt_ids"] == ["gt/browser-login"]
    assert task["gt_count"] == 1
    assert task["slice_gt_count"] == 2
    assert task["tier_relevance"] == {"gt/browser-login": 3}
    assert task["metrics"]["Hit@1"] == 1.0
    assert math.isclose(task["metrics"]["Precision@3"], 1 / 3)
    assert task["metrics"]["Recall@10"] == 1.0
    assert task["metrics"]["FullCoverage@3"] == 1.0
    assert report["aggregates"]["all"]["task_count"] == 3
    assert report["aggregates"]["single"]["task_count"] == 2
    assert report["aggregates"]["multi"]["task_count"] == 1


def test_skillrouter_official_scorer_filters_relevance_to_tier_pool(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    relevance = json.loads((root / "relevance.json").read_text(encoding="utf-8"))
    relevance["task-single-easy"]["relevance"]["gt/tdd-helper"] = 99
    (root / "relevance.json").write_text(
        json.dumps(relevance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = score_skillrouter_predictions(
        data_root=root,
        predictions_path=root / "predictions.json",
        mode="core",
        tier="easy",
    )

    single = _task(report, "task-single-easy")
    assert "gt/tdd-helper" not in single["tier_relevance"]
    assert math.isclose(single["metrics"]["nDCG@1"], 1 / 3)


def test_skillrouter_official_scorer_preserves_duplicate_predictions(tmp_path):
    root = tmp_path / "skillrouter_eval_core"
    _copy_fixture(root)
    (root / "predictions.json").write_text(
        json.dumps(
            {
                "task-single-easy": [
                    "degraded/browser-login",
                    "degraded/browser-login",
                    "gt/browser-login",
                ],
                "task-multi-hard": ["gt/tdd-helper"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = score_skillrouter_predictions(
        data_root=root,
        predictions_path=root / "predictions.json",
        mode="core",
        tier="easy",
    )

    single = _task(report, "task-single-easy")
    assert single["predictions"] == [
        "degraded/browser-login",
        "degraded/browser-login",
        "gt/browser-login",
    ]
    assert math.isclose(single["metrics"]["MRR@10"], 1 / 3)
    assert math.isclose(single["metrics"]["Precision@3"], 1 / 3)
    assert math.isclose(single["metrics"]["nDCG@3"], 0.8622942238119067)


def test_skillrouter_score_report_cli_writer(tmp_path):
    output = tmp_path / "score-report.json"

    report = write_skillrouter_score_report(
        data_root=FIXTURE,
        predictions_path=PREDICTIONS,
        output_path=output,
        mode="core",
        tier="easy",
    )

    assert output.exists()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == report
    assert written["tier"] == "easy"
    assert written["aggregates"]["all"]["task_count"] == 2


def test_cli_external_score_writes_official_scorer_report(tmp_path):
    output = tmp_path / "official.json"

    exit_code = main(
        [
            "external-score",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(FIXTURE),
            "--predictions",
            str(PREDICTIONS),
            "--output",
            str(output),
            "--tier",
            "easy",
            "--mode",
            "core",
        ]
    )

    assert exit_code == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["schema_version"] == "v0.3.skillrouter-official-scorer.v1"
    assert written["tier"] == "easy"
    assert written["aggregates"]["all"]["task_count"] == 2
    assert "negative_hit_rate" not in json.dumps(written)


def test_cli_external_score_tiers_writes_by_tier_report(tmp_path):
    output = tmp_path / "combined.json"

    exit_code = main(
        [
            "external-score",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(FIXTURE),
            "--predictions",
            str(PREDICTIONS),
            "--output",
            str(output),
            "--tiers",
            "easy",
            "hard",
            "--mode",
            "core",
        ]
    )

    assert exit_code == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    assert set(written["by_tier"]) == {"easy", "hard"}
    assert set(written["by_tier"]["easy"]["aggregates"]) == {"all", "single", "multi"}
    assert set(written["by_tier"]["hard"]["aggregates"]) == {"all", "single", "multi"}


def _task(report: dict, task_id: str) -> dict:
    return next(row for row in report["tasks"] if row["task_id"] == task_id)


def _copy_fixture(target: Path) -> None:
    import shutil

    shutil.copytree(FIXTURE, target)


def _add_cross_tier_multi_task(root: Path) -> None:
    with (root / "tasks.jsonl").open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "id": "task-cross-tier-multi",
                    "instruction_text": "Route a multi-skill task with one easy candidate.",
                    "difficulty": "medium",
                    "num_skills": 2,
                    "skill_names": ["Browser Login", "TDD Helper"],
                    "domain": "engineering",
                    "excluded": False,
                },
                sort_keys=True,
            )
            + "\n"
        )
    relevance = json.loads((root / "relevance.json").read_text(encoding="utf-8"))
    relevance["task-cross-tier-multi"] = {
        "task_type": "multi_skill",
        "gt_skill_ids": ["gt/browser-login", "gt/tdd-helper"],
        "core_gt_ids": ["gt/browser-login", "gt/tdd-helper"],
        "auxiliary_gt_ids": [],
        "relevance": {
            "gt/browser-login": 3,
            "gt/tdd-helper": 3,
        },
    }
    (root / "relevance.json").write_text(
        json.dumps(relevance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    predictions = json.loads((root / "predictions.json").read_text(encoding="utf-8"))
    predictions["task-cross-tier-multi"] = ["gt/browser-login", "gt/tdd-helper"]
    (root / "predictions.json").write_text(
        json.dumps(predictions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
