# Hermes SkillEval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline Python CLI harness that indexes Hermes-style skills, evaluates skill routers against labeled benchmark tasks, and generates metrics reports with no network and no LLM required.

**Architecture:** The project is a standalone Python package with focused modules for parsing skills, loading tasks, routing, metrics, storage, reporting, and CLI orchestration. It does not modify or import Hermes Agent; Hermes-compatible skill directories are external inputs.

**Tech Stack:** Python 3.11+, dataclasses, PyYAML, argparse, pytest, Markdown/JSONL files, optional future embedding dependencies.

---

## File Structure

Create these files and directories:

```text
pyproject.toml
README.md
src/hermes_skilleval/__init__.py
src/hermes_skilleval/cli.py
src/hermes_skilleval/models.py
src/hermes_skilleval/skill_parser.py
src/hermes_skilleval/skill_index.py
src/hermes_skilleval/task_loader.py
src/hermes_skilleval/storage.py
src/hermes_skilleval/metrics.py
src/hermes_skilleval/report.py
src/hermes_skilleval/routers/__init__.py
src/hermes_skilleval/routers/base.py
src/hermes_skilleval/routers/keyword.py
src/hermes_skilleval/routers/embedding.py
src/hermes_skilleval/routers/hybrid.py
tests/conftest.py
tests/test_skill_parser.py
tests/test_task_loader.py
tests/test_keyword_router.py
tests/test_metrics.py
tests/test_report.py
tests/test_cli_smoke.py
tests/fixtures/skills/coding/systematic-debugging/SKILL.md
tests/fixtures/skills/coding/test-driven-development/SKILL.md
tests/fixtures/skills/creative/songwriting-and-ai-music/SKILL.md
tests/fixtures/tasks/python-debugging-001/task.yaml
tests/fixtures/tasks/python-debugging-001/prompt.md
benchmarks/tasks/<30 task directories>
```

## Task 1: Project Scaffold and Core Models

**Files:**
- Create: `pyproject.toml`
- Create: `src/hermes_skilleval/__init__.py`
- Create: `src/hermes_skilleval/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write model tests**

Create `tests/test_models.py`:

```python
from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill


def test_skill_dataclass_fields():
    skill = Skill(
        id="systematic-debugging",
        name="Systematic Debugging",
        path="/tmp/skills/systematic-debugging/SKILL.md",
        category="coding",
        description="Debug failures systematically.",
        body="Use a hypothesis-driven debugging loop.",
        trigger_terms=["debugging", "failure"],
        token_count_estimate=8,
    )

    assert skill.id == "systematic-debugging"
    assert skill.category == "coding"
    assert skill.token_count_estimate == 8


def test_benchmark_task_dataclass_fields():
    task = BenchmarkTask(
        id="python-debugging-001",
        category="coding",
        difficulty="easy",
        prompt="A Python test suite is failing.",
        gold_skills=["systematic-debugging"],
        negative_skills=["songwriting-and-ai-music"],
        verifier="skill_selection",
    )

    assert task.gold_skills == ["systematic-debugging"]
    assert task.negative_skills == ["songwriting-and-ai-music"]


def test_route_result_dataclass_fields():
    result = RouteResult(
        task_id="python-debugging-001",
        router="keyword",
        selected_skill_ids=["systematic-debugging"],
        scores={"systematic-debugging": 1.0},
        latency_ms=2.5,
    )

    assert result.router == "keyword"
    assert result.scores["systematic-debugging"] == 1.0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hermes_skilleval'`.

- [ ] **Step 3: Create package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes-skilleval"
version = "0.1.0"
description = "Offline skill routing evaluation harness for Hermes-style agent skills"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
]

[project.scripts]
skilleval = "hermes_skilleval.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 4: Create models**

Create `src/hermes_skilleval/__init__.py`:

```python
"""Hermes SkillEval: offline skill routing evaluation harness."""

__version__ = "0.1.0"
```

Create `src/hermes_skilleval/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    path: str
    category: str | None
    description: str
    body: str
    trigger_terms: list[str]
    token_count_estimate: int


@dataclass(frozen=True)
class BenchmarkTask:
    id: str
    category: str
    difficulty: str
    prompt: str
    gold_skills: list[str]
    negative_skills: list[str]
    verifier: str


@dataclass(frozen=True)
class RouteResult:
    task_id: str
    router: str
    selected_skill_ids: list[str]
    scores: dict[str, float]
    latency_ms: float


@dataclass(frozen=True)
class EvalRun:
    task: BenchmarkTask
    result: RouteResult
    warnings: list[str]


@dataclass(frozen=True)
class MetricSummary:
    router: str
    task_count: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_5: float
    mrr: float
    ndcg_at_5: float
    negative_hit_rate: float
    average_latency_ms: float
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
pytest tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add pyproject.toml src/hermes_skilleval/__init__.py src/hermes_skilleval/models.py tests/test_models.py
git commit -m "feat: scaffold SkillEval package models"
```

