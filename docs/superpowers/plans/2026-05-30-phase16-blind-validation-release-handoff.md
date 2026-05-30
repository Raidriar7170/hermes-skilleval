# Phase 16 Blind Validation And Release Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a blind real-skill migration validation pack and a release handoff gate so Phase 15's held-out provenance becomes stronger project evidence without claiming external benchmark status.

**Architecture:** Keep the Phase 14 trained model unchanged. Add a new blind task root that was not used for fine-tuning, evaluate the baseline MiniLM embedding router and the fine-tuned embedding router against that root, then write a Phase 16 comparison pack and release handoff document. Add a small release-check module so the final public artifact gate is repeatable.

**Tech Stack:** Python 3.11, argparse CLI, pytest, JSONL, Markdown, existing `skilleval` eval/dashboard commands, optional sentence-transformers runtime, A100 artifacts under `/mnt/data/minghongsun`.

**Repository Execution Note:** Follow `AGENTS.md` Codex Orchestrator Apply Protocol for implementation in this repository. Start from `main` after the Phase 15 fast-forward merge. Use an isolated worktree or branch named `codex/phase16-blind-validation-release-handoff`. Do not commit model checkpoints, private hosts, SSH details, tokens, passwords, downloaded models, or files outside `/mnt/data/minghongsun` into public docs or artifacts.

---

## File Structure

- Create `benchmarks/blind-migration-tasks/*/task.yaml`
  - Sixteen new blind tasks, one per migrated skill in `docs/demo/phase9-real-skill-library-migration/skills.json`.
  - Every task uses `split: test` and `robustness_tags: [blind-validation, phase16, real-skill-library-migration]`.
- Create `benchmarks/blind-migration-tasks/*/prompt.md`
  - Natural task prompts that do not reveal gold or negative skill IDs.
- Create `src/hermes_skilleval/blind_validation.py`
  - Compare baseline and candidate route JSONL files.
  - Write Phase 16 `regression-summary.json`, `route-diffs.jsonl`, and `comparison.md`.
- Modify `src/hermes_skilleval/cli.py`
  - Add `write-blind-validation`.
  - Add `verify-release`.
- Create `src/hermes_skilleval/release_checks.py`
  - Check required public artifacts.
  - Scan public docs/artifacts for sensitive strings and checkpoint extensions.
  - Guard public wording against affirmative SOTA/production/external-benchmark overclaim while allowing explicit negative disclaimers such as "does not establish SOTA".
- Create `tests/test_phase16_blind_tasks.py`
  - Guard blind task count, split policy, skill coverage, missing references, prompt leakage, and Phase 14 training leakage.
- Create `tests/test_blind_validation.py`
  - Unit-test Phase 16 summary generation and regression detection.
- Modify `tests/test_cli_smoke.py`
  - Cover `write-blind-validation` and `verify-release`.
- Create `tests/test_release_checks.py`
  - Unit-test sensitive scan, checkpoint scan, required artifact checks, and overclaim guard.
- Create `tests/test_phase16_artifacts.py`
  - Guard committed Phase 16 docs/artifacts after generation.
- Create `docs/phase16.md`
  - Document blind validation scope, result table, and limits.
- Create `docs/release-handoff.md`
  - One-page reviewer/interview handoff over Phase 9 through Phase 16 evidence.
- Modify `README.md`
  - Add Phase 16 command surface, roadmap entry, handoff link, and current test count.
- Generate `docs/demo/phase16-blind-validation/`
  - `baseline-minilm/results.jsonl`
  - `baseline-minilm/report.md`
  - `finetuned-embedding/results.jsonl`
  - `finetuned-embedding/report.md`
  - `regression-summary.json`
  - `route-diffs.jsonl`
  - `comparison.md`
  - `dashboard.html`
  - `release-check-summary.json`

## Blind Task Catalog

Implement these exact task IDs and skill labels. The prompt text can be expanded, but it must preserve the intent in the `Prompt intent` column and must not contain the literal gold or negative skill ID.

