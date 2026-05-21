from pathlib import Path

import pytest

from hermes_skilleval.task_loader import load_task, load_tasks


FIXTURES = Path(__file__).parent / "fixtures" / "tasks"


def test_load_task_reads_yaml_and_prompt():
    task = load_task(FIXTURES / "python-debugging-001")

    assert task.id == "python-debugging-001"
    assert task.category == "coding"
    assert task.gold_skills == ["systematic-debugging", "test-driven-development"]
    assert task.negative_skills == ["songwriting-and-ai-music"]
    assert "test suite is failing" in task.prompt


def test_load_tasks_recursively():
    tasks = load_tasks(FIXTURES)

    assert [task.id for task in tasks] == ["python-debugging-001"]


def test_load_task_requires_prompt_file(tmp_path):
    task_dir = tmp_path / "broken"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text(
        "id: broken\ncategory: coding\ndifficulty: easy\ngold_skills: []\nnegative_skills: []\nverifier: skill_selection\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing prompt.md"):
        load_task(task_dir)
