from __future__ import annotations

from pathlib import Path


A100_USER_ROOT = Path("/mnt/data/minghongsun")


def validate_a100_user_path(path: str, *, field: str) -> str:
    allowed_root = A100_USER_ROOT.resolve(strict=False)
    resolved_path = Path(path).resolve(strict=False)
    try:
        resolved_path.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(f"{field} must be under /mnt/data/minghongsun/") from exc
    return str(resolved_path)
