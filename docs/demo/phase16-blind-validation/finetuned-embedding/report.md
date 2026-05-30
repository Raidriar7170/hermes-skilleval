# Hermes SkillEval Report

- Router: embedding
- Records: 16

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.938 |
| Recall@3 | 1.000 |
| Recall@5 | 1.000 |
| Precision@5 | 0.200 |
| MRR | 0.969 |
| NDCG@5 | 0.977 |
| Negative Hit Rate | 0.812 |
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.812 |
| Average Latency (ms) | 47.781 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| apply-patch-discipline | 10 |
| accessibility-tree-inspection | 8 |
| evidence-backed-final | 8 |
| systematic-debugging | 7 |
| visual-regression-review | 6 |
| task-tool-delegation | 5 |
| workspace-git-hygiene | 5 |
| browser-smoke-testing | 4 |
| form-interaction-flow | 4 |
| verification-before-completion | 4 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| blind-browser-accessibility-tree | 1.000 | 1.000 | 453.773 |
| blind-browser-form-wizard | 1.000 | 1.000 | 21.531 |
| blind-browser-smoke-console | 1.000 | 1.000 | 21.369 |
| blind-browser-visual-diff | 1.000 | 1.000 | 20.352 |
| blind-claude-mcp-routing | 1.000 | 1.000 | 20.444 |
| blind-claude-plan-session | 1.000 | 1.000 | 20.604 |
| blind-claude-slash-command | 1.000 | 0.000 | 21.055 |
| blind-claude-task-delegation | 1.000 | 1.000 | 20.250 |
| blind-codex-apply-patch | 1.000 | 1.000 | 20.042 |
| blind-codex-evidence-final | 1.000 | 0.000 | 20.364 |
| blind-codex-git-hygiene | 1.000 | 1.000 | 22.872 |
| blind-codex-worker-handoff | 1.000 | 0.000 | 20.286 |
| blind-sp-debug-loop | 1.000 | 1.000 | 20.375 |
| blind-sp-red-green | 1.000 | 1.000 | 20.063 |
| blind-sp-verify-before-claim | 1.000 | 1.000 | 20.508 |
| blind-sp-worktree-isolation | 1.000 | 1.000 | 20.609 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| blind-browser-accessibility-tree | accessibility-tree-inspection, browser-smoke-testing, visual-regression-review, form-interaction-flow, evidence-backed-final | accessibility-tree-inspection | 1.000 | 1.000 |
| blind-browser-form-wizard | form-interaction-flow, browser-smoke-testing, accessibility-tree-inspection, visual-regression-review, verification-before-completion | form-interaction-flow | 1.000 | 1.000 |
| blind-browser-smoke-console | browser-smoke-testing, visual-regression-review, accessibility-tree-inspection, form-interaction-flow, evidence-backed-final | browser-smoke-testing | 1.000 | 1.000 |
| blind-browser-visual-diff | visual-regression-review, browser-smoke-testing, accessibility-tree-inspection, form-interaction-flow, apply-patch-discipline | visual-regression-review | 1.000 | 1.000 |
| blind-claude-mcp-routing | mcp-tool-routing, task-tool-delegation, plan-mode, slash-command-workflow, apply-patch-discipline | mcp-tool-routing | 1.000 | 1.000 |
| blind-claude-plan-session | plan-mode, task-tool-delegation, slash-command-workflow, apply-patch-discipline, test-driven-development | plan-mode | 1.000 | 1.000 |
| blind-claude-task-delegation | task-tool-delegation, plan-mode, apply-patch-discipline, accessibility-tree-inspection, slash-command-workflow | task-tool-delegation | 1.000 | 1.000 |
| blind-codex-apply-patch | apply-patch-discipline, systematic-debugging, workspace-git-hygiene, evidence-backed-final, using-git-worktrees | apply-patch-discipline | 1.000 | 1.000 |
| blind-codex-git-hygiene | workspace-git-hygiene, apply-patch-discipline, using-git-worktrees, evidence-backed-final, systematic-debugging | workspace-git-hygiene | 1.000 | 1.000 |
| blind-sp-debug-loop | systematic-debugging, test-driven-development, verification-before-completion, accessibility-tree-inspection, visual-regression-review | systematic-debugging | 1.000 | 1.000 |
| blind-sp-red-green | test-driven-development, systematic-debugging, verification-before-completion, accessibility-tree-inspection, visual-regression-review | test-driven-development | 1.000 | 1.000 |
| blind-sp-verify-before-claim | verification-before-completion, systematic-debugging, test-driven-development, task-tool-delegation, evidence-backed-final | verification-before-completion | 1.000 | 1.000 |
| blind-sp-worktree-isolation | using-git-worktrees, workspace-git-hygiene, subagent-worker-protocol, evidence-backed-final, apply-patch-discipline | using-git-worktrees | 1.000 | 1.000 |
