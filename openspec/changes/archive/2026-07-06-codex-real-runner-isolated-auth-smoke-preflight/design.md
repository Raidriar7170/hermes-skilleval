## Context

PR #18 recorded a real Codex runner smoke/preflight attempt after explicit
human authorization. The runner reached the isolated `HOME` / `CODEX_HOME`
boundary with clean skill inventory, but the Codex subprocess failed closed
with `BLOCKED_ISOLATED_CODEX_HOME_AUTH_401_AFTER_PREFLIGHT` because the
isolated `CODEX_HOME` did not contain usable authentication.

PR #19 archived that blocker/evidence record into the long-lived
`codex-real-runner-smoke-preflight` spec. This change starts the next bounded
phase: resolving only the isolated-auth smoke/preflight blocker and recording
the outcome as evidence. It must not become Stage 2 pilot execution.

## Goals / Non-Goals

**Goals:**

- Establish a minimal isolated-auth resolution procedure for Codex real-runner
  smoke/preflight.
- Keep `HOME` and `CODEX_HOME` isolated while allowing only the minimal
  authentication material required for Codex CLI smoke/preflight.
- Record authentication provenance, command outputs, hashes, environment
  allowlist, clean skill inventory, and non-actions in a new evidence artifact.
- Preserve the next-step boundary: an unblocked smoke/preflight may only lead
  to a separate pilot-freeze approval request.

**Non-Goals:**

- No Stage 2 pilot execution.
- No 4x3x1 matrix run.
- No real Codex 12-run execution.
- No pilot-plan freeze.
- No task traces.
- No evidence gate or oracle qualification rerun.
- No oracle/verifier evidence or routed-prediction rewrites.
- No task manifest or public prompt edits.
- No performance, benchmark, task-success, or router-promotion claims.

## Decisions

1. Treat authentication as isolated runtime provenance, not global inheritance.

   The implementation should not simply switch to inherited `CODEX_HOME` for
   final evidence. It should create a fresh isolated runtime and copy or
   materialize only the minimal authentication files required by the installed
   Codex CLI. The artifact must record the source category and hashes for
   copied authentication material without exposing secrets.

2. Keep the smoke prompt non-task and hash-addressed.

   The Codex invocation must continue to use a non-task smoke/preflight prompt.
   The artifact should record the prompt hash and assert that no selected Stage
   2 public prompts or task IDs were used.

3. Make the result status fail-closed.

   If isolated authentication remains unavailable, the phase should record a
   blocked status rather than a success or execution-ready status. If the
   smoke/preflight reaches a non-auth terminal result, the artifact should
   record that result and still keep execution readiness false.

4. Do not reuse task-success semantics.

   Process exit code, verifier output, or Codex response content from this
   smoke/preflight cannot be treated as Stage 2 task success. The only claim
   permitted here is runner/auth/isolation evidence for a later approval step.

## Risks / Trade-offs

- [Risk] Authentication files may contain secrets. -> Mitigation: record only
  paths relative to the isolated runtime, file presence, sizes, and hashes where
  safe; never print token values or raw config contents.
- [Risk] Copying too much global `CODEX_HOME` imports skills/plugins/config
  leakage. -> Mitigation: enforce allowlisted auth-only material and rerun clean
  skill inventory checks after materialization.
- [Risk] A green smoke/preflight could be overstated as pilot readiness. ->
  Mitigation: artifact, Human Brief, and PR body must keep
  `execution_readiness=false` and
  `can_be_used_as_real_stage2_input_package_now=false`.
- [Risk] Codex CLI auth storage layout may differ by version. -> Mitigation:
  record installed CLI version/help hashes and treat unsupported layout as a
  blocked auth-layout status.

## Open Questions

- Which installed Codex CLI auth files are sufficient and safe to copy into an
  isolated `CODEX_HOME` on this machine?
- Should the implementation add a helper script for auth-only materialization,
  or keep the process as one bounded evidence-generation command?