| Task ID | Category | Difficulty | Gold skill | Negative skill | Prompt intent |
|---|---|---|---|---|---|
| `blind-browser-accessibility-tree` | `browser-gui` | `hard` | `accessibility-tree-inspection` | `browser-smoke-testing` | Inspect a local modal with keyboard focus failure and report roles, names, and focus order evidence. |
| `blind-browser-smoke-console` | `browser-gui` | `medium` | `browser-smoke-testing` | `visual-regression-review` | Open a local dashboard, verify key controls render, and report console or network errors. |
| `blind-browser-form-wizard` | `browser-gui` | `hard` | `form-interaction-flow` | `accessibility-tree-inspection` | Fill a multi-step form, choose values, submit it, and report resulting validation state. |
| `blind-browser-visual-diff` | `browser-gui` | `medium` | `visual-regression-review` | `browser-smoke-testing` | Compare a local page screenshot against a reference and identify visual regressions. |
| `blind-claude-mcp-routing` | `claude-code` | `medium` | `mcp-tool-routing` | `slash-command-workflow` | Decide whether a repo question should use MCP resources or normal file reads and explain the routing. |
| `blind-claude-plan-session` | `claude-code` | `medium` | `plan-mode` | `task-tool-delegation` | Turn an ambiguous requested change into a plan-mode question flow before implementation. |
| `blind-claude-slash-command` | `claude-code` | `medium` | `slash-command-workflow` | `mcp-tool-routing` | Explain how to run a named slash-command workflow and what files it should update. |
| `blind-claude-task-delegation` | `claude-code` | `hard` | `task-tool-delegation` | `plan-mode` | Split independent codebase checks across delegated read-only agents and combine findings. |
| `blind-codex-apply-patch` | `codex` | `medium` | `apply-patch-discipline` | `workspace-git-hygiene` | Edit a tracked source file with a surgical patch and avoid shell write tricks. |
| `blind-codex-evidence-final` | `codex` | `medium` | `evidence-backed-final` | `verification-before-completion` | Write a final answer that cites exact verification commands and avoids unsupported claims. |
| `blind-codex-worker-handoff` | `codex` | `hard` | `subagent-worker-protocol` | `task-tool-delegation` | Prepare a bounded worker brief with ownership, validation, changed-file reporting, and review loop. |
| `blind-codex-git-hygiene` | `codex` | `medium` | `workspace-git-hygiene` | `apply-patch-discipline` | Inspect dirty git state and protect unrelated user changes while continuing a task. |
| `blind-sp-debug-loop` | `superpowers` | `hard` | `systematic-debugging` | `test-driven-development` | Diagnose a failing test by reproducing, isolating, forming hypotheses, and verifying the root cause. |
| `blind-sp-red-green` | `superpowers` | `hard` | `test-driven-development` | `systematic-debugging` | Add a behavior through red-green-refactor rather than coding the implementation first. |
| `blind-sp-worktree-isolation` | `superpowers` | `medium` | `using-git-worktrees` | `workspace-git-hygiene` | Start feature work in an isolated worktree and report branch/root/status before edits. |
| `blind-sp-verify-before-claim` | `superpowers` | `medium` | `verification-before-completion` | `evidence-backed-final` | Before saying a task is complete, identify, run, and report the verification commands. |

## Task 1: Blind Migration Task Pack

**Files:**
- Create: `benchmarks/blind-migration-tasks/*/task.yaml`
- Create: `benchmarks/blind-migration-tasks/*/prompt.md`
- Create: `tests/test_phase16_blind_tasks.py`

- [ ] **Step 1: Write failing blind-pack tests**

Create `tests/test_phase16_blind_tasks.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path("benchmarks/blind-migration-tasks")
SKILLS_INDEX = Path("docs/demo/phase9-real-skill-library-migration/skills.json")
PHASE14_PAIRS = Path("docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl")
EXPECTED_GOLD_SKILLS = {
    "accessibility-tree-inspection",
    "browser-smoke-testing",
    "form-interaction-flow",
    "visual-regression-review",
    "mcp-tool-routing",
    "plan-mode",
    "slash-command-workflow",
    "task-tool-delegation",
    "apply-patch-discipline",
    "evidence-backed-final",
    "subagent-worker-protocol",
    "workspace-git-hygiene",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "verification-before-completion",
}


def _tasks() -> list[tuple[Path, dict]]:
    return [
        (path, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(ROOT.glob("*/task.yaml"))
    ]


def test_phase16_blind_pack_has_one_task_per_migrated_skill() -> None:
    tasks = _tasks()
    assert len(tasks) == 16
    gold = [task["gold_skills"][0] for _, task in tasks]
    assert set(gold) == EXPECTED_GOLD_SKILLS
    assert len(gold) == len(set(gold))


def test_phase16_blind_tasks_are_test_split_and_referenced_skills_exist() -> None:
    skill_ids = {
        skill["id"]
        for skill in json.loads(SKILLS_INDEX.read_text(encoding="utf-8"))
    }
    for path, task in _tasks():
        assert task["split"] == "test", path
        assert task["verifier"] == "skill_selection", path
        assert task["robustness_tags"] == [
            "blind-validation",
            "phase16",
            "real-skill-library-migration",
        ], path
        assert set(task["gold_skills"]).issubset(skill_ids), path
        assert set(task["negative_skills"]).issubset(skill_ids), path
        assert not set(task["gold_skills"]) & set(task["negative_skills"]), path


def test_phase16_prompts_do_not_reveal_skill_ids() -> None:
    for task_path, task in _tasks():
        prompt = (task_path.parent / "prompt.md").read_text(encoding="utf-8")
        assert prompt.strip(), task_path
        for skill_id in task["gold_skills"] + task["negative_skills"]:
            assert skill_id not in prompt, task_path


def test_phase16_blind_task_ids_not_used_in_phase14_training() -> None:
    train_like = {
        json.loads(line)["task_id"]
        for line in PHASE14_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    blind_ids = {task["id"] for _, task in _tasks()}
    assert not blind_ids & train_like


def test_phase16_prompts_are_not_phase14_training_queries() -> None:
    phase14_queries = {
        json.loads(line)["query_text"].strip()
        for line in PHASE14_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    prompts = {
        (task_path.parent / "prompt.md").read_text(encoding="utf-8").strip()
        for task_path, _ in _tasks()
    }
    assert not prompts & phase14_queries
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_phase16_blind_tasks.py
```

Expected before creating the pack: FAIL because `benchmarks/blind-migration-tasks` does not exist and the task count is `0`.

