# Phase 8 Static Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `skilleval dashboard` command that turns existing router run `results.jsonl` artifacts into one self-contained interactive HTML dashboard.

**Architecture:** Add a focused `dashboard.py` module that loads run folders, normalizes records, computes summaries, assigns failure tags, and renders a standalone HTML document. The existing CLI delegates to this module, while docs and demo artifacts prove the feature against the committed Phase 7B results.

**Tech Stack:** Python 3.11 standard library, existing SkillEval metric helpers, inline HTML/CSS/JavaScript, pytest, ruff, mypy.

---

## File Structure

- Create `src/hermes_skilleval/dashboard.py`: data loading, validation, normalization, summary metrics, failure tags, HTML rendering, and file writing.
- Modify `src/hermes_skilleval/cli.py`: add `dashboard` parser and `_run_dashboard` handler.
- Create `tests/test_dashboard.py`: unit tests for payload building, metric fallback, failure tags, HTML rendering, and missing-run failures.
- Modify `tests/test_cli_smoke.py`: CLI smoke coverage for success and empty-run failure.
- Create `tests/test_phase8_artifacts.py`: regression coverage for committed dashboard artifact.
- Create `docs/phase8.md`: implementation and usage note.
- Create `docs/demo/phase8-static-dashboard/dashboard.html`: generated static dashboard artifact.
- Modify `README.md`: mark dashboard Roadmap item complete and add usage.
- Modify `docs/demo/README.md`: list the dashboard artifact.
- Modify `docs/resume.md`: add a compact Phase 8 milestone.

## Task 1: Dashboard Payload Builder

**Files:**
- Create: `src/hermes_skilleval/dashboard.py`
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing payload tests**

Create `tests/test_dashboard.py` with the following initial tests:

```python
import json
from pathlib import Path

import pytest

from hermes_skilleval.dashboard import build_dashboard_payload


def test_build_dashboard_payload_loads_child_runs_and_summaries(tmp_path: Path):
    _write_run(
        tmp_path,
        "alpha-router",
        [
            {
                "task_id": "task-001",
                "router": "alpha",
                "split": "test",
                "category": "infra",
                "difficulty": "easy",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "recall_at_5": 1.0,
                "mrr": 1.0,
                "ndcg_at_5": 1.0,
                "negative_hit_rate": 0.0,
                "abstention_rate": 0.0,
                "selection_rate_at_5": 0.2,
                "latency_ms": 12.0,
                "scores": {"docker": 3.0, "academic-writing": -2.0},
            },
            {
                "task_id": "task-002",
                "router": "alpha",
                "split": "test",
                "category": "infra",
                "difficulty": "hard",
                "selected_skill_ids": ["academic-writing"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "recall_at_5": 0.0,
                "mrr": 0.0,
                "ndcg_at_5": 0.0,
                "negative_hit_rate": 1.0,
                "abstention_rate": 0.0,
                "selection_rate_at_5": 0.2,
                "latency_ms": 18.0,
            },
        ],
    )
    _write_run(
        tmp_path,
        "beta-router",
        [
            {
                "task_id": "task-003",
                "router": "beta",
                "split": "dev",
                "category": "writing",
                "difficulty": "medium",
                "selected_skill_ids": [],
                "gold_skills": ["academic-writing"],
                "negative_skills": ["docker"],
                "latency_ms": 20.0,
            }
        ],
    )

    payload = build_dashboard_payload(tmp_path)
    data = payload.to_json_dict()

    assert [run["label"] for run in data["runs"]] == ["alpha-router", "beta-router"]
    assert data["runs"][0]["task_count"] == 2
    assert data["runs"][0]["metrics"]["recall_at_5"] == 0.5
    assert data["runs"][0]["metrics"]["negative_hit_rate"] == 0.5
    assert data["runs"][1]["metrics"]["abstention_rate"] == 1.0
    assert len(data["records"]) == 3
    assert data["records"][1]["failure_tags"] == ["recall-miss", "negative-hit", "low-selection"]
    assert data["records"][2]["failure_tags"] == ["recall-miss", "abstained", "low-selection"]
    assert data["records"][0]["score_ranking"][0] == {"skill_id": "docker", "score": 3.0}
    assert data["filters"]["runs"] == ["alpha-router", "beta-router"]
    assert data["filters"]["splits"] == ["dev", "test"]
    assert data["filters"]["categories"] == ["infra", "writing"]
    assert data["filters"]["difficulties"] == ["easy", "hard", "medium"]
    assert data["filters"]["failure_tags"] == ["abstained", "low-selection", "negative-hit", "recall-miss"]


def test_build_dashboard_payload_requires_run_results(tmp_path: Path):
    with pytest.raises(ValueError, match="no dashboard runs found"):
        build_dashboard_payload(tmp_path)


def _write_run(root: Path, label: str, records: list[dict[str, object]]) -> None:
    run_dir = root / label
    run_dir.mkdir(parents=True)
    (run_dir / "results.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_dashboard.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'hermes_skilleval.dashboard'`.

