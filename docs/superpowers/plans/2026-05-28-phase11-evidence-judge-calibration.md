# Phase 11 Evidence Judge Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable evidence judge for Phase 10 agent-loop traces so SkillEval can score whether an agent-style run satisfied task evidence, not only whether the router selected a gold skill.

**Architecture:** Add a focused `agent_judge.py` module that consumes Phase 10 `agent-traces.jsonl` and writes deterministic judge outputs. The CLI exposes `skilleval judge-agent-loop`; committed Phase 11 artifacts compare the three Phase 10 conditions under the same rubric and the dashboard can summarize optional judge metrics.

**Tech Stack:** Python 3.11 standard library, existing JSONL/report/dashboard helpers, pytest, committed Phase 10 artifacts.

---

## Scope

Phase 11 is intentionally an offline evaluation layer. It does not require API keys, real browser execution, or live LLM calls. The default backend is `deterministic-rubric`; an optional `llm-prompt-export` mode may write review prompts for later human/LLM inspection, but CI and committed artifacts must be reproducible without network access.

## File Structure

- Create `src/hermes_skilleval/agent_judge.py`: load traces, validate schema, apply deterministic evidence rubric, write `judge-results.jsonl`, dashboard-compatible `results.jsonl`, `judge-summary.json`, and `judge-rubric.md`.
- Modify `src/hermes_skilleval/cli.py`: add `judge-agent-loop` parser and handler.
- Modify `src/hermes_skilleval/dashboard.py`: include optional judge metrics (`judge_score`, `evidence_score`, `judge_pass_rate`) in run summaries when records contain them.
- Create `tests/test_agent_judge.py`: unit tests for scoring, schema validation, prompt preservation, and control-condition outcomes.
- Modify `tests/test_cli_smoke.py`: add a `judge-agent-loop` smoke test.
- Modify `tests/test_dashboard.py`: cover optional judge metric summarization.
- Create `tests/test_phase11_artifacts.py`: pin committed Phase 11 artifact contract and README/docs links.
- Create `docs/phase11.md`: explain rubric, limitations, commands, and current results.
- Create `docs/demo/phase11-evidence-judge-calibration/`: generated judge artifacts and dashboard.
- Modify `README.md`: add Phase 11 to timeline, usage, Roadmap, and verified test count.

## Task 1: Deterministic Evidence Judge Core

**Files:**
- Create: `src/hermes_skilleval/agent_judge.py`
- Create: `tests/test_agent_judge.py`

- [ ] **Step 1: Write failing judge-core tests**

Create `tests/test_agent_judge.py` with tests for one passed trace and one failed trace:

```python
import json
from pathlib import Path

import pytest

from hermes_skilleval.agent_judge import judge_agent_loop


def test_judge_agent_loop_scores_trace_evidence_and_writes_artifacts(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "trace_schema_version": "phase10.agent-loop.v1",
                "trace_id": "agent-loop-hybrid:task-001",
                "task_id": "task-001",
                "prompt": "Fix the regression and include evidence.",
                "execution_condition": "routed-skill",
                "source_router": "hybrid",
                "selected_skill_ids": ["systematic-debugging"],
                "agent_status": "passed",
                "agent_success": True,
                "expected_evidence": ["failing test reproduced", "fix verified"],
                "evidence_checks": [
                    {"name": "failing test reproduced", "satisfied": True},
                    {"name": "fix verified", "satisfied": True},
                ],
                "failure_type": None,
                "failure_reason": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "judge"

    summary = judge_agent_loop(
        traces_path=traces,
        output_dir=output_dir,
        run_label="judge-agent-loop-hybrid",
    )

    judge_records = _read_jsonl(output_dir / "judge-results.jsonl")
    dashboard_records = _read_jsonl(output_dir / "results.jsonl")

    assert summary["judge_pass_rate"] == 1.0
    assert summary["mean_judge_score"] == 1.0
    assert judge_records[0]["judge_status"] == "passed"
    assert judge_records[0]["judge_score"] == 1.0
    assert judge_records[0]["evidence_score"] == 1.0
    assert judge_records[0]["prompt"] == "Fix the regression and include evidence."
    assert dashboard_records[0]["router"] == "judge-agent-loop-hybrid"
    assert dashboard_records[0]["judge_score"] == 1.0
    assert (output_dir / "judge-summary.json").exists()
    assert (output_dir / "judge-rubric.md").exists()


def test_judge_agent_loop_penalizes_missing_evidence_and_negative_failure(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "trace_schema_version": "phase10.agent-loop.v1",
                "trace_id": "agent-loop-hybrid:task-002",
                "task_id": "task-002",
                "prompt": "Route safely without choosing a negative skill.",
                "execution_condition": "routed-skill",
                "source_router": "hybrid",
                "selected_skill_ids": ["visual-regression-review"],
                "agent_status": "failed",
                "agent_success": False,
                "expected_evidence": ["safe skill selected", "final evidence noted"],
                "evidence_checks": [
                    {"name": "safe skill selected", "satisfied": False},
                    {"name": "final evidence noted", "satisfied": False},
                ],
                "failure_type": "negative_skill_selected",
                "failure_reason": "Selected a task negative skill.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = judge_agent_loop(
        traces_path=traces,
        output_dir=tmp_path / "judge",
        run_label="judge-agent-loop-hybrid",
    )

    record = _read_jsonl(tmp_path / "judge" / "judge-results.jsonl")[0]
    assert summary["judge_pass_rate"] == 0.0
    assert record["judge_status"] == "failed"
    assert record["evidence_score"] == 0.0
    assert record["penalties"] == ["missing-evidence", "negative-skill-failure"]


def test_judge_agent_loop_rejects_unknown_trace_schema(tmp_path: Path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps({"trace_schema_version": "wrong", "trace_id": "x", "task_id": "x"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported trace_schema_version"):
        judge_agent_loop(traces_path=traces, output_dir=tmp_path / "judge")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_agent_judge.py -q -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'hermes_skilleval.agent_judge'`.