## Task 2: Skill Parser

**Files:**
- Create: `src/hermes_skilleval/skill_parser.py`
- Create: `tests/test_skill_parser.py`
- Create: `tests/fixtures/skills/coding/systematic-debugging/SKILL.md`
- Create: `tests/fixtures/skills/coding/test-driven-development/SKILL.md`
- Create: `tests/fixtures/skills/creative/songwriting-and-ai-music/SKILL.md`

- [ ] **Step 1: Create skill fixtures**

Create `tests/fixtures/skills/coding/systematic-debugging/SKILL.md`:

```markdown
---
name: systematic-debugging
description: Use when diagnosing failing tests, runtime errors, or unexpected behavior.
---

# Systematic Debugging

Follow a hypothesis-driven loop. Reproduce the failure, isolate the cause, make one change, and verify the fix.
```

Create `tests/fixtures/skills/coding/test-driven-development/SKILL.md`:

```markdown
---
name: test-driven-development
description: Use when implementing behavior that can be covered by automated tests.
---

# Test-Driven Development

Write a failing test first, implement the smallest change, and run the relevant tests again.
```

Create `tests/fixtures/skills/creative/songwriting-and-ai-music/SKILL.md`:

```markdown
# Songwriting and AI Music

Use when writing lyrics, melodies, hooks, or prompts for music generation.
```

- [ ] **Step 2: Write parser tests**

Create `tests/test_skill_parser.py`:

```python
from pathlib import Path

from hermes_skilleval.skill_parser import parse_skill_file, scan_skills


FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_parse_skill_with_frontmatter():
    skill = parse_skill_file(FIXTURES / "coding" / "systematic-debugging" / "SKILL.md", FIXTURES)

    assert skill.id == "systematic-debugging"
    assert skill.name == "systematic-debugging"
    assert skill.category == "coding"
    assert "diagnosing failing tests" in skill.description
    assert "hypothesis-driven" in skill.body
    assert "debugging" in skill.trigger_terms
    assert skill.token_count_estimate > 0


def test_parse_skill_without_frontmatter_uses_fallbacks():
    skill = parse_skill_file(
        FIXTURES / "creative" / "songwriting-and-ai-music" / "SKILL.md",
        FIXTURES,
    )

    assert skill.id == "songwriting-and-ai-music"
    assert skill.name == "Songwriting and AI Music"
    assert skill.category == "creative"
    assert skill.description == "Use when writing lyrics, melodies, hooks, or prompts for music generation."


def test_scan_skills_recursively():
    skills = scan_skills(FIXTURES)
    ids = {skill.id for skill in skills}

    assert ids == {
        "systematic-debugging",
        "test-driven-development",
        "songwriting-and-ai-music",
    }
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
pytest tests/test_skill_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing parser functions.

- [ ] **Step 4: Implement parser**

Create `src/hermes_skilleval/skill_parser.py`:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.models import Skill


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


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
    metadata, body = _split_frontmatter(text)

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


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    loaded = yaml.safe_load(raw_meta) or {}
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
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
pytest tests/test_skill_parser.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/hermes_skilleval/skill_parser.py tests/test_skill_parser.py tests/fixtures/skills
git commit -m "feat: parse Hermes skill files"
```

## Task 3: Task Loader

**Files:**
- Create: `src/hermes_skilleval/task_loader.py`
- Create: `tests/test_task_loader.py`
- Create: `tests/fixtures/tasks/python-debugging-001/task.yaml`
- Create: `tests/fixtures/tasks/python-debugging-001/prompt.md`

- [ ] **Step 1: Create task fixture**

Create `tests/fixtures/tasks/python-debugging-001/task.yaml`:

```yaml
id: python-debugging-001
category: coding
difficulty: easy
gold_skills:
  - systematic-debugging
  - test-driven-development
negative_skills:
  - songwriting-and-ai-music
verifier: skill_selection
```

Create `tests/fixtures/tasks/python-debugging-001/prompt.md`:

```markdown
A Python test suite is failing after a refactor. Investigate the failure, identify the root cause, write a regression test, and implement the minimal fix.
```

- [ ] **Step 2: Write loader tests**

Create `tests/test_task_loader.py`:

```python
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
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
pytest tests/test_task_loader.py -v
```

Expected: FAIL with missing `task_loader`.

- [ ] **Step 4: Implement task loader**

Create `src/hermes_skilleval/task_loader.py`:

```python
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
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
pytest tests/test_task_loader.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/hermes_skilleval/task_loader.py tests/test_task_loader.py tests/fixtures/tasks
git commit -m "feat: load benchmark tasks"
```

