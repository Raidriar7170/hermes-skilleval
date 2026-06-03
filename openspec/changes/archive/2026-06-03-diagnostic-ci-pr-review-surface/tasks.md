## 1. Review Packet Contract

- [x] 1.1 Add failing tests for PR review packet JSON and Markdown output from a passing diagnostic gate report.
- [x] 1.2 Add failing tests for failed gate reports and invalid gate-report inputs.
- [x] 1.3 Implement the review packet module that summarizes verdict, policy status, attention items, evidence gaps, and source artifacts.

## 2. CLI And Demo Artifacts

- [x] 2.1 Add `skilleval diagnostic-pr-review-surface` CLI wiring with explicit input and output paths.
- [x] 2.2 Generate committed demo review packet JSON and Markdown artifacts from `docs/demo/diagnostic-onboarding/`.
- [x] 2.3 Add tests that protect the demo review packet artifact contract and bounded wording.

## 3. Documentation And Closeout

- [x] 3.1 Document local review packet usage in README, `docs/usage.md`, and the diagnostic demo README without GitHub API, annotation, Marketplace Action, SaaS, runtime router, or SOTA claims.
- [x] 3.2 Add a concise Chinese Human Brief for this phase.
- [x] 3.3 Run focused tests, full tests, release-check, diagnostic CI gate, OpenSpec validation, diff hygiene, and leak/overclaim scans.
