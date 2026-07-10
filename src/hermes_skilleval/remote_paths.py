from __future__ import annotations

from pathlib import Path


A100_USER_ROOT = Path("/mnt/data/minghongsun")


def resolve_path_root(root: str | Path, *, field: str) -> str:
    try:
        resolved_root = Path(root).resolve(strict=False)
    except TypeError as exc:
        raise ValueError(f"{field} must be a path") from exc
    if resolved_root.exists() and not resolved_root.is_dir():
        raise ValueError(f"{field} must be a directory: {resolved_root}")
    return str(resolved_root)


def validate_path_within_root(
    path: str | Path,
    *,
    root: str | Path,
    field: str,
) -> str:
    resolved_root = Path(resolve_path_root(root, field="root"))
    try:
        candidate = Path(path)
    except TypeError as exc:
        raise ValueError(f"{field} must be a path") from exc
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
    resolved_path = Path(path).resolve(strict=False)
    return validate_path_within_root(resolved_path, root=A100_USER_ROOT, field=field)
