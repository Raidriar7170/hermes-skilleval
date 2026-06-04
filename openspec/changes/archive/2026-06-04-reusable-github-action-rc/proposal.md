## Why

External Skill Library Maintainers can already inspect local demo artifacts, but
there is no reusable GitHub Actions entry point that they can try from a fresh
repository. The next bounded step is a reusable action release-candidate scaffold
that proves the external onboarding shape without publishing a tag or claiming a
Marketplace release.

## What Changes

- Add a root-level `action.yml` composite action that runs SkillEval against an
  external skill library and labeled benchmark using explicit thresholds.
- Add a thin `skilleval github-action-gate` CLI command that writes deterministic
  JSON/Markdown gate artifacts and a PR-facing CI summary without using GitHub
  API comments, annotations, tokens, SaaS, or runtime router services.
- Add `examples/github-action/` with public-safe skills, benchmark tasks, and an
  example workflow that references the action by branch or commit placeholder,
  not by an unpublished `v0.2.0` tag.
- Document external onboarding and fresh-clone smoke usage in README and
  `docs/usage.md` with conservative boundaries.
- Add focused tests for action metadata, example fixtures, gate behavior,
  summary wording, and fresh-clone smoke.
- Generate Human Brief and loop reports for the phase.

## Capabilities

### New Capabilities
- `reusable-github-action-rc`: Reusable GitHub composite action release-candidate
  scaffold for external benchmark gating and bounded CI summaries.

### Modified Capabilities
- None.

## Impact

- `action.yml`
- `examples/github-action/`
- `src/hermes_skilleval/`
- `tests/`
- `README.md`
- `docs/usage.md`
- `docs/human-briefs/`
- OpenSpec change artifacts
