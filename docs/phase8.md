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
