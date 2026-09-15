# Method and evidence boundaries

Active contract: [FullStack Goal](../goals/Hermes_Repo_Aware_Cost_Aware_FullStack_Codex_Goal.md).

This is a local PILOT, not a confirmatory claim. Twenty qualified public repair families are partitioned 8 rank-train / 2 rank-dev / 4 gate-fit / 2 gate-calibration / 4 final-test. Two final families are from csv-diff, absent from fitting and calibration. Qualification preserves 21 candidates and 30 attempts. Historical task results are not reused as new outcomes.

## Models

Reuse public SkillRouter encoder revision `c03c9bcee9fce92ab0262bb6dcf54d174a8ba558` and reranker revision `78986e1142d12857cfd85b8005e62902cd42d858`. Backbone provenance: [SkillRouter](https://github.com/zhengyanzhao1997/SkillRouter), [reranker model](https://huggingface.co/pipizhao/SkillRouter-Reranker-0.6B). Their reported results are not Hermes results.

Local MPS float32 training uses PEFT LoRA r=8, alpha=16, dropout=.05 on observed q_proj/v_proj, AdamW learning rate 5e-5, seed 7170, two epochs, eight family-weighted textual preference pairs. Text labels are explicitly model_judged_text, weight .5; they are relative textual support judgments, not causal execution labels. There is no adequate execution preference signal. Unknown skills are not independently labelled failures.

Training and inference share causal final-position yes-minus-no logits, the same four-section tokenization and saved adapter. The 1024-token budget reserves task/context/metadata/evidence proportions 30/25/10/remainder after the original chat prefix and suffix. Long task truncation preserves head and tail; every section records truncation. Evidence text is capped at 4000 characters. This is a new representation, separately compared with untrained same-backbone versions. A request-only inference ablation reuses the same trained checkpoint; no separately trained request-only model is claimed.

## Context, support and selection

The extractor statically reads current/pre-repair source bytes and TOML/INI/AST without executing setup.py. Directory traversal is pruned and bounded, file/byte/snippet budgets are explicit, and unknown layouts remain unsupported. All five execution policies receive one identical sourced summary. The strong baseline retrieves with request-only input.

The execution pool reuses five complete licensed packages from the inherited registry. This is deliberately a small natural pool, not an index-scale experiment. It limits routing discrimination and generalization. No copied aliases or confirmation-answer skills are added.

Shared learned scoring produces per-requirement text-support estimates. Explicit bounded contradiction rules cover preservation/removal, read-only/overwrite and declared network requirements; other conflicts are not comprehensively solved. Unsupported scores remain UNKNOWN, never success probabilities. A .8 fixed sigmoid threshold is conservative and may yield complete fallback.

The finite-pool optimizer exactly enumerates subsets under K<=4 and a 4000 tokenizer-token potential body-loading budget. Objective: mean requirement maximum support + .25 summed relevance - .2 explicit equivalence pair penalty - .1 normalized potential loading tokens. Candidates without any supported requirement are excluded. Empty/nonpositive feasible sets fall back N. The guarantee covers only this proxy within the retrieved pool, not actual utility or global library optimality. Same-K and variable-K development rows are separate.

## Gate and protocol

R is frozen before gate data. The gate uses only request lengths/structure, static source counts and generic tool mentions. Features normalize on fit families only. Regularized action-conditional logistic quality and linear normalized time/token models use real N/F/R outcomes; unknown quality is missing. One-class quality uses a smoothed constant and explicit INSUFFICIENT state. Independent calibration checks Brier scores; tiny samples do not support a calibrated probability guarantee. Missing or degenerate data returns N. Dollars remain null.

Execution uses the inherited isolated Codex container, one concurrent trial, gpt-5.6-sol/medium, 600 seconds per Agent, one predeclared repetition per cell. Native-minus development ablation is separate from equal-information main arms. The final H decision is persisted before its own Agent run. Main outcomes use controller-owned target and protected regression checks against reconstructed patches. No reference files enter the Agent or router snapshot.

No default promotion, merge or release. Quality noninferiority margin is .05; small samples cannot establish equivalence from a nonsignificant difference. Unknowns and prelaunch failures remain visible. Training and collection expense are separate from request cost.
