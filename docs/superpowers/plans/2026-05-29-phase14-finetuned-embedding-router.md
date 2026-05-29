# Phase 14 Fine-Tuned Embedding Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible fine-tuned embedding-router evaluation path for Hermes-style skill routing without committing model checkpoints or overstating results.

**Architecture:** Phase 14 separates local, deterministic repository work from GPU training work. The repo exports audited task-skill training pairs, writes a remote-ready training config and script, evaluates a fine-tuned SentenceTransformer model path when one exists, and imports only metrics/artifacts into `docs/demo/phase14-finetuned-embedding-router/`. The README roadmap must stay incomplete until a real fine-tuned model evaluation artifact exists.

**Tech Stack:** Python 3.11, existing `BenchmarkTask`/`Skill` models, `load_tasks`, `load_skill_index`, existing `EmbeddingRouter` with `SentenceTransformerEmbeddingModel`, existing router metrics, optional `sentence-transformers` for remote training, pytest, JSONL/Markdown artifacts.

**Execution status:** Local repository infrastructure is implemented: training
pair export, train config, remote training script, fine-tuned evaluation guard,
Phase 14 docs, and local training-data artifacts. Real model training and
fine-tuned evaluation remain gated on A100/optional dependency execution; do not
mark the README roadmap item complete until `finetuned-results.jsonl` and
`regression-summary.json` exist from a real model path and pass validation.

---

## Scope And Evidence Boundary

Phase 14 is allowed to add:

- training-data export from existing benchmark and migration task labels;
- hard-negative construction from task `negative_skills` and prior failure artifacts;
- a remote-ready A100 training script that writes checkpoints outside the repo;
- CLI support for exporting data and evaluating a fine-tuned model path;
- committed evaluation artifacts only after a real model path has been evaluated.

Phase 14 must not:

- commit model checkpoints, embedding caches, tensorboard logs, or downloaded models;
- write outside `/mnt/data/minghongsun/<project>` on the A100 machine;
- claim SOTA, standard benchmark status, industry benchmark status, or production readiness;
- mark the README fine-tuned roadmap item complete before `finetuned-results.jsonl` and `regression-summary.json` exist and pass validation;
- fabricate a fine-tuned run by using the hashing backend or a fake model.

---

## File Structure

- Create `src/hermes_skilleval/embedding_training.py`
  - Owns training-pair export, split leakage checks, pair summary, train config payload, and model-card skeleton rendering.
- Create `src/hermes_skilleval/finetuned_eval.py`
  - Owns before/after route comparison for baseline embedding versus fine-tuned embedding results.
- Create `scripts/train_embedding_router.py`
  - Runs optional `sentence-transformers` training from exported JSONL pairs. This script is remote-ready and writes all training outputs to an explicit `--output-dir`.
- Modify `src/hermes_skilleval/cli.py`
  - Adds `export-embedding-training-data`.
  - Adds `judge-finetuned-embedding`.
  - Reuses existing `eval --router embedding --embedding-backend sentence-transformers --embedding-model <path>` for actual model evaluation.
- Create `tests/test_embedding_training.py`
  - Unit tests for pair export, hard-negative construction, split leakage guard, and config payload.
- Create `tests/test_finetuned_eval.py`
  - Unit tests for before/after regression summary and artifact writing.
- Modify `tests/test_cli_smoke.py`
  - Adds CLI smoke tests for the new export and judge commands.
- Create `tests/test_phase14_artifacts.py`
  - Guards committed Phase 14 artifacts and README/docs wording.
- Create `docs/phase14.md`
  - Documents local export, A100 training, model evaluation, import rules, and result interpretation.
- Create `docs/demo/phase14-finetuned-embedding-router/`
  - `training-pairs.jsonl`
  - `training-summary.json`
  - `train-config.json`
  - `model-card.md`
  - `baseline-results.jsonl`
  - `finetuned-results.jsonl`
  - `regression-summary.json`
  - `comparison.md`
- Modify `README.md`
  - Adds Phase 14 docs link and CLI snippets.
  - Updates test count.
  - Marks the fine-tuned roadmap item complete only after real fine-tuned artifacts pass.

---

## Artifact Contract

### `training-pairs.jsonl`

Each line is a JSON object:

```json
{
  "pair_id": "migration/browser-local-dashboard/positive/browser-smoke-testing",
  "task_id": "browser-local-dashboard",
  "split": "train",
  "query_text": "browser-local-dashboard browser ...",
  "skill_id": "browser-smoke-testing",
  "skill_text": "browser-smoke-testing Browser Smoke Testing ...",
  "label": 1,
  "pair_type": "positive",
  "source": "gold_skill"
}
```

### `training-summary.json`

Required fields:

