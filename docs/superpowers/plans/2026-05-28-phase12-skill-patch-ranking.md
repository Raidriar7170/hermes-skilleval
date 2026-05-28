# Phase 12 Skill Patch Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline deterministic metadata patch ranking layer that turns Phase 11 failed agent-loop traces into auditable skill metadata patch candidates.

**Architecture:** Add a focused `skill_patch_ranking.py` module that joins Phase 11 judge failures with Phase 9 routes, migration task metadata, and the migrated skill index. The CLI exposes `skilleval rank-skill-patches`; committed artifacts show ranked candidates for the three Phase 11 `negative_skill_selected` failures without modifying source `SKILL.md` files.

**Tech Stack:** Python 3.11 standard library, PyYAML, existing `skill_index` loader, existing JSONL/Markdown artifact patterns, pytest.

---

## File Structure

- Create `src/hermes_skilleval/skill_patch_ranking.py`: load inputs, normalize failure records, generate candidates, score candidates, write JSONL/summary/report artifacts.
- Modify `src/hermes_skilleval/cli.py`: add `rank-skill-patches` parser and handler.
- Create `tests/test_skill_patch_ranking.py`: unit tests for failure loading, candidate generation, ranking stability, and no source mutation.
- Modify `tests/test_cli_smoke.py`: add `rank-skill-patches` smoke test.
- Create `tests/test_phase12_artifacts.py`: pin committed Phase 12 artifact contract.
- Create `docs/phase12.md`: explain ranking signals, scope limits, commands, and current result.
- Create `docs/demo/phase12-skill-patch-ranking/`: generated `patch-candidates.jsonl`, `ranked-patches.jsonl`, `ranking-summary.json`, and `ranked-patches.md`.
- Modify `README.md`: add Phase 12 timeline, usage, Roadmap item, and final test count.

## Task 1: Patch Ranking Core

**Files:**
- Create: `src/hermes_skilleval/skill_patch_ranking.py`
- Create: `tests/test_skill_patch_ranking.py`

- [ ] **Step 1: Write failing core tests**

Create `tests/test_skill_patch_ranking.py` with:

```python
import json
from pathlib import Path

import yaml

from hermes_skilleval.skill_patch_ranking import rank_skill_patches


def test_rank_skill_patches_generates_ranked_candidates_for_failed_judge_run(tmp_path: Path):
    _write_task(
        tmp_path / "tasks",
        "task-001",
        gold=["browser-smoke-testing"],
        negative=["systematic-debugging"],
        expected_evidence=["opened URL", "nonblank page"],
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                _skill("browser-smoke-testing", ["browser", "smoke"], "Open local pages."),
                _skill("systematic-debugging", ["debug"], "Debug failures."),
            ]
        ),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "router": "hybrid",
                "selected_skill_ids": ["browser-smoke-testing", "systematic-debugging"],
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "scores": {"browser-smoke-testing": 30.0, "systematic-debugging": 20.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judge = tmp_path / "judge-results.jsonl"
    judge.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "trace_id": "agent-loop-hybrid:task-001",
                "execution_condition": "routed-skill",
                "judge_pass": False,
                "judge_score": 0.0,
                "evidence_score": 0.0,
                "failure_type": "negative_skill_selected",
                "penalties": ["missing-evidence", "negative-skill-failure"],
                "expected_evidence": ["opened URL", "nonblank page"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = rank_skill_patches(
        judge_results_path=judge,
        routes_path=routes,
        tasks_path=tmp_path / "tasks",
        skills_index_path=skills_index,
        output_dir=tmp_path / "phase12",
    )

    candidates = _read_jsonl(tmp_path / "phase12" / "patch-candidates.jsonl")
    ranked = _read_jsonl(tmp_path / "phase12" / "ranked-patches.jsonl")

    assert summary["phase"] == "Phase 12"
    assert summary["failed_task_count"] == 1
    assert summary["candidate_count"] >= 2
    assert ranked[0]["rank"] == 1
    assert ranked[0]["source_task_id"] == "task-001"
    assert ranked[0]["target_skill_id"] == "browser-smoke-testing"
    assert ranked[0]["demote_skill_ids"] == ["systematic-debugging"]
    assert ranked[0]["total_score"] >= ranked[-1]["total_score"]
    assert {candidate["patch_field"] for candidate in candidates} >= {
        "trigger_terms",
        "description",
    }
    assert (tmp_path / "phase12" / "ranking-summary.json").exists()
    assert (tmp_path / "phase12" / "ranked-patches.md").exists()


def test_rank_skill_patches_ignores_passing_judge_records(tmp_path: Path):
    _write_task(
        tmp_path / "tasks",
        "task-001",
        gold=["systematic-debugging"],
        negative=["visual-regression-review"],
        expected_evidence=["root cause note"],
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps([_skill("systematic-debugging", ["debug"], "Debug failures.")]),
        encoding="utf-8",
    )
    routes = tmp_path / "routes.jsonl"
    routes.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": ["visual-regression-review"],
                "scores": {"systematic-debugging": 40.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judge = tmp_path / "judge-results.jsonl"
    judge.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "judge_pass": True,
                "failure_type": None,
                "penalties": [],
                "expected_evidence": ["root cause note"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = rank_skill_patches(
        judge_results_path=judge,
        routes_path=routes,
        tasks_path=tmp_path / "tasks",
        skills_index_path=skills_index,
        output_dir=tmp_path / "phase12",
    )

    assert summary["failed_task_count"] == 0
    assert summary["candidate_count"] == 0
    assert _read_jsonl(tmp_path / "phase12" / "patch-candidates.jsonl") == []


def _write_task(
    root: Path,
    task_id: str,
    *,
    gold: list[str],
    negative: list[str],
    expected_evidence: list[str],
) -> None:
    task_dir = root / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": task_id,
                "category": "migration",
                "difficulty": "medium",
                "gold_skills": gold,
                "negative_skills": negative,
                "verifier": "manual",
                "split": "test",
                "robustness_tags": ["migration-evaluation"],
                "expected_evidence": expected_evidence,
                "migration_dimensions": ["evidence completeness"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Open the local dashboard and verify a nonblank page.",
        encoding="utf-8",
    )


def _skill(skill_id: str, trigger_terms: list[str], description: str) -> dict[str, object]:
    return {
        "id": skill_id,
        "name": skill_id.replace("-", " ").title(),
        "path": f"benchmarks/migrated-skills/test/{skill_id}/SKILL.md",
        "category": "test",
        "description": description,
        "body": description,
        "trigger_terms": trigger_terms,
        "token_count_estimate": 10,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_ranking.py -q -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'hermes_skilleval.skill_patch_ranking'`.

