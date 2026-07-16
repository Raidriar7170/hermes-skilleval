## ADDED Requirements

### Requirement: Protocol and evaluator are frozen before blind-v2 access
The system SHALL create Commit A before reading any blind-v2 prompt, gold label, or negative label. Commit A SHALL bind the base Git commit, current `origin/main`, exact Arm A/C identities and files, frozen training inputs, query and skill-representation contracts, evaluator paths and hashes, metric/statistical definitions, unchanged pilot-002 gate, expected `64`/`48` counts, single-attempt policy, and all prohibited post-data actions.

#### Scenario: Commit A is created without blind data
- **WHEN** preregistration is prepared from the frozen repository and model authority
- **THEN** `blind_v2_data_seen` is `false`, evaluator code is frozen in the same commit, and no blind-v2 source file has been opened

#### Scenario: Frozen authority drifts
- **WHEN** any model, checkpoint, manifest, seed, training input, skill index, query contract, skill representation, or gate hash differs from preregistration authority
- **THEN** the system stops before blind-v2 data access and performs no repair, replacement, retraining, or evaluation

### Requirement: Synthetic model-load smoke is A/C-only and non-benchmark
The system SHALL run a pre-data synthetic smoke for Arm A and Arm C seeds `7170`, `7171`, and `7172` using fixed preregistered strings, identical CPU loading, verified file hashes and sizes, finite normalized embeddings, consistent dimensions, and a removed private temporary directory.

#### Scenario: All frozen models load
- **WHEN** each required A/C model passes file verification, load, encode, dimension, and finite-value checks
- **THEN** the smoke reports pass without reading blind-v2, computing benchmark metrics, or writing an evaluation attempt

#### Scenario: A model fails smoke
- **WHEN** any required model cannot be verified, loaded, or encoded
- **THEN** the system stops before checking or reading the human pack

### Requirement: Blind-v2 originates outside the repository from humans
The system SHALL accept blind-v2 only from an absolute `HERMES_BLIND_V2_ROOT` outside the repository containing `blind-v2-authored.csv`, `blind-v2-independent-review.csv`, and `reviewer-metadata.json`. Codex and model agents MUST NOT author, edit, complete, adjudicate, or relabel any prompt, gold skill, negative skill, reviewer identity, decision, or reason.

#### Scenario: Human pack is absent or incomplete
- **WHEN** the environment root is absent or any required file is missing
- **THEN** the system creates only blank templates and a human guide under `/tmp/hermes-blind-v2-authoring-pack/`, reports the complete deficit, and stops at `BLIND_V2_WAITING_FOR_HUMAN_DATA`

#### Scenario: Independent human review is missing
- **WHEN** no reviewer is a different real human from the author or reviewer metadata discloses model-ranking access
- **THEN** the system rejects final-blind status and performs no scoring

### Requirement: Static validation precedes every model score
The system SHALL validate source bytes, UTF-8, schemas, duplicate keys, task/prompt/family uniqueness, canonical skills, author-reviewer separation, review agreement and reasons, leakage, old-path exclusion, exact overlap, NFKC-casefold near duplicates, family disjointness, gold-negative inequality, and final distributions before loading any evaluation model.

#### Scenario: Valid 64/48 pack
- **WHEN** exactly 64 accepted tasks cover 16 gold skills with four tasks each, exactly three negative-labeled plus one positive-only task per gold skill, 48 total tempting negatives, at least 12 negative targets with no target over six, 64 disjoint semantic families, and complete human agreement
- **THEN** static validation passes without emitting model scores or task selection based on model behavior

#### Scenario: Any candidate is rejected or disagreed
- **WHEN** a row fails schema, naturalness/leakage declarations, overlap, uniqueness, review agreement, or distribution constraints
- **THEN** the row is excluded, the validator reports the deficit, and Codex does not edit or replace it

### Requirement: Commit B freezes the reviewed dataset before scoring
The system SHALL create `blind-v2-tasks.jsonl`, `blind-v2-review-summary.json`, and `blind-v2-manifest.json` under `data/router-v2-blind-v2/` only after static validation, then create Commit B before model scoring.

The pack-status and freeze commands SHALL validate a clean canonical Commit A plus its tamper-evident smoke receipt before reading `HERMES_BLIND_V2_ROOT`. Freeze SHALL derive skills and overlap references only from preregistered paths and write only the canonical three-file directory. Missing-pack templates SHALL be written only to `/tmp/hermes-blind-v2-authoring-pack/` without a caller-controlled destination.

#### Scenario: Prompts may be published
- **WHEN** reviewer metadata grants dataset license, publication permission, and post-evaluation prompt disclosure
- **THEN** Commit B contains the complete task data and exact source hashes

#### Scenario: Prompts are private
- **WHEN** publication permission is false
- **THEN** Commit B contains counts, distributions, source hashes, per-row prompt hashes, review summary, and role counts without prompt plaintext
- **AND** the formal evaluator revalidates the same external source bytes and exactly regenerates Commit B documents in memory before any model load

#### Scenario: Post-freeze mutation is attempted
- **WHEN** any process attempts to change tasks, reviews, gate, model, query/skill representation, checkpoint, or selected rows after Commit B
- **THEN** the evaluation refuses to start

