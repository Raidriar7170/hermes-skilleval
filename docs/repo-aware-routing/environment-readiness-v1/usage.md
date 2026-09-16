# Installed entrypoints

The wheel includes code and only requires PyYAML. Study artifacts, frozen source
snapshots, profile, private wheel assets and model weights remain external.
`PROJECT` is the checked-out public repository; `SNAPSHOTS` contains the four
original task-id directories; `BUILD_ROOT` is a new private preparation directory.
Set these paths explicitly. No personal home directory is assumed.

```sh
python -m pip wheel . --no-deps -w dist
python -m venv /tmp/hermes-light
/tmp/hermes-light/bin/pip install dist/hermes_skilleval-0.3.0-py3-none-any.whl
/tmp/hermes-light/bin/hermes-applicability --help
```

Commands below were exercised with actual external assets. Global options precede
the subcommand. Prepare once (public dependency access inside Docker build only):

```sh
hermes-applicability \
  --root "$PROJECT/artifacts/conditional-applicability-v1" \
  --registry "$PROJECT/configs/conditional-applicability-v1/registry.json" \
  --environment-profile "$PROJECT/configs/environment-readiness-v1/profile.json" \
  probe-environment --snapshots "$SNAPSHOTS" \
  --private-build-root "$BUILD_ROOT" --output "$FACTS"
```

A successful run saves per-task `wheelhouse` assets under BUILD_ROOT. Do not
replace those files or reuse facts after a source/profile/dependency change.
The controller uses a pinned official Python base and an offline install recipe
for probes; facts are not proof of safety and grant no execution authority.

```sh
hermes-applicability \
  --root "$PROJECT/artifacts/conditional-applicability-v1" \
  --registry "$PROJECT/configs/conditional-applicability-v1/registry.json" \
  --rule "$PROJECT/configs/conditional-applicability-v1/protocol.json" \
  --project-root "$PROJECT" \
  --environment-profile "$PROJECT/configs/environment-readiness-v1/profile.json" \
  --environment-assets "$BUILD_ROOT" \
  preflight --operation cal-score \
  --contract "$PROJECT/artifacts/decision-alignment-v1/applicability-contract.json" \
  --snapshots "$SNAPSHOTS" --environment-facts "$FACTS" \
  --output "$OUTPUT/preflight.json"
```

Without tokenizer configuration this intentionally exits 2 with TOKENIZATION_UNCHECKED,
while the environment layer can be SATISFIED. Add `--tokenizer-config "$MODEL_CONFIG"`
to this preflight for local tokenizer-only qualification. The config must point to
the existing frozen A base and epoch-3 adapter with exact recorded hashes.
The repaired four-task input qualified 40/40 rows; missing facts still reject
strict scoring before tokenizer/model construction.

Using the same global options, `aligned-score --config "$MODEL_CONFIG" --split cal`
accepts the same contract/snapshots/environment-facts/output options. It saves
`<output-stem>-scores.json` and uses only A's required axis. `aligned-calibrate`
adds `--scores` pointing to that stream and saves `<output-stem>-calibration.json`.
This calibration is A-only; J stays raw advisory. No command starts a repair Agent.

The installed advisory replay used the same globals plus:

```sh
hermes-applicability [GLOBAL_OPTIONS] advise \
  --config "$MODEL_CONFIG" --input "$PUBLIC_INPUT" \
  --manifest "$PROJECT/artifacts/decision-alignment-v1/decision-contracts.json" \
  --contract "$PROJECT/artifacts/decision-alignment-v1/applicability-contract.json" \
  --task-id sqlite-utils-issue-211 --snapshots "$SNAPSHOTS" \
  --environment-facts "$FACTS" --context-state usable --output "$OUTPUT/advice.json"
```

`[GLOBAL_OPTIONS]` denotes the expanded global flags above, not literal CLI syntax.
PUBLIC_INPUT contains only request/context/skill_name/skill_description/skill_body.
Verified advice checks it against the corresponding prepared source input.
Advisory remains accepted=false. Strict support requires a supported contract,
a non-null v2 calibration threshold, the registered public input and matching
environment/model bindings; it cannot authorize arbitrary new tasks.
`--environment-known` remains a historical declaration and is ignored as evidence.

Historical `records` retains original relative source bindings. For an external
working directory, expose the public tree's `artifacts`, `configs`, and `src`
as read-only files or symlinks, then run the installed `hermes-applicability records`.
This matched 40 old rows with zero model calls. Do not rewrite old binding hashes.

Independent cal-only reload (no old check selection or model):

```sh
python "$PROJECT/scripts/repo_aware/environment_readiness_replay.py" \
  --evidence "$PROJECT/artifacts/environment-readiness-v1" \
  --labels "$PROJECT/artifacts/conditional-applicability-v1/labels.jsonl" \
  --rule "$PROJECT/configs/conditional-applicability-v1/protocol.json" \
  --output "$OUTPUT/reload.json"
```

It requires the optional local numpy/scipy fitting dependencies. A clean lightweight
install can inspect records/facts/span behavior without Torch, Transformers or PEFT.
