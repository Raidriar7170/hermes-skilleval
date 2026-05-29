# Phase 13 Patch Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simulate Phase 12 ranked metadata patches in a shadow skill index and produce before/after routing regression artifacts.

**Architecture:** Add a focused `skill_patch_simulation` module that reads ranked patch candidates, applies the top-N candidates to copied `Skill` records, reruns a deterministic router over migration tasks, and compares baseline routes against shadow routes. The CLI only wires arguments and router construction; the module owns artifact writing and guard calculations.

**Tech Stack:** Python stdlib, existing `Skill`, `BenchmarkTask`, `SkillRouter`, metrics helpers, `load_skill_index`, `save_skill_index`, `load_tasks`, and existing deterministic routers.

---

## File Structure

- Create `src/hermes_skilleval/skill_patch_simulation.py`
  - Owns ranked patch loading, shadow patch application, shadow route execution, route diff generation, aggregate summary, and Markdown report rendering.
- Modify `src/hermes_skilleval/cli.py`
  - Adds `simulate-skill-patches` parser and `_run_simulate_skill_patches`.
  - Reuses `_router(args.router, args)` so router behavior stays consistent with `eval`.
- Create `tests/test_skill_patch_simulation.py`
  - Unit tests for shadow patch application, route-diff regression guard, and artifact writing.
- Modify `tests/test_cli_smoke.py`
  - Adds CLI smoke coverage for `simulate-skill-patches`.
- Create `tests/test_phase13_artifacts.py`
  - Guards committed Phase 13 artifacts and docs.
- Create `docs/phase13.md`
  - Documents scope, inputs, artifacts, and reproduction command.
- Create `docs/demo/phase13-patch-simulation/`
  - `shadow-skills.json`
  - `shadow-results.jsonl`
  - `route-diffs.jsonl`
  - `regression-summary.json`
  - `regression-report.md`
- Modify `README.md`
  - Adds usage snippet, Phase 13 docs link, roadmap status, and updated test count.

---

## Task 1: Shadow Patch Application

**Files:**
- Create: `src/hermes_skilleval/skill_patch_simulation.py`
- Test: `tests/test_skill_patch_simulation.py`

- [ ] **Step 1: Write the failing shadow-copy test**

```python
from hermes_skilleval.models import Skill
from hermes_skilleval.skill_patch_simulation import apply_ranked_patch_candidates


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
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py::test_apply_ranked_patch_candidates_returns_shadow_copy_without_mutating_source -q -p no:cacheprovider
```

Expected: fails with `ModuleNotFoundError` or missing `apply_ranked_patch_candidates`.

- [ ] **Step 3: Implement minimal patch application**

Create `src/hermes_skilleval/skill_patch_simulation.py` with:

```python
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from hermes_skilleval.models import Skill


def read_ranked_patches(path: Path | str) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return sorted(records, key=lambda record: int(record.get("rank") or 10**9))


def apply_ranked_patch_candidates(
    skills: list[Skill],
    candidates: list[dict[str, Any]],
    *,
    max_patches: int | None = None,
) -> tuple[list[Skill], list[dict[str, Any]]]:
    by_id = {skill.id: skill for skill in skills}
    applied: list[dict[str, Any]] = []
    limit = len(candidates) if max_patches is None else max_patches
    for candidate in sorted(candidates, key=lambda record: int(record.get("rank") or 10**9)):
        if len(applied) >= limit:
            break
        if candidate.get("status", "proposed") != "proposed":
            continue
        skill_id = str(candidate["target_skill_id"])
        if skill_id not in by_id:
            raise ValueError(f"patch target skill not found: {skill_id}")
        by_id[skill_id] = _apply_candidate(by_id[skill_id], candidate)
        applied.append(dict(candidate))
    return [by_id[skill.id] for skill in skills], applied


def _apply_candidate(skill: Skill, candidate: dict[str, Any]) -> Skill:
    field = str(candidate["patch_field"])
    operation = str(candidate["operation"])
    if field == "trigger_terms" and operation == "append_terms":
        terms = list(skill.trigger_terms)
        for term in candidate.get("added_terms", []):
            value = str(term)
            if value and value not in terms:
                terms.append(value)
        return replace(skill, trigger_terms=terms)
    if field == "description" and operation == "append_sentence":
        text = str(candidate.get("added_text") or "").strip()
        return replace(skill, description=_append_text(skill.description, text))
    if field == "body" and operation == "append_section_note":
        text = str(candidate.get("added_text") or "").strip()
        return replace(skill, body=_append_text(skill.body, text))
    raise ValueError(f"unsupported patch candidate: {field}/{operation}")


def _append_text(before: str, addition: str) -> str:
    if not addition or addition in before:
        return before
    return f"{before.rstrip()} {addition}".strip()
```

