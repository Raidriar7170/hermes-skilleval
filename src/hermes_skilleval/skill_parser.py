from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.models import Skill


FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)
WORD_RE = re.compile(r"[A-Za-z0-9]+")


def scan_skills(skills_path: Path | str) -> list[Skill]:
    root = Path(skills_path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"skills_path does not exist or is not a directory: {root}")

    skill_files = sorted(root.rglob("SKILL.md"))
    if not skill_files:
        raise ValueError(f"no SKILL.md files found under {root}; expected skills/**/SKILL.md")

    return [parse_skill_file(path, root) for path in skill_files]


def parse_skill_file(path: Path | str, skills_root: Path | str) -> Skill:
    skill_path = Path(path)
    root = Path(skills_root)
    text = skill_path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(text, skill_path)

    skill_id = _skill_id(skill_path)
    name = str(metadata.get("name") or _fallback_name(body, skill_id))
    description = str(metadata.get("description") or _fallback_description(body))
    category = _category_for(skill_path, root)
    trigger_terms = _trigger_terms(skill_id, name, description)

    return Skill(
        id=skill_id,
        name=name,
        path=str(skill_path),
        category=category,
        description=description,
        body=body.strip(),
        trigger_terms=trigger_terms,
        token_count_estimate=len(WORD_RE.findall(text)),
    )


def _split_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    try:
        loaded = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed skill frontmatter: {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        return {}, body
    return loaded, body


def _skill_id(path: Path) -> str:
    return path.parent.name


def _category_for(path: Path, root: Path) -> str | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) >= 3 else None


def _fallback_name(body: str, skill_id: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return skill_id.replace("-", " ").title()


def _fallback_description(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _trigger_terms(skill_id: str, name: str, description: str) -> list[str]:
    raw = f"{skill_id} {name} {description}".lower()
    terms = []
    seen = set()
    for term in WORD_RE.findall(raw):
        if len(term) < 3 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms
