## 1. Gate Contract

- [x] 1.1 Add failing tests for diagnostic CI gate pass/fail/report behavior.
- [x] 1.2 Implement a small diagnostic CI gate module that validates artifact contracts and threshold policies.
- [x] 1.3 Add `skilleval diagnostic-ci-gate` CLI wiring with explicit artifact paths, threshold flags, and JSON/Markdown outputs.

## 2. GitHub Actions And Demo Evidence

- [x] 2.1 Add tests that the validation workflow runs the diagnostic CI gate from committed demo artifacts.
- [x] 2.2 Update `.github/workflows/validate.yml` with a lightweight diagnostic CI gate step using committed artifact inputs and temporary report outputs.
- [x] 2.3 Regenerate or add committed diagnostic CI gate report artifacts for the demo pack.

## 3. Documentation And Review Artifacts

- [x] 3.1 Document local and GitHub Actions usage in README and `docs/usage.md` without hosted/runtime/SOTA claims.
- [x] 3.2 Add a Chinese Human Brief for this phase.
- [x] 3.3 Run focused tests, full tests, release-check, OpenSpec validation, and diff hygiene checks.
