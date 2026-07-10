# Proposal: SkillsBench Live-Agent Matrix

## Why

PR-4 defined the `live-agent.v1` runtime contract and PR-5 added the isolated
`CodexCliRunner`. PR-6 needs the next bounded layer: select deterministic
SkillsBench tasks, freeze the selected live-agent plan, and build the
three-condition matrix machinery without running a full live benchmark or
promoting routers.

The implementation must make pilot versus frozen evaluation explicit, preserve
verifier primacy for task success, and keep SkillsBench evidence separate from
Phase 10 deterministic replay and SkillRouter external scoring.

## What Changes

- Add a SkillsBench adapter for local fixture-shaped task records, skills, and
  deterministic verifier metadata.
- Validate and freeze only tasks with deterministic verifiers, no private
  credentials, and controlled network requirements.
- Add oracle qualification before a task can enter a frozen evaluation plan.
- Build a global E2E skill registry across selected tasks rather than
  per-task-only routing inputs.
- Generate `no-skill`, `routed-skill`, and `oracle-skill` live-agent matrix
  entries with the same prompt hash and fresh workspace per run.
- Record `live-agent.v1` trace paths, skill inventory, mounted/read/unknown
  evidence, timeout, process exit, verifier result, and redacted events.
- Add a SkillRouter overlap report scaffold for selected live-agent tasks.

## Out Of Scope

- No Phase 10 deterministic replay changes.
- No SkillRouter external matrix or official scorer changes.
- No full live-agent benchmark execution in CI.
- No router training, threshold tuning, hard-negative mining, model inference,
  router promotion, or release promotion.
- No Hermes Negative Hit Rate for SkillsBench unless explicit negative labels
  exist.

## Impact

- Affected code: new SkillsBench/live-agent adapter and matrix helpers, scoped
  CLI commands, tests, fixtures, and PR-6 OpenSpec docs.
- Stable dependencies: PR-4 `live-agent.v1` runtime APIs and PR-5
  `CodexCliRunner` remain the execution contract.
- Evidence boundary: PR-6 may create deterministic fixture traces and plans, but
  it does not claim full benchmark results.
