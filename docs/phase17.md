# Phase 17: Calibrated Release Selector

Phase 17 converts the Phase 16 blind-validation artifacts into an explicit
default-router release decision. It does not retrain the fine-tuned embedding
router or modify Phase 16 route results.

## Scope

Committed artifacts live under
`docs/demo/phase17-calibrated-release-selector/`:

- `release-decision.json`
- `release-decision.md`
- `task-decisions.jsonl`
- `release-check-summary.json`

The selector reads:

- `docs/demo/phase16-blind-validation/regression-summary.json`
- `docs/demo/phase16-blind-validation/route-diffs.jsonl`

## Policy

The default release policy is intentionally conservative:

| Budget | Value |
|---|---:|
| `max_regressions` | 0 |
| `max_negative_hit_delta` | 0.0 |
| `max_negative_accepted_delta` | 0.0 |
| `min_recall_at_5_delta` | 0.0 |
| `min_mrr_delta` | 0.0 |
| `min_ndcg_at_5_delta` | 0.0 |

Aggregate release decisions are `APPROVE_CANDIDATE`, `KEEP_BASELINE`, and
`REVIEW_REQUIRED`. `NO_CHANGE` appears only as a task-level status in
`task-decisions.jsonl`; it is not an aggregate release decision.

## Result

The current Phase 17 artifact reports `KEEP_BASELINE`. The selected default router remains `baseline-minilm`, the candidate router is
`finetuned-embedding`, and `approved_for_default` is `false`.

The selector keeps the baseline because Phase 16 returned `REVIEW_REQUIRED`,
reported two per-task regressions, and showed worse negative-hit and ranking
metric deltas for the candidate:

| Metric delta | Value |
|---|---:|
| Recall@5 | +0.000000 |
| MRR | -0.031250 |
| NDCG@5 | -0.023067 |
| Negative Hit Rate | +0.062500 |
| Negative Accepted Rate | +0.062500 |

## Reproduce

```bash
PYTHONPATH=src python -m hermes_skilleval.cli select-release-router \
  --regression-summary docs/demo/phase16-blind-validation/regression-summary.json \
  --route-diffs docs/demo/phase16-blind-validation/route-diffs.jsonl \
  --output-dir docs/demo/phase17-calibrated-release-selector
```

Run the public artifact guard with the Phase 17 docs and artifact root included:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli verify-release \
  --public-root README.md \
  --public-root docs/phase16.md \
  --public-root docs/phase17.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root docs/demo/phase17-calibrated-release-selector \
  --required-path docs/demo/phase17-calibrated-release-selector/release-decision.json \
  --required-path docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl \
  --required-path docs/phase17.md \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase17-calibrated-release-selector/release-check-summary.json
```

## Limitations

This remains a self-built Hermes-style skill-routing release gate. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
