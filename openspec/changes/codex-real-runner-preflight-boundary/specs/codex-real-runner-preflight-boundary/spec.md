## ADDED Requirements

### Requirement: Record static real-runner preflight boundary

The system SHALL record a static Codex real-runner preflight boundary decision
before any real `codex exec` smoke, live-agent trace, Stage 2 pilot plan, or
Stage 2 execution is allowed.

#### Scenario: Static boundary decision is recorded

- **WHEN** a merged non-execution Stage 2 input package is reviewed for the
  next Codex real-runner step
- **THEN** the system MUST write a JSON artifact with run ID, source commit,
  required input paths, parsed readiness fields, blocker state, and permitted
  next action
- **AND** the artifact MUST distinguish static package readiness from real
  runner execution readiness
- **AND** missing or unparsable required inputs MUST produce a blocked
  decision instead of an execution-ready decision

### Requirement: Preserve non-execution boundaries

The system SHALL keep Codex real-runner preflight design separate from runtime
execution evidence.

#### Scenario: Non-actions stay explicit

- **WHEN** the static boundary artifact is written
- **THEN** it MUST record `codex_cli_run=false`,
  `live_agent_traces_created=false`, `stage2_pilot_run=false`,
  `pilot_plan_frozen=false`, and `evidence_gate_rerun=false`
- **AND** it MUST keep `execution_readiness=false` unless a later authorized
  real-runner smoke/preflight phase records real runtime evidence
- **AND** it MUST NOT modify existing PR #13 input-package truth surfaces

### Requirement: Gate next action narrowly

The system SHALL make the next permitted action explicit and bounded.

#### Scenario: Next action is a later authorization gate

- **WHEN** static preflight criteria are satisfied
- **THEN** the permitted next action MUST be limited to a later explicitly
  authorized Codex real-runner smoke/preflight phase
- **AND** it MUST NOT authorize Stage 2 pilot execution, frozen pilot planning,
  matrix execution, trace creation, release promotion, or deployment

### Requirement: Provide human-review summary

The system SHALL provide a concise human-readable summary for the static
preflight boundary decision.

#### Scenario: Human Brief mirrors the artifact

- **WHEN** the boundary artifact is created
- **THEN** a Chinese Human Brief MUST summarize conclusion, current status,
  changed artifacts, verification commands, non-actions, risks, and
  recommended next step
- **AND** the Human Brief MUST link or name the OpenSpec change and JSON
  artifact as the authoritative sources