## Task 4: Keyword Router

**Files:**
- Create: `src/hermes_skilleval/routers/__init__.py`
- Create: `src/hermes_skilleval/routers/base.py`
- Create: `src/hermes_skilleval/routers/keyword.py`
- Create: `tests/test_keyword_router.py`

- [ ] **Step 1: Write router tests**

Create `tests/test_keyword_router.py`:

```python
import pytest

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.routers.keyword import KeywordRouter


def test_keyword_router_ranks_relevant_skill_first():
    skills = [
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="/skills/systematic-debugging/SKILL.md",
            category="coding",
            description="Diagnose failing tests and runtime errors.",
            body="Reproduce failures and isolate root causes.",
            trigger_terms=["debugging", "failing", "tests"],
            token_count_estimate=12,
        ),
        Skill(
            id="songwriting-and-ai-music",
            name="Songwriting",
            path="/skills/songwriting/SKILL.md",
            category="creative",
            description="Write lyrics and music prompts.",
            body="Create hooks and melodies.",
            trigger_terms=["lyrics", "music"],
            token_count_estimate=9,
        ),
    ]
    task = BenchmarkTask(
        id="python-debugging-001",
        category="coding",
        difficulty="easy",
        prompt="A Python test suite is failing and needs debugging.",
        gold_skills=["systematic-debugging"],
        negative_skills=["songwriting-and-ai-music"],
        verifier="skill_selection",
    )

    result = KeywordRouter().route(task, skills, top_k=2)

    assert result.selected_skill_ids[0] == "systematic-debugging"
    assert result.scores["systematic-debugging"] > result.scores["songwriting-and-ai-music"]
    assert result.latency_ms >= 0


def test_keyword_router_rejects_empty_skill_index():
    task = BenchmarkTask(
        id="empty",
        category="coding",
        difficulty="easy",
        prompt="Debug a failure.",
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )

    with pytest.raises(ValueError, match="skill index is empty"):
        KeywordRouter().route(task, [], top_k=5)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_keyword_router.py -v
```

Expected: FAIL with missing router modules.

- [ ] **Step 3: Implement router interface and keyword router**

Create `src/hermes_skilleval/routers/__init__.py`:

```python
"""Skill router implementations."""
```

Create `src/hermes_skilleval/routers/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill


class SkillRouter(ABC):
    name: str

    @abstractmethod
    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        raise NotImplementedError
```

Create `src/hermes_skilleval/routers/keyword.py`:

```python
from __future__ import annotations

import math
import re
import time
from collections import Counter

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class KeywordRouter(SkillRouter):
    name = "keyword"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        if not skills:
            raise ValueError("skill index is empty")
        started = time.perf_counter()
        query_terms = _terms(f"{task.category} {task.prompt}")
        scores = {skill.id: _score(query_terms, skill) for skill in skills}
        ranked = sorted(skills, key=lambda skill: (-scores[skill.id], skill.id))
        selected = [skill.id for skill in ranked[:top_k]]
        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=selected,
            scores=scores,
            latency_ms=latency_ms,
        )


def _terms(text: str) -> Counter[str]:
    return Counter(term.lower() for term in WORD_RE.findall(text) if len(term) >= 3)


def _score(query_terms: Counter[str], skill: Skill) -> float:
    skill_terms = _terms(
        " ".join(
            [
                skill.id.replace("-", " "),
                skill.name,
                skill.category or "",
                skill.description,
                " ".join(skill.trigger_terms),
                skill.body,
            ]
        )
    )
    if not query_terms or not skill_terms:
        return 0.0
    overlap = set(query_terms) & set(skill_terms)
    weighted_overlap = sum(query_terms[term] * (1.0 + math.log1p(skill_terms[term])) for term in overlap)
    category_boost = 0.5 if skill.category and skill.category.lower() in query_terms else 0.0
    return weighted_overlap + category_boost
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_keyword_router.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hermes_skilleval/routers tests/test_keyword_router.py
git commit -m "feat: add keyword skill router"
```

## Task 5: Metrics

**Files:**
- Create: `src/hermes_skilleval/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write metrics tests**

Create `tests/test_metrics.py`:

```python
from hermes_skilleval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
)


def test_recall_at_k_detects_gold_hit():
    assert recall_at_k(["a", "b", "c"], ["b"], 1) == 0.0
    assert recall_at_k(["a", "b", "c"], ["b"], 2) == 1.0


def test_precision_at_k_counts_gold_fraction():
    assert precision_at_k(["a", "b", "c"], ["a", "c"], 3) == 2 / 3


def test_mrr_uses_first_gold_rank():
    assert mean_reciprocal_rank(["x", "gold", "other"], ["gold"]) == 0.5
    assert mean_reciprocal_rank(["x", "y"], ["gold"]) == 0.0


