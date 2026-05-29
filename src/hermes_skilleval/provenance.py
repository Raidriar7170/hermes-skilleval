from __future__ import annotations

import json
import re
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
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
CREDENTIAL_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer)\b"
    r"\s*[:=]?\s*[A-Za-z0-9._~+/=-]{4,}"
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
            "baseline_source_task_count": _source_task_count(
                regression_summary,
                "baseline_source_task_count",
            ),
            "candidate_source_task_count": _source_task_count(
                regression_summary,
                "candidate_source_task_count",
            ),
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
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _reject_sensitive_values(value)
    return value


def _source_task_count(summary: dict[str, Any], field: str) -> int:
    return int(summary.get(field, summary["source_task_count"]))


def _reject_sensitive_values(value: Any) -> None:
    text = json.dumps(value, sort_keys=True)
    for marker in SENSITIVE_MARKERS:
        if _contains_sensitive_marker(text, marker):
            raise ValueError(f"sensitive value found: {marker}")
    if IPV4_RE.search(text):
        raise ValueError("sensitive value found: IPv4 address")
    if OPENAI_KEY_RE.search(text) or CREDENTIAL_RE.search(text):
        raise ValueError("sensitive value found: credential pattern")


def _contains_sensitive_marker(text: str, marker: str) -> bool:
    if marker in {"/root", "AKIA", "ssh-ed25519", "ssh-rsa"}:
        return marker in text
    pattern = rf"(?<![A-Z0-9]){re.escape(marker.upper())}(?![A-Z0-9])"
    return re.search(pattern, text.upper()) is not None


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
        "- Hard-negative optimizer steps: "
        f"{pack['remote_run']['hard_negative_optimizer_step_count']}",
        f"- Final loss: {pack['remote_run']['final_loss']}",
        "",
        "## Held-Out Evaluation",
        "",
        f"- Evaluated split: `{pack['heldout_eval']['evaluated_split']}`",
        f"- Source task count: {pack['heldout_eval']['source_task_count']}",
        "- Baseline source task count: "
        f"{pack['heldout_eval']['baseline_source_task_count']}",
        "- Candidate source task count: "
        f"{pack['heldout_eval']['candidate_source_task_count']}",
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
