# codex-real-runner-smoke-preflight Specification

## Purpose
Define the evidence, isolation, and non-execution boundaries for bounded Codex
real-runner smoke/preflight records before any Stage 2 pilot execution can be
considered.

## Requirements
### Requirement: Record real Codex smoke/preflight evidence

The system SHALL record a bounded runtime smoke/preflight packet after explicit
human authorization and before any Stage 2 pilot execution is allowed.

#### Scenario: Smoke/preflight packet is recorded

- **WHEN** the static preflight boundary permits
  `OPEN_EXPLICIT_CODEX_REAL_RUNNER_SMOKE_PREFLIGHT_PHASE`
- **THEN** the system MUST write a JSON artifact containing source commit,
  branch, required artifact paths, required artifact hashes, Codex CLI
  path/version/help hashes, command lines, stdout/stderr hashes, isolated
  runtime paths, environment allowlist, runner inventory, and status
- **AND** missing prerequisites or failed runtime isolation MUST produce a
  blocked smoke/preflight status rather than an execution-ready status

### Requirement: Preserve Stage 2 non-execution boundaries

The system SHALL keep the smoke/preflight phase separate from Stage 2 task
execution and benchmark evidence.

#### Scenario: Non-actions remain explicit

- **WHEN** the smoke/preflight artifact is written
- **THEN** it MUST record `stage2_pilot_run=false`,
  `matrix_4x3x1_run=false`, `pilot_plan_frozen=false`,
  `stage2_task_prompts_used=false`, `stage2_task_traces_created=false`,
  `evidence_gate_rerun=false`, `oracle_qualification_rerun=false`,
  `verifier_outputs_rewritten=false`, `routed_predictions_changed=false`,
  `performance_claim_made=false`, `router_promoted=false`, and
  `task_success_claimed=false`
- **AND** it MUST keep `execution_readiness=false` and
  `can_be_used_as_real_stage2_input_package_now=false`
- **AND** it MUST NOT modify existing Stage 2 input-package truth surfaces

### Requirement: Prove isolated runner wiring

The system SHALL use the project runner contract or an equivalent stricter
check to prove Codex CLI availability and isolation.

#### Scenario: Runner isolation is checked

- **WHEN** the smoke/preflight command is run
- **THEN** it MUST use isolated `CODEX_HOME` and isolated `HOME`
- **AND** it MUST record clean user, admin, and workspace skill inventory
- **AND** it MUST require workspace-write sandbox and approval policy `never`
- **AND** it MUST reject dangerous bypass flags and runner-controlled
  environment overrides

### Requirement: Keep next action narrow

The system SHALL make the next permitted action a separate approval step.

#### Scenario: Smoke/preflight does not authorize execution

- **WHEN** smoke/preflight checks pass
- **THEN** the next permitted action MUST be limited to requesting a separate
  pilot-freeze PR approval
- **AND** real Codex 12-run execution MUST still require separate explicit
  approval

### Requirement: Provide human-review summary

The system SHALL provide a concise human-readable companion summary for the
smoke/preflight phase.

#### Scenario: Human Brief mirrors artifact

- **WHEN** the smoke/preflight JSON artifact is created
- **THEN** a Chinese Human Brief MUST summarize conclusion, current status,
  changed artifacts, key hashes, verification commands, non-actions, remaining
  risks, and recommended next step
- **AND** the Human Brief MUST not replace the JSON artifact, OpenSpec files,
  validation output, or committed evidence as source of truth

### Requirement: Resolve isolated Codex authentication for smoke/preflight

The system SHALL support a bounded isolated-auth smoke/preflight phase after a
previous isolated `CODEX_HOME` authentication blocker.

#### Scenario: Authentication material is prepared inside isolated CODEX_HOME

- **WHEN** the system attempts isolated-auth smoke/preflight
- **THEN** it MUST create a fresh isolated `HOME` and `CODEX_HOME`
- **AND** it MUST materialize only allowlisted Codex authentication material
  needed by the installed Codex CLI
- **AND** it MUST record authentication material provenance without exposing
  token values, passwords, API keys, or raw secret contents
- **AND** it MUST reject or block if non-auth skills, plugins, prompts,
  configuration, or other global capability state leaks into the isolated
  runtime

### Requirement: Record isolated-auth smoke/preflight outcome

The system SHALL record the isolated-auth smoke/preflight outcome as bounded
runner evidence, not as task or benchmark evidence.

#### Scenario: Isolated-auth smoke/preflight is recorded

- **WHEN** the isolated-auth smoke/preflight command completes or fails closed
- **THEN** the system MUST write an evidence artifact containing source commit,
  branch, Codex CLI path/version/help hashes, authentication provenance
  summary, command lines, stdout/stderr hashes, isolated runtime paths,
  environment allowlist, clean skill inventory, prompt hash, and terminal status
- **AND** authentication failures MUST produce a blocked status rather than an
  execution-ready status
- **AND** a non-auth terminal result MUST still keep
  `execution_readiness=false` and
  `can_be_used_as_real_stage2_input_package_now=false`

### Requirement: Preserve Stage 2 non-execution during auth resolution

The system SHALL keep isolated-auth smoke/preflight separate from Stage 2 task
execution and pilot-freeze approval.

#### Scenario: Auth resolution does not authorize pilot execution

- **WHEN** isolated-auth smoke/preflight evidence is recorded
- **THEN** it MUST record `stage2_pilot_run=false`,
  `matrix_4x3x1_run=false`, `pilot_plan_frozen=false`,
  `stage2_task_prompts_used=false`, `stage2_task_traces_created=false`,
  `evidence_gate_rerun=false`, `oracle_qualification_rerun=false`,
  `verifier_outputs_rewritten=false`, `routed_predictions_changed=false`,
  `performance_claim_made=false`, `router_promoted=false`, and
  `task_success_claimed=false`
- **AND** it MUST NOT modify existing Stage 2 task manifests, public prompts,
  oracle/verifier evidence, routed predictions, scorer/matrix/evidence-gate
  semantics, or router defaults
- **AND** the next permitted action after an unblocked smoke/preflight MUST be
  limited to requesting a separate pilot-freeze PR approval