### Requirement: Exactly one terminal blind-v2 attempt is permitted
The system SHALL run only `router-v2-v4-final-blind-v2-001/attempt-1` from a fresh clean Commit B worktree after revalidating every frozen hash, exact Commit A/B ancestry and changed-file set, count, smoke result, namespace, marker, and worktree condition. Caller-supplied alternate task, model, hash, commit, evaluator, token, or output-root authorities SHALL NOT be accepted.

#### Scenario: Attempt starts
- **WHEN** all preflight checks pass and the output namespace does not exist
- **THEN** an exclusive started marker is written before inference and the attempt is irreversibly consumed

#### Scenario: Attempt fails after start
- **WHEN** any exception or infrastructure failure occurs after the started marker
- **THEN** started, terminal, and failure artifacts are retained, no retry or replacement namespace is created, and the conclusion is `BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE`

#### Scenario: Arm B is unavailable to the gate
- **WHEN** the evaluator computes routing results
- **THEN** only frozen Arm A and Arm C seeds `7170`, `7171`, and `7172` enter per-seed deltas, statistics, gate evaluation, and the final conclusion

#### Scenario: Ranking and latency match pilot-002
- **WHEN** any task is routed
- **THEN** one untimed per-query warm-up occurs immediately before one timed pass, and cosine scores are quantized to eight decimals with `ROUND_HALF_EVEN` before deterministic skill-ID tie breaking

### Requirement: Metrics and statistics are raw-count-first and preregistered
The system SHALL report per Arm/seed Recall@1 and Recall@5 raw counts over 64, MRR, NDCG@5, Negative Hit@1 and @5 raw counts over 48, first-negative rank, p50/p95 latency, per-task gold/negative ranks, paired wins/losses/ties, and per-gold, per-negative-target, per-family, and failure slices.

#### Scenario: Aggregate analysis is produced
- **WHEN** all seed results complete
- **THEN** the system reports mean, sample standard deviation, each Arm C minus Arm A delta, pooled repeated raw counts with a non-independence warning, exact paired McNemar tests for Recall@1 and Negative Hit@5, and 10,000-resample paired bootstrap 95% intervals with seed `7170` for MRR, NDCG@5, and NHR@5 deltas

#### Scenario: Statistical uncertainty conflicts with gate direction
- **WHEN** a confidence interval or p-value is inconclusive
- **THEN** the system reports that uncertainty without adding, removing, or changing any gate

### Requirement: The pilot-002 gate is applied mechanically
The system SHALL require mean and per-seed Recall@5 delta `>= 0`, mean and per-seed MRR/NDCG@5 delta `>= -0.01`, mean NHR@5 delta `<= -0.05`, every-seed NHR@5 delta `<= 0`, and mean/every-seed p95 latency ratio `<= 1.20`.

#### Scenario: Every gate passes
- **WHEN** all mean and every-seed thresholds pass
- **THEN** `research_conclusion` is `BLIND_V2_GENERALIZATION_SUPPORTED` while production, release, and automatic router promotion remain false

#### Scenario: Any gate fails
- **WHEN** one or more preregistered thresholds fail
- **THEN** `research_conclusion` is `BLIND_V2_NOT_SUPPORTED`, `router_decision` is `KEEP_BASELINE`, and the default router remains unchanged

### Requirement: Final artifacts bind complete lineage
The system SHALL write preregistration, blind-v2 manifest, review summary, started/terminal markers, per-seed, aggregate, paired, statistics, failure slices, evaluation summary, result report, and lineage manifest under the unique final namespace.

#### Scenario: Lineage is sealed
- **WHEN** the terminal result is written
- **THEN** the lineage manifest binds Commit A, Commit B, evaluator commit, model files, dataset/review source files and frozen documents, skill index, query contract, gate, attempt token, exact started marker, planned/actual success terminal, every non-self output artifact hash, and its own canonical self-hash

#### Scenario: Old artifacts are compared after completion
- **WHEN** validation recomputes repository and cache authority
- **THEN** pilot-001, pilot-002, Phase 16, training artifacts, model files, checkpoints, thresholds, and seeds show zero change

### Requirement: Public wording reflects the actual blind-v2 outcome
The system SHALL update `README.md`, `README_EN.md`, `docs/resume.md`, and `docs/interview-project-overview.html` only after a terminal result and SHALL use raw counts, human-review status, gate outcome, limitations, and unchanged-default language.

#### Scenario: Generalization is supported
- **WHEN** every preregistered gate passes
- **THEN** public wording may state that human-reviewed blind-v2 supports generalization but MUST NOT state SOTA, production readiness, release eligibility, or automatic promotion

#### Scenario: Generalization is not supported
- **WHEN** any gate fails
- **THEN** public wording states that the internal held-out result did not reproduce stably on human-reviewed blind-v2 and that the baseline remains gated

### Requirement: Prohibited actions remain absent
The system MUST NOT train, optimize, mine, relabel, tune, change thresholds/gates/seeds, select a best seed, delete hard tasks or failure artifacts, create a later attempt or blind set, modify the default router, merge, tag, release, deploy, or archive.

#### Scenario: Evaluation completes or blocks
- **WHEN** the workflow ends in supported, not-supported, infrastructure-failure, or waiting-for-human-data state
- **THEN** the final report enumerates every prohibited action as an explicit non-action
