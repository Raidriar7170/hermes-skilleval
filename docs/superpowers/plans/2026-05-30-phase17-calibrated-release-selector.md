# Phase 17 Calibrated Release Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative release selector that turns Phase 16 blind-validation evidence into an explicit default-router decision.

**Architecture:** Keep Phase 16 blind validation unchanged. Add a new `release_selector.py` module that reads `regression-summary.json` and `route-diffs.jsonl`, applies a small configurable regression budget, and writes `release-decision.json`, `release-decision.md`, and `task-decisions.jsonl`. Expose the selector through a `skilleval select-release-router` CLI command, then commit Phase 17 artifacts and docs showing that the current release keeps the baseline router by default.

**Tech Stack:** Python 3.11 standard library, existing JSON/JSONL artifact style, existing CLI `argparse`, `pytest`.

---

## Scope And Current Evidence

Phase 16 already writes the required input artifacts:

- `docs/demo/phase16-blind-validation/regression-summary.json`
- `docs/demo/phase16-blind-validation/route-diffs.jsonl`
- `docs/demo/phase16-blind-validation/comparison.md`

Current Phase 16 reading:

- `guard_status`: `REVIEW_REQUIRED`
- baseline: `baseline-minilm`
- candidate: `finetuned-embedding`
- blind tasks: `16`
- candidate preserves `recall_at_5`
- candidate worsens `mrr`, `ndcg_at_5`, `negative_hit_rate`, and `negative_accepted_rate`
- current default release decision should therefore keep `baseline-minilm`

Out of scope for Phase 17:

- Do not retrain the fine-tuned model.
- Do not change Phase 16 route results.
- Do not commit model checkpoints, embedding caches, private hosts, IPs, tokens, or remote logs.
- Do not claim standard benchmark, SOTA, or production readiness.

---

## File Structure

- Create `src/hermes_skilleval/release_selector.py`
  - Owns policy parsing, summary validation, task-level decision extraction, aggregate decision, JSON/Markdown/JSONL writing.
- Modify `src/hermes_skilleval/cli.py`
  - Adds `select-release-router` parser and `_run_select_release_router`.
- Create `tests/test_release_selector.py`
  - Unit-tests policy decisions and output artifacts.
- Modify `tests/test_cli_smoke.py`
  - Adds one CLI smoke test for `select-release-router`.
- Create `tests/test_phase17_artifacts.py`
  - Guards committed Phase 17 artifacts and documentation links.
- Create `docs/demo/phase17-calibrated-release-selector/`
  - Generated artifacts:
    - `release-decision.json`
    - `release-decision.md`
    - `task-decisions.jsonl`
    - `release-check-summary.json`
- Create `docs/phase17.md`
  - Documents scope, policy, result, limitations.
- Modify `docs/release-handoff.md`
  - Adds Phase 17 evidence row and current default-router reading.
- Modify `README.md`
  - Adds command block, timeline row, roadmap row, and fixes stale test count from `274` to the final full-suite count.

---

## Decision Model

### Status Values

Use these exact decision strings:

- `APPROVE_CANDIDATE`
- `KEEP_BASELINE`
- `REVIEW_REQUIRED`

### Default Policy

The default policy is intentionally conservative:

```json
{
  "max_regressions": 0,
  "max_negative_hit_delta": 0.0,
  "max_negative_accepted_delta": 0.0,
  "min_recall_at_5_delta": 0.0,
  "min_mrr_delta": 0.0,
  "min_ndcg_at_5_delta": 0.0
}
```

### Aggregate Rules

Return `REVIEW_REQUIRED` when:

- required fields are missing or malformed
- `route-diffs.jsonl` has task ids that do not match `regression-summary.json`
- no task diffs exist
- the Phase 16 summary itself is not for `artifact_type == "phase16-blind-validation"`
- duplicate task ids appear in route diffs
- `task_count` does not match the number of blind task ids or route diffs

Return `APPROVE_CANDIDATE` when all are true:

- Phase 16 `guard_status == "PASS"`
- `regression_count <= max_regressions`
- `negative_hit_rate` delta is at or below `max_negative_hit_delta`
- `negative_accepted_rate` delta is at or below `max_negative_accepted_delta`
- `recall_at_5`, `mrr`, and `ndcg_at_5` deltas are at or above their minimum deltas

Return `KEEP_BASELINE` when:

- inputs are valid
- candidate violates one or more policy budgets
- baseline router is present in the summary

For current Phase 16 artifacts, expected Phase 17 result:

```json
{
  "decision": "KEEP_BASELINE",
  "selected_router": "baseline-minilm",
  "candidate_router": "finetuned-embedding",
  "approved_for_default": false
}
```

---

## Task 1: Release Selector Unit Tests

**Files:**

- Create: `tests/test_release_selector.py`
- No implementation files yet.

- [ ] **Step 1: Add fixtures and the first failing keep-baseline test**

Create `tests/test_release_selector.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_skilleval.release_selector import (
    DEFAULT_RELEASE_POLICY,
    select_release_router,
    write_release_decision,
)


def _summary(
    *,
    guard_status: str = "REVIEW_REQUIRED",
    regression_count: int = 2,
    deltas: dict[str, float] | None = None,
) -> dict:
    metric_deltas = {
        "recall_at_5": 0.0,
        "mrr": -0.03125,
        "ndcg_at_5": -0.023067,
        "negative_hit_rate": 0.0625,
        "negative_accepted_rate": 0.0625,
        "selection_rate_at_5": 0.0,
    }
    if deltas:
        metric_deltas.update(deltas)
    return {
        "phase": "Phase 16",
        "artifact_type": "phase16-blind-validation",
        "task_count": 2,
        "blind_task_ids": ["task-a", "task-b"],
        "guard_status": guard_status,
        "baseline_router": "baseline-minilm",
        "candidate_router": "finetuned-embedding",
        "regression_count": regression_count,
        "improvement_count": 0,
        "metric_deltas": metric_deltas,
        "baseline_mean_metrics": {
            "recall_at_5": 1.0,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 0.75,
            "negative_accepted_rate": 0.75,
            "selection_rate_at_5": 1.0,
        },
        "candidate_mean_metrics": {
            "recall_at_5": 1.0,
            "mrr": 0.96875,
            "ndcg_at_5": 0.976933,
            "negative_hit_rate": 0.8125,
            "negative_accepted_rate": 0.8125,
            "selection_rate_at_5": 1.0,
        },
        "input_paths": {
            "baseline_results": "docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl",
            "candidate_results": "docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl",
            "task_root": "benchmarks/blind-migration-tasks",
        },
    }


def _diff(task_id: str, *, regression_flags: list[str]) -> dict:
    return {
        "task_id": task_id,
        "before_selected_skill_ids": ["gold"],
        "after_selected_skill_ids": ["gold", "negative"],
        "gold_skills": ["gold"],
        "negative_skills": ["negative"],
        "before_metrics": {
            "recall_at_5": 1.0,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 0.0,
            "negative_accepted_rate": 0.0,
            "selection_rate_at_5": 1.0,
        },
        "after_metrics": {
            "recall_at_5": 1.0,
            "mrr": 1.0,
            "ndcg_at_5": 1.0,
            "negative_hit_rate": 1.0,
            "negative_accepted_rate": 1.0,
            "selection_rate_at_5": 1.0,
        },
        "metric_deltas": {
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "negative_hit_rate": 1.0,
            "negative_accepted_rate": 1.0,
            "selection_rate_at_5": 0.0,
        },
        "selection_changed": True,
        "regression_flags": regression_flags,
        "improvement_flags": [],
        "applied_candidate_ids": [],
    }


def test_select_release_router_keeps_baseline_for_phase16_regression() -> None:
    decision = select_release_router(
        summary=_summary(),
        route_diffs=[
            _diff("task-a", regression_flags=["negative_hit_rate_increased"]),
            _diff("task-b", regression_flags=["mrr_decreased"]),
        ],
    )

    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["selected_router"] == "baseline-minilm"
    assert decision["candidate_router"] == "finetuned-embedding"
    assert decision["approved_for_default"] is False
    assert decision["policy"] == DEFAULT_RELEASE_POLICY
    assert "regression_count exceeds policy" in decision["reasons"]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_release_selector.py::test_select_release_router_keeps_baseline_for_phase16_regression -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hermes_skilleval.release_selector'`.

- [ ] **Step 3: Add approval, review-required, and artifact-write tests**

Append to `tests/test_release_selector.py`:

