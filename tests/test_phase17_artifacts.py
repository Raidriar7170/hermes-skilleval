from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("docs/demo/phase17-calibrated-release-selector")


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_phase17_artifact_pack_exists() -> None:
    required = [
        ROOT / "release-decision.json",
        ROOT / "release-decision.md",
        ROOT / "task-decisions.jsonl",
        ROOT / "release-check-summary.json",
    ]
    for path in required:
        assert path.is_file(), path


def test_phase17_current_decision_keeps_baseline() -> None:
    decision = json.loads((ROOT / "release-decision.json").read_text(encoding="utf-8"))

    assert decision["phase"] == "Phase 17"
    assert decision["artifact_type"] == "phase17-calibrated-release-selector"
    assert decision["source_phase"] == "Phase 16"
    assert decision["source_guard_status"] == "REVIEW_REQUIRED"
    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["selected_router"] == "baseline-minilm"
    assert decision["baseline_router"] == "baseline-minilm"
    assert decision["candidate_router"] == "finetuned-embedding"
    assert decision["approved_for_default"] is False
    assert decision["regression_count"] == 2


def test_phase17_task_decisions_match_task_count_and_include_keep_baseline() -> None:
    decision = json.loads((ROOT / "release-decision.json").read_text(encoding="utf-8"))
    task_decisions = _jsonl(ROOT / "task-decisions.jsonl")

    assert len(task_decisions) == decision["task_count"]
    assert any(record["decision"] == "KEEP_BASELINE" for record in task_decisions)
    assert all(record["aggregate_decision"] == decision["decision"] for record in task_decisions)


def test_phase17_docs_and_handoff_reference_release_selector() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    phase17 = Path("docs/phase17.md").read_text(encoding="utf-8")
    handoff = Path("docs/release-handoff.md").read_text(encoding="utf-8")
    usage = Path("docs/usage.md").read_text(encoding="utf-8")

    assert "Phase 17" in readme
    assert "select-release-router" in usage
    assert "docs/phase17.md" in readme
    assert "docs/demo/phase17-calibrated-release-selector/release-decision.json" in usage
    assert "Phase 17: Calibrated Release Selector" in phase17
    assert "KEEP_BASELINE" in phase17
    assert "selected default router remains `baseline-minilm`" in phase17
    assert "Phase 17" in handoff
    assert "docs/phase17.md" in handoff
    assert "keeps `baseline-minilm` as the default router" in handoff
