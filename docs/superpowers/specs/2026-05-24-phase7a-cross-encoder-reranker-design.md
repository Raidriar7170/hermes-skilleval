# Phase 7A Cross-Encoder Reranker Design

## Goal

Add an optional pretrained cross-encoder verifier/reranker to Hermes SkillEval so the project can evaluate a realistic learned skill-routing stage on a single free A100 GPU without training or disturbing other GPU users.

## Context

Phase 6B currently has a strong embedding plus contrastive gated baseline:

- `embedding-minilm`: high coverage and strong Recall@5, but higher ambiguous negative acceptance.
- `gated-minilm-selective`: stronger top-rank quality, but still accepts many ambiguous negatives.
- `gated-minilm-contrastive`: best negative control, with lower selection rate.

Phase 7A should test whether a pretrained cross-encoder can improve semantic reranking after embedding retrieval while preserving the contrastive safety behavior that made Phase 6B valuable.

The current dev machine exposes eight A100-80GB GPUs. A read-only check showed GPUs `0`, `1`, and `2` occupied by existing work and GPUs `3`, `4`, `5`, `6`, and `7` effectively idle. Phase 7A runs must pin to one idle GPU with `CUDA_VISIBLE_DEVICES=3` by default and must not kill or inspect-modify other users' processes.

## Design Summary

Introduce a new `cross-encoder` router that wraps the existing embedding router:

1. Use the existing embedding backend to retrieve a candidate pool.
2. Score each `(task text, skill text)` pair with a pretrained cross-encoder model.
3. Rerank only the candidate pool by cross-encoder score.
4. Optionally apply the existing selective and contrastive acceptance controls.
5. Emit normal `results.jsonl`, markdown reports, comparison reports, and failure analysis through the existing CLI flow.

This keeps the architecture incremental: the embedding router remains the retrieval stage, the new router owns learned pairwise reranking, and the gated contrastive logic remains the acceptance policy.

## Components

### Cross-Encoder Model Wrapper

Add a small protocol and implementation in a new router module:

- `CrossEncoderModel` protocol with `cache_key` and `score_pairs(pairs: Iterable[tuple[str, str]]) -> list[float]`.
- `SentenceTransformerCrossEncoderModel` implementation using the optional `sentence-transformers` dependency.
- `StaticCrossEncoderModel` or test-local fake model for deterministic unit tests.

Dependency failure should reuse the style of `EmbeddingDependencyError`: a missing optional backend prints a CLI error and exits with code `2`.

### Cross-Encoder Router

Add `CrossEncoderReranker` as a `SkillRouter` implementation. It should accept:

- `base_router`: defaults to the existing `EmbeddingRouter`.
- `model`: defaults to a sentence-transformers cross-encoder when selected through the CLI.
- `candidate_pool_size`: defaults to `10`.
- `selective`, `min_confidence`, `contrastive_selective`, `contrastive_margin`, and `min_evidence`: same semantics as the gated router.

The router returns scores for all skills. Candidate scores come from the cross-encoder. Non-candidate skills receive a stable low score so downstream reports stay structurally consistent.

### Shared Contrastive Acceptance

Phase 6B's contrastive selective code currently lives inside `routers/gated.py`. Phase 7A should extract the reusable evidence and selection helpers into a small shared module, for example `routers/verification.py`, so both `VerificationGatedRouter` and `CrossEncoderReranker` can use the same acceptance policy.

This is a targeted refactor: public behavior of the gated router must remain unchanged.

### CLI Surface

Extend the CLI without changing existing commands:

- Add `cross-encoder` to `ROUTER_NAMES`.
- Add router specs such as `cross-encoder:sentence-transformers`.
- Add `--cross-encoder-model`, defaulting to `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- Add `--cross-encoder-batch-size`, defaulting to `16`.
- Reuse existing `--embedding-backend`, `--embedding-model`, `--embedding-cache`, `--gated-pool-size`, `--selective`, and contrastive flags.

The comparison command should support labels such as:

```bash
skilleval compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-contrastive=gated:sentence-transformers,cross-encoder-minilm=cross-encoder:sentence-transformers \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache docs/demo/phase7a-cross-encoder/embedding-cache.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --selective \
  --contrastive-selective \
  --output-dir docs/demo/phase7a-cross-encoder
