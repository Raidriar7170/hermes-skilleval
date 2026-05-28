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
- Judge pass: `judge_score >= 0.75` with no blocking penalties.

## Dashboard Compatibility

The judge writes `results.jsonl` files so existing dashboard and comparison
tools can inspect the Phase 11 runs. In these dashboard-compatible results,
the Recall and Negative metric fields are judge proxy fields derived from
`judge_pass`, not the original router gold/negative-skill metrics from Phase 9
or Phase 10 routing results.

Use `judge-results.jsonl` and `judge-summary.json` for the authoritative
Evidence Judge calibration fields: `judge_score`, `evidence_score`,
`judge_pass_rate`, `judge_status`, and `penalties`.

## Artifacts

Artifacts live under `docs/demo/phase11-evidence-judge-calibration/`.
Each run includes `judge-results.jsonl`, `results.jsonl`, `judge-summary.json`,
and `judge-rubric.md`.

| Condition | Run | Judge Pass Rate | Mean Judge Score | Mean Evidence Score |
|---|---|---:|---:|---:|
| `no-skill` | `judge-agent-loop-no-skill-hybrid` | 0.000 | 0.000 | 0.000 |
| `routed-skill` | `judge-agent-loop-hybrid` | 0.750 | 0.750 | 0.750 |
| `oracle-skill` | `judge-agent-loop-oracle-skill-hybrid` | 1.000 | 1.000 | 1.000 |

## Reproduce

Use `skilleval judge-agent-loop` against any Phase 10 `agent-traces.jsonl`:

```bash
skilleval judge-agent-loop \
  --traces docs/demo/phase10-agent-in-the-loop/agent-loop-hybrid/agent-traces.jsonl \
  --output-dir runs/phase11-evidence-judge/hybrid \
  --run-label judge-agent-loop-hybrid
```
