import json
from pathlib import Path

from hermes_skilleval.cli import main
from hermes_skilleval.task_loader import load_tasks


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


def test_builtin_benchmark_has_30_tasks():
    tasks = load_tasks(Path("benchmarks/tasks"))

    assert len(tasks) == 30


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
    assert len(records) == 1
    assert set(records[0]) == EXPECTED_RESULT_KEYS
    assert records[0]["router"] == "hybrid"
    assert len(records[0]["selected_skill_ids"]) <= 3

    assert main(["report", "--runs", str(run_dir)]) == 0
    report_path = run_dir / "report.md"
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "# Hermes SkillEval Report" in report
    assert "## Metrics" in report
    assert "## Top Selected Skills" in report
    assert "## Task Results" in report


def test_cli_main_returns_one_and_prints_help_without_command(capsys):
    assert main([]) == 1
    assert "usage: skilleval" in capsys.readouterr().out


def test_cli_eval_missing_index_returns_error_without_traceback(tmp_path, capsys):
    result = main(
        [
            "eval",
            "--index",
            str(tmp_path / "missing-skills.json"),
            "--tasks",
            str(FIXTURES / "tasks"),
            "--output-dir",
            str(tmp_path / "run"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_index_malformed_skill_frontmatter_returns_error_without_traceback(tmp_path, capsys):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "coding" / "bad-skill"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        "---\n"
        "name: Bad Skill\n"
        "description: [unterminated\n"
        "---\n"
        "# Bad Skill\n",
        encoding="utf-8",
    )

    result = main(
        [
            "index",
            "--skills-path",
            str(skills_root),
            "--output",
            str(tmp_path / "index" / "skills.json"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "error:" in captured.err
    assert "malformed skill frontmatter" in captured.err
    assert str(skill_path) in captured.err
    assert "Traceback" not in captured.err


def test_cli_report_missing_results_returns_error_without_traceback(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = main(["report", "--runs", str(run_dir)])

    captured = capsys.readouterr()
    assert result == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_eval_rejects_non_positive_top_k_before_creating_output(tmp_path, capsys):
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

    result = main(
        [
            "eval",
            "--index",
            str(index_path),
            "--tasks",
            str(FIXTURES / "tasks"),
            "--top-k",
            "0",
            "--output-dir",
            str(run_dir),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "top-k" in captured.err
    assert not (run_dir / "results.jsonl").exists()
    assert not run_dir.exists()
