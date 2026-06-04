## 1. Tests

- [x] 1.1 Add RED tests for `docs/release-notes/v0.2.0.md`,
  `docs/demo/v0.2.0-final-approval/final-approval.json`,
  `final-approval.md`, and `input-manifest.json`.
- [x] 1.2 Add project-surface coverage for README, usage, evidence map, release
  handoff, and Human Brief links/boundary wording.

## 2. Release Notes And Checklist

- [x] 2.1 Add `docs/release-notes/v0.2.0.md` with implemented capabilities,
  evidence links, and publication boundaries.
- [x] 2.2 Add final approval JSON, Markdown checklist, and input manifest under
  `docs/demo/v0.2.0-final-approval/`.
- [x] 2.3 Ensure checklist status remains `NEEDS_REVIEW` and does not authorize
  tag creation, GitHub Release creation, Marketplace publication, or automatic
  publication.

## 3. Public Surfaces And Brief

- [x] 3.1 Link release notes and final approval artifacts from README,
  `docs/usage.md`, `docs/evidence-map.md`, and `docs/release-handoff.md`.
- [x] 3.2 Add a concise Chinese Human Brief for this phase.

## 4. Validation And Review

- [x] 4.1 Run focused tests and full local validation.
- [x] 4.2 Run OpenSpec strict validation, release-check, tag/release absence
  checks, overclaim/secret scan, and `git diff --check`.
- [x] 4.3 Run Reviewer diff review and fix in-scope Must Fix items.
- [x] 4.4 Archive the OpenSpec change and rerun final validation.
