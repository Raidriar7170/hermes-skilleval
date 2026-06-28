## MODIFIED Requirements

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

#### Scenario: Reject condition and workspace mismatch

- **WHEN** a request is built from a condition and prepared workspace
- **THEN** the ordered condition mounted skill IDs MUST match the ordered
  workspace mounted skill IDs
- **AND** request construction MUST fail closed when they differ

#### Scenario: Validate trace schema

- **WHEN** a real Codex CLI runner emits a `live-agent.v1` trace
- **THEN** the trace MUST validate against
  `schemas/live-agent-trace.schema.json`

## ADDED Requirements

### Requirement: Run Codex CLI with isolated execution

The system SHALL provide a `CodexCliRunner` that invokes `codex exec`
non-interactively without using live benchmark tasks.

#### Scenario: Build safe default command

- **WHEN** the runner is configured in default isolated mode
- **THEN** it MUST use an isolated run-local `CODEX_HOME`
- **AND** it MUST set `HOME` to a run-local empty home for final evidence
- **AND** it MUST invoke `codex exec` with JSONL output, ephemeral session,
  workspace-write sandbox, ignored user config, ignored rules, and output-last
  message capture
- **AND** it MUST NOT use `--yolo`, `danger-full-access`, or dangerous bypass
  flags
- **AND** it MUST reject runner-control flag overrides, including
  `--flag=value` forms, and `CODEX_HOME` overrides
- **AND** it MAY add runner-controlled `--skip-git-repo-check` only when
  `codex exec --help` advertises support
- **AND** prompt text MUST NOT be parsed as runner flags

#### Scenario: Allow inherited mode only for smoke tests

- **WHEN** the runner is configured to inherit `CODEX_HOME`
- **THEN** the run metadata MUST mark inherited mode as smoke-only
- **AND** final evidence MUST still default to isolated mode

### Requirement: Preflight Codex CLI safety

The system SHALL fail closed before subprocess execution when preflight detects
unsafe or unsupported Codex CLI conditions.

#### Scenario: Check version and help support

- **WHEN** preflight runs
- **THEN** it MUST collect Codex version and `codex exec --help`
- **AND** it MUST fail closed if required flags are unsupported

#### Scenario: Reject leakage surfaces

- **WHEN** global skills, plugins, MCP config, or inherited user config would be
  consumed by a final evidence run
- **THEN** preflight MUST fail closed
- **AND** isolated final-evidence preflight MUST inventory user, admin,
  workspace-parent, and bundled skill surfaces
- **AND** benchmark skills MUST be mounted only under
  `.agents/skills/<safe-skill-id>/SKILL.md` with Codex skill metadata

#### Scenario: Reject no-skill leakage

- **WHEN** the request condition is `no-skill`
- **AND** mounted benchmark skills are present
- **THEN** preflight MUST fail closed before subprocess execution

### Requirement: Parse Codex JSONL defensively

The system SHALL parse Codex JSONL events without trusting every emitted line.

#### Scenario: Preserve unknown events

- **WHEN** the CLI emits an unknown event type
- **THEN** the runner MUST preserve a redacted unknown-event record
- **AND** the runner MUST NOT crash solely because of the unknown type

#### Scenario: Preserve malformed JSONL as unknown

- **WHEN** the CLI emits malformed JSONL
- **THEN** the runner MUST preserve a redacted malformed-event record
- **AND** the runner MUST NOT crash solely because of that malformed line

#### Scenario: Track skill activation evidence

- **WHEN** JSONL events show mounted skill reads or declarations
- **THEN** the resulting trace MUST classify them as `READ` or `DECLARED`
- **AND** unrecognized skill activation evidence MUST be classified as
  `UNKNOWN`

### Requirement: Manage Codex subprocess lifecycle

The system SHALL bound Codex subprocess runtime and logs.

#### Scenario: Timeout cleanup

- **WHEN** the Codex subprocess exceeds the request timeout
- **THEN** the runner MUST kill the subprocess process group
- **AND** the runner MUST use a bounded kill fallback when the process group
  ignores termination
- **AND** the result MUST record timeout with no verifier-derived task success

#### Scenario: Redact and truncate logs

- **WHEN** stdout or stderr contains sensitive strings or exceeds configured
  size limits
- **THEN** trace-visible logs MUST be redacted and truncated
- **AND** runner-returned events and final messages MUST also be redacted and
  size-bounded
