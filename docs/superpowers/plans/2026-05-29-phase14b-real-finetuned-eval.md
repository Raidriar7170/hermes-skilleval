# Phase 14B Real Fine-Tuned Embedding Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Phase 14 fine-tuned embedding router evidence gap with local hardening and, when A100 access is available, real model training and regression-guarded evaluation.

**Architecture:** Keep local repository artifacts separate from remote model outputs. Local code validates that Phase 14 training/eval paths stay under `/mnt/data/minghongsun`, keeps README counts current, and only commits fine-tuned evaluation artifacts after a real SentenceTransformer model path has produced candidate results. Remote checkpoints, caches, logs, and downloaded models remain outside the repo.

**Tech Stack:** Python 3.11, pytest, ruff, mypy, existing `skilleval` CLI, `sentence-transformers` on the A100 machine, JSONL/Markdown artifacts.

---

## File Structure

- Modify `README.md`
  - Keep test-count claims aligned with the verified local suite.
- Create `src/hermes_skilleval/remote_paths.py`
  - Own canonical validation for user-owned A100 paths.
- Modify `src/hermes_skilleval/embedding_training.py`
  - Reuse canonical A100 output path validation for train config generation.
- Modify `src/hermes_skilleval/finetuned_eval.py`
  - Reuse canonical A100 model path validation before importing eval summaries.
- Modify `scripts/train_embedding_router.py`
  - Reuse equivalent resolved-path validation for direct script execution.
- Modify `tests/test_embedding_training.py`
  - Add traversal regression coverage for train config output paths.
- Modify `tests/test_finetuned_eval.py`
  - Add traversal regression coverage for fine-tuned model paths.
- Modify `tests/test_phase14_artifacts.py`
  - Guard README test-count snippets and Phase 14 roadmap state.
- Create or import only after real A100 evaluation:
  - `docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl`
  - `docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl`
  - `docs/demo/phase14-finetuned-embedding-router/regression-summary.json`
  - `docs/demo/phase14-finetuned-embedding-router/comparison.md`

## Task 1: README Evidence Count Hygiene

- [ ] **Step 1: Write the failing README artifact test**

Add assertions to `tests/test_phase14_artifacts.py`:

```python
def test_readme_test_counts_match_verified_suite_size():
    readme = README.read_text(encoding="utf-8")

    assert "| Test cases | 214 |" in readme
    assert "214 passed" in readme
    assert "211 passed" not in readme
    assert "| Test cases | 199 |" not in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase14_artifacts.py::test_readme_test_counts_match_verified_suite_size -q -p no:cacheprovider
```

Expected: fails because README still contains stale count snippets.

- [ ] **Step 3: Update README counts**

Change the benchmark scale table from `199` to `214`, and the expected pytest snippet from `211 passed` to `214 passed`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase14_artifacts.py::test_readme_test_counts_match_verified_suite_size -q -p no:cacheprovider
```

Expected: one test passes.

## Task 2: Canonical A100 Path Validation

- [ ] **Step 1: Write failing traversal tests**

Add to `tests/test_embedding_training.py`:

```python
def test_build_train_config_rejects_traversal_outside_minghongsun_path():
    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        build_train_config(
            training_pairs="training-pairs.jsonl",
            output_dir="/mnt/data/minghongsun/../leak/model",
            base_model="sentence-transformers/all-MiniLM-L6-v2",
            epochs=1,
            batch_size=16,
            learning_rate=2e-5,
            seed=7170,
        )
```

Add to `tests/test_finetuned_eval.py`:

```python
def test_write_finetuned_eval_summary_rejects_model_dir_traversal(tmp_path: Path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline.write_text(json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0)) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(_record(selected=["gold"], recall=1.0, negative_hit=0.0)) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="/mnt/data/minghongsun"):
        write_finetuned_eval_summary(
            baseline_results_path=baseline,
            candidate_results_path=candidate,
            output_dir=tmp_path / "phase14",
            baseline_router="embedding-minilm",
            candidate_router="finetuned-embedding",
            model_dir="/mnt/data/minghongsun/../leak/model",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py::test_build_train_config_rejects_traversal_outside_minghongsun_path tests/test_finetuned_eval.py::test_write_finetuned_eval_summary_rejects_model_dir_traversal -q -p no:cacheprovider
```

Expected: tests fail because current library checks use raw string prefixes.

- [ ] **Step 3: Implement shared validator**

Create `src/hermes_skilleval/remote_paths.py`:

```python
from __future__ import annotations

from pathlib import Path


A100_USER_ROOT = Path("/mnt/data/minghongsun")


def validate_a100_user_path(path: str, *, field: str) -> str:
    allowed_root = A100_USER_ROOT.resolve(strict=False)
    resolved_path = Path(path).resolve(strict=False)
    try:
        resolved_path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"{field} must be under /mnt/data/minghongsun/"
        ) from exc
    return str(resolved_path)
```

Use it in `embedding_training.build_train_config` and `finetuned_eval.write_finetuned_eval_summary`.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py tests/test_finetuned_eval.py tests/test_phase14_artifacts.py -q -p no:cacheprovider
```

Expected: targeted Phase 14 tests pass.

## Task 3: Remote Training And Evaluation Attempt

- [ ] **Step 1: Probe SSH aliases without exposing hosts**

Run a local check that lists configured SSH host aliases only. Do not print host names, IPs, keys, or tokens in docs.

- [ ] **Step 2: If an A100 alias is available, create the remote project directory**

Use only paths under:

```text
/mnt/data/minghongsun/hermes-skilleval-phase14
```

- [ ] **Step 3: Sync source or run from existing remote checkout**

Keep source, venv, caches, checkpoints, and logs under `/mnt/data/minghongsun/hermes-skilleval-phase14`.

- [ ] **Step 4: Train**

Run:

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

Expected: writes a model and `train-run-summary.json` outside the repo under the configured A100 output path.

- [ ] **Step 5: Evaluate baseline and candidate**

Run baseline:

```bash
skilleval eval \
  --index docs/demo/phase9-real-skill-library-migration/skills.json \
  --tasks benchmarks/migration-tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --top-k 5 \
  --output-dir /mnt/data/minghongsun/hermes-skilleval-phase14/eval/baseline
```

Run candidate:

```bash
skilleval eval \
  --index docs/demo/phase9-real-skill-library-migration/skills.json \
  --tasks benchmarks/migration-tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --top-k 5 \
  --output-dir /mnt/data/minghongsun/hermes-skilleval-phase14/eval/finetuned
```

- [ ] **Step 6: Import eval artifacts only if real outputs exist**

Copy only `results.jsonl` files into:

```text
docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl
docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl
```

Then run:

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase14-finetuned-embedding-router \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

Do not mark the roadmap complete unless `regression-summary.json` exists and the guard supports the claim.

## Task 4: Verification And Reporting

- [ ] **Step 1: Run local verification**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
ruff check .
mypy src tests
python -m pip install -e . --dry-run
git diff --check
```

- [ ] **Step 2: Sensitive scan touched artifacts**

Run a targeted scan for private hosts, keys, tokens, `/root`, and local user paths over touched files and Phase 14 artifacts.

- [ ] **Step 3: Report final state**

Report whether Phase 14B is:

- `local-hardening-complete`
- `remote-training-complete`
- `remote-training-blocked`
- `eval-artifacts-imported`

Include exact verification outputs and any blocker without leaking remote host details.
