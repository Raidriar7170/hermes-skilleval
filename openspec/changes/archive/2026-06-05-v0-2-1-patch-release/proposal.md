## Why

The post-release onboarding cleanup changed public docs, version-facing metadata,
and reusable Action onboarding after `v0.2.0` was already published. A small
`v0.2.1` patch release can make those cleanup changes available from an
immutable release tag without expanding project scope.

## What Changes

- Promote the existing `v0.2.1` patch-candidate note into actual `v0.2.1`
  release notes.
- Update package metadata and package `__version__` from `0.2.0` to `0.2.1`.
- Update current README, usage, and example Action refs from
  `Raidriar7170/hermes-skilleval@v0.2.0` to
  `Raidriar7170/hermes-skilleval@v0.2.1` after validation.
- Add post-release evidence for the `v0.2.1` tag and GitHub Release once
  published.
- Keep the release strictly conservative: no Marketplace publication, no GitHub
  API PR comment bot, no SaaS, no runtime MCP router, no public ranking table,
  no SOTA claim, no automatic release publication, and no
  `finetuned-embedding` default-router promotion.
- **BREAKING**: none.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `public-project-onboarding`: current external onboarding should reference the
  published `v0.2.1` patch tag after release.
- `v0-2-0-release-notes-and-final-approval`: release-note and final-approval
  surfaces should distinguish historical `v0.2.0` evidence from the new
  `v0.2.1` patch publication record.
- `docs-evidence-map`: evidence navigation should include the `v0.2.1` patch
  release notes and post-release record.

## Impact

- Affects README, usage docs, release notes, evidence map, release handoff,
  package metadata, reusable Action examples, tests, and release evidence docs.
- Requires full local validation before commit/tag/release.
- Requires an explicit release commit and remote tag/GitHub Release operation;
  no release automation should run before validation passes.
