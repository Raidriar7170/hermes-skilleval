# Repo-aware cost routing review

**Completed bounded pilot; insufficient learning signal.** Native stays default. No adaptive utility gain or generalization is claimed. [Results and all three tables](results.md) explain the unknown R outcome, observed H costs and conservative gate.

## Reproduce and inspect

- [Active Goal](../goals/Hermes_Repo_Aware_Cost_Aware_FullStack_Codex_Goal.md), [scope and resource ledger](progress.md), [method](method.md)
- [Model recipe, replay/assist entry points and records-only commands](usage.md)
- [One-page Chinese retrospective](retrospective.md)
- [Qualification](../../artifacts/repo-aware-routing/task-qualification/README.md), [candidate/split manifest](../../configs/repo-aware-routing/tasks/manifest.json)
- [Real training/reload](../../artifacts/repo-aware-routing/training/summary.json), [rank ablations](../../artifacts/repo-aware-routing/training/rank-dev.json)
- [Development controls](../../artifacts/repo-aware-routing/development/results.json), [equal-K execution](../../artifacts/repo-aware-routing/development-equal-k/results.json), [prelaunch failures](../../artifacts/repo-aware-routing/development-prelaunch/results.json)
- [Fit](../../artifacts/repo-aware-routing/gate-fit/results.json), [calibration](../../artifacts/repo-aware-routing/gate-calibration/results.json), [sealed gate](../../artifacts/repo-aware-routing/gate/freeze.json)
- [Final five-arm rows](../../artifacts/repo-aware-routing/final-test/results.json), [paired intervals and unseen repository](../../artifacts/repo-aware-routing/final-test/analysis.json)
- [Clean wheel](../../artifacts/repo-aware-routing/installation/clean-wheel.json), [real auto assist](../../artifacts/repo-aware-routing/assist/record.json), [assist patch](../../artifacts/repo-aware-routing/assist/candidate.patch)
- [Component profiling: R](../../artifacts/repo-aware-routing/performance/repo-aware.json), [auto](../../artifacts/repo-aware-routing/performance/auto.json). These are separate no-Agent cProfile diagnostics, not main comparison timings.

Public records checks run in ordinary lightweight pytest and the unchanged GitHub workflow. Final HEAD/CI and complete tracked-diff closure digest are attached to [Draft PR48](https://github.com/Raidriar7170/hermes-skilleval/pull/48), stacked on `codex/hermes-two-repo-fixed-baseline` at `e7535896137b7e58fb55de52cc34e94b1afd5ff4`. PR47 is preserved. No merge or release is part of this closeout.
