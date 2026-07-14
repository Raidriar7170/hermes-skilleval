## ADDED Requirements

### Requirement: Mining is frozen, deterministic, and train-only
The miner SHALL rank all 16 frozen skills for exactly 64 frozen train positive
prompts using exact MiniLM revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, single-threaded CPU inference,
eight-decimal score quantization, and `skill_id` tie-breaking. It SHALL reject
calibration, non-blind-test, Phase 16, and blind-v2 mining inputs.

#### Scenario: Complete deterministic mining succeeds
- **WHEN** every train prompt records all scores, gold rank, top-three non-gold candidates, candidate rank, score margin, and exact model/source/prompt/skill hashes
- **THEN** the mining artifact and its manifest validate reproducibly

#### Scenario: A forbidden split or source is used
- **WHEN** mining reads a non-train row, a non-frozen skill snapshot, Phase 16, or blind-v2 evidence
- **THEN** validation fails before scoring or artifact publication

### Requirement: Only baseline-hard model-supported negatives are admitted
A training hard negative SHALL satisfy `candidate_rank <= 5` or
`gold_score-candidate_score <= 0.05` on quantized scores and SHALL have an
adjudicated `HARD_NEGATIVE_ROLE_SUPPORTED` opinion. The 29 previously disputed
rows SHALL be excluded. The final package SHALL contain 48-64 hard negatives
and maximize coverage across the 16 skills before adding canonical extras.

#### Scenario: Enough valid negatives survive
- **WHEN** at least 48 rows satisfy both the baseline-hard rule and model adjudication
- **THEN** deterministic selection admits 48-64 rows and reports per-skill distribution

#### Scenario: The first round is short
- **WHEN** fewer than 48 rows survive the initial top-confuser round
- **THEN** only new, previously unseen baseline-confusion candidates may be reviewed and the threshold remains unchanged

#### Scenario: The final valid pool is short
- **WHEN** all allowed supplement rounds still yield fewer than 48 valid rows
- **THEN** package construction and training fail closed without disputed or easy-negative padding

### Requirement: New candidate review is two-pass model-only adjudication
New train and held-out candidates SHALL receive exactly two isolated
`MODEL_ONLY_PILOT` passes with distinct run identities and one adjudication that
binds both pass-row hashes. Every object SHALL carry the exact model-only truth
block and bounded rationale. No third pass or human-review claim is permitted.

#### Scenario: Isolated review is complete
- **WHEN** both pass files cover the identical candidate identities without access to one another and adjudication binds both rows
- **THEN** model review validation succeeds with `human_reviewer_count=0` and `model_correlation_risk=true`

#### Scenario: Review count or provenance is inflated
- **WHEN** an artifact adds a third pass, claims human or independent review, or omits a bound pass hash
- **THEN** validation fails

### Requirement: Held-out negative labels are score-blind and evaluation-only
The pipeline SHALL freeze non-blind-test hard-negative labels before training
using a deterministic taxonomy/lexical rule that does not load baseline scores,
then apply the same two-pass model review and adjudication. Supported rows SHALL
carry `usage=HELD_OUT_EVAL_ONLY` and SHALL never enter mining or training.

#### Scenario: Held-out labels remain isolated
- **WHEN** labels are selected without baseline scores, sealed before training, and consumed only by final evaluation
- **THEN** the held-out label artifact validates

#### Scenario: Held-out information leaks
- **WHEN** held-out labels, scores, or outcomes affect mining, sampling, training, hyperparameters, or gates
- **THEN** validation fails

### Requirement: Internal package preserves exact truth and exclusions
The internal package SHALL contain exactly 64 train positives and 48-64
admitted hard negatives and SHALL exclude calibration, test, no-skill,
disputed, ambiguous, unsupported, and easy-negative rows. Its manifest SHALL
record `review_mode=MODEL_ONLY_PILOT`, `human_reviewer_count=0`,
`can_start_internal_training=true`,
`can_start_production_training=false`, `release_eligible=false`,
`blind_v2_eligible=false`, and `router_decision=KEEP_BASELINE` while leaving the
PR #37 audit at no admission effect.

#### Scenario: Internal-only package is valid
- **WHEN** exact row counts, exclusions, hashes, and truth fields all match
- **THEN** internal preflight may proceed without creating production eligibility