```python
def test_select_release_router_approves_candidate_when_policy_passes() -> None:
    decision = select_release_router(
        summary=_summary(
            guard_status="PASS",
            regression_count=0,
            deltas={
                "recall_at_5": 0.0,
                "mrr": 0.05,
                "ndcg_at_5": 0.02,
                "negative_hit_rate": -0.25,
                "negative_accepted_rate": -0.25,
            },
        ),
        route_diffs=[
            _diff("task-a", regression_flags=[]),
            _diff("task-b", regression_flags=[]),
        ],
    )

    assert decision["decision"] == "APPROVE_CANDIDATE"
    assert decision["selected_router"] == "finetuned-embedding"
    assert decision["approved_for_default"] is True
    assert decision["reasons"] == ["candidate satisfies release policy"]


def test_select_release_router_reports_review_required_for_mismatched_diffs() -> None:
    decision = select_release_router(
        summary=_summary(regression_count=0),
        route_diffs=[_diff("unexpected-task", regression_flags=[])],
    )

    assert decision["decision"] == "REVIEW_REQUIRED"
    assert decision["selected_router"] is None
    assert decision["approved_for_default"] is False
    assert any("task ids differ" in reason for reason in decision["reasons"])


def test_write_release_decision_writes_json_markdown_and_task_decisions(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "regression-summary.json"
    diffs_path = tmp_path / "route-diffs.jsonl"
    output_dir = tmp_path / "phase17"
    summary_path.write_text(json.dumps(_summary(), sort_keys=True) + "\n", encoding="utf-8")
    diffs_path.write_text(
        "\n".join(
            [
                json.dumps(_diff("task-a", regression_flags=["negative_hit_rate_increased"]), sort_keys=True),
                json.dumps(_diff("task-b", regression_flags=["mrr_decreased"]), sort_keys=True),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    decision = write_release_decision(
        regression_summary_path=summary_path,
        route_diffs_path=diffs_path,
        output_dir=output_dir,
    )

    assert decision["decision"] == "KEEP_BASELINE"
    assert (output_dir / "release-decision.json").is_file()
    assert (output_dir / "release-decision.md").is_file()
    assert (output_dir / "task-decisions.jsonl").is_file()
    markdown = (output_dir / "release-decision.md").read_text(encoding="utf-8")
    assert "# Phase 17 Calibrated Release Selector" in markdown
    assert "Selected router: `baseline-minilm`" in markdown
    task_lines = (output_dir / "task-decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(task_lines) == 2
```

- [ ] **Step 4: Run the full release selector unit test file**

Run:

```bash
pytest tests/test_release_selector.py -q
```

Expected: FAIL because `release_selector.py` does not exist yet.

- [ ] **Step 5: Commit tests after they fail for the expected reason**

Do not commit if the failure is unrelated to the missing implementation.

```bash
git add tests/test_release_selector.py
git commit -m "test: cover phase17 release selector decisions"
```

---

## Task 2: Release Selector Implementation

**Files:**

- Create: `src/hermes_skilleval/release_selector.py`
- Test: `tests/test_release_selector.py`

- [ ] **Step 1: Implement `release_selector.py`**

Create `src/hermes_skilleval/release_selector.py`:

```python
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


APPROVE_CANDIDATE = "APPROVE_CANDIDATE"
KEEP_BASELINE = "KEEP_BASELINE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

DEFAULT_RELEASE_POLICY: dict[str, float | int] = {
    "max_regressions": 0,
    "max_negative_hit_delta": 0.0,
    "max_negative_accepted_delta": 0.0,
    "min_recall_at_5_delta": 0.0,
    "min_mrr_delta": 0.0,
    "min_ndcg_at_5_delta": 0.0,
}


def write_release_decision(
    *,
    regression_summary_path: Path | str,
    route_diffs_path: Path | str,
    output_dir: Path | str,
    policy: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    summary = _read_json(regression_summary_path)
    route_diffs = _read_jsonl(route_diffs_path)
    decision = select_release_router(
        summary=summary,
        route_diffs=route_diffs,
        policy=policy,
    )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "release-decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "release-decision.md").write_text(
        _render_markdown(decision),
        encoding="utf-8",
    )
    _write_jsonl(output / "task-decisions.jsonl", decision["task_decisions"])
    return decision


def select_release_router(
    *,
    summary: dict[str, Any],
    route_diffs: list[dict[str, Any]],
    policy: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    release_policy = _normalize_policy(policy)
    validation_reasons = _validation_reasons(summary, route_diffs)
    baseline_router = summary.get("baseline_router")
    candidate_router = summary.get("candidate_router")
    task_decisions = _task_decisions(route_diffs)
    flag_counts = Counter(
        flag
        for diff in route_diffs
        for flag in diff.get("regression_flags", [])
    )

    if validation_reasons:
        decision = REVIEW_REQUIRED
        selected_router = None
        approved = False
        reasons = validation_reasons
    else:
        budget_reasons = _budget_reasons(summary, release_policy)
        if budget_reasons:
            decision = KEEP_BASELINE
            selected_router = baseline_router
            approved = False
            reasons = budget_reasons
        else:
            decision = APPROVE_CANDIDATE
            selected_router = candidate_router
            approved = True
            reasons = ["candidate satisfies release policy"]

    return {
        "phase": "Phase 17",
        "artifact_type": "phase17-calibrated-release-selector",
        "source_phase": summary.get("phase"),
        "source_guard_status": summary.get("guard_status"),
        "decision": decision,
        "selected_router": selected_router,
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "approved_for_default": approved,
        "policy": release_policy,
        "reasons": reasons,
        "task_count": summary.get("task_count"),
        "regression_count": summary.get("regression_count"),
        "improvement_count": summary.get("improvement_count"),
        "metric_deltas": summary.get("metric_deltas", {}),
        "regression_flag_counts": dict(sorted(flag_counts.items())),
        "task_decisions": task_decisions,
        "input_paths": summary.get("input_paths", {}),
    }
```

