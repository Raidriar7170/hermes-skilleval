# Hermes SkillEval Failure Analysis

## Migration Failure Taxonomy

- `routing_miss`: gold migrated skill is absent from the selected top-k set.
- `tool_adaptation_failure`: tool or ecosystem-specific workflow is routed to the wrong adapter family.
- `instruction_drift`: process gates are weakened into generic coding guidance.
- `evidence_gap`: selected skill does not preserve the evidence expected for review.

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 12 | 1 | 0 | 2 | 3 |
| gated-hashing-selective | 12 | 12 | 12 | 0 | 12 |
| hybrid | 12 | 1 | 0 | 3 | 4 |

## Candidate vs Baseline

- Baseline: `embedding-hashing`
- Candidate: `gated-hashing-selective`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.750 | 0.000 | -0.750 |
| Recall@5 | 1.000 | 0.000 | -1.000 |
| MRR | 0.944 | 0.000 | -0.944 |
| NDCG@5 | 0.948 | 0.000 | -0.948 |
| Negative Hit Rate | 0.167 | 0.000 | +0.167 |
| Avg Latency ms | 2.819 | 3.295 | -0.476 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| browser-accessibility-audit | regressed | ok | missing-gold@5: accessibility-tree-inspection; top1-miss | accessibility-tree-inspection, form-interaction-flow, browser-smoke-testing, visual-regression-review, workspace-git-hygiene |  |
| browser-form-regression | trade-off | top1-miss | missing-gold@5: form-interaction-flow; top1-miss | browser-smoke-testing, visual-regression-review, form-interaction-flow, accessibility-tree-inspection, systematic-debugging |  |
| browser-local-dashboard | regressed | ok | missing-gold@5: browser-smoke-testing, visual-regression-review; top1-miss | browser-smoke-testing, visual-regression-review, mcp-tool-routing, accessibility-tree-inspection, apply-patch-discipline |  |
| claude-command-routing | regressed | ok | missing-gold@5: slash-command-workflow; top1-miss | slash-command-workflow, mcp-tool-routing, visual-regression-review, systematic-debugging, plan-mode |  |
| claude-mcp-selection | regressed | ok | missing-gold@5: mcp-tool-routing, task-tool-delegation; top1-miss | mcp-tool-routing, browser-smoke-testing, evidence-backed-final, task-tool-delegation, visual-regression-review |  |
| claude-plan-to-tasks | trade-off | negative-hit@5: verification-before-completion | missing-gold@5: plan-mode; top1-miss | plan-mode, visual-regression-review, evidence-backed-final, subagent-worker-protocol, verification-before-completion |  |
| codex-git-hygiene | regressed | ok | missing-gold@5: workspace-git-hygiene; top1-miss | workspace-git-hygiene, using-git-worktrees, subagent-worker-protocol, accessibility-tree-inspection, verification-before-completion |  |
| codex-minimal-diff | regressed | ok | missing-gold@5: apply-patch-discipline; top1-miss | apply-patch-discipline, test-driven-development, browser-smoke-testing, systematic-debugging, accessibility-tree-inspection |  |
| codex-worker-handoff | regressed | ok | missing-gold@5: evidence-backed-final, subagent-worker-protocol; top1-miss | subagent-worker-protocol, evidence-backed-final, systematic-debugging, slash-command-workflow, visual-regression-review |  |
| sp-debug-red-green | trade-off | negative-hit@5: visual-regression-review | missing-gold@5: systematic-debugging, test-driven-development; top1-miss | test-driven-development, systematic-debugging, visual-regression-review, browser-smoke-testing, slash-command-workflow |  |
| sp-isolated-worktree | regressed | ok | missing-gold@5: using-git-worktrees; top1-miss | using-git-worktrees, workspace-git-hygiene, accessibility-tree-inspection, browser-smoke-testing, task-tool-delegation |  |
| sp-verify-before-claim | regressed | ok | missing-gold@5: verification-before-completion; top1-miss | verification-before-completion, systematic-debugging, test-driven-development, slash-command-workflow, mcp-tool-routing |  |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| browser-form-regression | migration | embedding-hashing | top1-miss | form-interaction-flow | evidence-backed-final | browser-smoke-testing, visual-regression-review, form-interaction-flow, accessibility-tree-inspection, systematic-debugging |
| claude-plan-to-tasks | migration | embedding-hashing | negative-hit@5: verification-before-completion | plan-mode | verification-before-completion | plan-mode, visual-regression-review, evidence-backed-final, subagent-worker-protocol, verification-before-completion |
| sp-debug-red-green | migration | embedding-hashing | negative-hit@5: visual-regression-review | systematic-debugging, test-driven-development | visual-regression-review | test-driven-development, systematic-debugging, visual-regression-review, browser-smoke-testing, slash-command-workflow |
| browser-accessibility-audit | migration | gated-hashing-selective | missing-gold@5: accessibility-tree-inspection; top1-miss | accessibility-tree-inspection | using-git-worktrees |  |
| browser-form-regression | migration | gated-hashing-selective | missing-gold@5: form-interaction-flow; top1-miss | form-interaction-flow | evidence-backed-final |  |
| browser-local-dashboard | migration | gated-hashing-selective | missing-gold@5: browser-smoke-testing, visual-regression-review; top1-miss | browser-smoke-testing, visual-regression-review | systematic-debugging |  |
| claude-command-routing | migration | gated-hashing-selective | missing-gold@5: slash-command-workflow; top1-miss | slash-command-workflow | apply-patch-discipline |  |
| claude-mcp-selection | migration | gated-hashing-selective | missing-gold@5: mcp-tool-routing, task-tool-delegation; top1-miss | mcp-tool-routing, task-tool-delegation | accessibility-tree-inspection |  |
| claude-plan-to-tasks | migration | gated-hashing-selective | missing-gold@5: plan-mode; top1-miss | plan-mode | verification-before-completion |  |
| codex-git-hygiene | migration | gated-hashing-selective | missing-gold@5: workspace-git-hygiene; top1-miss | workspace-git-hygiene | browser-smoke-testing |  |
| codex-minimal-diff | migration | gated-hashing-selective | missing-gold@5: apply-patch-discipline; top1-miss | apply-patch-discipline | slash-command-workflow |  |
| codex-worker-handoff | migration | gated-hashing-selective | missing-gold@5: evidence-backed-final, subagent-worker-protocol; top1-miss | subagent-worker-protocol, evidence-backed-final | task-tool-delegation |  |
| sp-debug-red-green | migration | gated-hashing-selective | missing-gold@5: systematic-debugging, test-driven-development; top1-miss | systematic-debugging, test-driven-development | visual-regression-review |  |
| sp-isolated-worktree | migration | gated-hashing-selective | missing-gold@5: using-git-worktrees; top1-miss | using-git-worktrees | form-interaction-flow |  |
| sp-verify-before-claim | migration | gated-hashing-selective | missing-gold@5: verification-before-completion; top1-miss | verification-before-completion | plan-mode |  |
| browser-form-regression | migration | hybrid | top1-miss | form-interaction-flow | evidence-backed-final | browser-smoke-testing, visual-regression-review, form-interaction-flow, accessibility-tree-inspection, systematic-debugging |
| browser-local-dashboard | migration | hybrid | negative-hit@5: systematic-debugging | browser-smoke-testing, visual-regression-review | systematic-debugging | browser-smoke-testing, visual-regression-review, form-interaction-flow, test-driven-development, systematic-debugging |
| claude-command-routing | migration | hybrid | negative-hit@5: apply-patch-discipline | slash-command-workflow | apply-patch-discipline | slash-command-workflow, apply-patch-discipline, subagent-worker-protocol, workspace-git-hygiene, evidence-backed-final |
| sp-debug-red-green | migration | hybrid | negative-hit@5: visual-regression-review | systematic-debugging, test-driven-development | visual-regression-review | test-driven-development, systematic-debugging, visual-regression-review, browser-smoke-testing, mcp-tool-routing |