#### Scenario: A forbidden row or claim enters the package
- **WHEN** the package contains a forbidden split/role or implies human, production, release, blind, or promotion readiness
- **THEN** validation fails

### Requirement: Skill identity and deterministic sampling are sealed
Every validated example SHALL retain `skill_id`, and example/handoff
fingerprints SHALL bind it. Sampler `skill-unique-v1` SHALL emit every positive
exactly once per epoch, deterministically by seed and epoch, with at most one
example per `skill_id` in an MNRL batch, and SHALL record the batch-plan hash.

#### Scenario: Sampler is deterministic and skill-unique
- **WHEN** the same sealed input, seed, epoch, and sampler version are used
- **THEN** the identical plan is produced, all positives are covered once, and no batch repeats a skill

#### Scenario: Skill identity or coverage drifts
- **WHEN** `skill_id` is omitted from a fingerprint, a positive is skipped/duplicated, or a batch repeats a skill
- **THEN** preflight fails before framework import or output creation

### Requirement: Preflight is dependency-free and side-effect-free
`--preflight-only` SHALL validate configuration, package hashes, sampler plan,
lineage, and paths without importing Torch or sentence-transformers, querying
CUDA, or creating files, directories, caches, or model outputs.

#### Scenario: Preflight succeeds cleanly
- **WHEN** all bindings and invariants validate
- **THEN** it prints a canonical result and exits zero with no filesystem side effect

#### Scenario: Preflight would require runtime frameworks
- **WHEN** preflight imports a training framework, touches CUDA, or writes output
- **THEN** the preflight contract test fails

### Requirement: Training lineage is complete and frozen
Each config, run summary, and model manifest SHALL bind the data manifest,
accepted pairs, mining artifact/manifest, Git commit, exact base-model revision
and model-file hash, seed, sampler version/plan hash, and dependency versions.
Only arms A, B, and C, seeds `7170`-`7172`, 3 epochs, batch size 16, learning rate
`2e-5`, and hard-negative margin `1.5` are permitted.

#### Scenario: A permitted run is reproduced
- **WHEN** all frozen inputs, versions, seed, and arm configuration match
- **THEN** the run may execute and its output manifest binds the complete lineage

#### Scenario: An unregistered run is requested
- **WHEN** an architecture, arm, seed, hyperparameter, or input differs
- **THEN** execution fails before training

### Requirement: Final evaluation and decision are preregistered
Final non-blind-test evaluation SHALL occur once after all arms finish and SHALL
report Recall@1/5, MRR, NDCG@5, Negative Hit Rate@1/5, first-negative rank,
p50/p95 latency, per-seed results, mean/sample standard deviation, paired
wins/losses, and failure slices. Arm C versus paired Arm A is the only decision
comparison.

#### Scenario: All success gates pass
- **WHEN** mean and every-seed Recall@5 deltas are `>=0`, MRR and NDCG@5 deltas are `>=-0.01`, NHR@5 mean delta is `<=-0.05` with every-seed delta `<=0`, and mean/every-seed p95 ratios are `<=1.20`
- **THEN** the only conclusion is `ROUTER_V2_PILOT_IMPROVED`

#### Scenario: Any gate fails
- **WHEN** any preregistered threshold or consistency check fails
- **THEN** the only conclusion is `KEEP_BASELINE`

#### Scenario: Evaluation scope expands
- **WHEN** blind-v2, old blind results, post-hoc tuning, best-seed selection, or a new architecture is used
- **THEN** evaluation validation fails and the decision remains `KEEP_BASELINE`

### Requirement: Public wording remains conservative
README and resume recommendations SHALL explicitly state
`MODEL_ONLY_PILOT`, `human_reviewer_count=0`, non-SOTA, non-production, and
blind-v2 not run. They SHALL NOT use human-review, production-ready, release, or
promotion claims.

#### Scenario: Wording matches evidence
- **WHEN** all limitations are visible and the measured pilot conclusion is stated without inflation
- **THEN** documentation validation passes

#### Scenario: Wording overclaims
- **WHEN** wording implies human review, SOTA, production readiness, blind-v2 validation, release, or promotion
- **THEN** documentation validation fails
