## ADDED Requirements

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
