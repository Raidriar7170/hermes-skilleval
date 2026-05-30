import json
import re
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
CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer)\b"
    r"\s*[:=]\s*[A-Za-z0-9._~+/=-]{4,}"
)
OPENAI_KEY_RE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{16,}")


def test_phase15_heldout_artifacts_are_test_split_only():
    baseline = _read_jsonl(PHASE15_ROOT / "baseline-test-results.jsonl")
    candidate = _read_jsonl(PHASE15_ROOT / "finetuned-test-results.jsonl")
    summary = json.loads((PHASE15_ROOT / "regression-summary.json").read_text())

    assert len(baseline) == len(candidate) == summary["task_count"] == 4
    assert summary["source_task_count"] == 12
    assert summary["baseline_source_task_count"] == 12
    assert summary["candidate_source_task_count"] == 12
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
    assert CREDENTIAL_RE.search(text) is None
    assert OPENAI_KEY_RE.search(text) is None


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
    assert "| Test cases | 274 |" in readme
    assert "274 passed" in readme


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
