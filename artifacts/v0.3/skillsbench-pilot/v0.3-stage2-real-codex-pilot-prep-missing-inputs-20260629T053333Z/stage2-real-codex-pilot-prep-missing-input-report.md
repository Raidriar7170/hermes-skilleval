# Stage 2 Real Codex Pilot Prep Missing Inputs

Status: `BLOCKED_MISSING_INPUTS`

Created: `2026-06-29T05:33:33Z`

Branch: `ops/prepare-stage2-real-codex-pilot-inputs`

Base accepted blocked artifact commit:
`98eec36601cd504c3c9466ed36ed7fd4421fb1fa`

## Conclusion

The branch prepared fail-closed real-evidence guards and exposed the real
`CodexCliRunner` path, but it did not prepare a runnable Stage 2 pilot package
because the real 4-task inputs, deterministic verifier artifacts, oracle
qualification, routed predictions, and deterministic verifier integration are
still missing.

## Requested Pilot Shape

- 4 selected SkillsBench tasks.
- 3 conditions per task: `no-skill`, `routed-skill`, `oracle-skill`.
- 1 trial per condition.
- 12 total runs.
- Evidence label: `pilot_non_final`.

## Prepared

- Real evidence mode rejects fixture-only SkillsBench data.
- Real evidence mode rejects `FakeAgentRunner` and `FakeVerifier`.
- Real evidence mode requires final-evidence runner preflight with isolated
  `CODEX_HOME` and `HOME`.
- Plans now record task hashes, prompt hashes, verifier hashes, verifier
  code/config/input hashes, oracle qualification hashes, routed prediction
  hashes, router/config/top-k metadata, and global registry hash.
- `skillsbench-matrix` now exposes `--runner codex-cli` and
  `--evidence-mode real`.

## Still Missing

- A non-fixture or explicitly approved 4-task SkillsBench pilot data root.
- Deterministic verifier code/config/input artifacts for all 4 tasks.
- Oracle qualification records for all 4 tasks.
- Routed predictions over the global skill registry for all 4 tasks.
- A deterministic verifier integration for real matrix execution.

## Non-Actions Confirmed

- Stage 2 pilot was not run.
- Codex CLI was not run.
- No pilot plan was frozen.
- No live-agent traces were created.
- No evidence gate was rerun with fake live artifacts.
- `tests/fixtures/live_agent/skillsbench_tiny` was not used as real evidence.
- `FakeAgentRunner` and `FakeVerifier` were not used as real evidence.
- Scorer, matrix, and evidence-gate semantics were not modified.
