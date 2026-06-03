## 1. Workflow Coverage

- [x] 1.1 Add a failing project-surface test that the validation workflow runs diagnostic artifact drift checking from regenerated demo artifacts.
- [x] 1.2 Update `.github/workflows/validate.yml` to regenerate the diagnostic onboarding demo into `$RUNNER_TEMP` and run `skilleval diagnostic-artifact-drift-check`.
- [x] 1.3 Ensure drift check JSON and Markdown reports are written outside the repository working tree.

## 2. Documentation And Closeout

- [x] 2.1 Update README / usage docs to mention GitHub Actions drift-check coverage without PR annotation, Marketplace Action, SaaS, runtime-router, or release-approval claims.
- [x] 2.2 Run focused workflow/docs tests, full tests, release-check, diagnostic gates, OpenSpec validation, diff hygiene, and leak/overclaim scans.
- [x] 2.3 Add a concise Chinese Human Brief for this phase.
