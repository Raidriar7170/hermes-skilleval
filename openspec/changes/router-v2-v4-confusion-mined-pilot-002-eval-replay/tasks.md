## 1. Replay authority and frozen reuse

- [x] 1.1 Add focused RED tests for the exact pilot-002 manifest, five-field replacement boundary, pilot-001 training-root reuse, new output namespace, unique attempt token, and fail-before-attempt hash checks.
- [x] 1.2 Implement the minimal separated training/evaluation roots and canonical pre-attempt pilot manifest with all required replacement, model-only truth, frozen lineage, query-order, metric, and gate fields.
- [x] 1.3 Validate every pilot-001 run-pack, Arm A/B/C model manifest, checkpoint path, model-file SHA/size, and base revision without rebuilding the run pack or invoking training; prove drift stops before attempt consumption.
- [x] 1.4 Run focused replay/smoke/evaluation tests, Ruff, mypy, strict change validation, and `git diff --check` before any pilot-002 attempt.

## 2. One evaluation attempt

- [x] 2.1 Freeze a clean evaluation-code commit and create only the fixed pilot-002 `0700` output namespace while leaving pilot-001 attempt and training evidence unchanged.
- [x] 2.2 Run the final pre-attempt authority check and record the exact pilot-002 manifest, attempt token, frozen hashes, and absence of any existing attempt marker or artifact.
- [x] 2.3 Consume exactly one pilot-002 evaluation attempt; do not retry on failure and do not invoke training, run-pack building, mining, review, blind-v2, or pilot-003 paths.
- [x] 2.4 Preserve per-arm/per-seed metrics, mean/sample standard deviation, paired wins/losses, failure slices, first-negative rank, latency, and raw counts for 16 positives and 9 negative labels; apply the unchanged gate and record only its authorized decision.

## 3. Conservative evidence and PR closeout

- [x] 3.1 Copy the canonical pilot manifest and small evaluation evidence into the pilot-002 repository namespace, then update README and `docs/resume.md` with raw-count-first results and all required limitations.
- [x] 3.2 Add the Chinese L2 Human Brief with conclusion, hashes, verification, risks, non-overclaim boundary, and PR-only next step.
- [x] 3.3 Run focused and full tests, Ruff, mypy non-regression, strict OpenSpec validation, artifact/truth guards, smoke regression, and `git diff --check`.
- [x] 3.4 Obtain the required read-only Reviewer verdict, resolve only in-scope Must Fix findings, and re-run affected verification.
- [x] 3.5 Commit and push the bounded result, create the PR, wait for complete CI, and stop without merge, archive, release, deploy, tuning, or another pilot.

## 4. Post-attempt evidence repair

- [x] 4.1 Record the user's 2026-07-15 ratification of pilot-002 and PR #38's existing Human Brief and existing test scope without treating it as human review; preserve zero-human and `KEEP_BASELINE` truth and record `new_tests_authorized=false`.
- [x] 4.2 Copy the exact existing 144-row route artifact byte-for-byte into repository evidence and add the seven-row audit manifest outside the frozen artifact set.
- [x] 4.3 Add a self-sealed truth erratum that binds the unchanged pilot manifest, attempt ledger, summary, route artifact, and full model-only truth block without a rerun.
- [x] 4.4 Correct the result report, existing Human Brief, proposal, design, spec, and task truth surfaces without changing `src/**`, `tests/**`, or frozen attempt files.
- [x] 4.5 Run local JSON/hash/truth/OpenSpec/diff validation and confirm the frozen pilot manifest, started marker, terminal, and summary are unchanged from HEAD.
- [x] 4.6 Obtain a final read-only Reviewer verdict for the post-attempt evidence-repair diff and resolve only in-scope Must Fix findings.
- [ ] 4.7 After separate authorization, commit and push the repair and confirm post-repair exact-head CI; until then record the state as an uncommitted local diff with no post-repair exact-head CI.