- [ ] **Step 2: Add helper functions in the same file**

Append below the public functions:

```python
def _normalize_policy(
    policy: dict[str, float | int] | None,
) -> dict[str, float | int]:
    merged = dict(DEFAULT_RELEASE_POLICY)
    if policy:
        for key, value in policy.items():
            if key not in merged:
                raise ValueError(f"unknown release policy field: {key}")
            merged[key] = value
    return merged


def _read_json(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"no route diffs found in {path}")
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _validation_reasons(
    summary: dict[str, Any],
    route_diffs: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    required = (
        "artifact_type",
        "baseline_router",
        "candidate_router",
        "task_count",
        "blind_task_ids",
        "metric_deltas",
        "regression_count",
    )
    for field in required:
        if field not in summary:
            reasons.append(f"missing summary field: {field}")
    if summary.get("artifact_type") != "phase16-blind-validation":
        reasons.append("summary artifact_type must be phase16-blind-validation")
    expected_task_ids = {str(task_id) for task_id in summary.get("blind_task_ids", [])}
    actual_task_ids = {str(diff.get("task_id")) for diff in route_diffs}
    if expected_task_ids and actual_task_ids != expected_task_ids:
        reasons.append("task ids differ between regression summary and route diffs")
    if not route_diffs:
        reasons.append("route diffs are empty")
    return reasons


def _budget_reasons(
    summary: dict[str, Any],
    policy: dict[str, float | int],
) -> list[str]:
    reasons: list[str] = []
    deltas = summary.get("metric_deltas", {})
    regression_count = int(summary.get("regression_count", 0))
    if regression_count > int(policy["max_regressions"]):
        reasons.append("regression_count exceeds policy")
    if float(deltas.get("negative_hit_rate", 0.0)) > float(policy["max_negative_hit_delta"]):
        reasons.append("negative_hit_rate delta exceeds policy")
    if float(deltas.get("negative_accepted_rate", 0.0)) > float(policy["max_negative_accepted_delta"]):
        reasons.append("negative_accepted_rate delta exceeds policy")
    if float(deltas.get("recall_at_5", 0.0)) < float(policy["min_recall_at_5_delta"]):
        reasons.append("recall_at_5 delta below policy")
    if float(deltas.get("mrr", 0.0)) < float(policy["min_mrr_delta"]):
        reasons.append("mrr delta below policy")
    if float(deltas.get("ndcg_at_5", 0.0)) < float(policy["min_ndcg_at_5_delta"]):
        reasons.append("ndcg_at_5 delta below policy")
    return reasons


def _task_decisions(route_diffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = []
    for diff in sorted(route_diffs, key=lambda record: str(record.get("task_id"))):
        regression_flags = list(diff.get("regression_flags", []))
        improvement_flags = list(diff.get("improvement_flags", []))
        if regression_flags:
            status = KEEP_BASELINE
        elif improvement_flags:
            status = APPROVE_CANDIDATE
        else:
            status = "NO_CHANGE"
        decisions.append(
            {
                "task_id": diff.get("task_id"),
                "decision": status,
                "regression_flags": regression_flags,
                "improvement_flags": improvement_flags,
                "metric_deltas": diff.get("metric_deltas", {}),
            }
        )
    return decisions


def _render_markdown(decision: dict[str, Any]) -> str:
    selected = decision["selected_router"]
    selected_text = "`None`" if selected is None else f"`{selected}`"
    lines = [
        "# Phase 17 Calibrated Release Selector",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Selected router: {selected_text}",
        f"- Baseline router: `{decision['baseline_router']}`",
        f"- Candidate router: `{decision['candidate_router']}`",
        f"- Approved for default: `{decision['approved_for_default']}`",
        f"- Source guard status: `{decision['source_guard_status']}`",
        f"- Task count: {decision['task_count']}",
        "",
        "## Reasons",
        "",
    ]
    for reason in decision["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Metric Deltas",
            "",
            "| Metric | Delta |",
            "|---|---:|",
        ]
    )
    for metric, delta in sorted(decision["metric_deltas"].items()):
        lines.append(f"| {metric} | {float(delta):+.6f} |")
    lines.extend(["", "## Regression Flags", ""])
    if decision["regression_flag_counts"]:
        lines.extend(["| Flag | Count |", "|---|---:|"])
        for flag, count in decision["regression_flag_counts"].items():
            lines.append(f"| {flag} | {count} |")
    else:
        lines.append("No regression flags were observed.")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 3: Run release selector unit tests**

Run:

```bash
pytest tests/test_release_selector.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit implementation**

