# Phase 16: Blind validation and release handoff

Phase 16 evaluates the Phase 14 fine-tuned embedding router on a new blind
real-skill migration task pack. The model is unchanged from Phase 14; this
phase adds new task coverage, a stricter comparison artifact, and a release
verification gate.

## Scope

The blind task pack lives under `benchmarks/blind-migration-tasks/` and contains
one held-out `test` task for each migrated real skill. These task IDs and
prompts were not used in Phase 14 training pairs.

Committed artifacts live under `docs/demo/phase16-blind-validation/`:

- `baseline-minilm/results.jsonl` and `report.md`
- `finetuned-embedding/results.jsonl` and `report.md`
- `regression-summary.json`
- `route-diffs.jsonl`
- `comparison.md`
- `dashboard.html`

## Result

The blind validation guard is `REVIEW_REQUIRED` over 16 blind tasks. The
fine-tuned router preserves Recall@5 but introduces two per-task regressions and
higher negative-skill selection than the MiniLM baseline.

| Metric | Baseline | Fine-tuned | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000000 | 1.000000 | +0.000000 |
| MRR | 1.000000 | 0.968750 | -0.031250 |
| NDCG@5 | 1.000000 | 0.976933 | -0.023067 |
| Negative Hit Rate | 0.750000 | 0.812500 | +0.062500 |
| Negative Accepted Rate | 0.750000 | 0.812500 | +0.062500 |

This means the Phase 14 fine-tuned router should not replace the baseline as a
default blind-validation policy. It remains useful as a trained artifact with
provenance, but the blind pack shows that deployment would need a calibration,
rollback, or selective-acceptance layer.

## Release Gate

`skilleval verify-release` checks required public artifacts, checkpoint absence,
sensitive strings, and affirmative overclaim wording. The gate allows explicit
negative disclaimers such as "does not establish SOTA" and excludes historical
planning notes under `docs/superpowers/` from text scans.

## Limitations

This remains a self-built Hermes-style skill-routing benchmark. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
