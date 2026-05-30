# Hermes SkillEval Report

- Router: embedding
- Records: 16

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 1.000 |
| Recall@3 | 1.000 |
| Recall@5 | 1.000 |
| Precision@5 | 0.200 |
| MRR | 1.000 |
| NDCG@5 | 1.000 |
| Negative Hit Rate | 0.750 |
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.750 |
| Average Latency (ms) | 231.856 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| apply-patch-discipline | 10 |
| accessibility-tree-inspection | 7 |
| workspace-git-hygiene | 7 |
| visual-regression-review | 6 |
| evidence-backed-final | 6 |
| task-tool-delegation | 6 |
| systematic-debugging | 6 |
| browser-smoke-testing | 5 |
| plan-mode | 5 |
| test-driven-development | 5 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| blind-browser-accessibility-tree | 1.000 | 1.000 | 2810.830 |
| blind-browser-form-wizard | 1.000 | 1.000 | 93.727 |
| blind-browser-smoke-console | 1.000 | 1.000 | 69.345 |
| blind-browser-visual-diff | 1.000 | 1.000 | 71.553 |
| blind-claude-mcp-routing | 1.000 | 0.000 | 68.671 |
| blind-claude-plan-session | 1.000 | 1.000 | 72.896 |
| blind-claude-slash-command | 1.000 | 0.000 | 74.741 |
| blind-claude-task-delegation | 1.000 | 1.000 | 70.394 |
| blind-codex-apply-patch | 1.000 | 1.000 | 42.813 |
| blind-codex-evidence-final | 1.000 | 0.000 | 42.196 |
| blind-codex-git-hygiene | 1.000 | 1.000 | 43.339 |
| blind-codex-worker-handoff | 1.000 | 0.000 | 43.834 |
| blind-sp-debug-loop | 1.000 | 1.000 | 43.466 |
| blind-sp-red-green | 1.000 | 1.000 | 45.538 |
| blind-sp-verify-before-claim | 1.000 | 1.000 | 73.061 |
| blind-sp-worktree-isolation | 1.000 | 1.000 | 43.285 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| blind-browser-accessibility-tree | accessibility-tree-inspection, browser-smoke-testing, visual-regression-review, form-interaction-flow, plan-mode | accessibility-tree-inspection | 1.000 | 1.000 |
| blind-browser-form-wizard | form-interaction-flow, browser-smoke-testing, visual-regression-review, accessibility-tree-inspection, verification-before-completion | form-interaction-flow | 1.000 | 1.000 |
| blind-browser-smoke-console | browser-smoke-testing, visual-regression-review, accessibility-tree-inspection, form-interaction-flow, evidence-backed-final | browser-smoke-testing | 1.000 | 1.000 |
| blind-browser-visual-diff | visual-regression-review, browser-smoke-testing, accessibility-tree-inspection, form-interaction-flow, apply-patch-discipline | visual-regression-review | 1.000 | 1.000 |
| blind-claude-plan-session | plan-mode, task-tool-delegation, slash-command-workflow, apply-patch-discipline, test-driven-development | plan-mode | 1.000 | 1.000 |
| blind-claude-task-delegation | task-tool-delegation, apply-patch-discipline, plan-mode, accessibility-tree-inspection, workspace-git-hygiene | task-tool-delegation | 1.000 | 1.000 |
| blind-codex-apply-patch | apply-patch-discipline, workspace-git-hygiene, systematic-debugging, evidence-backed-final, using-git-worktrees | apply-patch-discipline | 1.000 | 1.000 |
| blind-codex-git-hygiene | workspace-git-hygiene, apply-patch-discipline, using-git-worktrees, evidence-backed-final, systematic-debugging | workspace-git-hygiene | 1.000 | 1.000 |
| blind-sp-debug-loop | systematic-debugging, test-driven-development, visual-regression-review, verification-before-completion, browser-smoke-testing | systematic-debugging | 1.000 | 1.000 |
| blind-sp-red-green | test-driven-development, systematic-debugging, verification-before-completion, visual-regression-review, accessibility-tree-inspection | test-driven-development | 1.000 | 1.000 |
| blind-sp-verify-before-claim | verification-before-completion, systematic-debugging, test-driven-development, evidence-backed-final, task-tool-delegation | verification-before-completion | 1.000 | 1.000 |
| blind-sp-worktree-isolation | using-git-worktrees, workspace-git-hygiene, subagent-worker-protocol, apply-patch-discipline, task-tool-delegation | using-git-worktrees | 1.000 | 1.000 |
