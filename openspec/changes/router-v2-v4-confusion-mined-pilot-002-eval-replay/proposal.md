## Why

Pilot `router-v2-v4-confusion-mined-pilot-001` consumed its only evaluation
attempt on an infrastructure failure before inference, so it produced no
held-out metric. The repaired Arm A materialization has now passed a separate
seven-model non-heldout real-load smoke, allowing one new pilot ID to replay
only the frozen evaluation without retraining or changing any input or gate.

## What Changes

- Add pilot `router-v2-v4-confusion-mined-pilot-002-eval-replay` with
  `replacement_reason=INFRASTRUCTURE_FAILURE_BEFORE_INFERENCE` and an exact
  reuse manifest for pilot-001 training data, mining evidence, run pack,
  held-out labels, model artifacts, seeds, query order, metrics, and gates.
- Separate the new evaluation output namespace and attempt token from the
  frozen pilot-001 training execution root so the existing Arm B/C snapshots
  and exact Arm A revision are reused rather than rebuilt or retrained.
- Permit exactly one pilot-002 evaluation attempt after fail-closed hash and
  manifest validation, and report every preregistered per-seed, aggregate,
  paired, latency, negative-label, raw-count, and failure-slice result.
- Apply the existing Arm C versus Arm A gates without threshold changes,
  best-seed selection, or reruns, producing only
  `ROUTER_V2_PILOT_IMPROVED` when every gate passes and `KEEP_BASELINE`
  otherwise.
- Update README, resume guidance, and the L2 Human Brief with raw counts and
  explicit `MODEL_ONLY_PILOT`, zero-human, non-SOTA, non-production, and
  blind-v2-not-run limitations.
- Record that on 2026-07-15 the user explicitly ratified pilot-002 and the
  existing Human Brief and existing test scope in PR #38, without counting the
  ratification as human review and with `new_tests_authorized=false`. Retain the immutable pilot manifest and attempt
  ledger, add a self-sealed truth erratum for its four missing model-only truth
  fields, and retain the exact 144-row route artifact with a seven-row audit
  manifest computed from the original artifact bytes.
- Do not retrain, rebuild the run pack, mine data, perform another review,
  access blind-v2, create pilot-003, release, promote, deploy, merge, or
  archive.

## Capabilities

### New Capabilities

- `router-v2-confusion-mined-pilot-eval-replay`: Defines the exact frozen-artifact reuse manifest, isolated one-attempt replay, preregistered reporting and gates, and conservative claim boundary for pilot-002.

### Modified Capabilities

None.

## Impact

- Adds a narrow replay authority and pilot manifest around
  `router_v2_pilot_evaluation_runner.py` and its CLI without changing the
  training implementation or frozen model artifacts.
- Writes evaluation outputs only to a new fixed local `0700` namespace and
  commits only small evidence and documentation artifacts to the repository.
- Preserves pilot-001 as consumed with `pilot_001_metrics_observed=false` and
  keeps `router_decision=KEEP_BASELINE` until the pilot-002 gate completes.
- The post-attempt repair changes no runner, test, frozen manifest, attempt
  marker, terminal, summary, metric, or decision. It adds retention and audit
  evidence only; final review and any post-repair commit/push/CI remain separate
  pending actions.
