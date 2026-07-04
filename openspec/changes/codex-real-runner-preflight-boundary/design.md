## Context

PR-5 added the real `CodexCliRunner` subprocess layer and its fail-closed
preflight contract. PR #13 later merged a non-execution Stage 2 input-package
candidate whose oracle qualification, input-package validator, and privacy
review are complete for review purposes, while preserving
`execution_readiness=false` and explicitly recording that no Codex real-runner
preflight, Stage 2 pilot, frozen plan, traces, or evidence-gate rerun occurred.

This change is the boundary step between those two facts. It does not exercise
the runner. It records whether the merged package has enough static evidence to
justify a later, separately authorized real-runner smoke/preflight phase.

## Goals / Non-Goals

**Goals:**

- Define a fail-closed boundary for Codex real-runner preflight readiness.
- Consume existing committed evidence from PR-5/PR-6/PR #13 without rewriting
  their truth surfaces.
- Record the current decision as a static JSON artifact and a concise Chinese
  Human Brief.
- Keep the next permitted action narrow: a later smoke/preflight design review
  or explicit smoke run authorization, not Stage 2 execution.

**Non-Goals:**

- No `codex exec` invocation.
- No live-agent trace creation.
- No Stage 2 pilot execution, frozen pilot plan, run-order generation, or
  evidence-gate rerun.
- No changes to `src/hermes_skilleval/**`, `tests/**`, release logic,
  `configs/v0.3/live-agent.yaml`, or existing PR #13 artifacts.
- No release, archive, deploy, or public performance claim.

## Decisions

1. **Static boundary artifact over runner execution.**
   The preflight packet is a JSON decision artifact built from committed
   evidence paths and source-file inspection. Alternative considered: run
   `codex exec --version` or a real `CodexCliRunner` smoke now. That would
   cross the current phase boundary, create runtime-dependent evidence, and
   weaken the clear distinction between boundary design and execution.

2. **Three readiness gates.**
   The artifact separates package readiness, runner-contract readiness, and
   execution authorization. Package readiness can be positive for non-execution
   review while execution authorization remains false. This avoids collapsing
   validator/privacy success into Stage 2 readiness.

3. **Fail closed on missing committed evidence.**
   Required inputs include the merged PR #13 readiness artifact, stage2 package
   candidate artifact, privacy decision artifact, `configs/v0.3/live-agent.yaml`,
   and the PR-5 runner implementation. Missing or unparsable inputs make the
   boundary decision `BLOCKED_STATIC_PRECHECK`.

4. **No mutation of historical truth surfaces.**
   This phase writes new artifacts under a new run directory and links back to
   existing evidence. Existing PR #13 JSON files are not updated, because they
   correctly describe the C4 closeout state.

5. **Human Brief is explanatory only.**
   The HTML brief summarizes the same decision for review. It is not a second
   source of truth and must link back to OpenSpec and artifact paths.

## Risks / Trade-offs

- [Risk] A static pass may be mistaken for a real Codex smoke pass. ->
  Mitigation: artifact status and brief use `STATIC_PRECHECK_ONLY` and keep
  `codex_cli_run=false`, `live_agent_traces_created=false`,
  `stage2_pilot_run=false`, and `execution_readiness=false`.
- [Risk] CLI flag drift is not detected without invoking Codex. -> Mitigation:
  record CLI drift as a blocker that the next separately authorized smoke
  phase must check against `codex exec --help`.
- [Risk] Existing artifact paths may move in a later cleanup. -> Mitigation:
  fail closed on missing inputs and keep this phase tied to PR #13 merge state.
- [Risk] The new capability duplicates completed PR-5/PR-6 deltas. ->
  Mitigation: define only the boundary decision capability; do not modify the
  historical runner or matrix capability requirements.

## Migration Plan

This phase is additive. Rollback is deleting
`openspec/changes/codex-real-runner-preflight-boundary/`, the new static
preflight artifact directory, and the new Human Brief. No runtime behavior or
release gate state changes.

## Open Questions

- The exact real smoke command, model, timeout, and isolated `CODEX_HOME` root
  remain for a later explicitly authorized smoke/preflight phase.
- Whether the later smoke phase may use inherited Codex config remains
  unresolved; PR-5 says inherit mode is smoke-only and not final evidence.
