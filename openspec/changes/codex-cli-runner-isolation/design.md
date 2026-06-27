# Design: Codex CLI Runner Isolation

## Context

PR-4 introduced an offline fake `live-agent.v1` contract. PR-5 is the first
real process runner layer, but it is still infrastructure only: no SkillsBench
tasks, no full live-agent benchmark, and no promotion logic. The runner must
make real Codex subprocess behavior observable without letting process success
replace verifier success.

## Goals / Non-Goals

**Goals:**

- Implement a `CodexCliRunner` that satisfies `AgentRunner`.
- Use `codex exec` in non-interactive JSONL mode.
- Default to isolated `CODEX_HOME`; allow inherit mode only for explicit smoke
  tests.
- Use workspace-write sandbox and approval policy never.
- Fail closed on unsupported or unsafe CLI flags, `danger-full-access`, bypass
  flags, inherited global skill/plugin/MCP/config leakage, and no-skill skill
  injection.
- Preserve PR-4 condition/workspace mounted-skill ordering and verifier source
  of truth.
- Parse JSONL defensively and retain unknown events without crashing.
- Kill the process group on timeout.
- Redact and truncate stdout/stderr and trace-visible event data.
- Provide a JSON Schema for `live-agent.v1` traces before real Codex traces are
  accepted.

**Non-Goals:**

- No SkillsBench integration, live benchmark matrix, router training/tuning,
  external matrix/scorer edits, release promotion, or Phase 10 replay changes.

## Decisions

1. **Runner is additive.** `CodexCliRunner` is added beside the fake runner and
   reuses `AgentRequest`, `RunnerOutput`, `execute_live_agent`, and verifier
   semantics. The fake API remains stable.

2. **Isolated mode is default.** By default the runner creates a run-local
   `CODEX_HOME` with no user config. Inherit mode exists for smoke tests only
   and is marked as not final evidence.

3. **Command construction is explicit.** The default invocation uses
   `codex exec --json --ephemeral --ignore-user-config --ignore-rules
   --sandbox workspace-write --cd <workspace> --output-last-message <file>`.
   Dangerous bypass flags, `danger-full-access`, control-flag overrides, and
   `CODEX_HOME` environment overrides are rejected before running. Prompt text
   is passed after `--` so prompt text beginning with flags is not parsed as
   runner configuration.

4. **Preflight happens before subprocess execution.** Preflight records Codex
   version/help, checks supported flags, scans inherited `CODEX_HOME` surfaces
   when inheritance is requested, and rejects no-skill mounted skills.

5. **JSONL parsing is defensive.** Malformed JSONL lines are preserved as
   unknown events rather than crashing the runner. Unknown event types are
   preserved and can mark skill activation `UNKNOWN`.

6. **Verifier remains authoritative.** The subprocess exit code is reported,
   but task success remains verifier pass/fail through PR-4
   `execute_live_agent`.

## Risks / Trade-offs

- **Risk: real CLI flags drift.** Mitigation: preflight reads `codex exec
  --help` and records version/help support in metadata.
- **Risk: global config leaks into evidence.** Mitigation: isolated
  `CODEX_HOME` is default; inherit mode is explicitly smoke-only and scanned.
- **Risk: process hangs.** Mitigation: timeout sends process-group `SIGTERM`
  and then bounded `SIGKILL` fallback, not only parent-process cleanup.
- **Risk: runner output leaks before trace serialization.** Mitigation:
  runner-level events, final messages, stdout, and stderr are redacted and
  size-bounded before returning `RunnerOutput`.
- **Risk: schema hardens incorrectly.** Mitigation: schema covers the stable
  PR-4 trace envelope and is validated by tests against fake and CLI-runner
  traces.

## Migration Plan

PR-5 is additive. Existing fake runner tests and Phase 10 deterministic replay
remain unchanged. Rollback is removing `CodexCliRunner`, schema, tests, PR-5
OpenSpec artifacts, and the Human Brief.
