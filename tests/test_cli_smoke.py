import json
import sys
import types
from pathlib import Path

import yaml

from hermes_skilleval.cli import main
from hermes_skilleval.task_loader import load_tasks


FIXTURES = Path(__file__).parent / "fixtures"

EXPECTED_RESULT_KEYS = {
    "task_id",
    "category",
    "difficulty",
    "split",
    "robustness_tags",
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
    "accepted_count",
    "coverage",
    "selection_rate_at_5",
    "abstention_rate",
    "accepted_recall_at_5",
    "negative_accepted_rate",
}


def test_builtin_benchmark_has_80_tasks():
    tasks = load_tasks(Path("benchmarks/tasks"))

    assert len(tasks) == 80


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


def test_cli_compare_supports_gated_embedding_backend_specs(tmp_path, monkeypatch):
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
                "gated-fake=gated:sentence-transformers",
                "--embedding-model",
                "fake-model",
                "--gated-pool-size",
                "3",
                "--top-k",
                "3",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    record = json.loads(
        (output_dir / "gated-fake" / "results.jsonl").read_text(encoding="utf-8")
    )
    comparison = (output_dir / "comparison.md").read_text(encoding="utf-8")

    assert record["router"] == "gated-fake"
    assert "| gated-fake |" in comparison


def test_cli_eval_cross_encoder_router_smoke(tmp_path, monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [
                [1.0, 0.0] if "debug" in sentence.lower() else [0.0, 1.0]
                for sentence in sentences
            ]

    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs, batch_size=16):
            return [
                5.0 if "systematic debugging" in pair[1].lower() else 1.0
                for pair in pairs
            ]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=FakeSentenceTransformer,
            CrossEncoder=FakeCrossEncoder,
        ),
    )
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "cross-encoder-run"

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
                "cross-encoder",
                "--embedding-backend",
                "sentence-transformers",
                "--embedding-model",
                "fake-embedding",
                "--cross-encoder-model",
                "fake-reranker",
                "--cross-encoder-batch-size",
                "4",
                "--gated-pool-size",
                "3",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    record = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8"))
    assert record["router"] == "cross-encoder"
    assert len(record["selected_skill_ids"]) <= 3


def test_cli_eval_cross_encoder_accepts_calibration_file(tmp_path, monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [[1.0, 0.0] for _ in sentences]

    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs, batch_size=16):
            return [
                5.0 if "systematic debugging" in pair[1].lower() else 1.0
                for pair in pairs
            ]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=FakeSentenceTransformer,
            CrossEncoder=FakeCrossEncoder,
        ),
    )
    calibration_path = tmp_path / "calibration.json"
    calibration_path.write_text(
        json.dumps(
            {
                "score_threshold": 3.0,
                "margin_threshold": 1.0,
                "fit_split": "dev",
                "max_negative_hit_rate": 0.05,
                "fitted_task_count": 2,
                "metrics": {"recall_at_5": 1.0, "negative_hit_rate": 0.0},
            }
        ),
        encoding="utf-8",
    )
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "cross-encoder-calibrated-run"

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
                "cross-encoder",
                "--embedding-backend",
                "sentence-transformers",
                "--embedding-model",
                "fake-embedding",
                "--cross-encoder-model",
                "fake-reranker",
                "--cross-encoder-calibration",
                str(calibration_path),
                "--gated-pool-size",
                "3",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    record = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8"))
    assert record["selected_skill_ids"] == ["systematic-debugging"]


def test_cli_compare_accepts_cross_encoder_router_spec(tmp_path, monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [[1.0, 0.0] for _ in sentences]

    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs, batch_size=16):
            return [2.0 for _ in pairs]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=FakeSentenceTransformer,
            CrossEncoder=FakeCrossEncoder,
        ),
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
                "embedding-fake=embedding:sentence-transformers,"
                "cross-fake=cross-encoder:sentence-transformers",
                "--embedding-model",
                "fake-embedding",
                "--cross-encoder-model",
                "fake-reranker",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert (output_dir / "embedding-fake" / "results.jsonl").exists()
    assert (output_dir / "cross-fake" / "results.jsonl").exists()
    assert (output_dir / "comparison.md").exists()