```

Remote GPU runs should prepend:

```bash
CUDA_VISIBLE_DEVICES=3
```

## Data Flow

For each task:

1. Build task text from task id, category, and prompt.
2. Use embedding retrieval to collect `candidate_pool_size` candidates.
3. Build skill text from id, name, category, description, trigger terms, and body.
4. Score `(task text, skill text)` pairs with the cross-encoder.
5. Sort candidates by cross-encoder score, base rank, and skill id.
6. Apply optional contrastive selective filtering.
7. Return up to `top_k` selected skill ids.

This lets Phase 7A measure whether the learned pairwise verifier improves ranking, and whether contrastive filtering remains necessary after learned reranking.

## Hardware and Deployment Safety

Phase 7A uses one GPU only. The run command must set `CUDA_VISIBLE_DEVICES=3` unless a fresh `nvidia-smi` check shows a different idle GPU is safer.

Before a remote run:

```bash
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
```

Safe GPU criteria:

- Low memory usage relative to 80GB, ideally under 1GB.
- Low utilization at the moment of launch.
- No process termination or forced cleanup.

The implementation should not auto-kill processes, call `nvidia-smi --gpu-reset`, or assume exclusive access to all GPUs.

## Testing Strategy

Unit tests should cover the router without loading a real model:

- Candidate pool uses the base router output.
- Cross-encoder scores reorder candidates.
- Tie-breaking is deterministic.
- Selective mode can return fewer than `top_k`.
- Contrastive selective mode reuses Phase 6B acceptance behavior.
- CLI parser accepts `cross-encoder:sentence-transformers` and rejects invalid backends.
- Missing optional dependencies produce the same controlled CLI error style as embedding.

Integration validation should run:

```bash
pytest -q
```

Remote benchmark validation should run on one idle A100:

```bash
CUDA_VISIBLE_DEVICES=3 skilleval compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-contrastive=gated:sentence-transformers,cross-encoder-minilm=cross-encoder:sentence-transformers \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache docs/demo/phase7a-cross-encoder/embedding-cache.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --selective \
  --contrastive-selective \
  --output-dir docs/demo/phase7a-cross-encoder
skilleval analyze-failures --runs docs/demo/phase7a-cross-encoder --baseline gated-minilm-contrastive --candidate cross-encoder-minilm
```

## Expected Outputs

Phase 7A should produce:

- A new `cross-encoder` router implementation.
- CLI options and tests for the new router.
- `docs/demo/phase7a-cross-encoder/results.jsonl` subdirectories for compared routers.
- `docs/demo/phase7a-cross-encoder/comparison.md`.
- `docs/demo/phase7a-cross-encoder/failure-analysis.md`.
- A short Phase 7A summary document describing hardware, command, metrics, and whether cross-encoder reranking beats or trades off against Phase 6B.

## Acceptance Criteria

Phase 7A is complete when all of these are true:

- Existing Phase 6B router behavior remains covered by tests.
- The new cross-encoder router can be unit-tested without GPU or network.
- The CLI can compare `embedding`, `gated`, and `cross-encoder` routers in one command.
- Full local test suite passes.
- A remote benchmark has been run on exactly one idle A100 selected through `CUDA_VISIBLE_DEVICES`.
- The benchmark report includes Recall@1, Recall@5, MRR, NDCG@5, negative hit rate, selection rate, average latency, and failure analysis.
- The documentation states whether the learned reranker is a strict improvement, a quality-latency trade-off, or a negative result.

## Risk Management

The main risk is model availability. The implementation should accept both Hugging Face model ids and local model paths through `--cross-encoder-model`. If the default model cannot be downloaded on the remote machine, the run can use a pre-downloaded local path without code changes.

The second risk is overclaiming. Phase 7A is inference-only; it should be presented as pretrained verifier deployment and benchmark, not model fine-tuning.

The third risk is GPU contention. The deployment command must explicitly pin one idle GPU and avoid multi-GPU launchers.
