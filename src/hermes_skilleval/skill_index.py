from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from hermes_skilleval.models import Skill


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
    return [Skill(**item) for item in payload]
