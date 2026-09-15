# Active Goal progress

Active authority: [FullStack Goal](../goals/Hermes_Repo_Aware_Cost_Aware_FullStack_Codex_Goal.md).
Baseline: PR47 open/draft, e7535896137b7e58fb55de52cc34e94b1afd5ff4. Stacked base: codex/hermes-two-repo-fixed-baseline.

M0 verified. M1 public task qualification in isolated data worktree. M2 context/model implementation active. M3–M8 pending, no training or utility claim yet.

Scope: read inherited implementation/configuration and public source/models; write new routing modules, bounded maintenance integration, tests, optional dependency config, new docs/configs/artifacts and this OpenSpec change. Frozen: all prior experiments and third-party model assets. Final scope is complete tracked delta from e753589.

Resource plan before new outcomes: local 48 GiB machine with observed MPS, existing Docker executor, existing authorized subscription. No new paid API/GPU; no reset-credit consumption. Local storage ceiling 30 GiB new assets, training 2 epochs initially, LoRA r=8, batch 1 with pair accumulation, max 1024 tokens; one seed 7170. Agent concurrency 1, per attempt 600 seconds, total study ceiling 120 Agent launches / 20 hours wall budget; repairs unlimited within resource budget. Monitor usage between phases; stop before exhausting available subscription. Initial PILOT target: 8 rank-train, 2 rank-dev, 4 gate-fit, 2 calibration, 4 final families (2 from one unseen repo), one repetition per action. Rough gate 18 + final 20 + development 12 = 50 launches, plus separate engineering smoke. Expand neither tasks nor repetitions after outcomes. Qualification may reduce counts before dependent outcomes, with reasons recorded. Dollar cost unknown. Quality noninferiority margin 0.05; this pilot will rarely establish it.

Next: qualify tasks; implement and test context, shared causal scoring, exact optimizer; train only admitted rank data, freeze R before gate feedback.