- [ ] **Step 3: Implement payload builder**

Create `src/hermes_skilleval/dashboard.py` with this structure:

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermes_skilleval.metrics import (
    abstention_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_hit_rate,
    recall_at_k,
    selection_rate_at_k,
)


SUMMARY_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "abstention_rate",
    "selection_rate_at_5",
    "latency_ms",
)
REQUIRED_FIELDS = {"task_id", "router", "selected_skill_ids", "gold_skills", "negative_skills", "latency_ms"}


@dataclass(frozen=True)
class DashboardRun:
    label: str
    source_path: str
    task_count: int
    metrics: dict[str, float]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "source_path": self.source_path,
            "task_count": self.task_count,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class DashboardRecord:
    run: str
    task_id: str
    router: str
    split: str
    category: str
    difficulty: str
    selected_skill_ids: list[str]
    gold_skills: list[str]
    negative_skills: list[str]
    metrics: dict[str, float]
    failure_tags: list[str]
    score_ranking: list[dict[str, float | str]]
    prompt: str
    raw: dict[str, Any]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "run": self.run,
            "task_id": self.task_id,
            "router": self.router,
            "split": self.split,
            "category": self.category,
            "difficulty": self.difficulty,
            "selected_skill_ids": self.selected_skill_ids,
            "gold_skills": self.gold_skills,
            "negative_skills": self.negative_skills,
            "metrics": self.metrics,
            "failure_tags": self.failure_tags,
            "score_ranking": self.score_ranking,
            "prompt": self.prompt,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class DashboardPayload:
    source_path: str
    generated_at: str
    runs: list[DashboardRun]
    records: list[DashboardRecord]

    def to_json_dict(self) -> dict[str, object]:
        records = [record.to_json_dict() for record in self.records]
        return {
            "source_path": self.source_path,
            "generated_at": self.generated_at,
            "runs": [run.to_json_dict() for run in self.runs],
            "records": records,
            "filters": {
                "runs": _sorted_unique(record.run for record in self.records),
                "splits": _sorted_unique(record.split for record in self.records),
                "categories": _sorted_unique(record.category for record in self.records),
                "difficulties": _sorted_unique(record.difficulty for record in self.records),
                "failure_tags": _sorted_unique(tag for record in self.records for tag in record.failure_tags),
            },
        }


def build_dashboard_payload(runs_path: Path | str) -> DashboardPayload:
    root = Path(runs_path)
    if not root.is_dir():
        raise ValueError(f"dashboard runs path must be a directory: {root}")

    run_dirs = sorted(path for path in root.iterdir() if (path / "results.jsonl").is_file())
    if not run_dirs:
        raise ValueError(f"no dashboard runs found under {root}")

    runs: list[DashboardRun] = []
    records: list[DashboardRecord] = []
    for run_dir in run_dirs:
        source = run_dir / "results.jsonl"
        raw_records = _read_jsonl(source)
        normalized = [_normalize_record(run_dir.name, record, source, index + 1) for index, record in enumerate(raw_records)]
        runs.append(
            DashboardRun(
                label=run_dir.name,
                source_path=str(source),
                task_count=len(normalized),
                metrics=_mean_summary_metrics(normalized),
            )
        )
        records.extend(normalized)

    return DashboardPayload(
        source_path=str(root),
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        runs=runs,
        records=records,
    )
```

Add helpers in the same file:

```python
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"expected object in {path} at line {line_number}")
        records.append(record)
    if not records:
        raise ValueError(f"no result records found in {path}")
    return records


