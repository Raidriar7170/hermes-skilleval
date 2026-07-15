## ADDED Requirements

### Requirement: Pilot-002 reuses the exact frozen pilot-001 evidence
The system SHALL create pilot
`router-v2-v4-confusion-mined-pilot-002-eval-replay` with a canonical manifest
that changes only pilot ID, attempt token, evaluation code commit, output
namespace, and replacement reason. It SHALL reuse the exact accepted-pairs,
data-manifest, mining rows and manifest, held-out-labels, run-pack inputs, Arm
B/C model paths and manifests and file hashes, base MiniLM revision and file
manifest, seeds, evaluation query order, metric definitions, and success gates
from pilot-001.

#### Scenario: Exact replay manifest is frozen
- **WHEN** every reused path, SHA-256 value, seed, order, metric, and gate matches pilot-001 and the five permitted replacement fields identify pilot-002
- **THEN** the manifest validates before attempt consumption

#### Scenario: Any frozen artifact drifts
- **WHEN** any checkpoint is missing or any reused byte, hash, path, seed, order, metric, or threshold differs
- **THEN** replay stops before attempt consumption and SHALL NOT retrain, rebuild, substitute, or repair the artifact

### Requirement: Replacement truth remains explicit and conservative
The pilot manifest SHALL record
`replacement_reason=INFRASTRUCTURE_FAILURE_BEFORE_INFERENCE`,
`reuses_frozen_training_artifacts_from_pilot_001=true`,
`pilot_001_metrics_observed=false`, `review_mode=MODEL_ONLY_PILOT`,
`human_reviewer_count=0`, `blind_v2_run=false`, `production_ready=false`,
`release_eligible=false`, and `router_decision=KEEP_BASELINE` until the gate
finishes.

#### Scenario: Pre-gate truth is valid
- **WHEN** pilot-002 is created or evaluation has not completed every gate
- **THEN** all required truth fields are present with exact types and `router_decision=KEEP_BASELINE`

#### Scenario: A claim is inflated
- **WHEN** an artifact implies human review, blind-v2 execution, production readiness, release eligibility, or pre-gate promotion
- **THEN** validation fails

### Requirement: Training artifacts and replay outputs are isolated
The runner SHALL read the frozen run pack and Arm B/C artifacts only from the
pilot-001 training execution root, SHALL resolve Arm A to the exact frozen
MiniLM snapshot, and SHALL write the attempt ledger and evaluation artifacts
only under a new fixed pilot-002 `0700` output namespace.

#### Scenario: Frozen artifacts are reused without training
- **WHEN** preflight verifies all run-pack, run-summary, model-manifest, model-file, and base-model hashes
- **THEN** one evaluation may start without invoking training or a run-pack builder

#### Scenario: Roots or topology are unsafe
- **WHEN** the training root, output root, model topology, permissions, or namespace differs from the authority
- **THEN** evaluation stops before attempt consumption

### Requirement: Pilot-002 has one terminal evaluation attempt
The system SHALL derive a new attempt token bound to pilot-002, its replacement
reason, exact frozen inputs, clean evaluation code commit, and output namespace.
It SHALL permit only attempt number 1 and SHALL treat every post-marker failure
as terminal without an attempt-2.

#### Scenario: The single attempt starts
- **WHEN** all pre-attempt validation passes and no pilot-002 ledger or artifacts exist
- **THEN** the runner atomically writes the attempt-1 marker before reading evaluation inputs or performing inference

#### Scenario: An attempt already exists or fails
- **WHEN** any pilot-002 attempt marker, terminal, staging, recovery, or published artifact exists, or the started attempt fails
- **THEN** no retry or second attempt is permitted and the decision remains `KEEP_BASELINE`

### Requirement: Reporting and decision use the unchanged preregistration
The one attempt SHALL report per-arm and per-seed Recall@1/5, MRR, NDCG@5,
Negative Hit Rate@1/5, first-negative rank, p50/p95 latency, arithmetic
mean/sample standard deviation, paired wins/losses, failure slices, and raw
counts for 16 held-out positives and 9 supported negative labels. Arm C versus
paired Arm A SHALL be the only decision comparison.

#### Scenario: Every gate passes
- **WHEN** mean and every-seed Recall@5 deltas are `>=0.00`, MRR and NDCG@5 deltas are `>=-0.01`, NHR@5 mean delta is `<=-0.05` with every seed `<=0.00`, and mean and every-seed p95 latency ratios are `<=1.20`
- **THEN** the only decision is `ROUTER_V2_PILOT_IMPROVED`

#### Scenario: Any gate fails
- **WHEN** any preregistered mean or per-seed threshold fails
- **THEN** the only decision is `KEEP_BASELINE`

#### Scenario: Evaluation scope or selection expands
- **WHEN** a threshold changes, a seed is selected post hoc, a rerun is attempted, or blind-v2, new mining, new review, new data, a new checkpoint, or pilot-003 is introduced
- **THEN** validation fails and `KEEP_BASELINE` remains authoritative

### Requirement: Public wording is raw-count-first and bounded
README, `docs/resume.md`, and the Human Brief SHALL prefer raw counts such as
Recall@5 `x/16` and negative hit `a/9 -> b/9`, and SHALL disclose
`MODEL_ONLY_PILOT / human_reviewer_count=0 / non-SOTA / non-production /
blind-v2 not run`.

#### Scenario: Documentation matches the evidence
- **WHEN** the completed evaluation and gate decision are published
- **THEN** rates are accompanied by raw counts and all limitations remain visible

#### Scenario: Documentation overclaims
- **WHEN** wording implies human validation, SOTA, production readiness, release, router promotion, or blind-v2 generalization
- **THEN** documentation validation fails