def test_cli_compare_rejects_invalid_cross_encoder_backend(tmp_path, capsys):
    index_path = tmp_path / "index" / "skills.json"

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
            "compare",
            "--index",
            str(index_path),
            "--tasks",
            str(FIXTURES / "tasks"),
            "--routers",
            "bad-cross=cross-encoder:hashing",
            "--output-dir",
            str(tmp_path / "comparison"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "unknown cross-encoder backend: hashing" in captured.err
    assert "Traceback" not in captured.err


def test_cli_calibrate_cross_encoder_writes_calibration_and_test_results(tmp_path):
    results_path = tmp_path / "rank-only.jsonl"
    calibration_path = tmp_path / "calibration.json"
    calibrated_path = tmp_path / "calibrated" / "results.jsonl"
    results_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                _rank_record(
                    "dev-clear",
                    split="dev",
                    selected=["gold-clear", "other-clear"],
                    scores={"gold-clear": 5.0, "other-clear": 1.0},
                    gold=["gold-clear"],
                    negative=[],
                ),
                _rank_record(
                    "dev-negative",
                    split="dev",
                    selected=["bad-dev", "other-dev"],
                    scores={"bad-dev": 4.5, "other-dev": 4.4},
                    gold=["missing-dev"],
                    negative=["bad-dev"],
                ),
                _rank_record(
                    "test-clear",
                    split="test",
                    selected=["gold-test", "other-test"],
                    scores={"gold-test": 5.0, "other-test": 2.0},
                    gold=["gold-test"],
                    negative=[],
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "calibrate-cross-encoder",
                "--results",
                str(results_path),
                "--output",
                str(calibration_path),
                "--calibrated-output",
                str(calibrated_path),
                "--max-negative-hit-rate",
                "0.0",
            ]
        )
        == 0
    )

    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in calibrated_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert calibration["fit_split"] == "dev"
    assert calibration["fitted_task_count"] == 2
    assert records[0]["task_id"] == "test-clear"
    assert records[0]["router"] == "cross-encoder-calibrated"
    assert records[0]["selected_skill_ids"][0] == "gold-test"
    assert records[0]["negative_hit_rate"] == 0.0


def test_cli_eval_gated_router_supports_selective_confidence_filter(tmp_path):
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "selective-run"

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
                "gated",
                "--selective",
                "--min-confidence",
                "0.5",
                "--gated-pool-size",
                "3",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    record = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8"))

    assert record["router"] == "gated"
    assert set(record["selected_skill_ids"]) == {
        "systematic-debugging",
        "test-driven-development",
    }
    assert "songwriting-and-ai-music" not in record["selected_skill_ids"]
    assert record["accepted_count"] == 2
    assert record["coverage"] == 1.0
    assert record["selection_rate_at_5"] == 0.4
    assert record["abstention_rate"] == 0.0
    assert record["accepted_recall_at_5"] == 1.0
    assert record["negative_accepted_rate"] == 0.0


def test_cli_eval_gated_router_passes_contrastive_options(tmp_path, monkeypatch):
    from hermes_skilleval.routers.gated import VerificationGatedRouter

    captured = {}
    original_init = VerificationGatedRouter.__init__

    def capture_init(self, *args, **kwargs):
        captured.update(kwargs)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(VerificationGatedRouter, "__init__", capture_init)
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "contrastive-run"

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
                "gated",
                "--selective",
                "--contrastive-selective",
                "--contrastive-margin",
                "4.5",
                "--min-evidence",
                "1.5",
                "--gated-pool-size",
                "3",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    assert captured["selective"] is True
    assert captured["contrastive_selective"] is True
    assert captured["contrastive_margin"] == 4.5
    assert captured["min_evidence"] == 1.5


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


