from __future__ import annotations

from pathlib import Path


A100_USER_ROOT = Path("/mnt/data/minghongsun")


def validate_path_within_root(
    path: str | Path,
    *,
    root: str | Path,
    field: str,
) -> str:
    resolved_root = Path(root).resolve(strict=False)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolved_root / candidate
    resolved_path = candidate.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        canonical_root = str(resolved_root).rstrip("/") + "/"
        raise ValueError(f"{field} must be under {canonical_root}") from exc
    return str(resolved_path)


def validate_a100_user_path(path: str, *, field: str) -> str:
    return validate_path_within_root(path, root=A100_USER_ROOT, field=field)
