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

The current training script consumes positive dev pairs with
`MultipleNegativesRankingLoss`. Hard negatives are exported for audit,
interpretation, and future losses that use explicit negative labels.

## Training Command

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

## Evaluation

The baseline and fine-tuned result files are committed only after a real
fine-tuned model path is evaluated. The checkpoint itself remains outside the
repository.

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It is not a standard
external benchmark and does not establish SOTA.
