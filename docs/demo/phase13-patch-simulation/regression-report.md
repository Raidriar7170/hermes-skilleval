# Phase 13 Patch Simulation

Offline deterministic patch simulation applies ranked metadata candidates to a shadow skill index and compares routing results against a baseline.

## Guard Summary

| Field | Value |
|---|---:|
| Guard status | PASS |
| Tasks | 12 |
| Applied candidates | 5 |
| Patched skills | browser-smoke-testing, slash-command-workflow, systematic-debugging, test-driven-development, visual-regression-review |
| Selection changes | 1 |
| Tasks with regressions | 0 |
| Tasks with improvements | 0 |

## Mean Metric Deltas

| Metric | Baseline | Shadow | Delta |
|---|---:|---:|---:|
| recall_at_5 | 1.000000 | 1.000000 | +0.000000 |
| mrr | 0.944444 | 0.944444 | +0.000000 |
| ndcg_at_5 | 0.958333 | 0.958333 | +0.000000 |
| negative_hit_rate | 0.250000 | 0.250000 | +0.000000 |
| negative_accepted_rate | 0.250000 | 0.250000 | +0.000000 |
| selection_rate_at_5 | 1.000000 | 1.000000 | +0.000000 |

## Route Diffs

| Task | Selection Changed | Regression Flags | Improvement Flags | Before Selected | After Selected | Applied Candidates |
|---|:-:|---|---|---|---|---|
| sp-verify-before-claim | True | - | - | verification-before-completion, systematic-debugging, evidence-backed-final, subagent-worker-protocol, test-driven-development | verification-before-completion, systematic-debugging, slash-command-workflow, test-driven-development, evidence-backed-final | - |

## Mutation Boundary

- Source `SKILL.md` files are not modified.
- The original `skills.json` input is not overwritten.
- `after_excerpt` is display-only and is not used as patch source.
