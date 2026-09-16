# Conditional-applicability study commands

Run from the repository root. The installed `hermes-applicability` command and `PYTHONPATH=src python scripts/repo_aware/applicability_study.py` share the same implementation. Native/fixed maintenance remains unchanged and does not import model dependencies.

Base install and records replay need only the package's normal dependencies:

```sh
python -m pip install .
hermes-applicability --help
hermes-applicability records
```

The records command verifies source bindings and recomputes the group-weighted tables and selection outcomes without Torch, models, credentials or Agent calls. It does not reproduce model inference, semantic truth of weak labels, or execution utility. Source artifacts are required alongside the wheel; this is a study replay command, not an embedded dataset distribution. Floating-point recomputation permits 1e-10 tolerance only for floating values; hashes, IDs and decisions remain exact.

For a separately named research reproduction, install the optional local ML environment and obtain the exact base revision from `base-identity.json`. Models/checkpoints remain private. `configs/conditional-applicability-v1/train.json` is a portable recipe with repository-root-relative paths; its output must not already exist.

```sh
python -m pip install '.[repo-routing-train]'
hermes-applicability train --config configs/conditional-applicability-v1/train.json
hermes-applicability reload \
  --summary local-assets/conditional-applicability-new-training/training-summary.json \
  --epoch 1
```

Actual study invocations used the same `train --config` and `reload --summary --epoch` entrypoints with private asset/output paths and both preregistered lambda values. Public summaries retain effective settings, gradients, checkpoint hashes and reload errors; exact private paths are intentionally omitted. A new run is not a replacement for the frozen check evidence and must not reuse the current check for tuning.

The `predict` input is an allowlisted object with exactly `request`, `context`, `skill_name`, `skill_description`, `skill_body`. Labels, task IDs, split and rationales are rejected. Config requires base/device/max_length, base_files hashes, and optional adapter/adapter_files hashes. Raw prediction is advisory; without a calibration or known conditions it cannot accept a skill.

```sh
hermes-applicability predict --config local-assets/score-config.json \
  --input local-assets/public-input.json
```

For calibrated scoring, add `--calibration artifacts/conditional-applicability-v1/calibration.json`; `--context-state usable --environment-known` is appropriate only after actually establishing those facts. It checks the same scorer identity and acceptance function as offline evaluation. Unavailable model files report explicit fallback; incompatible weights/calibration fail rather than substituting the old model. Do not mark unknown prerequisites as known to obtain acceptance.

Other implemented subcommands are `validate-labels`, `baselines`, `score`, `freeze`, `calibrate` and `check`; inspect each command's `--help` for required arguments. `score --no-context` is an inference ablation, not another independently trained model.

Public acquisition is separate from labeling. The pinned source/request manifest is `acquisition.json`; complete queried issue pages stay private, while the 24 selected requests are published. GitHub page bodies can change, so compare hashes before calling a rerun exact. The preparation script reads local clones and cached GitHub API page JSON, writes only a new output root, and never reads reference patches:

```sh
PYTHONPATH=src python scripts/repo_aware/prepare_applicability.py \
  --sources-root local-assets/upstreams --issues-root local-assets/issue-pages \
  --scratch local-assets/new-preparation-private --output-root local-assets/new-preparation
```

Use GitHub `gh api` with the exact read-only endpoints in `acquisition.json` to obtain the pages. `--sources-root` contains `sqlite-utils`, `csvkit`, `csv-diff` Git clones with the source revisions present. The script's `--help` and core CLI help were actually executed. The final installation evidence distinguishes executed model commands from the portable reproduction examples above.

The new channel is deliberately not an accepted `auto`/Gate repair version. Relabeling an old Gate's hash cannot activate it: the existing routing entrypoint rejects the new experimental version. The independently callable `hermes-applicability predict` is the available public-text inference surface; native/fixed paths remain unchanged. No supported execution is claimed merely because this scorer can run.

## Executed installation checks

`installation-verification.json` records the actual wheel SHA-256 and checks. A clean wheel-only environment without Torch/Transformers/sklearn ran `hermes-applicability records`: MATCHED, 40 check rows, zero model calls. All four new module byte contents matched the wheel.

A separate installed ML wheel was invoked from outside the checkout with this exact command:

```sh
hermes-applicability predict --config score-config.json \
  --input public-input.json --calibration calibration.json --context-state usable
```

That directory used local-assets symlinks to the authorized cached base and selected private adapter. The corresponding portable config is `configs/conditional-applicability-v1/score-local.example.json`; the public input and output are `artifacts/conditional-applicability-v1/predict-example.json` and `installed-prediction.json`. The two logits and compact input identities matched the saved selected-epoch development record with maximum absolute error 0. The result was SCORED, accepted=false, reason=unknown_environment: this is real inference, not a supported repair execution.

To reproduce with the current local selected weights, place the example config and public input under those filenames, copy the bound calibration, and make local-assets/base and local-assets/support-adapter point to the exact hashed assets. Weights are not distributed in Git. A newly trained adapter has a different identity and needs its own disjoint calibration/check; do not attach this frozen calibration to it by editing hashes.

The recorded model-selection command used `freeze --summaries <joint-summary> <noaux-summary> --rank-config <original-rank-config>`. Both candidates were trained with `train --config` and every epoch verified using `reload --summary ... --epoch 1|2|3`. Original rank scoring used `score --rank-only --split check`; support scoring and no-context scoring used the same public protocol. All comparison stream paths are in check-score-index.json.