def _normalize_record(run: str, record: dict[str, Any], path: Path, line_number: int) -> DashboardRecord:
    _validate_record(record, path, line_number)
    selected = _string_list(record, "selected_skill_ids")
    gold = _string_list(record, "gold_skills")
    negative = _string_list(record, "negative_skills")
    metrics = _record_metrics(record, selected, gold, negative)
    return DashboardRecord(
        run=run,
        task_id=str(record["task_id"]),
        router=str(record["router"]),
        split=str(record.get("split", "unknown")),
        category=str(record.get("category", "unknown")),
        difficulty=str(record.get("difficulty", "unknown")),
        selected_skill_ids=selected,
        gold_skills=gold,
        negative_skills=negative,
        metrics=metrics,
        failure_tags=_failure_tags(selected, metrics),
        score_ranking=_score_ranking(record),
        prompt=str(record.get("prompt", "")),
        raw=record,
    )


def _validate_record(record: dict[str, Any], path: Path, line_number: int) -> None:
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        raise ValueError(f"missing fields in {path} at line {line_number}: {', '.join(missing)}")
    for field in ("selected_skill_ids", "gold_skills", "negative_skills"):
        _string_list(record, field)
    _finite_number(record["latency_ms"], "latency_ms", path, line_number)


def _string_list(record: dict[str, Any], field: str) -> list[str]:
    value = record[field]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"field {field!r} must be a list of strings")
    return list(value)


def _record_metrics(record: dict[str, Any], selected: list[str], gold: list[str], negative: list[str]) -> dict[str, float]:
    return {
        "recall_at_5": _metric_or(record, "recall_at_5", recall_at_k(selected, gold, 5)),
        "mrr": _metric_or(record, "mrr", mean_reciprocal_rank(selected, gold)),
        "ndcg_at_5": _metric_or(record, "ndcg_at_5", ndcg_at_k(selected, gold, 5)),
        "negative_hit_rate": _metric_or(record, "negative_hit_rate", negative_hit_rate(selected, negative, 5)),
        "abstention_rate": _metric_or(record, "abstention_rate", abstention_rate(selected)),
        "selection_rate_at_5": _metric_or(record, "selection_rate_at_5", selection_rate_at_k(selected, 5)),
        "latency_ms": _metric_or(record, "latency_ms", 0.0),
    }


def _metric_or(record: dict[str, Any], field: str, fallback: float) -> float:
    value = record.get(field, fallback)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"metric {field!r} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"metric {field!r} must be finite")
    return number


