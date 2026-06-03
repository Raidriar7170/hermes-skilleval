## Why

The diagnostic onboarding path already proves the workflow on a small local
Markdown demo library, but it does not yet show how the same artifact contract
behaves against an external-style skill library shape. This phase closes that
evidence gap without introducing hosted services, GitHub API comments,
Marketplace packaging, or runtime router claims.

## What Changes

- Add a committed External Skill Library Validation Pack under `docs/demo/`
  with public-safe sample sources and regenerated diagnostic artifacts.
- Cover both stable Skill Source shapes already supported by the diagnostic
  adapter: Markdown `SKILL.md` folders and MCP-style tool schema JSON.
- Add tests that verify artifact contracts, route evidence, bounded wording,
  drift-check stability, and CI summary grouping for the new pack.
- Extend GitHub Actions validation to regenerate the pack into `$RUNNER_TEMP`,
  run the diagnostic CI gate and artifact drift check, and include the pack in
  the PR-facing CI summary and uploaded validation artifacts.
- Update README and usage docs with local simulation commands and clear
  non-goals.

## Capabilities

### New Capabilities

- `external-skill-library-validation-pack`: committed evidence pack and CI
  validation flow for external-style skill-library sources.

### Modified Capabilities

- `pr-facing-ci-summary`: group external validation pack files as diagnostic
  evidence and expose the external pack check in the validate summary.

## Impact

- Affected code: diagnostic artifact drift comparison, CI summary grouping, and
  CLI-facing tests.
- Affected docs: README, `docs/usage.md`, and a new demo README.
- Affected CI: `.github/workflows/validate.yml` regenerates and validates the
  external-style pack without new tokens, secrets, network services, or
  external API calls.
- No breaking changes to existing diagnostic, benchmark, dashboard, or
  release-check commands.
