from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.models import BenchmarkTask


REQUIRED_FIELDS = {
    "id",
    "category",
    "difficulty",
    "gold_skills",
    "negative_skills",
    "verifier",
}


def load_tasks(tasks_path: Path | str) -> list[BenchmarkTask]:
    root = Path(tasks_path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"tasks_path does not exist or is not a directory: {root}")

    task_dirs = sorted(path.parent for path in root.rglob("task.yaml"))
    if not task_dirs:
        raise ValueError(f"no benchmark tasks found under {root}; expected task.yaml files")

    return [load_task(path) for path in task_dirs]


def load_task(task_dir: Path | str) -> BenchmarkTask:
    directory = Path(task_dir)
    yaml_path = directory / "task.yaml"
    prompt_path = directory / "prompt.md"

    if not yaml_path.exists():
        raise ValueError(f"missing task.yaml in {directory}")
    if not prompt_path.exists():
        raise ValueError(f"missing prompt.md in {directory}")

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"task.yaml must contain a mapping: {yaml_path}")

    missing = sorted(REQUIRED_FIELDS - set(raw))
    if missing:
        raise ValueError(f"{yaml_path} missing required fields: {', '.join(missing)}")

    gold_skills = _string_list(raw["gold_skills"], yaml_path, "gold_skills")
    negative_skills = _string_list(raw["negative_skills"], yaml_path, "negative_skills")
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"prompt.md is empty: {prompt_path}")

    return BenchmarkTask(
        id=str(raw["id"]),
        category=str(raw["category"]),
        difficulty=str(raw["difficulty"]),
        prompt=prompt,
        gold_skills=gold_skills,
        negative_skills=negative_skills,
        verifier=str(raw["verifier"]),
    )


def _string_list(value: Any, path: Path, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path} field {field} must be a list of strings")
    return value