- [ ] **Step 3: Implement minimal judge core**

Create `src/hermes_skilleval/agent_judge.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_TRACE_SCHEMA = "phase10.agent-loop.v1"
DEFAULT_JUDGE_SCHEMA = "phase11.evidence-judge.v1"


def judge_agent_loop(
    *,
    traces_path: Path | str,
    output_dir: Path | str,
    run_label: str = "judge-agent-loop",
    backend: str = "deterministic-rubric",
) -> dict[str, object]:
    if backend != "deterministic-rubric":
        raise ValueError(f"unsupported judge backend: {backend}")
    traces = _read_jsonl(Path(traces_path))
    if not traces:
        raise ValueError(f"no trace records found in {traces_path}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    judge_records = [_judge_trace(trace, run_label, str(traces_path), backend) for trace in traces]
    dashboard_records = [_dashboard_record(record, run_label) for record in judge_records]

    _write_jsonl(output / "judge-results.jsonl", judge_records)
    _write_jsonl(output / "results.jsonl", dashboard_records)
    summary = _summary(judge_records, run_label, backend)
    (output / "judge-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "judge-rubric.md").write_text(_rubric_markdown(), encoding="utf-8")
    return summary


def _judge_trace(
    trace: dict[str, object],
    run_label: str,
    traces_path: str,
    backend: str,
) -> dict[str, object]:
    if trace.get("trace_schema_version") != SUPPORTED_TRACE_SCHEMA:
        raise ValueError(
            f"unsupported trace_schema_version: {trace.get('trace_schema_version')}"
        )
    expected = _string_list(trace.get("expected_evidence", []), "expected_evidence")
    checks = trace.get("evidence_checks", [])
    if not isinstance(checks, list):
        raise ValueError("evidence_checks must be a list")
    satisfied = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("satisfied") is True
    ]
    evidence_score = len(satisfied) / len(expected) if expected else 0.0
    penalties: list[str] = []
    if evidence_score < 1.0:
        penalties.append("missing-evidence")
    if trace.get("failure_type") == "negative_skill_selected":
        penalties.append("negative-skill-failure")
    if trace.get("agent_success") is not True:
        penalties.append("agent-loop-failed")
    judge_score = max(0.0, evidence_score - 0.25 * len(set(penalties)))
    judge_status = "passed" if judge_score >= 0.75 and not penalties else "failed"

    return {
        "judge_schema_version": DEFAULT_JUDGE_SCHEMA,
        "trace_schema_version": trace["trace_schema_version"],
        "trace_id": _required_string(trace.get("trace_id"), "trace_id"),
        "task_id": _required_string(trace.get("task_id"), "task_id"),
        "prompt": _required_string(trace.get("prompt"), "prompt"),
        "router": run_label,
        "execution_condition": trace.get("execution_condition", ""),
        "source_router": trace.get("source_router", ""),
        "source_traces_path": traces_path,
        "judge_backend": backend,
        "selected_skill_ids": _string_list(trace.get("selected_skill_ids", []), "selected_skill_ids"),
        "expected_evidence": expected,
        "evidence_score": round(evidence_score, 3),
        "judge_score": round(judge_score, 3),
        "judge_status": judge_status,
        "judge_pass": judge_status == "passed",
        "penalties": penalties,
        "failure_type": trace.get("failure_type"),
        "failure_reason": trace.get("failure_reason"),
    }


def _dashboard_record(record: dict[str, object], run_label: str) -> dict[str, object]:
    judge_pass = record["judge_pass"] is True
    selected = _string_list(record.get("selected_skill_ids", []), "selected_skill_ids")
    return {
        "task_id": record["task_id"],
        "router": run_label,
        "split": "test",
        "category": "agent-loop-judge",
        "difficulty": "",
        "prompt": record["prompt"],
        "selected_skill_ids": selected,
        "gold_skills": selected if judge_pass else [],
        "negative_skills": [],
        "latency_ms": 0.0,
        "recall_at_5": 1.0 if judge_pass else 0.0,
        "mrr": 1.0 if judge_pass else 0.0,
        "ndcg_at_5": 1.0 if judge_pass else 0.0,
        "negative_hit_rate": 0.0,
        "abstention_rate": 0.0 if selected else 1.0,
        "selection_rate_at_5": min(len(selected), 5) / 5,
        "judge_score": record["judge_score"],
        "evidence_score": record["evidence_score"],
        "judge_pass_rate": 1.0 if judge_pass else 0.0,
        "judge_status": record["judge_status"],
        "execution_condition": record["execution_condition"],
        "penalties": record["penalties"],
    }
```