- [ ] **Step 4: Run test to verify GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py::test_apply_ranked_patch_candidates_returns_shadow_copy_without_mutating_source -q -p no:cacheprovider
```

Expected: pass.

---

## Task 2: Route Diff And Regression Guard

**Files:**
- Modify: `src/hermes_skilleval/skill_patch_simulation.py`
- Test: `tests/test_skill_patch_simulation.py`

- [ ] **Step 1: Write the failing route-diff test**

```python
from hermes_skilleval.skill_patch_simulation import compare_route_records


def test_compare_route_records_flags_recall_and_negative_regressions():
    baseline = [
        {
            "task_id": "task-001",
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
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py::test_compare_route_records_flags_recall_and_negative_regressions -q -p no:cacheprovider
```

Expected: fails with missing `compare_route_records`.

- [ ] **Step 3: Implement comparison helpers**

Add to `skill_patch_simulation.py`:

```python
METRIC_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "negative_accepted_rate",
    "selection_rate_at_5",
)


def compare_route_records(
    baseline_records: list[dict[str, Any]],
    shadow_records: list[dict[str, Any]],
    *,
    applied_by_task: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    baseline_by_task = {str(record["task_id"]): record for record in baseline_records}
    shadow_by_task = {str(record["task_id"]): record for record in shadow_records}
    if set(baseline_by_task) != set(shadow_by_task):
        missing = sorted(set(baseline_by_task) ^ set(shadow_by_task))
        raise ValueError(f"baseline and shadow task ids differ: {', '.join(missing)}")
    applied_by_task = applied_by_task or {}
    return [
        _route_diff(
            baseline_by_task[task_id],
            shadow_by_task[task_id],
            applied_by_task.get(task_id, []),
        )
        for task_id in sorted(baseline_by_task)
    ]


def _route_diff(
    baseline: dict[str, Any],
    shadow: dict[str, Any],
    applied_candidate_ids: list[str],
) -> dict[str, Any]:
    before_metrics = {field: float(baseline[field]) for field in METRIC_FIELDS}
    after_metrics = {field: float(shadow[field]) for field in METRIC_FIELDS}
    metric_deltas = {
        field: round(after_metrics[field] - before_metrics[field], 6)
        for field in METRIC_FIELDS
    }
    before_selected = list(baseline["selected_skill_ids"])
    after_selected = list(shadow["selected_skill_ids"])
    negative = set(baseline["negative_skills"])
    before_negative = set(before_selected) & negative
    after_negative = set(after_selected) & negative
    regressions = []
    improvements = []
    for field in ("recall_at_5", "mrr", "ndcg_at_5"):
        if after_metrics[field] < before_metrics[field]:
            regressions.append(f"{field}_decreased")
        if after_metrics[field] > before_metrics[field]:
            improvements.append(f"{field}_increased")
    for field in ("negative_hit_rate", "negative_accepted_rate"):
        if after_metrics[field] > before_metrics[field]:
            regressions.append(f"{field}_increased")
        if after_metrics[field] < before_metrics[field]:
            improvements.append(f"{field}_decreased")
    if after_negative - before_negative:
        regressions.append("new_negative_skill_selected")
    if before_negative - after_negative:
        improvements.append("removed_negative_skill")
    return {
        "task_id": baseline["task_id"],
        "before_selected_skill_ids": before_selected,
        "after_selected_skill_ids": after_selected,
        "gold_skills": list(baseline["gold_skills"]),
        "negative_skills": list(baseline["negative_skills"]),
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "metric_deltas": metric_deltas,
        "selection_changed": before_selected != after_selected,
        "regression_flags": regressions,
        "improvement_flags": improvements,
        "applied_candidate_ids": applied_candidate_ids,
    }
```

- [ ] **Step 4: Run comparison tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py -q -p no:cacheprovider
```

Expected: all current simulation tests pass.

---

## Task 3: Simulation Artifact Writer

**Files:**
- Modify: `src/hermes_skilleval/skill_patch_simulation.py`
- Test: `tests/test_skill_patch_simulation.py`

- [ ] **Step 1: Write the failing artifact test**

```python
import json
from pathlib import Path

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.skill_patch_simulation import simulate_skill_patches


class FirstSkillRouter(SkillRouter):
    name = "first-skill"

    def route(self, task, skills, top_k):
        selected = [skills[0].id]
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=selected,
            scores={skill.id: float(len(skills) - index) for index, skill in enumerate(skills)},
            latency_ms=0.0,
        )


def test_simulate_skill_patches_writes_shadow_artifacts(tmp_path: Path):
    skills = [
        Skill("gold", "Gold", "skills/gold/SKILL.md", "test", "Gold skill.", "# Gold", ["gold"], 1),
        Skill("bad", "Bad", "skills/bad/SKILL.md", "test", "Bad skill.", "# Bad", ["bad"], 1),
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
```

- [ ] **Step 2: Run artifact test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py::test_simulate_skill_patches_writes_shadow_artifacts -q -p no:cacheprovider
```

Expected: fails with missing `simulate_skill_patches`.

- [ ] **Step 3: Implement artifact writer**

Extend `skill_patch_simulation.py` with:

```python
from hermes_skilleval.metrics import (
    abstention_rate,
    accepted_count,
    accepted_recall_at_k,
    coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_accepted_rate,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
    selection_rate_at_k,
)
from hermes_skilleval.models import BenchmarkTask, RouteResult
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.skill_index import save_skill_index


def simulate_skill_patches(
    *,
    ranked_patches: list[dict[str, Any]],
    baseline_records_path: Path | str,
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    router: SkillRouter,
    router_label: str,
    top_k: int,
    output_dir: Path | str,
    max_patches: int | None = None,
    input_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if max_patches is not None and max_patches <= 0:
        raise ValueError("max_patches must be positive")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    shadow_skills, applied = apply_ranked_patch_candidates(
        skills, ranked_patches, max_patches=max_patches
    )
    baseline_records = _read_jsonl(baseline_records_path)
    shadow_records = [_route_record(task, router.route(task, shadow_skills, top_k), router_label) for task in tasks]
    applied_by_task = _applied_by_task(applied)
    diffs = compare_route_records(baseline_records, shadow_records, applied_by_task=applied_by_task)
    summary = _summary(
        baseline_records,
        shadow_records,
        diffs,
        applied,
        router_label=router_label,
        top_k=top_k,
        input_paths=input_paths or {},
    )
    save_skill_index(shadow_skills, output / "shadow-skills.json")
    _write_jsonl(output / "shadow-results.jsonl", shadow_records)
    _write_jsonl(output / "route-diffs.jsonl", diffs)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "regression-report.md").write_text(_report(summary, diffs), encoding="utf-8")
    return summary
```

Also add private helpers for `_read_jsonl`, `_write_jsonl`, `_route_record`, `_summary`, `_mean_metrics`, `_applied_by_task`, and `_report`.

- [ ] **Step 4: Run simulation tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py -q -p no:cacheprovider
```

Expected: all simulation tests pass.

---

## Task 4: CLI Smoke Path

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Add a `test_cli_simulate_skill_patches_writes_artifacts` near the Phase 12 CLI smoke test. It should create one task, one baseline route file, one `skills.json`, one `ranked-patches.jsonl`, invoke:

```python
result = main(
    [
        "simulate-skill-patches",
        "--ranked-patches",
        str(ranked_patches),
        "--baseline-routes",
        str(baseline_routes),
        "--tasks",
        str(tasks),
        "--skills-index",
        str(skills_index),
        "--router",
        "hybrid",
        "--top-k",
        "1",
        "--max-patches",
        "1",
        "--output-dir",
        str(output_dir),
    ]
)
```

Assert `result == 0` and all five Phase 13 artifact files exist.

- [ ] **Step 2: Run CLI test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_simulate_skill_patches_writes_artifacts -q -p no:cacheprovider
```

Expected: fails because the CLI command is not registered.

- [ ] **Step 3: Add CLI command**

In `cli.py`:

```python
from hermes_skilleval.skill_patch_simulation import (
    read_ranked_patches,
    simulate_skill_patches,
)
```

Register parser:

```python
simulate_patches_parser = subparsers.add_parser(
    "simulate-skill-patches",
    help="apply ranked metadata patches to a shadow skill index and check route regressions",
)
simulate_patches_parser.add_argument("--ranked-patches", required=True)
simulate_patches_parser.add_argument("--baseline-routes", required=True)
simulate_patches_parser.add_argument("--tasks", required=True)
simulate_patches_parser.add_argument("--skills-index", required=True)
simulate_patches_parser.add_argument("--router", choices=ROUTER_NAMES, default="hybrid")
_add_embedding_args(simulate_patches_parser)
_add_gated_args(simulate_patches_parser)
_add_cross_encoder_args(simulate_patches_parser)
simulate_patches_parser.add_argument("--top-k", type=int, default=5)
simulate_patches_parser.add_argument("--max-patches", type=int, default=5)
simulate_patches_parser.add_argument("--output-dir", required=True)
simulate_patches_parser.set_defaults(handler=_run_simulate_skill_patches)
```

Handler:

```python
def _run_simulate_skill_patches(args: argparse.Namespace) -> None:
    skills = load_skill_index(args.skills_index)
    tasks = load_tasks(args.tasks)
    router = _router(args.router, args)
    router_label = f"{_default_router_label(args.router, getattr(args, 'embedding_backend', None))}-shadow"
    summary = simulate_skill_patches(
        ranked_patches=read_ranked_patches(args.ranked_patches),
        baseline_records_path=args.baseline_routes,
        tasks=tasks,
        skills=skills,
        router=router,
        router_label=router_label,
        top_k=args.top_k,
        max_patches=args.max_patches,
        output_dir=args.output_dir,
        input_paths={
            "ranked_patches": args.ranked_patches,
            "baseline_routes": args.baseline_routes,
            "tasks": args.tasks,
            "skills_index": args.skills_index,
        },
    )
    print(
        "Wrote patch simulation artifacts to "
        f"{args.output_dir}: {summary['guard_status']}"
    )
```

- [ ] **Step 4: Run CLI test to verify GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_simulate_skill_patches_writes_artifacts -q -p no:cacheprovider
```

Expected: pass.

---

## Task 5: Committed Demo Artifacts And Docs

**Files:**
- Create: `docs/phase13.md`
- Create: `docs/demo/phase13-patch-simulation/*`
- Modify: `README.md`
- Create: `tests/test_phase13_artifacts.py`

- [ ] **Step 1: Generate Phase 13 artifacts**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m hermes_skilleval.cli simulate-skill-patches \
  --ranked-patches docs/demo/phase12-skill-patch-ranking/ranked-patches.jsonl \
  --baseline-routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --router hybrid \
  --top-k 5 \
  --max-patches 5 \
  --output-dir docs/demo/phase13-patch-simulation
```

Expected: writes five artifacts under `docs/demo/phase13-patch-simulation/`.

- [ ] **Step 2: Add Phase 13 docs**

Create `docs/phase13.md` with:

```markdown
# Phase 13: Patch Simulation & Regression Guard

Phase 13 applies the top ranked Phase 12 metadata patch candidates to a shadow
skill index, reruns deterministic hybrid routing, and compares the shadow run
against the Phase 9 baseline routes.

## Scope

The run is offline and deterministic. It does not modify source SKILL.md files
and does not overwrite the original migrated skills index.

## Artifacts

Artifacts live under `docs/demo/phase13-patch-simulation/`:

- `shadow-skills.json`
- `shadow-results.jsonl`
- `route-diffs.jsonl`
- `regression-summary.json`
- `regression-report.md`

## Reproduce

```bash
PYTHONPATH=src python -m hermes_skilleval.cli simulate-skill-patches \
  --ranked-patches docs/demo/phase12-skill-patch-ranking/ranked-patches.jsonl \
  --baseline-routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --router hybrid \
  --top-k 5 \
  --max-patches 5 \
  --output-dir docs/demo/phase13-patch-simulation
```
```

After generation, add a compact result table with the actual `guard_status`,
task count, applied candidate count, regression count, and improvement count from
`regression-summary.json`.

- [ ] **Step 3: Update README**

Add a CLI usage section after Phase 12, add Phase 13 to the docs table, mark
roadmap item `Patch simulation regression guard` complete, and update test
counts after running the final suite.

- [ ] **Step 4: Write artifact guard test**

Create `tests/test_phase13_artifacts.py`:

```python
import json
from pathlib import Path


PHASE13_ROOT = Path("docs/demo/phase13-patch-simulation")
README = Path("README.md")
PHASE13_DOC = Path("docs/phase13.md")


def test_phase13_patch_simulation_artifacts_are_committed():
    summary = json.loads((PHASE13_ROOT / "regression-summary.json").read_text())
    diffs = _read_jsonl(PHASE13_ROOT / "route-diffs.jsonl")
    shadow_results = _read_jsonl(PHASE13_ROOT / "shadow-results.jsonl")
    shadow_skills = json.loads((PHASE13_ROOT / "shadow-skills.json").read_text())
    report = (PHASE13_ROOT / "regression-report.md").read_text(encoding="utf-8")

    assert summary["phase"] == "Phase 13"
    assert summary["artifact_type"] == "phase13-patch-simulation"
    assert summary["applied_candidate_count"] == 5
    assert len(diffs) == summary["task_count"]
    assert len(shadow_results) == summary["task_count"]
    assert isinstance(shadow_skills, list)
    assert report.startswith("# Phase 13 Patch Simulation")
    assert summary["source_mutation"] == "none; source SKILL.md files are not modified"


def test_phase13_docs_and_readme_are_updated():
    readme = README.read_text(encoding="utf-8")
    phase13 = PHASE13_DOC.read_text(encoding="utf-8")

    assert "| Phase 13 | Patch simulation regression guard |" in readme
    assert "simulate-skill-patches" in readme
    assert "does not modify source SKILL.md files" in phase13
    assert "regression-summary.json" in phase13


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 5: Run docs/artifact tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase13_artifacts.py -q -p no:cacheprovider
```

Expected: pass.

---

## Task 6: Final Validation

**Files:**
- All Phase 13 files

- [ ] **Step 1: Run targeted Phase 13 validation**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_simulation.py tests/test_phase13_artifacts.py tests/test_cli_smoke.py::test_cli_simulate_skill_patches_writes_artifacts -q -p no:cacheprovider
```

Expected: all targeted tests pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
```

Expected: all tests pass. Update README test count to the exact number shown.

- [ ] **Step 3: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Run sensitive information scan**

Run:

```bash
rg -n "115\\.190\\.60\\.96|\\b2222\\b|\\b18001\\b|BEGIN [A-Z ]*PRIVATE KEY|PRIVATE KEY|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|api[_-]?key\\s*[:=]|password\\s*[:=]|/root/code|/root/|/Users/raidriar" docs/demo/phase13-patch-simulation docs/phase13.md README.md src/hermes_skilleval tests -S
```

Expected: no matches; `rg` exits 1.

- [ ] **Step 5: Commit Phase 13**

Run:

```bash
git add README.md docs/phase13.md docs/demo/phase13-patch-simulation docs/superpowers/plans/2026-05-29-phase13-patch-simulation.md src/hermes_skilleval/cli.py src/hermes_skilleval/skill_patch_simulation.py tests/test_cli_smoke.py tests/test_phase13_artifacts.py tests/test_skill_patch_simulation.py
git commit -m "feat: add patch simulation regression guard"
```

Expected: a single Phase 13 commit on `codex/phase13-patch-simulation`.

---

## Self-Review Notes

- Scope stays offline and deterministic.
- No source `SKILL.md` files are modified.
- `shadow-skills.json` remains a standard `list[Skill]` index.
- `after_excerpt` is not used as patch source because it is display-only and truncated.
- Guard is per-task first, aggregate metrics second.
