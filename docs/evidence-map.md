# Hermes SkillEval Evidence Map

This page is a navigation layer, not a second source of truth. The canonical
evidence remains in the linked repository artifacts; this map only groups the
current proof chain by reviewer task and records what each artifact can and
cannot support.

Boundary: this is not a Marketplace Action, not GitHub API PR comments, not PR
annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not
production readiness, not release approval, and not automatic merge approval.

## Project Positioning

| Artifact | Helps verify | Limit |
|---|---|---|
| [`README.md`](../README.md) | Front-door project framing, current release evidence, diagnostic onboarding path, and reviewer quick start. | The README summarizes; phase files and demo artifacts remain authoritative. |
| [`CONTEXT.md`](../CONTEXT.md) | Durable domain language: developer-facing routing reliability toolkit, Skill Library Maintainer, Diagnostic Onboarding Path, and Release Gate. | It defines vocabulary, not a new release result. |
| [`docs/release-handoff.md`](release-handoff.md) | Reviewer-ready handoff for the conservative Phase 16-18 release story. | It is not release approval and does not promote a runtime integration. |
| [`docs/failure-gallery.md`](failure-gallery.md) | Reviewer-facing gallery of blocked-regression and diagnostic-risk examples. | It is an example index, not canonical evidence or a new verdict. |
| [`docs/interview-project-overview.html`](interview-project-overview.html) | Human-readable project explanation for interviews and portfolio review. | It is explanatory packaging, not benchmark leadership evidence. |

## Release-Gate Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`docs/demo/phase16-blind-validation/comparison.md`](demo/phase16-blind-validation/comparison.md) | Blind validation found unchanged Recall@5 but worse ranking and negative-skill behavior for the fine-tuned candidate. | It is a project release-gate input, not a public leaderboard. |
| [`docs/demo/phase17-calibrated-release-selector/release-decision.md`](demo/phase17-calibrated-release-selector/release-decision.md) | The selector records `KEEP_BASELINE`; `baseline-minilm` remains the default. | It does not approve a product launch or automatic merge. |
| [`docs/demo/phase18-ci-release-reproducibility/release-manifest.md`](demo/phase18-ci-release-reproducibility/release-manifest.md) | Phase 18 reproduces the release decision and records manifest-level evidence. | It proves reproducibility of the local release gate, not production readiness. |
| [`docs/phase18.md`](phase18.md) | Narrative summary for the CI-backed reproducibility pack. | It should be read with the manifest and release-check summary. |

## Diagnostic Onboarding Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`docs/demo/diagnostic-onboarding/README.md`](demo/diagnostic-onboarding/README.md) | The zero-label scan -> lint -> inspect -> route -> dashboard path for a Skill Library Maintainer. | This is committed local diagnostic evidence, not SaaS. |
| [`docs/demo/diagnostic-onboarding/ci-gate-report.md`](demo/diagnostic-onboarding/ci-gate-report.md) | Artifact-based diagnostic CI validation over generated demo outputs. | It is not a PR annotation system and does not block merges by itself. |
| [`docs/demo/diagnostic-onboarding/pr-review-packet.md`](demo/diagnostic-onboarding/pr-review-packet.md) | Local reviewer packet derived from diagnostic gate evidence. | It does not post GitHub API PR comments. |
| [`docs/demo/diagnostic-onboarding/dashboard.html`](demo/diagnostic-onboarding/dashboard.html) | Static diagnostic inspection surface for source summary, lint findings, route risks, and conflict clusters. | It is not a runtime console. |

## External-Style Validation Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`docs/demo/external-skill-library-validation/README.md`](demo/external-skill-library-validation/README.md) | External-style evidence pack for Markdown skill folders and MCP-style tool schema sources. | It is a bounded local pack, not benchmark status. |
| [`Markdown skill track CI gate`](demo/external-skill-library-validation/markdown-skills/ci-gate-report.md) | Regenerated artifacts for Markdown `SKILL.md` source shapes. | It does not claim universal skill-library coverage. |
| [`MCP tool schema track CI gate`](demo/external-skill-library-validation/mcp-tool-schema/ci-gate-report.md) | Regenerated artifacts for MCP-style tool schema source shapes. | It is not a runtime MCP router. |
| [`External pack Human Brief`](human-briefs/2026-06-03-autonomous-loop-external-skill-library-validation-pack.html) | Chinese phase summary for the autonomous-loop external validation pack. | Human Briefs are review aids, not source artifacts. |

## PR-Facing CI Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`.github/workflows/validate.yml`](../.github/workflows/validate.yml) | The validate workflow runs pytest, OpenSpec validation, release-check, diagnostic gates, drift checks, external-pack regeneration, and CI summary enforcement. | It uses GitHub Actions summary output, not GitHub API PR comments. |
| [`OpenSpec: PR-facing CI summary`](../openspec/specs/pr-facing-ci-summary/spec.md) | The archived spec for the local/GitHub Actions summary surface. | It is not a Marketplace Action and not PR annotations. |
| [`PR-facing CI Summary Human Brief`](human-briefs/2026-06-03-pr-facing-ci-summary.html) | Human-readable summary of the CI summary phase, validation commands, and boundaries. | It does not replace workflow logs or JSON artifacts. |

## OpenSpec Specs

| Artifact | Helps verify | Limit |
|---|---|---|
| [`diagnostic-skill-library-onboarding`](../openspec/specs/diagnostic-skill-library-onboarding/spec.md) | Diagnostic onboarding contract and expected maintainer flow. | Specs define intended behavior; tests and artifacts verify current behavior. |
| [`diagnostic-ci-gate`](../openspec/specs/diagnostic-ci-gate/spec.md) | Artifact-based gate requirements for diagnostic outputs. | It is not release approval. |
| [`diagnostic-artifact-drift-check`](../openspec/specs/diagnostic-artifact-drift-check/spec.md) | Drift-check behavior for regenerated diagnostic artifacts. | It compares artifacts; it does not judge product readiness. |
| [`diagnostic-pr-review-surface`](../openspec/specs/diagnostic-pr-review-surface/spec.md) | Local PR review packet surface for diagnostics. | It is not GitHub API PR comments. |
| [`external-skill-library-validation-pack`](../openspec/specs/external-skill-library-validation-pack/spec.md) | External-style validation pack requirements. | It is not a SOTA claim. |
| [`pr-facing-ci-summary`](../openspec/specs/pr-facing-ci-summary/spec.md) | CI summary inputs, outputs, and bounded decision language. | It is not automatic merge approval. |

## Human Briefs

| Artifact | Helps verify | Limit |
|---|---|---|
| [`2026-06-03 docs evidence map`](human-briefs/2026-06-03-docs-evidence-map.html) | This phase's Chinese companion brief: status, changed files, validation plan, and boundaries. | Generated for review convenience; OpenSpec and source artifacts remain authoritative. |
| [`2026-06-03 PR-facing CI summary`](human-briefs/2026-06-03-pr-facing-ci-summary.html) | Summary of local/GitHub Actions CI summary implementation and validation. | It is not a workflow log. |
| [`2026-06-03 external validation pack`](human-briefs/2026-06-03-external-skill-library-validation-pack.html) | Summary of external-style validation pack outputs and validation. | It is not benchmark status. |
| [`2026-06-03 autonomous-loop external validation pack`](human-briefs/2026-06-03-autonomous-loop-external-skill-library-validation-pack.html) | Autonomous-loop brief for the same external validation phase. | It is a companion narrative, not a second source of truth. |
