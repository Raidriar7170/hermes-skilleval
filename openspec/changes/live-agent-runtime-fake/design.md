## Context

Phase 10 already has deterministic offline replay artifacts, but v0.3 requires
a separate live-agent evidence contract before any real agent runner is used.
PR-4 introduces `live-agent.v1` as a local runtime abstraction with fake
implementations only. It provides schemas, condition construction, workspace
isolation, skill mounting, verifier separation, and trace semantics without
running Codex CLI, SkillsBench, networked services, or live agents.

## Goals / Non-Goals

**Goals:**

- Define `AgentRunner` protocol and request/result dataclasses for
  `live-agent.v1`.
- Build `no-skill`, `routed-skill`, and `oracle-skill` conditions from the same
  task prompt, changing only skill injection metadata.
- Fail closed when a request is built from a condition and workspace whose
  mounted skill IDs differ in content or order.
- Prepare fresh isolated workspaces and fail closed on workspace reuse.
- Mount benchmark skills into workspace-local files with stable hashes.
- Provide fake runner and fake verifier implementations for CI-only tests.
- Separate process exit status from verifier pass/fail.
- Emit trace records that distinguish `MOUNTED_ONLY`, `READ`, `DECLARED`, and
  `UNKNOWN` skill-use evidence.
- Redact secrets from trace-visible strings and keep unavailable usage/cost
  fields as `null`.

**Non-Goals:**

- No real Codex CLI runner, SkillsBench adapter, live-agent execution, network
  calls, model inference, router promotion, release gate changes, external
  matrix changes, or Phase 10 replay changes.

## Decisions

1. **New module boundary.** PR-4 adds a new `live_agent_runtime.py` module
   rather than modifying `agent_loop.py`. This keeps Phase 10 `agent-loop.v1`
   deterministic replay stable and makes `live-agent.v1` visibly separate.

2. **Fake runner is a protocol implementation.** The fake runner consumes
   scripted events and returns deterministic process output. It exists only to
   test schemas, redaction, timeout/error handling, and verifier separation.
   Real Codex CLI execution belongs to PR-5.

3. **Condition builder freezes prompt equality.** All conditions carry the
   same prompt text and prompt hash. Skill injection differs only through
   mounted skill IDs and condition metadata. Request construction also checks
   ordered condition/workspace mounted skill IDs so routed top-k order remains
   auditable.

4. **Workspace preparation is fail-closed.** A run workspace must be absent
   before preparation. Reusing an existing workspace raises an error so final
   evidence cannot accidentally share state. Mounted skill filenames include a
   stable skill-ID hash suffix so sanitized IDs such as `skill/a` and
   `skill_a` cannot collide. Duplicate skill IDs are rejected before any run
   workspace is created.

5. **Observable skill-use states only.** Mounted skills start as
   `MOUNTED_ONLY`. A fake read event moves them to `READ`; a declaration event
   moves them to `DECLARED`; malformed or unrecognized evidence is `UNKNOWN`.
   The runtime does not infer real use from model text.

## Risks / Trade-offs

- **Risk: fake runner is mistaken for live evidence.** → Mitigation: schema and
  docs state fake runner only; no real CLI integration or live task execution.
- **Risk: Phase 10 replay semantics drift.** → Mitigation: avoid editing Phase
  10 modules and add tests only under the new live-agent runtime surface.
- **Risk: secrets enter traces.** → Mitigation: central redaction helper covers
  request text, verifier details, event text, stdout/stderr, and final messages
  in fake traces, including nested trace-visible object keys.
- **Risk: local paths enter portable evidence.** → Mitigation: trace
  serialization records the workspace name by default rather than the absolute
  temporary directory path.
- **Risk: fake schema hardens too early.** → Mitigation: formal JSON Schema
  validation is deferred to PR-5 before real Codex traces are produced; PR-4
  keeps the trace shape deterministic and unit-tested.

## Migration Plan

PR-4 is additive. Existing CLI, release, router, external matrix, and Phase 10
paths remain unchanged. Rollback is removing the new live-agent module, tests,
OpenSpec change, and Human Brief.

## Open Questions

- Real Codex CLI event parsing, sandbox flags, SkillsBench task selection, and
  evidence-pack validation are explicitly deferred to later PRs.
- Formal JSON Schema validation for real Codex trace artifacts is deferred to
  PR-5 before any real live-agent traces are accepted.
