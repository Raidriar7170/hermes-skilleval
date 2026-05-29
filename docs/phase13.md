# Phase 13: Patch Simulation & Regression Guard

Phase 13 applies the top ranked Phase 12 metadata patch candidates to a shadow
skill index, reruns deterministic hybrid routing, and compares the shadow run
against the Phase 9 baseline routes.

## Scope

The run is offline and deterministic. It does not modify source SKILL.md files,
does not overwrite the original migrated skills index, and does not claim
fine-tuning or learned model training.

## Inputs

`simulate-skill-patches` joins four audited inputs:

- Phase 12 ranked metadata patch candidates
- Phase 9 baseline route records
- migration task `task.yaml` and `prompt.md` files
- the migrated skills index

## Artifacts

Artifacts live under `docs/demo/phase13-patch-simulation/`:

- `shadow-skills.json`
- `shadow-results.jsonl`
- `route-diffs.jsonl`
- `regression-summary.json`
- `regression-report.md`

| Guard Status | Tasks | Applied Candidates | Tasks With Regressions | Tasks With Improvements |
|---|---:|---:|---:|---:|
| PASS | 12 | 5 | 0 | 0 |

Patched skill IDs:

- `browser-smoke-testing`
- `slash-command-workflow`
- `systematic-debugging`
- `test-driven-development`
- `visual-regression-review`

The committed run changed one selected route without changing aggregate
Recall@5, MRR, NDCG@5, Negative Hit Rate, or Selection Rate@5.

| Task | Before Selected | After Selected |
|---|---|---|
| `sp-verify-before-claim` | `verification-before-completion`, `systematic-debugging`, `evidence-backed-final`, `subagent-worker-protocol`, `test-driven-development` | `verification-before-completion`, `systematic-debugging`, `slash-command-workflow`, `test-driven-development`, `evidence-backed-final` |

## Reproduce

```bash
PYTHONPATH=src python -m hermes_skilleval.cli simulate-skill-patches \
  --ranked-patches docs/demo/phase12-skill-patch-ranking/ranked-patches.jsonl \
  --baseline-routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --router hybrid \
  --top-k 5 \
  --max-patches 5 \
  --output-dir docs/demo/phase13-patch-simulation
```

The command writes only the shadow skill index, shadow route records, route
diffs, summary JSON, and Markdown report under the requested output directory.