Add these helpers in the same module:

```python
def _summary(
    records: list[dict[str, object]],
    run_label: str,
    backend: str,
) -> dict[str, object]:
    task_count = len(records)
    pass_count = sum(1 for record in records if record["judge_pass"] is True)
    judge_scores = [float(record["judge_score"]) for record in records]
    evidence_scores = [float(record["evidence_score"]) for record in records]
    conditions = sorted(
        {
            str(record["execution_condition"])
            for record in records
            if str(record.get("execution_condition", "")).strip()
        }
    )
    return {
        "artifact_type": "phase11-evidence-judge-summary",
        "phase": "Phase 11",
        "run_label": run_label,
        "judge_backend": backend,
        "execution_condition": conditions[0] if len(conditions) == 1 else "mixed",
        "task_count": task_count,
        "judge_pass_count": pass_count,
        "judge_pass_rate": round(pass_count / task_count, 3) if task_count else 0.0,
        "mean_judge_score": round(sum(judge_scores) / task_count, 3)
        if task_count
        else 0.0,
        "mean_evidence_score": round(sum(evidence_scores) / task_count, 3)
        if task_count
        else 0.0,
    }


def _rubric_markdown() -> str:
    return "\n".join(
        [
            "# Phase 11 Evidence Judge Rubric",
            "",
            "- Evidence score is satisfied evidence checks divided by expected evidence count.",
            "- Missing evidence adds `missing-evidence`.",
            "- Negative skill failures add `negative-skill-failure`.",
            "- Failed agent loops add `agent-loop-failed`.",
            "- A record passes when `judge_score >= 0.75` and no penalties remain.",
            "",
        ]
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"expected object in {path} at line {line_number}")
        records.append(record)
    return records


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return list(value)
```

