## Context

PR-1 introduced the SkillRouter external adapter/provenance boundary and PR-2
introduced official SkillRouter scorer parity for already-ranked predictions.
PR-3 builds the frozen zero-shot matrix layer on top of those stable surfaces:
it prepares evaluation plans, builds deterministic field-view candidate text,
records frozen router configs, runs only precomputed/frozen prediction inputs,
and emits official SkillRouter reports plus separate Hermes diagnostics.

The v0.3 protocol requires scored labels to remain evaluation-only. The matrix
must not train, tune thresholds, select routers after seeing results, run live
agents, promote release artifacts, or compute Hermes Negative Hit Rate unless
explicit negative labels exist.

## Goals / Non-Goals

**Goals:**

- Generate a frozen evaluation plan before any scored matrix report.
- Reuse the PR-1 adapter for tasks, relevance, skill pools, and provenance.
- Reuse the PR-2 scorer for full Easy/Hard official SkillRouter scoring.
- Add deterministic field views: `name_only`, `metadata`, and `full_body`.
- Add deterministic candidate subset sampling for Hermes stress diagnostics.
- Add paired bootstrap confidence intervals over task-level paired deltas.
- Add held-out-skill split generation using task-skill connected components.
- Add held-out-source diagnostics that fail closed to field-level
  `UNAVAILABLE` when source metadata is insufficient.
- Add a SkillRouter/SkillsBench overlap scaffold without requiring live task
  selection.

**Non-Goals:**

- No router training, threshold tuning, hard-negative mining from scored data,
  model inference, embedding generation, reranking, live-agent runtime, release
  promotion, or router promotion.
- No changes to PR-1 adapter/provenance APIs or PR-2 official scorer semantics
  unless a narrow compatibility bug is proven by tests.
- No commitment of full external datasets, model checkpoints, embedding caches,
  credentials, raw traces, or unredacted logs.

## Decisions

1. **Frozen plan as the matrix entry point.** The matrix runner consumes a
   plan JSON produced by a separate plan command. The plan records run ID,
   git commit, dirty summary, seed, data provenance with data file hashes,
   frozen router configs with prediction file hashes, field views, tiers,
   stress subset sizes, bootstrap settings, and output paths. The runner
   recomputes those hashes before scoring and fails closed on drift.

2. **Prediction-input matrix, not live router execution.** PR-3 compares frozen
   routers/configs by consuming ranked prediction files declared in the plan.
   It does not import model libraries or compute embeddings. This keeps the
   change bounded and prevents accidental tuning or inference on final labels.

3. **Config identity is separate from router identity.** Official matrix
   reports are keyed by `config_id`, defaulting to `{router_id}__{field_view}`
   when not provided. This preserves field-view ablations for the same router
   without overwriting reports.

4. **Official results delegate to PR-2.** Full Easy/Hard official scoring calls
   the PR-2 scorer for each frozen router/config and field view. Hermes
   diagnostics wrap those official outputs but do not modify metric formulas.

5. **Stress subsets are diagnostics only.** Candidate subsets use the protocol
   rule: include all selected GT skills first, then add distractors sorted by
   `sha256("20260625:" + skill_id)`. If a target size cannot contain the GT
   union, the subset result is field-level `UNAVAILABLE` with a reason.

6. **Split and overlap reports are deterministic scaffolds.** Held-out-skill
   split generation builds connected components over task and selected GT skill
   nodes. Held-out-source runs only when enough source metadata exists.
   SkillRouter/SkillsBench overlap reporting starts with exact IDs and
   normalized text hashes, leaving high-similarity diagnostics as structured
   placeholders.

## Risks / Trade-offs

- **Risk: frozen-router comparison is mistaken for live inference.** →
  Mitigation: require prediction files in frozen configs, document no
  embeddings/model inference, and test that plan/run paths do not instantiate
  router runtimes.
- **Risk: stress subsets get described as official SkillRouter results.** →
  Mitigation: write stress outputs only under `hermes_diagnostics` and keep
  official Easy/Hard reports separate.
- **Risk: held-out-source metadata is incomplete.** → Mitigation: output
  `UNAVAILABLE` with a precise reason rather than fabricating a split.
- **Risk: bootstrap intervals imply independent samples.** → Mitigation: use
  paired task-level deltas for shared eligible tasks and record seed,
  iteration count, and metric names.

## Migration Plan

PR-3 adds new modules, CLI commands, tests, OpenSpec artifacts, and a Human
Brief. Existing PR-1 validation and PR-2 scorer commands remain stable.
Rollback is removal of the new matrix modules/CLI surface and OpenSpec change
without altering adapter or scorer behavior.

## Open Questions

- Which real frozen router prediction files will be used for a full external
  matrix outside CI remains a run-configuration decision. PR-3 only defines the
  deterministic local machinery and tiny-fixture proof path.
