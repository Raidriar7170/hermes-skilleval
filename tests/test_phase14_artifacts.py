import json
from pathlib import Path


PHASE14_ROOT = Path("docs/demo/phase14-finetuned-embedding-router")
README = Path("README.md")
PHASE14_DOC = Path("docs/phase14.md")
TRAIN_SCRIPT = Path("scripts/train_embedding_router.py")


def test_phase14_training_data_artifacts_are_committed():
    pairs = _read_jsonl(PHASE14_ROOT / "training-pairs.jsonl")
    summary = json.loads((PHASE14_ROOT / "training-summary.json").read_text())
    config = json.loads((PHASE14_ROOT / "train-config.json").read_text())
    model_card = (PHASE14_ROOT / "model-card.md").read_text(encoding="utf-8")

    assert summary["phase"] == "Phase 14"
    assert summary["artifact_type"] == "phase14-embedding-training-data"
    assert summary["pair_count"] == len(pairs)
    assert summary["positive_count"] > 0
    assert summary["hard_negative_count"] > 0
    assert summary["leakage_guard"] == "PASS"
    assert config["output_dir"].startswith("/mnt/data/minghongsun/")
    assert config["model_checkpoint_committed"] is False
    assert "checkpoint is not committed" in model_card
    assert TRAIN_SCRIPT.exists()


def test_phase14_docs_do_not_overclaim_without_eval_artifacts():
    readme = README.read_text(encoding="utf-8")
    phase14 = PHASE14_DOC.read_text(encoding="utf-8")

    assert "export-embedding-training-data" in readme
    assert "judge-finetuned-embedding" in readme
    assert "Fine-tuned embedding router" in phase14
    assert "does not establish SOTA" in phase14
    assert "standard external benchmark" in phase14
    if not (PHASE14_ROOT / "finetuned-results.jsonl").exists():
        assert "- [ ] Fine-tuned embedding router" in readme


def test_phase14_real_eval_artifacts_pass_hard_negative_guard():
    summary_path = PHASE14_ROOT / "regression-summary.json"
    if not summary_path.exists():
        return

    readme = README.read_text(encoding="utf-8")
    phase14 = PHASE14_DOC.read_text(encoding="utf-8")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    baseline = _read_jsonl(PHASE14_ROOT / "baseline-results.jsonl")
    candidate = _read_jsonl(PHASE14_ROOT / "finetuned-results.jsonl")

    assert len(baseline) == len(candidate) == summary["task_count"] == 12
    assert summary["artifact_type"] == "phase14-finetuned-embedding-eval"
    assert summary["model_checkpoint_committed"] is False
    assert summary["guard_status"] == "PASS"
    assert summary["regression_count"] == 0
    assert summary["metric_deltas"]["negative_hit_rate"] < 0
    assert "- [x] Fine-tuned embedding router" in readme
    assert "regression guard is `PASS`" in phase14
    assert "browser-local-dashboard" in phase14


def test_readme_test_counts_match_verified_suite_size():
    readme = README.read_text(encoding="utf-8")

    assert "| Test cases | 296 |" in readme
    assert "296 passed" in readme
    assert "211 passed" not in readme
    assert "214 passed" not in readme
    assert "217 passed" not in readme
    assert "218 passed" not in readme
    assert "228 passed" not in readme
    assert "240 passed" not in readme
    assert "244 passed" not in readme
    assert "274 passed" not in readme
    assert "| Test cases | 199 |" not in readme


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
