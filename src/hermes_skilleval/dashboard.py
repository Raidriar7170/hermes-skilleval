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
REQUIRED_FIELDS = {
    "task_id",
    "router",
    "selected_skill_ids",
    "gold_skills",
    "negative_skills",
    "latency_ms",
}


@dataclass(frozen=True)
class DashboardRun:
    label: str
    source_path: str
    task_count: int
    metrics: dict[str, float]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "source_path": self.source_path,
            "task_count": self.task_count,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class DashboardRecord:
    run_label: str
    task_id: str
    router: str
    split: str
    category: str
    difficulty: str
    prompt: str
    selected_skill_ids: list[str]
    gold_skills: list[str]
    negative_skills: list[str]
    metrics: dict[str, float]
    failure_tags: list[str]
    score_ranking: list[dict[str, float | str]]
    raw: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "run": self.run_label,
            "task_id": self.task_id,
            "router": self.router,
            "split": self.split,
            "category": self.category,
            "difficulty": self.difficulty,
            "prompt": self.prompt,
            "selected_skill_ids": self.selected_skill_ids,
            "gold_skills": self.gold_skills,
            "negative_skills": self.negative_skills,
            "metrics": self.metrics,
            "failure_tags": self.failure_tags,
            "score_ranking": self.score_ranking,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class DashboardPayload:
    source_path: str
    generated_at: str
    runs: list[DashboardRun]
    records: list[DashboardRecord]
    filters: dict[str, list[str]]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "generated_at": self.generated_at,
            "runs": [run.to_json_dict() for run in self.runs],
            "records": [record.to_json_dict() for record in self.records],
            "filters": self.filters,
        }


def build_dashboard_payload(runs_path: Path | str) -> DashboardPayload:
    root = Path(runs_path)
    if not root.is_dir():
        raise ValueError(f"dashboard runs path must be a directory: {root}")

    run_dirs = sorted(
        path for path in root.iterdir() if path.is_dir() and (path / "results.jsonl").is_file()
    )
    if not run_dirs:
        raise ValueError(f"no dashboard runs found under {root}")

    runs: list[DashboardRun] = []
    records: list[DashboardRecord] = []
    for run_dir in run_dirs:
        raw_records = _read_jsonl(run_dir / "results.jsonl")
        normalized = [
            _normalize_record(record, run_dir / "results.jsonl", line_number)
            for line_number, record in raw_records
        ]
        dashboard_records = [
            DashboardRecord(
                run_label=run_dir.name,
                task_id=record["task_id"],
                router=record["router"],
                split=record["split"],
                category=record["category"],
                difficulty=record["difficulty"],
                prompt=record["prompt"],
                selected_skill_ids=record["selected_skill_ids"],
                gold_skills=record["gold_skills"],
                negative_skills=record["negative_skills"],
                metrics=record["metrics"],
                failure_tags=_failure_tags(
                    record["metrics"], record["selected_skill_ids"]
                ),
                score_ranking=_score_ranking(record),
                raw=record["raw"],
            )
            for record in normalized
        ]
        runs.append(
            DashboardRun(
                label=run_dir.name,
                source_path=str(run_dir / "results.jsonl"),
                task_count=len(dashboard_records),
                metrics=_mean_summary_metrics([record.metrics for record in dashboard_records]),
            )
        )
        records.extend(dashboard_records)

    filters = {
        "runs": [run.label for run in runs],
        "splits": _sorted_unique(record.split for record in records),
        "categories": _sorted_unique(record.category for record in records),
        "difficulties": _sorted_unique(record.difficulty for record in records),
        "failure_tags": _sorted_unique(tag for record in records for tag in record.failure_tags),
    }
    return DashboardPayload(
        source_path=str(root),
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        runs=runs,
        records=records,
        filters=filters,
    )


def write_dashboard(runs_path: Path | str, output_path: Path | str) -> None:
    payload = build_dashboard_payload(runs_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard_html(payload), encoding="utf-8")


