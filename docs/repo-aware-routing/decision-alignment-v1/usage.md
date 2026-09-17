# Installed commands

Run from a checkout containing the referenced public artifacts. The wheel contains code, not weights or the study dataset. Base install requires only PyYAML; records/selection/structural preflight do not import Torch, Transformers, PEFT or sklearn.

```sh
python -m pip install .
hermes-applicability --help
hermes-applicability records
hermes-applicability select-for-goal --output /tmp/hermes-decision
hermes-applicability decision-replay --output /tmp/hermes-decision
hermes-applicability preflight --operation calibrate \
  --contract /tmp/hermes-decision/applicability-contract.json \
  --output /tmp/hermes-decision/preflight.json
```

The last command intentionally exits **2**, writes a machine-readable BLOCKED report, and constructs zero models. Initial token status is TOKENIZATION_UNCHECKED. It nevertheless proves the context-known group upper bound is 2 < 3. Creating the failure report is not calibration success.

The real guarded scoring command also rejects the original cal before opening a model config or tokenizer:

```sh
hermes-applicability aligned-score --split cal \
  --config /tmp/not-present-model-config.json \
  --contract /tmp/hermes-decision/applicability-contract.json \
  --output /tmp/hermes-decision/cal-score-preflight.json
```

It exits 2. A missing model config here is intentional proof that structural rejection precedes heavy resource access.

Optional **local tokenizer only** (requires the existing Transformers tokenizer dependency) uses a score config with exact cached tokenizer hashes. It does not download or read/hash model weights:

```sh
hermes-applicability preflight --operation calibrate \
  --contract /tmp/hermes-decision/applicability-contract.json \
  --tokenizer-config local-assets/score-config.json \
  --snapshots local-assets/original-task-snapshots \
  --output /tmp/hermes-decision/repaired-preflight.json
```

This command was exercised with the existing private original snapshots/config, yielding four context-eligible groups, 40/40 complete token inputs, but BLOCKED due to unverified environment. `--snapshots` verifies pinned source hashes and extracts new context; it never relabels old logits. Omit it for the old input. Public `context_repairs` and row facts are in the committed report; private paths and full token IDs are omitted.

For explicit online advisory, use the dev-frozen label-free manifest and target-specific contract. This command's parser and blocked path were exercised; this round did **not** run its model forward:

```sh
hermes-applicability advise \
  --manifest /tmp/hermes-decision/decision-contracts.json \
  --contract /tmp/hermes-decision/applicability-contract.json \
  --config local-assets/score-config.json \
  --input local-assets/public-input.json \
  --context-state usable --output /tmp/hermes-decision/advice.json
```

Public input has exactly request/context/skill_name/skill_description/skill_body. A performs one output-axis forward; J uses the two supervised instructions and ranks by their **raw** product. Advisory always accepted=false. `--environment-known` is only appropriate for actually established facts, never to bypass a missing prerequisite. Supported mode requires an explicit supported contract and `--calibration`, matching identities and a non-null threshold. No such artifact is established here.

`aligned-calibrate --config ... --contract ... --scores ... --output ...` performs the same cal prerequisite gate before score consumption/fitting. `aligned-train --config ... --output ...` validates the config's exact fit/model-dev inputs and supervision before calling training; it does not read cal/check labels for preflight. Training was **not run**. Historical `train`, `score`, `calibrate` remain unchanged legacy protocol commands; use the `aligned-` entrypoints for the new protocol.

Defaults remain native; no command launches a repair Agent. Installation and regression evidence: [validation.json](../../../artifacts/decision-alignment-v1/validation.json).