```bash
git add src/hermes_skilleval/release_selector.py tests/test_release_selector.py
git commit -m "feat: add phase17 release selector"
```

---

## Task 3: CLI Command

**Files:**

- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Add failing CLI smoke test**

Add this test near the Phase 16 CLI tests in `tests/test_cli_smoke.py`:

```python
def test_cli_select_release_router_writes_decision_artifacts(tmp_path):
    summary = {
        "phase": "Phase 16",
        "artifact_type": "phase16-blind-validation",
        "task_count": 1,
        "blind_task_ids": ["blind-task"],
        "guard_status": "REVIEW_REQUIRED",
        "baseline_router": "baseline-minilm",
        "candidate_router": "finetuned-embedding",
        "regression_count": 1,
        "improvement_count": 0,
        "metric_deltas": {
            "recall_at_5": 0.0,
            "mrr": -0.1,
            "ndcg_at_5": -0.1,
            "negative_hit_rate": 1.0,
            "negative_accepted_rate": 1.0,
            "selection_rate_at_5": 0.0,
        },
        "baseline_mean_metrics": {},
        "candidate_mean_metrics": {},
        "input_paths": {},
    }
    diff = {
        "task_id": "blind-task",
        "regression_flags": ["negative_hit_rate_increased"],
        "improvement_flags": [],
        "metric_deltas": {"negative_hit_rate": 1.0},
    }
    summary_path = tmp_path / "regression-summary.json"
    diffs_path = tmp_path / "route-diffs.jsonl"
    output_dir = tmp_path / "phase17"
    summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    diffs_path.write_text(json.dumps(diff, sort_keys=True) + "\n", encoding="utf-8")

    result = main(
        [
            "select-release-router",
            "--regression-summary",
            str(summary_path),
            "--route-diffs",
            str(diffs_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    decision = json.loads((output_dir / "release-decision.json").read_text())
    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["selected_router"] == "baseline-minilm"
```

- [ ] **Step 2: Run the failing CLI test**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_select_release_router_writes_decision_artifacts -q
```

Expected: FAIL because the command is not registered.

- [ ] **Step 3: Wire parser and handler**

Modify imports at the top of `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.release_selector import write_release_decision
```

Add parser after `write-blind-validation` and before `verify-release`:

```python
    release_selector_parser = subparsers.add_parser(
        "select-release-router",
        help="write a Phase 17 default-router release decision from blind-validation artifacts",
    )
    release_selector_parser.add_argument("--regression-summary", required=True)
    release_selector_parser.add_argument("--route-diffs", required=True)
    release_selector_parser.add_argument("--output-dir", required=True)
    release_selector_parser.add_argument("--max-regressions", type=int, default=0)
    release_selector_parser.add_argument("--max-negative-hit-delta", type=float, default=0.0)
    release_selector_parser.add_argument("--max-negative-accepted-delta", type=float, default=0.0)
    release_selector_parser.add_argument("--min-recall-at-5-delta", type=float, default=0.0)
    release_selector_parser.add_argument("--min-mrr-delta", type=float, default=0.0)
    release_selector_parser.add_argument("--min-ndcg-at-5-delta", type=float, default=0.0)
    release_selector_parser.set_defaults(handler=_run_select_release_router)
