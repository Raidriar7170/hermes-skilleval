## 1. Test-First Contract

- [x] 1.1 Add tests for the external validation pack artifact contract,
      bounded wording, and deterministic regeneration flow.
- [x] 1.2 Add tests that classify external validation pack changed files as
      diagnostics in the PR-facing CI summary.

## 2. External Pack Artifacts

- [x] 2.1 Add public-safe external-style Markdown skill and MCP tool schema
      source fixtures.
- [x] 2.2 Regenerate and commit scan, lint, inspect, route, dashboard, CI gate,
      and PR review packet artifacts for both source tracks.
- [x] 2.3 Extend diagnostic artifact drift comparison to support the external
      validation pack artifact list.

## 3. CI and Documentation

- [x] 3.1 Wire GitHub Actions validate workflow to regenerate and drift-check the
      external validation pack into `$RUNNER_TEMP`.
- [x] 3.2 Update README and `docs/usage.md` with the external pack purpose,
      local simulation commands, and non-goals.
- [x] 3.3 Generate the phase Human Brief HTML and keep it linked to source
      artifacts.

## 4. Validation and Archive

- [x] 4.1 Run focused tests, full pytest, OpenSpec strict validation,
      release-check, diagnostic drift checks, CI summary simulation, and
      whitespace checks.
- [x] 4.2 Review the diff, fix Must Fix issues, archive the OpenSpec change,
      then rerun final validation.
