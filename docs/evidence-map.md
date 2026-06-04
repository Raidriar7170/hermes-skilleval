# Hermes SkillEval Evidence Map

This page is a navigation layer, not a second source of truth. The canonical
evidence remains in the linked repository artifacts; this map only groups the
current proof chain by reviewer task and records what each artifact can and
cannot support.

Boundary: this is not a Marketplace Action, not a Marketplace Action release,
not GitHub API PR comments, not PR annotations, not SaaS, not a runtime MCP
router, not a SOTA claim, not production readiness, not release approval, not
automatic merge approval, and not a v0.2.0 release.

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
| [`v0.2.0 release decision`](demo/v0.2.0-release-decision/release-decision.md) | Records `NEEDS_REVIEW`, `Published: false`, `KEEP_BASELINE`, and the Phase 16/17/18 plus action smoke evidence chain. | It is human release review evidence, not automatic publication, not release approval, and not a v0.2.0 release. |
| [`v0.2.0 release decision JSON`](demo/v0.2.0-release-decision/release-decision.json) | Machine-readable decision fields for release review, router selection, and action RC support evidence. | It does not create a tag, GitHub Release, Marketplace publication, or deployment. |
| [`v0.2.0 input manifest`](demo/v0.2.0-release-decision/input-manifest.json) | Source artifact paths, sizes, and hashes used by the release decision package. | It is a package manifest, not a second source of truth. |
| [`v0.2.0 release notes`](release-notes/v0.2.0.md) | Prepared release notes for human approval, limited to implemented capabilities and committed evidence links. | It is not a tag, GitHub Release, Marketplace publication, or proof of publication. |
| [`v0.2.0 final approval checklist`](demo/v0.2.0-final-approval/final-approval.md) | Reviewer-readable GO Conditions, NO-GO Until, and Requires Human Confirmation checklist. | It is release-review packaging, not release approval or automatic publication. |
| [`v0.2.0 final approval JSON`](demo/v0.2.0-final-approval/final-approval.json) | Machine-readable final approval fields: Overall decision: `NEEDS_REVIEW`, Published: `false`, and source checks. | It does not create a tag, GitHub Release, Marketplace publication, or deployment. |
| [`v0.2.0 final approval input manifest`](demo/v0.2.0-final-approval/input-manifest.json) | Source artifact paths, sizes, and hashes used by the final approval package. | It is a package manifest, not a second source of truth. |
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

