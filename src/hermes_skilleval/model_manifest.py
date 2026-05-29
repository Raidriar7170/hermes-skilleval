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
    total_size_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relpath = path.relative_to(root).as_posix()
        if relpath in EXCLUDED_EVIDENCE_FILES:
            continue
        payload = path.read_bytes()
        total_size_bytes += len(payload)
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
        "total_size_bytes": total_size_bytes,
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
