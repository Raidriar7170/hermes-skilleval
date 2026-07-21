## Why

Router V2 pilot-002 improved internal held-out ranking and negative-skill risk, but it used only 16 positive tasks, 9 supported negative labels, and model-only review. The original final blind-v2 plan required an external human-authored 64/48 pack; the user has now explicitly replaced that blocked plan with a larger, fully agent-generated protocol using two role-isolated reviewers and unanimous acceptance, while preserving the frozen Arm A/C models, gate, and one-attempt boundary.

The first successor execution, Run 001, later stopped before dataset construction because model-authored candidate indexes used `1..16`. Run 002 preserves the Run 001 terminal, reuses none of its responses, removes candidate identity from Generator output, and assigns every index and opaque ID deterministically in the host before continuing the same 128/96 research contract.

## What Changes

- Supersede the human-pack preregistration with a new authoritative `Commit A-agent` before any candidate generation, while retaining the existing human-protocol commit as non-authoritative history.
- Generate exactly 256 first-round candidates with `gpt-5.6-sol` at reasoning effort `max`, then permit at most one deficit-only generation round.
- Review each candidate in separate fresh sessions with Reviewer A (`gpt-5.6-sol`, `ultra`) and Reviewer B (`gpt-5.6-luna`, `max`) without exposing generator labels, the other review, quotas, Router scores, or prior task context.
- Accept a candidate only when the generator and both reviewers exactly agree on gold skill and negative-skill/none, and both reviewers independently accept naturalness, single-primary-skill clarity, non-leakage, and negative confusability.
- Freeze exactly 128 tasks over 16 canonical skills, with eight tasks per gold skill, six negative-labeled plus two positive-only tasks per skill, 96 negative-labeled tasks total, and 128 distinct semantic families.
- Apply preregistered deterministic contamination checks and hash-based selection without loading Arm A/C; keep raw generation/review ledgers outside Git and bind their hashes, prompts, model configurations, and run lineage in Commit B.
- Run one terminal Arm A versus Arm C evaluation for seeds `7170`, `7171`, and `7172`, retain complete failure evidence, apply the unchanged pilot-002 gate mechanically, and return `KEEP_BASELINE` regardless of outcome.
- Restrict every result claim to the agent-constructed, dual-agent-unanimous blind set; never describe it as human-reviewed, statistically independent, or proof of generalization to human-authored real-world tasks.

## Capabilities

### New Capabilities

- `router-v2-final-blind-v2`: Fail-closed agent-only preregistration, sealed generation, role-isolated dual review, deterministic dataset freeze, single-attempt evaluation, statistics, bounded result wording, and frozen project closeout for Router V2 blind-v2.

### Modified Capabilities

None. Existing pilot-001, pilot-002, Phase 16, training, release, and default-router requirements remain unchanged.

## Impact

- Reopens the dedicated blind-v2 contract, runner, CLI, tests, protocol, and preregistration created by historical commit `09ba4104a147a2f740ef69283c850f40e78a0b15`; that commit remains audit history but cannot authorize agent generation or formal evaluation.
- Reuses the frozen Arm A/C model files, canonical 16-skill index, prompt-only query contract, skill representation, metric primitives, pilot-002 gate, and existing embedding/runtime dependencies as read-only inputs.
- Adds three explicitly disclosed OpenAI data-construction roles, but no router training model, checkpoint, optimizer step, threshold, dashboard, Human Brief, generic qualification framework, release action, or default-router promotion.
- The branch remains based on `origin/main` `8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552`, whose pre-existing Validate workflow failure must not be hidden or attributed to this change.