def test_cli_improve_skills_writes_patch_outputs(tmp_path):
    index_path = tmp_path / "index" / "skills.json"
    runs_dir = tmp_path / "runs"
    router_dir = runs_dir / "embedding-minilm"
    router_dir.mkdir(parents=True)
    patches_path = tmp_path / "improvement" / "patches.json"
    patched_index_path = tmp_path / "improvement" / "patched-skills.json"
    report_path = tmp_path / "improvement" / "patches.md"

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
    record = {
        "task_id": "python-debugging-001",
        "category": "coding",
        "difficulty": "easy",
        "router": "embedding-minilm",
        "selected_skill_ids": ["songwriting-and-ai-music", "systematic-debugging"],
        "scores": {},
        "gold_skills": ["systematic-debugging", "test-driven-development"],
        "negative_skills": ["songwriting-and-ai-music"],
        "latency_ms": 1.0,
        "recall_at_1": 0.0,
        "recall_at_3": 0.5,
        "recall_at_5": 0.5,
        "precision_at_5": 0.2,
        "mrr": 0.5,
        "ndcg_at_5": 0.5,
        "negative_hit_rate": 1.0,
    }
    (router_dir / "results.jsonl").write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = main(
        [
            "improve-skills",
            "--runs",
            str(runs_dir),
            "--router",
            "embedding-minilm",
            "--index",
            str(index_path),
            "--tasks",
            str(FIXTURES / "tasks"),
            "--output",
            str(patches_path),
            "--patched-index",
            str(patched_index_path),
            "--report",
            str(report_path),
        ]
    )

    payload = json.loads(patches_path.read_text(encoding="utf-8"))
    patched = json.loads(patched_index_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert result == 0
    assert payload["patch_count"] >= 1
    assert any(patch["skill_id"] == "test-driven-development" for patch in payload["patches"])
    assert any("refactor" in skill["trigger_terms"] for skill in patched)
    assert "# Hermes SkillEval Self-Improvement Patches" in report


def test_cli_judge_improvement_writes_acceptance_report(tmp_path):
    runs_dir = tmp_path / "runs"
    for router, recall in (("before", 0.5), ("patched", 1.0)):
        router_dir = runs_dir / router
        router_dir.mkdir(parents=True)
        record = {
            "task_id": "task-001",
            "router": router,
            "selected_skill_ids": ["gold"],
            "gold_skills": ["gold"],
            "negative_skills": [],
            "latency_ms": 1.0,
            "recall_at_1": recall,
            "recall_at_3": recall,
            "recall_at_5": recall,
            "precision_at_5": 0.2,
            "mrr": recall,
            "ndcg_at_5": recall,
            "negative_hit_rate": 0.0,
        }
        (router_dir / "results.jsonl").write_text(
            json.dumps(record, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    output = tmp_path / "acceptance.md"

    result = main(
        [
            "judge-improvement",
            "--runs",
            str(runs_dir),
            "--baseline",
            "before",
            "--candidate",
            "patched",
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert "- Status: accepted" in output.read_text(encoding="utf-8")


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


def test_cli_dashboard_writes_static_html(tmp_path):
    runs = tmp_path / "runs"
    run_dir = runs / "sample-router"
    run_dir.mkdir(parents=True)
    (run_dir / "results.jsonl").write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "router": "sample",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "latency_ms": 7.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "dashboard" / "index.html"

    result = main(["dashboard", "--runs", str(runs), "--output", str(output)])

    assert result == 0
    html = output.read_text(encoding="utf-8")
    assert "Hermes SkillEval Dashboard" in html
    assert "sample-router" in html
    assert "task-001" in html


def test_cli_dashboard_reports_empty_runs_dir(tmp_path, capsys):
    result = main(
        [
            "dashboard",
            "--runs",
            str(tmp_path),
            "--output",
            str(tmp_path / "dashboard.html"),
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    assert "no dashboard runs found" in captured.err


def test_cli_run_agent_loop_writes_trace_artifacts(tmp_path):
    tasks = tmp_path / "tasks"
    task_dir = tasks / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        "\n".join(
            [
                "id: task-001",
                "category: migration",
                "difficulty: easy",
                "gold_skills:",
                "  - systematic-debugging",
                "negative_skills:",
                "  - visual-regression-review",
                "verifier: manual",
                "split: test",
                "robustness_tags:",
                "  - migration-evaluation",
                "migration_source: superpowers",
                "expected_evidence:",
                "  - final evidence noted",
                "migration_dimensions:",
                "  - evidence completeness",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text("Debug and report evidence.", encoding="utf-8")
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                {
                    "id": "systematic-debugging",
                    "name": "Systematic Debugging",
                    "path": "skill/SKILL.md",
                    "category": "superpowers",
                    "description": "Debug failures.",
                    "body": "Debug with evidence.",
                    "trigger_terms": ["debug"],
                    "token_count_estimate": 8,
                }
            ]
        ),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "router": "hybrid",
                "selected_skill_ids": ["systematic-debugging"],
                "scores": {"systematic-debugging": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "agent-loop"

    result = main(
        [
            "run-agent-loop",
            "--routes",
            str(routes),
            "--tasks",
            str(tasks),
            "--skills-index",
            str(skills_index),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "results.jsonl").exists()
    assert (output_dir / "agent-traces.jsonl").exists()
    assert (output_dir / "agent-loop-summary.json").exists()


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


def test_cli_judge_agent_loop_writes_judge_artifacts(tmp_path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "trace_schema_version": "phase10.agent-loop.v1",
                "trace_id": "agent-loop-hybrid:task-001",
                "task_id": "task-001",
                "prompt": "Verify the final evidence.",
                "execution_condition": "routed-skill",
                "source_router": "hybrid",
                "selected_skill_ids": ["verification-before-completion"],
                "agent_status": "passed",
                "agent_success": True,
                "expected_evidence": ["test command shown"],
                "evidence_checks": [{"name": "test command shown", "satisfied": True}],
                "failure_type": None,
                "failure_reason": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "judge"

    result = main(
        [
            "judge-agent-loop",
            "--traces",
            str(traces),
            "--output-dir",
            str(output_dir),
            "--run-label",
            "judge-agent-loop-hybrid",
        ]
    )

    assert result == 0
    assert (output_dir / "judge-results.jsonl").exists()
    assert (output_dir / "results.jsonl").exists()
    assert (output_dir / "judge-summary.json").exists()
    assert (output_dir / "judge-rubric.md").exists()


def test_cli_rank_skill_patches_writes_artifacts(tmp_path):
    tasks = tmp_path / "tasks"
    task_dir = tasks / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "task-001",
                "category": "migration",
                "difficulty": "medium",
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "verifier": "manual",
                "split": "test",
                "robustness_tags": ["migration-evaluation"],
                "expected_evidence": ["opened URL", "nonblank page"],
                "migration_dimensions": ["evidence completeness"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Open the local dashboard and verify a nonblank page.",
        encoding="utf-8",
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                {
                    "id": "browser-smoke-testing",
                    "name": "Browser Smoke Testing",
                    "path": "benchmarks/migrated-skills/test/browser-smoke-testing/SKILL.md",
                    "category": "test",
                    "description": "Open local pages.",
                    "body": "Open local pages.",
                    "trigger_terms": ["browser", "smoke"],
                    "token_count_estimate": 10,
                },
                {
                    "id": "systematic-debugging",
                    "name": "Systematic Debugging",
                    "path": "benchmarks/migrated-skills/test/systematic-debugging/SKILL.md",
                    "category": "test",
                    "description": "Debug failures.",
                    "body": "Debug failures.",
                    "trigger_terms": ["debug"],
                    "token_count_estimate": 10,
                },
            ]
        ),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "router": "hybrid",
                "selected_skill_ids": [
                    "browser-smoke-testing",
                    "systematic-debugging",
                ],
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "scores": {
                    "browser-smoke-testing": 30.0,
                    "systematic-debugging": 20.0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judge = tmp_path / "judge-results.jsonl"
    judge.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "trace_id": "agent-loop-hybrid:task-001",
                "execution_condition": "routed-skill",
                "judge_pass": False,
                "judge_score": 0.0,
                "evidence_score": 0.0,
                "failure_type": "negative_skill_selected",
                "penalties": ["missing-evidence", "negative-skill-failure"],
                "expected_evidence": ["opened URL", "nonblank page"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase12"

    result = main(
        [
            "rank-skill-patches",
            "--judge-results",
            str(judge),
            "--routes",
            str(routes),
            "--tasks",
            str(tasks),
            "--skills-index",
            str(skills_index),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "patch-candidates.jsonl").exists()
    assert (output_dir / "ranked-patches.jsonl").exists()
    assert (output_dir / "ranking-summary.json").exists()
    assert (output_dir / "ranked-patches.md").exists()


def test_cli_simulate_skill_patches_writes_artifacts(tmp_path):
    tasks = tmp_path / "tasks"
    task_dir = tasks / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "task-001",
                "category": "migration",
                "difficulty": "medium",
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "verifier": "manual",
                "split": "test",
                "robustness_tags": ["migration-evaluation"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Open the local browser dashboard and verify a nonblank page.",
        encoding="utf-8",
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                {
                    "id": "browser-smoke-testing",
                    "name": "Browser Smoke Testing",
                    "path": "benchmarks/migrated-skills/test/browser-smoke-testing/SKILL.md",
                    "category": "test",
                    "description": "Open local pages.",
                    "body": "Open local pages.",
                    "trigger_terms": ["browser", "smoke"],
                    "token_count_estimate": 10,
                },
                {
                    "id": "systematic-debugging",
                    "name": "Systematic Debugging",
                    "path": "benchmarks/migrated-skills/test/systematic-debugging/SKILL.md",
                    "category": "test",
                    "description": "Debug failures.",
                    "body": "Debug failures.",
                    "trigger_terms": ["debug"],
                    "token_count_estimate": 10,
                },
            ]
        ),
        encoding="utf-8",
    )
    baseline_routes = tmp_path / "baseline-results.jsonl"
    baseline_routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "category": "migration",
                "difficulty": "medium",
                "split": "test",
                "robustness_tags": ["migration-evaluation"],
                "selected_skill_ids": ["browser-smoke-testing"],
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "recall_at_5": 1.0,
                "mrr": 1.0,
                "ndcg_at_5": 1.0,
                "negative_hit_rate": 0.0,
                "negative_accepted_rate": 0.0,
                "selection_rate_at_5": 0.2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ranked_patches = tmp_path / "ranked-patches.jsonl"
    ranked_patches.write_text(
        json.dumps(
            {
                "candidate_id": "task-001::browser-smoke-testing::description::append_sentence",
                "source_task_id": "task-001",
                "target_skill_id": "browser-smoke-testing",
                "patch_field": "description",
                "operation": "append_sentence",
                "added_terms": ["dashboard"],
                "added_text": "Strengthen metadata for dashboard evidence.",
                "rank": 1,
                "status": "proposed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase13"

    result = main(
        [
            "simulate-skill-patches",
            "--ranked-patches",
            str(ranked_patches),
            "--baseline-routes",
            str(baseline_routes),
            "--tasks",
            str(tasks),
            "--skills-index",
            str(skills_index),
            "--router",
            "hybrid",
            "--top-k",
            "1",
            "--max-patches",
            "1",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "shadow-skills.json").exists()
    assert (output_dir / "shadow-results.jsonl").exists()
    assert (output_dir / "route-diffs.jsonl").exists()
    assert (output_dir / "regression-summary.json").exists()
    assert (output_dir / "regression-report.md").exists()


def test_cli_export_embedding_training_data_writes_pairs(tmp_path):
    tasks = tmp_path / "tasks"
    task_dir = tasks / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "task-001",
                "category": "browser-gui",
                "difficulty": "medium",
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "verifier": "manual",
                "split": "dev",
                "robustness_tags": ["phase14"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Open the local dashboard and verify it is nonblank.",
        encoding="utf-8",
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                {
                    "id": "browser-smoke-testing",
                    "name": "Browser Smoke Testing",
                    "path": "skills/browser-smoke-testing/SKILL.md",
                    "category": "browser-gui",
                    "description": "Open local dashboards.",
                    "body": "# Browser Smoke Testing",
                    "trigger_terms": ["browser", "dashboard"],
                    "token_count_estimate": 10,
                },
                {
                    "id": "systematic-debugging",
                    "name": "Systematic Debugging",
                    "path": "skills/systematic-debugging/SKILL.md",
                    "category": "superpowers",
                    "description": "Investigate bugs.",
                    "body": "# Systematic Debugging",
                    "trigger_terms": ["debug"],
                    "token_count_estimate": 10,
                },
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase14"

    result = main(
        [
            "export-embedding-training-data",
            "--tasks",
            str(tasks),
            "--skills-index",
            str(skills_index),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "training-pairs.jsonl").exists()
    assert (output_dir / "training-summary.json").exists()


def test_cli_judge_finetuned_embedding_writes_summary(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    record = {
        "task_id": "task-001",
        "category": "browser-gui",
        "difficulty": "medium",
        "split": "test",
        "robustness_tags": ["phase14"],
        "selected_skill_ids": ["gold"],
        "gold_skills": ["gold"],
        "negative_skills": ["bad"],
        "recall_at_5": 1.0,
        "mrr": 1.0,
        "ndcg_at_5": 1.0,
        "negative_hit_rate": 0.0,
        "negative_accepted_rate": 0.0,
        "selection_rate_at_5": 0.2,
    }
    baseline.write_text(json.dumps(record) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(record) + "\n", encoding="utf-8")
    output_dir = tmp_path / "phase14"

    result = main(
        [
            "judge-finetuned-embedding",
            "--baseline-results",
            str(baseline),
            "--candidate-results",
            str(candidate),
            "--output-dir",
            str(output_dir),
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        ]
    )

    assert result == 0
    assert (output_dir / "regression-summary.json").exists()
    assert (output_dir / "comparison.md").exists()


def test_cli_judge_finetuned_embedding_filters_to_test_split(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline_records = [
        _finetuned_eval_record("dev-task", split="dev", selected=["gold"]),
        _finetuned_eval_record(
            "test-task",
            split="test",
            selected=["gold", "bad"],
            negative_hit_rate=1.0,
            negative_accepted_rate=1.0,
        ),
    ]
    candidate_records = [
        _finetuned_eval_record(
            "dev-task",
            split="dev",
            selected=["bad"],
            recall_at_5=0.0,
            mrr=0.0,
            ndcg_at_5=0.0,
            negative_hit_rate=1.0,
            negative_accepted_rate=1.0,
        ),
        _finetuned_eval_record(
            "test-task",
            split="test",
            selected=["gold", "bad"],
            negative_hit_rate=1.0,
            negative_accepted_rate=1.0,
        ),
    ]
    baseline.write_text(
        "".join(json.dumps(record) + "\n" for record in baseline_records),
        encoding="utf-8",
    )
    candidate.write_text(
        "".join(json.dumps(record) + "\n" for record in candidate_records),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase15"

    result = main(
        [
            "judge-finetuned-embedding",
            "--baseline-results",
            str(baseline),
            "--candidate-results",
            str(candidate),
            "--output-dir",
            str(output_dir),
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            "--apply-split",
            "test",
            "--write-filtered-results",
        ]
    )

    assert result == 0
    summary = json.loads((output_dir / "regression-summary.json").read_text())
    assert summary["evaluated_split"] == "test"
    assert summary["split_policy"] == "records where split == 'test'"
    assert summary["source_task_count"] == 2
    assert summary["task_count"] == 1
    assert summary["guard_status"] == "PASS"
    assert summary["artifact_type"] == "phase15-heldout-finetuned-embedding-eval"
    assert (output_dir / "baseline-test-results.jsonl").exists()
    assert (output_dir / "finetuned-test-results.jsonl").exists()


def test_cli_write_model_manifest_writes_manifest(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "model-manifest.json"

    result = main(
        [
            "write-model-manifest",
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            "--local-model-dir",
            str(model_dir),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert manifest["files"][0]["path"] == "config.json"


def test_cli_write_finetuned_provenance_writes_pack(tmp_path):
    training_summary = tmp_path / "training-summary.json"
    train_config = tmp_path / "train-config.json"
    train_run_summary = tmp_path / "train-run-summary.json"
    model_manifest = tmp_path / "model-manifest.json"
    regression_summary = tmp_path / "regression-summary.json"
    training_summary.write_text(
        json.dumps(
            {
                "pair_count": 28,
                "positive_count": 16,
                "hard_negative_count": 12,
                "leakage_guard": "PASS",
            }
        ),
        encoding="utf-8",
    )
    train_config.write_text(
        json.dumps(
            {
                "loss": "MultipleNegativesRankingLoss+ContrastiveLoss",
                "hard_negative_margin": 1.5,
                "epochs": 3,
                "batch_size": 8,
                "learning_rate": 2e-5,
                "base_model": "/mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2",
                "output_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            }
        ),
        encoding="utf-8",
    )
    train_run_summary.write_text(
        json.dumps(
            {
                "device": "cuda:0",
                "epoch_count": 3,
                "trained_pair_count": 11,
                "trained_hard_negative_pair_count": 8,
                "optimizer_step_count": 6,
                "hard_negative_optimizer_step_count": 3,
                "final_loss": 0.2228596806526184,
            }
        ),
        encoding="utf-8",
    )
    model_manifest.write_text(
        json.dumps(
            {
                "model_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
                "file_count": 1,
                "total_size_bytes": 2,
                "files": [
                    {"path": "config.json", "size_bytes": 2, "sha256": "0" * 64}
                ],
            }
        ),
        encoding="utf-8",
    )
    regression_summary.write_text(
        json.dumps(
            {
                "evaluated_split": "test",
                "source_task_count": 12,
                "task_count": 4,
                "guard_status": "PASS",
                "regression_count": 0,
                "metric_deltas": {"recall_at_5": 0.0},
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase15"

    result = main(
        [
            "write-finetuned-provenance",
            "--training-summary",
            str(training_summary),
            "--train-config",
            str(train_config),
            "--train-run-summary",
            str(train_run_summary),
            "--model-manifest",
            str(model_manifest),
            "--regression-summary",
            str(regression_summary),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "provenance.json").exists()
    assert (output_dir / "provenance.md").exists()


def test_cli_write_blind_validation_summary(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    record = _finetuned_eval_record(
        "blind-task",
        split="test",
        selected=["apply-patch-discipline"],
        gold=("apply-patch-discipline",),
        negative=("workspace-git-hygiene",),
    )
    baseline.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    result = main(
        [
            "write-blind-validation",
            "--baseline-results",
            str(baseline),
            "--candidate-results",
            str(candidate),
            "--output-dir",
            str(tmp_path / "out"),
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            "--task-root",
            "benchmarks/blind-migration-tasks",
        ]
    )

    assert result == 0
    summary = json.loads((tmp_path / "out" / "regression-summary.json").read_text())
    assert summary["guard_status"] == "PASS"


def test_cli_verify_release_reports_json_summary(tmp_path):
    public_file = tmp_path / "README.md"
    public_file.write_text("# Release\n", encoding="utf-8")

    result = main(
        [
            "verify-release",
            "--public-root",
            str(tmp_path),
            "--required-path",
            str(public_file),
            "--summary-output",
            str(tmp_path / "release-check-summary.json"),
        ]
    )

    assert result == 0
    summary = json.loads((tmp_path / "release-check-summary.json").read_text())
    assert summary["status"] == "PASS"


def _finetuned_eval_record(
    task_id,
    *,
    split,
    selected,
    gold=("gold",),
    negative=("bad",),
    recall_at_5=1.0,
    mrr=1.0,
    ndcg_at_5=1.0,
    negative_hit_rate=0.0,
    negative_accepted_rate=0.0,
):
    return {
        "task_id": task_id,
        "category": "agent",
        "difficulty": "medium",
        "split": split,
        "robustness_tags": ["phase15"],
        "selected_skill_ids": list(selected),
        "gold_skills": list(gold),
        "negative_skills": list(negative),
        "recall_at_5": recall_at_5,
        "mrr": mrr,
        "ndcg_at_5": ndcg_at_5,
        "negative_hit_rate": negative_hit_rate,
        "negative_accepted_rate": negative_accepted_rate,
        "selection_rate_at_5": len(selected) / 5,
    }


def _rank_record(task_id, *, split, selected, scores, gold, negative):
    return {
        "task_id": task_id,
        "category": "coding",
        "difficulty": "medium",
        "split": split,
        "robustness_tags": [],
        "router": "cross-encoder-rank-only",
        "selected_skill_ids": selected,
        "scores": scores,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": 1.0,
    }
