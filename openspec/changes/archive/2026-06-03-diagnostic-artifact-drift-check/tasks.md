## 1. Drift Contract

- [x] 1.1 Add failing tests for semantic equality when diagnostic artifacts differ only by `generated_at`.
- [x] 1.2 Add failing tests for semantic drift and invalid artifact inputs.
- [x] 1.3 Implement artifact normalization and drift report generation.

## 2. CLI And Demo Coverage

- [x] 2.1 Add `skilleval diagnostic-artifact-drift-check` CLI wiring for file-pair and directory comparison.
- [x] 2.2 Add tests that compare the committed diagnostic onboarding demo artifacts against regenerated or copied artifacts with timestamp changes.
- [x] 2.3 Document usage in README, `docs/usage.md`, and the diagnostic demo README without GitHub API, annotation, Marketplace Action, SaaS, runtime router, SOTA, or release-approval claims.

## 3. Closeout

- [x] 3.1 Add a concise Chinese Human Brief for this phase.
- [x] 3.2 Run focused tests, full tests, release-check, diagnostic CI gate, OpenSpec validation, diff hygiene, and leak/overclaim scans.