- [ ] **Step 3: Create the blind task directories**

Create one directory per row in the Blind Task Catalog. Each `task.yaml` must follow this shape:

```yaml
id: blind-browser-accessibility-tree
category: browser-gui
difficulty: hard
gold_skills:
- accessibility-tree-inspection
negative_skills:
- browser-smoke-testing
verifier: skill_selection
split: test
robustness_tags:
- blind-validation
- phase16
- real-skill-library-migration
```

For every other task, change only `id`, `category`, `difficulty`, `gold_skills`, and `negative_skills` according to the catalog. Each `prompt.md` must be a natural-language task request based on the catalog intent and must avoid literal skill IDs.

- [ ] **Step 4: Run the blind-pack tests again**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_phase16_blind_tasks.py
```

Expected after creating the pack: PASS.

- [ ] **Step 5: Commit the blind task pack**

```bash
git add benchmarks/blind-migration-tasks tests/test_phase16_blind_tasks.py
git commit -m "test: add phase16 blind migration task pack"
```

## Task 2: Blind Validation Summary Writer

**Files:**
- Create: `src/hermes_skilleval/blind_validation.py`
- Modify: `src/hermes_skilleval/cli.py`
- Create: `tests/test_blind_validation.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing summary tests**

Create `tests/test_blind_validation.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_skilleval.blind_validation import write_blind_validation_summary


def _record(task_id: str, *, selected: list[str], negative_hit_rate: float = 0.0) -> dict:
    return {
        "task_id": task_id,
        "category": "codex",
        "difficulty": "medium",
        "split": "test",
        "robustness_tags": ["blind-validation", "phase16", "real-skill-library-migration"],
        "router": "embedding",
        "prompt": "Need a safe edit workflow.",
        "selected_skill_ids": selected,
        "scores": {skill_id: 1.0 / (index + 1) for index, skill_id in enumerate(selected)},
        "gold_skills": ["apply-patch-discipline"],
        "negative_skills": ["workspace-git-hygiene"],
        "latency_ms": 1.0,
        "recall_at_1": 1.0 if selected[0] == "apply-patch-discipline" else 0.0,
        "recall_at_3": 1.0,
        "recall_at_5": 1.0,
        "precision_at_5": 0.2,
        "mrr": 1.0 if selected[0] == "apply-patch-discipline" else 0.5,
        "ndcg_at_5": 1.0,
        "negative_hit_rate": negative_hit_rate,
        "accepted_count": len(selected),
        "coverage": 1.0,
        "selection_rate_at_5": len(selected) / 5,
        "abstention_rate": 0.0,
        "accepted_recall_at_5": 1.0,
        "negative_accepted_rate": negative_hit_rate,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_write_blind_validation_summary_detects_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(baseline, [_record("blind-task", selected=["apply-patch-discipline"])])
    _write_jsonl(
        candidate,
        [
            _record(
                "blind-task",
                selected=["apply-patch-discipline", "workspace-git-hygiene"],
                negative_hit_rate=1.0,
            )
        ],
    )

    summary = write_blind_validation_summary(
        baseline_results_path=baseline,
        candidate_results_path=candidate,
        output_dir=tmp_path / "out",
        baseline_router="baseline-minilm",
        candidate_router="finetuned-embedding",
        model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        task_root="benchmarks/blind-migration-tasks",
    )

    assert summary["phase"] == "Phase 16"
    assert summary["artifact_type"] == "phase16-blind-validation"
    assert summary["task_count"] == 1
    assert summary["guard_status"] == "REVIEW_REQUIRED"
    assert summary["regression_count"] == 1
    assert (tmp_path / "out" / "route-diffs.jsonl").is_file()
    assert (tmp_path / "out" / "comparison.md").is_file()


def test_write_blind_validation_summary_rejects_mismatched_task_ids(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(baseline, [_record("baseline-only", selected=["apply-patch-discipline"])])
    _write_jsonl(candidate, [_record("candidate-only", selected=["apply-patch-discipline"])])

    with pytest.raises(ValueError, match="task ids differ"):
        write_blind_validation_summary(
            baseline_results_path=baseline,
            candidate_results_path=candidate,
            output_dir=tmp_path / "out",
            baseline_router="baseline-minilm",
            candidate_router="finetuned-embedding",
            model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            task_root="benchmarks/blind-migration-tasks",
        )
```

- [ ] **Step 2: Add a failing CLI smoke test**

Append to `tests/test_cli_smoke.py`:

```python
def test_cli_write_blind_validation_summary(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    record = _finetuned_eval_record(
        "blind-task",
        split="test",
        selected=["apply-patch-discipline"],
        gold=("apply-patch-discipline",),
        negative=("workspace-git-hygiene",),
    )
    baseline.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    result = main(
        [
            "write-blind-validation",
            "--baseline-results",
            str(baseline),
            "--candidate-results",
            str(candidate),
            "--output-dir",
            str(tmp_path / "out"),
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            "--task-root",
            "benchmarks/blind-migration-tasks",
        ]
    )

    assert result == 0
    summary = json.loads((tmp_path / "out" / "regression-summary.json").read_text())
    assert summary["guard_status"] == "PASS"
```

