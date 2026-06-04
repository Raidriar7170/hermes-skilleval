## Why

The project now has a reproducible release gate, a bounded Reusable GitHub
Action RC, local external-consumer smoke, and one hosted consumer smoke run.
Those artifacts are enough to support a human `v0.2.0` release review, but they
do not authorize automatic tag, GitHub Release, Marketplace publication, or
default-router promotion.

## What Changes

- Add a conservative `v0.2.0` release decision package that reads current
  release-gate and action-RC evidence into one reviewer-facing conclusion.
- Record the current decision as `NEEDS_REVIEW`: ready for human release
  review, not approved for automatic publication.
- Preserve the Phase 17/18 router release decision: `KEEP_BASELINE`,
  `baseline-minilm` remains selected, and `finetuned-embedding` remains not
  approved as the default router.
- Link the local external-consumer action smoke and hosted consumer smoke as RC
  support evidence, not release approval.
- Add tests and public-surface links that enforce release-boundary wording.
- Do not create a tag, GitHub Release, Marketplace listing, PR, deployment, or
  claim that `v0.2.0` has been released.

## Capabilities

### New Capabilities

- `v0-2-0-release-decision`: reviewer-facing `v0.2.0` release decision package
  that aggregates release-gate, reusable-action RC, local smoke, and hosted
  smoke evidence without publishing.

### Modified Capabilities

- `docs-evidence-map`: surface the `v0.2.0` release decision package while
  preserving source-of-truth and publication boundaries.
- `reusable-github-action-rc`: clarify that local and hosted action smoke are
  supporting RC evidence for a release review, not release approval.

## Impact

- Affected docs/evidence: a new release decision pack under
  `docs/demo/v0.2.0-release-decision/`, README/usage/evidence-map links, and a
  phase Human Brief.
- Affected tests: new focused release-decision tests plus project-surface
  coverage for links, decision values, and forbidden claims.
- Affected OpenSpec specs: new `v0-2-0-release-decision` spec and bounded
  updates to evidence-map / reusable-action specs after archive sync.
- External systems: none. This phase must not publish, deploy, tag, create a
  GitHub Release, create a PR, or modify Marketplace state.
