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

The remote training script uses positive `dev` pairs with
`MultipleNegativesRankingLoss`. The hard-negative rows are still exported for
auditability, result interpretation, and future training losses that consume
explicit negative labels.

## Remote Training

GPU training outputs must stay under:

`/mnt/data/minghongsun/hermes-skilleval-phase14`

The remote-ready script is:

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

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
| MRR | 0.902778 | 0.916667 | +0.013889 |
| NDCG@5 | 0.920888 | 0.938488 | +0.017600 |
| Negative Hit Rate | 0.333333 | 0.250000 | -0.083333 |
| Negative Accepted Rate | 0.333333 | 0.250000 | -0.083333 |

The regression guard is `REVIEW_REQUIRED`, not `PASS`: the fine-tuned router
improves aggregate ranking and reduces mean negative-hit rate, but
`browser-local-dashboard` introduces a new negative skill selection. The README
roadmap therefore remains unchecked until that per-task regression is removed
or explicitly accepted with a stronger guard rationale.

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
