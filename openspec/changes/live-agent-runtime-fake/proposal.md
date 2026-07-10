## Why

v0.3 needs a live-agent evidence contract before any real Codex CLI or
SkillsBench integration can be trusted. PR-4 creates a local, fake-runner
`live-agent.v1` runtime abstraction that is testable in CI while keeping Phase
10 deterministic offline replay unchanged.

## What Changes

- Add `live-agent.v1` request/result/trace structures and an `AgentRunner`
  protocol.
- Add condition builders for `no-skill`, `routed-skill`, and `oracle-skill`
  while keeping the task prompt identical across conditions.
- Add isolated workspace preparation and benchmark skill mounting helpers.
- Add fake agent runner and fake verifier implementations for deterministic
  tests only.
- Separate agent process exit status from deterministic verifier pass/fail.
- Track skill-use evidence as `READ`, `DECLARED`, `MOUNTED_ONLY`, or
  `UNKNOWN` from observable fake events.
- Keep usage and cost fields `null` when unavailable.
- Add tests for success, verifier failure, process failure, timeout, malformed
  event input, unknown events, secret redaction, skill leakage, and workspace
  reuse.
- Do not integrate real Codex CLI, SkillsBench, live-agent execution,
  external matrix/scorer changes, router promotion, or release gate logic.

## Capabilities

### New Capabilities

- `live-agent-runtime`: Defines the `live-agent.v1` runtime contract, fake
  runner/verifier, condition builders, workspace and skill mounting behavior,
  trace schema, redaction, and deterministic tests.

### Modified Capabilities

- None.

## Impact

- Affected code: new live-agent runtime module(s) and optional scoped CLI/test
  helpers if needed.
- Affected tests: new fake-runner live-agent runtime tests covering trace
  schema, conditions, isolation, verifier/process separation, evidence, errors,
  redaction, leakage, and workspace reuse.
- Affected docs/OpenSpec: PR-4 OpenSpec artifacts and a concise Human Brief.
- Stable boundaries: Phase 10 `agent-loop.v1` replay remains unchanged; PR-3
  external matrix/scorer paths remain untouched.
- Out of scope: real Codex CLI runner, SkillsBench adapter, live-agent runs,
  router promotion, release gates, training, model inference, network access,
  or committing raw live traces.