- [ ] **Step 3: Run the failing tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_blind_validation.py tests/test_cli_smoke.py
```

Expected before implementation: FAIL with `ModuleNotFoundError: hermes_skilleval.blind_validation` or an unknown CLI command.

- [ ] **Step 4: Implement `blind_validation.py`**

Create `src/hermes_skilleval/blind_validation.py` with these public functions and fields:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_skilleval.remote_paths import validate_a100_user_path
from hermes_skilleval.skill_patch_simulation import compare_route_records


METRIC_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "negative_accepted_rate",
    "selection_rate_at_5",
)


def write_blind_validation_summary(
    *,
    baseline_results_path: Path | str,
    candidate_results_path: Path | str,
    output_dir: Path | str,
    baseline_router: str,
    candidate_router: str,
    model_dir: str,
    task_root: str,
) -> dict[str, Any]:
    baseline_records = _read_jsonl(baseline_results_path)
    candidate_records = _read_jsonl(candidate_results_path)
    diffs = compare_route_records(baseline_records, candidate_records)
    regression_count = sum(1 for diff in diffs if diff["regression_flags"])
    improvement_count = sum(1 for diff in diffs if diff["improvement_flags"])
    baseline_metrics = _mean_metrics(baseline_records)
    candidate_metrics = _mean_metrics(candidate_records)
    summary = {
        "phase": "Phase 16",
        "artifact_type": "phase16-blind-validation",
        "task_root": task_root,
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "model_dir": validate_a100_user_path(model_dir, field="model_dir"),
        "model_checkpoint_committed": False,
        "split_policy": "blind task root; all records must use split == 'test'",
        "task_count": len(candidate_records),
        "blind_task_ids": sorted(str(record["task_id"]) for record in candidate_records),
        "guard_status": "PASS" if regression_count == 0 else "REVIEW_REQUIRED",
        "baseline_mean_metrics": baseline_metrics,
        "candidate_mean_metrics": candidate_metrics,
        "metric_deltas": {
            field: round(candidate_metrics[field] - baseline_metrics[field], 6)
            for field in METRIC_FIELDS
        },
        "regression_count": regression_count,
        "improvement_count": improvement_count,
        "input_paths": {
            "baseline_results": str(baseline_results_path),
            "candidate_results": str(candidate_results_path),
            "task_root": task_root,
        },
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / "route-diffs.jsonl", diffs)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "comparison.md").write_text(_render_markdown(summary, diffs), encoding="utf-8")
    return summary
```

Also implement private `_read_jsonl`, `_write_jsonl`, `_mean_metrics`, and `_render_markdown` in the same style as `src/hermes_skilleval/finetuned_eval.py`. `_render_markdown` must include the title `# Phase 16 Blind Validation`, baseline/candidate names, task count, guard status, a metric table, and a guard-flags table when regressions or improvements exist.

- [ ] **Step 5: Add the CLI command**

Modify `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.blind_validation import write_blind_validation_summary
```

Add parser setup near the Phase 15 provenance commands:

```python
blind_validation_parser = subparsers.add_parser(
    "write-blind-validation",
    help="write a Phase 16 blind validation summary from baseline and candidate results",
)
blind_validation_parser.add_argument("--baseline-results", required=True)
blind_validation_parser.add_argument("--candidate-results", required=True)
blind_validation_parser.add_argument("--output-dir", required=True)
blind_validation_parser.add_argument("--baseline-router", default="baseline-minilm")
blind_validation_parser.add_argument("--candidate-router", default="finetuned-embedding")
blind_validation_parser.add_argument("--model-dir", required=True)
blind_validation_parser.add_argument("--task-root", required=True)
blind_validation_parser.set_defaults(handler=_run_write_blind_validation)
```

Add the handler:

```python
def _run_write_blind_validation(args: argparse.Namespace) -> None:
    summary = write_blind_validation_summary(
        baseline_results_path=args.baseline_results,
        candidate_results_path=args.candidate_results,
        output_dir=args.output_dir,
        baseline_router=args.baseline_router,
        candidate_router=args.candidate_router,
        model_dir=args.model_dir,
        task_root=args.task_root,
    )
    print(
        "Wrote Phase 16 blind validation summary to "
        f"{args.output_dir}: guard={summary['guard_status']}, "
        f"tasks={summary['task_count']}"
    )
```

