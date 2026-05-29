# Phase 15 Held-Out Generalization And Provenance Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strict held-out `test` split evidence pack for the Phase 14 fine-tuned embedding router and commit sanitized provenance for the remote A100 training run without committing checkpoints.

**Architecture:** Keep Phase 14 training unchanged. Extend the fine-tuned embedding judge so it can evaluate only a requested split and optionally write filtered JSONL copies. Add a small model-manifest writer for remote checkpoints, then add a provenance-pack writer that joins training config, training-data summary, remote train-run summary, model manifest, and held-out judge summary into committed JSON/Markdown artifacts.

**Tech Stack:** Python 3.11, argparse CLI, pytest, JSONL, SHA-256 file hashing, existing `skilleval` CLI, A100 artifacts under `/mnt/data/minghongsun`.

**Repository Execution Note:** Follow `AGENTS.md` Codex Orchestrator Apply Protocol for implementation in this repository. Use Superpowers skills only as local discipline for TDD, debugging, verification, review response, and branch finishing.

---

## File Structure

- Modify `src/hermes_skilleval/finetuned_eval.py`
  - Add `apply_split` filtering for `dev`, `test`, or `all`.
  - Add optional filtered result JSONL copies.
  - Add summary fields that distinguish source task count from evaluated task count.
- Modify `src/hermes_skilleval/cli.py`
  - Add `judge-finetuned-embedding --apply-split`.
  - Add `judge-finetuned-embedding --write-filtered-results`.
  - Add `write-model-manifest`.
  - Add `write-finetuned-provenance`.
- Create `src/hermes_skilleval/model_manifest.py`
  - Build a deterministic SHA-256 manifest for a remote model directory.
  - Exclude evidence JSON files from checkpoint file hashing.
- Modify `scripts/train_embedding_router.py`
  - Write `model-manifest.json` next to `train-run-summary.json` after model save.
- Create `src/hermes_skilleval/provenance.py`
  - Build `provenance.json` and `provenance.md`.
  - Reject common secret, host, `/root`, and private-key strings.
- Modify `tests/test_cli_smoke.py`
  - Cover held-out judge filtering and the two new CLI commands.
- Create `tests/test_model_manifest.py`
  - Unit-test manifest hashing and empty-directory rejection.
- Create `tests/test_provenance.py`
  - Unit-test provenance rendering and sensitive-value rejection.
- Create `tests/test_phase15_artifacts.py`
  - Guard committed Phase 15 artifacts, docs, checkpoint absence, and public wording.
- Create `docs/phase15.md`
  - Document the held-out-only result and provenance pack.
- Modify `README.md`
  - Add Phase 15 command surface, roadmap entry, and verified test count.
- Generate `docs/demo/phase15-held-out-generalization/`
  - `baseline-test-results.jsonl`
  - `finetuned-test-results.jsonl`
  - `regression-summary.json`
  - `comparison.md`
  - `train-run-summary.json`
  - `model-manifest.json`
  - `provenance.json`
  - `provenance.md`

## Task 1: Held-Out Split Judge

**Files:**
- Modify: `tests/test_cli_smoke.py`
- Modify: `src/hermes_skilleval/finetuned_eval.py`
- Modify: `src/hermes_skilleval/cli.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Add this helper near the existing Phase 14 CLI smoke tests in `tests/test_cli_smoke.py`:

```python
def _finetuned_eval_record(
    task_id,
    *,
    split,
    selected,
    gold=("gold",),
    negative=("bad",),
    recall_at_5=1.0,
    mrr=1.0,
    ndcg_at_5=1.0,
    negative_hit_rate=0.0,
    negative_accepted_rate=0.0,
):
    return {
        "task_id": task_id,
        "category": "agent",
        "difficulty": "medium",
        "split": split,
        "robustness_tags": ["phase15"],
        "selected_skill_ids": list(selected),
        "gold_skills": list(gold),
        "negative_skills": list(negative),
        "recall_at_5": recall_at_5,
        "mrr": mrr,
        "ndcg_at_5": ndcg_at_5,
        "negative_hit_rate": negative_hit_rate,
        "negative_accepted_rate": negative_accepted_rate,
        "selection_rate_at_5": len(selected) / 5,
    }
