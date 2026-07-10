# Hermes SkillEval Evidence Map

This page is a navigation layer, not a second source of truth. The canonical
evidence remains in the linked repository artifacts; this map groups the current
proof chain by reviewer task. It distinguishes historical pre-publish review artifacts
from post-release artifacts as the current publication record.

Boundary: This is a reusable repository Action, not a Marketplace-published Action, not a GitHub API PR comment bot, not a SaaS dashboard, and not a runtime MCP router. It is not GitHub API PR comments, not PR annotations, not a public leaderboard, not a SOTA claim, not production readiness, not release approval, and not automatic merge approval.

## Project Positioning

| Artifact | Helps verify | Limit |
|---|---|---|
| [`README.md`](../README.md) | Developer-tool front door, current `v0.3.0` release-prep onboarding, Action usage, dashboard preview, and compact evidence links. | The README summarizes; source artifacts remain authoritative. |
| [`CONTEXT.md`](../CONTEXT.md) | Durable domain language for routing reliability, Skill Library Maintainers, diagnostics, and release gates. | It defines vocabulary, not a new release result. |
| [`docs/release-handoff.md`](release-handoff.md) | Reviewer-ready handoff for Phase 16-18, historical release review, and post-release evidence. | It is not release approval or product readiness. |
| [`docs/failure-gallery.md`](failure-gallery.md) | Gallery of blocked regressions and diagnostic risks. | It is an example index, not canonical evidence or a new verdict. |
| [`docs/interview-project-overview.html`](interview-project-overview.html) | Human-readable project explanation for interviews and portfolio review. | It is explanatory packaging, not benchmark leadership evidence. |

## Release-Gate Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`docs/demo/phase16-blind-validation/comparison.md`](demo/phase16-blind-validation/comparison.md) | Blind validation found unchanged Recall@5 but worse ranking and negative-skill behavior for the fine-tuned candidate. | It is a project release-gate input, not a public leaderboard. |
| [`docs/demo/phase17-calibrated-release-selector/release-decision.md`](demo/phase17-calibrated-release-selector/release-decision.md) | The selector records `KEEP_BASELINE`; `baseline-minilm` remains the default. | It does not approve a product launch or automatic merge. |
| [`docs/demo/phase18-ci-release-reproducibility/release-manifest.md`](demo/phase18-ci-release-reproducibility/release-manifest.md) | Phase 18 reproduces the release decision and records manifest-level evidence. | It proves reproducibility of the local release gate, not production readiness. |
| [`v0.2.0 release decision`](demo/v0.2.0-release-decision/release-decision.md) | Historical pre-publish review evidence: `NEEDS_REVIEW`, `Published: false`, `KEEP_BASELINE`, and source links. | It is not automatic publication, release approval, or product readiness. |
| [`v0.2.0 release decision JSON`](demo/v0.2.0-release-decision/release-decision.json) | Machine-readable historical decision fields for release review and router selection. | It does not create a tag, GitHub Release, Marketplace publication, or deployment. |
| [`v0.2.0 input manifest`](demo/v0.2.0-release-decision/input-manifest.json) | Source artifact paths, sizes, and hashes used by the release decision package. | It is a package manifest, not a second source of truth. |
| [`v0.2.0 release notes`](release-notes/v0.2.0.md) | Published release notes for implemented capabilities, committed evidence, and boundaries. | It is not Marketplace publication, PR comment automation, SaaS, or a runtime MCP router. |
| [`v0.2.0 final approval checklist`](demo/v0.2.0-final-approval/final-approval.md) | Historical pre-publish GO Conditions, NO-GO Until, and Requires Human Confirmation checklist. | It is review packaging, not release approval or automatic publication. |
| [`v0.2.0 final approval JSON`](demo/v0.2.0-final-approval/final-approval.json) | Machine-readable historical checklist fields: Overall decision: `NEEDS_REVIEW`, Published: `false`, and source checks. | It does not create a tag, GitHub Release, Marketplace publication, or deployment. |
| [`v0.2.0 final approval input manifest`](demo/v0.2.0-final-approval/input-manifest.json) | Source artifact paths, sizes, and hashes used by the final approval package. | It is a package manifest, not a second source of truth. |
| [`v0.2.0 post-release evidence`](demo/v0.2.0-post-release/post-release.md) | Current publication record: actual GitHub tag and GitHub Release facts after explicit human GO. | It is not Marketplace publication, PR comment automation, SaaS, or a runtime MCP router. |
| [`v0.2.0 post-release JSON`](demo/v0.2.0-post-release/post-release.json) | Machine-readable current publication facts, release URL, tag, and verification commands. | It is not a public release action by itself. |
| [`docs/phase18.md`](phase18.md) | Narrative summary for the CI-backed reproducibility pack. | It should be read with the manifest and release-check summary. |

