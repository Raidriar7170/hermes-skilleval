## 1. Summary Core

- [x] 1.1 Add failing tests for CI summary decision logic, Markdown structure, overclaim scan results, and changed-file grouping.
- [x] 1.2 Implement `src/hermes_skilleval/ci_summary.py` with JSON and Markdown output.
- [x] 1.3 Add `skilleval ci-summary` CLI wiring with explicit check, report, changed-file, overclaim-root, JSON output, and Markdown output arguments.

## 2. Workflow And Documentation

- [x] 2.1 Add failing workflow surface tests for `$GITHUB_STEP_SUMMARY`, `if: always()`, `skilleval ci-summary`, and final decision enforcement.
- [x] 2.2 Update `.github/workflows/validate.yml` to capture validation outcomes, generate the CI summary, append it to `$GITHUB_STEP_SUMMARY`, optionally upload reports, and enforce `BLOCK_MERGE`.
- [x] 2.3 Update README and `docs/usage.md` with local simulation commands and bounded PR-facing CI summary wording.

## 3. Closeout

- [x] 3.1 Add focused tests for the CLI and project surface without overclaiming Marketplace Action, PR comment bot, MCP runtime router, SaaS, SOTA, or release approval.
- [x] 3.2 Run focused tests, full tests, OpenSpec validation, release-check, drift-check, git diff hygiene, and overclaim/leak scans.
- [x] 3.3 Add a concise Chinese Human Brief for this phase.
