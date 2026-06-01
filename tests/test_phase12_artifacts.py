import json
from pathlib import Path


PHASE12_ROOT = Path("docs/demo/phase12-skill-patch-ranking")
README = Path("README.md")
PHASE12_DOC = Path("docs/phase12.md")
TIMELINE = Path("docs/experiment-timeline.md")
USAGE = Path("docs/usage.md")


def test_phase12_patch_ranking_artifacts_are_committed():
    candidates = _read_jsonl(PHASE12_ROOT / "patch-candidates.jsonl")
    ranked = _read_jsonl(PHASE12_ROOT / "ranked-patches.jsonl")
    summary = json.loads((PHASE12_ROOT / "ranking-summary.json").read_text())
    report = (PHASE12_ROOT / "ranked-patches.md").read_text(encoding="utf-8")

    assert summary["phase"] == "Phase 12"
    assert summary["artifact_type"] == "phase12-skill-patch-ranking"
    assert summary["failed_task_count"] == 3
    assert summary["candidate_count"] >= 9
    assert len(candidates) == summary["candidate_count"]
    assert len(ranked) == summary["candidate_count"]
    assert {record["rank"] for record in candidates} == {None}
    assert [record["rank"] for record in ranked] == list(range(1, len(ranked) + 1))
    assert {record["source_task_id"] for record in ranked} == {
        "browser-local-dashboard",
        "claude-command-routing",
        "sp-debug-red-green",
    }
    assert all(record["status"] == "proposed" for record in ranked)
    assert report.startswith("# Phase 12 Skill Patch Ranking")


def test_phase12_docs_and_readme_are_updated():
    readme = README.read_text(encoding="utf-8")
    phase12 = PHASE12_DOC.read_text(encoding="utf-8")
    timeline = TIMELINE.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")

    assert "docs/experiment-timeline.md" in readme
    assert "| Phase 12 | Offline skill metadata patch ranking |" in timeline
    assert "- [x] Offline skill metadata patch ranking" in readme
    assert "rank-skill-patches" in usage
    assert "does not modify source SKILL.md files" in phase12
    assert "negative_skill_selected" in phase12


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
