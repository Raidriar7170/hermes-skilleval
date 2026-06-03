# Hermes SkillEval Failure Gallery

This page is a navigation layer over committed failure evidence. The
canonical evidence remains in the linked artifacts; this gallery only groups
examples by the reviewer question they answer and records what each example
should not be used to claim.

Boundary phrases: not a Marketplace Action; not GitHub API PR comments; not PR annotations; not SaaS; not a runtime MCP router; not a SOTA claim; not benchmark status; not production readiness; not release approval; not automatic merge approval.

## Release-Gate Regression Examples

| Example | Evidence | Reviewer reading | Limit |
|---|---|---|---|
| Blind validation blocked promotion | [`comparison.md`](demo/phase16-blind-validation/comparison.md), [`regression-summary.json`](demo/phase16-blind-validation/regression-summary.json), [`route-diffs.jsonl`](demo/phase16-blind-validation/route-diffs.jsonl) | Phase 16 records `REVIEW_REQUIRED` after unchanged Recall@5 but worse ranking and negative-skill behavior. | This is a local release-gate input, not a public leaderboard. |
| Negative skill newly selected | [`route-diffs.jsonl`](demo/phase16-blind-validation/route-diffs.jsonl), [`release-decision.md`](demo/phase17-calibrated-release-selector/release-decision.md) | `blind-claude-mcp-routing` includes `new_negative_skill_selected`, so Phase 17 keeps the safer default. | It does not prove the candidate is unusable everywhere. |
| Ranking quality regressed | [`comparison.md`](demo/phase16-blind-validation/comparison.md), [`task-decisions.jsonl`](demo/phase17-calibrated-release-selector/task-decisions.jsonl) | `blind-codex-worker-handoff` carries `mrr_decreased` and `ndcg_at_5_decreased`. | It is one release-gate case, not a universal model verdict. |
| Conservative release decision reproduced | [`release-decision.md`](demo/phase17-calibrated-release-selector/release-decision.md), [`release-manifest.md`](demo/phase18-ci-release-reproducibility/release-manifest.md) | Phase 17 records `KEEP_BASELINE`; Phase 18 reproduces that decision and artifact hashes. | Phase 18 proves local gate reproducibility, not production readiness. |

## Diagnostic Routing-Clarity Examples

| Example | Evidence | Reviewer reading | Limit |
|---|---|---|---|
| Missing negative boundaries | [`lint.json`](demo/diagnostic-onboarding/lint.json), [`ci-gate-report.md`](demo/diagnostic-onboarding/ci-gate-report.md) | The diagnostic pack includes `missing_negative_boundaries` findings that a Skill Library Maintainer should review. | Lint findings are review signals, not proof a skill is wrong. |
| review-worthy conflict risk clusters | [`inspect.json`](demo/diagnostic-onboarding/inspect.json), [`dashboard.html`](demo/diagnostic-onboarding/dashboard.html) | Conflict clusters identify overlapping routing cues that deserve human review. | Conflict clusters are not duplicate-detection verdicts. |
| Route risk flags for example queries | [`route-browser-smoke.json`](demo/diagnostic-onboarding/route-browser-smoke.json), [`route-debug-red-green.json`](demo/diagnostic-onboarding/route-debug-red-green.json) | Route candidates can carry risk flags when near-miss skills appear plausible. | Route risk flags do not automatically block a merge or release. |
| Local PR review packet | [`pr-review-packet.md`](demo/diagnostic-onboarding/pr-review-packet.md) | The packet summarizes review-worthy lint, conflict, and route-risk counts for discussion. | It is local reviewer evidence, not GitHub API PR comments. |

## External-Style Validation Examples

| Example | Evidence | Reviewer reading | Limit |
|---|---|---|---|
| External pack overview | [`README.md`](demo/external-skill-library-validation/README.md) | The pack exercises Markdown `SKILL.md` folders and MCP-style tool schema input shapes. | It is a bounded local pack, not benchmark status. |
| Markdown skill source track | [`ci-gate-report.md`](demo/external-skill-library-validation/markdown-skills/ci-gate-report.md), [`pr-review-packet.md`](demo/external-skill-library-validation/markdown-skills/pr-review-packet.md) | The Markdown track regenerates scan, lint, inspect, route, dashboard, and review artifacts. | It does not claim coverage of every real skill library. |
| MCP-style tool schema track | [`ci-gate-report.md`](demo/external-skill-library-validation/mcp-tool-schema/ci-gate-report.md), [`pr-review-packet.md`](demo/external-skill-library-validation/mcp-tool-schema/pr-review-packet.md) | The schema track validates another public-safe source shape. | It is not a runtime MCP router. |
| Historical failure-mode reports | [`phase13 regression report`](demo/phase13-patch-simulation/regression-report.md), [`phase9 failure analysis`](demo/phase9-real-skill-library-migration/failure-analysis.md), [`phase8 dashboard`](demo/phase8-static-dashboard/dashboard.html) | Older artifacts show how failure analysis and regression guards evolved before the current release gate. | Historical reports are context; Phase 16-18 remain the current release reading. |

## CI Boundary Examples

| Example | Evidence | Reviewer reading | Limit |
|---|---|---|---|
| Validate workflow summary path | [`.github/workflows/validate.yml`](../.github/workflows/validate.yml), [`pr-facing-ci-summary spec`](../openspec/specs/pr-facing-ci-summary/spec.md) | CI can collect check outcomes and render an `ALLOW_MERGE` or `BLOCK_MERGE` summary. | The summary is not automatic merge approval. |
| Overclaim boundary scan | [`docs/evidence-map.md`](evidence-map.md), [`docs/release-handoff.md`](release-handoff.md) | Public docs repeat boundaries so reviewer-facing artifacts do not drift into product or benchmark claims. | Boundary scans do not replace human review. |
| Drift-check evidence | [`diagnostic artifact drift spec`](../openspec/specs/diagnostic-artifact-drift-check/spec.md), [`external validation pack spec`](../openspec/specs/external-skill-library-validation-pack/spec.md) | Regenerated artifacts can be compared against committed evidence to catch semantic drift. | Drift checks compare local artifacts; they do not approve a release. |

## How To Use This Gallery

Use this gallery when a reviewer asks, "What failure did the project actually
catch?" Start with the Release-Gate Regression Examples, then use the
diagnostic and external-style examples to explain how maintainers inspect risky
skill libraries before writing labeled benchmarks.

Do not use this page as a second source of truth. Follow each link to the
committed artifact before making any claim about a metric, route decision,
diagnostic finding, or CI outcome.
