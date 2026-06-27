## 1. OpenSpec And Scope

- [x] 1.1 Create change `external-matrix-generalization` with proposal,
  design, tasks, and `external-evaluation-matrix` spec.
- [x] 1.2 Keep PR-3 limited to frozen external matrix planning, scoring
  orchestration, and diagnostics; do not implement training, threshold tuning,
  scored-set hard-negative mining, model inference, embeddings, rerankers,
  live-agent runtime, release promotion, router promotion, or Hermes Negative
  Hit Rate without explicit negative labels.

## 2. Frozen Plan And Field Views

- [x] 2.1 Add RED tests for frozen evaluation plan generation before scored
  matrix output, including run ID, seed, git commit, dirty summary, adapter
  provenance, frozen router configs, field views, tiers, subset sizes, and
  output paths.
- [x] 2.2 Implement frozen plan data structures, writer, and validation
  helpers using the PR-1 adapter/provenance surface.
- [x] 2.3 Add RED tests for `name_only`, `metadata`, and `full_body` field
  view builders.
- [x] 2.4 Implement versioned deterministic field view builders for SkillRouter
  skill records.

## 3. Official Matrix Scoring

- [x] 3.1 Add RED tests that a matrix run consumes an existing frozen plan and
  invokes PR-2 official scoring for full Easy/Hard tiers.
- [x] 3.2 Implement matrix runner orchestration for frozen prediction files
  without running routers, embeddings, rerankers, models, training, live agents,
  or release promotion.
- [x] 3.3 Add RED tests that official results and Hermes diagnostics are
  separated and that missing predictions follow PR-2 scorer parity semantics.

## 4. Hermes Stress Diagnostics

- [x] 4.1 Add RED tests for deterministic candidate subset sampling that always
  includes all unique selected GT skills before distractors.
- [x] 4.2 Add RED tests for `UNAVAILABLE` subset output when the target size is
  smaller than the selected GT union.
- [x] 4.3 Implement candidate subset sampling with
  `sha256("20260625:" + skill_id)` distractor ordering and subset hashes.
- [x] 4.4 Add RED tests and implementation for Hermes candidate-pool stress
  diagnostics that never appear as official SkillRouter results.

## 5. Confidence Intervals And Splits

- [x] 5.1 Add RED tests for paired bootstrap confidence intervals using
  task-level paired metric deltas, seed `20260625`, and deterministic output.
- [x] 5.2 Implement paired bootstrap confidence interval helpers.
- [x] 5.3 Add RED tests for held-out-skill split generation using task-skill
  connected components.
- [x] 5.4 Implement held-out-skill split generation and overlap assertions.
- [x] 5.5 Add RED tests for held-out-source field-level `UNAVAILABLE` when
  source metadata is insufficient.
- [x] 5.6 Implement held-out-source split diagnostics for sufficient metadata
  and `UNAVAILABLE` output for insufficient metadata.

## 6. Overlap Scaffold And CLI

- [x] 6.1 Add RED tests for SkillRouter/SkillsBench overlap scaffold with
  exact ID overlap, normalized text hash overlap, and high-similarity
  diagnostic placeholder.
- [x] 6.2 Implement overlap report scaffold that supports missing live tasks as
  field-level `UNAVAILABLE`.
- [x] 6.3 Add scoped CLI commands for plan generation and matrix execution.
- [x] 6.4 Add CLI tests for frozen plan generation and matrix execution on the
  tiny fixture.

## 7. Documentation And Human Brief

- [x] 7.1 Add concise Chinese Human Brief for PR-3 with status, changed files,
  verification, limits, and next step.
- [x] 7.2 Update v0.3 docs only as needed to link PR-3 artifacts without
  changing historical phase docs or release logic.

## 8. Validation

- [x] 8.1 Run focused external matrix tests.
- [x] 8.2 Run `python -m pytest -q`.
- [x] 8.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 8.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 8.5 Run `git diff --check`.
- [x] 8.6 Run v0.3 YAML parse check.
- [x] 8.7 Run CRLF/new-file line-ending check.
