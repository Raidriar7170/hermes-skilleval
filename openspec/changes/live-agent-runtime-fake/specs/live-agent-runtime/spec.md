## ADDED Requirements

### Requirement: Define live-agent runtime contract

The system SHALL define a `live-agent.v1` runtime contract without invoking a
real Codex CLI or SkillsBench process.

#### Scenario: Construct request and result records

- **WHEN** a caller builds a live-agent request
- **THEN** the request MUST include task ID, prompt, condition, workspace path,
  mounted skills, timeout, and metadata
- **AND** the result MUST include process exit code, timeout status, verifier
  outcome, trace schema version, usage, and cost
- **AND** usage and cost MUST be `null` when unavailable

### Requirement: Build skill-injection conditions

The system SHALL build `no-skill`, `routed-skill`, and `oracle-skill`
conditions while preserving prompt equality.

#### Scenario: Build comparable conditions

- **WHEN** conditions are built for the same task prompt
- **THEN** all conditions MUST have the same prompt hash
- **AND** `no-skill` MUST mount no benchmark skills
- **AND** `routed-skill` MUST mount only routed skill IDs
- **AND** `oracle-skill` MUST mount only oracle skill IDs

### Requirement: Prepare isolated workspaces and mount skills

The system SHALL prepare a fresh workspace for each live-agent run and mount
benchmark skills locally.

#### Scenario: Prepare workspace

- **WHEN** a workspace is prepared for a run
- **THEN** the workspace path MUST NOT already exist
- **AND** mounted skills MUST be written under a workspace-local skill
  directory
- **AND** each mounted skill MUST record ID, relative path, and SHA-256
- **AND** mounted skill filenames MUST be collision-resistant

#### Scenario: Reject workspace reuse

- **WHEN** the requested run workspace already exists
- **THEN** workspace preparation MUST fail closed

#### Scenario: Reject duplicate mounted skill IDs

- **WHEN** mounted skills contain duplicate skill IDs
- **THEN** workspace preparation MUST fail closed before creating or writing the
  run workspace

### Requirement: Execute fake runner and verifier

The system SHALL provide fake runner and fake verifier implementations for
deterministic tests.

#### Scenario: Separate process and verifier outcomes

- **WHEN** the fake runner returns process output
- **THEN** process exit code MUST be recorded separately from deterministic
  verifier pass/fail
- **AND** task success MUST be derived from verifier pass/fail, not process
  exit code alone

#### Scenario: Handle timeout and process failure

- **WHEN** the fake runner reports timeout or non-zero process exit
- **THEN** the trace MUST record that process state
- **AND** verifier outcome MUST still be represented separately

### Requirement: Emit live-agent trace schema

The system SHALL emit a deterministic `live-agent.v1` trace record.

#### Scenario: Trace successful fake run

- **WHEN** a fake live-agent run completes
- **THEN** the trace MUST include schema version, request, result, mounted
  skills, skill-use evidence, redacted events, stdout, stderr, and final
  message
- **AND** secrets MUST be redacted from trace-visible text
- **AND** secrets MUST be redacted from trace-visible object keys and values
- **AND** trace serialization MUST NOT expose absolute workspace paths by
  default

#### Scenario: Handle malformed and unknown events

- **WHEN** fake runner events are malformed
- **THEN** the run MUST fail closed with a malformed-event error
- **WHEN** fake runner events have unknown types
- **THEN** the trace MUST preserve a redacted unknown-event record without
  crashing

### Requirement: Track observable skill-use evidence

The system SHALL classify skill-use evidence only from observable events.

#### Scenario: Classify mounted and read skills

- **WHEN** a skill is mounted but has no read or declaration event
- **THEN** its evidence state MUST be `MOUNTED_ONLY`
- **WHEN** a skill read event is observed
- **THEN** its evidence state MUST be `READ`
- **WHEN** a skill declaration event is observed
- **THEN** its evidence state MUST be `DECLARED`
- **WHEN** evidence cannot be interpreted
- **THEN** its evidence state MUST be `UNKNOWN`

### Requirement: Prevent no-skill leakage

The system SHALL fail closed when no-skill conditions receive benchmark skills.

#### Scenario: Reject no-skill leakage

- **WHEN** a `no-skill` condition includes mounted benchmark skills
- **THEN** request construction or execution MUST fail closed
