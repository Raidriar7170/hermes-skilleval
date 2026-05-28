import json
from pathlib import Path


PHASE11_ROOT = Path("docs/demo/phase11-evidence-judge-calibration")
README = Path("README.md")
PHASE11_DOC = Path("docs/phase11.md")

RUNS = {
    "judge-agent-loop-no-skill-hybrid": "no-skill",
    "judge-agent-loop-hybrid": "routed-skill",
    "judge-agent-loop-oracle-skill-hybrid": "oracle-skill",
}


def test_phase11_judge_artifacts_cover_three_conditions():
    for run_label, condition in RUNS.items():
        run_dir = PHASE11_ROOT / run_label
        judge_results = _read_jsonl(run_dir / "judge-results.jsonl")
        dashboard_results = _read_jsonl(run_dir / "results.jsonl")
        summary = json.loads((run_dir / "judge-summary.json").read_text())
        rubric = (run_dir / "judge-rubric.md").read_text(encoding="utf-8")

        assert len(judge_results) == 12
        assert len(dashboard_results) == 12
        assert summary["phase"] == "Phase 11"
        assert summary["judge_backend"] == "deterministic-rubric"
        assert summary["task_count"] == 12
        assert summary["execution_condition"] == condition
        assert rubric.startswith("# Phase 11 Evidence Judge Rubric")
        assert {record["execution_condition"] for record in judge_results} == {condition}
        assert all(record["prompt"] for record in judge_results)
        assert all("judge_score" in record for record in dashboard_results)
        assert all("evidence_score" in record for record in dashboard_results)
        assert all("judge_pass_rate" in record for record in dashboard_results)

    no_skill = json.loads(
        (PHASE11_ROOT / "judge-agent-loop-no-skill-hybrid" / "judge-summary.json")
        .read_text(encoding="utf-8")
    )
    routed = json.loads(
        (PHASE11_ROOT / "judge-agent-loop-hybrid" / "judge-summary.json")
        .read_text(encoding="utf-8")
    )
    oracle = json.loads(
        (PHASE11_ROOT / "judge-agent-loop-oracle-skill-hybrid" / "judge-summary.json")
        .read_text(encoding="utf-8")
    )

    assert no_skill["judge_pass_rate"] == 0.0
    assert routed["judge_pass_rate"] > no_skill["judge_pass_rate"]
    assert oracle["judge_pass_rate"] == 1.0


def test_phase11_dashboard_and_docs_are_committed():
    dashboard = (PHASE11_ROOT / "dashboard.html").read_text(encoding="utf-8")
    comparison = (PHASE11_ROOT / "comparison.md").read_text(encoding="utf-8")
    summary = json.loads((PHASE11_ROOT / "phase11-summary.json").read_text())
    readme = README.read_text(encoding="utf-8")
    phase11 = PHASE11_DOC.read_text(encoding="utf-8")

    assert "judge-agent-loop-hybrid" in dashboard
    assert "judge_score" in dashboard
    assert "judge proxy" in dashboard
    assert "Hermes SkillEval Router Comparison" in comparison
    assert "judge proxy" in comparison
    assert summary["phase"] == "Phase 11"
    assert "| Phase 11 | Evidence judge calibration |" in readme
    assert "judge-agent-loop" in readme
    assert "deterministic-rubric" in phase11
    assert "does not require API keys" in phase11
    assert "judge proxy" in phase11


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
