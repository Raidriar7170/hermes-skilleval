# Run and reproduce

Run repository-relative examples from this checkout. Python 3.11+ is required. Native, fixed and auto's cheap branches need only the base wheel, no Torch or Transformers. Real Agent execution additionally needs the existing authorized Codex login and the documented offline Docker executor image. No new paid provider is configured by these commands.

## Install

```sh
python -m build --wheel
python -m venv /tmp/hermes-routing
/tmp/hermes-routing/bin/pip install dist/hermes_skilleval-0.3.0-py3-none-any.whl
/tmp/hermes-routing/bin/hermes-maintain doctor
```

Configs and complete skill assets are explicit inputs from the checkout. The wheel contains executable code and sandbox resources. The example image `hermes-repo-aware-data:v1` is local; build the inherited clean executor first and then [the dependency layer](../../configs/repo-aware-routing/DataQualification.Dockerfile). A tag is not a publicly downloadable image identity.

## Current-source auto assist

Use a matching csvkit source snapshot for the supplied development smoke checks. It is a product integration observation, not a new independent task. The source baseline is the parent of the public fix linked by [this task specification](../../configs/repo-aware-routing/tasks/csvkit-empty-stack.json). The checks cover only the explicitly declared empty-input behavior and protected cases.

```sh
hermes-maintain assist \
  --repo /absolute/path/to/csvkit-source \
  --request configs/repo-aware-routing/assist/request.md \
  --repository-config configs/repo-aware-routing/assist/repository.json \
  --checks configs/repo-aware-routing/assist/checks.json \
  --registry configs/repo-portability/skills-v1/registry.json \
  --skill-assets configs/repo-portability/skills-v1 \
  --policy auto --routing-config configs/repo-aware-routing/routing.json \
  --output /tmp/new-hermes-auto-run --plan-only
```

Remove `--plan-only` for real authorized execution. Choose a new output directory for every attempt. Source content is copied, never automatically patched. `resolved` stays null for assist; inspect mapped requirement checks and the captured patch. Historical replay instead uses `hermes-maintain run` and still requires independently bound qualification and the canary.

All new policies use `--policy native|fixed|strong|repo-aware|auto --routing-config ...`. Legacy `--arm` retains its original meanings. Do not combine new policies with legacy arm/fixed overrides. Explicit repo-aware requires the bound adapter; missing assets produce an error. Auto records the declared cheap fallback and does not pretend it ran R.

For route-only inspection without an Agent:

```sh
hermes-maintain route --repo /absolute/path/to/source \
  --request configs/repo-aware-routing/assist/request.md \
  --registry configs/repo-portability/skills-v1/registry.json \
  --skill-assets configs/repo-portability/skills-v1 \
  --policy auto --routing-config configs/repo-aware-routing/routing.json \
  --output /tmp/new-routing-decision.json
```

## Rebuild models and data

No model weights or full upstream datasets are committed. The current trained adapter is retained locally by the study owner. Public users must acquire the exact public base revisions and retrain; retraining does not automatically reproduce an identical adapter or authorize reusing the old gate with a different R.

1. Follow [task preparation and qualification](../../configs/repo-aware-routing/tasks/README.md). Keep reference/target data outside Agent and routing inputs.
2. Use an isolated training environment: `pip install -e '.[repo-routing-train]'`. Recorded local versions are Torch 2.14.0, Transformers 5.17.0 and PEFT 0.21.0; CPU is supported as an explicit slower configuration. No CUDA was used in this study.
3. Put pinned encoder/reranker assets beneath `local-assets/`, outside tracked files. Do not commit that directory.
4. Run the real training and independent reload commands below. Paths in train.json resolve from the process working directory; routing model paths resolve from the routing configuration directory.

For exact public base assets, run this inside the isolated training environment. Preserve the recorded revisions and licenses.

```python
from huggingface_hub import snapshot_download
snapshot_download("pipizhao/SkillRouter-Embedding-0.6B",
    revision="c03c9bcee9fce92ab0262bb6dcf54d174a8ba558",
    local_dir="local-assets/SkillRouter-Embedding-0.6B")
snapshot_download("pipizhao/SkillRouter-Reranker-0.6B",
    revision="78986e1142d12857cfd85b8005e62902cd42d858",
    local_dir="local-assets/SkillRouter-Reranker-0.6B")
```

```sh
python scripts/repo_aware/prepare_rank_data.py --tasks /private/task-root \
  --registry configs/repo-portability/skills-v1/registry.json \
  --output local-assets/rank-train.jsonl
python scripts/repo_aware/train_reranker.py --config configs/repo-aware-routing/train.json
python scripts/repo_aware/train_reranker.py --reload local-assets/training-v1/training.json
python scripts/repo_aware/freeze.py --config configs/repo-aware-routing/routing.json \
  --registry configs/repo-portability/skills-v1/registry.json \
  --output local-assets/new-frozen-routing.json
```

The frozen identity binds source, base model files, adapter configuration/weights, pool, context and selection settings. A new adapter requires a new identity and new compatible gate feedback. Collect N/F/R only after freezing R, keep calibration families separate, then use:

```sh
python scripts/repo_aware/evaluate.py --protocol /private/gate-fit-protocol.json --resume
python scripts/repo_aware/collect_feedback.py --protocol /private/gate-fit-protocol.json --output /private/fit.jsonl
python scripts/repo_aware/collect_feedback.py --protocol /private/gate-calibration-protocol.json --output /private/calibration.jsonl
python scripts/repo_aware/train_gate.py --fit /private/fit.jsonl \
  --calibration /private/calibration.jsonl --r-version FROZEN_R_SHA256 \
  --output /private/new-gate.json
```

The calibration protocol must also be executed before collecting its feedback. Freeze the complete policy before final confirmation. All protocol entries use the same declared model/effort, isolation, timeout and skill pool. Do not regenerate final policies from observed final outcomes.

## Records-only

No model, Docker or credentials are needed to recompute published qualification:

```sh
python scripts/repo_aware/recompute_qualification.py
```

Execution exports use `export_execution.py --protocol PRIVATE_PROTOCOL --output NEW_PUBLIC_DIR`; public results use `recompute_execution.py --index PUBLIC_DIR/index.json --output RESULT.json` and `report.py` with the same arguments. These commands recompute outcomes from bound JUnit artifacts; they do not re-execute third-party code or prove behaviors outside the frozen checks.
