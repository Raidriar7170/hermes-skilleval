# Phase 8 Static Dashboard Design

## Goal

Phase 8 adds a static, self-contained HTML dashboard for interactive inspection of
existing SkillEval router runs. The dashboard should make the committed benchmark
artifacts easier to browse without rerunning benchmarks or starting a web server.

The first target artifact is:

```bash
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

## Scope

The dashboard generator reads existing `results.jsonl` files and writes one HTML
file with embedded CSS, JavaScript, and JSON data. The file must work when opened
directly in a browser from disk.

In scope:

- Load all child directories under `--runs` that contain `results.jsonl`.
- Preserve the child directory name as the run label.
- Compute run-level summary metrics from record fields when present, with
  fallback metric calculation for standard SkillEval records.
- Render the confirmed MVP layout: metric strip, filter sidebar, task table, and
  selected-task inspector.
- Provide client-side search, filters, sortable columns, and task selection.
- Include failure tags for `recall-miss`, `negative-hit`, `abstained`, and
  `low-selection`.
- Add a CLI command named `dashboard`.
- Commit a demo HTML artifact and update README Roadmap/docs references.

Out of scope for Phase 8:

- A live server, Streamlit app, FastAPI service, or frontend build pipeline.
- Re-running benchmark evaluations from the dashboard command.
- Editing benchmark results, skill metadata, or task files from the page.
- Cross-run diff algorithms beyond side-by-side filtering and sorting.
- External assets, CDN dependencies, or network calls.

## User Experience

The dashboard opens to a work-focused benchmark inspection view.

Top bar:

- Title: `Hermes SkillEval Dashboard`.
- Source path and generated timestamp.
- Global search input matching task id, router, selected skills, gold skills,
  negative skills, category, difficulty, and prompt text when present.

Metric strip:

- Shows one card per loaded run.
- Each card includes task count, Recall@5, MRR, NDCG@5, Negative Hit Rate,
  Abstention Rate, Selection Rate@5, and average latency.

Filter sidebar:

- Router/run selector.
- Split selector.
- Category selector.
- Difficulty selector.
- Failure type selector.

Task table:

- One row per JSONL record.
- Columns: run, task id, split, category, difficulty, Recall@5, Negative Hit
  Rate, Abstention Rate, selected skills, and failure tags.
- Clicking a row populates the inspector.
- Numeric columns are sortable.

Task inspector:

- Task id, router/run, split/category/difficulty, and failure tags.
- Prompt excerpt if `prompt` is available in the record.
- Gold skills, negative skills, and selected skills.
- Score ranking when `scores` is available, sorted by descending score.
- Raw JSON block for auditability.

The visual style should stay consistent with an operational evaluation tool:
compact, scannable, restrained, and optimized for repeated inspection.

## Data Model

Add `src/hermes_skilleval/dashboard.py`.

Core structures:

- `DashboardRun`: run label, source `results.jsonl` path, summary metrics, and
  records.
- `DashboardRecord`: normalized record with run label, metrics, failure tags,
  selected/gold/negative skills, optional prompt/category/difficulty/split, and
  optional score ranking.
- `DashboardPayload`: source directory, generated timestamp, runs, records, and
  filter option lists.

The module should expose:

- `build_dashboard_payload(runs_path: Path | str) -> DashboardPayload`
- `render_dashboard_html(payload: DashboardPayload) -> str`
- `write_dashboard(runs_path: Path | str, output_path: Path | str) -> None`

The implementation may use dataclasses internally, but the renderer should
serialize a plain JSON-compatible dictionary into the HTML.

## Metrics And Failure Tags

For each record, use existing metric fields when available:

- `recall_at_5`
- `mrr`
- `ndcg_at_5`
- `negative_hit_rate`
- `abstention_rate`
- `selection_rate_at_5`
- `latency_ms`

When a derived metric is missing and the standard fields are present
(`selected_skill_ids`, `gold_skills`, `negative_skills`), calculate it using the
existing metric helpers.

Failure tags:

- `recall-miss`: `recall_at_5 < 1.0`
- `negative-hit`: `negative_hit_rate > 0.0`
- `abstained`: no selected skills or `abstention_rate > 0.0`
- `low-selection`: `selection_rate_at_5 < 1.0`

These tags are descriptive diagnostics, not acceptance criteria.

## CLI

Add:

```bash
skilleval dashboard --runs <runs-dir> --output <dashboard.html>
```

Behavior:

- `--runs` is required and must point to a directory.
- The command finds immediate child directories with `results.jsonl`.
- If no runs are found, it exits with the existing CLI error handling path and a
  clear message.
- Parent directories for `--output` are created automatically.
- On success, print `Wrote dashboard to <output>`.

## Error Handling

The dashboard reader should fail clearly for:

- Missing `--runs` directory.
- No child `results.jsonl` files.
- Malformed JSONL.
- Records missing required SkillEval fields needed for inspection.
- Non-list skill fields or non-numeric metric fields.

The CLI should reuse the existing `ValueError`, `OSError`, and
`json.JSONDecodeError` handling in `main`.

## Testing

Add `tests/test_dashboard.py` for unit coverage:

- Loads multiple run directories and preserves run labels.
- Computes summary metrics from minimal records.
- Falls back to metric helpers when derived metric fields are absent.
- Assigns failure tags correctly.
- Renders a self-contained HTML document with embedded payload and no external
  script or stylesheet references.
- Raises `ValueError` when no runs are available.

Extend `tests/test_cli_smoke.py`:

- `skilleval dashboard` writes an HTML file for a fixture run directory.
- The CLI returns code `2` for an empty runs directory.

Add `tests/test_phase8_artifacts.py` after generating the demo artifact:

- Confirms the dashboard HTML exists.
- Confirms it embeds the expected Phase 7B run labels.
- Confirms there are no `http://`, `https://`, CDN, or external script/style
  references.

Full verification before completion:

```bash
pytest -q
ruff check .
mypy src tests
python -m pip install -e . --dry-run
```

## Documentation And Demo Artifact

Create:

- `docs/phase8.md`
- `docs/demo/phase8-static-dashboard/dashboard.html`

Update:

- `README.md`: mark the Web dashboard Roadmap item complete and add the CLI
  usage snippet.
- `docs/demo/README.md`: list the dashboard artifact.
- `docs/resume.md`: add Phase 8 as a compact project milestone.

## Acceptance Criteria

Phase 8 is complete when:

- The dashboard command generates a static self-contained HTML file from
  committed run results.
- The page supports search, filtering, sorting, row selection, score inspection,
  and raw JSON inspection without a server.
- The Phase 8 demo artifact is committed.
- README Roadmap marks `Web dashboard for interactive failure inspection` as
  complete.
- Tests, lint, type checking, and editable install dry-run all pass.
