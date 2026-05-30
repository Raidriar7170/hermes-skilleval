from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path("benchmarks/blind-migration-tasks")
SKILLS_INDEX = Path("docs/demo/phase9-real-skill-library-migration/skills.json")
PHASE14_PAIRS = Path("docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl")
EXPECTED_GOLD_SKILLS = {
    "accessibility-tree-inspection",
    "browser-smoke-testing",
    "form-interaction-flow",
    "visual-regression-review",
    "mcp-tool-routing",
    "plan-mode",
    "slash-command-workflow",
    "task-tool-delegation",
    "apply-patch-discipline",
    "evidence-backed-final",
    "subagent-worker-protocol",
    "workspace-git-hygiene",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "verification-before-completion",
}


def _tasks() -> list[tuple[Path, dict]]:
    return [
        (path, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(ROOT.glob("*/task.yaml"))
    ]


def test_phase16_blind_pack_has_one_task_per_migrated_skill() -> None:
    tasks = _tasks()
    assert len(tasks) == 16
    gold = [task["gold_skills"][0] for _, task in tasks]
    assert set(gold) == EXPECTED_GOLD_SKILLS
    assert len(gold) == len(set(gold))


def test_phase16_blind_tasks_are_test_split_and_referenced_skills_exist() -> None:
    skill_ids = {
        skill["id"]
        for skill in json.loads(SKILLS_INDEX.read_text(encoding="utf-8"))
    }
    for path, task in _tasks():
        assert task["split"] == "test", path
        assert task["verifier"] == "skill_selection", path
        assert task["robustness_tags"] == [
            "blind-validation",
            "phase16",
            "real-skill-library-migration",
        ], path
        assert set(task["gold_skills"]).issubset(skill_ids), path
        assert set(task["negative_skills"]).issubset(skill_ids), path
        assert not set(task["gold_skills"]) & set(task["negative_skills"]), path


def test_phase16_prompts_do_not_reveal_skill_ids() -> None:
    for task_path, task in _tasks():
        prompt = (task_path.parent / "prompt.md").read_text(encoding="utf-8")
        assert prompt.strip(), task_path
        for skill_id in task["gold_skills"] + task["negative_skills"]:
            assert skill_id not in prompt, task_path


def test_phase16_blind_task_ids_not_used_in_phase14_training() -> None:
    train_like = {
        json.loads(line)["task_id"]
        for line in PHASE14_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    blind_ids = {task["id"] for _, task in _tasks()}
    assert not blind_ids & train_like


def test_phase16_prompts_are_not_phase14_training_queries() -> None:
    phase14_queries = {
        json.loads(line)["query_text"].strip()
        for line in PHASE14_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    prompts = {
        (task_path.parent / "prompt.md").read_text(encoding="utf-8").strip()
        for task_path, _ in _tasks()
    }
    assert not prompts & phase14_queries
