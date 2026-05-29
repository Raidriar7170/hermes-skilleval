# Phase 15: Held-out generalization and provenance pack

Phase 15 separates the Phase 14 fine-tuned embedding-router result into a
strict held-out `test` split report and a sanitized provenance pack. It does not
train a new model; it audits the already trained Phase 14 model against records
whose task IDs were not used for train-like fine-tuning.

## Scope

Committed artifacts live under
`docs/demo/phase15-held-out-generalization/`. The pack may contain JSONL
evaluation records, summaries, model file hashes, and Markdown reports. It must
not contain model checkpoints, downloaded models, SSH details, tokens, private
hosts, or files outside `/mnt/data/minghongsun`.

## Held-Out Result

The held-out judge filters the Phase 14 baseline and fine-tuned result files to
`split == "test"`. The current source result files contain 12 migration tasks;
4 are held-out `test` tasks.

| Metric | Baseline | Fine-tuned | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000000 | 1.000000 | +0.000000 |
| MRR | 1.000000 | 1.000000 | +0.000000 |
| NDCG@5 | 1.000000 | 1.000000 | +0.000000 |
| Negative Hit Rate | 0.250000 | 0.250000 | +0.000000 |
| Negative Accepted Rate | 0.250000 | 0.250000 | +0.000000 |

The held-out guard is `PASS` because the fine-tuned router introduces no
regression on the four held-out migration tasks. This is regression-free
held-out evidence, not a held-out uplift claim.

## Provenance

`provenance.json` and `provenance.md` join:

- Phase 14 training data summary and leakage guard.
- Phase 14 training config.
- Remote A100 train-run summary.
- Remote model file manifest with SHA-256 hashes.
- Phase 15 held-out regression summary.

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
