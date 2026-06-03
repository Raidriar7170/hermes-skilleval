## Why

The diagnostic CLI is implemented, but first-time users still need a concrete,
committed demo that shows the full zero-label workflow without inventing their
own skill library first. A small diagnostic evidence pack makes the new product
surface easier to inspect, screenshot, test, and link from the README.

## What Changes

- Add a committed diagnostic onboarding demo under `docs/demo/` that runs the
  full scan -> lint -> inspect -> route -> diagnostic-dashboard chain.
- Include a small real-looking demo skill library and/or MCP schema fixture that
  demonstrates source annotations, warnings, conflict clusters, route evidence,
  and risk flags.
- Commit generated diagnostic artifacts with a short README explaining how to
  regenerate them.
- Add tests that verify the demo artifacts are present, stable, self-contained,
  and do not overclaim runtime, SaaS, CI merge blocking, or benchmark results.
- Keep P0 scope: no GitHub Action, no runtime MCP server, no leaderboard, and no
  hosted UI.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `diagnostic-skill-library-onboarding`: Adds a reproducible demo/evidence pack
  for the existing diagnostic onboarding workflow.

## Impact

- Docs/demo artifacts: add a diagnostic demo directory with JSON and HTML
  outputs.
- Tests: add artifact integrity checks for the diagnostic demo pack.
- Docs: add concise links from README and CLI usage docs to the demo.
- CLI/runtime code: no new core diagnostic behavior is expected unless
  implementation uncovers a small artifact-generation bug.