```json
{
  "phase": "Phase 14",
  "artifact_type": "phase14-embedding-training-data",
  "pair_count": 0,
  "task_count": 0,
  "skill_count": 0,
  "pairs_by_split": {},
  "pairs_by_type": {},
  "positive_count": 0,
  "hard_negative_count": 0,
  "leakage_guard": "PASS",
  "input_paths": {}
}
```

### `train-config.json`

Required fields:

```json
{
  "phase": "Phase 14",
  "base_model": "sentence-transformers/all-MiniLM-L6-v2",
  "training_pairs": "docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl",
  "output_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
  "epochs": 1,
  "batch_size": 16,
  "learning_rate": 0.00002,
  "loss": "MultipleNegativesRankingLoss",
  "seed": 7170
}
```

### `regression-summary.json`

Required fields:

```json
{
  "phase": "Phase 14",
  "artifact_type": "phase14-finetuned-embedding-eval",
  "baseline_router": "embedding-minilm",
  "candidate_router": "finetuned-embedding",
  "task_count": 0,
  "guard_status": "PASS",
  "baseline_mean_metrics": {},
  "candidate_mean_metrics": {},
  "metric_deltas": {},
  "regression_count": 0,
  "improvement_count": 0,
  "model_checkpoint_committed": false
}
```

---

## Task 1: Training Pair Export Module

**Files:**
- Create: `src/hermes_skilleval/embedding_training.py`
- Test: `tests/test_embedding_training.py`

- [ ] **Step 1: Write the failing positive and hard-negative export test**

```python
from hermes_skilleval.embedding_training import export_embedding_training_pairs
from hermes_skilleval.models import BenchmarkTask, Skill


def test_export_embedding_training_pairs_includes_gold_and_hard_negative_pairs():
    task = BenchmarkTask(
        id="browser-local-dashboard",
        category="browser-gui",
        difficulty="medium",
        prompt="Open the static HTML dashboard and verify that it is nonblank.",
        gold_skills=["browser-smoke-testing"],
        negative_skills=["systematic-debugging"],
        verifier="manual",
        split="train",
        robustness_tags=["migration"],
    )
    skills = [
        Skill(
            id="browser-smoke-testing",
            name="Browser Smoke Testing",
            path="skills/browser-smoke-testing/SKILL.md",
            category="browser-gui",
            description="Open a local web target and verify rendering.",
            body="# Browser Smoke Testing",
            trigger_terms=["browser", "dashboard"],
            token_count_estimate=10,
        ),
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="skills/systematic-debugging/SKILL.md",
            category="superpowers",
            description="Investigate bugs before changing code.",
            body="# Systematic Debugging",
            trigger_terms=["debug", "failure"],
            token_count_estimate=10,
        ),
    ]

    pairs, summary = export_embedding_training_pairs(
        tasks=[task],
        skills=skills,
        input_paths={"tasks": "fixture/tasks", "skills_index": "fixture/skills.json"},
    )

    assert [pair["pair_type"] for pair in pairs] == ["positive", "hard_negative"]
    assert pairs[0]["label"] == 1
    assert pairs[0]["skill_id"] == "browser-smoke-testing"
    assert pairs[1]["label"] == 0
    assert pairs[1]["skill_id"] == "systematic-debugging"
    assert summary["positive_count"] == 1
    assert summary["hard_negative_count"] == 1
    assert summary["leakage_guard"] == "PASS"
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py::test_export_embedding_training_pairs_includes_gold_and_hard_negative_pairs -q -p no:cacheprovider
```

Expected: fails because `hermes_skilleval.embedding_training` does not exist.

- [ ] **Step 3: Implement minimal exporter**

Create `src/hermes_skilleval/embedding_training.py` with:

