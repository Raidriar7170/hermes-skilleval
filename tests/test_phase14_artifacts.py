import json
from pathlib import Path


PHASE14_ROOT = Path("docs/demo/phase14-finetuned-embedding-router")
README = Path("README.md")
PHASE14_DOC = Path("docs/phase14.md")
TRAIN_SCRIPT = Path("scripts/train_embedding_router.py")


def test_phase14_training_data_artifacts_are_committed():
    pairs = _read_jsonl(PHASE14_ROOT / "training-pairs.jsonl")
    summary = json.loads((PHASE14_ROOT / "training-summary.json").read_text())
    config = json.loads((PHASE14_ROOT / "train-config.json").read_text())
    model_card = (PHASE14_ROOT / "model-card.md").read_text(encoding="utf-8")

    assert summary["phase"] == "Phase 14"
    assert summary["artifact_type"] == "phase14-embedding-training-data"
    assert summary["pair_count"] == len(pairs)
    assert summary["positive_count"] > 0
    assert summary["hard_negative_count"] > 0
    assert summary["leakage_guard"] == "PASS"
    assert config["output_dir"].startswith("/mnt/data/minghongsun/")
    assert config["model_checkpoint_committed"] is False
    assert "checkpoint is not committed" in model_card
    assert TRAIN_SCRIPT.exists()


def test_phase14_docs_do_not_overclaim_without_eval_artifacts():
    readme = README.read_text(encoding="utf-8")
    phase14 = PHASE14_DOC.read_text(encoding="utf-8")

    assert "export-embedding-training-data" in readme
    assert "judge-finetuned-embedding" in readme
    assert "Fine-tuned embedding router" in phase14
    assert "does not establish SOTA" in phase14
    assert "standard external benchmark" in phase14
    if not (PHASE14_ROOT / "finetuned-results.jsonl").exists():
        assert "- [ ] Fine-tuned embedding router" in readme


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
