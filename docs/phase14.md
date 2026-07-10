# Phase 14: Fine-tuned embedding router

Phase 14 adds a reproducible path for domain-specific embedding-router
fine-tuning. It exports supervised task-skill pairs, writes a remote-ready A100
training config, and evaluates a real fine-tuned SentenceTransformer model only
when a model path exists.

## Scope

This phase keeps local repository work separate from GPU training work. The repo
may contain training pairs, summaries, configs, model cards, and evaluation
reports, but it must not contain model checkpoints, embedding caches, downloaded
models, training logs, private hosts, tokens, or SSH details.

## Local Artifacts

Committed local artifacts live under
`docs/demo/phase14-finetuned-embedding-router/`:

- `training-pairs.jsonl`
- `training-summary.json`
- `train-config.json`
- `model-card.md`

The current committed local export contains 28 task-skill pairs from the Phase 9
migration benchmark: 16 gold-skill positive pairs and 12 task-labeled hard
negative pairs. The leakage guard is `PASS` because train-like `dev` tasks and
held-out `test` tasks do not share task IDs.

The remote training script uses train-like positive pairs with
`MultipleNegativesRankingLoss` and train-like hard-negative pairs with
`ContrastiveLoss` at margin `1.5`. Held-out `test` rows remain reserved for
evaluation and regression judging.

## Training Output Root

The trainer selects one output root in this order: explicit CLI
`--output-root`, `output_root` from the JSON config, then the backward-compatible
default `/mnt/data/minghongsun`. A relative selected root resolves from the
trainer process working directory, not from the config file's directory.
Relative `output_dir` values resolve beneath the selected root; absolute values
are accepted only when they remain contained by that root after normalization
and existing-symlink resolution.

The committed historical config records the A100 path
`/mnt/data/minghongsun/hermes-skilleval-phase14`. With that config, the default
remote command remains:

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

For a local config whose `output_dir` is relative, for example
`models/minilm-skill-router`, an explicit local-root override is:

```bash
python scripts/train_embedding_router.py \
  --config /path/to/train-config.local.json \
  --output-root "$PWD/.hermes-training"
```

An override does not relocate an absolute `output_dir`; if that directory is
outside the selected root, the trainer exits before dependency imports or
output writes.

The script requires `sentence-transformers` and `torch` on the training machine.
It writes the model to the configured output directory and does not copy the
checkpoint into this repository.

## Evaluation Artifacts

These files are committed only after a real fine-tuned model path is evaluated:

- `baseline-results.jsonl`
- `finetuned-results.jsonl`
- `regression-summary.json`
- `comparison.md`

The comparison command is:

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase14-finetuned-embedding-router \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

## Current Real Evaluation

The current imported run used a real fine-tuned model path under
`/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router`.
It compares 12 Phase 9 migration tasks against the cached MiniLM baseline.

| Metric | Baseline | Fine-tuned | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000000 | 1.000000 | +0.000000 |
| MRR | 0.902778 | 1.000000 | +0.097222 |
| NDCG@5 | 0.920888 | 1.000000 | +0.079112 |
| Negative Hit Rate | 0.333333 | 0.083333 | -0.250000 |
| Negative Accepted Rate | 0.333333 | 0.083333 | -0.250000 |

The regression guard is `PASS`: three-epoch hard-negative training removes the
previous `browser-local-dashboard` negative-skill regression while preserving
full Recall@5.

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
