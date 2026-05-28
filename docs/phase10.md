# Phase 10: Agent-in-the-loop Migration Evaluation

Phase 10 connects the Phase 9 migrated skill-library benchmark to a small
agent-in-the-loop evaluation layer. It asks whether routed skills would improve
an agent-style execution trace, rather than only reporting whether the router
retrieved a gold skill.

## Evaluation Setup

The committed artifacts use Phase 9's `hybrid` migration run as the source
router output and replay the same 12 migration tasks under three execution
conditions. These three execution conditions are:

- `no-skill`: the simulated agent receives no skill guidance.
- `routed-skill`: the simulated agent receives the skill IDs selected by the
  Phase 9 `hybrid` router.
- `oracle-skill`: the simulated agent receives each task's gold migrated skill
  labels.

This is deterministic and offline. It does not claim real browser execution,
Claude Code execution, or LLM judging. The goal is to preserve a replayable
trace contract that can later be replaced by a real agent adapter.

## Artifact Contract

Each run under `docs/demo/phase10-agent-in-the-loop/` contains:

- `results.jsonl`: dashboard-compatible task metrics plus agent-loop fields.
- `agent-traces.jsonl`: one trace per task using schema
  `phase10.agent-loop.v1`.
- `agent-loop-summary.json`: task count, success count, success rate, and mean
  evidence completion.
- `report.md`: a compact task-level execution summary.

The phase root also includes `comparison.md`, `dashboard.html`, and
`phase10-summary.json` for side-by-side inspection.

## Current Result

| Condition | Run | Agent Success Rate | Mean Evidence Completion |
|---|---|---:|---:|
| `no-skill` | `agent-loop-no-skill-hybrid` | 0.000 | 0.000 |
| `routed-skill` | `agent-loop-hybrid` | 0.750 | 0.750 |
| `oracle-skill` | `agent-loop-oracle-skill-hybrid` | 1.000 | 1.000 |

The gap between `no-skill` and `routed-skill` shows that the migrated skill
router provides useful execution guidance in this deterministic harness. The
gap between `routed-skill` and `oracle-skill` remains the actionable error
surface: three tasks still fail because the routed top-5 includes a negative
skill for the task.

## Reproduce

```bash
skilleval run-agent-loop \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --condition routed-skill \
  --output-dir runs/phase10-agent-loop/hybrid
```

Use `--condition no-skill` and `--condition oracle-skill` for the two control
runs.
