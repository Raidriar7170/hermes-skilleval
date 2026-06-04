## Context

The repository now has diagnostic onboarding, external-style validation packs,
artifact drift checks, PR-facing CI summaries, and Node 24 preflight coverage.
Those pieces prove the internal validation workflow, but external users still
need an easy fresh-repository entry point.

GitHub composite actions are appropriate for this release-candidate scaffold:
they can live at repository root as `action.yml`, declare inputs, run shell
steps, and conditionally use `actions/upload-artifact`. The scaffold is not a
Marketplace publication and does not require token permissions.

## Goals / Non-Goals

**Goals:**
- Provide a root-level composite action that external repositories can reference
  by branch or commit while the project evaluates release readiness.
- Support required inputs `skill-path` and `benchmark-path`, threshold inputs
  `min-recall-at-k` and `max-negative-hit-rate`, and `upload-artifacts`.
- Write deterministic gate artifacts and a `$GITHUB_STEP_SUMMARY` Markdown
  summary with `ALLOW_MERGE` / `BLOCK_MERGE`.
- Include a fresh-clone example that runs offline with public-safe fixtures.

**Non-Goals:**
- No `v0.2.0` tag, GitHub Release, or Marketplace Action publication in this
  phase.
- No GitHub API PR comment bot, annotations, token permissions, SaaS dashboard,
  or runtime MCP router.
- No reuse of the repo-specific Phase 17/18 `release-check` as an external
  benchmark gate.
- No standard external benchmark, SOTA, production-readiness, release approval,
  or automatic merge approval claim.

## Decisions

- Add a new `skilleval github-action-gate` command instead of embedding a long
  shell script in `action.yml`. The command can reuse existing index/eval/report
  primitives, write a stable JSON/Markdown gate artifact, and fail closed when
  thresholds are not met.
- Use `hybrid` router and `top-k=5` by default for the RC example. The action is
  about packaging the workflow, not proving a new router.
- Generate `ci-summary` from the gate outcome and an overclaim scan of the
  example/docs surfaces. This preserves the existing summary contract while
  avoiding PR comments or annotations.
- Treat artifact drift as optional in this RC scaffold: the action can compare
  committed expected artifacts only when a future input is added or a documented
  baseline exists. The required Phase 5a path focuses on reproducible gate
  artifacts and fresh-clone smoke rather than inventing a baseline contract.
- Document action usage with `@main` or a commit SHA placeholder. `@v0.2.0`
  remains a future release-confirmation step.

## Risks / Trade-offs

- [Risk] Users may read root `action.yml` as a Marketplace release. -> Mitigation:
  action name and docs call it an RC scaffold and explicitly say it is not a
  Marketplace Action release.
- [Risk] External benchmark gate fails because benchmark labels are missing or
  skill IDs do not match. -> Mitigation: example fixtures include both gold and
  negative labels and tests run a fresh-clone smoke.
- [Risk] Composite action shell quoting can drift from the CLI. -> Mitigation:
  keep action steps thin and delegate metrics to `skilleval github-action-gate`.
- [Risk] `upload-artifacts` requires `actions/upload-artifact`. -> Mitigation:
  keep it optional and do not require tokens or extra permissions.
