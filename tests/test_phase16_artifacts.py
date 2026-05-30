from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("docs/demo/phase16-blind-validation")
CHECKPOINT_SUFFIXES = {".bin", ".ckpt", ".pt", ".pth", ".safetensors"}


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_phase16_artifact_pack_exists_and_is_blind_only() -> None:
    required = [
        ROOT / "baseline-minilm" / "results.jsonl",
        ROOT / "baseline-minilm" / "report.md",
        ROOT / "finetuned-embedding" / "results.jsonl",
        ROOT / "finetuned-embedding" / "report.md",
        ROOT / "regression-summary.json",
        ROOT / "route-diffs.jsonl",
        ROOT / "comparison.md",
        ROOT / "dashboard.html",
    ]
    for path in required:
        assert path.is_file(), path

    baseline = _jsonl(ROOT / "baseline-minilm" / "results.jsonl")
    candidate = _jsonl(ROOT / "finetuned-embedding" / "results.jsonl")
    assert len(baseline) == 16
    assert len(candidate) == 16
    assert {record["task_id"] for record in baseline} == {
        record["task_id"] for record in candidate
    }
    assert {record["split"] for record in baseline + candidate} == {"test"}
    assert all("blind-validation" in record["robustness_tags"] for record in baseline + candidate)


def test_phase16_summary_shape_and_review_required_result() -> None:
    summary = json.loads((ROOT / "regression-summary.json").read_text(encoding="utf-8"))

    assert summary["phase"] == "Phase 16"
    assert summary["artifact_type"] == "phase16-blind-validation"
    assert summary["task_count"] == 16
    assert summary["model_checkpoint_committed"] is False
    assert summary["guard_status"] == "REVIEW_REQUIRED"
    assert summary["regression_count"] == 2
    assert summary["metric_deltas"]["recall_at_5"] == 0.0
    assert summary["metric_deltas"]["negative_hit_rate"] == 0.0625


def test_phase16_public_artifacts_avoid_overclaims() -> None:
    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "comparison.md",
            ROOT / "baseline-minilm" / "report.md",
            ROOT / "finetuned-embedding" / "report.md",
        ]
    ).lower()
    forbidden = ["state-of-the-art", "production-ready"]
    for phrase in forbidden:
        assert phrase not in public_text
    assert "external benchmark" not in public_text


def test_phase16_artifact_pack_does_not_commit_checkpoints() -> None:
    checkpoint_files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix in CHECKPOINT_SUFFIXES
    ]
    assert checkpoint_files == []
