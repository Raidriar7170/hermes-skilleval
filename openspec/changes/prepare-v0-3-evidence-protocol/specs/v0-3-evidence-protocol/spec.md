# v0-3-evidence-protocol Specification

## Purpose

Define the frozen v0.3 evidence protocol for external SkillRouter evaluation,
live-agent execution evidence, evidence validity gates, router promotion gates,
and artifact retention before later implementation PRs produce results.

## ADDED Requirements

### Requirement: Freeze v0.3 research questions before results

The system SHALL provide a v0.3 protocol that records the research questions
before external benchmark or live-agent results are produced.

#### Scenario: Inspect protocol research questions

- **WHEN** a maintainer opens `docs/v0.3/protocol.md`
- **THEN** it MUST list research questions covering external routing
  generalization, field-view contribution, live-agent pass-rate transfer,
  route-to-execution gap, and conservative baseline retention under conflicting
  evidence
- **AND** it MUST state that PR-0 does not claim any v0.3 benchmark run,
  live-agent run, or router promotion has happened

### Requirement: Preregister final evaluation settings

The system SHALL require final scored benchmark and live-agent runs to write a
preregistration artifact before results are inspected.

#### Scenario: Prepare a final v0.3 run

- **WHEN** a later PR prepares a final scored or live-agent run
- **THEN** the preregistration MUST include git commit, dirty state, run ID,
  timestamp, seed `20260625`, router IDs, versions, thresholds, top-k values,
  text builders, data refs, file hashes, field views, candidate pools, task
  selection rules, runtime versions, and gate thresholds
- **AND** final scored labels and live-agent outcomes MUST NOT be used to
  rewrite the router list, thresholds, task list, or gate thresholds

### Requirement: Keep SkillRouter scored labels evaluation-only

The system SHALL treat SkillRouter final scored labels as evaluation-only.

#### Scenario: Use external scored data

- **WHEN** a later PR uses SkillRouter scored tasks
- **THEN** the implementation MUST NOT use final scored labels for training,
  threshold tuning, variant selection, or hard-negative mining
- **AND** official metrics MUST be reported separately from Hermes diagnostics
- **AND** Hermes Negative Hit Rate or Negative Accepted Rate MUST NOT be
  reported unless explicit negative labels exist

### Requirement: Define deterministic candidate-pool stress sampling

The system SHALL define deterministic candidate-pool sampling for non-official
Hermes stress tests.

#### Scenario: Build a stress candidate pool

- **WHEN** a later PR builds a non-official stress subset
- **THEN** it MUST include every relevant skill before distractors
- **AND** it MUST mark the subset `UNAVAILABLE` when the target size cannot
  include the relevant-skill union
- **AND** it MUST select distractors by sorting skill IDs with
  `sha256("20260625:" + skill_id)`
- **AND** it MUST use the same candidate list for every router and task in the
  tier
- **AND** it MUST record the candidate list hash in the manifest

### Requirement: Preserve Phase 10 as historical replay

The system SHALL preserve Phase 10 as deterministic offline replay and require a
distinct live-agent contract for v0.3 execution evidence.

#### Scenario: Describe live-agent evidence

- **WHEN** v0.3 docs or configs describe live-agent evidence
- **THEN** they MUST NOT call Phase 10 replay live-agent proof
- **AND** they MUST require a distinct runtime contract such as `live-agent.v1`
- **AND** deterministic verifiers MUST be the primary live-agent success judge
- **AND** LLM, screenshot, transcript, human, or preference review MUST be
  diagnostic only

### Requirement: Separate evidence validity from router promotion

The system SHALL define separate gates for evidence usability and default-router
promotion.

#### Scenario: Evaluate a v0.3 evidence packet

- **WHEN** a v0.3 evidence packet is reviewed
- **THEN** the Benchmark Validity Gate MUST emit one of `VALID_EVIDENCE`,
  `INVALID_EVIDENCE`, or `REVIEW_REQUIRED`
- **AND** missing optional fields MUST use `UNAVAILABLE` with a reason
- **AND** the Router Promotion Gate MUST emit one of `KEEP_BASELINE`,
  `PROMOTE_CANDIDATE`, or `REVIEW_REQUIRED`
- **AND** router promotion MUST NOT occur before valid or explicitly reviewed
  evidence exists

### Requirement: Define stop conditions and retention policy

The system SHALL define stop conditions and artifact retention rules before
external data or live-agent traces are produced.

#### Scenario: Encounter contaminated or unsafe evidence

- **WHEN** scored labels influence training or threshold selection, provenance
  cannot be established, verifier instability persists, oracle-skill
  qualification fails, or sensitive artifacts would need to enter Git
- **THEN** the run MUST stop or be marked `REVIEW_REQUIRED` or
  `INVALID_EVIDENCE`
- **AND** Git MUST NOT contain external full data, model checkpoints, embedding
  caches, credentials, raw auth files, private host details, raw live-agent
  traces, or unredacted logs
- **AND** Git MAY contain small fixtures, redacted summaries, manifests,
  hashes, protocol docs, reports, and reproducible commands

### Requirement: Provide placeholder-only configs

The system SHALL provide placeholder configs for future v0.3 implementation
without claiming execution.

#### Scenario: Inspect v0.3 configs

- **WHEN** a maintainer opens `configs/v0.3/external-skillrouter.yaml`,
  `configs/v0.3/live-agent.yaml`, or `configs/v0.3/release-gate.yaml`
- **THEN** each file MUST identify itself as placeholder or `FILL_BEFORE_RUN`
- **AND** each file MUST include seed `20260625`
- **AND** the release-gate config MUST keep evidence statuses separate from
  promotion decisions
