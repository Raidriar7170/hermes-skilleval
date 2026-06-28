## 1. OpenSpec And Scope

- [x] 1.1 Create PR-7 OpenSpec proposal, design, spec, and task artifacts.
- [x] 1.2 Keep PR-7 limited to evidence validation and reporting.

## 2. Tests First

- [x] 2.1 Add RED tests for allowed validity statuses and field-level `UNAVAILABLE`.
- [x] 2.2 Add RED tests for frozen external matrix input/hash/plan checks.
- [x] 2.3 Add RED tests for live-agent prompt hash, no-skill leakage, verifier, trace, and overlap checks.
- [x] 2.4 Add RED tests that promotion defaults to `KEEP_BASELINE` and invalid validity blocks promotion.

## 3. Evidence Validator

- [x] 3.1 Implement artifact loading, hash/digest checks, and structured check records.
- [x] 3.2 Implement external routing evidence validation and summary extraction.
- [x] 3.3 Implement live-agent evidence validation and summary extraction.
- [x] 3.4 Implement validity status derivation and conservative promotion gate.

## 4. CLI And Reporting

- [x] 4.1 Add a scoped CLI command for v0.3 evidence validation.
- [x] 4.2 Write JSON and optional Markdown decision reports.
- [x] 4.3 Add concise Chinese Human Brief for PR-7.

## 5. Validation

- [x] 5.1 Run focused PR-7 tests.
- [x] 5.2 Run `python -m pytest -q`.
- [x] 5.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 5.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 5.5 Run `git diff --check`.
- [x] 5.6 Run v0.3 YAML parse check.
- [x] 5.7 Run CRLF/new-file line-ending check.
