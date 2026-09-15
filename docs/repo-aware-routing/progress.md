# Active Goal progress

Active authority: [FullStack Goal](../goals/Hermes_Repo_Aware_Cost_Aware_FullStack_Codex_Goal.md).
Baseline: PR47 open/draft, e7535896137b7e58fb55de52cc34e94b1afd5ff4. Stacked base: codex/hermes-two-repo-fixed-baseline.

M0–M8 bounded pilot work is complete; final published HEAD/CI and closure digest are recorded on Draft PR48. Real rank training, gate fit/calibration and all 20 final cells ran. See [results](results.md): DATA_SIGNAL_INSUFFICIENT / PILOT / INCONCLUSIVE / KEEP_NATIVE.
Scope: read inherited implementation/configuration and public source/models; write new routing modules, bounded maintenance integration, tests, optional dependency config, new docs/configs/artifacts and this OpenSpec change. Frozen: all prior experiments and third-party model assets. Final scope is complete tracked delta from e753589.

Resource plan before new outcomes: local 48 GiB machine with observed MPS, existing Docker executor, existing authorized subscription. No new paid API/GPU; no reset-credit consumption. Local storage ceiling 30 GiB new assets, training 2 epochs initially, LoRA r=8, batch 1 with pair accumulation, max 1024 tokens; one seed 7170. Agent concurrency 1, per attempt 600 seconds, total study ceiling 120 Agent launches / 20 hours wall budget; repairs unlimited within resource budget. Monitor usage between phases; stop before exhausting available subscription. Initial PILOT target: 8 rank-train, 2 rank-dev, 4 gate-fit, 2 calibration, 4 final families (2 from one unseen repo), one repetition per action. Rough gate 18 + final 20 + development 12 = 50 launches, plus separate engineering smoke. Expand neither tasks nor repetitions after outcomes. Qualification may reduce counts before dependent outcomes, with reasons recorded. Dollar cost unknown. Quality noninferiority margin 0.05; this pilot will rarely establish it.

## Execution closeout

All 48 predeclared research Agent executions are retained: development 8, equal-K 2, fit 12, calibration 6 and final 20. Four prelaunch failures remain separately unknown. R was frozen before gate data and the gate was byte-sealed before final launches. No final outcome triggered policy tuning or a repeated run.

Final R identity: `b840e2b1bbf4a2c51cd87deb7a207621609ce92ce8ff3e9e2188816bcb9c4a94`. Earlier development freezes were superseded before gate collection; no retraining occurred. Zero within-family action contrast forces the actually fitted gate to N.

Engineering repairs retained in history: lightweight venv pip restored for fresh-install test; narrow JUnit/patch whitespace attributes preserve original bytes; evidence pytest import fixed. GitHub rejected a workflow edit for missing OAuth workflow scope; that edit was removed before publishing, and the unchanged workflow runs the records check through ordinary pytest. No permission escalation or force push.

Final closure compares the complete tracked delta with e753589, refreshes frozen assets/evidence, checks actual remote HEAD and same-HEAD CI, and leaves PR48 draft. No merge or release.
