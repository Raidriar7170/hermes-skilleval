# v0.2.0 Release Decision

This v0.2.0 release decision is a reviewer package for human release review,
not automatic publication.

- Decision: `NEEDS_REVIEW`
- Published: `false`
- Router decision: `KEEP_BASELINE`
- Default router: `baseline-minilm`

| Field | Value |
|---|---|
| Decision | `NEEDS_REVIEW` |
| Published | `false` |
| Router decision | `KEEP_BASELINE` |
| Default router | `baseline-minilm` |
| Candidate router | `finetuned-embedding` |
| Candidate default approval | `false` |
| Action RC evidence | RC support evidence only |

`finetuned-embedding` is not approved as default. Phase 16/17/18 keep
`baseline-minilm` as the default router, while local and hosted action smoke
support a human release review of the reusable action RC.

## Evidence Inputs

| Evidence | Result | Link |
|---|---|---|
| Phase 16 blind validation | `REVIEW_REQUIRED`; two regressions | [`comparison.md`](../phase16-blind-validation/comparison.md), [`regression-summary.json`](../phase16-blind-validation/regression-summary.json), [`route-diffs.jsonl`](../phase16-blind-validation/route-diffs.jsonl) |
| Phase 17 release selector | `KEEP_BASELINE`; `baseline-minilm` remains default | [`release-decision.md`](../phase17-calibrated-release-selector/release-decision.md), [`release-decision.json`](../phase17-calibrated-release-selector/release-decision.json) |
| Phase 18 reproducibility | `PASS`; release-check summary is `PASS` | [`release-manifest.md`](../phase18-ci-release-reproducibility/release-manifest.md), [`release-manifest.json`](../phase18-ci-release-reproducibility/release-manifest.json), [`release-check-summary.json`](../phase18-ci-release-reproducibility/release-check-summary.json) |
| Local external-consumer action smoke | `ALLOW_MERGE`; RC support evidence | [`gate-report.md`](../external-repo-action-smoke-pack/output/gate-report.md), [`ci-summary.md`](../external-repo-action-smoke-pack/output/ci-summary.md) |
| Hosted consumer action smoke | `ALLOW_MERGE`; hosted RC support evidence | [`run-metadata.json`](../hosted-consumer-action-smoke/run-metadata.json), [`gate-report.md`](../hosted-consumer-action-smoke/output/gate-report.md), [`ci-summary.md`](../hosted-consumer-action-smoke/output/ci-summary.md) |

Machine-readable package files:
[`release-decision.json`](release-decision.json) and
[`input-manifest.json`](input-manifest.json).

## Boundary

Current evidence supports human release review and requires explicit human confirmation
before tag creation, GitHub Release creation, Marketplace publication, or any
public release action.

This package is not a Marketplace Action release, not GitHub API PR comments,
not PR annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not
benchmark status, not production readiness, not release approval, not automatic
merge approval, and not a v0.2.0 release.
