import json
from pathlib import Path

from hermes_skilleval.skill_index import load_skill_index


PHASE13_ROOT = Path("docs/demo/phase13-patch-simulation")
README = Path("README.md")
PHASE13_DOC = Path("docs/phase13.md")
TIMELINE = Path("docs/experiment-timeline.md")


def test_phase13_patch_simulation_artifacts_are_committed():
    summary = json.loads((PHASE13_ROOT / "regression-summary.json").read_text())
    diffs = _read_jsonl(PHASE13_ROOT / "route-diffs.jsonl")
    shadow_results = _read_jsonl(PHASE13_ROOT / "shadow-results.jsonl")
    shadow_skills = json.loads((PHASE13_ROOT / "shadow-skills.json").read_text())
    loaded_shadow_skills = load_skill_index(PHASE13_ROOT / "shadow-skills.json")
    report = (PHASE13_ROOT / "regression-report.md").read_text(encoding="utf-8")

    assert summary["phase"] == "Phase 13"
    assert summary["artifact_type"] == "phase13-patch-simulation"
    assert summary["applied_candidate_count"] == 5
    assert len(diffs) == summary["task_count"]
    assert len(shadow_results) == summary["task_count"]
    assert isinstance(shadow_skills, list)
    assert len(loaded_shadow_skills) == len(shadow_skills)
    assert set(shadow_skills[0]) == {
        "id",
        "name",
        "path",
        "category",
        "description",
        "body",
        "trigger_terms",
        "token_count_estimate",
    }
    assert report.startswith("# Phase 13 Patch Simulation")
    assert summary["source_mutation"] == "none; source SKILL.md files are not modified"
    assert summary["patched_skill_ids"]


def test_phase13_docs_and_readme_are_updated():
    readme = README.read_text(encoding="utf-8")
    phase13 = PHASE13_DOC.read_text(encoding="utf-8")
    timeline = TIMELINE.read_text(encoding="utf-8")

    assert "docs/experiment-timeline.md" in readme
    assert "| Phase 13 | Patch simulation regression guard |" in timeline
    assert "simulate-skill-patches" in readme
    assert "does not modify source SKILL.md files" in phase13
    assert "regression-summary.json" in phase13


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
