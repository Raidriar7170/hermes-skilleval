# Proposal: Codex CLI Runner Isolation

## Why

PR-4 defined the `live-agent.v1` fake runtime contract. PR-5 needs a real
`CodexCliRunner` implementation that can invoke `codex exec` under strict local
isolation while preserving the PR-4 request/result/verifier semantics. This
must happen before any SkillsBench integration or benchmark-scale live-agent
evidence is accepted.

Local `codex exec --help` on 2026-06-28 confirms support for:

- `--sandbox read-only|workspace-write|danger-full-access`
- `--ephemeral`
- `--ignore-user-config`
- `--ignore-rules`
- `--json`
- `--output-last-message <FILE>`
- `--cd <DIR>`
- `--config <key=value>`

It also exposes dangerous bypass flags. PR-5 must reject those for evidence
runs.

## What Changes

- Add `CodexCliRunner` implementing the PR-4 `AgentRunner` protocol.
- Add subprocess execution for `codex exec` with non-interactive JSONL mode,
  workspace-write sandbox, approval policy never, isolated `CODEX_HOME` by
  default, and process-group cleanup on timeout.
- Add explicit preflight checks for Codex version/help support, forbidden
  sandbox flags, global skill/plugin/MCP/config leakage, and no-skill leakage.
- Mount benchmark skills into a Codex-compatible workspace-local skills path
  while preserving PR-4 condition/workspace skill semantics.
- Parse JSONL events defensively, preserving unknown event types and marking
  skill activation `UNKNOWN` when needed.
- Add stdout/stderr size limits and reuse PR-4 redaction behavior.
- Add `schemas/live-agent-trace.schema.json` and validate real Codex traces in
  tests.
- Keep usage/cost `null` unless reliable token usage is available.

## Out Of Scope

- No SkillsBench adapter or live-agent benchmark matrix.
- No router training, threshold tuning, or model inference.
- No external SkillRouter matrix/scorer changes.
- No router promotion or release gate changes.
- No Phase 10 deterministic offline replay changes.
- No `--yolo`, `danger-full-access`, or dangerous bypass flags.

## Impact

- Affected code: PR-4 live-agent runtime module, if needed for additive runner
  classes/helpers only.
- Affected tests: new Codex CLI runner tests using fake local executable
  scripts, not the real live benchmark.
- Affected docs/OpenSpec: PR-5 OpenSpec artifacts, trace schema, and concise
  Human Brief.