def test_ndcg_at_k_rewards_better_ordering():
    good = ndcg_at_k(["a", "b", "c"], ["a", "c"], 3)
    bad = ndcg_at_k(["b", "c", "a"], ["a", "c"], 3)

    assert good > bad


def test_negative_hit_rate_detects_bad_skills():
    assert negative_hit_rate(["a", "bad"], ["bad"], 2) == 1.0
    assert negative_hit_rate(["a", "b"], ["bad"], 2) == 0.0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_metrics.py -v
```

Expected: FAIL with missing `metrics`.

- [ ] **Step 3: Implement metrics**

Create `src/hermes_skilleval/metrics.py`:

```python
from __future__ import annotations

import math


def recall_at_k(selected: list[str], gold: list[str], k: int) -> float:
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    selected_set = set(selected[:k])
    return len(selected_set & gold_set) / len(gold_set)


def precision_at_k(selected: list[str], gold: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    gold_set = set(gold)
    selected_slice = selected[:k]
    if not selected_slice:
        return 0.0
    return len(set(selected_slice) & gold_set) / k


def mean_reciprocal_rank(selected: list[str], gold: list[str]) -> float:
    gold_set = set(gold)
    for index, skill_id in enumerate(selected, start=1):
        if skill_id in gold_set:
            return 1.0 / index
    return 0.0


def ndcg_at_k(selected: list[str], gold: list[str], k: int) -> float:
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    dcg = 0.0
    for index, skill_id in enumerate(selected[:k], start=1):
        if skill_id in gold_set:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(gold_set), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def negative_hit_rate(selected: list[str], negative: list[str], k: int) -> float:
    negative_set = set(negative)
    if not negative_set:
        return 0.0
    return 1.0 if set(selected[:k]) & negative_set else 0.0
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_metrics.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hermes_skilleval/metrics.py tests/test_metrics.py
git commit -m "feat: add routing metrics"
```

## Task 6: Index, Hybrid Router, Evaluation Storage

**Files:**
- Create: `src/hermes_skilleval/skill_index.py`
- Create: `src/hermes_skilleval/routers/embedding.py`
- Create: `src/hermes_skilleval/routers/hybrid.py`
- Create: `src/hermes_skilleval/storage.py`
- Create: `tests/test_skill_index.py`
- Create: `tests/test_hybrid_router.py`

- [ ] **Step 1: Write index and hybrid tests**

Create `tests/test_skill_index.py`:

```python
from pathlib import Path

from hermes_skilleval.skill_index import load_skill_index, save_skill_index
from hermes_skilleval.skill_parser import scan_skills


FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_save_and_load_skill_index(tmp_path):
    skills = scan_skills(FIXTURES)
    output = tmp_path / "skills.json"

    save_skill_index(skills, output)
    loaded = load_skill_index(output)

    assert [skill.id for skill in loaded] == [skill.id for skill in skills]
```

Create `tests/test_hybrid_router.py`:

```python
from pathlib import Path

from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.task_loader import load_task


SKILLS = Path(__file__).parent / "fixtures" / "skills"
TASKS = Path(__file__).parent / "fixtures" / "tasks"


def test_hybrid_router_works_without_embedding_dependency():
    skills = scan_skills(SKILLS)
    task = load_task(TASKS / "python-debugging-001")

    result = HybridRouter().route(task, skills, top_k=3)

    assert result.router == "hybrid"
    assert "systematic-debugging" in result.selected_skill_ids[:2]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_skill_index.py tests/test_hybrid_router.py -v
```

Expected: FAIL with missing modules.

- [ ] **Step 3: Implement index, embedding stub, hybrid router, storage helpers**

Create `src/hermes_skilleval/skill_index.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hermes_skilleval.models import Skill


def save_skill_index(skills: list[Skill], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(skill) for skill in skills]
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def load_skill_index(index_path: Path | str) -> list[Skill]:
    path = Path(index_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"skill index must contain a list: {path}")
    return [Skill(**item) for item in data]
```

Create `src/hermes_skilleval/routers/embedding.py`:

```python
from __future__ import annotations

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter


class EmbeddingRouter(SkillRouter):
    name = "embedding"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        raise RuntimeError(
            "embedding router requires optional embedding dependencies; use keyword or hybrid for the offline MVP"
        )
```

Create `src/hermes_skilleval/routers/hybrid.py`:

```python
from __future__ import annotations

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.keyword import KeywordRouter


class HybridRouter(KeywordRouter):
    name = "hybrid"

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        result = super().route(task, skills, top_k)
        adjusted = dict(result.scores)
        for skill in skills:
            if skill.category == task.category:
                adjusted[skill.id] = adjusted.get(skill.id, 0.0) + 1.0
            if skill.id in task.prompt:
                adjusted[skill.id] = adjusted.get(skill.id, 0.0) + 2.0
        ranked = sorted(skills, key=lambda skill: (-adjusted[skill.id], skill.id))
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=[skill.id for skill in ranked[:top_k]],
            scores=adjusted,
            latency_ms=result.latency_ms,
        )
