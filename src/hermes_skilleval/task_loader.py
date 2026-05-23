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
REQUIRED_SCALAR_FIELDS = ("id", "category", "difficulty", "verifier")


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

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed task.yaml: {yaml_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"task.yaml must contain a mapping: {yaml_path}")

    missing = sorted(REQUIRED_FIELDS - set(raw))
    if missing:
        raise ValueError(f"{yaml_path} missing required fields: {', '.join(missing)}")

    scalars = {
        field: _required_string(raw[field], yaml_path, field)
        for field in REQUIRED_SCALAR_FIELDS
    }
    gold_skills = _string_list(raw["gold_skills"], yaml_path, "gold_skills", min_items=1)
    negative_skills = _string_list(raw["negative_skills"], yaml_path, "negative_skills")
    split = _optional_split(raw.get("split", "dev"), yaml_path)
    robustness_tags = _string_list(
        raw.get("robustness_tags", ["legacy"]),
        yaml_path,
        "robustness_tags",
        min_items=1,
    )
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"prompt.md is empty: {prompt_path}")

    return BenchmarkTask(
        id=scalars["id"],
        category=scalars["category"],
        difficulty=scalars["difficulty"],
        prompt=prompt,
        gold_skills=gold_skills,
        negative_skills=negative_skills,
        verifier=scalars["verifier"],
        split=split,
        robustness_tags=robustness_tags,
    )


def _required_string(value: Any, path: Path, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} field {field} must be a non-empty string")
    return value


def _string_list(value: Any, path: Path, field: str, *, min_items: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path} field {field} must be a list of non-empty strings")
    if len(value) < min_items:
        raise ValueError(f"{path} field {field} must be a non-empty list of non-empty strings")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path} field {field}[{index}] must be a non-empty string")
    return value


def _optional_split(value: Any, path: Path) -> str:
    if value not in {"dev", "test"}:
        raise ValueError(f"{path} field split must be 'dev' or 'test'")
    return value
