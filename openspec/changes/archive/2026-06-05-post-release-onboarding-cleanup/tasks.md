## 1. Version and Release-State Consistency

- [x] 1.1 Update `pyproject.toml` and package version metadata from `0.1.0` to `0.2.0`.
- [x] 1.2 Audit README, release notes, usage docs, examples, action metadata, and current public docs for stale `0.1.0`, RC, `@main`, and "not a v0.2.0 release" wording.
- [x] 1.3 Preserve historical pre-publish artifacts as historical evidence while ensuring current public surfaces describe `v0.2.0` as published.
- [x] 1.4 Prepare a short `v0.2.1` patch-candidate note only if post-release metadata/doc changes warrant it; do not tag, publish, or create a GitHub Release.

## 2. README Developer-Tool Front Door

- [x] 2.1 Rewrite the README opening with the new tagline and external maintainer positioning.
- [x] 2.2 Add or refresh first-screen sections for What it does, Why skill routing is hard, Quick Start, Use as GitHub Action, Example failure caught, Dashboard preview, Evidence links, and Limitations / Boundaries.
- [x] 2.3 Reduce README phase-history and evidence-chain detail to 3-5 high-signal links, moving longer navigation to `docs/evidence-map.md` or `docs/release-handoff.md`.
- [x] 2.4 Standardize the concise boundary sentence and keep `baseline-minilm` as default while stating `finetuned-embedding` is not approved as default.

## 3. GitHub Action Onboarding

- [x] 3.1 Update root `action.yml` display metadata from RC wording to reusable GitHub Action wording.
- [x] 3.2 Replace current user-facing Action examples with `Raidriar7170/hermes-skilleval@v0.2.0`.
- [x] 3.3 Add the copy/paste pull-request workflow with `skill-path`, `benchmark-path`, `min-recall-at-k`, `max-negative-hit-rate`, and `upload-artifacts` inputs.
- [x] 3.4 Document that the action writes GitHub Actions summary and artifacts and does not require a GitHub API token.
- [x] 3.5 Ensure docs do not claim Marketplace publication, PR comment bot behavior, PR annotations, SaaS, or runtime MCP routing.

## 4. External User Quick Demo

- [x] 4.1 Refresh `examples/github-action/` docs and workflow so current onboarding points at `@v0.2.0`.
- [x] 4.2 Add or update `docs/usage.md` with a fresh-clone local path covering install, scan, route, gate, and CI summary commands against committed example fixtures.
- [x] 4.3 Add or update GitHub Action trial instructions covering copied workflow, example skill folder, example benchmark, and expected `ALLOW_MERGE` / `BLOCK_MERGE` summary behavior.
- [x] 4.4 Add a fresh-clone smoke script or documented command sequence that uses only repo-relative paths and temporary outputs.

## 5. Demo Repository Plan

- [x] 5.1 Add `docs/demo-repo-plan.md` or `examples/external-action-consumer/README.md` for future `Raidriar7170/hermes-skilleval-demo`.
- [x] 5.2 Describe a Good PR scenario that produces `ALLOW_MERGE`.
- [x] 5.3 Describe a Bad PR scenario that introduces a routing regression or negative hit and produces `BLOCK_MERGE`.
- [x] 5.4 Link the plan from README or usage docs without claiming the external demo repository already exists.

## 6. Evidence Navigation and Historical Boundaries

- [x] 6.1 Update `docs/evidence-map.md` and `docs/release-handoff.md` so long evidence chains live there, not in the README front door.
- [x] 6.2 Update release notes and final-approval references so historical pre-publish evidence is labeled historical and post-release evidence is the current publication record.
- [x] 6.3 Update hosted and local consumer smoke references so captured historical refs are not presented as the current recommended Action ref.
- [x] 6.4 Keep current public docs free of stale "not a v0.2.0 release" and unnecessary RC wording.

## 7. Tests and Guards

- [x] 7.1 Extend project-surface tests for README required sections, version metadata, Action ref `@v0.2.0`, and forbidden stale wording.
- [x] 7.2 Extend reusable Action / external smoke tests for current onboarding docs and no-token summary/artifact behavior.
- [x] 7.3 Add fresh-clone smoke coverage or a deterministic test for the documented fresh-clone command path.
- [x] 7.4 Update overclaim scans to preserve the concise boundary while forbidding Marketplace, PR comment bot, SaaS, runtime MCP router, leaderboard, SOTA, automatic release publication, and fine-tuned default-router claims.

## 8. Validation and Closeout

- [x] 8.1 Run `python -m pytest -q`.
- [x] 8.2 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 8.3 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check`.
- [x] 8.4 Run `git diff --check`.
- [x] 8.5 Run existing local simulations for drift-check, CI summary, consumer smoke, Pages, or Validate workflow if present.
- [x] 8.6 Report changed files grouped by README, version metadata, docs, examples, and tests; report remaining stale wording, overclaim status, validation results, and any `v0.2.1` patch-release recommendation without publishing.