```

Create `src/hermes_skilleval/storage.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def timestamped_run_dir(root: Path | str = "runs") -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(root) / stamp
    path.mkdir(parents=True, exist_ok=False)
    return path


def ensure_dir(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_skill_index.py tests/test_hybrid_router.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hermes_skilleval/skill_index.py src/hermes_skilleval/routers/embedding.py src/hermes_skilleval/routers/hybrid.py src/hermes_skilleval/storage.py tests/test_skill_index.py tests/test_hybrid_router.py
git commit -m "feat: add skill index and hybrid router"
```

## Task 7: Report Generation

**Files:**
- Create: `src/hermes_skilleval/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write report test**

Create `tests/test_report.py`:

```python
import json

from hermes_skilleval.report import write_markdown_report


def test_write_markdown_report_includes_metrics_and_failures(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "python-debugging-001",
                        "router": "keyword",
                        "selected_skill_ids": ["systematic-debugging"],
                        "gold_skills": ["systematic-debugging"],
                        "negative_skills": ["songwriting-and-ai-music"],
                        "latency_ms": 1.0,
                    }
                ),
                json.dumps(
                    {
                        "task_id": "research-001",
                        "router": "keyword",
                        "selected_skill_ids": ["songwriting-and-ai-music"],
                        "gold_skills": ["research"],
                        "negative_skills": ["songwriting-and-ai-music"],
                        "latency_ms": 3.0,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.md"

    write_markdown_report(results, output)
    text = output.read_text(encoding="utf-8")

    assert "# Hermes SkillEval Report" in text
    assert "Recall@1" in text
    assert "python-debugging-001" in text
    assert "research-001" in text
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_report.py -v
```

Expected: FAIL with missing `report`.

- [ ] **Step 3: Implement Markdown report**

Create `src/hermes_skilleval/report.py`:

```python
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from hermes_skilleval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
)


def write_markdown_report(results_path: Path | str, output_path: Path | str) -> None:
    records = _load_jsonl(Path(results_path))
    if not records:
        raise ValueError(f"no result records found: {results_path}")

    router = str(records[0]["router"])
    recalls_1 = [_metric(record, recall_at_k, 1) for record in records]
    recalls_3 = [_metric(record, recall_at_k, 3) for record in records]
    recalls_5 = [_metric(record, recall_at_k, 5) for record in records]
    precisions_5 = [_metric(record, precision_at_k, 5) for record in records]
    mrrs = [mean_reciprocal_rank(record["selected_skill_ids"], record["gold_skills"]) for record in records]
    ndcgs_5 = [ndcg_at_k(record["selected_skill_ids"], record["gold_skills"], 5) for record in records]
    negative_hits = [
        negative_hit_rate(record["selected_skill_ids"], record["negative_skills"], 5) for record in records
    ]
    latencies = [float(record["latency_ms"]) for record in records]
    selected_counts = Counter(skill for record in records for skill in record["selected_skill_ids"][:5])
    failures = [
        record
        for record in records
        if recall_at_k(record["selected_skill_ids"], record["gold_skills"], 5) == 0.0
        or negative_hit_rate(record["selected_skill_ids"], record["negative_skills"], 5) > 0.0
    ]

    lines = [
        "# Hermes SkillEval Report",
        "",
        f"Router: `{router}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Recall@1 | {_fmt(mean(recalls_1))} |",
        f"| Recall@3 | {_fmt(mean(recalls_3))} |",
        f"| Recall@5 | {_fmt(mean(recalls_5))} |",
        f"| Precision@5 | {_fmt(mean(precisions_5))} |",
        f"| MRR | {_fmt(mean(mrrs))} |",
        f"| NDCG@5 | {_fmt(mean(ndcgs_5))} |",
        f"| Negative Hit Rate | {_fmt(mean(negative_hits))} |",
        f"| Average Latency ms | {_fmt(mean(latencies))} |",
        "",
        "## Top Selected Skills",
        "",
    ]
    for skill, count in selected_counts.most_common(10):
        lines.append(f"- `{skill}`: {count}")

    lines.extend(["", "## Failure Cases", ""])
    if failures:
        for record in failures[:10]:
            lines.append(
                f"- `{record['task_id']}` selected `{', '.join(record['selected_skill_ids'][:5])}` "
                f"for gold `{', '.join(record['gold_skills'])}`"
            )
    else:
        lines.append("- No failure cases in this run.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _metric(record: dict[str, Any], fn, k: int) -> float:
    return fn(record["selected_skill_ids"], record["gold_skills"], k)


def _fmt(value: float) -> str:
    return f"{value:.4f}"
```

- [ ] **Step 4: Run test and verify pass**

Run:

```bash
pytest tests/test_report.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hermes_skilleval/report.py tests/test_report.py
git commit -m "feat: generate markdown evaluation reports"
```

## Task 8: CLI Commands and End-to-End Smoke Test

**Files:**
- Create: `src/hermes_skilleval/cli.py`
- Create: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write CLI smoke test**

Create `tests/test_cli_smoke.py`:

```python
from pathlib import Path

from hermes_skilleval.cli import main


FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_index_eval_report_smoke(tmp_path):
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "run"

    assert main(["index", "--skills-path", str(FIXTURES / "skills"), "--output", str(index_path)]) == 0
    assert index_path.exists()

    assert (
        main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--router",
                "hybrid",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )
    assert (run_dir / "results.jsonl").exists()

    assert main(["report", "--runs", str(run_dir)]) == 0
    assert (run_dir / "report.md").exists()
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_cli_smoke.py -v
```

Expected: FAIL with missing CLI implementation.

- [ ] **Step 3: Implement CLI**

Create `src/hermes_skilleval/cli.py`:

```python
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from hermes_skilleval.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
)
from hermes_skilleval.report import write_markdown_report
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.routers.keyword import KeywordRouter
from hermes_skilleval.skill_index import load_skill_index, save_skill_index
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.task_loader import load_tasks


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "index":
        return _index(args)
    if args.command == "eval":
        return _eval(args)
    if args.command == "report":
        return _report(args)
    parser.print_help()
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skilleval")
    sub = parser.add_subparsers(dest="command")

    index = sub.add_parser("index")
    index.add_argument("--skills-path", required=True)
    index.add_argument("--output", default="index/skills.json")

    eval_cmd = sub.add_parser("eval")
    eval_cmd.add_argument("--index", required=True)
    eval_cmd.add_argument("--tasks", required=True)
    eval_cmd.add_argument("--router", choices=["keyword", "hybrid"], default="keyword")
    eval_cmd.add_argument("--top-k", type=int, default=5)
    eval_cmd.add_argument("--output-dir", default="runs/latest")

    report = sub.add_parser("report")
    report.add_argument("--runs", required=True)

    return parser


