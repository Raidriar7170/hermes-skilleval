from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from hermes_skilleval.models import Skill


SKILL_FIELDS = {field.name for field in fields(Skill)}
STRING_FIELDS = {"id", "name", "path", "description", "body"}


def save_skill_index(skills: list[Skill], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(skill) for skill in skills]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_skill_index(index_path: Path | str) -> list[Skill]:
    path = Path(index_path)
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("skill index JSON must be a list")
    return [_load_skill(item, path, index) for index, item in enumerate(payload)]


def _load_skill(item: Any, path: Path, index: int) -> Skill:
    context = f"{path.name} item {index}"
    if not isinstance(item, dict):
        raise ValueError(f"{context} must be an object")

    field_names = set(item)
    missing = sorted(SKILL_FIELDS - field_names)
    if missing:
        raise ValueError(f"{context} missing fields: {', '.join(missing)}")

    unknown = sorted(field_names - SKILL_FIELDS)
    if unknown:
        raise ValueError(f"{context} unknown fields: {', '.join(unknown)}")

    for field_name in sorted(STRING_FIELDS):
        if not isinstance(item[field_name], str):
            raise ValueError(f"{context} {field_name} must be a string")

    if item["category"] is not None and not isinstance(item["category"], str):
        raise ValueError(f"{context} category must be a string or null")

    trigger_terms = item["trigger_terms"]
    if not isinstance(trigger_terms, list) or not all(
        isinstance(term, str) for term in trigger_terms
    ):
        raise ValueError(f"{context} trigger_terms must be a list of strings")

    token_count = item["token_count_estimate"]
    if not isinstance(token_count, int) or isinstance(token_count, bool):
        raise ValueError(f"{context} token_count_estimate must be an int")

    return Skill(**item)
