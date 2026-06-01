import json
import re
from pathlib import Path

import yaml

from hermes_skilleval.dashboard import write_dashboard
from hermes_skilleval.task_loader import load_tasks


PHASE9_ROOT = Path("docs/demo/phase9-real-skill-library-migration")
MIGRATED_SKILLS = Path("benchmarks/migrated-skills")
MIGRATION_TASKS = Path("benchmarks/migration-tasks")
README = Path("README.md")
PHASE9_DOC = Path("docs/phase9.md")
TIMELINE = Path("docs/experiment-timeline.md")


EXPECTED_SKILL_FAMILIES = {
    "superpowers",
    "codex",
    "claude-code",
    "browser-gui",
}

EXPECTED_ADAPTER_PROVENANCE = {
    "apply-patch-discipline": {
        "adapter_kind": "codex-orchestrator-adapter",
        "source_collection": "codex-global-routing",
        "original_path": ".codex/AGENTS.md#codex-orchestrator-apply-protocol",
    },
    "evidence-backed-final": {
        "adapter_kind": "codex-orchestrator-adapter",
        "source_collection": "codex-global-routing",
        "original_path": ".codex/AGENTS.md#codex-orchestrator-apply-protocol",
    },
    "subagent-worker-protocol": {
        "adapter_kind": "codex-orchestrator-adapter",
        "source_collection": "codex-global-routing",
        "original_path": ".codex/AGENTS.md#codex-orchestrator-apply-protocol",
    },
    "workspace-git-hygiene": {
        "adapter_kind": "codex-orchestrator-adapter",
        "source_collection": "codex-global-routing",
        "original_path": ".codex/AGENTS.md#codex-orchestrator-apply-protocol",
    },
    "accessibility-tree-inspection": {
        "adapter_kind": "browser-gui-adapter",
        "source_collection": "openai-bundled-computer-use",
        "original_path": "openai-bundled/computer-use/skills/computer-use/SKILL.md",
    },
    "browser-smoke-testing": {
        "adapter_kind": "browser-gui-adapter",
        "source_collection": "openai-bundled-browser",
        "original_path": "openai-bundled/browser/skills/browser/SKILL.md",
    },
    "form-interaction-flow": {
        "adapter_kind": "browser-gui-adapter",
        "source_collection": "openai-bundled-chrome",
        "original_path": "openai-bundled/chrome/skills/chrome/SKILL.md",
    },
    "visual-regression-review": {
        "adapter_kind": "browser-gui-adapter",
        "source_collection": "openai-bundled-browser",
        "original_path": "openai-bundled/browser/skills/browser/SKILL.md",
    },
}


def test_phase9_migrated_skill_corpus_preserves_source_metadata():
    skill_files = sorted(MIGRATED_SKILLS.rglob("SKILL.md"))

    assert len(skill_files) == 16

    families = {path.relative_to(MIGRATED_SKILLS).parts[0] for path in skill_files}
    assert families == EXPECTED_SKILL_FAMILIES

    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        metadata = yaml.safe_load(text.split("---", 2)[1])
        assert metadata["migration_source"] in EXPECTED_SKILL_FAMILIES
        assert metadata["original_path"]
        assert not metadata["original_path"].startswith("/")
        assert metadata["migration_date"] == "2026-05-28"
        assert "adapter_notes" in metadata
        assert metadata["source_snapshot_kind"] == "short-verbatim-excerpt"
        assert 25 <= metadata["source_snapshot_words"] <= 60
        assert "## Source Snapshot" in text
        assert metadata["source_snapshot_words"] == _source_snapshot_word_count(text)
        if metadata["migration_source"] == "claude-code":
            assert metadata["adapter_kind"] == "claude-code-style-adapter"
            assert metadata["source_collection"] == "hermes-autonomous-ai-agents"
            assert metadata["original_path"] == (
                "hermes/autonomous-ai-agents/claude-code/SKILL.md"
            )
            assert metadata["source_snapshot_label"].startswith(
                "Hermes Claude Code orchestration guide"
            )
        if path.parent.name in EXPECTED_ADAPTER_PROVENANCE:
            assert {
                "adapter_kind": metadata["adapter_kind"],
                "source_collection": metadata["source_collection"],
                "original_path": metadata["original_path"],
            } == EXPECTED_ADAPTER_PROVENANCE[path.parent.name]


def test_phase9_migration_tasks_cover_sources_and_evidence_dimensions():
    task_files = sorted(MIGRATION_TASKS.rglob("task.yaml"))
    loaded_tasks = load_tasks(MIGRATION_TASKS)
    skill_ids = {
        path.parent.name
        for path in MIGRATED_SKILLS.rglob("SKILL.md")
    }

    assert len(task_files) == 12
    assert len(loaded_tasks) == 12

    covered_sources = set()
    for task_file in task_files:
        task = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        prompt = (task_file.parent / "prompt.md").read_text(encoding="utf-8").strip()

        covered_sources.add(task["migration_source"])
        assert task["gold_skills"]
        assert task["negative_skills"]
        assert task["expected_evidence"]
        assert task["migration_dimensions"]
        assert "migration-evaluation" in task["robustness_tags"]
        assert set(task["gold_skills"]).issubset(skill_ids)
        assert set(task["negative_skills"]).issubset(skill_ids)
        assert prompt

    assert covered_sources == EXPECTED_SKILL_FAMILIES