def render_dashboard_html(payload: DashboardPayload) -> str:
    payload_json = (
        json.dumps(payload.to_json_dict(), ensure_ascii=False, sort_keys=True)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
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


def _dashboard_css() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --panel: #ffffff;
  --text: #20242c;
  --muted: #667085;
  --line: #d9dee7;
  --accent: #2563eb;
  --ok: #0f766e;
  --warn: #b45309;
  --bad: #b91c1c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 13px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
}
h1 { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: 0; }
p { margin: 0; }
#sourceLine { margin-top: 2px; color: var(--muted); font-size: 12px; }
#searchInput {
  width: min(420px, 42vw);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
  background: #fff;
}
.layout {
  display: grid;
  grid-template-columns: 220px minmax(520px, 1fr) 320px;
  grid-template-areas:
    "metrics metrics metrics"
    "filters table inspector";
  gap: 12px;
  padding: 12px;
}
.metric-strip {
  grid-area: metrics;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}
.metric, .filters, .table-panel, .inspector {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.metric { padding: 10px 12px; }
.metric .label, .filter-title, .field-label { color: var(--muted); font-size: 11px; text-transform: uppercase; }
.metric .value { margin-top: 3px; font-size: 20px; font-weight: 700; }
.filters {
  grid-area: filters;
  align-self: start;
  padding: 10px;
}
.filter-group { padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid var(--line); }
.filter-group:last-child { margin-bottom: 0; border-bottom: 0; }
.filter-title { margin-bottom: 6px; font-weight: 700; }
label.check {
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 3px 0;
  color: #344054;
}
input[type="checkbox"] { margin: 0; }
.table-panel {
  grid-area: table;
  min-width: 0;
  overflow: auto;
}
.table-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
}
table { width: 100%; border-collapse: collapse; }
th, td {
  padding: 8px 10px;
  border-bottom: 1px solid #edf0f4;
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  background: #fbfcfe;
  color: #475467;
  font-size: 12px;
  font-weight: 700;
  cursor: default;
}
th[data-sort] { cursor: pointer; }
tr { cursor: pointer; }
tr:hover, tr.selected { background: #eef5ff; }
.num { font-variant-numeric: tabular-nums; }
.pill {
  display: inline-block;
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 2px 6px;
  margin: 0 4px 4px 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f9fafb;
  vertical-align: top;
}
.tag { border-color: #fed7aa; background: #fff7ed; color: var(--warn); }
.tag.bad { border-color: #fecaca; background: #fff1f2; color: var(--bad); }
.inspector {
  grid-area: inspector;
  align-self: start;
  max-height: calc(100vh - 130px);
  overflow: auto;
  padding: 12px;
}
.inspector h2 { margin: 0 0 10px; font-size: 16px; }
.field { margin-bottom: 11px; }
.field-value { margin-top: 3px; overflow-wrap: anywhere; }
pre {
  overflow: auto;
  padding: 8px;
  border-radius: 6px;
  background: #111827;
  color: #f9fafb;
  font-size: 12px;
}
.empty { color: var(--muted); padding: 18px; text-align: center; }
@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
    grid-template-areas: "metrics" "filters" "table" "inspector";
  }
  #searchInput { width: 100%; }
  .topbar { align-items: stretch; flex-direction: column; }
  .inspector { max-height: none; }
}
"""


def _dashboard_js() -> str:
    return r"""
(function () {
  "use strict";

  const payload = window.__SKILLEVAL_DASHBOARD__ || {};
  const records = Array.isArray(payload.records) ? payload.records : [];
  const filters = payload.filters || {};
  const active = { run: new Set(), split: new Set(), category: new Set(), difficulty: new Set(), failure: new Set() };
  const state = { search: "", sortKey: "run", sortDir: 1, selected: records[0] || null };

  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  const metric = (record, key) => Number(record && record.metrics ? record.metrics[key] : 0) || 0;
  const pct = (value) => (Number(value) * 100).toFixed(1) + "%";
  const num = (value) => Number(value || 0).toFixed(3);
  const list = (values, className) => {
    const items = Array.isArray(values) ? values : [];
    if (!items.length) return '<span class="field-value">None</span>';
    return items.map((item) => '<span class="pill ' + className + '">' + esc(item) + "</span>").join("");
  };
  const getSortValue = (record, key) => {
    if (key in (record.metrics || {})) return metric(record, key);
    return String(record[key] == null ? "" : record[key]).toLowerCase();
  };

  function renderSourceLine() {
    $("sourceLine").textContent = "Source: " + (payload.source_path || "") + " | Generated: " + (payload.generated_at || "");
  }

  function average(key) {
    if (!records.length) return 0;
    return records.reduce((sum, record) => sum + metric(record, key), 0) / records.length;
  }

  function renderMetrics() {
    const totalRuns = Array.isArray(payload.runs) ? payload.runs.length : 0;
    const rows = [
      ["Runs", totalRuns],
      ["Tasks", records.length],
      ["Recall@5", pct(average("recall_at_5"))],
      ["MRR", num(average("mrr"))],
      ["Neg Hit", pct(average("negative_hit_rate"))],
      ["Abstain", pct(average("abstention_rate"))],
      ["Latency", Math.round(average("latency_ms")) + " ms"],
    ];
    $("metricStrip").innerHTML = rows.map(([label, value]) =>
      '<div class="metric"><div class="label">' + esc(label) + '</div><div class="value">' + esc(value) + "</div></div>"
    ).join("");
  }

  function filterGroup(title, key, values) {
    const items = (values || []).map((value) => {
      const id = "filter-" + key + "-" + String(value).replace(/[^a-z0-9_-]+/gi, "-");
      return '<label class="check" for="' + esc(id) + '"><input id="' + esc(id) + '" type="checkbox" data-filter="' + esc(key) + '" value="' + esc(value) + '">' + esc(value) + "</label>";
    }).join("");
    return '<div class="filter-group"><div class="filter-title">' + esc(title) + "</div>" + (items || '<div class="field-value">None</div>') + "</div>";
  }

  function renderFilters() {
    $("filters").innerHTML = [
      filterGroup("Run", "run", filters.runs),
      filterGroup("Split", "split", filters.splits),
      filterGroup("Category", "category", filters.categories),
      filterGroup("Difficulty", "difficulty", filters.difficulties),
      filterGroup("Failure", "failure", filters.failure_tags),
    ].join("");
    $("filters").addEventListener("change", (event) => {
      const target = event.target;
      if (!target || target.type !== "checkbox") return;
      const bucket = active[target.dataset.filter];
      if (target.checked) bucket.add(target.value);
      else bucket.delete(target.value);
      renderTable();
    });
  }

  function matchesFilters(record) {
    if (active.run.size && !active.run.has(record.run)) return false;
    if (active.split.size && !active.split.has(record.split || "")) return false;
    if (active.category.size && !active.category.has(record.category || "")) return false;
    if (active.difficulty.size && !active.difficulty.has(record.difficulty || "")) return false;
    if (active.failure.size) {
      const tags = new Set(record.failure_tags || []);
      for (const tag of active.failure) if (!tags.has(tag)) return false;
    }
    if (!state.search) return true;
    const haystack = [
      record.run, record.task_id, record.router, record.split, record.category,
      record.difficulty, record.prompt,
      ...(record.selected_skill_ids || []),
      ...(record.gold_skills || []),
      ...(record.negative_skills || []),
      ...(record.failure_tags || []),
    ].join(" ").toLowerCase();
    return haystack.includes(state.search);
  }

  function visibleRecords() {
    return records.filter(matchesFilters).sort((left, right) => {
      const a = getSortValue(left, state.sortKey);
      const b = getSortValue(right, state.sortKey);
      if (a < b) return -1 * state.sortDir;
      if (a > b) return 1 * state.sortDir;
      return String(left.task_id).localeCompare(String(right.task_id));
    });
  }

  function renderTable() {
    const rows = visibleRecords();
    $("tableMeta").textContent = rows.length + " of " + records.length + " tasks";
    if (!rows.length) {
      $("recordRows").innerHTML = '<tr><td class="empty" colspan="10">No matching records</td></tr>';
      renderInspector(null);
      return;
    }
    if (!state.selected || !rows.includes(state.selected)) state.selected = rows[0];
    $("recordRows").innerHTML = rows.map((record, index) =>
      '<tr data-index="' + index + '"' + (record === state.selected ? ' class="selected"' : "") + ">" +
      "<td>" + esc(record.run) + "</td>" +
      "<td>" + esc(record.task_id) + "</td>" +
      "<td>" + esc(record.split) + "</td>" +
      "<td>" + esc(record.category) + "</td>" +
      "<td>" + esc(record.difficulty) + "</td>" +
      '<td class="num">' + pct(metric(record, "recall_at_5")) + "</td>" +
      '<td class="num">' + pct(metric(record, "negative_hit_rate")) + "</td>" +
      '<td class="num">' + pct(metric(record, "abstention_rate")) + "</td>" +
      "<td>" + list(record.selected_skill_ids, "") + "</td>" +
      "<td>" + list(record.failure_tags, "tag bad") + "</td>" +
      "</tr>"
    ).join("");
    Array.from($("recordRows").querySelectorAll("tr[data-index]")).forEach((row) => {
      row.addEventListener("click", () => {
        state.selected = rows[Number(row.dataset.index)];
        renderTable();
      });
    });
    renderInspector(state.selected);
  }

  function renderRanking(record) {
    const ranking = Array.isArray(record.score_ranking) ? record.score_ranking : [];
    if (!ranking.length) return '<div class="field-value">No scores</div>';
    return "<ol>" + ranking.map((row) => "<li>" + esc(row.skill_id) + " <span class=\"num\">" + num(row.score) + "</span></li>").join("") + "</ol>";
  }

  function renderInspector(record) {
    if (!record) {
      $("inspector").innerHTML = '<div class="empty">Select a task to inspect details</div>';
      return;
    }
    $("inspector").innerHTML =
      "<h2>" + esc(record.task_id) + "</h2>" +
      '<div class="field"><div class="field-label">Run</div><div class="field-value">' + esc(record.run) + "</div></div>" +
      '<div class="field"><div class="field-label">Router</div><div class="field-value">' + esc(record.router) + "</div></div>" +
      '<div class="field"><div class="field-label">Prompt</div><div class="field-value">' + esc(record.prompt || "No prompt") + "</div></div>" +
      '<div class="field"><div class="field-label">Selected</div><div class="field-value">' + list(record.selected_skill_ids, "") + "</div></div>" +
      '<div class="field"><div class="field-label">Gold</div><div class="field-value">' + list(record.gold_skills, "") + "</div></div>" +
      '<div class="field"><div class="field-label">Negative</div><div class="field-value">' + list(record.negative_skills, "") + "</div></div>" +
      '<div class="field"><div class="field-label">Score Ranking</div>' + renderRanking(record) + "</div>" +
      '<div class="field"><div class="field-label">Metrics</div><pre>' + esc(JSON.stringify(record.metrics || {}, null, 2)) + "</pre></div>" +
      '<div class="field"><div class="field-label">Raw JSON</div><pre>' + esc(JSON.stringify(record.raw || {}, null, 2)) + "</pre></div>";
  }

  function bindSorting() {
    document.querySelectorAll("th[data-sort]").forEach((heading) => {
      heading.addEventListener("click", () => {
        const key = heading.dataset.sort;
        if (state.sortKey === key) state.sortDir *= -1;
        else {
          state.sortKey = key;
          state.sortDir = 1;
        }
        renderTable();
      });
    });
  }

  $("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderTable();
  });

  renderSourceLine();
  renderMetrics();
  renderFilters();
  bindSorting();
  renderTable();
}());
"""


def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"malformed JSONL in {path} at line {line_number}: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"expected object in {path} at line {line_number}")
            records.append((line_number, record))
    if not records:
        raise ValueError(f"no result records found in {path}")
    return records


def _normalize_record(
    record: dict[str, Any], path: Path, line_number: int
) -> dict[str, Any]:
    _validate_record(record, path, line_number)
    selected = _string_list_field(record, "selected_skill_ids", path, line_number)
    gold = _string_list_field(record, "gold_skills", path, line_number)
    negative = _string_list_field(record, "negative_skills", path, line_number)
    normalized = {
        "task_id": record["task_id"],
        "router": record["router"],
        "split": record.get("split", ""),
        "category": record.get("category", ""),
        "difficulty": record.get("difficulty", ""),
        "prompt": record.get("prompt", ""),
        "selected_skill_ids": selected,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": float(record["latency_ms"]),
        "scores": record.get("scores", {}),
        "raw": dict(record),
    }
    normalized["metrics"] = _record_metrics(
        record, selected, gold, negative, path, line_number
    )
    return normalized


def _validate_record(record: dict[str, Any], path: Path, line_number: int) -> None:
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        raise ValueError(
            f"missing fields in {path} at line {line_number}: {', '.join(missing)}"
        )
    for field in ("task_id", "router"):
        if not isinstance(record[field], str):
            raise ValueError(
                f"field {field!r} must be a string in {path} at line {line_number}"
            )
    for field in ("split", "category", "difficulty"):
        if field in record and not isinstance(record[field], str):
            raise ValueError(
                f"field {field!r} must be a string in {path} at line {line_number}"
            )
    if "prompt" in record and not isinstance(record["prompt"], str):
        raise ValueError(f"field 'prompt' must be a string in {path} at line {line_number}")
    for field in ("selected_skill_ids", "gold_skills", "negative_skills"):
        _string_list_field(record, field, path, line_number)
    if _finite_number(record["latency_ms"]) is None:
        raise ValueError(f"field 'latency_ms' must be finite in {path} at line {line_number}")


def _string_list_field(
    record: dict[str, Any], field: str, path: Path, line_number: int
) -> list[str]:
    value = record[field]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(
            f"field {field!r} must be a list of strings in {path} at line {line_number}"
        )
    return list(value)


def _record_metrics(
    record: dict[str, Any],
    selected: list[str],
    gold: list[str],
    negative: list[str],
    path: Path,
    line_number: int,
) -> dict[str, float]:
    return {
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


def _metric_or(
    record: dict[str, Any], field: str, fallback: float, path: Path, line_number: int
) -> float:
    if field not in record:
        return float(fallback)
    value = _finite_number(record[field])
    if value is None:
        raise ValueError(f"field {field!r} must be finite in {path} at line {line_number}")
    return value


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return numeric


def _failure_tags(metrics: dict[str, float], selected: list[str]) -> list[str]:
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
    scores = record.get("scores")
    if not isinstance(scores, dict):
        return []
    rows: list[dict[str, float | str]] = []
    for skill_id, value in scores.items():
        score = _finite_number(value)
        if isinstance(skill_id, str) and score is not None:
            rows.append({"skill_id": skill_id, "score": score})
    return sorted(rows, key=lambda row: (-float(row["score"]), str(row["skill_id"])))


def _mean_summary_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        field: round(sum(row[field] for row in rows) / len(rows), 6)
        for field in SUMMARY_FIELDS
    }


def _sorted_unique(values: Any) -> list[str]:
    return sorted({value for value in values if value})
