from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def ensure_dir(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def timestamped_run_dir(root: Path | str = "runs") -> Path:
    root_path = Path(root)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for suffix in ["", *(f"-{index:03d}" for index in range(1, 1000))]:
        directory = root_path / f"{timestamp}{suffix}"
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return directory
    raise FileExistsError(f"no available run directory for {timestamp} under {root_path}")