def test_phase9_demo_artifacts_are_committed_and_auditable():
    skills = json.loads((PHASE9_ROOT / "skills.json").read_text(encoding="utf-8"))
    summary = json.loads((PHASE9_ROOT / "migration-summary.json").read_text(encoding="utf-8"))
    dashboard = (PHASE9_ROOT / "dashboard.html").read_text(encoding="utf-8")
    failure_analysis = (PHASE9_ROOT / "failure-analysis.md").read_text(encoding="utf-8")
    comparison = (PHASE9_ROOT / "comparison.md").read_text(encoding="utf-8")

    assert len(skills) == 16
    assert summary["phase"] == "Phase 9"
    assert summary["task_count"] == 12
    assert summary["skill_count"] == 16
    assert set(summary["migration_sources"]) == EXPECTED_SKILL_FAMILIES
    assert summary["environment_limitations"] == [
        "Neural MiniLM and cross-encoder migration runs are documented as follow-up work; committed Phase 9 artifacts use offline deterministic routers."
    ]
    assert summary["metadata_policy"] == (
        "migration_source, expected_evidence, and migration_dimensions are Phase 9 audit metadata read from task.yaml; current router result records do not score these fields."
    )
    assert "routing_miss" in summary["failure_taxonomy"]
    assert "tool_adaptation_failure" in summary["failure_taxonomy"]
    assert "instruction_drift" in summary["failure_taxonomy"]
    assert "evidence_gap" in summary["failure_taxonomy"]
    assert len(summary["per_task_routes"]) == 12
    assert {
        route["task_id"]
        for route in summary["per_task_routes"]
    } == {
        path.parent.name
        for path in MIGRATION_TASKS.rglob("task.yaml")
    }

    for router in ("hybrid", "embedding-hashing", "gated-hashing-selective"):
        records = _read_jsonl(PHASE9_ROOT / router / "results.jsonl")
        assert len(records) == 12
        assert (PHASE9_ROOT / router / "report.md").exists()
        assert summary["router_metrics"][router] == {
            "task_count": 12,
            "recall_at_5": _mean(records, "recall_at_5"),
            "negative_hit_rate": _mean(records, "negative_hit_rate"),
        }
        records_by_task = {record["task_id"]: record for record in records}
        for route in summary["per_task_routes"]:
            route_record = records_by_task[route["task_id"]]
            route_router = route["routers"][router]
            assert route_router["selected_skill_ids"] == route_record["selected_skill_ids"][:5]
            assert route_router["recall_at_5"] == round(float(route_record["recall_at_5"]), 3)
            assert route_router["negative_hit_rate"] == round(
                float(route_record["negative_hit_rate"]),
                3,
            )

    for route in summary["per_task_routes"]:
        assert route["task_id"]
        assert route["migration_source"] in EXPECTED_SKILL_FAMILIES
        assert route["expected_evidence"]
        assert route["migration_dimensions"]
        assert set(route["routers"]) == {
            "hybrid",
            "embedding-hashing",
            "gated-hashing-selective",
        }

    assert "Phase 9 Real Skill-Library Migration" in dashboard
    assert "12 migration records" in dashboard
    assert "Migrated sources" in dashboard
    assert "browser-gui, claude-code, codex, superpowers" in dashboard
    assert "Hermes SkillEval Router Comparison" in comparison
    assert "Migration Failure Taxonomy" in failure_analysis


def test_phase9_is_documented_in_readme_and_phase_notes():
    readme = README.read_text(encoding="utf-8")
    phase9 = PHASE9_DOC.read_text(encoding="utf-8")
    timeline = TIMELINE.read_text(encoding="utf-8")

    assert "docs/experiment-timeline.md" in readme
    assert "| Phase 9 | Real skill-library migration evaluation |" in timeline
    assert "- [x] Real skill-library migration test protocol" in readme
    assert "Phase 9" in readme
    assert "12 migration tasks" in phase9
    assert "16 migrated skills" in phase9
    assert "offline deterministic routers" in phase9
    assert "audit metadata" in phase9
    assert "source snapshot" in phase9


def test_phase9_dashboard_can_be_regenerated_from_committed_runs(tmp_path):
    output = tmp_path / "phase9-dashboard.html"

    write_dashboard(PHASE9_ROOT, output)

    html = output.read_text(encoding="utf-8")
    assert "docs/demo/phase9-real-skill-library-migration" in html
    assert "12 task records" in html
    assert "Migrated sources" in html
    assert "browser-gui, claude-code, codex, superpowers" in html
    assert "hybrid" in html
    assert "embedding-hashing" in html
    assert "gated-hashing-selective" in html


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mean(records: list[dict[str, object]], metric: str) -> float:
    values = []
    for record in records:
        value = record[metric]
        assert isinstance(value, int | float)
        values.append(float(value))
    return round(sum(values) / len(values), 3)


def _source_snapshot_word_count(text: str) -> int:
    excerpt = text.split("````text", 1)[1].split("````", 1)[0]
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", excerpt))
