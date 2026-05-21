import json
from pathlib import Path

from hermes_skilleval.cli import main


FIXTURES = Path(__file__).parent / "fixtures"

EXPECTED_RESULT_KEYS = {
    "task_id",
    "category",
    "difficulty",
    "router",
    "selected_skill_ids",
    "scores",
    "gold_skills",
    "negative_skills",
    "latency_ms",
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "precision_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
}


def test_cli_index_eval_report_smoke(tmp_path):
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "run"

    assert (
        main(
            [
                "index",
                "--skills-path",
                str(FIXTURES / "skills"),
                "--output",
                str(index_path),
            ]
        )
        == 0
    )
    assert index_path.exists()

    assert (
        main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--router",
                "hybrid",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )
    results_path = run_dir / "results.jsonl"
    assert results_path.exists()

    records = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records
    assert set(records[0]) == EXPECTED_RESULT_KEYS

    assert main(["report", "--runs", str(run_dir)]) == 0
    report_path = run_dir / "report.md"
    assert report_path.exists()
    assert "# Hermes SkillEval Report" in report_path.read_text(encoding="utf-8")
