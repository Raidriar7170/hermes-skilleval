## Why

The `v0.2.0` release decision package is complete and records
`NEEDS_REVIEW`, but the repository does not yet have a `v0.2.0` release-notes
draft or a final human approval checklist that separates "ready to decide" from
"published." This change closes that review gap without creating a tag,
GitHub Release, Marketplace listing, or public release action.

## What Changes

- Add a conservative `docs/release-notes/v0.2.0.md` draft that describes only
  implemented, committed capabilities.
- Add a final approval checklist artifact that makes the human GO/NO-GO decision
  explicit before any tag or GitHub Release is created.
- Link the release notes and final approval checklist from README, usage docs,
  evidence map, release handoff, and a concise Chinese Human Brief.
- Add focused tests that verify release notes/checklist links, source evidence,
  publication boundaries, and forbidden release/product claims.
- Do not create a tag, GitHub Release, Marketplace publication, PR, deployment,
  version bump, or automatic publication.

## Capabilities

### New Capabilities

- `v0-2-0-release-notes-and-final-approval`: reviewer-facing release notes draft
  and final human approval checklist for `v0.2.0`, without publication.

### Modified Capabilities

- `docs-evidence-map`: surface the release notes draft, final approval checklist,
  and Human Brief as review artifacts while preserving source-of-truth and
  publication boundaries.

## Impact

- Affected docs/evidence: `docs/release-notes/v0.2.0.md`,
  `docs/demo/v0.2.0-final-approval/`, README, `docs/usage.md`,
  `docs/evidence-map.md`, `docs/release-handoff.md`, and a phase Human Brief.
- Affected tests: focused final-approval tests plus project-surface coverage for
  links, checklist fields, release notes boundaries, and forbidden claims.
- Affected OpenSpec specs: a new `v0-2-0-release-notes-and-final-approval`
  spec and a `docs-evidence-map` delta.