```

Add this test below `test_cli_judge_finetuned_embedding_writes_summary`:

```python
def test_cli_judge_finetuned_embedding_filters_to_test_split(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    baseline_records = [
        _finetuned_eval_record("dev-task", split="dev", selected=["gold"]),
        _finetuned_eval_record(
            "test-task",
            split="test",
            selected=["gold", "bad"],
            negative_hit_rate=1.0,
            negative_accepted_rate=1.0,
        ),
    ]
    candidate_records = [
        _finetuned_eval_record(
            "dev-task",
            split="dev",
            selected=["bad"],
            recall_at_5=0.0,
            mrr=0.0,
            ndcg_at_5=0.0,
            negative_hit_rate=1.0,
            negative_accepted_rate=1.0,
        ),
        _finetuned_eval_record(
            "test-task",
            split="test",
            selected=["gold", "bad"],
            negative_hit_rate=1.0,
            negative_accepted_rate=1.0,
        ),
    ]
    baseline.write_text(
        "".join(json.dumps(record) + "\n" for record in baseline_records),
        encoding="utf-8",
    )
    candidate.write_text(
        "".join(json.dumps(record) + "\n" for record in candidate_records),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase15"

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
            "--apply-split",
            "test",
            "--write-filtered-results",
        ]
    )

    assert result == 0
    summary = json.loads((output_dir / "regression-summary.json").read_text())
    assert summary["evaluated_split"] == "test"
    assert summary["split_policy"] == "records where split == 'test'"
    assert summary["source_task_count"] == 2
    assert summary["task_count"] == 1
    assert summary["guard_status"] == "PASS"
    assert (output_dir / "baseline-test-results.jsonl").exists()
    assert (output_dir / "finetuned-test-results.jsonl").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_judge_finetuned_embedding_filters_to_test_split -q -p no:cacheprovider
