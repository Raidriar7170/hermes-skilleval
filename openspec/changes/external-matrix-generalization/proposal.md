## Why

PR-1 can validate real-shaped SkillRouter data and PR-2 can score ranked
predictions with official SkillRouter semantics, but v0.3 still needs a frozen
zero-shot evaluation matrix before any external routing claims are credible.
PR-3 creates that matrix boundary while keeping scored labels evaluation-only
and avoiding training, threshold tuning, live agents, release promotion, or
router selection after results are visible.

## What Changes

- Add a frozen evaluation plan artifact that must be generated before any
  scored matrix output.
- Compare only preregistered frozen routers/configs against the PR-1 adapter
  and PR-2 scorer surfaces.
- Add field views for `name_only`, `metadata`, and `full_body` skill text.
- Produce full Easy/Hard official scoring runs through the PR-2 scorer.
- Add separate Hermes diagnostics for candidate pool stress tests, including
  deterministic subsets that always include all selected GT skills.
- Add deterministic paired bootstrap confidence intervals over task-level
  paired router deltas.
- Add held-out-skill split generation using task-skill connected components.
- Add held-out-source diagnostics only when source metadata is sufficient;
  otherwise write a field-level `UNAVAILABLE` marker with a reason.
- Add a SkillRouter/SkillsBench overlap report scaffold for exact ID,
  normalized text hash, and future high-similarity diagnostics.
- Do not train, tune thresholds, mine hard negatives from scored data, run
  live agents, promote routers, or calculate Hermes Negative Hit Rate for
  SkillRouter without explicit negative labels.

## Capabilities

### New Capabilities

- `external-evaluation-matrix`: Defines frozen external routing matrix plans,
  field views, official SkillRouter scoring orchestration, Hermes stress
  diagnostics, paired confidence intervals, split reports, and overlap report
  scaffolding.

### Modified Capabilities

- None.

## Impact

- Affected code: new external matrix planning/running/report modules and
  scoped CLI commands in `src/hermes_skilleval/cli.py`.
- Affected tests: new deterministic fixture tests for frozen plans, field
  views, candidate subsets, bootstrap intervals, connected-component
  held-out-skill splits, held-out-source availability, and overlap scaffolds.
- Affected docs/OpenSpec: PR-3 OpenSpec artifacts and a concise Human Brief.
- Stable dependencies: PR-1 SkillRouter adapter/provenance and PR-2 official
  scorer APIs.
- Out of scope: model training, threshold tuning, scored-set hard-negative
  mining, embeddings/rerankers unless represented as frozen input configs, live
  agents, release promotion, raw external dataset commits, and Hermes Negative
  Hit Rate without explicit negative labels.
