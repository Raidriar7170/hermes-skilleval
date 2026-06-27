## 1. OpenSpec And Scope

- [x] 1.1 Create change `skillrouter-official-scorer-parity`.
- [x] 1.2 Add proposal, design, tasks, and scorer parity spec.
- [x] 1.3 Keep PR-2 limited to official scorer parity; do not implement router
  execution, model inference, training, live-agent runtime, release promotion,
  or Hermes Negative Hit Rate.

## 2. Tests And Fixtures

- [x] 2.1 Add hand-computable predictions fixture for
  `skillrouter_eval_core_tiny`.
- [x] 2.2 Add RED tests for per-task nDCG@1/3/10, Hit@1, Precision@3,
  MRR@10, Recall@10/20/50, and FullCoverage@3/5/10.
- [x] 2.3 Add RED tests for per-tier all/single/multi aggregation and
  combined `by_tier.easy`/`by_tier.hard` output.
- [x] 2.4 Add RED tests for core mode generic-only filtering, core GT fallback,
  single mode filtering, and tier relevance filtering.
- [x] 2.5 Add CLI smoke test if scorer CLI is added.
- [x] 2.6 Add medium-difficulty task regression proving Easy/Hard evaluation
  tiers are candidate skill pools, not task difficulty groups.

## 3. Implementation

- [x] 3.1 Add scorer-only module that consumes adapter records and ranked
  predictions.
- [x] 3.2 Implement official metrics and slice aggregation.
- [x] 3.3 Add optional CLI command for scorer parity.
- [x] 3.4 Ensure no router/model/training/live-agent/release code is added.

## 4. Documentation And Human Brief

- [x] 4.1 Add concise Chinese Human Brief for PR-2.
- [x] 4.2 Document PR-2 as official scorer parity only.

## 5. Validation

- [x] 5.1 Run focused scorer tests.
- [x] 5.2 Run `python -m pytest -q`.
- [x] 5.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 5.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 5.5 Run `git diff --check`.
- [x] 5.6 Run v0.3 YAML parse check.