## v0.3 Stage 2 Evidence Chain

| Artifact | Helps verify | Limit |
|---|---|---|
| [`v0.3.0 release-prep notes`](release-notes/v0.3.0.md) | Release framing for the Stage 2 real Codex pilot evidence-chain release. | This prepares release metadata only; it does not create a tag or GitHub Release. |
| [`PR #30 closeout artifact`](../artifacts/v0.3/skillsbench-pilot/v0.3-stage2-real-codex-evidence-gate-closeout-20260708T080414Z/stage2-real-codex-evidence-gate-closeout.json) | Final closeout posture: `REVIEW_REQUIRED / KEEP_BASELINE`, `blocking_failure_count=0`, and `live_agent.overlap_status` as the remaining caveat. | `REVIEW_REQUIRED` is not PASS and `KEEP_BASELINE` is not a performance conclusion. |
| [`PR #25 execution artifact`](../artifacts/v0.3/skillsbench-pilot/v0.3-stage2-real-codex-12-run-execution-20260707T072652Z/stage2-real-codex-12-run-execution.json) | Real Codex 12-run execution evidence over the frozen 4x3x1 plan. | Raw verifier facts only; no performance claim or router promotion. |
| [`PR #25 matrix report`](../artifacts/v0.3/skillsbench-pilot/v0.3-stage2-real-codex-12-run-execution-20260707T072652Z/stage2-real-codex-12-run-matrix-report.json) | 12 runs completed with verifier output; raw verifier facts are 6 passed and 6 failed. | Process exit code is not task success; deterministic verifier output is the only task success source. |
| [`PR #22 frozen pilot plan`](../artifacts/v0.3/skillsbench-pilot/v0.3-stage2-pilot-freeze-20260707T025315Z/stage2-pilot-plan.frozen.json) | Frozen 4 tasks x 3 conditions x 1 trial plan and fixed run order. | It is a plan artifact, not execution evidence. |
| [`PR #27 adapter artifact`](../artifacts/v0.3/skillsbench-pilot/v0.3-stage2-real-codex-evidence-gate-adapter-20260708T032000Z/stage2-real-codex-evidence-gate-adapter.json) | Adapter contract for mapping Stage 2 real Codex artifacts into the evidence gate. | Adapter support is not a router promotion. |
| [`PR #29 data-root provenance repair`](../artifacts/v0.3/skillsbench-pilot/v0.3-external-matrix-data-root-provenance-repair-20260708T065712Z/external-matrix-data-root-provenance-repair.json) | External matrix data-root provenance/materialization repair with `blocking_failure_count=0` after repair. | The 402MB external data root is not committed. |
| [`v0.3.0 release readiness artifact`](../artifacts/v0.3/release/v0.3.0-release-readiness.json) | Machine-readable release-prep summary of source PRs, key artifacts, non-claims, and validation commands. | It is not a tag, GitHub Release, benchmark PASS, or performance claim. |

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

## Reusable GitHub Action Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`action.yml`](../action.yml) | Root composite action metadata for running the offline SkillEval gate from an external repository. | It is a reusable repository Action, not Marketplace publication or PR automation. |
| [`examples/github-action/README.md`](../examples/github-action/README.md) | Public-safe fresh-clone fixture with two skills, two labeled tasks, and local gate commands. | It is an example fixture, not benchmark status or production readiness. |
| [`examples/github-action/.github/workflows/skilleval.yml`](../examples/github-action/.github/workflows/skilleval.yml) | Current copy/paste workflow using `Raidriar7170/hermes-skilleval@v0.3.0` with bounded thresholds. | It does not post PR comments or annotations and does not approve merges automatically. |
| [`docs/demo-repo-plan.md`](demo-repo-plan.md) | Future external demo repository plan for `Raidriar7170/hermes-skilleval-demo`. | It is a plan only; it does not claim the repository exists. |
| [`OpenSpec: reusable-github-action-rc`](../openspec/specs/reusable-github-action-rc/spec.md) | Archived/root capability contract including the post-release cleanup delta. | The capability name is historical; current onboarding uses the published Action ref. |

## Local External Consumer Smoke Pack

| Artifact | Helps verify | Limit |
|---|---|---|
| [`External Repo Action Smoke Pack`](demo/external-repo-action-smoke-pack/README.md) | Historical local external-consumer smoke evidence with consumer-shaped `skills/`, `benchmark/`, and `skilleval-output` paths. | Captured refs are historical smoke evidence, not the current recommended released Action ref. |
| [`External consumer gate report`](demo/external-repo-action-smoke-pack/output/gate-report.md) | The committed local smoke gate decision: `ALLOW_MERGE`, `recall_at_5=1.0`, and `negative_hit_rate=0.0`. | It is not benchmark status or automatic merge approval. |
| [`External consumer CI summary`](demo/external-repo-action-smoke-pack/output/ci-summary.md) | Step-summary style Markdown from the local consumer smoke. | It does not post GitHub API PR comments or PR annotations. |

