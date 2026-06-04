## Why

Current reviewer surfaces now use `394 passed`, while a few older
autonomous-loop Human Briefs still preserve their
original `384` or `391` run counts. Reviewers need an explicit boundary between
current validation claims and historical run evidence so the project does not
silently rewrite old phase reports or present stale counts as current.

## What Changes

- Add a historical Human Brief count boundary so older loop reports with exact
  pytest counts explain that those counts were original run or baseline
  evidence, not the latest public validation count.
- Add tests that distinguish current public surfaces from historical loop
  reports with contemporaneous counts.
- Add a concise Chinese Human Brief for this audit phase.
- Do not change release posture, create tags, publish a Marketplace Action, or
  change benchmark/product claims.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `docs-evidence-map`: distinguish current public validation-count surfaces
  from historical Human Briefs that intentionally preserve contemporaneous run
  counts.

## Impact

- Affected docs: selected `docs/human-briefs/*.html`, possibly
  `docs/evidence-map.md` if a navigation note is useful.
- Affected tests: `tests/test_project_surface.py`.
- Affected OpenSpec artifacts: `openspec/specs/docs-evidence-map/spec.md`
  after archive sync.
- No runtime API, CLI, dependency, release, tag, or Marketplace changes.