```

Expected: FAIL because `--apply-split` and `--write-filtered-results` do not exist yet.

- [ ] **Step 3: Add split filtering and filtered JSONL output**

Update `src/hermes_skilleval/finetuned_eval.py`:

```python
def write_finetuned_eval_summary(
    *,
    baseline_results_path: Path | str,
    candidate_results_path: Path | str,
    output_dir: Path | str,
    baseline_router: str,
    candidate_router: str,
    model_dir: str,
    apply_split: str = "all",
    write_filtered_results: bool = False,
) -> dict[str, Any]:
    validated_model_dir = validate_a100_user_path(model_dir, field="model_dir")

    baseline_source_records = _read_jsonl(baseline_results_path)
    candidate_source_records = _read_jsonl(candidate_results_path)
    baseline_records = _filter_records_by_split(
        baseline_source_records,
        apply_split=apply_split,
        label="baseline",
    )
    candidate_records = _filter_records_by_split(
        candidate_source_records,
        apply_split=apply_split,
        label="candidate",
    )
    diffs = compare_route_records(baseline_records, candidate_records)
    baseline_metrics = _mean_metrics(baseline_records)
    candidate_metrics = _mean_metrics(candidate_records)
    regression_count = sum(1 for diff in diffs if diff["regression_flags"])
    improvement_count = sum(1 for diff in diffs if diff["improvement_flags"])
    summary = {
        "phase": "Phase 15" if apply_split == "test" else "Phase 14",
        "artifact_type": "phase15-heldout-finetuned-embedding-eval"
        if apply_split == "test"
        else "phase14-finetuned-embedding-eval",
        "baseline_router": baseline_router,
        "candidate_router": candidate_router,
        "model_dir": validated_model_dir,
        "model_checkpoint_committed": False,
        "evaluated_split": apply_split,
        "split_policy": _split_policy(apply_split),
        "source_task_count": len(candidate_source_records),
        "task_count": len(candidate_records),
        "guard_status": "PASS" if regression_count == 0 else "REVIEW_REQUIRED",
        "baseline_mean_metrics": baseline_metrics,
        "candidate_mean_metrics": candidate_metrics,
        "metric_deltas": {
            field: round(candidate_metrics[field] - baseline_metrics[field], 6)
            for field in METRIC_FIELDS
        },
        "regression_count": regression_count,
        "improvement_count": improvement_count,
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if write_filtered_results:
        suffix = "all" if apply_split == "all" else apply_split
        _write_jsonl(output / f"baseline-{suffix}-results.jsonl", baseline_records)
        _write_jsonl(output / f"finetuned-{suffix}-results.jsonl", candidate_records)
    (output / "regression-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "comparison.md").write_text(_report(summary, diffs), encoding="utf-8")
    return summary
```

Add these helpers in the same module:

```python
def _filter_records_by_split(
    records: list[dict[str, Any]],
    *,
    apply_split: str,
    label: str,
) -> list[dict[str, Any]]:
    if apply_split not in {"dev", "test", "all"}:
        raise ValueError("apply_split must be 'dev', 'test', or 'all'")
    filtered = (
        records
        if apply_split == "all"
        else [record for record in records if record.get("split") == apply_split]
    )
    if not filtered:
        raise ValueError(f"no {label} records found for split {apply_split!r}")
    return filtered


def _split_policy(apply_split: str) -> str:
    if apply_split == "all":
        return "all source records"
    return f"records where split == {apply_split!r}"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
```

Update `_report()` so the header includes held-out scope:

```python
lines = [
    "# Phase 15 Held-Out Fine-Tuned Embedding Router Evaluation"
    if summary["evaluated_split"] == "test"
    else "# Phase 14 Fine-Tuned Embedding Router Evaluation",
    "",
    f"- Baseline: `{summary['baseline_router']}`",
    f"- Candidate: `{summary['candidate_router']}`",
    f"- Evaluated split: `{summary['evaluated_split']}`",
    f"- Source task count: {summary['source_task_count']}",
    f"- Evaluated task count: {summary['task_count']}",
    f"- Guard status: {summary['guard_status']}",
    f"- Model checkpoint committed: {summary['model_checkpoint_committed']}",
    "",
    "| Metric | Baseline | Candidate | Delta |",
    "|---|---:|---:|---:|",
]
```

- [ ] **Step 4: Wire CLI flags**

In `src/hermes_skilleval/cli.py`, add these arguments to the `judge-finetuned-embedding` parser:

```python
judge_finetuned_parser.add_argument(
    "--apply-split",
    choices=("dev", "test", "all"),
    default="all",
)
judge_finetuned_parser.add_argument(
    "--write-filtered-results",
    action="store_true",
)
```

Pass them in `_run_judge_finetuned_embedding`:

```python
write_finetuned_eval_summary(
    baseline_results_path=args.baseline_results,
    candidate_results_path=args.candidate_results,
    output_dir=args.output_dir,
    baseline_router=args.baseline_router,
    candidate_router=args.candidate_router,
    model_dir=args.model_dir,
    apply_split=args.apply_split,
    write_filtered_results=args.write_filtered_results,
)
```

- [ ] **Step 5: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_cli_smoke.py::test_cli_judge_finetuned_embedding_writes_summary tests/test_cli_smoke.py::test_cli_judge_finetuned_embedding_filters_to_test_split -q -p no:cacheprovider
```

Expected: both tests pass.

## Task 2: Model Manifest Writer

**Files:**
- Create: `tests/test_model_manifest.py`
- Create: `src/hermes_skilleval/model_manifest.py`
- Modify: `tests/test_cli_smoke.py`
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `scripts/train_embedding_router.py`
- Modify: `tests/test_train_embedding_router_script.py`

- [ ] **Step 1: Write failing model-manifest tests**

Create `tests/test_model_manifest.py`:

```python
import hashlib
import json

import pytest

from hermes_skilleval.model_manifest import build_model_manifest, write_model_manifest


MODEL_LABEL = "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router"


def test_build_model_manifest_records_relative_paths_and_sha256(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model": "demo"}\n', encoding="utf-8")
    (model_dir / "modules.json").write_text("[]\n", encoding="utf-8")
    (model_dir / "train-run-summary.json").write_text("{}\n", encoding="utf-8")

    manifest = build_model_manifest(
        model_dir=model_dir,
        model_dir_label=MODEL_LABEL,
    )

    assert manifest["phase"] == "Phase 15"
    assert manifest["artifact_type"] == "phase15-model-file-manifest"
    assert manifest["model_dir"] == MODEL_LABEL
    assert manifest["model_checkpoint_committed"] is False
    assert manifest["file_count"] == 2
    assert [item["path"] for item in manifest["files"]] == [
        "config.json",
        "modules.json",
    ]
    expected = hashlib.sha256(b'{"model": "demo"}\n').hexdigest()
    assert manifest["files"][0]["sha256"] == expected


def test_write_model_manifest_rejects_empty_model_dir(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    with pytest.raises(ValueError, match="no model files found"):
        write_model_manifest(
            model_dir=model_dir,
            model_dir_label=MODEL_LABEL,
            output_path=tmp_path / "model-manifest.json",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_model_manifest.py -q -p no:cacheprovider
```

Expected: FAIL because `hermes_skilleval.model_manifest` does not exist.

- [ ] **Step 3: Implement the model-manifest module**

Create `src/hermes_skilleval/model_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hermes_skilleval.remote_paths import validate_a100_user_path


EXCLUDED_EVIDENCE_FILES = {
    "model-manifest.json",
    "train-run-summary.json",
}


def build_model_manifest(
    *,
    model_dir: Path | str,
    model_dir_label: str,
) -> dict[str, Any]:
    validated_label = validate_a100_user_path(model_dir_label, field="model_dir")
    root = Path(model_dir)
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relpath = path.relative_to(root).as_posix()
        if relpath in EXCLUDED_EVIDENCE_FILES:
            continue
        payload = path.read_bytes()
        files.append(
            {
                "path": relpath,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    if not files:
        raise ValueError(f"no model files found in {root}")
    return {
        "phase": "Phase 15",
        "artifact_type": "phase15-model-file-manifest",
        "model_dir": validated_label,
        "model_checkpoint_committed": False,
        "file_count": len(files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in files),
        "files": files,
    }


def write_model_manifest(
    *,
    model_dir: Path | str,
    model_dir_label: str,
    output_path: Path | str,
) -> dict[str, Any]:
    manifest = build_model_manifest(
        model_dir=model_dir,
        model_dir_label=model_dir_label,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
```

- [ ] **Step 4: Add CLI smoke test for manifest writing**

Add this test to `tests/test_cli_smoke.py`:

```python
def test_cli_write_model_manifest_writes_manifest(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "model-manifest.json"

    result = main(
        [
            "write-model-manifest",
            "--model-dir",
            "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            "--local-model-dir",
            str(model_dir),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert manifest["files"][0]["path"] == "config.json"
```

- [ ] **Step 5: Wire `write-model-manifest` CLI**

In `src/hermes_skilleval/cli.py`, import the writer:

```python
from hermes_skilleval.model_manifest import write_model_manifest
```

Add the parser:

```python
manifest_parser = subparsers.add_parser(
    "write-model-manifest",
    help="write a sanitized file manifest for a remote model directory",
)
manifest_parser.add_argument("--model-dir", required=True)
manifest_parser.add_argument("--local-model-dir", default=None)
manifest_parser.add_argument("--output", required=True)
manifest_parser.set_defaults(handler=_run_write_model_manifest)
```

Add the handler:

```python
def _run_write_model_manifest(args: argparse.Namespace) -> None:
    write_model_manifest(
        model_dir=args.local_model_dir or args.model_dir,
        model_dir_label=args.model_dir,
        output_path=args.output,
    )
```

- [ ] **Step 6: Make the training script write the manifest**

In `scripts/train_embedding_router.py`, add:

```python
from hermes_skilleval.model_manifest import write_model_manifest
```

After `model.save(...)` succeeds and before returning:

```python
write_model_manifest(
    model_dir=model_output,
    model_dir_label=output_dir,
    output_path=model_output / "model-manifest.json",
)
```

Update the fake `SentenceTransformer.save` in `tests/test_train_embedding_router_script.py` so it writes a small model file:

```python
def save(self, path, **kwargs):
    FakeSentenceTransformer.save_kwargs = kwargs
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "config.json").write_text("{}\n", encoding="utf-8")
```

Assert the manifest exists:

```python
model_manifest = output_dir / "model-manifest.json"
assert model_manifest.exists()
assert json.loads(model_manifest.read_text())["file_count"] == 1
```

- [ ] **Step 7: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_model_manifest.py tests/test_cli_smoke.py::test_cli_write_model_manifest_writes_manifest tests/test_train_embedding_router_script.py -q -p no:cacheprovider
```

Expected: all targeted tests pass.

## Task 3: Provenance Pack Writer

**Files:**
- Create: `tests/test_provenance.py`
- Create: `src/hermes_skilleval/provenance.py`
- Modify: `tests/test_cli_smoke.py`
- Modify: `src/hermes_skilleval/cli.py`

- [ ] **Step 1: Write failing provenance tests**

Create `tests/test_provenance.py`:

```python
import json

import pytest

from hermes_skilleval.provenance import write_finetuned_provenance_pack


def test_write_finetuned_provenance_pack_summarizes_sources_without_checkpoints(tmp_path):
    training_summary = tmp_path / "training-summary.json"
    train_config = tmp_path / "train-config.json"
    train_run_summary = tmp_path / "train-run-summary.json"
    model_manifest = tmp_path / "model-manifest.json"
    regression_summary = tmp_path / "regression-summary.json"
    output_dir = tmp_path / "phase15"
    training_summary.write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "pair_count": 28,
                "positive_count": 16,
                "hard_negative_count": 12,
                "leakage_guard": "PASS",
            }
        ),
        encoding="utf-8",
    )
    train_config.write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "base_model": "/mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2",
                "output_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
                "epochs": 3,
                "batch_size": 8,
                "learning_rate": 2e-5,
                "loss": "MultipleNegativesRankingLoss+ContrastiveLoss",
                "hard_negative_margin": 1.5,
                "model_checkpoint_committed": False,
            }
        ),
        encoding="utf-8",
    )
    train_run_summary.write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "device": "cuda:0",
                "epoch_count": 3,
                "trained_pair_count": 11,
                "trained_hard_negative_pair_count": 8,
                "optimizer_step_count": 6,
                "hard_negative_optimizer_step_count": 3,
                "final_loss": 0.2228596806526184,
            }
        ),
        encoding="utf-8",
    )
    model_manifest.write_text(
        json.dumps(
            {
                "phase": "Phase 15",
                "artifact_type": "phase15-model-file-manifest",
                "model_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
                "model_checkpoint_committed": False,
                "file_count": 2,
                "total_size_bytes": 42,
                "files": [
                    {"path": "config.json", "size_bytes": 3, "sha256": "0" * 64},
                    {"path": "modules.json", "size_bytes": 3, "sha256": "1" * 64},
                ],
            }
        ),
        encoding="utf-8",
    )
    regression_summary.write_text(
        json.dumps(
            {
                "phase": "Phase 15",
                "artifact_type": "phase15-heldout-finetuned-embedding-eval",
                "evaluated_split": "test",
                "source_task_count": 12,
                "task_count": 4,
                "guard_status": "PASS",
                "regression_count": 0,
                "model_checkpoint_committed": False,
                "metric_deltas": {
                    "recall_at_5": 0.0,
                    "mrr": 0.0,
                    "ndcg_at_5": 0.0,
                    "negative_hit_rate": 0.0,
                    "negative_accepted_rate": 0.0,
                    "selection_rate_at_5": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )

    pack = write_finetuned_provenance_pack(
        training_summary_path=training_summary,
        train_config_path=train_config,
        train_run_summary_path=train_run_summary,
        model_manifest_path=model_manifest,
        regression_summary_path=regression_summary,
        output_dir=output_dir,
    )

    assert pack["phase"] == "Phase 15"
    assert pack["artifact_type"] == "phase15-heldout-provenance-pack"
    assert pack["model_checkpoint_committed"] is False
    assert pack["heldout_eval"]["evaluated_split"] == "test"
    assert pack["training"]["pair_count"] == 28
    assert pack["remote_run"]["epoch_count"] == 3
    assert (output_dir / "provenance.json").exists()
    markdown = (output_dir / "provenance.md").read_text(encoding="utf-8")
    assert "checkpoint is not committed" in markdown
    assert "standard external benchmark" in markdown


def test_write_finetuned_provenance_pack_rejects_sensitive_values(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"token": "PRIVATE KEY"}), encoding="utf-8")

    with pytest.raises(ValueError, match="sensitive value"):
        write_finetuned_provenance_pack(
            training_summary_path=path,
            train_config_path=path,
            train_run_summary_path=path,
            model_manifest_path=path,
            regression_summary_path=path,
            output_dir=tmp_path / "out",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_provenance.py -q -p no:cacheprovider
```

Expected: FAIL because `hermes_skilleval.provenance` does not exist.

- [ ] **Step 3: Implement provenance pack module**

Create `src/hermes_skilleval/provenance.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SENSITIVE_MARKERS = (
    "AKIA",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "PRIVATE KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "ssh-ed25519",
    "ssh-rsa",
    "/root",
)


def write_finetuned_provenance_pack(
    *,
    training_summary_path: Path | str,
    train_config_path: Path | str,
    train_run_summary_path: Path | str,
    model_manifest_path: Path | str,
    regression_summary_path: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    training_summary = _read_json(training_summary_path)
    train_config = _read_json(train_config_path)
    train_run_summary = _read_json(train_run_summary_path)
    model_manifest = _read_json(model_manifest_path)
    regression_summary = _read_json(regression_summary_path)
    pack = {
        "phase": "Phase 15",
        "artifact_type": "phase15-heldout-provenance-pack",
        "model_checkpoint_committed": False,
        "training": {
            "pair_count": training_summary["pair_count"],
            "positive_count": training_summary["positive_count"],
            "hard_negative_count": training_summary["hard_negative_count"],
            "leakage_guard": training_summary["leakage_guard"],
            "loss": train_config["loss"],
            "hard_negative_margin": train_config.get("hard_negative_margin"),
            "epochs": train_config["epochs"],
            "batch_size": train_config["batch_size"],
            "learning_rate": train_config["learning_rate"],
            "base_model": train_config["base_model"],
            "output_dir": train_config["output_dir"],
        },
        "remote_run": {
            "device": train_run_summary.get("device"),
            "epoch_count": train_run_summary["epoch_count"],
            "trained_pair_count": train_run_summary["trained_pair_count"],
            "trained_hard_negative_pair_count": train_run_summary[
                "trained_hard_negative_pair_count"
            ],
            "optimizer_step_count": train_run_summary["optimizer_step_count"],
            "hard_negative_optimizer_step_count": train_run_summary[
                "hard_negative_optimizer_step_count"
            ],
            "final_loss": train_run_summary.get("final_loss"),
        },
        "model_manifest": {
            "model_dir": model_manifest["model_dir"],
            "file_count": model_manifest["file_count"],
            "total_size_bytes": model_manifest["total_size_bytes"],
            "files": model_manifest["files"],
        },
        "heldout_eval": {
            "evaluated_split": regression_summary["evaluated_split"],
            "source_task_count": regression_summary["source_task_count"],
            "task_count": regression_summary["task_count"],
            "guard_status": regression_summary["guard_status"],
            "regression_count": regression_summary["regression_count"],
            "metric_deltas": regression_summary["metric_deltas"],
        },
        "limitations": [
            "self-built Hermes-style skill-routing benchmark",
            "standard external benchmark is not claimed",
            "model checkpoint is not committed",
        ],
    }
    _reject_sensitive_values(pack)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "provenance.json").write_text(
        json.dumps(pack, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "provenance.md").write_text(_render_markdown(pack), encoding="utf-8")
    return pack


def _read_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _reject_sensitive_values(value: Any) -> None:
    text = json.dumps(value, sort_keys=True)
    for marker in SENSITIVE_MARKERS:
        if marker in text:
            raise ValueError(f"sensitive value found: {marker}")


def _render_markdown(pack: dict[str, Any]) -> str:
    deltas = pack["heldout_eval"]["metric_deltas"]
    lines = [
        "# Phase 15 Held-Out Generalization Provenance",
        "",
        "## Scope",
        "",
        "This pack records how the Phase 14 fine-tuned embedding router was trained, "
        "which remote model files were produced, and how the committed held-out "
        "test-split judge result was generated. The model checkpoint is not committed.",
        "",
        "## Training",
        "",
        f"- Pair count: {pack['training']['pair_count']}",
        f"- Positive pairs: {pack['training']['positive_count']}",
        f"- Hard-negative pairs: {pack['training']['hard_negative_count']}",
        f"- Leakage guard: {pack['training']['leakage_guard']}",
        f"- Loss: `{pack['training']['loss']}`",
        f"- Epochs: {pack['training']['epochs']}",
        "",
        "## Remote Run",
        "",
        f"- Device: `{pack['remote_run']['device']}`",
        f"- Optimizer steps: {pack['remote_run']['optimizer_step_count']}",
        f"- Hard-negative optimizer steps: {pack['remote_run']['hard_negative_optimizer_step_count']}",
        f"- Final loss: {pack['remote_run']['final_loss']}",
        "",
        "## Held-Out Evaluation",
        "",
        f"- Evaluated split: `{pack['heldout_eval']['evaluated_split']}`",
        f"- Source task count: {pack['heldout_eval']['source_task_count']}",
        f"- Held-out task count: {pack['heldout_eval']['task_count']}",
        f"- Guard status: `{pack['heldout_eval']['guard_status']}`",
        f"- Regression count: {pack['heldout_eval']['regression_count']}",
        "",
        "| Metric | Delta |",
        "|---|---:|",
    ]
    for field, delta in sorted(deltas.items()):
        lines.append(f"| {field} | {float(delta):+.6f} |")
    lines.extend(
        [
            "",
            "## Model Manifest",
            "",
            f"- Model directory: `{pack['model_manifest']['model_dir']}`",
            f"- File count: {pack['model_manifest']['file_count']}",
            f"- Total size bytes: {pack['model_manifest']['total_size_bytes']}",
            "",
            "## Limitations",
            "",
            "This is a self-built Hermes-style skill-routing benchmark, not a "
            "standard external benchmark. It supports regression-aware project "
            "evidence; it does not establish SOTA or production readiness.",
            "",
        ]
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Add CLI smoke test for provenance writing**

Add this test to `tests/test_cli_smoke.py`:

```python
def test_cli_write_finetuned_provenance_writes_pack(tmp_path):
    training_summary = tmp_path / "training-summary.json"
    train_config = tmp_path / "train-config.json"
    train_run_summary = tmp_path / "train-run-summary.json"
    model_manifest = tmp_path / "model-manifest.json"
    regression_summary = tmp_path / "regression-summary.json"
    training_summary.write_text(
        json.dumps(
            {
                "pair_count": 28,
                "positive_count": 16,
                "hard_negative_count": 12,
                "leakage_guard": "PASS",
            }
        ),
        encoding="utf-8",
    )
    train_config.write_text(
        json.dumps(
            {
                "loss": "MultipleNegativesRankingLoss+ContrastiveLoss",
                "hard_negative_margin": 1.5,
                "epochs": 3,
                "batch_size": 8,
                "learning_rate": 2e-5,
                "base_model": "/mnt/data/minghongsun/hermes-skilleval-models/all-MiniLM-L6-v2",
                "output_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
            }
        ),
        encoding="utf-8",
    )
    train_run_summary.write_text(
        json.dumps(
            {
                "device": "cuda:0",
                "epoch_count": 3,
                "trained_pair_count": 11,
                "trained_hard_negative_pair_count": 8,
                "optimizer_step_count": 6,
                "hard_negative_optimizer_step_count": 3,
                "final_loss": 0.2228596806526184,
            }
        ),
        encoding="utf-8",
    )
    model_manifest.write_text(
        json.dumps(
            {
                "model_dir": "/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router",
                "file_count": 1,
                "total_size_bytes": 2,
                "files": [{"path": "config.json", "size_bytes": 2, "sha256": "0" * 64}],
            }
        ),
        encoding="utf-8",
    )
    regression_summary.write_text(
        json.dumps(
            {
                "evaluated_split": "test",
                "source_task_count": 12,
                "task_count": 4,
                "guard_status": "PASS",
                "regression_count": 0,
                "metric_deltas": {"recall_at_5": 0.0},
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase15"

    result = main(
        [
            "write-finetuned-provenance",
            "--training-summary",
            str(training_summary),
            "--train-config",
            str(train_config),
            "--train-run-summary",
            str(train_run_summary),
            "--model-manifest",
            str(model_manifest),
            "--regression-summary",
            str(regression_summary),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert (output_dir / "provenance.json").exists()
    assert (output_dir / "provenance.md").exists()
```

- [ ] **Step 5: Wire provenance CLI**

In `src/hermes_skilleval/cli.py`, import:

```python
from hermes_skilleval.provenance import write_finetuned_provenance_pack
```

Add the parser:

```python
provenance_parser = subparsers.add_parser(
    "write-finetuned-provenance",
    help="write a sanitized provenance pack for held-out fine-tuned embedding evidence",
)
provenance_parser.add_argument("--training-summary", required=True)
provenance_parser.add_argument("--train-config", required=True)
provenance_parser.add_argument("--train-run-summary", required=True)
provenance_parser.add_argument("--model-manifest", required=True)
provenance_parser.add_argument("--regression-summary", required=True)
provenance_parser.add_argument("--output-dir", required=True)
provenance_parser.set_defaults(handler=_run_write_finetuned_provenance)
```

Add the handler:

```python
def _run_write_finetuned_provenance(args: argparse.Namespace) -> None:
    write_finetuned_provenance_pack(
        training_summary_path=args.training_summary,
        train_config_path=args.train_config,
        train_run_summary_path=args.train_run_summary,
        model_manifest_path=args.model_manifest,
        regression_summary_path=args.regression_summary,
        output_dir=args.output_dir,
    )
```

- [ ] **Step 6: Run targeted tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_provenance.py tests/test_cli_smoke.py::test_cli_write_finetuned_provenance_writes_pack -q -p no:cacheprovider
```

Expected: all targeted tests pass.

## Task 4: Generate Phase 15 Held-Out Artifacts

**Files:**
- Generate: `docs/demo/phase15-held-out-generalization/baseline-test-results.jsonl`
- Generate: `docs/demo/phase15-held-out-generalization/finetuned-test-results.jsonl`
- Generate: `docs/demo/phase15-held-out-generalization/regression-summary.json`
- Generate: `docs/demo/phase15-held-out-generalization/comparison.md`
- Generate: `docs/demo/phase15-held-out-generalization/train-run-summary.json`
- Generate: `docs/demo/phase15-held-out-generalization/model-manifest.json`
- Generate: `docs/demo/phase15-held-out-generalization/provenance.json`
- Generate: `docs/demo/phase15-held-out-generalization/provenance.md`

- [ ] **Step 1: Generate the held-out-only judge artifacts locally**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase15-held-out-generalization \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --apply-split test \
  --write-filtered-results
```

Expected from the current Phase 14 artifacts:

```json
{
  "evaluated_split": "test",
  "source_task_count": 12,
  "task_count": 4,
  "guard_status": "PASS",
  "regression_count": 0,
  "metric_deltas": {
    "recall_at_5": 0.0,
    "mrr": 0.0,
    "ndcg_at_5": 0.0,
    "negative_hit_rate": 0.0,
    "negative_accepted_rate": 0.0,
    "selection_rate_at_5": 0.0
  }
}
```

- [ ] **Step 2: Sync current code to the A100 project directory**

Use the existing SSH alias. Keep all remote files under:

```text
/mnt/data/minghongsun/hermes-skilleval-phase14
```

Do not write under `/root`, `/tmp`, or another user's directory. If using a tar stream instead of `rsync`, delete macOS `._*` files on the remote before running Python packaging commands:

```bash
find /mnt/data/minghongsun/hermes-skilleval-phase14 -name '._*' -type f -delete
```

- [ ] **Step 3: Write the remote model manifest on the A100**

Run on the A100 from the synced repo directory:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli write-model-manifest \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --output /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router/model-manifest.json
```

Expected: `model-manifest.json` exists under the model directory and contains SHA-256 entries for model files, but no checkpoint bytes are copied into the repo.

- [ ] **Step 4: Copy sanitized remote summaries into the Phase 15 artifact directory**

Copy only these two remote JSON files into `docs/demo/phase15-held-out-generalization/`:

```text
/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router/train-run-summary.json
/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router/model-manifest.json
```

Expected local paths:

```text
docs/demo/phase15-held-out-generalization/train-run-summary.json
docs/demo/phase15-held-out-generalization/model-manifest.json
```

- [ ] **Step 5: Generate the provenance pack**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli write-finetuned-provenance \
  --training-summary docs/demo/phase14-finetuned-embedding-router/training-summary.json \
  --train-config docs/demo/phase14-finetuned-embedding-router/train-config.json \
  --train-run-summary docs/demo/phase15-held-out-generalization/train-run-summary.json \
  --model-manifest docs/demo/phase15-held-out-generalization/model-manifest.json \
  --regression-summary docs/demo/phase15-held-out-generalization/regression-summary.json \
  --output-dir docs/demo/phase15-held-out-generalization
```

Expected: `provenance.json` and `provenance.md` are written under `docs/demo/phase15-held-out-generalization/`.

## Task 5: Phase 15 Docs And Artifact Guards

**Files:**
- Create: `tests/test_phase15_artifacts.py`
- Create: `docs/phase15.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing artifact tests**

Create `tests/test_phase15_artifacts.py`:

```python
import json
from pathlib import Path


PHASE15_ROOT = Path("docs/demo/phase15-held-out-generalization")
README = Path("README.md")
PHASE15_DOC = Path("docs/phase15.md")
CHECKPOINT_SUFFIXES = {".bin", ".onnx", ".pt", ".pth", ".safetensors"}
SENSITIVE_MARKERS = (
    "AKIA",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "PRIVATE KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "ssh-ed25519",
    "ssh-rsa",
    "/root",
)


def test_phase15_heldout_artifacts_are_test_split_only():
    baseline = _read_jsonl(PHASE15_ROOT / "baseline-test-results.jsonl")
    candidate = _read_jsonl(PHASE15_ROOT / "finetuned-test-results.jsonl")
    summary = json.loads((PHASE15_ROOT / "regression-summary.json").read_text())

    assert len(baseline) == len(candidate) == summary["task_count"] == 4
    assert summary["source_task_count"] == 12
    assert summary["evaluated_split"] == "test"
    assert summary["guard_status"] == "PASS"
    assert summary["regression_count"] == 0
    assert all(record["split"] == "test" for record in baseline)
    assert all(record["split"] == "test" for record in candidate)
    assert summary["metric_deltas"]["recall_at_5"] >= 0
    assert summary["metric_deltas"]["negative_hit_rate"] <= 0


def test_phase15_provenance_pack_is_sanitized_and_checkpoint_free():
    provenance = json.loads((PHASE15_ROOT / "provenance.json").read_text())
    manifest = json.loads((PHASE15_ROOT / "model-manifest.json").read_text())
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PHASE15_ROOT.glob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md"}
    )

    assert provenance["artifact_type"] == "phase15-heldout-provenance-pack"
    assert provenance["model_checkpoint_committed"] is False
    assert manifest["model_checkpoint_committed"] is False
    assert manifest["file_count"] > 0
    assert not any(path.suffix in CHECKPOINT_SUFFIXES for path in PHASE15_ROOT.iterdir())
    assert all(marker not in text for marker in SENSITIVE_MARKERS)


def test_phase15_docs_and_readme_reference_the_pack_without_overclaiming():
    readme = README.read_text(encoding="utf-8")
    phase15 = PHASE15_DOC.read_text(encoding="utf-8")

    assert "Phase 15" in readme
    assert "held-out" in readme
    assert "provenance" in readme
    assert "Phase 15: Held-out generalization and provenance pack" in phase15
    assert "does not establish SOTA" in phase15
    assert "standard external benchmark" in phase15
    assert "production readiness" in phase15
    assert "| Test cases | 228 |" in readme
    assert "228 passed" in readme


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
```

- [ ] **Step 2: Run artifact tests to verify they fail**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase15_artifacts.py -q -p no:cacheprovider
```

Expected: FAIL until Phase 15 artifacts and docs are generated.

- [ ] **Step 3: Create `docs/phase15.md`**

Create `docs/phase15.md` with this structure:

```markdown
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
```

- [ ] **Step 4: Update `README.md`**

Add Phase 15 to the phase table:

```markdown
| Phase 15 | Held-out generalization and provenance pack | [`docs/phase15.md`](docs/phase15.md) |
```

Add a command block near the Phase 14 command section:

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase15-held-out-generalization \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --apply-split test \
  --write-filtered-results

skilleval write-finetuned-provenance \
  --training-summary docs/demo/phase14-finetuned-embedding-router/training-summary.json \
  --train-config docs/demo/phase14-finetuned-embedding-router/train-config.json \
  --train-run-summary docs/demo/phase15-held-out-generalization/train-run-summary.json \
  --model-manifest docs/demo/phase15-held-out-generalization/model-manifest.json \
  --regression-summary docs/demo/phase15-held-out-generalization/regression-summary.json \
  --output-dir docs/demo/phase15-held-out-generalization
```

Update the test count lines from `218` to `228` after the full suite confirms `228 passed`.

- [ ] **Step 5: Run artifact tests**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest tests/test_phase15_artifacts.py -q -p no:cacheprovider
```

Expected: Phase 15 artifact tests pass.

## Task 6: Final Verification And Commit

**Files:**
- Verify all files touched by Tasks 1-5.

- [ ] **Step 1: Run full local verification**

Run:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
ruff check .
mypy src tests
python -m pip install -e . --dry-run
git diff --check
```

Expected:

```text
228 passed
All checks passed!
Success: no issues found in 70 source files
Would install hermes-skilleval-0.1.0
```

- [ ] **Step 2: Run sensitive scan over touched public artifacts**

Run:

```bash
rg -n "AKIA|SECRET|TOKEN|PASSWORD|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|/root|ssh-rsa|ssh-ed25519|[0-9]{1,3}(\\.[0-9]{1,3}){3}" \
  README.md docs/phase15.md docs/demo/phase15-held-out-generalization
```

Expected: exit code `1` with no matches in public docs or committed demo artifacts.

- [ ] **Step 3: Review the final diff**

Run:

```bash
git diff -- README.md docs/phase15.md docs/demo/phase15-held-out-generalization src/hermes_skilleval scripts tests
```

Expected: the diff only contains Phase 15 split filtering, model-manifest/provenance code, generated Phase 15 artifacts, tests, and docs.

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md docs/phase15.md docs/demo/phase15-held-out-generalization src/hermes_skilleval scripts tests
git commit -m "feat: add phase15 held-out provenance pack"
```

Expected: one focused commit on `codex/phase14-finetuned-embedding-router`.