```

Add handler near `_run_write_blind_validation`:

```python
def _run_select_release_router(args: argparse.Namespace) -> None:
    decision = write_release_decision(
        regression_summary_path=args.regression_summary,
        route_diffs_path=args.route_diffs,
        output_dir=args.output_dir,
        policy={
            "max_regressions": args.max_regressions,
            "max_negative_hit_delta": args.max_negative_hit_delta,
            "max_negative_accepted_delta": args.max_negative_accepted_delta,
            "min_recall_at_5_delta": args.min_recall_at_5_delta,
            "min_mrr_delta": args.min_mrr_delta,
            "min_ndcg_at_5_delta": args.min_ndcg_at_5_delta,
        },
    )
    print(
        "Wrote Phase 17 release decision to "
        f"{args.output_dir}: decision={decision['decision']}, "
        f"selected={decision['selected_router']}"
    )
```

- [ ] **Step 4: Run targeted CLI and selector tests**

Run:

```bash
pytest tests/test_release_selector.py tests/test_cli_smoke.py::test_cli_select_release_router_writes_decision_artifacts -q
```

Expected: PASS.

- [ ] **Step 5: Commit CLI command**

```bash
git add src/hermes_skilleval/cli.py tests/test_cli_smoke.py
git commit -m "feat: expose phase17 release selector cli"
```

---

## Task 4: Generate Phase 17 Artifacts

**Files:**

- Create directory: `docs/demo/phase17-calibrated-release-selector/`
- Generated:
  - `docs/demo/phase17-calibrated-release-selector/release-decision.json`
  - `docs/demo/phase17-calibrated-release-selector/release-decision.md`
  - `docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl`
  - `docs/demo/phase17-calibrated-release-selector/release-check-summary.json`

- [ ] **Step 1: Generate release decision artifacts**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli select-release-router \
  --regression-summary docs/demo/phase16-blind-validation/regression-summary.json \
  --route-diffs docs/demo/phase16-blind-validation/route-diffs.jsonl \
  --output-dir docs/demo/phase17-calibrated-release-selector
```

Expected:

```text
Wrote Phase 17 release decision to docs/demo/phase17-calibrated-release-selector: decision=KEEP_BASELINE, selected=baseline-minilm
```

- [ ] **Step 2: Verify generated JSON decision**

Run:

```bash
jq '{phase, artifact_type, decision, selected_router, approved_for_default, regression_count}' \
  docs/demo/phase17-calibrated-release-selector/release-decision.json
```

Expected:

```json
{
  "phase": "Phase 17",
  "artifact_type": "phase17-calibrated-release-selector",
  "decision": "KEEP_BASELINE",
  "selected_router": "baseline-minilm",
  "approved_for_default": false,
  "regression_count": 2
}
```

- [ ] **Step 3: Run release check including Phase 17 paths**

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
  --public-root docs/demo/phase17-calibrated-release-selector \
  --public-root benchmarks/blind-migration-tasks \
  --required-path docs/demo/phase16-blind-validation/regression-summary.json \
  --required-path docs/demo/phase17-calibrated-release-selector/release-decision.json \
  --required-path docs/demo/phase17-calibrated-release-selector/release-decision.md \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase17-calibrated-release-selector/release-check-summary.json
```

Expected:

```text
Release check PASS: docs/demo/phase17-calibrated-release-selector/release-check-summary.json
```

- [ ] **Step 4: Commit generated Phase 17 artifacts**

```bash
git add docs/demo/phase17-calibrated-release-selector
git commit -m "docs: add phase17 release selector artifacts"
```

---

## Task 5: Artifact Guard Tests

**Files:**

- Create: `tests/test_phase17_artifacts.py`

- [ ] **Step 1: Add artifact guard tests**

Create `tests/test_phase17_artifacts.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("docs/demo/phase17-calibrated-release-selector")


def test_phase17_release_decision_artifacts_exist() -> None:
    assert (ROOT / "release-decision.json").is_file()
    assert (ROOT / "release-decision.md").is_file()
    assert (ROOT / "task-decisions.jsonl").is_file()
    assert (ROOT / "release-check-summary.json").is_file()


