## Why

PR #18 proved the real Codex runner can reach the isolated smoke/preflight
boundary, but it failed closed because the isolated `CODEX_HOME` did not
contain usable authentication. The next bounded step is to resolve and record
that isolated-auth smoke/preflight blocker without widening into Stage 2 pilot
execution.

## What Changes

- Define a bounded isolated-auth resolution smoke/preflight phase for the
  existing Codex real-runner smoke/preflight capability.
- Permit only the minimal non-task Codex runner invocation needed to prove
  isolated authentication, runner wiring, and isolation after PR #18.
- Record a new smoke/preflight artifact with command output hashes, isolated
  runtime evidence, authentication provenance classification, and explicit
  non-actions.
- Keep `execution_readiness=false` and
  `can_be_used_as_real_stage2_input_package_now=false` unless a later,
  separate pilot-freeze approval changes those semantics.
- Do not run Stage 2 pilot tasks, the 4x3x1 matrix, pilot-plan freeze,
  evidence gate, oracle qualification, verifier rewrites, routed-prediction
  rewrites, task traces, benchmark scoring, router promotion, or performance
  claims.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `codex-real-runner-smoke-preflight`: add requirements for isolated-auth
  resolution evidence, blocked/success status semantics, authentication
  provenance recording, and preservation of non-execution boundaries after the
  PR #18 `BLOCKED_ISOLATED_CODEX_HOME_AUTH_401_AFTER_PREFLIGHT` record.

## Impact

- Affected runtime surface: `CodexCliRunner` isolated `CODEX_HOME` / `HOME`
  smoke/preflight invocation and related evidence capture scripts or artifacts.
- Affected documentation: OpenSpec delta, a concise Chinese Human Brief, and a
  new bounded smoke/preflight evidence artifact under `artifacts/v0.3/`.
- No changes to Stage 2 task manifests, public prompts, oracle/verifier
  evidence, routed predictions, scorer/matrix/evidence-gate semantics, router
  defaults, or pilot execution plans.
