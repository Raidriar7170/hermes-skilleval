# Exercised entrypoints

The new entrypoint is `hermes-applicability independent-validate`. The equivalent
module invocation used for the actual study is
`python -m hermes_skilleval.repo_routing.independent_validation`. Run `--help` for
exact options. Historical commands retain their earlier meaning.

Set `PROJECT` to the public checkout, `PRIVATE` to the separately prepared private
study directory, and `OUTPUT` to a fresh output directory. Never overwrite the
frozen published outputs. Below, `COMMON` is a shell array:

```sh
COMMON=(
  --tasks "$PROJECT/artifacts/frozen-independent-validation-v1/tasks.json"
  --registry "$PROJECT/configs/conditional-applicability-v1/registry.json"
  --protocol "$PROJECT/configs/frozen-independent-validation-v1/protocol.json"
  --project-root "$PROJECT"
)
hermes-applicability independent-validate --stage preflight \
  "${COMMON[@]}" --output "$OUTPUT/preflight.json"
```

This records-only roster/binding preflight performs zero model calls. Measured
source environments must be separately prepared with the profile's pinned base,
explicit capabilities and matching source snapshots. `score` rechecks the actual
source/wheel/image recipes before model construction. The original legacy probe
payload is unchanged; the new explicit-capability profile selects its own
frozen payload.

The actual cal scoring command used the following flags (with concrete local
paths), followed by cal-only fitting:

```sh
python -m hermes_skilleval.repo_routing.independent_validation \
  --stage score --split cal "${COMMON[@]}" \
  --model-configs "$PRIVATE/model-configs.json" \
  --snapshots "$PRIVATE/snapshots" \
  --environment-facts "$PROJECT/artifacts/frozen-independent-validation-v1/environment-facts.json" \
  --environment-profile "$PROJECT/configs/frozen-independent-validation-v1/environment-profile.json" \
  --environment-assets "$PRIVATE/environment-assets" \
  --output "$OUTPUT/cal-scores.json"
python -m hermes_skilleval.repo_routing.independent_validation \
  --stage calibrate "${COMMON[@]}" \
  --scores "$OUTPUT/cal-scores.json" --cal-labels "$OUTPUT/cal-labels.jsonl" \
  --output "$OUTPUT/policy-lock.json"
```

Model configs are local path adapters to the frozen base/A/J/original-rank files;
`protocol.json` publishes their verified content identities. They contain no new
fit parameters. The cheap classifier and priors are read directly from the old
frozen baseline JSON. Prediction stages reject label arguments and never open
annotation files. Annotation merging uses `scripts/repo_aware/independent_merge_labels.py`
on a single requested split and exactly two blinded contexts.

For check prediction, use the same score flags with `--split check`, add
`--lock "$OUTPUT/policy-lock.json" --lock-sha256 "$LOCK_SHA"`, and choose
`--output "$OUTPUT/check-scores.json"`. `LOCK_SHA` is the freshly verified SHA-256
of the policy lock. The score command writes `check-scores.lock.json` before any
check annotation is generated. No threshold does not stop raw scoring.

Only after predictions are locked and check labels are merged:

```sh
hermes-applicability independent-validate --stage check "${COMMON[@]}" \
  --scores "$OUTPUT/check-scores.json" --scores-sha256 "$PREDICTIONS_SHA" \
  --lock "$OUTPUT/policy-lock.json" --lock-sha256 "$LOCK_SHA" \
  --check-labels "$OUTPUT/check-labels.jsonl" --output "$OUTPUT/results.json"
hermes-applicability independent-validate --stage records "${COMMON[@]}" \
  --scores "$OUTPUT/check-scores.json" --scores-sha256 "$PREDICTIONS_SHA" \
  --lock "$OUTPUT/policy-lock.json" --lock-sha256 "$LOCK_SHA" \
  --check-labels "$OUTPUT/check-labels.jsonl" --results "$OUTPUT/results.json" \
  --output "$OUTPUT/records.json"
```

`PREDICTIONS_SHA` comes from the separate prediction lock, not from recomputing a
new hash after edits. The records path rechecks source/protocol identity, exact
row alignment and saved metrics without Torch/Transformers/PEFT. The independent
arithmetic reload also reconstructs cal curves and check decisions:

```sh
python "$PROJECT/scripts/repo_aware/independent_reload.py" \
  --root "$OUTPUT" --protocol "$PROJECT/configs/frozen-independent-validation-v1/protocol.json" \
  --baseline "$PROJECT/artifacts/conditional-applicability-v1/baseline-models.json" \
  --output "$OUTPUT/reload.json"
```

Reload fitting needs NumPy/SciPy; basic records does not. The clean wheel was
installed into a separate lightweight environment and exercised from `/tmp`.
Source snapshots, model weights, dependency wheels, auth material and private
traces remain outside the public package. The conditional repair matrix was not
started because A had no new-cal operating point; there is no claim of repair
utility or a runnable approved production policy.

Historical source-reference audit was independently reproduced from the exact
starting commit (81 matching source-file records):

```sh
python "$PROJECT/scripts/repo_aware/independent_history.py" \
  --repository "$PROJECT" --baseline 23b303d1c3c02de03b4447f71df68d9b8da852af \
  --output "$OUTPUT/history-recomputed.json"
```

Post-check descriptive appendix (no new scores or refits):

```sh
python "$PROJECT/scripts/repo_aware/independent_descriptive.py" \
  --root "$OUTPUT" --output "$OUTPUT/descriptive-slices.json"
```

The published records use prediction SHA
`c71e4eae7f209efa53685de559933d99b36930e737cf88e54bb1b52b6ae32db8`
and policy SHA
`94d8db438e96a78ba52aa7a111a0b913ddf87eb1113189d4c988fcf4f4a56438`.
