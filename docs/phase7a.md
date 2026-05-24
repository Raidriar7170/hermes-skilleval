# Phase 7A: Cross-Encoder Reranker

Phase 7A adds a pretrained cross-encoder reranker after MiniLM embedding retrieval and evaluates it against the Phase 6B contrastive gated baseline on the 80-task, 45-skill benchmark.

## What Changed

- Added a `cross-encoder` router that retrieves candidates with the existing embedding router, scores `(task, skill)` pairs with a pretrained cross-encoder, and reranks only the candidate pool.
- Shared Phase 6B verification and contrastive selective helpers between the gated router and the cross-encoder router.
- Added CLI support for `--router cross-encoder`, `cross-encoder:sentence-transformers` compare specs, `--cross-encoder-model`, and `--cross-encoder-batch-size`.
- Added a committed Phase 7A benchmark run in `docs/demo/phase7a-cross-encoder`.

## Hardware Safety

The remote benchmark ran on the shared 8xA100 development machine after a read-only `nvidia-smi` check showed GPUs `0`, `1`, and `2` occupied and GPUs `3`, `4`, `5`, `6`, and `7` idle. The benchmark was pinned with `CUDA_VISIBLE_DEVICES=3`.

All remote project files, benchmark artifacts, temporary cache directories, and local model snapshots were kept under the user's NAS directory:

- `/mnt/data/minghongsun/hermes-skilleval`
- `/mnt/data/minghongsun/hermes-skilleval-models`
- `/mnt/data/minghongsun/hf-cache`
- `/mnt/data/minghongsun/tmp`

No GPU process was killed or reset.

## Commands

The remote machine could not reach Hugging Face, so the MiniLM embedding model and MS MARCO MiniLM cross-encoder were downloaded on the Mac and staged as local paths under `/mnt/data/minghongsun/hermes-skilleval-models`.

```bash
CUDA_VISIBLE_DEVICES=3 \
HF_HOME=/mnt/data/minghongsun/hf-cache \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
TMPDIR=/mnt/data/minghongsun/tmp \
PYTHONPATH=src \
python -m hermes_skilleval.cli compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-contrastive=gated:sentence-transformers,cross-encoder-minilm=cross-encoder:sentence-transformers \
  --embedding-backend sentence-transformers \
  --embedding-model /mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2 \
  --embedding-cache docs/demo/phase7a-cross-encoder/embedding-cache.json \
  --cross-encoder-model /mnt/data/minghongsun/hermes-skilleval-models/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --selective \
  --contrastive-selective \
  --output-dir docs/demo/phase7a-cross-encoder
```

A second rank-only cross-encoder run was added to isolate reranking quality from acceptance filtering:

```bash
CUDA_VISIBLE_DEVICES=3 \
HF_HOME=/mnt/data/minghongsun/hf-cache \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
TMPDIR=/mnt/data/minghongsun/tmp \
PYTHONPATH=src \
python -m hermes_skilleval.cli eval \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --router cross-encoder \
  --embedding-backend sentence-transformers \
  --embedding-model /mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2 \
  --embedding-cache docs/demo/phase7a-cross-encoder/embedding-cache.json \
  --cross-encoder-model /mnt/data/minghongsun/hermes-skilleval-models/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only
```

## Results

| Router | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 0.812 | 0.956 | 0.934 | 0.930 | 0.100 | 1.000 | 14.273 |
| gated-minilm-contrastive | 0.881 | 0.969 | 0.985 | 0.964 | 0.037 | 0.320 | 10.711 |
| cross-encoder-minilm selective | 0.775 | 0.781 | 0.838 | 0.794 | 0.000 | 0.175 | 18.222 |
| cross-encoder-minilm rank-only | 0.881 | 0.994 | 0.985 | 0.978 | 0.125 | 1.000 | 23.448 |

## Interpretation

The pretrained cross-encoder is useful as a reranker but not yet as a drop-in selective router. The rank-only run improves Recall@5 from `0.969` to `0.994` and NDCG@5 from `0.964` to `0.978` versus Phase 6B contrastive gating, while matching Recall@1 and MRR. That shows the learned pairwise scoring stage can recover more gold skills from the embedding candidate pool.

The trade-off is negative control: rank-only cross-encoder reranking raises Negative Hit Rate to `0.125`, especially on the deliberately ambiguous same-category robustness tasks. The selective cross-encoder run overcorrects in the other direction: it achieves `0.000` Negative Hit Rate, but Recall@5 falls to `0.781` and Selection Rate@5 falls to `0.175`.

The best current result is therefore not "replace Phase 6B." It is a clear next-step result: use the cross-encoder for ranking quality, then calibrate a better acceptance policy instead of applying the Phase 6B confidence thresholds directly to cross-encoder logits.

## Resume Value

Phase 7A demonstrates single-GPU deployment of a learned verifier reranker, offline model staging under shared A100 infrastructure, GPU-safe execution with `CUDA_VISIBLE_DEVICES`, and evidence-based analysis of ranking quality versus negative-skill control.
