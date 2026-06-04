## Why

The Reusable GitHub Action RC is now merged, but public reviewer navigation still
does not surface that evidence consistently. A few public-facing summaries also
retain stale test-count wording or archived `Purpose TBD` text in synced
OpenSpec specs, which weakens the repo's source-of-truth story.

## What Changes

- Refresh the evidence map so reviewers can find the reusable action RC,
  example fixture, synced spec, and Human Brief from the same navigation layer.
- Tighten project-surface tests so stale public test counts and missing RC
  evidence-map links fail explicitly.
- Replace `Purpose TBD` placeholders in synced OpenSpec specs with bounded,
  capability-specific purpose text.
- Update public README summary wording from the older 365-test count to the
  current 392-test count.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `docs-evidence-map`: require public reviewer surfaces to stay current after
  new evidence phases, including reusable action RC evidence and explicit
  OpenSpec purpose text.

## Impact

- Public docs: `README.md`, `docs/evidence-map.md`.
- OpenSpec specs: synced spec purpose text under `openspec/specs/*/spec.md`.
- Tests: `tests/test_project_surface.py`.
- Human Brief: a concise Chinese companion report for this phase.
