from pathlib import Path

import pytest

from hermes_skilleval.task_loader import load_task, load_tasks


FIXTURES = Path(__file__).parent / "fixtures" / "tasks"
VALID_TASK_YAML = (
    "id: valid-task\n"
    "category: coding\n"
    "difficulty: easy\n"
    "gold_skills:\n"
    "  - systematic-debugging\n"
    "negative_skills: []\n"
    "verifier: skill_selection\n"
)


def _write_task(tmp_path, task_yaml: str, prompt: str = "Do the task.") -> Path:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text(task_yaml, encoding="utf-8")
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    return task_dir


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


def test_load_task_allows_empty_negative_skills(tmp_path):
    task = load_task(_write_task(tmp_path, VALID_TASK_YAML))

    assert task.gold_skills == ["systematic-debugging"]
    assert task.negative_skills == []


def test_load_task_requires_prompt_file(tmp_path):
    task_dir = tmp_path / "broken"
    task_dir.mkdir()
    (task_dir / "task.yaml").write_text(
        "id: broken\ncategory: coding\ndifficulty: easy\ngold_skills: []\nnegative_skills: []\nverifier: skill_selection\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing prompt.md"):
        load_task(task_dir)


def test_load_task_rejects_missing_required_field(tmp_path):
    task_dir = _write_task(
        tmp_path,
        "id: missing-category\n"
        "difficulty: easy\n"
        "gold_skills:\n"
        "  - systematic-debugging\n"
        "negative_skills: []\n"
        "verifier: skill_selection\n",
    )

    with pytest.raises(ValueError, match=r"task\.yaml.*missing required fields: category"):
        load_task(task_dir)


@pytest.mark.parametrize(
    ("field", "task_yaml"),
    [
        (
            "id",
            "id: null\n"
            "category: coding\n"
            "difficulty: easy\n"
            "gold_skills:\n"
            "  - systematic-debugging\n"
            "negative_skills: []\n"
            "verifier: skill_selection\n",
        ),
        (
            "category",
            "id: invalid-category\n"
            "category: []\n"
            "difficulty: easy\n"
            "gold_skills:\n"
            "  - systematic-debugging\n"
            "negative_skills: []\n"
            "verifier: skill_selection\n",
        ),
        (
            "difficulty",
            "id: empty-difficulty\n"
            "category: coding\n"
            "difficulty: ''\n"
            "gold_skills:\n"
            "  - systematic-debugging\n"
            "negative_skills: []\n"
            "verifier: skill_selection\n",
        ),
        (
            "verifier",
            "id: invalid-verifier\n"
            "category: coding\n"
            "difficulty: easy\n"
            "gold_skills:\n"
            "  - systematic-debugging\n"
            "negative_skills: []\n"
            "verifier: 123\n",
        ),
    ],
)
def test_load_task_rejects_invalid_or_empty_required_scalars(tmp_path, field, task_yaml):
    task_dir = _write_task(
        tmp_path,
        task_yaml,
    )

    with pytest.raises(ValueError, match=rf"task\.yaml.*field {field}.*non-empty string"):
        load_task(task_dir)


@pytest.mark.parametrize(
    ("field", "task_yaml", "expected_fragment"),
    [
        (
            "gold_skills",
            VALID_TASK_YAML.replace("gold_skills:\n  - systematic-debugging\n", "gold_skills: []\n"),
            "non-empty list",
        ),
        (
            "gold_skills",
            VALID_TASK_YAML.replace("  - systematic-debugging\n", "  - ''\n"),
            "field gold_skills[0] must be a non-empty string",
        ),
        (
            "negative_skills",
            VALID_TASK_YAML.replace("negative_skills: []\n", "negative_skills:\n  - ''\n"),
            "field negative_skills[0] must be a non-empty string",
        ),
    ],
)
def test_load_task_rejects_invalid_skill_lists(tmp_path, field, task_yaml, expected_fragment):
    task_dir = _write_task(tmp_path, task_yaml)

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message_text = str(exc_info.value)
    assert str(task_dir / "task.yaml") in message_text
    assert f"field {field}" in message_text
    assert expected_fragment in message_text


def test_load_task_rejects_empty_prompt(tmp_path):
    task_dir = _write_task(tmp_path, VALID_TASK_YAML, prompt="  \n")

    with pytest.raises(ValueError, match=r"prompt\.md is empty"):
        load_task(task_dir)


def test_load_task_wraps_malformed_yaml_with_path(tmp_path):
    task_dir = _write_task(tmp_path, "id: [unterminated\n")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "malformed task.yaml" in message
    assert str(task_dir / "task.yaml") in message