- [ ] **Step 4: Run judge-core tests to verify GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_agent_judge.py -q -p no:cacheprovider
```

Expected: `3 passed`.

## Task 2: CLI Command

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Add failing CLI smoke test**

Append to `tests/test_cli_smoke.py`:

```python
def test_cli_judge_agent_loop_writes_judge_artifacts(tmp_path):
    traces = tmp_path / "agent-traces.jsonl"
    traces.write_text(
        json.dumps(
            {
                "trace_schema_version": "phase10.agent-loop.v1",
                "trace_id": "agent-loop-hybrid:task-001",
                "task_id": "task-001",
                "prompt": "Verify the final evidence.",
                "execution_condition": "routed-skill",
                "source_router": "hybrid",
                "selected_skill_ids": ["verification-before-completion"],
                "agent_status": "passed",
                "agent_success": True,
                "expected_evidence": ["test command shown"],
                "evidence_checks": [{"name": "test command shown", "satisfied": True}],
                "failure_type": None,
                "failure_reason": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "judge"

    result = main(
        [
            "judge-agent-loop",
            "--traces",
            str(traces),
            "--output-dir",
            str(output_dir),
            "--run-label",
            "judge-agent-loop-hybrid",
        ]
    )

    assert result == 0
    assert (output_dir / "judge-results.jsonl").exists()
    assert (output_dir / "results.jsonl").exists()
    assert (output_dir / "judge-summary.json").exists()
    assert (output_dir / "judge-rubric.md").exists()
```

- [ ] **Step 2: Run CLI smoke test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_judge_agent_loop_writes_judge_artifacts -q -p no:cacheprovider
```

Expected: fail because `judge-agent-loop` is not registered.

- [ ] **Step 3: Wire parser and handler**

Modify `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.agent_judge import judge_agent_loop
```

Add parser near `run-agent-loop`:

```python
judge_loop_parser = subparsers.add_parser(
    "judge-agent-loop",
    help="judge Phase 10 agent-loop traces with a deterministic evidence rubric",
)
judge_loop_parser.add_argument("--traces", required=True)
judge_loop_parser.add_argument("--output-dir", required=True)
judge_loop_parser.add_argument("--run-label", default="judge-agent-loop")
judge_loop_parser.add_argument(
    "--backend",
    choices=("deterministic-rubric",),
    default="deterministic-rubric",
)
judge_loop_parser.set_defaults(handler=_run_judge_agent_loop)
```

Add handler:

```python
def _run_judge_agent_loop(args: argparse.Namespace) -> None:
    summary = judge_agent_loop(
        traces_path=args.traces,
        output_dir=args.output_dir,
        run_label=args.run_label,
        backend=args.backend,
    )
    print(
        "Wrote agent-loop judge artifacts to "
        f"{args.output_dir}: {summary['judge_pass_count']}/"
        f"{summary['task_count']} passed"
    )
```

- [ ] **Step 4: Run CLI smoke test to verify GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_judge_agent_loop_writes_judge_artifacts -q -p no:cacheprovider
```

Expected: `1 passed`.

## Task 3: Dashboard Judge Metrics

**Files:**
- Modify: `src/hermes_skilleval/dashboard.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing dashboard metric test**

Add to `tests/test_dashboard.py`:

```python
def test_dashboard_payload_summarizes_optional_judge_metrics(tmp_path: Path):
    _write_run(
        tmp_path,
        "judge-agent-loop-hybrid",
        [
            {
                "task_id": "task-001",
                "router": "judge-agent-loop-hybrid",
                "selected_skill_ids": ["verification-before-completion"],
                "gold_skills": ["verification-before-completion"],
                "negative_skills": [],
                "latency_ms": 0.0,
                "judge_score": 1.0,
                "evidence_score": 1.0,
                "judge_pass_rate": 1.0,
            },
            {
                "task_id": "task-002",
                "router": "judge-agent-loop-hybrid",
                "selected_skill_ids": ["visual-regression-review"],
                "gold_skills": [],
                "negative_skills": [],
                "latency_ms": 0.0,
                "judge_score": 0.25,
                "evidence_score": 0.5,
                "judge_pass_rate": 0.0,
            },
        ],
    )

    payload = build_dashboard_payload(tmp_path)
    metrics = payload.to_json_dict()["runs"][0]["metrics"]

    assert metrics["judge_score"] == 0.625
    assert metrics["evidence_score"] == 0.75
    assert metrics["judge_pass_rate"] == 0.5
```

- [ ] **Step 2: Run dashboard test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_dashboard.py::test_dashboard_payload_summarizes_optional_judge_metrics -q -p no:cacheprovider
```

Expected: fail because the metrics are not included in run summaries.

- [ ] **Step 3: Extend dashboard summary fields**

Modify `src/hermes_skilleval/dashboard.py`:

```python
OPTIONAL_SUMMARY_FIELDS = (
    "judge_score",
    "evidence_score",
    "judge_pass_rate",
)
```

Update `_record_metrics` so it adds finite optional fields when present:

```python
metrics = {
    "recall_at_5": _metric_or(
        record, "recall_at_5", recall_at_k(selected, gold, 5), path, line_number
    ),
    "mrr": _metric_or(
        record, "mrr", mean_reciprocal_rank(selected, gold), path, line_number
    ),
    "ndcg_at_5": _metric_or(
        record, "ndcg_at_5", ndcg_at_k(selected, gold, 5), path, line_number
    ),
    "negative_hit_rate": _metric_or(
        record,
        "negative_hit_rate",
        negative_hit_rate(selected, negative, 5),
        path,
        line_number,
    ),
    "abstention_rate": _metric_or(
        record, "abstention_rate", abstention_rate(selected), path, line_number
    ),
    "selection_rate_at_5": _metric_or(
        record,
        "selection_rate_at_5",
        selection_rate_at_k(selected, 5),
        path,
        line_number,
    ),
    "latency_ms": _metric_or(record, "latency_ms", 0.0, path, line_number),
}
for field in OPTIONAL_SUMMARY_FIELDS:
    if field in record:
        metrics[field] = _metric_or(record, field, 0.0, path, line_number)
return metrics
```

Update `_mean_summary_metrics` so it averages over the union of metric keys in the records:

```python
def _mean_summary_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    fields = sorted({field for row in rows for field in row})
    return {
        field: round(sum(row.get(field, 0.0) for row in rows) / len(rows), 6)
        for field in fields
    }
```

- [ ] **Step 4: Run dashboard tests to verify GREEN**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_dashboard.py::test_dashboard_payload_summarizes_optional_judge_metrics tests/test_dashboard.py -q -p no:cacheprovider
```

Expected: all dashboard tests pass.

## Task 4: Generate Phase 11 Artifacts

**Files:**
- Create: `docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-no-skill-hybrid/`
- Create: `docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-hybrid/`
- Create: `docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-oracle-skill-hybrid/`
- Create: `docs/demo/phase11-evidence-judge-calibration/comparison.md`
- Create: `docs/demo/phase11-evidence-judge-calibration/dashboard.html`
- Create: `docs/demo/phase11-evidence-judge-calibration/phase11-summary.json`

- [ ] **Step 1: Generate judge runs**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli judge-agent-loop \
  --traces docs/demo/phase10-agent-in-the-loop/agent-loop-no-skill-hybrid/agent-traces.jsonl \
  --output-dir docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-no-skill-hybrid \
  --run-label judge-agent-loop-no-skill-hybrid

PYTHONPATH=src python -m hermes_skilleval.cli judge-agent-loop \
  --traces docs/demo/phase10-agent-in-the-loop/agent-loop-hybrid/agent-traces.jsonl \
  --output-dir docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-hybrid \
  --run-label judge-agent-loop-hybrid

PYTHONPATH=src python -m hermes_skilleval.cli judge-agent-loop \
  --traces docs/demo/phase10-agent-in-the-loop/agent-loop-oracle-skill-hybrid/agent-traces.jsonl \
  --output-dir docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-oracle-skill-hybrid \
  --run-label judge-agent-loop-oracle-skill-hybrid
```

Expected: each directory has `judge-results.jsonl`, `results.jsonl`, `judge-summary.json`, and `judge-rubric.md`.

- [ ] **Step 2: Generate comparison and dashboard**

Run:

```bash
PYTHONPATH=src python - <<'PY'
import json
from pathlib import Path
from hermes_skilleval.comparison import write_comparison_report
from hermes_skilleval.dashboard import write_dashboard

root = Path("docs/demo/phase11-evidence-judge-calibration")
runs = {
    "judge-agent-loop-no-skill-hybrid": root / "judge-agent-loop-no-skill-hybrid" / "results.jsonl",
    "judge-agent-loop-hybrid": root / "judge-agent-loop-hybrid" / "results.jsonl",
    "judge-agent-loop-oracle-skill-hybrid": root / "judge-agent-loop-oracle-skill-hybrid" / "results.jsonl",
}
write_comparison_report(runs, root / "comparison.md")
write_dashboard(root, root / "dashboard.html")
summaries = {
    label: json.loads((root / label / "judge-summary.json").read_text(encoding="utf-8"))
    for label in runs
}
(root / "phase11-summary.json").write_text(
    json.dumps(
        {
            "artifact_type": "phase11-evidence-judge-summary",
            "phase": "Phase 11",
            "run_labels": sorted(runs),
            "backend": "deterministic-rubric",
            "runs": summaries,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
```

Expected: `comparison.md`, `dashboard.html`, and `phase11-summary.json` are written.

## Task 5: Artifact Contract Tests

**Files:**
- Create: `tests/test_phase11_artifacts.py`

- [ ] **Step 1: Write failing artifact tests**

Create `tests/test_phase11_artifacts.py`:

```python
import json
from pathlib import Path


PHASE11_ROOT = Path("docs/demo/phase11-evidence-judge-calibration")
README = Path("README.md")
PHASE11_DOC = Path("docs/phase11.md")

RUNS = {
    "judge-agent-loop-no-skill-hybrid": "no-skill",
    "judge-agent-loop-hybrid": "routed-skill",
    "judge-agent-loop-oracle-skill-hybrid": "oracle-skill",
}


def test_phase11_judge_artifacts_cover_three_conditions():
    for run_label, condition in RUNS.items():
        run_dir = PHASE11_ROOT / run_label
        judge_results = _read_jsonl(run_dir / "judge-results.jsonl")
        dashboard_results = _read_jsonl(run_dir / "results.jsonl")
        summary = json.loads((run_dir / "judge-summary.json").read_text())
        rubric = (run_dir / "judge-rubric.md").read_text(encoding="utf-8")

        assert len(judge_results) == 12
        assert len(dashboard_results) == 12
        assert summary["phase"] == "Phase 11"
        assert summary["judge_backend"] == "deterministic-rubric"
        assert summary["task_count"] == 12
        assert summary["execution_condition"] == condition
        assert rubric.startswith("# Phase 11 Evidence Judge Rubric")
        assert {record["execution_condition"] for record in judge_results} == {condition}
        assert all(record["prompt"] for record in judge_results)

    no_skill = json.loads(
        (PHASE11_ROOT / "judge-agent-loop-no-skill-hybrid" / "judge-summary.json")
        .read_text(encoding="utf-8")
    )
    routed = json.loads(
        (PHASE11_ROOT / "judge-agent-loop-hybrid" / "judge-summary.json")
        .read_text(encoding="utf-8")
    )
    oracle = json.loads(
        (PHASE11_ROOT / "judge-agent-loop-oracle-skill-hybrid" / "judge-summary.json")
        .read_text(encoding="utf-8")
    )

    assert no_skill["judge_pass_rate"] == 0.0
    assert routed["judge_pass_rate"] > no_skill["judge_pass_rate"]
    assert oracle["judge_pass_rate"] == 1.0


def test_phase11_dashboard_and_docs_are_committed():
    dashboard = (PHASE11_ROOT / "dashboard.html").read_text(encoding="utf-8")
    comparison = (PHASE11_ROOT / "comparison.md").read_text(encoding="utf-8")
    summary = json.loads((PHASE11_ROOT / "phase11-summary.json").read_text())
    readme = README.read_text(encoding="utf-8")
    phase11 = PHASE11_DOC.read_text(encoding="utf-8")

    assert "judge-agent-loop-hybrid" in dashboard
    assert "judge_score" in dashboard
    assert "Hermes SkillEval Router Comparison" in comparison
    assert summary["phase"] == "Phase 11"
    assert "| Phase 11 | Evidence judge calibration |" in readme
    assert "judge-agent-loop" in readme
    assert "deterministic-rubric" in phase11
    assert "does not require API keys" in phase11


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 2: Run artifact tests to verify RED before docs/artifacts exist**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase11_artifacts.py -q -p no:cacheprovider
```

Expected: fail on missing Phase 11 artifacts/docs.

- [ ] **Step 3: Rerun after Task 4 and Task 6**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase11_artifacts.py -q -p no:cacheprovider
```

Expected: `2 passed`.

## Task 6: Documentation and README

**Files:**
- Create: `docs/phase11.md`
- Modify: `README.md`

- [ ] **Step 1: Write Phase 11 docs**

Create `docs/phase11.md` with these sections:

```markdown
# Phase 11: Evidence Judge Calibration

Phase 11 judges Phase 10 agent-loop traces with an offline deterministic rubric.
It scores evidence satisfaction, applies explicit penalties, and writes
dashboard-compatible judge artifacts.

## Scope

The committed run uses `deterministic-rubric` and does not require API keys,
network access, real browser execution, or live LLM judging.

## Rubric

- Evidence score: satisfied evidence checks divided by expected evidence count.
- Penalties: missing evidence, negative skill failure, and failed agent loop.
- Judge pass: score at or above the pass threshold with no blocking penalties.

## Artifacts

Artifacts live under `docs/demo/phase11-evidence-judge-calibration/`.
Each run includes `judge-results.jsonl`, `results.jsonl`, `judge-summary.json`,
and `judge-rubric.md`.

## Reproduce

Use `skilleval judge-agent-loop` against any Phase 10 `agent-traces.jsonl`.
```

After artifact generation, include this result table using the exact values in
`phase11-summary.json`:

```markdown
| Condition | Run | Judge Pass Rate | Mean Judge Score | Mean Evidence Score |
|---|---|---:|---:|---:|
| `no-skill` | `judge-agent-loop-no-skill-hybrid` | 0.000 | 0.000 | 0.000 |
| `routed-skill` | `judge-agent-loop-hybrid` | 0.750 | 0.750 | 0.750 |
| `oracle-skill` | `judge-agent-loop-oracle-skill-hybrid` | 1.000 | 1.000 | 1.000 |
```

- [ ] **Step 2: Update README**

Update README:

- Add CLI usage section after Phase 10:
  `skilleval judge-agent-loop --traces docs/demo/phase10-agent-in-the-loop/agent-loop-hybrid/agent-traces.jsonl --output-dir runs/phase11-evidence-judge/hybrid`
- Add timeline row:
  `| Phase 11 | Evidence judge calibration | [docs/phase11.md](docs/phase11.md) |`
- Add Roadmap item:
  `- [x] Evidence judge calibration for agent-loop traces`
- Update test count after running the full suite.

## Task 7: Final Validation and Review

**Files:**
- All changed files.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest \
  tests/test_agent_judge.py \
  tests/test_phase11_artifacts.py \
  tests/test_cli_smoke.py::test_cli_judge_agent_loop_writes_judge_artifacts \
  tests/test_dashboard.py::test_dashboard_payload_summarizes_optional_judge_metrics \
  -q -p no:cacheprovider
```

Expected: all targeted Phase 11 tests pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
```

Expected: all tests pass. Update README with the exact passing count.

- [ ] **Step 3: Run whitespace and public artifact scans**

Run:

```bash
git diff --check
```

Expected: no output.

Run:

```bash
rg -n "115\\.190\\.60\\.96|\\b2222\\b|\\b18001\\b|BEGIN [A-Z ]*PRIVATE KEY|PRIVATE KEY|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|api[_-]?key\\s*[:=]|password\\s*[:=]|/root/code|/root/|/Users/raidriar" \
  docs/demo/phase11-evidence-judge-calibration docs/phase11.md README.md src/hermes_skilleval tests -S
```

Expected: no matches. `rg` exit code `1` means no matches.

- [ ] **Step 4: Request read-only Reviewer**

Ask a reviewer to inspect:

- `src/hermes_skilleval/agent_judge.py`
- `src/hermes_skilleval/cli.py`
- `src/hermes_skilleval/dashboard.py`
- `tests/test_agent_judge.py`
- `tests/test_phase11_artifacts.py`
- `docs/phase11.md`
- `docs/demo/phase11-evidence-judge-calibration/`

Reviewer output must include:

```text
Must Fix:
Should Fix:
Nice to Have:
Re-plan Needed: Yes/No
Final Verdict:
```

- [ ] **Step 5: Fix reviewer Must Fix items**

If `Re-plan Needed: No`, fix Must Fix items only, rerun targeted tests, full suite, `git diff --check`, and sensitive scan.

If `Re-plan Needed: Yes`, stop and re-plan before expanding scope.

## Self-Review Checklist

- Spec coverage: deterministic judge, CLI, artifacts, dashboard metrics, docs, and verification each have a task.
- Placeholder scan: no task uses unresolved `TBD`, `TODO`, or "implement later" placeholders.
- Type consistency: plan consistently uses `judge_score`, `evidence_score`, `judge_pass_rate`, `judge-results.jsonl`, and `judge-summary.json`.
- Scope check: live LLM calls are out of scope; only reproducible deterministic artifacts are required for Phase 11.