- [ ] **Step 6: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_blind_validation.py tests/test_cli_smoke.py
```

Expected after implementation: PASS.

- [ ] **Step 7: Commit the summary writer**

```bash
git add src/hermes_skilleval/blind_validation.py src/hermes_skilleval/cli.py tests/test_blind_validation.py tests/test_cli_smoke.py
git commit -m "feat: add phase16 blind validation summary"
```

## Task 3: Generate Phase 16 Blind Evaluation Artifacts

**Files:**
- Create: `docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl`
- Create: `docs/demo/phase16-blind-validation/baseline-minilm/report.md`
- Create: `docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl`
- Create: `docs/demo/phase16-blind-validation/finetuned-embedding/report.md`
- Create: `docs/demo/phase16-blind-validation/regression-summary.json`
- Create: `docs/demo/phase16-blind-validation/route-diffs.jsonl`
- Create: `docs/demo/phase16-blind-validation/comparison.md`
- Create: `docs/demo/phase16-blind-validation/dashboard.html`
- Create: `tests/test_phase16_artifacts.py`

- [ ] **Step 1: Write failing artifact tests**

Create `tests/test_phase16_artifacts.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("docs/demo/phase16-blind-validation")
CHECKPOINT_SUFFIXES = {".bin", ".ckpt", ".pt", ".pth", ".safetensors"}


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_phase16_artifact_pack_exists_and_is_blind_only() -> None:
    required = [
        ROOT / "baseline-minilm" / "results.jsonl",
        ROOT / "baseline-minilm" / "report.md",
        ROOT / "finetuned-embedding" / "results.jsonl",
        ROOT / "finetuned-embedding" / "report.md",
        ROOT / "regression-summary.json",
        ROOT / "route-diffs.jsonl",
        ROOT / "comparison.md",
        ROOT / "dashboard.html",
    ]
    for path in required:
        assert path.is_file(), path

    baseline = _jsonl(ROOT / "baseline-minilm" / "results.jsonl")
    candidate = _jsonl(ROOT / "finetuned-embedding" / "results.jsonl")
    assert len(baseline) == 16
    assert len(candidate) == 16
    assert {record["task_id"] for record in baseline} == {
        record["task_id"] for record in candidate
    }
    assert {record["split"] for record in baseline + candidate} == {"test"}
    assert all("blind-validation" in record["robustness_tags"] for record in baseline + candidate)


def test_phase16_summary_shape_and_public_claims() -> None:
    summary = json.loads((ROOT / "regression-summary.json").read_text(encoding="utf-8"))
    assert summary["phase"] == "Phase 16"
    assert summary["artifact_type"] == "phase16-blind-validation"
    assert summary["task_count"] == 16
    assert summary["model_checkpoint_committed"] is False
    assert summary["guard_status"] in {"PASS", "REVIEW_REQUIRED"}
    text = (ROOT / "comparison.md").read_text(encoding="utf-8").lower()
    forbidden = ["state-of-the-art", "sota", "production-ready", "external benchmark"]
    for phrase in forbidden:
        assert phrase not in text


def test_phase16_artifact_pack_does_not_commit_checkpoints() -> None:
    checkpoint_files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix in CHECKPOINT_SUFFIXES
    ]
    assert checkpoint_files == []
```

- [ ] **Step 2: Run the failing artifact test**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_phase16_artifacts.py
```

Expected before artifact generation: FAIL because the Phase 16 artifact root does not exist.

- [ ] **Step 3: Evaluate the baseline MiniLM router**

Run locally if the optional embedding dependency and model cache are available:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli eval \
  --index docs/demo/phase9-real-skill-library-migration/skills.json \
  --tasks benchmarks/blind-migration-tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --output-dir docs/demo/phase16-blind-validation/baseline-minilm

PYTHONPATH=src python -m hermes_skilleval.cli report \
  --runs docs/demo/phase16-blind-validation/baseline-minilm
```

If local resources are insufficient, run the same command on the A100 from a project checkout under `/mnt/data/minghongsun/hermes-skilleval-phase16`, then copy back only `results.jsonl` and `report.md`.

- [ ] **Step 4: Evaluate the fine-tuned embedding router**

Run on the A100 or any environment that can access the Phase 14 model directory:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli eval \
  --index docs/demo/phase9-real-skill-library-migration/skills.json \
  --tasks benchmarks/blind-migration-tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --output-dir docs/demo/phase16-blind-validation/finetuned-embedding

PYTHONPATH=src python -m hermes_skilleval.cli report \
  --runs docs/demo/phase16-blind-validation/finetuned-embedding
```

Copy back only `results.jsonl` and `report.md`. Do not copy model files, caches, checkpoints, remote logs, SSH details, or host addresses into the repository.

- [ ] **Step 5: Write the Phase 16 blind validation summary**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli write-blind-validation \
  --baseline-results docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl \
  --candidate-results docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl \
  --output-dir docs/demo/phase16-blind-validation \
  --baseline-router baseline-minilm \
  --candidate-router finetuned-embedding \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --task-root benchmarks/blind-migration-tasks
```

- [ ] **Step 6: Write a dashboard for the two blind runs**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli dashboard \
  --runs docs/demo/phase16-blind-validation \
  --output docs/demo/phase16-blind-validation/dashboard.html
```

The dashboard command only reads subdirectories with `results.jsonl`, so it will include `baseline-minilm` and `finetuned-embedding`.

- [ ] **Step 7: Run artifact tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_phase16_artifacts.py
```

Expected after artifact generation: PASS.

- [ ] **Step 8: Commit the Phase 16 artifacts**

```bash
git add docs/demo/phase16-blind-validation tests/test_phase16_artifacts.py
git commit -m "docs: add phase16 blind validation artifacts"
```

## Task 4: Release Check Gate

**Files:**
- Create: `src/hermes_skilleval/release_checks.py`
- Modify: `src/hermes_skilleval/cli.py`
- Create: `tests/test_release_checks.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing release-check tests**

Create `tests/test_release_checks.py`:

