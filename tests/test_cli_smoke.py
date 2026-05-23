import json
import sys
import types
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


def test_cli_eval_embedding_router_smoke(tmp_path):
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "embedding-run"

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

    assert (
        main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--router",
                "embedding",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    record = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8"))
    assert record["router"] == "embedding"
    assert len(record["selected_skill_ids"]) <= 3


def test_cli_eval_sentence_transformer_embedding_backend_smoke(
    tmp_path,
    monkeypatch,
):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [
                [1.0, 0.0] if "debug" in sentence.lower() else [0.0, 1.0]
                for sentence in sentences
            ]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "embedding-run"
    cache_path = tmp_path / "cache" / "embeddings.json"

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

    assert (
        main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--router",
                "embedding",
                "--embedding-backend",
                "sentence-transformers",
                "--embedding-model",
                "fake-model",
                "--embedding-cache",
                str(cache_path),
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    record = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8"))
    assert record["router"] == "embedding"
    assert cache_path.exists()


def test_cli_eval_sentence_transformer_missing_dependency_returns_error_without_traceback(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "embedding-run"

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
            "--router",
            "embedding",
            "--embedding-backend",
            "sentence-transformers",
            "--embedding-model",
            "missing-model",
            "--top-k",
            "3",
            "--output-dir",
            str(run_dir),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "sentence-transformers backend requires optional dependency" in captured.err
    assert "Traceback" not in captured.err
    assert not run_dir.exists()


def test_cli_compare_writes_router_runs_and_summary(tmp_path):
    index_path = tmp_path / "index" / "skills.json"
    output_dir = tmp_path / "comparison"

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

    assert (
        main(
            [
                "compare",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--routers",
                "keyword,embedding",
                "--top-k",
                "3",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert (output_dir / "keyword" / "results.jsonl").exists()
    assert (output_dir / "keyword" / "report.md").exists()
    assert (output_dir / "embedding" / "results.jsonl").exists()
    assert (output_dir / "embedding" / "report.md").exists()
    comparison = (output_dir / "comparison.md").read_text(encoding="utf-8")
    assert "# Hermes SkillEval Router Comparison" in comparison
    assert "| keyword |" in comparison
    assert "| embedding |" in comparison
    assert "Recall@5" in comparison


def test_cli_compare_supports_labeled_embedding_backend_specs(tmp_path, monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [
                [1.0, 0.0] if "debug" in sentence.lower() else [0.0, 1.0]
                for sentence in sentences
            ]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    index_path = tmp_path / "index" / "skills.json"
    output_dir = tmp_path / "comparison"

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

    assert (
        main(
            [
                "compare",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--routers",
                ",".join(
                    [
                        "keyword",
                        "embedding-hashing=embedding:hashing",
                        "embedding-fake=embedding:sentence-transformers",
                    ]
                ),
                "--embedding-model",
                "fake-model",
                "--top-k",
                "3",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    hashing_record = json.loads(
        (output_dir / "embedding-hashing" / "results.jsonl").read_text(
            encoding="utf-8"
        )
    )
    fake_record = json.loads(
        (output_dir / "embedding-fake" / "results.jsonl").read_text(encoding="utf-8")
    )
    comparison = (output_dir / "comparison.md").read_text(encoding="utf-8")

    assert hashing_record["router"] == "embedding-hashing"
    assert fake_record["router"] == "embedding-fake"
    assert "| embedding-hashing |" in comparison
    assert "| embedding-fake |" in comparison


def test_cli_analyze_failures_writes_report_from_comparison_dir(tmp_path):
    output_dir = tmp_path / "comparison"
    for router in ("embedding-hashing", "embedding-minilm"):
        router_dir = output_dir / router
        router_dir.mkdir(parents=True)
        record = {
            "task_id": "task-001",
            "category": "coding",
            "difficulty": "easy",
            "router": router,
            "selected_skill_ids": ["gold-skill"],
            "scores": {"gold-skill": 1.0},
            "gold_skills": ["gold-skill"],
            "negative_skills": ["negative-skill"],
            "latency_ms": 1.0,
            "recall_at_1": 1.0,
            "recall_at_3": 1.0,
            "recall_at_5": 1.0,
            "precision_at_5": 0.2,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 0.0,
        }
        (router_dir / "results.jsonl").write_text(
            json.dumps(record, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    result = main(
        [
            "analyze-failures",
            "--runs",
            str(output_dir),
            "--baseline",
            "embedding-hashing",
            "--candidate",
            "embedding-minilm",
        ]
    )

    report = output_dir / "failure-analysis.md"
    assert result == 0
    assert report.exists()
    assert "# Hermes SkillEval Failure Analysis" in report.read_text(encoding="utf-8")


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
