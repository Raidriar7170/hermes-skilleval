# Hermes SkillEval Release Handoff

## One-line Positioning

Hermes SkillEval is a verification-gated skill routing and self-improvement
harness for Hermes-style agent skills, with reproducible JSONL, Markdown, and
HTML artifacts.

## Evidence Chain

| Phase | Evidence | Artifact |
|---|---|---|
| Phase 9 | Real skill-library migration protocol | `docs/phase9.md` |
| Phase 10 | Agent-in-the-loop migration traces | `docs/phase10.md` |
| Phase 11 | Deterministic evidence judge calibration | `docs/phase11.md` |
| Phase 12 | Offline skill metadata patch ranking | `docs/phase12.md` |
| Phase 13 | Patch simulation regression guard | `docs/phase13.md` |
| Phase 14 | Fine-tuned embedding router path | `docs/phase14.md` |
| Phase 15 | Held-out provenance pack | `docs/phase15.md` |
| Phase 16 | Blind validation and release gate | `docs/phase16.md` |
| Phase 17 | Calibrated release selector keeps baseline | `docs/phase17.md` |
| Phase 18 | CI-backed release reproducibility pack | `docs/phase18.md` |
| v0.2.0 historical decision | Pre-publish human release review package | `docs/demo/v0.2.0-release-decision/release-decision.md` |
| v0.2.0 historical final approval | Pre-publish human approval checklist | `docs/demo/v0.2.0-final-approval/final-approval.md` |
| v0.2.0 post-release | Current GitHub tag and GitHub Release record | `docs/demo/v0.2.0-post-release/post-release.md` |

## Reviewer Entry Points

- Dashboard: `docs/demo/phase16-blind-validation/dashboard.html`
- Blind validation summary: `docs/demo/phase16-blind-validation/regression-summary.json`
- Phase 16 comparison: `docs/demo/phase16-blind-validation/comparison.md`
- Phase 17 release decision: `docs/demo/phase17-calibrated-release-selector/release-decision.json`
- Phase 17 task decisions: `docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl`
- Phase 18 release manifest: `docs/demo/phase18-ci-release-reproducibility/release-manifest.json`
- Phase 18 reproducibility check: `docs/demo/phase18-ci-release-reproducibility/release-check-summary.json`
- v0.2.0 release decision: `docs/demo/v0.2.0-release-decision/release-decision.md`
- v0.2.0 release decision JSON: `docs/demo/v0.2.0-release-decision/release-decision.json`
- v0.2.0 input manifest: `docs/demo/v0.2.0-release-decision/input-manifest.json`
- v0.2.0 release notes: `docs/release-notes/v0.2.0.md`
- v0.2.0 final approval checklist: `docs/demo/v0.2.0-final-approval/final-approval.md`
- v0.2.0 final approval JSON: `docs/demo/v0.2.0-final-approval/final-approval.json`
- v0.2.0 final approval input manifest: `docs/demo/v0.2.0-final-approval/input-manifest.json`
- v0.2.0 final approval Human Brief: `docs/human-briefs/2026-06-04-v0-2-0-release-notes-and-final-approval.html`
- post-release onboarding cleanup Human Brief: `docs/human-briefs/2026-06-05-post-release-onboarding-cleanup.html`
- v0.2.0 post-release evidence: `docs/demo/v0.2.0-post-release/post-release.md`
- v0.2.1 patch release notes: `docs/release-notes/v0.2.1.md`
- Provenance: `docs/demo/phase15-held-out-generalization/provenance.md`
- Release check: `docs/demo/phase17-calibrated-release-selector/release-check-summary.json`

## Current Release Reading

Phase 16 is intentionally conservative. It reports `REVIEW_REQUIRED` rather
than a pass because the fine-tuned router preserved Recall@5 but worsened
negative-hit behavior on the blind task pack. This is useful release evidence:
the project can show both positive provenance and a guard that refuses to hide a
blind regression.

Phase 17 makes that reading explicit for default-router selection. The release
selector returns `KEEP_BASELINE`, keeps `baseline-minilm` as the default router,
and records `approved_for_default: false` for `finetuned-embedding`.

Phase 18 makes the release reading CI-reproducible. The release-check command
reruns the selector and public artifact guard, writes a manifest with artifact
hashes, and keeps the default-router decision at `KEEP_BASELINE`.

The v0.2.0 release decision package is historical pre-publish review evidence.
It records `NEEDS_REVIEW` and `Published: false`, links Phase 16/17/18 evidence
plus local and hosted reusable GitHub Action smoke, keeps
`finetuned-embedding` unapproved as default, and does not override the current
post-release publication record.

The v0.2.0 release notes summarize the published GitHub Release package,
implemented capabilities, and committed review evidence. The v0.2.0 final
approval checklist remains the historical pre-publish approval artifact: it
records Overall decision: `NEEDS_REVIEW`, Published: `false`, GO Conditions,
NO-GO Until, and Requires Human Confirmation. It is not automatic publication
and does not replace the post-release evidence.

The v0.2.0 post-release evidence records the actual GitHub tag and GitHub
Release facts: Published: `true`, Tag created: `true`, GitHub Release created:
`true`, Marketplace published: `false`, release URL
`https://github.com/Raidriar7170/hermes-skilleval/releases/tag/v0.2.0`, and
target commit `13af31ee4fd2e9eed4a40f643284120bc5afab9e`.

The v0.2.1 patch release notes package this post-release onboarding cleanup
only. They do not add runtime features, do not change the default router, and do
not imply Marketplace publication, SaaS, GitHub API PR comments, or runtime MCP
routing.

## Boundaries

The repository does not commit model checkpoints, private machine details, or
claims beyond self-built Hermes-style evidence.

This is a reusable repository Action, not a Marketplace-published Action, not a
GitHub API PR comment bot, not a SaaS dashboard, and not a runtime MCP router.
The historical v0.2.0 decision package is not GitHub API PR comments, not PR
annotations, not a public leaderboard, not a SOTA claim, not benchmark status,
not production readiness, not release approval, not automatic merge approval,
and not automatic publication.

The v0.2.0 final approval checklist follows the same boundary: not automatic
publication, not release approval, not Marketplace publication, not GitHub API
PR comments, not PR annotations, not SaaS, not a runtime MCP router, not a SOTA claim,
not benchmark status, not production readiness, and not automatic merge approval.
