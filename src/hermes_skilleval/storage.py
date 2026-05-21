from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def timestamped_run_dir(root: Path | str = "runs") -> Path:
    directory = Path(root) / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    directory.mkdir(parents=True, exist_ok=False)
    return directory
