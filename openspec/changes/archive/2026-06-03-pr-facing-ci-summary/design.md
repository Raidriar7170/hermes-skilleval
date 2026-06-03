## Context

The validate workflow already runs the core reliability checks: pytest, Phase 18
release-check, diagnostic CI gate, diagnostic artifact regeneration, PR review
packet generation, and semantic artifact drift checking. It now needs a
reviewer-friendly Markdown summary so a maintainer can understand the result
from the GitHub Actions summary panel instead of reading raw logs.

The summary must remain local and artifact-based. It must not call the GitHub
API, post comments, write annotations, require tokens, publish a Marketplace
Action, introduce SaaS, or make runtime-router or release-approval claims.

## Goals / Non-Goals

**Goals:**

- Add `skilleval ci-summary` as a deterministic local summary writer.
- Summarize explicit check outcomes for pytest, OpenSpec validation,
  release-check, diagnostic CI gate, diagnostic artifact drift, and overclaim
  scanning.
- Group changed files into stable categories for review.
- Emit JSON and Markdown with a final `ALLOW_MERGE` / `BLOCK_MERGE` decision.
- Write the Markdown output to `$GITHUB_STEP_SUMMARY` in the validate workflow.
- Keep enough local command shape for developers to simulate the summary before
  pushing.

**Non-Goals:**

- GitHub API comments, PR annotations, Checks API integration, or bots.
- Marketplace Action packaging or reusable workflow publication.
- Runtime MCP router integration.
- SaaS dashboards, hosted services, tokens, or external state.
- Changing the underlying release-check, diagnostic gate, or drift-check
  decision semantics.

## Decisions

- **Explicit check inputs.** `skilleval ci-summary` accepts `--check name=STATUS`
  pairs instead of running pytest, OpenSpec, release-check, or drift-check
  internally. The workflow remains responsible for running checks; the command
  summarizes their outcomes.
- **Final decision from required checks.** Any required check outside `PASS`,
  `SUCCESS`, or `SKIPPED_OPTIONAL` blocks the merge summary. This keeps
  `ALLOW_MERGE` conservative and easy to test.
- **Reuse release overclaim scanning.** The summary imports the existing
  `find_overclaim_matches()` helper instead of duplicating claim detection.
- **Changed files from an explicit file list.** The command reads a sorted
  changed-file list produced by git in CI or by a local developer. It does not
  call GitHub APIs or infer PR metadata.
- **Workflow runs checks with captured outcomes.** Validation steps use
  `continue-on-error: true`; a final summary/enforcement step always runs,
  writes `$GITHUB_STEP_SUMMARY`, and exits non-zero only when the summary
  decision is `BLOCK_MERGE`.
- **Pinned OpenSpec CLI install.** The workflow installs
  `@fission-ai/openspec@1.3.1` for `openspec validate --all --strict`, matching
  the locally validated CLI version.

## Risks / Trade-offs

- [Risk] `continue-on-error` could hide failures. -> Mitigation: final
  enforcement reads the summary JSON and fails the job on `BLOCK_MERGE`.
- [Risk] Status spelling varies between local use and GitHub Actions outcomes.
  -> Mitigation: normalize common statuses such as `success`, `failure`,
  `cancelled`, `PASS`, `FAIL`, and `REVIEW_REQUIRED`.
- [Risk] Changed-file grouping can become noisy. -> Mitigation: keep v1 groups
  broad and deterministic: workflow, source, tests, docs, OpenSpec,
  diagnostics, and other.
- [Risk] Reviewers may confuse the summary with automation products. ->
  Mitigation: Markdown and docs explicitly state it is a local/GitHub Actions
  summary, not a GitHub API comment bot, PR annotation system, Marketplace
  Action, SaaS, runtime MCP router, or release approval.