```python
from __future__ import annotations

from pathlib import Path

from hermes_skilleval.release_checks import (
    ReleaseCheckResult,
    find_checkpoint_files,
    find_sensitive_matches,
    find_overclaim_matches,
    verify_required_paths,
)


def test_find_sensitive_matches_detects_secret_patterns(tmp_path: Path) -> None:
    path = tmp_path / "public.md"
    path.write_text("api_key=abc123\nBearer abc123\n", encoding="utf-8")
    matches = find_sensitive_matches([path])
    assert [match.path for match in matches] == [path, path]


def test_find_checkpoint_files_detects_weight_files(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_text("not real weights", encoding="utf-8")
    assert find_checkpoint_files(tmp_path) == [checkpoint]


def test_find_overclaim_matches_flags_affirmative_public_claims(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("This is a SOTA production-ready external benchmark.\n", encoding="utf-8")
    matches = find_overclaim_matches([path])
    assert len(matches) == 3


def test_find_overclaim_matches_allows_negative_disclaimers(tmp_path: Path) -> None:
    path = tmp_path / "phase.md"
    path.write_text(
        "This does not establish SOTA and is not a standard external benchmark.\n",
        encoding="utf-8",
    )
    assert find_overclaim_matches([path]) == []


def test_verify_required_paths_reports_missing(tmp_path: Path) -> None:
    existing = tmp_path / "README.md"
    existing.write_text("# ok\n", encoding="utf-8")
    result = verify_required_paths([existing, tmp_path / "missing.md"])
    assert isinstance(result, ReleaseCheckResult)
    assert result.ok is False
    assert "missing.md" in result.message
```

- [ ] **Step 2: Add a failing CLI smoke test**

Append to `tests/test_cli_smoke.py`:

```python
def test_cli_verify_release_reports_json_summary(tmp_path):
    public_file = tmp_path / "README.md"
    public_file.write_text("# Release\n", encoding="utf-8")

    result = main(
        [
            "verify-release",
            "--public-root",
            str(tmp_path),
            "--required-path",
            str(public_file),
            "--summary-output",
            str(tmp_path / "release-check-summary.json"),
        ]
    )

    assert result == 0
    summary = json.loads((tmp_path / "release-check-summary.json").read_text())
    assert summary["status"] == "PASS"
```

- [ ] **Step 3: Run failing release-check tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_release_checks.py tests/test_cli_smoke.py
```

Expected before implementation: FAIL with missing `hermes_skilleval.release_checks` or unknown command.

- [ ] **Step 4: Implement `release_checks.py`**

Create a small module with these public names:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


SENSITIVE_RE = re.compile(
    r"(AKIA|BEGIN OPENSSH|BEGIN RSA|PRIVATE KEY|ssh-ed25519|ssh-rsa|"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]|bearer\s+|"
    r"\bsk-[A-Za-z0-9_-]{8,}|\b(?:\d{1,3}\.){3}\d{1,3}\b|/root)",
    re.IGNORECASE,
)
OVERCLAIM_RE = re.compile(
    r"(?i)\b(state-of-the-art|sota|production-ready|external benchmark)\b"
)
CHECKPOINT_SUFFIXES = {".bin", ".ckpt", ".pt", ".pth", ".safetensors"}


@dataclass(frozen=True)
class TextMatch:
    path: Path
    line_number: int
    text: str


@dataclass(frozen=True)
class ReleaseCheckResult:
    name: str
    ok: bool
    message: str


def find_sensitive_matches(paths: list[Path]) -> list[TextMatch]:
    return _find_text_matches(paths, SENSITIVE_RE)


def find_overclaim_matches(paths: list[Path]) -> list[TextMatch]:
    return _find_text_matches(paths, OVERCLAIM_RE)


def find_checkpoint_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in CHECKPOINT_SUFFIXES
    )


def verify_required_paths(paths: list[Path]) -> ReleaseCheckResult:
    missing = [str(path) for path in paths if not path.exists()]
    return ReleaseCheckResult(
        name="required_paths",
        ok=not missing,
        message="all required paths exist" if not missing else "missing: " + ", ".join(missing),
    )
```

