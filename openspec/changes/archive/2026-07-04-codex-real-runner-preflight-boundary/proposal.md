## Why

PR #13 merged a non-execution Stage 2 input-package candidate with validator
evidence, and PR #16 later recorded explicit human privacy acceptance while
keeping execution readiness false. The current truth surface still explicitly
says no Codex real-runner preflight has run. Before any future smoke run, pilot
plan, or Stage 2 execution, Hermes needs a small fail-closed boundary packet
that turns the existing PR-5 runner contract and current merged package state
into concrete preflight criteria without invoking Codex.

## What Changes

- Add an OpenSpec change that defines the Codex real-runner preflight boundary
  as a separate non-execution phase.
- Record a static preflight readiness artifact for the current merged package
  state, including PR #16 privacy acceptance provenance, required inputs,
  current blockers, permitted next action, and explicit non-actions.
- Add a concise Chinese Human Brief for human review of the boundary decision.
- Preserve the existing runner implementation, Stage 2 package artifacts,
  release gates, tests, and historical evidence.
- Do not run `codex exec`, create live-agent traces, freeze a pilot plan,
  rerun the evidence gate, or execute the Stage 2 matrix.

## Capabilities

### New Capabilities

- `codex-real-runner-preflight-boundary`: Defines how Hermes records a
  non-execution readiness decision before any Codex real-runner smoke or
  live-agent Stage 2 execution is allowed.

### Modified Capabilities

- None.

## Impact

- Affected artifacts:
  - `openspec/changes/codex-real-runner-preflight-boundary/**`
  - `artifacts/v0.3/skillsbench-pilot/v0.3-codex-real-runner-preflight-boundary-*/`
  - `docs/human-briefs/*codex-real-runner-preflight-boundary.html`
- No changes to `src/hermes_skilleval/**`, `tests/**`, release logic, runner
  command construction, or committed Stage 2 input-package truth surfaces.
- Validation remains local/static: JSON parsing, boundary scans, OpenSpec
  strict validation, and release reproducibility checks.
