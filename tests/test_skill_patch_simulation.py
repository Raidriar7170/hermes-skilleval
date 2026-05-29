import json
from pathlib import Path

import pytest

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.skill_patch_simulation import (
    apply_ranked_patch_candidates,
    compare_route_records,
    simulate_skill_patches,
)


def test_apply_ranked_patch_candidates_returns_shadow_copy_without_mutating_source():
    original = Skill(
        id="browser-smoke-testing",
        name="Browser Smoke Testing",
        path="skills/browser-smoke-testing/SKILL.md",
        category="test",
        description="Open local pages.",
        body="# Browser Smoke Testing",
        trigger_terms=["browser"],
        token_count_estimate=10,
    )
    candidates = [
        {
            "candidate_id": "task-001::browser-smoke-testing::trigger_terms::append_terms",
            "source_task_id": "task-001",
            "target_skill_id": "browser-smoke-testing",
            "patch_field": "trigger_terms",
            "operation": "append_terms",
            "added_terms": ["dashboard", "browser"],
            "added_text": "",
            "rank": 1,
            "status": "proposed",
        },
        {
            "candidate_id": "task-001::browser-smoke-testing::description::append_sentence",
            "source_task_id": "task-001",
            "target_skill_id": "browser-smoke-testing",
            "patch_field": "description",
            "operation": "append_sentence",
            "added_terms": ["dashboard"],
            "added_text": "Strengthen metadata for nonblank dashboard evidence.",
            "rank": 2,
            "status": "proposed",
        },
    ]

    shadow, applied = apply_ranked_patch_candidates([original], candidates)

    assert original.trigger_terms == ["browser"]
    assert original.description == "Open local pages."
    assert shadow[0] is not original
    assert shadow[0].trigger_terms == ["browser", "dashboard"]
    assert shadow[0].description.endswith(
        "Strengthen metadata for nonblank dashboard evidence."
    )
    assert [record["candidate_id"] for record in applied] == [
        "task-001::browser-smoke-testing::trigger_terms::append_terms",
        "task-001::browser-smoke-testing::description::append_sentence",
    ]


def test_apply_ranked_patch_candidates_copies_unpatched_skills_too():
    original = Skill(
        id="browser-smoke-testing",
        name="Browser Smoke Testing",
        path="skills/browser-smoke-testing/SKILL.md",
        category="test",
        description="Open local pages.",
        body="# Browser Smoke Testing",
        trigger_terms=["browser"],
        token_count_estimate=10,
    )
    untouched = Skill(
        id="visual-regression-review",
        name="Visual Regression Review",
        path="skills/visual-regression-review/SKILL.md",
        category="test",
        description="Review screenshots.",
        body="# Visual Regression Review",
        trigger_terms=["visual"],
        token_count_estimate=10,
    )
    candidates = [
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
    ]

    shadow, _ = apply_ranked_patch_candidates([original, untouched], candidates)

    assert shadow[0] is not original
    assert shadow[1] is not untouched
    assert shadow[1] == untouched
    assert shadow[1].trigger_terms is not untouched.trigger_terms