def _index(args: argparse.Namespace) -> int:
    skills = scan_skills(Path(args.skills_path))
    save_skill_index(skills, Path(args.output))
    print(f"Indexed {len(skills)} skills to {args.output}")
    return 0


def _eval(args: argparse.Namespace) -> int:
    skills = load_skill_index(Path(args.index))
    tasks = load_tasks(Path(args.tasks))
    router = KeywordRouter() if args.router == "keyword" else HybridRouter()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"

    with results_path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            result = router.route(task, skills, top_k=args.top_k)
            record = {
                "task_id": task.id,
                "category": task.category,
                "difficulty": task.difficulty,
                "router": result.router,
                "selected_skill_ids": result.selected_skill_ids,
                "scores": result.scores,
                "gold_skills": task.gold_skills,
                "negative_skills": task.negative_skills,
                "latency_ms": result.latency_ms,
                "recall_at_1": recall_at_k(result.selected_skill_ids, task.gold_skills, 1),
                "recall_at_3": recall_at_k(result.selected_skill_ids, task.gold_skills, 3),
                "recall_at_5": recall_at_k(result.selected_skill_ids, task.gold_skills, 5),
                "precision_at_5": precision_at_k(result.selected_skill_ids, task.gold_skills, 5),
                "mrr": mean_reciprocal_rank(result.selected_skill_ids, task.gold_skills),
                "ndcg_at_5": ndcg_at_k(result.selected_skill_ids, task.gold_skills, 5),
                "negative_hit_rate": negative_hit_rate(result.selected_skill_ids, task.negative_skills, 5),
            }
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    print(f"Wrote evaluation records to {results_path}")
    return 0


