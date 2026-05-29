# Phase 14 Fine-Tuned Embedding Router Model Card

## Scope

This artifact records a domain-specific SentenceTransformer fine-tuning path for
Hermes-style skill routing. The model checkpoint is not committed to this repo.

## Training Data

- Source: `training-pairs.jsonl`
- Pair count: 28
- Positive pairs: 16
- Hard-negative pairs: 12
- Labels: gold skill positives and task negative hard negatives
- Split policy: dev pairs for training, test pairs held out for reporting

The current training script consumes train-like positive pairs with
`MultipleNegativesRankingLoss` and train-like hard-negative pairs with
`ContrastiveLoss` at margin `1.5`. Held-out test rows remain reserved for
evaluation and regression judging.

## Training Command

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

## Evaluation

The committed baseline and fine-tuned result files come from a real model path
under `/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router`.
The checkpoint itself remains outside the repository.

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It is not a standard
external benchmark and does not establish SOTA.
