## Context

PR #13 merged the Stage 2 input package candidate with oracle qualification
and validator evidence. PR #15 recorded a privacy provenance blocker, PR #16
recorded explicit human privacy acceptance, PR #14 recorded the static Codex
real-runner preflight boundary, and PR #17 archived that boundary. The current
permitted next action is a separately authorized real-runner smoke/preflight
phase, not Stage 2 execution.

This change consumes that authorization. It performs only the smallest runtime
check needed to prove the installed Codex CLI and `CodexCliRunner` isolation
contract are usable for later review. The Stage 2 package remains
non-executable: `execution_readiness=false` and
`can_be_used_as_real_stage2_input_package_now=false`.

## Goals / Non-Goals

**Goals:**

- Verify latest base hygiene, PR reachability, and Issue #11 closure.
- Confirm prerequisite artifact paths, hashes, and readiness fields from the
  merged base.
- Capture real Codex CLI path/version/help output and hash it as evidence.
- Create an isolated runtime workspace with isolated `HOME` and `CODEX_HOME`.
- Run a minimal non-task Codex invocation through the existing runner contract.
- Record non-actions and guard scans proving no Stage 2 task prompts, traces,
  matrix run, frozen pilot plan, evidence gate rerun, oracle rerun, verifier
  rewrite, routed-prediction rewrite, or performance claim occurred.
- Provide a concise Chinese Human Brief for review.

**Non-Goals:**

- No Stage 2 pilot execution.
- No 4x3x1 matrix.
- No selected-task prompt execution.
- No Stage 2 task trace creation.
- No pilot-plan freeze.
- No evidence-gate rerun.
- No oracle qualification rerun.
- No verifier output rewrite.
- No routed-prediction rewrite.
- No task success, benchmark, performance, router promotion, or release claim.

## Decisions

1. **Run through `CodexCliRunner`, not ad hoc shell-only `codex exec`.**
   The existing runner contract already validates required flags, sandbox,
   approval policy, isolated `CODEX_HOME`, isolated `HOME`, and capability
   inventory. Calling it for one non-task prompt proves the project runner
   wiring rather than only proving the CLI binary exists.

2. **Use a non-task prompt with no mounted skills.**
   The smoke prompt must not contain any selected Stage 2 task prompt or
   public task manifest text. `task_id` is a synthetic smoke identifier and
   `condition` remains `no-skill`; no verifier result is used as task success.

3. **Write stdout/stderr and output artifacts under a new evidence directory.**
   Runtime outputs are preserved as bounded preflight evidence. Hashes are
   recorded in the summary JSON so later review can verify the files without
   treating the raw command output as a trace corpus.

4. **Keep readiness false.**
   A successful smoke/preflight may only permit a later pilot-freeze approval
   request. It does not make the Stage 2 package execution-ready and does not
   authorize real Codex 12-run execution.

5. **Fail closed on missing or risky prerequisites.**
   If any required artifact is missing, if Codex help lacks runner-required
   flags, if isolation is not proven, or if the smoke invocation would require
   task prompts, the artifact records a blocked smoke/preflight status rather
   than inventing success.

## Risks / Trade-offs

- [Risk] A smoke pass could be confused with task success. -> Mitigation:
  artifact fields explicitly set `stage2_pilot_run=false`,
  `stage2_task_prompts_used=false`, `task_success_claimed=false`, and
  `execution_readiness=false`.
- [Risk] Codex CLI output may contain machine-local paths. -> Mitigation:
  record hashes and bounded stdout/stderr paths, avoid secrets, and do not
  publish private IPs, tokens, or SSH details.
- [Risk] Isolated `CODEX_HOME` may lack authentication. -> Mitigation: record
  the real failure as a smoke/preflight blocker instead of switching to an
  inherited user config unless explicitly justified as smoke-only.
- [Risk] Existing Stage 2 artifacts contain historical blocked records in
  addition to current pass records. -> Mitigation: prerequisite checks read the
  current strict artifact paths named in this phase and do not infer readiness
  from older blocked files.

## Migration Plan

This change is additive. Rollback is removing the new OpenSpec change, the new
smoke/preflight artifact directory, and the new Human Brief. No runtime code or
existing Stage 2 truth surface is modified.

## Open Questions

- Whether a later pilot-freeze PR should use the same installed Codex CLI
  version remains a separate review question.
- Whether the eventual real Codex 12-run execution may reuse any smoke
  workspace is out of scope; this phase treats the smoke workspace as bounded
  evidence only.
