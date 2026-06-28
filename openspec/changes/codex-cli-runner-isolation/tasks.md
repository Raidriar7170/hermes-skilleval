## 1. OpenSpec And Scope

- [x] 1.1 Create change `codex-cli-runner-isolation` with proposal, design,
  tasks, and `live-agent-runtime` spec delta.
- [x] 1.2 Keep PR-5 limited to `CodexCliRunner`; do not modify Phase 10,
  SkillsBench, external matrix/scorer, router promotion, or release gate logic.
- [x] 1.3 Record local `codex exec --help` supported flags in the design
  context.

## 2. Schema

- [x] 2.1 Add `schemas/live-agent-trace.schema.json`.
- [x] 2.2 Add tests validating fake and Codex runner traces against the schema.

## 3. Runner Configuration And Preflight

- [x] 3.1 Add RED tests for safe default command construction: `--json`,
  `--ephemeral`, `--ignore-user-config`, `--ignore-rules`,
  `--sandbox workspace-write`, `--cd`, and `--output-last-message`.
- [x] 3.2 Add RED tests rejecting `danger-full-access`, dangerous bypass flags,
  and `--yolo`.
- [x] 3.3 Add RED tests for isolated `CODEX_HOME` default and inherited
  smoke-only metadata.
- [x] 3.4 Add RED tests for version/help preflight and unsupported required
  flags.
- [x] 3.5 Add RED tests for global skill/plugin/MCP/config leakage and
  no-skill leakage.
- [x] 3.6 Implement `CodexCliRunner` configuration and preflight.
- [x] 3.7 Mount benchmark skills under
  `.agents/skills/<safe-skill-id>/SKILL.md` with `name` and `description`
  metadata.
- [x] 3.8 Add final-evidence inventory and fail-closed checks for user HOME,
  admin, and workspace-parent skill surfaces.
- [x] 3.9 Reject runner control flags in both split and `--flag=value` forms,
  and add runner-controlled `--skip-git-repo-check` only when supported.

## 4. Subprocess Execution

- [x] 4.1 Add RED tests using fake Codex executable scripts for success,
  non-zero exit, timeout, process-group cleanup, and output-last-message.
- [x] 4.2 Implement non-interactive subprocess execution and process-group
  timeout cleanup.
- [x] 4.3 Ensure process exit code is never treated as task success.

## 5. JSONL Parsing And Evidence

- [x] 5.1 Add RED tests for JSONL event parsing, malformed JSONL preservation,
  unknown event preservation, final messages, skill reads/declarations, and
  UNKNOWN skill activation evidence.
- [x] 5.2 Implement defensive JSONL parsing into PR-4-compatible events.
- [x] 5.3 Keep usage/cost `null` unless reliable token usage is available.

## 6. Redaction, Logs, Docs

- [x] 6.1 Add RED tests for stdout/stderr size limits and redaction.
- [x] 6.2 Implement log truncation/redaction.
- [x] 6.3 Add concise Chinese Human Brief for PR-5.
- [x] 6.4 Link PR-5 Human Brief from v0.3 implementation guide.

## 7. Validation

- [x] 7.1 Run focused Codex CLI runner tests.
- [x] 7.2 Run `python -m pytest -q`.
- [x] 7.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 7.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 7.5 Run `git diff --check`.
- [x] 7.6 Run v0.3 YAML parse check.
- [x] 7.7 Run CRLF/new-file line-ending check.