```python
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from hermes_skilleval.models import BenchmarkTask, Skill


def export_embedding_training_pairs(
    *,
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    input_paths: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    skill_by_id = {skill.id: skill for skill in skills}
    pairs: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda item: item.id):
        for skill_id in task.gold_skills:
            pairs.append(_pair(task, skill_by_id, skill_id, label=1, pair_type="positive", source="gold_skill"))
        for skill_id in task.negative_skills:
            if skill_id in skill_by_id:
                pairs.append(_pair(task, skill_by_id, skill_id, label=0, pair_type="hard_negative", source="negative_skill"))
    summary = _summary(tasks, skills, pairs, input_paths)
    return pairs, summary


def write_training_pairs(
    pairs: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    pairs_path: Path | str,
    summary_path: Path | str,
) -> None:
    pairs_output = Path(pairs_path)
    summary_output = Path(summary_path)
    pairs_output.parent.mkdir(parents=True, exist_ok=True)
    pairs_output.write_text(
        "".join(json.dumps(pair, sort_keys=True) + "\n" for pair in pairs),
        encoding="utf-8",
    )
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pair(
    task: BenchmarkTask,
    skill_by_id: dict[str, Skill],
    skill_id: str,
    *,
    label: int,
    pair_type: str,
    source: str,
) -> dict[str, Any]:
    if skill_id not in skill_by_id:
        raise ValueError(f"task {task.id} references missing skill: {skill_id}")
    skill = skill_by_id[skill_id]
    return {
        "pair_id": f"{task.id}/{pair_type}/{skill_id}",
        "task_id": task.id,
        "split": task.split,
        "query_text": _task_text(task),
        "skill_id": skill.id,
        "skill_text": _skill_text(skill),
        "label": label,
        "pair_type": pair_type,
        "source": source,
    }


def _summary(
    tasks: list[BenchmarkTask],
    skills: list[Skill],
    pairs: list[dict[str, Any]],
    input_paths: dict[str, str],
) -> dict[str, Any]:
    pairs_by_split = Counter(str(pair["split"]) for pair in pairs)
    pairs_by_type = Counter(str(pair["pair_type"]) for pair in pairs)
    positive_count = sum(1 for pair in pairs if int(pair["label"]) == 1)
    hard_negative_count = sum(1 for pair in pairs if int(pair["label"]) == 0)
    return {
        "phase": "Phase 14",
        "artifact_type": "phase14-embedding-training-data",
        "pair_count": len(pairs),
        "task_count": len(tasks),
        "skill_count": len(skills),
        "pairs_by_split": dict(sorted(pairs_by_split.items())),
        "pairs_by_type": dict(sorted(pairs_by_type.items())),
        "positive_count": positive_count,
        "hard_negative_count": hard_negative_count,
        "leakage_guard": _leakage_guard(tasks),
        "input_paths": input_paths,
    }


def _leakage_guard(tasks: list[BenchmarkTask]) -> str:
    task_ids_by_split: dict[str, set[str]] = {}
    for task in tasks:
        task_ids_by_split.setdefault(task.split, set()).add(task.id)
    train_ids = task_ids_by_split.get("train", set()) | task_ids_by_split.get("dev", set())
    test_ids = task_ids_by_split.get("test", set())
    return "PASS" if not (train_ids & test_ids) else "FAIL"


def _task_text(task: BenchmarkTask) -> str:
    return " ".join([task.id.replace("-", " "), task.category, task.difficulty, task.prompt])


def _skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.id.replace("-", " "),
            skill.name,
            skill.category or "",
            skill.description,
            " ".join(skill.trigger_terms),
            skill.body,
        ]
    )
```

- [ ] **Step 4: Run exporter tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py -q -p no:cacheprovider
```

Expected: exporter tests pass.

---

## Task 2: Export CLI And Committed Training Data

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`
- Create: `docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl`
- Create: `docs/demo/phase14-finetuned-embedding-router/training-summary.json`

- [ ] **Step 1: Write the failing CLI smoke test**

Add this test to `tests/test_cli_smoke.py`:

```python
def test_cli_export_embedding_training_data_writes_pairs(tmp_path):
    tasks = tmp_path / "tasks"
    task_dir = tasks / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "task-001",
                "category": "browser-gui",
                "difficulty": "medium",
                "gold_skills": ["browser-smoke-testing"],
                "negative_skills": ["systematic-debugging"],
                "verifier": "manual",
                "split": "train",
                "robustness_tags": ["phase14"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "Open the local dashboard and verify it is nonblank.",
        encoding="utf-8",
    )
    skills_index = tmp_path / "skills.json"
    skills_index.write_text(
        json.dumps(
            [
                {
                    "id": "browser-smoke-testing",
                    "name": "Browser Smoke Testing",
                    "path": "skills/browser-smoke-testing/SKILL.md",
                    "category": "browser-gui",
                    "description": "Open local dashboards.",
                    "body": "# Browser Smoke Testing",
                    "trigger_terms": ["browser", "dashboard"],
                    "token_count_estimate": 10,
                },
                {
                    "id": "systematic-debugging",
                    "name": "Systematic Debugging",
                    "path": "skills/systematic-debugging/SKILL.md",
                    "category": "superpowers",
                    "description": "Investigate bugs.",
                    "body": "# Systematic Debugging",
                    "trigger_terms": ["debug"],
                    "token_count_estimate": 10,
                },
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase14"

    result = main(
        [
            "export-embedding-training-data",
            "--tasks",
            str(tasks),
            "--skills-index",
            str(skills_index),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "training-pairs.jsonl").exists()
    assert (output_dir / "training-summary.json").exists()
```