## Hosted Consumer Action Smoke Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`Hosted Consumer Action Smoke`](demo/hosted-consumer-action-smoke/README.md) | Historical hosted smoke run from a dedicated consumer repository. | Captured action refs are historical; current onboarding recommends `Raidriar7170/hermes-skilleval@v0.3.0` after the v0.3.0 tag is published. |
| [`Hosted run metadata`](demo/hosted-consumer-action-smoke/run-metadata.json) | Run URL, run id, workflow name, conclusion, action ref, commit, and artifact names. | It is a captured run record, not ongoing monitoring. |
| [`Hosted consumer gate report`](demo/hosted-consumer-action-smoke/output/gate-report.md) | Downloaded hosted artifact with `ALLOW_MERGE`, `recall_at_5=1.0`, and `negative_hit_rate=0.0`. | It is smoke evidence, not benchmark status or automatic merge approval. |
| [`Hosted consumer CI summary`](demo/hosted-consumer-action-smoke/output/ci-summary.md) | Downloaded step-summary style Markdown from the hosted consumer run. | It does not post GitHub API PR comments or PR annotations. |

## Release Evidence

| Artifact | Helps verify | Limit |
|---|---|---|
| [`v0.2.0 release notes`](release-notes/v0.2.0.md) | Published release notes for implemented capabilities and evidence links. | It does not imply Marketplace publication or production readiness. |
| [`v0.2.0 post-release evidence`](demo/v0.2.0-post-release/post-release.md) | Current publication record after human GO: tag and GitHub Release exist, Marketplace remains false. | It is not PR automation, SaaS, or runtime routing. |
| [`v0.2.0 post-release JSON`](demo/v0.2.0-post-release/post-release.json) | Machine-readable publication facts and verification commands. | It is evidence only, not a release command. |
| [`v0.2.1 patch release notes`](release-notes/v0.2.1.md) | Patch release notes for packaging the post-release onboarding cleanup. | It is not a feature expansion, Marketplace publication, SaaS, or runtime routing. |
| [`v0.2.1 post-release evidence`](demo/v0.2.1-post-release/post-release.md) | Current patch publication record: tag and GitHub Release exist, Marketplace remains false. | It is not PR automation, SaaS, or runtime routing. |
| [`v0.2.1 post-release JSON`](demo/v0.2.1-post-release/post-release.json) | Machine-readable patch publication facts and verification commands. | It is evidence only, not a release command. |
| [`v0.3.0 release-prep notes`](release-notes/v0.3.0.md) | Stage 2 real Codex pilot evidence-chain release notes and non-claims. | It does not create the v0.3.0 tag or GitHub Release. |
| [`v0.3.0 release readiness artifact`](../artifacts/v0.3/release/v0.3.0-release-readiness.json) | Machine-readable readiness state for the v0.3.0 release-prep PR. | Tag and GitHub Release require separate explicit human approval after merge. |

## OpenSpec Specs

These root specs are archived/current OpenSpec contracts from completed changes,
including `post-release-onboarding-cleanup`.

| Artifact | Helps verify | Limit |
|---|---|---|
| [`diagnostic-skill-library-onboarding`](../openspec/specs/diagnostic-skill-library-onboarding/spec.md) | Diagnostic onboarding contract and expected maintainer flow. | Specs define intended behavior; tests and artifacts verify current behavior. |
| [`diagnostic-ci-gate`](../openspec/specs/diagnostic-ci-gate/spec.md) | Artifact-based gate requirements for diagnostic outputs. | It is not release approval. |
| [`diagnostic-artifact-drift-check`](../openspec/specs/diagnostic-artifact-drift-check/spec.md) | Drift-check behavior for regenerated diagnostic artifacts. | It compares artifacts; it does not judge product readiness. |
| [`diagnostic-pr-review-surface`](../openspec/specs/diagnostic-pr-review-surface/spec.md) | Local PR review packet surface for diagnostics. | It is not GitHub API PR comments. |
| [`external-skill-library-validation-pack`](../openspec/specs/external-skill-library-validation-pack/spec.md) | External-style validation pack requirements. | It is not a SOTA claim. |
| [`pr-facing-ci-summary`](../openspec/specs/pr-facing-ci-summary/spec.md) | CI summary inputs, outputs, and bounded decision language. | It is not automatic merge approval. |
| [`reusable-github-action-rc`](../openspec/specs/reusable-github-action-rc/spec.md) | Reusable composite action requirements and public claim boundaries. | It excludes Marketplace publication, GitHub API automation, SaaS, runtime MCP routing, and product-readiness claims. |
| [`v0-2-0-release-decision`](../openspec/specs/v0-2-0-release-decision/spec.md) | Historical release decision package requirements for `NEEDS_REVIEW`, `Published: false`, and source-evidence consistency. | It is not release approval or Marketplace publication. |
| [`v0-2-0-release-notes-and-final-approval`](../openspec/specs/v0-2-0-release-notes-and-final-approval/spec.md) | Release notes and historical final approval review requirements. | It does not authorize future patch publication without human confirmation. |

