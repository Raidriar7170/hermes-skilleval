## Why

`v0.2.0` has been published, but the repository front door and several public
docs still read like pre-release or RC review packaging: package metadata is
still `0.1.0`, the reusable action examples point at `@main`, and README
evidence sections still say the release is not published.

This change aligns the GitHub homepage, version metadata, Action usage, and
fresh-clone onboarding with the post-release state while preserving the
project's conservative boundaries.

## What Changes

- Update project version metadata and user-facing release wording to `0.2.0`.
- Rewrite the README first screen around developer-tool onboarding:
  tagline, positioning, what it does, why routing is hard, Quick Start, GitHub
  Action usage, example failure, dashboard preview, evidence links, and
  limitations.
- Replace current reusable Action examples that point at
  `Raidriar7170/hermes-skilleval@main` with the released
  `Raidriar7170/hermes-skilleval@v0.2.0` ref.
- Rename public-facing "Reusable GitHub Action RC" wording to "Reusable GitHub
  Action" where the current release capability is described.
- Keep long phase history and evidence-chain detail out of the README front
  door by moving or linking it through `docs/evidence-map.md` and
  `docs/release-handoff.md`.
- Add or refresh external-user Quick Demo / fresh-clone instructions for local
  CLI usage and GitHub Action usage against example skills and benchmarks.
- Add a bounded demo-repo plan for a future
  `Raidriar7170/hermes-skilleval-demo` repository without creating or claiming
  that repository exists.
- Add focused checks that prevent stale `@main`, RC, "not a v0.2.0 release",
  and overclaim wording from returning to current public surfaces.
- Do not add MCP runtime routing, Marketplace Action publication, GitHub API PR
  comments, SaaS dashboards, public leaderboards, SOTA claims, automatic
  release publication, or fine-tuned router promotion.

## Capabilities

### New Capabilities

- `public-project-onboarding`: Defines the post-release README, version
  metadata, fresh-clone onboarding, Action copy/paste workflow, demo-repo plan,
  and public-surface claim boundaries for external users.

### Modified Capabilities

- `reusable-github-action-rc`: Update the existing reusable action contract from
  release-candidate wording to the published `v0.2.0` reusable repository
  Action posture, while continuing to exclude Marketplace publication, PR
  comments, SaaS, and runtime MCP routing.
- `external-repo-action-smoke-pack`: Refresh external consumer smoke and
  example docs so current onboarding uses `@v0.2.0`, GitHub Actions summaries,
  and artifacts without requiring GitHub API tokens.
- `hosted-consumer-action-smoke`: Clarify which hosted smoke evidence is
  historical and ensure current user-facing references do not recommend `@main`
  for released onboarding.
- `docs-evidence-map`: Keep the evidence map and release handoff as the place
  for longer evidence chains and phase history, while README keeps only
  high-signal links.
- `v0-2-0-release-decision`: Clarify that pre-publish decision artifacts are
  historical review evidence now that the release has been published.
- `v0-2-0-release-notes-and-final-approval`: Update release-note and approval
  wording so current docs distinguish historical pre-publish review artifacts
  from the actual published `v0.2.0` post-release evidence.

## Impact

- Affected public docs: `README.md`, `docs/usage.md`,
  `docs/evidence-map.md`, `docs/release-handoff.md`, release notes, and any
  new onboarding/demo-plan docs.
- Affected examples: `examples/github-action/` and any new external consumer
  example documentation.
- Affected metadata: `pyproject.toml`, package `__version__`, and root
  `action.yml` display metadata.
- Affected tests: project-surface, reusable action, release/public wording,
  fresh-clone smoke, and overclaim/forbidden-claim checks.
- No new runtime service, router backend, marketplace publication, GitHub API
  automation, release tag, GitHub Release, or fine-tuning promotion is in scope.