- [ ] **Step 2: Run CLI smoke test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_export_embedding_training_data_writes_pairs -q -p no:cacheprovider
```

Expected: fails because `export-embedding-training-data` is not registered.

- [ ] **Step 3: Add CLI parser and handler**

Modify `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.embedding_training import (
    export_embedding_training_pairs,
    write_training_pairs,
)
```

Register:

```python
export_training_parser = subparsers.add_parser(
    "export-embedding-training-data",
    help="export task-skill pairs for supervised embedding-router training",
)
export_training_parser.add_argument("--tasks", required=True)
export_training_parser.add_argument("--skills-index", required=True)
export_training_parser.add_argument("--output-dir", required=True)
export_training_parser.set_defaults(handler=_run_export_embedding_training_data)
```

Handler:

```python
def _run_export_embedding_training_data(args: argparse.Namespace) -> None:
    tasks = load_tasks(args.tasks)
    skills = load_skill_index(args.skills_index)
    pairs, summary = export_embedding_training_pairs(
        tasks=tasks,
        skills=skills,
        input_paths={"tasks": args.tasks, "skills_index": args.skills_index},
    )
    output_dir = ensure_dir(args.output_dir)
    write_training_pairs(
        pairs,
        summary,
        pairs_path=output_dir / "training-pairs.jsonl",
        summary_path=output_dir / "training-summary.json",
    )
    print(f"Wrote {summary['pair_count']} embedding training pairs to {output_dir}")
```

- [ ] **Step 4: Generate committed training data**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m hermes_skilleval.cli export-embedding-training-data \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase14-finetuned-embedding-router
```

Expected: writes `training-pairs.jsonl` and `training-summary.json`.

- [ ] **Step 5: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py tests/test_cli_smoke.py::test_cli_export_embedding_training_data_writes_pairs -q -p no:cacheprovider
```

Expected: pass.

---

## Task 3: Train Config And Remote Training Script

**Files:**
- Modify: `src/hermes_skilleval/embedding_training.py`
- Create: `scripts/train_embedding_router.py`
- Modify: `tests/test_embedding_training.py`
- Create: `docs/demo/phase14-finetuned-embedding-router/train-config.json`

- [ ] **Step 1: Write the failing train-config test**

Add to `tests/test_embedding_training.py`:

```python
from hermes_skilleval.embedding_training import build_train_config


def test_build_train_config_keeps_outputs_under_minghongsun_path():
    config = build_train_config(
        training_pairs="docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl",
        output_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        epochs=1,
        batch_size=16,
        learning_rate=2e-5,
        seed=7170,
    )

    assert config["phase"] == "Phase 14"
    assert config["output_dir"].startswith("/mnt/data/minghongsun/")
    assert config["loss"] == "MultipleNegativesRankingLoss"
    assert config["model_checkpoint_committed"] is False
```

- [ ] **Step 2: Run train-config test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_embedding_training.py::test_build_train_config_keeps_outputs_under_minghongsun_path -q -p no:cacheprovider
```

Expected: fails because `build_train_config` does not exist.

- [ ] **Step 3: Implement config builder**

Add to `embedding_training.py`:

```python
def build_train_config(
    *,
    training_pairs: str,
    output_dir: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
) -> dict[str, Any]:
    if not output_dir.startswith("/mnt/data/minghongsun/"):
        raise ValueError("A100 training output_dir must be under /mnt/data/minghongsun/")
    return {
        "phase": "Phase 14",
        "base_model": base_model,
        "training_pairs": training_pairs,
        "output_dir": output_dir,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "loss": "MultipleNegativesRankingLoss",
        "seed": seed,
        "model_checkpoint_committed": False,
    }


def write_train_config(config: dict[str, Any], output_path: Path | str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Add remote training script**

Create `scripts/train_embedding_router.py`:

```python
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a SentenceTransformer skill router model.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not str(config["output_dir"]).startswith("/mnt/data/minghongsun/"):
        raise SystemExit("output_dir must be under /mnt/data/minghongsun/")
    try:
        from sentence_transformers import InputExample, SentenceTransformer, losses
        from torch.utils.data import DataLoader
    except (ImportError, ModuleNotFoundError) as exc:
        raise SystemExit(
            "sentence-transformers and torch are required on the training machine; "
            "install the repo with: python -m pip install -e '.[embedding]'"
        ) from exc

    random.seed(int(config["seed"]))
    pairs = [
        json.loads(line)
        for line in Path(config["training_pairs"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    positive_pairs = [pair for pair in pairs if int(pair["label"]) == 1 and pair["split"] in {"train", "dev"}]
    if not positive_pairs:
        raise SystemExit("no positive train/dev pairs found")
    train_examples = [
        InputExample(texts=[pair["query_text"], pair["skill_text"]])
        for pair in positive_pairs
    ]
    model = SentenceTransformer(config["base_model"])
    train_loader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=int(config["batch_size"]),
    )
    train_loss = losses.MultipleNegativesRankingLoss(model)
    model.fit(
        train_objectives=[(train_loader, train_loss)],
        epochs=int(config["epochs"]),
        warmup_steps=0,
        optimizer_params={"lr": float(config["learning_rate"])},
        show_progress_bar=True,
    )
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save(str(output_dir))
    (output_dir / "train-run-summary.json").write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "trained_pair_count": len(train_examples),
                "base_model": config["base_model"],
                "output_dir": str(output_dir),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Write committed train config**

Use a CLI handler or a focused Python invocation to write:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
from hermes_skilleval.embedding_training import build_train_config, write_train_config

config = build_train_config(
    training_pairs="docs/demo/phase14-finetuned-embedding-router/training-pairs.jsonl",
    output_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
    base_model="sentence-transformers/all-MiniLM-L6-v2",
    epochs=1,
    batch_size=16,
    learning_rate=2e-5,
    seed=7170,
)
write_train_config(config, "docs/demo/phase14-finetuned-embedding-router/train-config.json")
PY
```

Expected: `train-config.json` exists and contains no private host, IP, password, token, or checkpoint bytes.

---

## Task 4: Fine-Tuned Evaluation Guard

**Files:**
- Create: `src/hermes_skilleval/finetuned_eval.py`
- Modify: `src/hermes_skilleval/cli.py`
- Create: `tests/test_finetuned_eval.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write the failing evaluation summary test**

Create `tests/test_finetuned_eval.py`:

```python
import json
from pathlib import Path

from hermes_skilleval.finetuned_eval import write_finetuned_eval_summary


def test_write_finetuned_eval_summary_flags_negative_hit_regression(tmp_path: Path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "category": "browser-gui",
                "difficulty": "medium",
                "split": "test",
                "robustness_tags": ["phase14"],
                "selected_skill_ids": ["gold"],
                "gold_skills": ["gold"],
                "negative_skills": ["bad"],
                "recall_at_5": 1.0,
                "mrr": 1.0,
                "ndcg_at_5": 1.0,
                "negative_hit_rate": 0.0,
                "negative_accepted_rate": 0.0,
                "selection_rate_at_5": 0.2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "task_id": "task-001",
                "category": "browser-gui",
                "difficulty": "medium",
                "split": "test",
                "robustness_tags": ["phase14"],
                "selected_skill_ids": ["bad"],
                "gold_skills": ["gold"],
                "negative_skills": ["bad"],
                "recall_at_5": 0.0,
                "mrr": 0.0,
                "ndcg_at_5": 0.0,
                "negative_hit_rate": 1.0,
                "negative_accepted_rate": 1.0,
                "selection_rate_at_5": 0.2,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = write_finetuned_eval_summary(
        baseline_results_path=baseline,
        candidate_results_path=candidate,
        output_dir=tmp_path / "phase14",
        baseline_router="embedding-minilm",
        candidate_router="finetuned-embedding",
        model_dir="/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
    )

    assert summary["guard_status"] == "REVIEW_REQUIRED"
    assert summary["regression_count"] == 1
    assert summary["model_checkpoint_committed"] is False
    assert (tmp_path / "phase14" / "regression-summary.json").exists()
    assert (tmp_path / "phase14" / "comparison.md").exists()
```

- [ ] **Step 2: Run evaluation test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_finetuned_eval.py::test_write_finetuned_eval_summary_flags_negative_hit_regression -q -p no:cacheprovider
```

Expected: fails because `hermes_skilleval.finetuned_eval` does not exist.

- [ ] **Step 3: Implement evaluation summary**

Create `src/hermes_skilleval/finetuned_eval.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_skilleval.skill_patch_simulation import compare_route_records


METRIC_FIELDS = (
    "recall_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "negative_accepted_rate",
    "selection_rate_at_5",
)


def write_finetuned_eval_summary(
    *,
    baseline_results_path: Path | str,
    candidate_results_path: Path | str,
    output_dir: Path | str,
    baseline_router: str,
    candidate_router: str,
    model_dir: str,
) -> dict[str, Any]:
    baseline_records = _read_jsonl(baseline_results_path)
    candidate_records = _read_jsonl(candidate_results_path)
    diffs = compare_route_records(baseline_records, candidate_records)
    baseline_metrics = _mean_metrics(baseline_records)
    candidate_metrics = _mean_metrics(candidate_records)
    summary = {
        "phase": "Phase 14",
        "artifact_type": "phase14-finetuned-embedding-eval",
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "model_dir": model_dir,
        "model_checkpoint_committed": False,
        "task_count": len(candidate_records),
        "baseline_mean_metrics": baseline_metrics,
        "candidate_mean_metrics": candidate_metrics,
        "metric_deltas": {
            field: round(candidate_metrics[field] - baseline_metrics[field], 6)
            for field in METRIC_FIELDS
        },
        "regression_count": sum(1 for diff in diffs if diff["regression_flags"]),
        "improvement_count": sum(1 for diff in diffs if diff["improvement_flags"]),
    }
    summary["guard_status"] = "PASS" if summary["regression_count"] == 0 else "REVIEW_REQUIRED"
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "comparison.md").write_text(_report(summary, diffs), encoding="utf-8")
    return summary


def _read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mean_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    return {
        field: round(sum(float(record[field]) for record in records) / len(records), 6)
        for field in METRIC_FIELDS
    }


def _report(summary: dict[str, Any], diffs: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 14 Fine-Tuned Embedding Router Evaluation",
        "",
        f"- Baseline: `{summary['baseline_router']}`",
        f"- Candidate: `{summary['candidate_router']}`",
        f"- Guard status: {summary['guard_status']}",
        f"- Model checkpoint committed: {summary['model_checkpoint_committed']}",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    for field in METRIC_FIELDS:
        lines.append(
            f"| {field} | {summary['baseline_mean_metrics'][field]:.6f} | "
            f"{summary['candidate_mean_metrics'][field]:.6f} | "
            f"{summary['metric_deltas'][field]:+.6f} |"
        )
    flagged = [diff for diff in diffs if diff["regression_flags"] or diff["improvement_flags"]]
    lines.extend(["", "## Guard Flags", ""])
    if not flagged:
        lines.append("No per-task regression or improvement flags were observed.")
    else:
        lines.extend(["| Task | Regression Flags | Improvement Flags |", "|---|---|---|"])
        for diff in flagged:
            lines.append(
                "| "
                f"{diff['task_id']} | "
                f"{', '.join(diff['regression_flags']) or '-'} | "
                f"{', '.join(diff['improvement_flags']) or '-'} |"
            )
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Add CLI handler**

Register:

```python
judge_finetuned_parser = subparsers.add_parser(
    "judge-finetuned-embedding",
    help="compare fine-tuned embedding results against a baseline embedding run",
)
judge_finetuned_parser.add_argument("--baseline-results", required=True)
judge_finetuned_parser.add_argument("--candidate-results", required=True)
judge_finetuned_parser.add_argument("--output-dir", required=True)
judge_finetuned_parser.add_argument("--baseline-router", default="embedding-minilm")
judge_finetuned_parser.add_argument("--candidate-router", default="finetuned-embedding")
judge_finetuned_parser.add_argument("--model-dir", required=True)
judge_finetuned_parser.set_defaults(handler=_run_judge_finetuned_embedding)
```

Handler:

```python
def _run_judge_finetuned_embedding(args: argparse.Namespace) -> None:
    summary = write_finetuned_eval_summary(
        baseline_results_path=args.baseline_results,
        candidate_results_path=args.candidate_results,
        output_dir=args.output_dir,
        baseline_router=args.baseline_router,
        candidate_router=args.candidate_router,
        model_dir=args.model_dir,
    )
    print(
        "Wrote fine-tuned embedding evaluation to "
        f"{args.output_dir}: {summary['guard_status']}"
    )
```

- [ ] **Step 5: Add judge CLI smoke test**

Add to `tests/test_cli_smoke.py`:

```python
def test_cli_judge_finetuned_embedding_writes_summary(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    record = {
        "task_id": "task-001",
        "category": "browser-gui",
        "difficulty": "medium",
        "split": "test",
        "robustness_tags": ["phase14"],
        "selected_skill_ids": ["gold"],
        "gold_skills": ["gold"],
        "negative_skills": ["bad"],
        "recall_at_5": 1.0,
        "mrr": 1.0,
        "ndcg_at_5": 1.0,
        "negative_hit_rate": 0.0,
        "negative_accepted_rate": 0.0,
        "selection_rate_at_5": 0.2,
    }
    baseline.write_text(json.dumps(record) + "\n", encoding="utf-8")
    candidate.write_text(json.dumps(record) + "\n", encoding="utf-8")
    output_dir = tmp_path / "phase14"

    result = main(
        [
            "judge-finetuned-embedding",
            "--baseline-results",
            str(baseline),
            "--candidate-results",
            str(candidate),
            "--output-dir",
            str(output_dir),
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
        ]
    )

    assert result == 0
    assert (output_dir / "regression-summary.json").exists()
    assert (output_dir / "comparison.md").exists()
```

- [ ] **Step 6: Run evaluation tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest \
  tests/test_finetuned_eval.py \
  tests/test_cli_smoke.py::test_cli_judge_finetuned_embedding_writes_summary \
  -q -p no:cacheprovider
```

Expected: pass.

---

## Task 5: Real Model Evaluation Procedure

**Files:**
- Create or update: `docs/phase14.md`
- Create or update: `docs/demo/phase14-finetuned-embedding-router/model-card.md`
- Create after actual evaluation: `docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl`
- Create after actual evaluation: `docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl`
- Create after actual evaluation: `docs/demo/phase14-finetuned-embedding-router/regression-summary.json`
- Create after actual evaluation: `docs/demo/phase14-finetuned-embedding-router/comparison.md`

- [ ] **Step 1: Run baseline embedding evaluation locally**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m hermes_skilleval.cli eval \
  --index docs/demo/phase9-real-skill-library-migration/skills.json \
  --tasks benchmarks/migration-tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --top-k 5 \
  --output-dir docs/demo/phase14-finetuned-embedding-router/baseline
```

Expected when optional dependencies and model access are available: writes `baseline/results.jsonl`. If optional dependencies are unavailable locally, do not fabricate baseline results; record the blocker and run this command on the A100 environment after installing `.[embedding]`.

- [ ] **Step 2: Train model on A100**

Run on the A100 machine from the project checkout under `/mnt/data/minghongsun/hermes-skilleval-phase14`:

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

Expected: writes the model directory configured by `train-config.json`. Do not copy the model directory into the repository.

- [ ] **Step 3: Evaluate fine-tuned model path**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m hermes_skilleval.cli eval \
  --index docs/demo/phase9-real-skill-library-migration/skills.json \
  --tasks benchmarks/migration-tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --top-k 5 \
  --output-dir docs/demo/phase14-finetuned-embedding-router/finetuned
```

Expected: writes `finetuned/results.jsonl`. The output can be copied back into the repo as `finetuned-results.jsonl` only after confirming it contains no private path, host, IP, token, or checkpoint data.

- [ ] **Step 4: Write fine-tuned comparison artifacts**

Run:

```bash
cp docs/demo/phase14-finetuned-embedding-router/baseline/results.jsonl \
  docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl
cp docs/demo/phase14-finetuned-embedding-router/finetuned/results.jsonl \
  docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m hermes_skilleval.cli judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase14-finetuned-embedding-router \
  --baseline-router embedding-minilm \
  --candidate-router finetuned-embedding \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

Expected: writes `regression-summary.json` and `comparison.md`.

- [ ] **Step 5: Write model card**

Create `docs/demo/phase14-finetuned-embedding-router/model-card.md`:

```markdown
# Phase 14 Fine-Tuned Embedding Router Model Card

## Scope

This artifact records a domain-specific SentenceTransformer fine-tuning run for
Hermes-style skill routing. The model checkpoint is not committed to this repo.

## Training Data

- Source: `training-pairs.jsonl`
- Labels: gold skill positives and task negative hard negatives
- Split policy: train/dev pairs for training, test pairs held out for reporting

## Training Command

```bash
python scripts/train_embedding_router.py \
  --config docs/demo/phase14-finetuned-embedding-router/train-config.json
```

## Evaluation

The committed comparison uses `baseline-results.jsonl`,
`finetuned-results.jsonl`, and `regression-summary.json`.

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It is not a standard
external benchmark and does not establish SOTA.
```

---

## Task 6: Phase 14 Docs And Artifact Guards

**Files:**
- Create: `docs/phase14.md`
- Create: `tests/test_phase14_artifacts.py`
- Modify: `README.md`

- [ ] **Step 1: Write artifact guard test before docs update**

Create `tests/test_phase14_artifacts.py`:

```python
import json
from pathlib import Path


PHASE14_ROOT = Path("docs/demo/phase14-finetuned-embedding-router")
README = Path("README.md")
PHASE14_DOC = Path("docs/phase14.md")


def test_phase14_training_data_artifacts_are_committed():
    pairs = _read_jsonl(PHASE14_ROOT / "training-pairs.jsonl")
    summary = json.loads((PHASE14_ROOT / "training-summary.json").read_text())
    config = json.loads((PHASE14_ROOT / "train-config.json").read_text())

    assert summary["phase"] == "Phase 14"
    assert summary["artifact_type"] == "phase14-embedding-training-data"
    assert summary["pair_count"] == len(pairs)
    assert summary["positive_count"] > 0
    assert summary["hard_negative_count"] > 0
    assert summary["leakage_guard"] == "PASS"
    assert config["output_dir"].startswith("/mnt/data/minghongsun/")
    assert config["model_checkpoint_committed"] is False


def test_phase14_docs_do_not_overclaim_without_eval_artifacts():
    readme = README.read_text(encoding="utf-8")
    phase14 = PHASE14_DOC.read_text(encoding="utf-8")

    assert "export-embedding-training-data" in readme
    assert "Fine-tuned embedding router" in phase14
    assert "does not establish SOTA" in phase14
    if not (PHASE14_ROOT / "finetuned-results.jsonl").exists():
        assert "- [ ] Fine-tuned embedding router" in readme


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 2: Run artifact guard test to verify RED**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase14_artifacts.py -q -p no:cacheprovider
```

Expected: fails until Phase 14 docs and artifacts exist.

- [ ] **Step 3: Create `docs/phase14.md`**

Create:

```markdown
# Phase 14: Fine-Tuned Embedding Router

Phase 14 adds a reproducible path for domain-specific embedding-router
fine-tuning. It exports supervised task-skill pairs, writes a remote-ready
training config, and evaluates a real fine-tuned SentenceTransformer model only
when a model path exists.

## Scope

This phase does not commit model checkpoints, embedding caches, downloaded
models, tensorboard logs, private hostnames, IPs, tokens, or SSH details.

## Local Artifacts

- `training-pairs.jsonl`
- `training-summary.json`
- `train-config.json`
- `model-card.md`

## Evaluation Artifacts

These files are committed only after a real fine-tuned model run:

- `baseline-results.jsonl`
- `finetuned-results.jsonl`
- `regression-summary.json`
- `comparison.md`

## Remote Storage

GPU training outputs must stay under:

`/mnt/data/minghongsun/hermes-skilleval-phase14`

## Limitations

This is a self-built Hermes-style skill-routing benchmark. It does not establish
SOTA and should not be described as a standard external benchmark.
```

- [ ] **Step 4: Update README**

Add a Phase 14 usage snippet:

```bash
skilleval export-embedding-training-data \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase14-finetuned-embedding-router
```

Add Phase 14 to the docs table:

```markdown
| Phase 14 | Fine-tuned embedding router | [`docs/phase14.md`](docs/phase14.md) |
```

Keep the roadmap unchecked until `finetuned-results.jsonl` exists and passes:

```markdown
- [ ] Fine-tuned embedding router for domain-specific skill libraries
```

- [ ] **Step 5: Run artifact guard test**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase14_artifacts.py -q -p no:cacheprovider
```

Expected: pass.

---

## Task 7: Final Validation And Review

**Files:**
- All Phase 14 files

- [ ] **Step 1: Run targeted Phase 14 tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest \
  tests/test_embedding_training.py \
  tests/test_finetuned_eval.py \
  tests/test_phase14_artifacts.py \
  tests/test_cli_smoke.py::test_cli_export_embedding_training_data_writes_pairs \
  -q -p no:cacheprovider
```

Expected: all targeted tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
```

Expected: all tests pass. Update README test counts to the exact count shown.

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Run sensitive scan**

Run:

```bash
run the current repository sensitive-scan command over Phase 14 docs,
artifacts, scripts, source, and tests
```

Expected: no matches; `rg` exits 1.

- [ ] **Step 5: Request code review**

Reviewer must check:

- no checkpoint or embedding cache is committed;
- train config writes only under `/mnt/data/minghongsun/`;
- README does not mark fine-tuned roadmap complete unless real evaluation artifacts exist;
- no SOTA or standard-benchmark wording appears;
- split leakage guard exists;
- baseline and candidate evaluation records are aligned before comparison.

- [ ] **Step 6: Commit Phase 14**

After review fixes and final validation:

```bash
git add README.md docs/phase14.md docs/demo/phase14-finetuned-embedding-router docs/superpowers/plans/2026-05-29-phase14-finetuned-embedding-router.md scripts/train_embedding_router.py src/hermes_skilleval/cli.py src/hermes_skilleval/embedding_training.py src/hermes_skilleval/finetuned_eval.py tests/test_cli_smoke.py tests/test_embedding_training.py tests/test_finetuned_eval.py tests/test_phase14_artifacts.py
git commit -m "feat: add fine-tuned embedding router evaluation path"
```

Expected: one Phase 14 commit on `codex/phase14-finetuned-embedding-router`.

---

## Execution Gate

If optional `sentence-transformers` dependencies or A100 access are unavailable, stop after the local export/config/test artifacts and report Phase 14 as infrastructure-ready but not evaluation-complete. Do not fabricate `finetuned-results.jsonl`, do not mark the roadmap complete, and do not claim fine-tuning improved metrics.

---

## Self-Review Notes

- The plan uses existing embedding router semantics instead of inventing a new router family.
- Training outputs stay outside the repo under `/mnt/data/minghongsun/hermes-skilleval-phase14`.
- The committed repo contains data, configs, metrics, and reports, not model weights.
- The wording remains evidence-bounded: self-built Hermes-style benchmark, no SOTA claim.
- The implementation has a clear stop condition if real model training cannot be completed.