- [ ] **Step 3: Implement core module**

Create `src/hermes_skilleval/skill_patch_ranking.py` with:

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from hermes_skilleval.skill_index import load_skill_index


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SCORING_WEIGHTS = {
    "gold_boost": 0.35,
    "negative_separation": 0.25,
    "minimality": 0.15,
    "field_safety": 0.10,
    "source_support": 0.15,
}
FIELD_SAFETY = {"trigger_terms": 1.0, "description": 0.75, "body": 0.55}


def rank_skill_patches(
    *,
    judge_results_path: Path | str,
    routes_path: Path | str,
    tasks_path: Path | str,
    skills_index_path: Path | str,
    output_dir: Path | str,
) -> dict[str, object]:
    judge_records = _read_jsonl(Path(judge_results_path))
    routes = {str(record["task_id"]): record for record in _read_jsonl(Path(routes_path))}
    tasks = _load_tasks(Path(tasks_path))
    skills = {skill.id: skill for skill in load_skill_index(skills_index_path)}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    failures = [
        _failure_input(record, routes, tasks, skills)
        for record in judge_records
        if record.get("judge_pass") is not True
    ]
    candidates = []
    for failure in failures:
        candidates.extend(_candidates_for_failure(failure))
    ranked = _rank_candidates(candidates)

    _write_jsonl(output / "patch-candidates.jsonl", candidates)
    _write_jsonl(output / "ranked-patches.jsonl", ranked)
    summary = _summary(
        failures=failures,
        candidates=ranked,
        judge_results_path=str(judge_results_path),
        routes_path=str(routes_path),
        tasks_path=str(tasks_path),
        skills_index_path=str(skills_index_path),
    )
    (output / "ranking-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "ranked-patches.md").write_text(_report(summary, ranked), encoding="utf-8")
    return summary
```

Implement helpers in the same module:

- `_read_jsonl(path)`: return list of dicts.
- `_write_jsonl(path, records)`: one sorted JSON object per line.
- `_load_tasks(root)`: load every `task.yaml` plus `prompt.md`; preserve `gold_skills`, `negative_skills`, `expected_evidence`, and `migration_dimensions`.
- `_failure_input(record, routes, tasks, skills)`: join judge failure with route/task/skill metadata; raise `ValueError` when required join data is missing.
- `_candidates_for_failure(failure)`: generate three candidate types for every gold skill:
  - `trigger_terms` / `append_terms`
  - `description` / `append_sentence`
  - `body` / `append_section_note`
- `_candidate(failure, skill_id, patch_field, operation, added_terms, added_text)`: produce dict with `candidate_id`, `source_task_id`, `target_skill_id`, `patch_field`, `operation`, `before_excerpt`, `after_excerpt`, `added_terms`, `added_text`, `demote_skill_ids`, `rationale`, `evidence_inputs`, `deterministic_scores`, `total_score`, `rank`, `status`.
- `_rank_candidates(candidates)`: sort by `-total_score`, `source_task_id`, `target_skill_id`, `patch_field`, then assign 1-based rank.
- `_score_candidate(candidate, failure)`: combine weights from `SCORING_WEIGHTS`.
- `_tokens(text)`: lower-case lexical terms length >= 4.
- `_summary(failures, candidates, judge_results_path, routes_path, tasks_path, skills_index_path)`: include `phase: "Phase 12"`, `artifact_type: "phase12-skill-patch-ranking"`, failed task count, candidate count, top candidate ids, input paths, scoring weights.
- `_report(summary, ranked)`: Markdown starting with `# Phase 12 Skill Patch Ranking`.

Do not write back to `benchmarks/migrated-skills` or `skills.json`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_skill_patch_ranking.py -q -p no:cacheprovider
```

Expected: `2 passed`.

## Task 2: CLI Command

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Add CLI smoke test**

Append a test named `test_cli_rank_skill_patches_writes_artifacts` to `tests/test_cli_smoke.py`. Use the same miniature fixture shape as Task 1 and call:

```python
result = main(
    [
        "rank-skill-patches",
        "--judge-results",
        str(judge),
        "--routes",
        str(routes),
        "--tasks",
        str(tasks),
        "--skills-index",
        str(skills_index),
        "--output-dir",
        str(output_dir),
    ]
)
```

Assert:

```python
assert result == 0
assert (output_dir / "patch-candidates.jsonl").exists()
assert (output_dir / "ranked-patches.jsonl").exists()
assert (output_dir / "ranking-summary.json").exists()
assert (output_dir / "ranked-patches.md").exists()
```

- [ ] **Step 2: Verify CLI RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_rank_skill_patches_writes_artifacts -q -p no:cacheprovider
```

Expected: fail because `rank-skill-patches` is not registered.

- [ ] **Step 3: Wire CLI**

Modify `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.skill_patch_ranking import rank_skill_patches
```

Add parser near the existing improvement commands:

```python
rank_patches_parser = subparsers.add_parser(
    "rank-skill-patches",
    help="rank offline metadata patch candidates from failed agent-loop judge records",
)
rank_patches_parser.add_argument("--judge-results", required=True)
rank_patches_parser.add_argument("--routes", required=True)
rank_patches_parser.add_argument("--tasks", required=True)
rank_patches_parser.add_argument("--skills-index", required=True)
rank_patches_parser.add_argument("--output-dir", required=True)
rank_patches_parser.set_defaults(handler=_run_rank_skill_patches)
```

Add handler:

```python
def _run_rank_skill_patches(args: argparse.Namespace) -> None:
    summary = rank_skill_patches(
        judge_results_path=args.judge_results,
        routes_path=args.routes,
        tasks_path=args.tasks,
        skills_index_path=args.skills_index,
        output_dir=args.output_dir,
    )
    print(
        "Wrote skill patch ranking artifacts to "
        f"{args.output_dir}: {summary['candidate_count']} candidates"
    )
```

- [ ] **Step 4: Verify CLI GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_rank_skill_patches_writes_artifacts -q -p no:cacheprovider
```

Expected: `1 passed`.

## Task 3: Phase 12 Artifacts and Docs

**Files:**
- Create: `docs/demo/phase12-skill-patch-ranking/patch-candidates.jsonl`
- Create: `docs/demo/phase12-skill-patch-ranking/ranked-patches.jsonl`
- Create: `docs/demo/phase12-skill-patch-ranking/ranking-summary.json`
- Create: `docs/demo/phase12-skill-patch-ranking/ranked-patches.md`
- Create: `docs/phase12.md`
- Modify: `README.md`
- Create: `tests/test_phase12_artifacts.py`

- [ ] **Step 1: Add artifact tests**

Create `tests/test_phase12_artifacts.py`:

```python
import json
from pathlib import Path


PHASE12_ROOT = Path("docs/demo/phase12-skill-patch-ranking")
README = Path("README.md")
PHASE12_DOC = Path("docs/phase12.md")


def test_phase12_patch_ranking_artifacts_are_committed():
    candidates = _read_jsonl(PHASE12_ROOT / "patch-candidates.jsonl")
    ranked = _read_jsonl(PHASE12_ROOT / "ranked-patches.jsonl")
    summary = json.loads((PHASE12_ROOT / "ranking-summary.json").read_text())
    report = (PHASE12_ROOT / "ranked-patches.md").read_text(encoding="utf-8")

    assert summary["phase"] == "Phase 12"
    assert summary["artifact_type"] == "phase12-skill-patch-ranking"
    assert summary["failed_task_count"] == 3
    assert summary["candidate_count"] >= 9
    assert len(candidates) == summary["candidate_count"]
    assert len(ranked) == summary["candidate_count"]
    assert [record["rank"] for record in ranked] == list(range(1, len(ranked) + 1))
    assert {record["source_task_id"] for record in ranked} == {
        "browser-local-dashboard",
        "claude-command-routing",
        "sp-debug-red-green",
    }
    assert all(record["status"] == "proposed" for record in ranked)
    assert report.startswith("# Phase 12 Skill Patch Ranking")


def test_phase12_docs_and_readme_are_updated():
    readme = README.read_text(encoding="utf-8")
    phase12 = PHASE12_DOC.read_text(encoding="utf-8")

    assert "| Phase 12 | Offline skill metadata patch ranking |" in readme
    assert "- [x] Offline skill metadata patch ranking" in readme
    assert "rank-skill-patches" in readme
    assert "does not modify source SKILL.md files" in phase12
    assert "negative_skill_selected" in phase12


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 2: Verify artifact RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase12_artifacts.py -q -p no:cacheprovider
```

Expected: fail on missing Phase 12 artifacts/docs.

- [ ] **Step 3: Generate artifacts**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli rank-skill-patches \
  --judge-results docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-hybrid/judge-results.jsonl \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase12-skill-patch-ranking
```

Expected: four artifact files are written under `docs/demo/phase12-skill-patch-ranking/`.

- [ ] **Step 4: Write docs**

Create `docs/phase12.md`:

```markdown
# Phase 12: Offline Skill Metadata Patch Ranking

Phase 12 ranks metadata patch candidates from Phase 11 failed agent-loop judge
records. It focuses on `negative_skill_selected` failures where the router
retrieved gold skills but also selected a task negative skill.

## Scope

The committed run is offline and deterministic. It does not modify source
SKILL.md files, does not write a patched skill index, and does not claim
fine-tuning or learned model training.

## Artifacts

Artifacts live under `docs/demo/phase12-skill-patch-ranking/`:

- `patch-candidates.jsonl`
- `ranked-patches.jsonl`
- `ranking-summary.json`
- `ranked-patches.md`

## Reproduce

Use `skilleval rank-skill-patches` with Phase 11 judge failures, Phase 9
routes, migration tasks, and the migrated skill index.
```

Add this result summary table, replacing the candidate count and top candidate
IDs with the exact values from `ranking-summary.json` after artifacts are
generated:

```markdown
| Failed Tasks | Candidates | Top Candidate IDs |
|---:|---:|---|
| 3 | 18 | values copied from `ranking-summary.json["top_candidate_ids"]` |
```

- [ ] **Step 5: Update README**

Update README:

- Add quick-start usage for `skilleval rank-skill-patches`.
- Add timeline row:
  `| Phase 12 | Offline skill metadata patch ranking | [docs/phase12.md](docs/phase12.md) |`
- Add Roadmap item:
  `- [x] Offline skill metadata patch ranking ([docs](docs/phase12.md), [demo](docs/demo/phase12-skill-patch-ranking/ranked-patches.md))`
- Update test count after full suite.

## Task 4: Final Validation and Review

**Files:**
- All changed files.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest \
  tests/test_skill_patch_ranking.py \
  tests/test_phase12_artifacts.py \
  tests/test_cli_smoke.py::test_cli_rank_skill_patches_writes_artifacts \
  -q -p no:cacheprovider
```

Expected: all targeted tests pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
```

Expected: all tests pass. Update README with exact count.

- [ ] **Step 3: Run diff and sensitive scans**

Run:

```bash
git diff --check
```

Expected: no output.

Run:

```bash
rg -n "115\\.190\\.60\\.96|\\b2222\\b|\\b18001\\b|BEGIN [A-Z ]*PRIVATE KEY|PRIVATE KEY|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|api[_-]?key\\s*[:=]|password\\s*[:=]|/root/code|/root/|/Users/raidriar" \
  docs/demo/phase12-skill-patch-ranking docs/phase12.md README.md src/hermes_skilleval tests -S
```

Expected: no matches. `rg` exit code `1` means no matches.

- [ ] **Step 4: Request read-only Reviewer**

Reviewer must inspect Phase 12 code, docs, artifacts, and tests, then output:

```text
Must Fix:
Should Fix:
Nice to Have:
Re-plan Needed: Yes/No
Final Verdict:
```

## Self-Review Checklist

- The plan only outputs candidate artifacts and never mutates source `SKILL.md` files.
- Phase 12 wording uses “offline deterministic metadata patch ranking,” not fine-tuning.
- Failure inputs are joined from Phase 11 judge results plus Phase 9 route/task/skill metadata.
- Tests cover core module, CLI smoke, committed artifacts, docs, and README.
