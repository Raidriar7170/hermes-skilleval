## 1. Tests

- [x] 1.1 Add RED tests for the `v0.2.0` release decision JSON, Markdown, manifest, evidence links, and forbidden claims.
- [x] 1.2 Add project-surface coverage for README/usage/evidence-map/Human Brief links and release-boundary wording.

## 2. Decision Package

- [x] 2.1 Generate `docs/demo/v0.2.0-release-decision/release-decision.json` from committed Phase 16/17/18 and action smoke evidence.
- [x] 2.2 Add `release-decision.md` and `input-manifest.json` with reviewer-readable rationale and source artifact paths.
- [x] 2.3 Ensure the package records `NEEDS_REVIEW`, `published: false`, `KEEP_BASELINE`, and no automatic release approval.

## 3. Docs And Briefs

- [x] 3.1 Link the decision package from README, usage docs, evidence map, and relevant release/reusable-action docs.
- [x] 3.2 Add a concise Chinese phase Human Brief for `v0.2.0-release-decision`.

## 4. Validation And Archive

- [x] 4.1 Run focused release-decision tests and full local validation.
- [x] 4.2 Run release-check and confirm no unreviewed Phase 17/18 artifact drift.
- [x] 4.3 Run Reviewer diff review and fix in-scope Must Fix items.
- [x] 4.4 Archive the OpenSpec change, generate loop report, and run final validation.