## Reusable Action RC Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`action.yml`](../action.yml) | Root composite action metadata for running the offline SkillEval gate from an external repository. | It is release-candidate evidence, not a Marketplace Action release or v0.2.0 release. |
| [`examples/github-action/README.md`](../examples/github-action/README.md) | Public-safe fresh-clone fixture with two skills, two labeled tasks, and local gate commands. | It is an example fixture, not benchmark status or production readiness. |
| [`examples/github-action/.github/workflows/skilleval.yml`](../examples/github-action/.github/workflows/skilleval.yml) | Example workflow that calls the RC action by `@main` with bounded thresholds. | It does not post PR comments or annotations and does not approve merges automatically. |
| [`External Repo Action Smoke Pack`](demo/external-repo-action-smoke-pack/README.md) | Local external-consumer smoke evidence with consumer-shaped `skills/`, `benchmark/`, and `skilleval-output` paths. | It is not hosted GitHub Actions proof, release approval, Marketplace publication, or production readiness. |
| [`External consumer gate report`](demo/external-repo-action-smoke-pack/output/gate-report.md) | The committed local smoke gate decision: `ALLOW_MERGE`, `recall_at_5=1.0`, and `negative_hit_rate=0.0`. | It is not benchmark status or automatic merge approval. |
| [`External consumer CI summary`](demo/external-repo-action-smoke-pack/output/ci-summary.md) | Step-summary style Markdown from the local consumer smoke. | It does not post GitHub API PR comments or PR annotations. |
| [`Hosted Consumer Action Smoke`](demo/hosted-consumer-action-smoke/README.md) | One GitHub-hosted consumer smoke run from a dedicated consumer repository calling `Raidriar7170/hermes-skilleval@main`. | It is not Marketplace publication, release approval, product readiness, PR automation, SaaS, or runtime MCP routing. |
| [`Hosted run metadata`](demo/hosted-consumer-action-smoke/run-metadata.json) | Run URL, run id, workflow name, conclusion, action ref, commit, and artifact names. | It is a captured run record, not ongoing monitoring. |
| [`Hosted consumer gate report`](demo/hosted-consumer-action-smoke/output/gate-report.md) | Downloaded hosted artifact with `ALLOW_MERGE`, `recall_at_5=1.0`, and `negative_hit_rate=0.0`. | It is smoke evidence, not benchmark status or automatic merge approval. |
| [`Hosted consumer CI summary`](demo/hosted-consumer-action-smoke/output/ci-summary.md) | Downloaded step-summary style Markdown from the hosted consumer run. | It does not post GitHub API PR comments or PR annotations. |
| [`v0.2.0 release decision package`](demo/v0.2.0-release-decision/release-decision.md) | Aggregates local and hosted action smoke as RC support evidence for human release review. | Action smoke does not approve publication, production readiness, or automatic merge approval. |
| [`OpenSpec: reusable-github-action-rc`](../openspec/specs/reusable-github-action-rc/spec.md) | Synced capability contract for the reusable composite action RC. | It explicitly excludes release publication, GitHub API automation, SaaS, runtime MCP routing, and product-readiness claims. |
| [`Reusable Action RC Human Brief`](human-briefs/2026-06-04-reusable-github-action-rc.html) | Chinese phase summary with validation results, Reviewer fixes, and claim boundaries. | Human Briefs are review aids, not source artifacts or release approval. |
| [`External Repo Action Smoke Pack Human Brief`](human-briefs/2026-06-04-external-repo-action-smoke-pack.html) | Chinese phase summary for the local external-consumer smoke pack. | It is a companion narrative, not hosted workflow proof or release approval. |
| [`Hosted Consumer Action Smoke Human Brief`](human-briefs/2026-06-04-hosted-consumer-action-smoke.html) | Chinese phase summary for the hosted consumer smoke run. | It is a companion narrative, not release approval. |
| [`2026-06-04 v0.2.0 release decision`](human-briefs/2026-06-04-v0-2-0-release-decision.html) | Chinese companion brief for the `NEEDS_REVIEW` release decision package. | It is review packaging, not a release note or publication record. |
| [`Reusable Action RC Loop Brief`](human-briefs/2026-06-04-autonomous-loop-reusable-github-action-rc.html) | Autonomous-loop companion report for the RC phase. | It is a companion narrative, not a workflow log or second source of truth. |

## OpenSpec Specs