## Human Briefs

| Artifact | Helps verify | Limit |
|---|---|---|
| [`2026-06-03 docs evidence map`](human-briefs/2026-06-03-docs-evidence-map.html) | This phase's Chinese companion brief: status, changed files, validation plan, and boundaries. | Generated for review convenience; OpenSpec and source artifacts remain authoritative. |
| [`2026-06-03 PR-facing CI summary`](human-briefs/2026-06-03-pr-facing-ci-summary.html) | Summary of local/GitHub Actions CI summary implementation and validation. | It is not a workflow log. |
| [`2026-06-03 external validation pack`](human-briefs/2026-06-03-external-skill-library-validation-pack.html) | Summary of external-style validation pack outputs and validation. | It is not benchmark status. |
| [`2026-06-03 autonomous-loop external validation pack`](human-briefs/2026-06-03-autonomous-loop-external-skill-library-validation-pack.html) | Autonomous-loop brief for the same external validation phase. | It is a companion narrative, not a second source of truth. |
| [`2026-06-04 reusable action`](human-briefs/2026-06-04-reusable-github-action-rc.html) | Historical summary of the reusable action implementation, validation, and Reviewer fixes. | It is not a release note or Marketplace publication record. |
| [`2026-06-04 autonomous-loop reusable action`](human-briefs/2026-06-04-autonomous-loop-reusable-github-action-rc.html) | Loop-level report for the same reusable action phase. | It is a companion narrative, not a second source of truth. |
| [`2026-06-04 external action smoke`](human-briefs/2026-06-04-external-repo-action-smoke-pack.html) | Chinese phase summary for the local external-consumer smoke pack. | It is a companion narrative, not hosted workflow proof or release approval. |
| [`2026-06-04 hosted action smoke`](human-briefs/2026-06-04-hosted-consumer-action-smoke.html) | Chinese phase summary for the hosted consumer smoke run. | It is a companion narrative, not release approval. |
| [`2026-06-04 v0.2.0 release decision`](human-briefs/2026-06-04-v0-2-0-release-decision.html) | Summary of the `NEEDS_REVIEW` release decision package, validation, and boundaries. | It is review packaging, not release approval. |
| [`2026-06-04 v0.2.0 release notes and final approval`](human-briefs/2026-06-04-v0-2-0-release-notes-and-final-approval.html) | Summary of the release-notes preparation phase, final approval checklist, validation plan, and human-confirmation boundaries. | It is historical review packaging, not Marketplace publication. |
| [`2026-06-05 post-release onboarding cleanup`](human-briefs/2026-06-05-post-release-onboarding-cleanup.html) | Chinese companion brief for the v0.2.0 post-release README, version, Action, and onboarding cleanup. | It is not a new feature phase or release publication. |
| [`2026-06-05 v0.2.1 patch release`](human-briefs/2026-06-05-v0-2-1-patch-release.html) | Summary of the patch release publication facts, validation commands, evidence links, and boundaries. | It is a companion narrative, not a GitHub Release record or release command. |
| [`2026-06-04 autonomous-loop v0.2.0 release decision`](human-briefs/2026-06-04-autonomous-loop-v0-2-0-release-decision.html) | Loop-level closeout report for the release decision phase, stop reason, and validation results. | It records guarded integration status, not release approval. |
| [`2026-06-04 autonomous-loop reusable action`](human-briefs/2026-06-04-autonomous-loop-reusable-github-action-rc.html) | Autonomous-loop companion report for the reusable action phase. | It is a companion narrative, not a workflow log or second source of truth. |
| [`2026-06-04 public evidence surface refresh`](human-briefs/2026-06-04-public-evidence-surface-refresh.html) | Summary of the evidence-map, public count, and synced spec purpose refresh. | It is a companion narrative, not a second source of truth. |
| [`2026-06-04 autonomous-loop public evidence surface refresh`](human-briefs/2026-06-04-autonomous-loop-public-evidence-surface-refresh.html) | Loop-level closeout report for the public evidence surface refresh. | It records stop reason and auto-integration status, not release approval. |
