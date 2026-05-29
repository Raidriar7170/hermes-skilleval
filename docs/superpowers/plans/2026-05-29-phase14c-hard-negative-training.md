# Phase 14C Hard-Negative Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Phase 14 `browser-local-dashboard` fine-tuned embedding regression by training on exported hard-negative pairs instead of using only positive pairs.

**Architecture:** Keep the existing MultipleNegativesRankingLoss positive-pair training path, then add a second train/dev hard-negative contrastive step that pushes task-labeled negative skills away from the task query. Keep checkpoints and caches on the A100 under `/mnt/data/minghongsun`, and import only JSONL/Markdown evaluation artifacts into the repo.

**Tech Stack:** Python 3.11, pytest, fake `torch`/`sentence_transformers` test doubles, SentenceTransformers `ContrastiveLoss`, A100 CUDA training, existing `judge-finetuned-embedding` regression guard.

---

## File Structure

- Modify `scripts/train_embedding_router.py`
  - Add train/dev hard-negative selection.
  - Add `ContrastiveLoss` hard-negative training steps.
  - Write hard-negative counts in `train-run-summary.json`.
- Modify `tests/test_train_embedding_router_script.py`
  - Add fake hard-negative training rows.
  - Add fake `ContrastiveLoss` and `torch.zeros`.
  - Assert hard-negative steps call backward before optimizer step.
- Modify `src/hermes_skilleval/embedding_training.py`
  - Update train config loss description to include hard-negative contrastive training.
- Modify `tests/test_embedding_training.py`
  - Update config loss assertion.
- Modify `docs/phase14.md`
  - Replace the old limitation that hard negatives are audit-only.
- Regenerate remote Phase 14 model and local eval artifacts:
  - `docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl`
  - `docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl`
  - `docs/demo/phase14-finetuned-embedding-router/regression-summary.json`
  - `docs/demo/phase14-finetuned-embedding-router/comparison.md`

## Task 1: Hard-Negative Training Unit Test

- [ ] **Step 1: Write failing training-script test changes**

Update `tests/test_train_embedding_router_script.py` so the main fake training test includes one `label=0` `dev` row. Assert:

```python
assert summary["trained_pair_count"] == 2
assert summary["trained_hard_negative_pair_count"] == 1
assert summary["hard_negative_optimizer_step_count"] == 1
assert summary["optimizer_step_count"] == 3
assert FakeLossValue.backward_count == 3
```

Add fake `torch.zeros`, fake `ContrastiveLoss`, and a class-level counter for the labels it receives.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_train_embedding_router_script.py::test_train_script_runs_manual_training_loop_with_fake_dependencies -q -p no:cacheprovider
```

Expected: fails because the script does not train hard-negative pairs or write hard-negative summary fields.

- [ ] **Step 3: Implement hard-negative training**

In `scripts/train_embedding_router.py`:

- select `hard_negative_pairs` where `label == 0` and split is `train` or `dev`;
- instantiate `hard_negative_loss = losses.ContrastiveLoss(model)` when rows exist;
- after positive batches, run hard-negative batches with `torch.zeros(len(batch), device=model.device)`;
- call `loss.backward()` before every optimizer step;
- write `trained_hard_negative_pair_count` and `hard_negative_optimizer_step_count`.

- [ ] **Step 4: Run targeted training-script tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_train_embedding_router_script.py -q -p no:cacheprovider
```

Expected: training script tests pass.

## Task 2: Config And Documentation Accuracy

- [ ] **Step 1: Update config loss test**

Change `tests/test_embedding_training.py` to assert:

```python
assert config["loss"] == "MultipleNegativesRankingLoss+ContrastiveLoss"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py::test_build_train_config_keeps_outputs_under_minghongsun_path -q -p no:cacheprovider
```

Expected: fails until `build_train_config` updates the loss string.

- [ ] **Step 3: Update code and docs**

Update `src/hermes_skilleval/embedding_training.py` and `docs/phase14.md` so hard negatives are no longer described as audit-only.

- [ ] **Step 4: Run Phase 14 local tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py tests/test_train_embedding_router_script.py tests/test_phase14_artifacts.py -q -p no:cacheprovider
```

Expected: Phase 14 local tests pass.

## Task 3: Remote Experiment And Artifact Import

- [ ] **Step 1: Sync current worktree to A100 project directory**

Use the existing SSH alias and write only under:

```text
/mnt/data/minghongsun/hermes-skilleval-phase14
```

- [ ] **Step 2: Train hard-negative candidate**

Use the cached base model path:

```text
/mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2
```

Write the candidate model under:

```text
/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

- [ ] **Step 3: Evaluate baseline and candidate**

Use existing `skilleval eval` commands for baseline MiniLM and the fine-tuned candidate over `benchmarks/migration-tasks`.

- [ ] **Step 4: Import eval JSONL and regenerate judge artifacts**

Copy only `results.jsonl` files into the Phase 14 demo directory, then run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase14-finetuned-embedding-router \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

Only mark the roadmap complete if `regression_count == 0`.

## Task 4: Final Verification

- [ ] **Step 1: Run full local verification**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
ruff check .
mypy src tests
python -m pip install -e . --dry-run
git diff --check
```

- [ ] **Step 2: Run sensitive scan**

Scan touched Phase 14 files for private hosts, keys, tokens, `/root`, and local user paths.

- [ ] **Step 3: Report result**

Report whether Phase 14C reached `guard_status == PASS` or remains `REVIEW_REQUIRED`, with exact metric deltas and remaining task-level flags.