| Artifact | Helps verify | Limit |
|---|---|---|
| [`diagnostic-skill-library-onboarding`](../openspec/specs/diagnostic-skill-library-onboarding/spec.md) | Diagnostic onboarding contract and expected maintainer flow. | Specs define intended behavior; tests and artifacts verify current behavior. |
| [`diagnostic-ci-gate`](../openspec/specs/diagnostic-ci-gate/spec.md) | Artifact-based gate requirements for diagnostic outputs. | It is not release approval. |
| [`diagnostic-artifact-drift-check`](../openspec/specs/diagnostic-artifact-drift-check/spec.md) | Drift-check behavior for regenerated diagnostic artifacts. | It compares artifacts; it does not judge product readiness. |
| [`diagnostic-pr-review-surface`](../openspec/specs/diagnostic-pr-review-surface/spec.md) | Local PR review packet surface for diagnostics. | It is not GitHub API PR comments. |
| [`external-skill-library-validation-pack`](../openspec/specs/external-skill-library-validation-pack/spec.md) | External-style validation pack requirements. | It is not a SOTA claim. |
| [`pr-facing-ci-summary`](../openspec/specs/pr-facing-ci-summary/spec.md) | CI summary inputs, outputs, and bounded decision language. | It is not automatic merge approval. |
| [`reusable-github-action-rc`](../openspec/specs/reusable-github-action-rc/spec.md) | Reusable composite action RC requirements and public claim boundaries. | It is not a Marketplace Action release or v0.2.0 release. |
| [`v0-2-0-release-decision`](../openspec/specs/v0-2-0-release-decision/spec.md) | Release decision package requirements for `NEEDS_REVIEW`, `Published: false`, and source-evidence consistency. | It is not release approval, Marketplace publication, or a v0.2.0 release. |
| [`v0-2-0-release-notes-and-final-approval`](../openspec/specs/v0-2-0-release-notes-and-final-approval/spec.md) | Release notes and final approval review requirements for `NEEDS_REVIEW`, `Published: false`, and human-confirmation boundaries. | It is not release approval, Marketplace publication, or a v0.2.0 release. |

## Human Briefs

| Artifact | Helps verify | Limit |
|---|---|---|
| [`2026-06-03 docs evidence map`](human-briefs/2026-06-03-docs-evidence-map.html) | This phase's Chinese companion brief: status, changed files, validation plan, and boundaries. | Generated for review convenience; OpenSpec and source artifacts remain authoritative. |
| [`2026-06-03 PR-facing CI summary`](human-briefs/2026-06-03-pr-facing-ci-summary.html) | Summary of local/GitHub Actions CI summary implementation and validation. | It is not a workflow log. |
| [`2026-06-03 external validation pack`](human-briefs/2026-06-03-external-skill-library-validation-pack.html) | Summary of external-style validation pack outputs and validation. | It is not benchmark status. |
| [`2026-06-03 autonomous-loop external validation pack`](human-briefs/2026-06-03-autonomous-loop-external-skill-library-validation-pack.html) | Autonomous-loop brief for the same external validation phase. | It is a companion narrative, not a second source of truth. |
| [`2026-06-04 reusable action RC`](human-briefs/2026-06-04-reusable-github-action-rc.html) | Summary of the reusable action RC implementation, validation, and Reviewer fixes. | It is not a release note or Marketplace publication record. |
| [`2026-06-04 autonomous-loop reusable action RC`](human-briefs/2026-06-04-autonomous-loop-reusable-github-action-rc.html) | Loop-level report for the same reusable action RC phase. | It is a companion narrative, not a second source of truth. |
| [`2026-06-04 v0.2.0 release decision`](human-briefs/2026-06-04-v0-2-0-release-decision.html) | Summary of the `NEEDS_REVIEW` release decision package, validation, and boundaries. | It is review packaging, not release approval. |
| [`2026-06-04 v0.2.0 release notes and final approval`](human-briefs/2026-06-04-v0-2-0-release-notes-and-final-approval.html) | Summary of the release-notes draft, final approval checklist, validation plan, and human-confirmation boundaries. | It is review packaging, not release approval or publication. |
| [`2026-06-04 autonomous-loop v0.2.0 release decision`](human-briefs/2026-06-04-autonomous-loop-v0-2-0-release-decision.html) | Loop-level closeout report for the release decision phase, stop reason, and validation results. | It records guarded integration status, not release approval. |
| [`2026-06-04 public evidence surface refresh`](human-briefs/2026-06-04-public-evidence-surface-refresh.html) | Summary of the evidence-map, public count, and synced spec purpose refresh. | It is a companion narrative, not a second source of truth. |
| [`2026-06-04 autonomous-loop public evidence surface refresh`](human-briefs/2026-06-04-autonomous-loop-public-evidence-surface-refresh.html) | Loop-level closeout report for the public evidence surface refresh. | It records stop reason and auto-integration status, not release approval. |
