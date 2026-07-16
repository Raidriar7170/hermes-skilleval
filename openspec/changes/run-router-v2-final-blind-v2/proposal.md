## Why

Router V2 pilot-002 improved internal held-out ranking and negative-skill risk, but it used only 16 positive tasks, 9 supported negative labels, and model-only review. A final, independently human-reviewed 64/48 blind-v2 is required to test whether the already frozen Arm C checkpoints generalize without retraining, post-hoc tuning, or another blind set.

## What Changes

- Preregister one final blind-v2 protocol before any blind-v2 prompt or label is read.
- Validate an external human-authored and independently reviewed pack without model scoring or automatic adjudication.
- Freeze exactly 64 positive tasks and 48 negative-labeled tasks in a second commit before model scoring.
- Run one terminal Arm A versus Arm C evaluation for seeds `7170`, `7171`, and `7172`, retaining started, terminal, result, statistics, failure-slice, and lineage artifacts even on infrastructure failure.
- Apply the unchanged pilot-002 gate mechanically, report raw counts and paired statistics, and keep the default router unchanged regardless of outcome.
- Stop at `BLIND_V2_WAITING_FOR_HUMAN_DATA` after preregistration, synthetic model-load smoke, and blank authoring materials when the required external human pack is absent or incomplete.

## Capabilities

### New Capabilities

- `router-v2-final-blind-v2`: Fail-closed preregistration, human-pack validation, dataset freeze, single-attempt evaluation, statistics, gate decision, and frozen project closeout for Router V2 blind-v2.

### Modified Capabilities

None. Existing pilot-001, pilot-002, Phase 16, training, release, and default-router requirements remain unchanged.

## Impact

- Adds a dedicated blind-v2 contract, runner, CLI, focused tests, protocol document, preregistration, optional frozen dataset, final evaluation artifacts, and result-only public wording updates.
- Reuses the frozen Arm A/C model files, canonical 16-skill index, prompt-only query contract, skill representation, metric primitives, and pilot-002 gate as read-only inputs.
- Adds no dependency, training path, threshold, model, checkpoint, dashboard, Human Brief, generic qualification framework, release action, or default-router promotion.
- The branch starts from `origin/main` `8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552`, whose pre-existing Validate workflow currently fails; this change must not hide or misattribute that baseline state.