def _finite_number(value: object, field: str, path: Path, line_number: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(float(value)):
        raise ValueError(f"field {field!r} must be finite in {path} at line {line_number}")


def _failure_tags(selected: list[str], metrics: dict[str, float]) -> list[str]:
    tags: list[str] = []
    if metrics["recall_at_5"] < 1.0:
        tags.append("recall-miss")
    if metrics["negative_hit_rate"] > 0.0:
        tags.append("negative-hit")
    if not selected or metrics["abstention_rate"] > 0.0:
        tags.append("abstained")
    if metrics["selection_rate_at_5"] < 1.0:
        tags.append("low-selection")
    return tags


def _score_ranking(record: dict[str, Any]) -> list[dict[str, float | str]]:
    scores = record.get("scores", {})
    if not isinstance(scores, dict):
        return []
    rows = []
    for skill_id, score in scores.items():
        if isinstance(skill_id, str) and isinstance(score, int | float) and not isinstance(score, bool):
            rows.append({"skill_id": skill_id, "score": float(score)})
    return sorted(rows, key=lambda row: (-float(row["score"]), str(row["skill_id"])))


def _mean_summary_metrics(records: list[DashboardRecord]) -> dict[str, float]:
    return {
        field: round(sum(record.metrics[field] for record in records) / len(records), 6)
        for field in SUMMARY_FIELDS
    }


def _sorted_unique(values) -> list[str]:
    return sorted({str(value) for value in values if str(value)})
```

- [ ] **Step 4: Run payload tests**

Run:

```bash
pytest tests/test_dashboard.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit payload builder**

Run:

```bash
git add src/hermes_skilleval/dashboard.py tests/test_dashboard.py
git commit -m "feat: add dashboard payload builder"
```

Expected: commit succeeds.

## Task 2: Static HTML Renderer

**Files:**
- Modify: `src/hermes_skilleval/dashboard.py`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Add failing renderer tests**

Append these tests to `tests/test_dashboard.py`:

```python
from hermes_skilleval.dashboard import render_dashboard_html, write_dashboard


def test_render_dashboard_html_is_self_contained(tmp_path: Path):
    _write_run(
        tmp_path,
        "alpha-router",
        [
            {
                "task_id": "task-001",
                "router": "alpha",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "latency_ms": 12.0,
            }
        ],
    )

    payload = build_dashboard_payload(tmp_path)
    html = render_dashboard_html(payload)

    assert html.startswith("<!doctype html>")
    assert "Hermes SkillEval Dashboard" in html
    assert "window.__SKILLEVAL_DASHBOARD__" in html
    assert "alpha-router" in html
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "https://" not in html
    assert "http://" not in html


def test_write_dashboard_creates_parent_directory(tmp_path: Path):
    _write_run(
        tmp_path / "runs",
        "alpha-router",
        [
            {
                "task_id": "task-001",
                "router": "alpha",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "latency_ms": 12.0,
            }
        ],
    )

    output = tmp_path / "nested" / "dashboard.html"
    write_dashboard(tmp_path / "runs", output)

    assert output.exists()
    assert "task-001" in output.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run renderer tests to verify they fail**

Run:

```bash
pytest tests/test_dashboard.py::test_render_dashboard_html_is_self_contained tests/test_dashboard.py::test_write_dashboard_creates_parent_directory -q
```

Expected: fail with `ImportError` for `render_dashboard_html` or `write_dashboard`.

- [ ] **Step 3: Add renderer API**

Add these functions to `src/hermes_skilleval/dashboard.py`:

```python
def write_dashboard(runs_path: Path | str, output_path: Path | str) -> None:
    payload = build_dashboard_payload(runs_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard_html(payload), encoding="utf-8")


def render_dashboard_html(payload: DashboardPayload) -> str:
    payload_json = json.dumps(payload.to_json_dict(), ensure_ascii=False, sort_keys=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes SkillEval Dashboard</title>
  <style>{_dashboard_css()}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <h1>Hermes SkillEval Dashboard</h1>
      <p id="sourceLine"></p>
    </div>
    <input id="searchInput" type="search" aria-label="Search task, router, skill, category">
  </header>
  <main class="layout">
    <section class="metric-strip" id="metricStrip"></section>
    <aside class="filters" id="filters"></aside>
    <section class="table-panel">
      <div class="table-meta" id="tableMeta"></div>
      <table>
        <thead>
          <tr>
            <th data-sort="run">Run</th>
            <th data-sort="task_id">Task</th>
            <th data-sort="split">Split</th>
            <th data-sort="category">Category</th>
            <th data-sort="difficulty">Difficulty</th>
            <th data-sort="recall_at_5">Recall@5</th>
            <th data-sort="negative_hit_rate">Neg Hit</th>
            <th data-sort="abstention_rate">Abstain</th>
            <th>Selected</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody id="recordRows"></tbody>
      </table>
    </section>
    <aside class="inspector" id="inspector"></aside>
  </main>
  <script>window.__SKILLEVAL_DASHBOARD__ = {payload_json};</script>
  <script>{_dashboard_js()}</script>
</body>
</html>
"""
```

- [ ] **Step 4: Add compact CSS**

Add `_dashboard_css()` to `src/hermes_skilleval/dashboard.py`:

```python
def _dashboard_css() -> str:
    return """
:root { color-scheme: light; --bg: #f7f8fa; --panel: #ffffff; --ink: #17202a; --muted: #64748b; --line: #d8dee8; --accent: #2563eb; --bad: #b42318; --warn: #9a6700; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 22px; background: var(--panel); border-bottom: 1px solid var(--line); }
h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
p { margin: 0; }
#sourceLine { color: var(--muted); margin-top: 4px; }
#searchInput { width: min(420px, 42vw); padding: 9px 11px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--ink); }
.layout { display: grid; grid-template-columns: 220px minmax(520px, 1fr) 320px; grid-template-areas: "metrics metrics metrics" "filters table inspector"; gap: 14px; padding: 14px; }
.metric-strip { grid-area: metrics; display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.metric-card, .filters, .table-panel, .inspector { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
.metric-card { padding: 12px; }
.metric-card h2 { margin: 0 0 8px; font-size: 14px; }
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 10px; color: var(--muted); }
.metric-grid b { color: var(--ink); font-variant-numeric: tabular-nums; }
.filters { grid-area: filters; padding: 12px; align-self: start; }
.filter-group { margin-bottom: 12px; }
.filter-group label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
select { width: 100%; padding: 7px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
.table-panel { grid-area: table; overflow: hidden; }
.table-meta { padding: 10px 12px; color: var(--muted); border-bottom: 1px solid var(--line); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 12px; cursor: pointer; user-select: none; }
td.numeric { font-variant-numeric: tabular-nums; text-align: right; }
tr.record-row { cursor: pointer; }
tr.record-row:hover, tr.record-row.selected { background: #eef4ff; }
.pill { display: inline-block; margin: 0 4px 4px 0; padding: 2px 6px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-size: 12px; }
.pill.bad { color: var(--bad); border-color: #f2b8b5; background: #fff5f5; }
.pill.warn { color: var(--warn); border-color: #efd8a5; background: #fff9e8; }
.inspector { grid-area: inspector; padding: 12px; align-self: start; max-height: calc(100vh - 130px); overflow: auto; }
.inspector h2 { margin: 0 0 8px; font-size: 16px; }
.section { margin-top: 14px; }
.section h3 { margin: 0 0 6px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: 10px; background: #f1f5f9; border-radius: 6px; font-size: 12px; }
@media (max-width: 980px) { .layout { grid-template-columns: 1fr; grid-template-areas: "metrics" "filters" "table" "inspector"; } #searchInput { width: 100%; } .topbar { align-items: stretch; flex-direction: column; } }
"""
```

- [ ] **Step 5: Add client-side JavaScript**

Add `_dashboard_js()` to `src/hermes_skilleval/dashboard.py`:

```python
def _dashboard_js() -> str:
    return r"""
const payload = window.__SKILLEVAL_DASHBOARD__;
let state = { search: "", filters: { run: "", split: "", category: "", difficulty: "", failure: "" }, sortKey: "run", sortDir: "asc", selectedIndex: 0 };

function fmt(value) {
  return Number(value || 0).toFixed(3);
}
function text(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
function metric(record, key) {
  return Number(record.metrics[key] || 0);
}
function renderMetrics() {
  document.getElementById("sourceLine").textContent = `${payload.source_path} · generated ${payload.generated_at}`;
  document.getElementById("metricStrip").innerHTML = payload.runs.map(run => `
    <article class="metric-card">
      <h2>${text(run.label)}</h2>
      <div class="metric-grid">
        <span>Tasks <b>${run.task_count}</b></span>
        <span>Recall@5 <b>${fmt(run.metrics.recall_at_5)}</b></span>
        <span>MRR <b>${fmt(run.metrics.mrr)}</b></span>
        <span>NDCG@5 <b>${fmt(run.metrics.ndcg_at_5)}</b></span>
        <span>Neg Hit <b>${fmt(run.metrics.negative_hit_rate)}</b></span>
        <span>Abstain <b>${fmt(run.metrics.abstention_rate)}</b></span>
        <span>Select@5 <b>${fmt(run.metrics.selection_rate_at_5)}</b></span>
        <span>Latency <b>${fmt(run.metrics.latency_ms)}</b></span>
      </div>
    </article>`).join("");
}
function renderFilters() {
  const groups = [
    ["run", "Run", payload.filters.runs],
    ["split", "Split", payload.filters.splits],
    ["category", "Category", payload.filters.categories],
    ["difficulty", "Difficulty", payload.filters.difficulties],
    ["failure", "Failure Type", payload.filters.failure_tags],
  ];
  document.getElementById("filters").innerHTML = groups.map(([key, label, values]) => `
    <div class="filter-group">
      <label for="filter-${key}">${label}</label>
      <select id="filter-${key}" data-filter="${key}">
        <option value="">All</option>
        ${values.map(value => `<option value="${text(value)}">${text(value)}</option>`).join("")}
      </select>
    </div>`).join("");
  document.querySelectorAll("[data-filter]").forEach(select => {
    select.addEventListener("change", event => {
      state.filters[event.target.dataset.filter] = event.target.value;
      state.selectedIndex = 0;
      renderTable();
    });
  });
}
function searchBlob(record) {
  return [record.run, record.task_id, record.router, record.split, record.category, record.difficulty, record.prompt, ...record.selected_skill_ids, ...record.gold_skills, ...record.negative_skills].join(" ").toLowerCase();
}
function filteredRecords() {
  const query = state.search.trim().toLowerCase();
  return payload.records.filter(record => {
    if (query && !searchBlob(record).includes(query)) return false;
    if (state.filters.run && record.run !== state.filters.run) return false;
    if (state.filters.split && record.split !== state.filters.split) return false;
    if (state.filters.category && record.category !== state.filters.category) return false;
    if (state.filters.difficulty && record.difficulty !== state.filters.difficulty) return false;
    if (state.filters.failure && !record.failure_tags.includes(state.filters.failure)) return false;
    return true;
  }).sort((left, right) => {
    const key = state.sortKey;
    const leftValue = key in left.metrics ? left.metrics[key] : left[key];
    const rightValue = key in right.metrics ? right.metrics[key] : right[key];
    const result = typeof leftValue === "number" && typeof rightValue === "number"
      ? leftValue - rightValue
      : String(leftValue).localeCompare(String(rightValue));
    return state.sortDir === "asc" ? result : -result;
  });
}
function tagPills(tags) {
  return tags.map(tag => `<span class="pill ${tag === "negative-hit" || tag === "recall-miss" ? "bad" : "warn"}">${text(tag)}</span>`).join("");
}
function renderTable() {
  const rows = filteredRecords();
  if (state.selectedIndex >= rows.length) state.selectedIndex = 0;
  document.getElementById("tableMeta").textContent = `${rows.length} matching records`;
  document.getElementById("recordRows").innerHTML = rows.map((record, index) => `
    <tr class="record-row ${index === state.selectedIndex ? "selected" : ""}" data-index="${index}">
      <td>${text(record.run)}</td>
      <td>${text(record.task_id)}</td>
      <td>${text(record.split)}</td>
      <td>${text(record.category)}</td>
      <td>${text(record.difficulty)}</td>
      <td class="numeric">${fmt(record.metrics.recall_at_5)}</td>
      <td class="numeric">${fmt(record.metrics.negative_hit_rate)}</td>
      <td class="numeric">${fmt(record.metrics.abstention_rate)}</td>
      <td>${record.selected_skill_ids.map(item => `<span class="pill">${text(item)}</span>`).join("")}</td>
      <td>${tagPills(record.failure_tags)}</td>
    </tr>`).join("");
  document.querySelectorAll(".record-row").forEach(row => row.addEventListener("click", event => {
    state.selectedIndex = Number(event.currentTarget.dataset.index);
    renderTable();
  }));
  renderInspector(rows[state.selectedIndex]);
}
function renderInspector(record) {
  const target = document.getElementById("inspector");
  if (!record) {
    target.innerHTML = "<h2>No records</h2><p>Adjust filters to inspect tasks.</p>";
    return;
  }
  target.innerHTML = `
    <h2>${text(record.task_id)}</h2>
    <p>${text(record.run)} · ${text(record.split)} · ${text(record.category)} · ${text(record.difficulty)}</p>
    <div class="section"><h3>Failure Tags</h3>${tagPills(record.failure_tags) || "<span class='pill'>clean</span>"}</div>
    <div class="section"><h3>Prompt</h3><p>${text(record.prompt || "No prompt stored in this result record.")}</p></div>
    <div class="section"><h3>Gold Skills</h3>${record.gold_skills.map(item => `<span class="pill">${text(item)}</span>`).join("")}</div>
    <div class="section"><h3>Negative Skills</h3>${record.negative_skills.map(item => `<span class="pill bad">${text(item)}</span>`).join("")}</div>
    <div class="section"><h3>Selected Skills</h3>${record.selected_skill_ids.map(item => `<span class="pill">${text(item)}</span>`).join("") || "<span class='pill warn'>abstained</span>"}</div>
    <div class="section"><h3>Score Ranking</h3><pre>${text(record.score_ranking.slice(0, 25).map(row => `${row.skill_id}: ${fmt(row.score)}`).join("\n") || "No scores stored.")}</pre></div>
    <div class="section"><h3>Raw JSON</h3><pre>${text(JSON.stringify(record.raw, null, 2))}</pre></div>`;
}
function attachEvents() {
  document.getElementById("searchInput").addEventListener("input", event => {
    state.search = event.target.value;
    state.selectedIndex = 0;
    renderTable();
  });
  document.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", event => {
    const key = event.currentTarget.dataset.sort;
    if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    else { state.sortKey = key; state.sortDir = "asc"; }
    renderTable();
  }));
}
renderMetrics();
renderFilters();
attachEvents();
renderTable();
"""
```

- [ ] **Step 6: Run renderer tests**

Run:

```bash
pytest tests/test_dashboard.py -q
```

Expected: all dashboard tests pass.

- [ ] **Step 7: Commit renderer**

Run:

```bash
git add src/hermes_skilleval/dashboard.py tests/test_dashboard.py
git commit -m "feat: render static dashboard html"
```

Expected: commit succeeds.

## Task 3: CLI Dashboard Command

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Add failing CLI smoke tests**

Append these tests to `tests/test_cli_smoke.py`:

```python
def test_cli_dashboard_writes_static_html(tmp_path):
    runs = tmp_path / "runs"
    run_dir = runs / "sample-router"
    run_dir.mkdir(parents=True)
    (run_dir / "results.jsonl").write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "router": "sample",
                "selected_skill_ids": ["docker"],
                "gold_skills": ["docker"],
                "negative_skills": ["academic-writing"],
                "latency_ms": 7.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "dashboard" / "index.html"

    result = cli.main(["dashboard", "--runs", str(runs), "--output", str(output)])

    assert result == 0
    html = output.read_text(encoding="utf-8")
    assert "Hermes SkillEval Dashboard" in html
    assert "sample-router" in html
    assert "task-001" in html


def test_cli_dashboard_reports_empty_runs_dir(tmp_path, capsys):
    result = cli.main(["dashboard", "--runs", str(tmp_path), "--output", str(tmp_path / "dashboard.html")])

    assert result == 2
    captured = capsys.readouterr()
    assert "no dashboard runs found" in captured.err
```

If `tests/test_cli_smoke.py` imports `json` under a different local scope, reuse the existing import rather than adding a duplicate.

- [ ] **Step 2: Run CLI dashboard tests to verify they fail**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_dashboard_writes_static_html tests/test_cli_smoke.py::test_cli_dashboard_reports_empty_runs_dir -q
```

Expected: fail because `dashboard` is not a recognized command.

- [ ] **Step 3: Wire CLI parser**

In `src/hermes_skilleval/cli.py`, add the import:

```python
from hermes_skilleval.dashboard import write_dashboard
```

Inside `_build_parser()`, after the `report` parser block, add:

```python
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="write a self-contained HTML dashboard for router run results",
    )
    dashboard_parser.add_argument("--runs", required=True)
    dashboard_parser.add_argument("--output", required=True)
    dashboard_parser.set_defaults(handler=_run_dashboard)
```

Add the handler near `_run_report`:

```python
def _run_dashboard(args: argparse.Namespace) -> None:
    write_dashboard(args.runs, args.output)
    print(f"Wrote dashboard to {args.output}")
```

- [ ] **Step 4: Run CLI dashboard tests**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_dashboard_writes_static_html tests/test_cli_smoke.py::test_cli_dashboard_reports_empty_runs_dir -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run focused dashboard suite**

Run:

```bash
pytest tests/test_dashboard.py tests/test_cli_smoke.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit CLI integration**

Run:

```bash
git add src/hermes_skilleval/cli.py tests/test_cli_smoke.py
git commit -m "feat: add dashboard cli"
```

Expected: commit succeeds.

## Task 4: Phase 8 Demo Artifact And Docs

**Files:**
- Create: `docs/phase8.md`
- Create: `docs/demo/phase8-static-dashboard/dashboard.html`
- Create: `tests/test_phase8_artifacts.py`
- Modify: `README.md`
- Modify: `docs/demo/README.md`
- Modify: `docs/resume.md`

- [ ] **Step 1: Generate demo artifact**

Run:

```bash
python -m hermes_skilleval.cli dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

Expected output:

```text
Wrote dashboard to docs/demo/phase8-static-dashboard/dashboard.html
```

- [ ] **Step 2: Add artifact regression tests**

Create `tests/test_phase8_artifacts.py`:

```python
from pathlib import Path


PHASE8_DASHBOARD = Path("docs/demo/phase8-static-dashboard/dashboard.html")


def test_phase8_dashboard_artifact_is_committed_and_self_contained():
    html = PHASE8_DASHBOARD.read_text(encoding="utf-8")

    assert "Hermes SkillEval Dashboard" in html
    assert "cross-encoder-calibrated-strict-test" in html
    assert "cross-encoder-calibrated-balanced-test" in html
    assert "cross-encoder-rank-only-test" in html
    assert "gated-minilm-contrastive-test" in html
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "https://" not in html
    assert "http://" not in html
```

- [ ] **Step 3: Run artifact test**

Run:

```bash
pytest tests/test_phase8_artifacts.py -q
```

Expected: `1 passed`.

- [ ] **Step 4: Create Phase 8 documentation**

Create `docs/phase8.md`:

```markdown
# Phase 8: Static Failure Inspection Dashboard

Phase 8 adds a static HTML dashboard for inspecting committed SkillEval run
artifacts without starting a web server or rerunning benchmarks.

## What changed

- Added `skilleval dashboard`.
- Added `src/hermes_skilleval/dashboard.py` for run loading, summary metrics,
  failure tagging, and static HTML rendering.
- Added a committed dashboard artifact at
  `docs/demo/phase8-static-dashboard/dashboard.html`.

## Usage

```bash
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

The dashboard embeds all data, CSS, and JavaScript in one file. It supports
search, filters, sortable task rows, task inspection, score ranking, and raw JSON
inspection.

## Acceptance check

The Phase 8 artifact is generated from the Phase 7B run folders and includes the
four same-test comparison runs:

- `gated-minilm-contrastive-test`
- `cross-encoder-rank-only-test`
- `cross-encoder-calibrated-strict-test`
- `cross-encoder-calibrated-balanced-test`

This closes the README Roadmap item for interactive failure inspection while
keeping the project offline and reproducible.
```

- [ ] **Step 5: Update README**

In `README.md`, add a short dashboard usage snippet after the existing report or calibration examples:

```markdown
### Static Dashboard

```bash
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

The generated file is self-contained and can be opened directly in a browser for
interactive run filtering, failure inspection, score ranking, and raw JSON audit.
```

In the Roadmap section, change:

```markdown
- [ ] Web dashboard for interactive failure inspection
```

to:

```markdown
- [x] Web dashboard for interactive failure inspection
```

In the phase table, add:

```markdown
| Phase 8 | Static failure inspection dashboard | [`docs/phase8.md`](docs/phase8.md) |
```

- [ ] **Step 6: Update demo README**

In `docs/demo/README.md`, add the dashboard command near the Phase 7B commands:

```markdown
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

In the artifact list, add:

```markdown
- `phase8-static-dashboard/dashboard.html`: self-contained interactive dashboard
  for filtering Phase 7B runs, inspecting failures, viewing score rankings, and
  auditing raw task records.
```

- [ ] **Step 7: Update resume**

In `docs/resume.md`, add a milestone bullet after Phase 7B:

```markdown
- Phase 8: a static self-contained dashboard makes committed benchmark runs
  inspectable in a browser with filters, sortable task rows, failure tags, score
  rankings, and raw JSON audit views.
```

Also add `static dashboard` to the keyword line if the surrounding sentence lists project capabilities.

- [ ] **Step 8: Run docs/artifact focused tests**

Run:

```bash
pytest tests/test_phase8_artifacts.py tests/test_dashboard.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit demo and docs**

Run:

```bash
git add README.md docs/demo/README.md docs/resume.md docs/phase8.md docs/demo/phase8-static-dashboard/dashboard.html tests/test_phase8_artifacts.py
git commit -m "docs: add phase8 dashboard artifact"
```

Expected: commit succeeds.

## Task 5: Full Verification And Roadmap Closure

**Files:**
- Verify all changed files from Tasks 1-4.

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run:

```bash
ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run type checking**

Run:

```bash
mypy src tests
```

Expected:

```text
Success: no issues found in 43 source files
```

The exact source-file count may change by one depending on how test modules are counted; the success line is the required evidence.

- [ ] **Step 4: Run editable install dry-run**

Run:

```bash
python -m pip install -e . --dry-run
```

Expected includes:

```text
Would install hermes-skilleval-0.1.0
```

- [ ] **Step 5: Verify Roadmap state**

Run:

```bash
rg -n "Web dashboard|Phase 8|skilleval dashboard" README.md docs/phase8.md docs/demo/README.md docs/resume.md
```

Expected:

- README Roadmap has `- [x] Web dashboard for interactive failure inspection`.
- README references `skilleval dashboard`.
- `docs/phase8.md` exists and describes the static dashboard.
- `docs/demo/README.md` lists the Phase 8 artifact.
- `docs/resume.md` includes the Phase 8 milestone.

- [ ] **Step 6: Inspect final Git state**

Run:

```bash
git status --short
```

Expected: no unstaged or untracked changes.

- [ ] **Step 7: Report completion evidence**

In the final implementation response, include:

- Summary of the dashboard command and generated artifact path.
- Verification commands and their passing outputs.
- Current commit hash from `git log -1 --oneline`.

## Self-Review

- Spec coverage: Tasks 1-4 cover loading child `results.jsonl` files, summary metrics, failure tags, HTML rendering, CLI integration, demo artifact, README Roadmap closure, and docs updates.
- Scope control: The plan keeps Phase 8 static and self-contained. It does not add a server, frontend build system, editing workflows, or network resources.
- Type consistency: The plan uses `DashboardPayload`, `DashboardRun`, `DashboardRecord`, `build_dashboard_payload`, `render_dashboard_html`, and `write_dashboard` consistently across tests, implementation, and CLI.