def test_phase17_release_decision_keeps_baseline_for_current_blind_pack() -> None:
    decision = json.loads((ROOT / "release-decision.json").read_text(encoding="utf-8"))

    assert decision["phase"] == "Phase 17"
    assert decision["artifact_type"] == "phase17-calibrated-release-selector"
    assert decision["source_phase"] == "Phase 16"
    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["selected_router"] == "baseline-minilm"
    assert decision["candidate_router"] == "finetuned-embedding"
    assert decision["approved_for_default"] is False
    assert decision["regression_count"] == 2
    assert "regression_count exceeds policy" in decision["reasons"]


def test_phase17_task_decisions_match_phase16_task_count() -> None:
    decision = json.loads((ROOT / "release-decision.json").read_text(encoding="utf-8"))
    task_decisions = [
        json.loads(line)
        for line in (ROOT / "task-decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(task_decisions) == decision["task_count"]
    assert any(record["decision"] == "KEEP_BASELINE" for record in task_decisions)


def test_phase17_markdown_documents_selected_router() -> None:
    markdown = (ROOT / "release-decision.md").read_text(encoding="utf-8")

    assert "# Phase 17 Calibrated Release Selector" in markdown
    assert "Decision: `KEEP_BASELINE`" in markdown
    assert "Selected router: `baseline-minilm`" in markdown
```

- [ ] **Step 2: Run artifact tests**

Run:

```bash
pytest tests/test_phase17_artifacts.py -q
```

Expected: PASS after artifacts are generated.

- [ ] **Step 3: Commit artifact guards**

```bash
git add tests/test_phase17_artifacts.py
git commit -m "test: guard phase17 release selector artifacts"
```

---

## Task 6: Docs And Public Surface

**Files:**

- Create: `docs/phase17.md`
- Modify: `docs/release-handoff.md`
- Modify: `README.md`
- Modify: `tests/test_phase17_artifacts.py`
- Modify: existing artifact tests if they pin README test count.

- [ ] **Step 1: Add docs guard test**

Append to `tests/test_phase17_artifacts.py`:

```python
def test_phase17_docs_and_readme_links() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    phase = Path("docs/phase17.md").read_text(encoding="utf-8")
    handoff = Path("docs/release-handoff.md").read_text(encoding="utf-8")

    assert "Phase 17" in readme
    assert "select-release-router" in readme
    assert "296" in readme
    assert "Calibrated release selector" in phase
    assert "KEEP_BASELINE" in phase
    assert "Phase 17" in handoff
```

- [ ] **Step 2: Run docs guard test and confirm it fails**

Run:

```bash
pytest tests/test_phase17_artifacts.py::test_phase17_docs_and_readme_links -q
```

Expected: FAIL because `docs/phase17.md` and README links are not added yet.

- [ ] **Step 3: Create `docs/phase17.md`**

Create `docs/phase17.md`:

```markdown
# Phase 17: Calibrated release selector

Phase 17 turns the Phase 16 blind-validation result into an explicit
default-router release decision. It does not retrain the model or change the
Phase 16 route results. Instead, it applies a conservative regression budget to
the committed blind-validation summary and route diffs.

## Scope

The selector reads:

- `docs/demo/phase16-blind-validation/regression-summary.json`
- `docs/demo/phase16-blind-validation/route-diffs.jsonl`

It writes:

- `docs/demo/phase17-calibrated-release-selector/release-decision.json`
- `docs/demo/phase17-calibrated-release-selector/release-decision.md`
- `docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl`
- `docs/demo/phase17-calibrated-release-selector/release-check-summary.json`

## Policy

The default policy allows no blind regressions and no positive negative-hit
delta. It also requires Recall@5, MRR, and NDCG@5 to avoid regression. This is
deliberately stricter than a model-selection leaderboard because the release
question is whether the candidate should become the default router.

## Result

The current Phase 17 decision is `KEEP_BASELINE`. The selected default router is
`baseline-minilm`, while `finetuned-embedding` remains a trained artifact with
provenance but is not approved as the default policy.

This result follows directly from Phase 16: the fine-tuned router preserved
Recall@5 but introduced two per-task regressions and increased negative-skill
selection on the blind task pack.

## Limitations

Phase 17 is a release decision layer over the current self-built Hermes-style
blind task pack. It does not establish SOTA, does not replace external
benchmarks, and does not prove production readiness.
```

- [ ] **Step 4: Update `docs/release-handoff.md`**

Add a Phase 17 row to the evidence table:

```markdown
| Phase 17 | Calibrated default-router release decision | `docs/phase17.md` |
```

Add reviewer entry points:

```markdown
- Phase 17 release decision: `docs/demo/phase17-calibrated-release-selector/release-decision.md`
- Phase 17 task decisions: `docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl`
```

Update current release reading:

```markdown
Phase 17 keeps `baseline-minilm` as the default router. This is intentionally
conservative: Phase 16 showed that the fine-tuned router preserved Recall@5 but
worsened blind negative-hit behavior, so Phase 17 records the rollback/default
decision instead of hiding the regression.
```

- [ ] **Step 5: Update `README.md`**

Make these precise edits:

- Change Benchmark Scale `Test cases` from the stale value to the actual final `python -m pytest -q` pass count after Phase 17 tests are added.
- Change Tech Stack `Testing` row from the stale value to the same actual final pass count.
- Change Project Summary engineering-quality bullet from the stale value to the same actual final pass count.
- Add Quick Start command section after Phase 16:

````markdown
### 14. Select the Default Release Router

```bash
skilleval select-release-router \
  --regression-summary docs/demo/phase16-blind-validation/regression-summary.json \
  --route-diffs docs/demo/phase16-blind-validation/route-diffs.jsonl \
  --output-dir docs/demo/phase17-calibrated-release-selector
```

Phase 17 applies a conservative release policy to the Phase 16 blind-validation
pack. The committed decision is `KEEP_BASELINE`: `baseline-minilm` remains the
default router because the fine-tuned router introduced blind regressions.
````

- Renumber later README sections if needed.
- Add experiment timeline row:

```markdown
| Phase 17 | Calibrated release selector | [`docs/phase17.md`](docs/phase17.md) |
```

- Add roadmap row:

```markdown
- [x] Calibrated default-router release selector
      ([docs](docs/phase17.md), [decision](docs/demo/phase17-calibrated-release-selector/release-decision.md))
```

- [ ] **Step 6: Run docs and artifact tests**

Run:

```bash
pytest tests/test_phase17_artifacts.py tests/test_project_surface.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit docs**

```bash
git add README.md docs/phase17.md docs/release-handoff.md tests/test_phase17_artifacts.py
git commit -m "docs: document phase17 release selector"
```

---

## Task 7: Final Validation

**Files:**

- No new files unless validation finds a real Phase 17 issue.

- [ ] **Step 1: Run targeted Phase 17 validation**

Run:

```bash
pytest tests/test_release_selector.py tests/test_phase17_artifacts.py tests/test_cli_smoke.py::test_cli_select_release_router_writes_decision_artifacts -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass. After the focused malformed-input regression tests, the expected full-suite count is `296 passed`.

- [ ] **Step 3: Run release gate with Phase 17 included**

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
  --public-root docs/phase17.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root docs/demo/phase17-calibrated-release-selector \
  --public-root benchmarks/blind-migration-tasks \
  --required-path docs/demo/phase16-blind-validation/regression-summary.json \
  --required-path docs/demo/phase17-calibrated-release-selector/release-decision.json \
  --required-path docs/demo/phase17-calibrated-release-selector/release-decision.md \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase17-calibrated-release-selector/release-check-summary.json
```

Expected:

```text
Release check PASS: docs/demo/phase17-calibrated-release-selector/release-check-summary.json
```

- [ ] **Step 4: Inspect git status and recent commits**

Run:

```bash
git status -sb
git --no-pager log --oneline -n 8
```

Expected: clean worktree on the Phase 17 branch after commits.

- [ ] **Step 5: Final report**

Report:

- changed files
- final decision from `release-decision.json`
- test command and pass count
- release check status
- any residual limitations

---

## Success Criteria

- `skilleval select-release-router` exists and writes `release-decision.json`, `release-decision.md`, and `task-decisions.jsonl`.
- Current Phase 16 artifacts produce `decision == "KEEP_BASELINE"` and `selected_router == "baseline-minilm"`.
- Phase 17 docs clearly state that the fine-tuned router is not approved as the default router.
- README test count is refreshed from `274` to the actual post-Phase17 count.
- `verify-release` still passes when Phase 17 docs/artifacts are included.
- Full `python -m pytest -q` passes.

## Self-Review

- Spec coverage: The plan covers module implementation, CLI, generated artifacts, docs, artifact guards, and final validation.
- Placeholder scan: No unresolved placeholder markers are intentionally left.
- Type consistency: Public functions use `Path | str` for file inputs, `dict[str, Any]` for artifacts, and the same decision strings across tests, CLI, docs, and artifacts.
- Scope check: The plan is focused on release selection only; retraining, new blind-task generation, and dashboard redesign are intentionally excluded.
