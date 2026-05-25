# Phase 7B Cross-Encoder Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish a reproducible dev-split cross-encoder acceptance calibration layer and Phase 7B evidence package.

**Architecture:** Add a pure calibration module that consumes existing rank-only cross-encoder JSONL records, fits score and margin thresholds on the dev split, and applies the frozen policy to test records. Wire the calibration into the CLI and router so offline artifact generation and live evaluation share the same acceptance semantics.

**Tech Stack:** Python 3.11, `pytest`, existing `hermes_skilleval` CLI, JSONL benchmark artifacts.

---

### Task 1: Verify Existing Calibration Behavior

**Files:**
- Modify: `src/hermes_skilleval/calibration.py`
- Test: `tests/test_cross_encoder_calibration.py`

- [x] **Step 1: Write tests for dev-only fitting, score thresholding, margin thresholding, selection-rate caps, and JSON round trip**

The current test file covers:

```python
def test_fit_cross_encoder_calibration_uses_dev_split_and_controls_negatives():
    ...

def test_apply_cross_encoder_calibration_filters_by_score_and_margin():
    ...

def test_fit_cross_encoder_calibration_can_cap_selection_rate():
    ...

def test_cross_encoder_calibration_round_trips_json(tmp_path):
    ...
```

- [x] **Step 2: Run calibration tests**

Run: `pytest tests/test_cross_encoder_calibration.py -q`

Expected: all calibration tests pass.

### Task 2: Wire Calibration Into Router And CLI

**Files:**
- Modify: `src/hermes_skilleval/routers/cross_encoder.py`
- Modify: `src/hermes_skilleval/cli.py`
- Test: `tests/test_cross_encoder_router.py`
- Test: `tests/test_cli_smoke.py`

- [x] **Step 1: Add router tests for calibrated top-margin acceptance**

The router tests should prove a narrow top-1/top-2 margin abstains and a clear margin accepts the top candidate:

```python
def test_cross_encoder_calibrated_acceptance_requires_top_margin():
    ...

def test_cross_encoder_calibrated_acceptance_keeps_high_margin_candidates():
    ...
```

- [x] **Step 2: Add CLI tests for calibration JSON loading and calibration artifact generation**

The CLI smoke tests should cover:

```python
def test_cli_eval_cross_encoder_accepts_calibration_file(tmp_path, monkeypatch):
    ...

def test_cli_calibrate_cross_encoder_writes_calibration_and_test_results(tmp_path):
    ...
```

- [x] **Step 3: Run targeted router and CLI tests**

Run: `pytest tests/test_cross_encoder_router.py tests/test_cli_smoke.py -q`

Expected: all targeted tests pass.

### Task 3: Generate Phase 7B Artifacts

**Files:**
- Create/Update: `docs/demo/phase7b-cross-encoder-calibration/strict-calibration.json`
- Create/Update: `docs/demo/phase7b-cross-encoder-calibration/balanced-calibration.json`
- Create/Update: `docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test/results.jsonl`
- Create/Update: `docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test/report.md`
- Create/Update: `docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test/results.jsonl`
- Create/Update: `docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test/report.md`

- [x] **Step 1: Rebuild strict calibration**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/strict-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.3
```

Expected: calibration JSON and 30 test records are written.

- [x] **Step 2: Rebuild balanced calibration**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/balanced-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.4
```

Expected: calibration JSON and 30 test records are written.

- [x] **Step 3: Rebuild reports**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli report \
  --runs docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test

PYTHONPATH=src python -m hermes_skilleval.cli report \
  --runs docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test
```

Expected: both markdown reports match the regenerated results.

### Task 4: Document Phase 7B Results

**Files:**
- Create: `docs/phase7b.md`
- Create: `docs/demo/phase7b-cross-encoder-calibration/comparison.md`
- Modify: `README.md`

- [x] **Step 1: Build a same-split comparison**

Generate a comparison over the 30 test records for:

- `gated-minilm-contrastive-test`
- `cross-encoder-rank-only-test`
- `cross-encoder-calibrated-strict-test`
- `cross-encoder-calibrated-balanced-test`

Run:

```bash
PYTHONPATH=src python - <<'PY'
import json
from pathlib import Path
from hermes_skilleval.comparison import write_comparison_report
from hermes_skilleval.report import write_markdown_report

root = Path("docs/demo/phase7b-cross-encoder-calibration")
sources = {
    "gated-minilm-contrastive-test": Path(
        "docs/demo/phase7a-cross-encoder/gated-minilm-contrastive/results.jsonl"
    ),
    "cross-encoder-rank-only-test": Path(
        "docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl"
    ),
}
result_paths = {}
for label, source in sources.items():
    out_dir = root / label
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.jsonl"
    records = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    test_records = [record for record in records if record.get("split") == "test"]
    out_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in test_records),
        encoding="utf-8",
    )
    write_markdown_report(out_path, out_dir / "report.md")
    result_paths[label] = out_path

result_paths.update(
    {
        "cross-encoder-calibrated-balanced-test": root
        / "cross-encoder-calibrated-balanced-test"
        / "results.jsonl",
        "cross-encoder-calibrated-strict-test": root
        / "cross-encoder-calibrated-strict-test"
        / "results.jsonl",
    }
)
write_comparison_report(result_paths, root / "comparison.md")
PY
```

- [x] **Step 2: Write `docs/phase7b.md`**

Include the commands, calibration files, same-split metrics, and interpretation:

- strict calibration controls negative hits best;
- balanced calibration preserves more Recall@5;
- this is threshold calibration, not Platt or isotonic probability calibration.

- [x] **Step 3: Update `README.md`**

Mark calibrated cross-encoder acceptance thresholds as complete and add Phase 7B to the demo table.

### Task 5: Final Verification

**Files:**
- Test all changed source and docs indirectly through CLI/report generation.

- [x] **Step 1: Run the full test suite**

Run: `pytest -q`

Expected: all tests pass.

- [x] **Step 2: Inspect git diff**

Run: `git diff --stat`

Expected: diff contains only Phase 7B calibration code, tests, docs, and artifacts.

### Task 6: Phase 7B Completion Polish

**Files:**
- Create: `tests/test_phase7b_artifacts.py`
- Modify: `src/hermes_skilleval/comparison.py`
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/resume.md`

- [x] **Step 1: Add artifact regression coverage**

Run: `pytest tests/test_phase7b_artifacts.py -q`

Expected: Phase 7B strict, balanced, rank-only, and contrastive baseline artifact metrics match the documented held-out test values.

- [x] **Step 2: Fix static typing checks**

Run: `mypy src tests`

Expected: mypy exits 0.
