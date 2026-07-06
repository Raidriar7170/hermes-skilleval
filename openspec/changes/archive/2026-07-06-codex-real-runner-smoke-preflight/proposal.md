## Why

The archived Codex real-runner preflight boundary permits the next action:
`OPEN_EXPLICIT_CODEX_REAL_RUNNER_SMOKE_PREFLIGHT_PHASE`. The project now has
explicit human authorization to perform that narrow runtime smoke/preflight and
record real evidence without running Stage 2 tasks.

## What Changes

- Add an OpenSpec change for the bounded Codex real-runner smoke/preflight
  phase.
- Inspect the merged Stage 2 prerequisite artifacts and record their paths,
  hashes, and readiness fields without rewriting them.
- Capture real Codex CLI path, version, `exec --help`, and runner-contract
  compatibility evidence.
- Create an isolated `HOME` / `CODEX_HOME` runtime workspace and run only a
  minimal non-task Codex smoke/preflight invocation.
- Record command lines, stdout/stderr files, hashes, environment allowlist,
  isolation inventory, and non-action proofs in a new JSON artifact.
- Add a concise Chinese Human Brief that mirrors the new artifact.
- Do not run Stage 2 pilot tasks, the 4x3x1 matrix, pilot-plan freeze,
  evidence gate, oracle qualification, verifier rewrites, routed-prediction
  rewrites, task traces, benchmark scoring, router promotion, or performance
  claims.

## Capabilities

### New Capabilities

- `codex-real-runner-smoke-preflight`: Defines the runtime smoke/preflight
  evidence packet allowed after the static boundary approval and before any
  later pilot-freeze review.

### Modified Capabilities

- None.

## Impact

- Affected artifacts:
  - `openspec/changes/codex-real-runner-smoke-preflight/**`
  - `artifacts/v0.3/skillsbench-pilot/v0.3-codex-real-runner-smoke-preflight-*/`
  - `docs/human-briefs/*codex-real-runner-smoke-preflight.html`
- No changes to Stage 2 task manifests, public prompts, oracle/verifier
  evidence, routed predictions, scorer semantics, matrix semantics, evidence
  gate semantics, release logic, or router defaults.
- The smoke invocation is non-task and may only prove runner wiring and
  isolation. It must not be treated as task success.
