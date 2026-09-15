# Active Goal progress

Active authority: [FullStack Goal](../goals/Hermes_Repo_Aware_Cost_Aware_FullStack_Codex_Goal.md).
Baseline: PR47 open/draft, e7535896137b7e58fb55de52cc34e94b1afd5ff4. Stacked base: codex/hermes-two-repo-fixed-baseline.

M0–M3 implemented and locally verified. M4–M8 execution and closure are in progress. Real rank training and independent checkpoint reload are complete; no algorithm utility claim.

Scope: read inherited implementation/configuration and public source/models; write new routing modules, bounded maintenance integration, tests, optional dependency config, new docs/configs/artifacts and this OpenSpec change. Frozen: all prior experiments and third-party model assets. Final scope is complete tracked delta from e753589.

Resource plan before new outcomes: local 48 GiB machine with observed MPS, existing Docker executor, existing authorized subscription. No new paid API/GPU; no reset-credit consumption. Local storage ceiling 30 GiB new assets, training 2 epochs initially, LoRA r=8, batch 1 with pair accumulation, max 1024 tokens; one seed 7170. Agent concurrency 1, per attempt 600 seconds, total study ceiling 120 Agent launches / 20 hours wall budget; repairs unlimited within resource budget. Monitor usage between phases; stop before exhausting available subscription. Initial PILOT target: 8 rank-train, 2 rank-dev, 4 gate-fit, 2 calibration, 4 final families (2 from one unseen repo), one repetition per action. Rough gate 18 + final 20 + development 12 = 50 launches, plus separate engineering smoke. Expand neither tasks nor repetitions after outcomes. Qualification may reduce counts before dependent outcomes, with reasons recorded. Dollar cost unknown. Quality noninferiority margin 0.05; this pilot will rarely establish it.

Next: finish the frozen development, gate-fit, calibration, and final execution matrices; publish independent recomputation and complete product verification.

## Current checkpoint

M1: 20 qualified families (21 candidates, 30 qualification attempts), data controller declared stable. M2/M3: implemented and 16 real optimization steps completed; clean process reload matched exactly. Text-only labels: 8 family preferences; execution preference signal insufficient. Current support scorer, static context and gate fail-closed paths passed focused checks and read-only review fixes.

R binding `b840e2b1bbf4a2c51cd87deb7a207621609ce92ce8ff3e9e2188816bcb9c4a94` is the pre-gate freeze. The earlier binding was superseded before any gate collection when the explicit Top2 development ablation and accurate strong-baseline constructor counters were wired. No training rerun occurred. Portable `configs/repo-aware-routing/routing.json` binds the same R; model locations are remappable without altering identity.

Execution controller is running the development matrix. Three initial calls were rejected by inherited parent-skill isolation before model start, plus one missing-qualification prelaunch attempt during data preparation. All remain recorded. Stable reruns use a temporary workspace outside global skill ancestry. Development N-/N+ first pair both produced independently checked patches; no quality effect inferred.

Private run root is the sibling `hermes-repo-aware-private/`; active command is `venv/bin/python scripts/repo_aware/evaluate.py --protocol ../hermes-repo-aware-private/dev-protocol-v2.json --resume`. Next run the predeclared equal-K protocol, then gate-fit and gate-calibration protocols using routing-frozen-v3.json; collect_feedback and train_gate afterward. Do not change frozen R while collecting gate data.

Draft PR48 created on the required stacked base. First CI failed only raw JUnit whitespace; narrow evidence attributes preserve bytes. Final CI and complete five-arm results remain pending. Formal full-suite initial result: 1279 pass, one environment failure because uv's lightweight venv lacked pip. Installing pip repaired the exact failing fresh-install test; latest focused 29 tests passed.

M4 execution complete: development N-/N+/S/R each 2/2, learned same-K Top2 2/2. No development quality gain observed. Gate fit collection has started with frozen R v3. Lightweight suite 1281 passed before evidence negative tests; evidence identity negative controls 8/8 plus public-table recomputation passed. Clean wheel doctor has no model imports. GitHub workflow modification was rejected for missing OAuth workflow scope; the workflow remains unchanged and ordinary pytest invokes public recomputation.
