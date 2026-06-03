## Why

Skill Library Maintainers need a lightweight way to catch diagnostic regressions
in pull requests after the scan/lint/inspect/route artifact contract exists.
The next product step is a repo-local CI gate that can fail on review-worthy
diagnostic risk without claiming hosted SaaS, runtime routing, or benchmark SOTA.

## What Changes

- Add a diagnostic CI gate command that reads committed diagnostic artifacts and
  applies conservative thresholds for lint findings, conflict clusters, route
  risk flags, and missing route evidence.
- Add a GitHub Actions workflow example/job that reads committed diagnostic demo
  artifacts and runs the diagnostic CI gate with temporary report outputs.
- Add tests and docs that show how maintainers can adapt the gate to their own
  skill library while preserving the existing release-check workflow.
- No breaking changes.

## Capabilities

### New Capabilities

- `diagnostic-ci-gate`: CI-oriented validation for diagnostic skill-library
  artifacts and example GitHub Actions wiring.

### Modified Capabilities

- `diagnostic-skill-library-onboarding`: Diagnostic artifacts become actionable
  in CI through a bounded gate while preserving unlabeled onboarding behavior.

## Impact

- Affected code: CLI parser, a small CI gate module, diagnostic demo docs,
  project surface tests, and GitHub workflow.
- Affected artifacts: diagnostic demo CI gate JSON/Markdown reports are
  committed for local review; GitHub Actions writes fresh reports to
  `$RUNNER_TEMP`.
- Dependencies: no new third-party dependencies.
- Non-goals: no Marketplace Action release, no PR annotation API, no merge/push
  automation, no SaaS backend, no runtime MCP router.