def test_compare_route_records_flags_recall_and_negative_regressions():
    baseline = [
        {
            "task_id": "task-001",
            "category": "test",
            "difficulty": "easy",
            "split": "test",
            "robustness_tags": ["simulation"],
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
    ]
    shadow = [
        {
            "task_id": "task-001",
            "category": "test",
            "difficulty": "easy",
            "split": "test",
            "robustness_tags": ["simulation"],
            "selected_skill_ids": ["bad"],
            "gold_skills": ["gold"],
            "negative_skills": ["bad"],
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "negative_hit_rate": 1.0,
            "negative_accepted_rate": 1.0,
            "selection_rate_at_5": 0.2,
        }
    ]

    diffs = compare_route_records(
        baseline,
        shadow,
        applied_by_task={"task-001": ["candidate-1"]},
    )

    assert diffs[0]["task_id"] == "task-001"
    assert diffs[0]["selection_changed"] is True
    assert "recall_at_5_decreased" in diffs[0]["regression_flags"]
    assert "negative_hit_rate_increased" in diffs[0]["regression_flags"]
    assert "new_negative_skill_selected" in diffs[0]["regression_flags"]
    assert diffs[0]["improvement_flags"] == []
    assert diffs[0]["applied_candidate_ids"] == ["candidate-1"]


def test_compare_route_records_rejects_mismatched_task_labels():
    baseline = [
        {
            "task_id": "task-001",
            "category": "test",
            "difficulty": "easy",
            "split": "test",
            "robustness_tags": ["simulation"],
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
    ]
    shadow = [
        {
            "task_id": "task-001",
            "category": "test",
            "difficulty": "easy",
            "split": "test",
            "robustness_tags": ["simulation"],
            "selected_skill_ids": ["gold"],
            "gold_skills": ["different-gold"],
            "negative_skills": ["bad"],
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "negative_hit_rate": 0.0,
            "negative_accepted_rate": 0.0,
            "selection_rate_at_5": 0.2,
        }
    ]

    with pytest.raises(ValueError, match="gold_skills"):
        compare_route_records(baseline, shadow)


def test_compare_route_records_rejects_duplicate_task_ids():
    record = {
        "task_id": "task-001",
        "category": "test",
        "difficulty": "easy",
        "split": "test",
        "robustness_tags": ["simulation"],
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

    with pytest.raises(ValueError, match="duplicate task ids"):
        compare_route_records([record, dict(record)], [record])


class FirstSkillRouter(SkillRouter):
    name = "first-skill"

    def route(self, task, skills, top_k):
        selected = [skills[0].id]
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=selected,
            scores={
                skill.id: float(len(skills) - index)
                for index, skill in enumerate(skills)
            },
            latency_ms=0.0,
        )


def test_simulate_skill_patches_writes_shadow_artifacts(tmp_path: Path):
    skills = [
        Skill(
            "gold",
            "Gold",
            "skills/gold/SKILL.md",
            "test",
            "Gold skill.",
            "# Gold",
            ["gold"],
            1,
        ),
        Skill(
            "bad",
            "Bad",
            "skills/bad/SKILL.md",
            "test",
            "Bad skill.",
            "# Bad",
            ["bad"],
            1,
        ),
    ]
    tasks = [
        BenchmarkTask(
            id="task-001",
            category="test",
            difficulty="easy",
            prompt="Use gold skill.",
            gold_skills=["gold"],
            negative_skills=["bad"],
            verifier="manual",
            split="test",
            robustness_tags=["simulation"],
        )
    ]
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "category": "test",
                "difficulty": "easy",
                "split": "test",
                "robustness_tags": ["simulation"],
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
        )
        + "\n",
        encoding="utf-8",
    )
    candidates = [
        {
            "candidate_id": "task-001::gold::description::append_sentence",
            "source_task_id": "task-001",
            "target_skill_id": "gold",
            "patch_field": "description",
            "operation": "append_sentence",
            "added_terms": ["gold"],
            "added_text": "Strengthen metadata for gold evidence.",
            "rank": 1,
            "status": "proposed",
        }
    ]

    summary = simulate_skill_patches(
        ranked_patches=candidates,
        baseline_records_path=baseline,
        tasks=tasks,
        skills=skills,
        router=FirstSkillRouter(),
        router_label="first-skill-shadow",
        top_k=1,
        output_dir=tmp_path / "phase13",
    )

    assert summary["phase"] == "Phase 13"
    assert summary["artifact_type"] == "phase13-patch-simulation"
    assert summary["applied_candidate_count"] == 1
    assert summary["source_mutation"] == "none; source SKILL.md files are not modified"
    assert (tmp_path / "phase13" / "shadow-skills.json").exists()
    assert (tmp_path / "phase13" / "shadow-results.jsonl").exists()
    assert (tmp_path / "phase13" / "route-diffs.jsonl").exists()
    assert (tmp_path / "phase13" / "regression-summary.json").exists()
    assert (tmp_path / "phase13" / "regression-report.md").exists()