Also implement `_find_text_matches`, `run_release_checks`, and `write_release_check_summary`. `run_release_checks` must accept `public_roots: list[Path]` and `required_paths: list[Path]`; each public root may be a file or a directory. Scan only text-like files (`.md`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.html`, `.txt`, `.py`), exclude `docs/superpowers/**` by default, and return a JSON-serializable summary with `status`, `checks`, and `match_count`. `find_overclaim_matches` must ignore negative disclaimer lines containing phrases such as `does not establish`, `not a standard`, `not an external`, `does not claim`, or `should not be described`.

- [ ] **Step 5: Add the CLI command**

Modify `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.release_checks import write_release_check_summary
```

Add parser setup:

```python
verify_release_parser = subparsers.add_parser(
    "verify-release",
    help="scan public artifacts for required files, secrets, checkpoints, and overclaims",
)
verify_release_parser.add_argument("--public-root", action="append", required=True)
verify_release_parser.add_argument("--required-path", action="append", default=[])
verify_release_parser.add_argument("--summary-output", required=True)
verify_release_parser.set_defaults(handler=_run_verify_release)
```

Add the handler:

```python
def _run_verify_release(args: argparse.Namespace) -> None:
    summary = write_release_check_summary(
        public_roots=[Path(path) for path in args.public_root],
        required_paths=[Path(path) for path in args.required_path],
        output_path=Path(args.summary_output),
    )
    print(f"Release check {summary['status']}: {args.summary_output}")
    if summary["status"] != "PASS":
        raise ValueError("release check failed")
```

- [ ] **Step 6: Run targeted release-check tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_release_checks.py tests/test_cli_smoke.py
```

Expected after implementation: PASS.

- [ ] **Step 7: Commit the release gate**

```bash
git add src/hermes_skilleval/release_checks.py src/hermes_skilleval/cli.py tests/test_release_checks.py tests/test_cli_smoke.py
git commit -m "feat: add release verification gate"
```

## Task 5: Phase 16 Docs And Release Handoff

**Files:**
- Create: `docs/phase16.md`
- Create: `docs/release-handoff.md`
- Modify: `README.md`
- Modify: `tests/test_phase16_artifacts.py`
- Modify: `tests/test_phase14_artifacts.py`

- [ ] **Step 1: Extend artifact tests for docs and release handoff**

Add to `tests/test_phase16_artifacts.py`:

```python
def test_phase16_docs_and_release_handoff_exist() -> None:
    phase_doc = Path("docs/phase16.md")
    handoff = Path("docs/release-handoff.md")
    readme = Path("README.md")
    for path in [phase_doc, handoff, readme]:
        assert path.is_file(), path

    phase_text = phase_doc.read_text(encoding="utf-8")
    handoff_text = handoff.read_text(encoding="utf-8")
    readme_text = readme.read_text(encoding="utf-8")
    assert "Phase 16" in phase_text
    assert "blind validation" in phase_text.lower()
    assert "Phase 9" in handoff_text and "Phase 16" in handoff_text
    assert "docs/phase16.md" in readme_text
    assert "docs/release-handoff.md" in readme_text
```

Update `tests/test_phase14_artifacts.py` test-count guards to reject the old count and accept the new final count after this plan's tests are in place. Measure the expected final count from the full suite before editing the guard.

- [ ] **Step 2: Run the failing doc artifact test**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_phase16_artifacts.py
```

Expected before docs: FAIL because `docs/phase16.md` and `docs/release-handoff.md` do not exist.

- [ ] **Step 3: Create `docs/phase16.md`**

Create a concise doc with this structure:

```markdown
# Phase 16: Blind validation and release handoff

Phase 16 evaluates the Phase 14 fine-tuned embedding router on a new blind
real-skill migration task pack. The model is unchanged from Phase 14; this
phase adds new task coverage, a stricter comparison artifact, and a release
verification gate.

## Scope

The blind task pack lives under `benchmarks/blind-migration-tasks/` and contains
one held-out `test` task for each migrated real skill. These tasks were not used
for Phase 14 training.

## Result

The committed blind-validation result is recorded in
`docs/demo/phase16-blind-validation/regression-summary.json` and visualized in
`docs/demo/phase16-blind-validation/dashboard.html`. Treat this as a blind
regression audit over a new self-built task root, not as an external benchmark
claim.

## Release Gate

`skilleval verify-release` checks required public artifacts, checkpoint absence,
sensitive strings, and overclaim wording.

## Limitations

This remains a self-built Hermes-style skill-routing benchmark. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
```

- [ ] **Step 4: Create `docs/release-handoff.md`**

Create a one-page handoff with:

```markdown
# Hermes SkillEval Release Handoff

## One-line Positioning

Hermes SkillEval is a verification-gated skill routing and self-improvement
harness for Hermes-style agent skills, with reproducible JSONL, Markdown, and
HTML artifacts.

## Evidence Chain

| Phase | Evidence | Artifact |
|---|---|---|
| Phase 9 | Real skill-library migration protocol | `docs/phase9.md` |
| Phase 10 | Agent-in-the-loop migration traces | `docs/phase10.md` |
| Phase 11 | Deterministic evidence judge calibration | `docs/phase11.md` |
| Phase 12 | Offline skill metadata patch ranking | `docs/phase12.md` |
| Phase 13 | Patch simulation regression guard | `docs/phase13.md` |
| Phase 14 | Fine-tuned embedding router path | `docs/phase14.md` |
| Phase 15 | Held-out provenance pack | `docs/phase15.md` |
| Phase 16 | Blind validation and release gate | `docs/phase16.md` |

## Reviewer Entry Points

- Dashboard: `docs/demo/phase16-blind-validation/dashboard.html`
- Blind validation summary: `docs/demo/phase16-blind-validation/regression-summary.json`
- Provenance: `docs/demo/phase15-held-out-generalization/provenance.md`
- Release check: `docs/demo/phase16-blind-validation/release-check-summary.json`

## Boundaries

The repository does not commit model checkpoints, private machine details, or
external benchmark claims.
```

- [ ] **Step 5: Update README**

Add a Phase 16 command block near the Phase 15 section:

```bash
skilleval write-blind-validation \
  --baseline-results docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl \
  --candidate-results docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl \
  --output-dir docs/demo/phase16-blind-validation \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --task-root benchmarks/blind-migration-tasks

skilleval verify-release \
  --public-root README.md \
  --public-root docs/phase9.md \
  --public-root docs/phase10.md \
  --public-root docs/phase11.md \
  --public-root docs/phase12.md \
  --public-root docs/phase13.md \
  --public-root docs/phase14.md \
  --public-root docs/phase15.md \
  --public-root docs/phase16.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root benchmarks/blind-migration-tasks \
  --required-path docs/demo/phase16-blind-validation/regression-summary.json \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase16-blind-validation/release-check-summary.json
```

Also add:

```markdown
| Phase 16 | Blind validation and release handoff | [`docs/phase16.md`](docs/phase16.md) |
```

and a roadmap item:

```markdown
- [x] Blind validation and release handoff gate
      ([docs](docs/phase16.md), [handoff](docs/release-handoff.md))
```

- [ ] **Step 6: Run doc artifact tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_phase16_artifacts.py tests/test_phase14_artifacts.py
```

Expected after docs and README update: PASS.

- [ ] **Step 7: Commit docs and handoff**

```bash
git add docs/phase16.md docs/release-handoff.md README.md tests/test_phase16_artifacts.py tests/test_phase14_artifacts.py
git commit -m "docs: add phase16 release handoff"
```

## Task 6: Final Verification And Archive Commit

**Files:**
- Modify generated summary only if verification exposes a real issue.

- [ ] **Step 1: Run the release check command**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli verify-release \
  --public-root README.md \
  --public-root docs/phase9.md \
  --public-root docs/phase10.md \
  --public-root docs/phase11.md \
  --public-root docs/phase12.md \
  --public-root docs/phase13.md \
  --public-root docs/phase14.md \
  --public-root docs/phase15.md \
  --public-root docs/phase16.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root benchmarks/blind-migration-tasks \
  --required-path docs/phase16.md \
  --required-path docs/release-handoff.md \
  --required-path docs/demo/phase16-blind-validation/regression-summary.json \
  --required-path docs/demo/phase16-blind-validation/dashboard.html \
  --summary-output docs/demo/phase16-blind-validation/release-check-summary.json
```

Expected: `Release check PASS`.

- [ ] **Step 2: Run the full Python suite**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
```

Expected: all tests pass. Record the final count and update README/test-count guards if they are intentionally count-sensitive.

- [ ] **Step 3: Run static checks**

Run:

```bash
ruff check .
mypy src tests
python -m pip install -e . --dry-run
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 4: Run checkpoint and sensitive scans**

Run:

```bash
find docs/demo/phase16-blind-validation -type f \
  \( -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' -o -name '*.pth' -o -name '*.ckpt' \) -print
```

Expected: no output.

Run:

```bash
rg -n --hidden --glob '!*.pyc' --glob '!__pycache__/**' --glob '!.git/**' \
  '(AKIA|SECRET|TOKEN|PASSWORD|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|ssh-ed25519|ssh-rsa|/root|\b(?:\d{1,3}\.){3}\d{1,3}\b)' \
  README.md docs/phase*.md docs/release-handoff.md docs/demo benchmarks/blind-migration-tasks
```

Expected: no public artifact hits. If code/test false positives are scanned separately, explain them and keep the public artifact scan clean.

- [ ] **Step 5: Commit final generated release-check summary**

```bash
git add docs/demo/phase16-blind-validation/release-check-summary.json
git commit -m "chore: record phase16 release check summary"
```

- [ ] **Step 6: Final status report**

Run:

```bash
git status --short --branch
git log --oneline --decorate -6
```

Expected: the Phase 16 branch is ahead of `main` with a clean worktree except for unrelated user-owned files such as `.DS_Store`.

## Final Verification Checklist

- [ ] `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider`
- [ ] `ruff check .`
- [ ] `mypy src tests`
- [ ] `python -m pip install -e . --dry-run`
- [ ] `git diff --check`
- [ ] `PYTHONPATH=src python -m hermes_skilleval.cli verify-release ...`
- [ ] public artifact sensitive scan returns no hits
- [ ] Phase 16 demo artifact root contains no model checkpoints
- [ ] `README.md`, `docs/phase16.md`, and `docs/release-handoff.md` avoid SOTA, production-ready, and external-benchmark claims

## Success Criteria

- The blind task pack has 16 tasks, one per migrated skill, and none of the task IDs appear in Phase 14 train-like data.
- Baseline and fine-tuned blind runs use the same 16 task IDs and `split == "test"`.
- `docs/demo/phase16-blind-validation/regression-summary.json` states `phase: Phase 16`, `artifact_type: phase16-blind-validation`, `task_count: 16`, and `model_checkpoint_committed: false`.
- `docs/release-handoff.md` gives a reviewer a direct path from Phase 9 through Phase 16 artifacts.
- `verify-release` is repeatable from the CLI and writes `release-check-summary.json`.
- Full tests, lint, typing, editable-install dry-run, whitespace check, sensitive scan, and no-checkpoint scan are clean before commit.

## Self-Review Notes

- Scope coverage: the plan covers blind task creation, blind evaluation artifacts, release gate, docs, README, and final verification.
- Type consistency: `write_blind_validation_summary` returns a JSON-serializable `dict[str, Any]`; CLI handlers use `Path` only at the command boundary.
- Public wording: the docs explicitly frame this as self-built Hermes-style evidence and reject standard external benchmark, SOTA, and production readiness claims.
- Remote boundary: the only allowed remote artifact path in commands is under `/mnt/data/minghongsun`; public docs must not include hostnames, IPs, tokens, passwords, or SSH keys.
