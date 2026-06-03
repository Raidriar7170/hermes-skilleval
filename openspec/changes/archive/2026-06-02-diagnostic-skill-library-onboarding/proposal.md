## Why

Hermes SkillEval is already strong as an offline benchmark and release-gate
harness, but first-time open-source users cannot yet point it at their own real
agent skill library and get immediate diagnostic value. The next product step is
to make the project useful to Skill Library Maintainers before they author
gold/negative benchmark labels.

## What Changes

- Add a diagnostic onboarding workflow for real user-owned skill libraries.
- Introduce a user-facing CLI front door for scanning, linting, routing example
  queries, and inspecting conflict risk clusters.
- Support stable first-version skill source shapes:
  - Markdown skill folders containing `SKILL.md`-style files.
  - MCP tool schema files such as `mcp.json`.
- Produce stable JSON diagnostic artifacts for scan, lint, route, and inspect
  outputs so later CI gate productization can compare changes.
- Generate a static diagnostic dashboard focused on source summaries,
  routing-readiness findings, and explainable conflict risk clusters.
- Keep the existing benchmark and release-gate workflow intact as deeper
  evaluation machinery.
- Exclude P0 runtime and platform expansion work:
  - No MCP server or runtime skill router.
  - No GitHub Action or pull-request merge blocking.
  - No large public benchmark or leaderboard.
  - No SaaS-like dashboard UI.

## Capabilities

### New Capabilities

- `diagnostic-skill-library-onboarding`: Covers the zero-label diagnostic
  workflow for scanning real skill sources, linting routing clarity, routing
  example queries with evidence/risk flags, inspecting conflict risk clusters,
  and writing stable diagnostic artifacts.

### Modified Capabilities

- None.

## Impact

- CLI: add product-facing commands for diagnostic onboarding while preserving
  existing evaluation-oriented commands.
- Skill parsing/indexing: extend normalization beyond the built-in benchmark
  toward user-provided Markdown skill folders and MCP tool schemas.
- Routing and diagnostics: add route-evidence and route-risk reporting for
  unlabeled queries.
- Reporting/dashboard: add static diagnostic artifact and dashboard outputs.
- Tests/docs: add focused coverage and docs for the diagnostic onboarding path.