def _report(args: argparse.Namespace) -> int:
    run_dir = Path(args.runs)
    results_path = run_dir / "results.jsonl"
    output_path = run_dir / "report.md"
    write_markdown_report(results_path, output_path)
    print(f"Wrote report to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run smoke test and full test suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hermes_skilleval/cli.py tests/test_cli_smoke.py
git commit -m "feat: add SkillEval CLI"
```

## Task 9: Benchmark Tasks and README

**Files:**
- Create: `benchmarks/tasks/*/task.yaml`
- Create: `benchmarks/tasks/*/prompt.md`
- Create: `scripts/generate_benchmark_tasks.py`
- Create: `README.md`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Create 30 benchmark task directories**

Create `scripts/generate_benchmark_tasks.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


TASKS = [
    ("coding-debugging-001", "coding", "easy", ["systematic-debugging", "test-driven-development"], ["songwriting-and-ai-music"], "A Python test suite is failing after a refactor. Reproduce the failure, identify the root cause, write a regression test, and implement the minimal fix."),
    ("coding-debugging-002", "coding", "medium", ["systematic-debugging"], ["ascii-art"], "A CLI command sometimes exits successfully without writing its expected output file. Diagnose the bug and propose a minimal fix with tests."),
    ("coding-debugging-003", "coding", "medium", ["test-driven-development"], ["songwriting-and-ai-music"], "Add a new parser option to an existing Python package using test-driven development and keep the public API stable."),
    ("coding-debugging-004", "coding", "hard", ["systematic-debugging"], ["creative-ideation"], "A race condition appears in a concurrent worker queue only under load. Design a debugging plan that isolates the timing issue."),
    ("coding-debugging-005", "coding", "easy", ["test-driven-development"], ["baoyu-comic"], "Implement a small pure function and prove its behavior using failing tests first."),
    ("coding-debugging-006", "coding", "medium", ["systematic-debugging"], ["songwriting-and-ai-music"], "A cache invalidation change caused stale results in a web service. Find the failing path and add a regression test."),
    ("coding-debugging-007", "coding", "medium", ["test-driven-development", "systematic-debugging"], ["ascii-art"], "A YAML loader accepts malformed input silently. Define expected behavior, write tests, and fix validation."),
    ("coding-debugging-008", "coding", "hard", ["systematic-debugging"], ["popular-web-designs"], "A model evaluation script produces nondeterministic metrics between identical runs. Investigate sources of randomness and propose fixes."),
    ("coding-debugging-009", "coding", "easy", ["test-driven-development"], ["songwriting-and-ai-music"], "Refactor a utility function while preserving behavior through tests."),
    ("coding-debugging-010", "coding", "medium", ["systematic-debugging"], ["creative-ideation"], "A dependency upgrade broke an import path. Diagnose the compatibility issue and suggest a targeted patch."),
    ("research-writing-001", "research", "easy", ["research-paper-summary"], ["test-driven-development"], "Summarize a machine learning paper with key claims, evidence, limitations, and open questions."),
    ("research-writing-002", "research", "medium", ["literature-review"], ["songwriting-and-ai-music"], "Compare three papers on agent skill learning and identify common evaluation weaknesses."),
    ("research-writing-003", "research", "medium", ["citation-checking"], ["ascii-art"], "Check whether a technical claim is supported by the cited source and flag unsupported statements."),
    ("research-writing-004", "research", "easy", ["academic-writing"], ["macos-computer-use"], "Rewrite an abstract to be clearer, more concise, and more specific about the method and result."),
    ("research-writing-005", "research", "hard", ["literature-review", "citation-checking"], ["songwriting-and-ai-music"], "Build a structured related-work section for agent benchmarks and cite each comparison accurately."),
    ("research-writing-006", "research", "medium", ["research-paper-summary"], ["test-driven-development"], "Extract the dataset, method, metric, and conclusion from a speech recognition paper."),
    ("research-writing-007", "research", "easy", ["academic-writing"], ["ascii-art"], "Turn rough experiment notes into a polished results paragraph without overstating the conclusion."),
    ("research-writing-008", "research", "medium", ["citation-checking"], ["creative-ideation"], "Identify which citations in a draft support empirical claims and which only provide background context."),
    ("data-mlops-001", "data-analysis", "easy", ["data-analysis"], ["songwriting-and-ai-music"], "Analyze a CSV file, compute summary statistics, and explain anomalies in the results."),
    ("data-mlops-002", "mlops", "medium", ["mlflow"], ["ascii-art"], "Compare two model training runs and identify which hyperparameters changed."),
    ("data-mlops-003", "mlops", "medium", ["wandb"], ["baoyu-comic"], "Inspect experiment tracking logs and summarize the best checkpoint by validation metric."),
    ("data-mlops-004", "data-analysis", "medium", ["python-data-analysis"], ["songwriting-and-ai-music"], "Clean a dataset with missing values and produce a reproducible transformation script."),
    ("data-mlops-005", "mlops", "hard", ["docker", "mlflow"], ["creative-ideation"], "Package a model evaluation job in Docker and record metrics in an experiment tracker."),
    ("data-mlops-006", "data-analysis", "easy", ["python-data-analysis"], ["macos-computer-use"], "Create a chart from tabular benchmark results and explain the trend."),
    ("creative-productivity-001", "creative", "easy", ["ascii-art"], ["systematic-debugging"], "Create a small ASCII diagram explaining a three-step workflow."),
    ("creative-productivity-002", "creative", "medium", ["baoyu-comic"], ["mlflow"], "Turn a short technical anecdote into a four-panel comic concept."),
    ("creative-productivity-003", "creative", "easy", ["songwriting-and-ai-music"], ["test-driven-development"], "Write a short chorus for an upbeat song about debugging late at night."),
    ("productivity-001", "productivity", "easy", ["apple-reminders"], ["citation-checking"], "Create a reminder list for preparing a research presentation."),
    ("productivity-002", "productivity", "medium", ["google-calendar"], ["ascii-art"], "Schedule a focused work block and avoid conflicts with existing meetings."),
    ("productivity-003", "productivity", "medium", ["note-taking"], ["docker"], "Turn meeting notes into action items, decisions, and unresolved questions."),
]


def main() -> None:
    root = Path("benchmarks/tasks")
    root.mkdir(parents=True, exist_ok=True)
    for task_id, category, difficulty, gold_skills, negative_skills, prompt in TASKS:
        task_dir = root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        task_yaml = {
            "id": task_id,
            "category": category,
            "difficulty": difficulty,
            "gold_skills": gold_skills,
            "negative_skills": negative_skills,
            "verifier": "skill_selection",
        }
        (task_dir / "task.yaml").write_text(
            yaml.safe_dump(task_yaml, sort_keys=False),
            encoding="utf-8",
        )
        (task_dir / "prompt.md").write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
```

Run:

```bash
python scripts/generate_benchmark_tasks.py
```

Expected: `benchmarks/tasks` contains exactly 30 directories, each with `task.yaml` and `prompt.md`.

- [ ] **Step 2: Write README**

Create `README.md`:

````markdown
# Hermes SkillEval

Hermes SkillEval is an offline CLI harness for evaluating skill routing in Hermes-style agent skill libraries.

The MVP indexes `skills/**/SKILL.md`, loads labeled benchmark tasks, compares routers, and writes reproducible JSONL and Markdown reports. It does not require Hermes Agent, network access, or an LLM API key.

## Quickstart

Install in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Index a skills directory:

```bash
skilleval index --skills-path /path/to/hermes/skills --output index/skills.json
```

Run evaluation:

```bash
skilleval eval --index index/skills.json --tasks benchmarks/tasks --router hybrid --top-k 5 --output-dir runs/latest
```

Generate a report:

```bash
skilleval report --runs runs/latest
```

Run tests:

```bash
pytest -v
```

## Metrics

Reports include Recall@1, Recall@3, Recall@5, Precision@5, MRR, NDCG@5, Negative Hit Rate, latency, top selected skills, and failure cases.

## Scope

This first version evaluates skill selection only. Real Hermes execution, LLM judges, automatic skill patching, and web dashboards are planned future extensions.
````

- [ ] **Step 3: Add benchmark count smoke test**

Modify `tests/test_cli_smoke.py` by adding:

```python
from hermes_skilleval.task_loader import load_tasks


def test_builtin_benchmark_has_30_tasks():
    tasks = load_tasks(Path("benchmarks/tasks"))

    assert len(tasks) == 30
```

- [ ] **Step 4: Run full test suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md benchmarks scripts/generate_benchmark_tasks.py tests/test_cli_smoke.py
git commit -m "docs: add benchmark tasks and quickstart"
```

## Task 10: MVP Verification Against Spec

**Files:**
- Modify: none unless verification reveals a defect.

- [ ] **Step 1: Install editable package**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: install completes successfully.

- [ ] **Step 2: Run full tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run local fixture smoke flow**

Run:

```bash
skilleval index --skills-path tests/fixtures/skills --output /tmp/skilleval-fixture-index.json
skilleval eval --index /tmp/skilleval-fixture-index.json --tasks tests/fixtures/tasks --router hybrid --top-k 3 --output-dir /tmp/skilleval-fixture-run
skilleval report --runs /tmp/skilleval-fixture-run
```

Expected:

```text
/tmp/skilleval-fixture-index.json exists
/tmp/skilleval-fixture-run/results.jsonl exists
/tmp/skilleval-fixture-run/report.md exists
```

- [ ] **Step 4: Run benchmark task smoke flow**

Run:

```bash
skilleval index --skills-path tests/fixtures/skills --output /tmp/skilleval-index.json
skilleval eval --index /tmp/skilleval-index.json --tasks benchmarks/tasks --router keyword --top-k 5 --output-dir /tmp/skilleval-benchmark-run
skilleval report --runs /tmp/skilleval-benchmark-run
```

Expected:

```text
/tmp/skilleval-benchmark-run/results.jsonl has 30 lines
/tmp/skilleval-benchmark-run/report.md contains "Recall@5"
```

- [ ] **Step 5: Inspect git status**

Run:

```bash
git status --short
```

Expected: clean worktree.
