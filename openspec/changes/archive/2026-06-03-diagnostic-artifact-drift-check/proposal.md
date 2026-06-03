## Why

The diagnostic demo can be regenerated locally, but CI currently avoids
regenerate-and-diff checks because diagnostic artifacts contain volatile
`generated_at` timestamps. A small artifact drift check can compare committed
and regenerated outputs semantically without treating timestamps as product
regressions.

## What Changes

- Add a deterministic diagnostic artifact drift check that compares expected and
  actual diagnostic artifacts after normalizing allowed volatile fields.
- Support JSON artifacts and self-contained HTML dashboard packets that embed
  diagnostic JSON payloads.
- Add tests and docs for using the drift check with the committed diagnostic
  onboarding demo.
- No breaking changes.

## Capabilities

### New Capabilities

- `diagnostic-artifact-drift-check`: Local semantic comparison for diagnostic
  artifacts while ignoring approved volatile fields.

### Modified Capabilities

- None.

## Impact

- Affected code: CLI parser, a small artifact comparison module, docs, and
  tests.
- Affected workflows: maintainers can regenerate demo artifacts into a temporary
  directory and compare them against committed artifacts without timestamp
  noise.
- Dependencies: no new third-party dependencies.
- Non-goals: no GitHub PR annotations, no Marketplace Action release, no
  automatic merge/publish behavior, no SaaS backend, no runtime MCP router, and
  no change to Phase 16-18 release decisions.
