## Context

`v0.2.0` is already published. The completed
`post-release-onboarding-cleanup` change improved public onboarding and prepared
a `v0.2.1` patch-candidate note, but deliberately did not tag or publish.

The user has now explicitly approved doing the `v0.2.1` patch release. This
release should package documentation, metadata, and onboarding consistency only.

## Goals / Non-Goals

**Goals:**

- Publish a small `v0.2.1` patch release for the completed onboarding cleanup.
- Keep Action examples pinned to the current released tag after publication.
- Record post-release evidence for tag and GitHub Release facts.
- Preserve conservative router and product boundaries.

**Non-Goals:**

- No MCP runtime router.
- No Marketplace Action publication.
- No GitHub API PR comment bot or PR annotations.
- No SaaS dashboard, public ranking table, SOTA claim, automatic merge approval,
  automatic release publication, or fine-tuned default-router promotion.
- No benchmark/model behavior changes.

## Decisions

- Treat `v0.2.1` as a patch release only. The release is docs/metadata/onboarding
  packaging for the already implemented cleanup, not a feature release.
- Update package metadata to `0.2.1` so the release commit and package metadata
  match the tag.
- Update current Action examples to `Raidriar7170/hermes-skilleval@v0.2.1`
  after validation, because external users should copy the latest immutable
  release tag.
- Preserve `v0.2.0` evidence as historical/current evidence for that release and
  add separate `v0.2.1` post-release evidence after publication.
- Publish only after full local validation passes and the release commit is
  created. If GitHub credentials or remote operations fail, stop with local
  release prep complete rather than faking publication evidence.

## Risks / Trade-offs

- Release publication can fail because `gh` authentication or network access is
  unavailable -> Mitigation: verify local release prep first, then report the
  exact remote blocker if it happens.
- Updating Action examples from `v0.2.0` to `v0.2.1` changes the freshly cleaned
  onboarding surface -> Mitigation: update tests and rerun stale-ref scans.
- Post-release evidence can overclaim publication before it happens ->
  Mitigation: write candidate/pre-release docs first, then fill published facts
  only after tag and GitHub Release exist.
- OpenSpec archive may change root specs -> Mitigation: run
  `openspec validate --all --strict` and project-surface tests after archive.
