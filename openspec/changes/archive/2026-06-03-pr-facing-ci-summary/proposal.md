## Why

The validate workflow now runs pytest, OpenSpec validation, release-check,
diagnostic gates, and artifact drift checks, but reviewers still need to read
raw logs to understand the result. A PR-facing Markdown summary gives maintainers
a stable, local-first review surface without introducing GitHub API comments,
tokens, Marketplace Action packaging, or runtime services.

## What Changes

- Add `skilleval ci-summary` to write a deterministic JSON and Markdown summary
  from CI check statuses, report paths, changed files, and overclaim scan
  results.
- Add an `ALLOW_MERGE` / `BLOCK_MERGE` decision based on explicit check inputs.
- Update `.github/workflows/validate.yml` to write the summary to
  `$GITHUB_STEP_SUMMARY`.
- Optionally upload local diagnostic/release reports as workflow artifacts when
  GitHub Actions supports the built-in artifact action.
- Document local simulation usage in README and `docs/usage.md` with bounded
  claims.
- Add tests for stable summary output, changed-file grouping, decision logic,
  and overclaim-safe wording.

## Capabilities

### New Capabilities

- `pr-facing-ci-summary`: Local and GitHub Actions Markdown summaries for
  SkillEval CI checks.

### Modified Capabilities

- None.

## Impact

- New module and CLI entry point under `src/hermes_skilleval/`.
- Tests for summary generation, CLI wiring, and workflow surface.
- `.github/workflows/validate.yml` summary and optional artifact upload steps.
- README, `docs/usage.md`, OpenSpec archive, and Human Brief artifacts.
