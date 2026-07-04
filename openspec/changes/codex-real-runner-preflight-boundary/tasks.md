## 1. OpenSpec Boundary

- [x] 1.1 Create proposal, design, and capability spec for the static
  Codex real-runner preflight boundary.
- [x] 1.2 Keep scope limited to non-execution boundary design; do not modify
  runtime code, tests, release logic, or PR #13 truth surfaces.

## 2. Static Precheck Artifact

- [x] 2.1 Inspect the merged PR #13 input-package readiness artifacts and the
  existing PR-5 Codex runner contract.
- [x] 2.2 Write a static precheck JSON artifact with required inputs, blocker
  state, allowed next action, and explicit non-actions.

## 3. Human Brief

- [x] 3.1 Generate a concise Chinese Human Brief that mirrors the JSON
  artifact and OpenSpec boundary.

## 4. Validation

- [x] 4.1 Validate OpenSpec with `openspec validate --all --strict`.
- [x] 4.2 Validate JSON syntax and boundary fields for the new artifact.
- [x] 4.3 Run release reproducibility check and `git diff --check`.
- [x] 4.4 Confirm no Codex run, traces, pilot freeze, Stage 2 run, deploy,
  archive, or release was produced.
