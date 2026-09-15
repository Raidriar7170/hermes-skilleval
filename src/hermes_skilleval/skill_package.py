"""Verified complete skill packages; no install hooks are executed."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


class SkillPackageUnavailable(ValueError):
    """SKILL_PACKAGE_UNAVAILABLE: incomplete or unsafe package."""


def package_manifest(root: Path | str) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or not (root / "SKILL.md").is_file():
        raise SkillPackageUnavailable(
            "SKILL_PACKAGE_UNAVAILABLE: missing package/SKILL.md"
        )
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SkillPackageUnavailable(
                "SKILL_PACKAGE_UNAVAILABLE: symlink: " + str(path)
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise SkillPackageUnavailable("SKILL_PACKAGE_UNAVAILABLE: non-regular file")
        relative = path.relative_to(root).as_posix()
        if any(
            part in {".git", "__pycache__"} for part in path.relative_to(root).parts
        ):
            raise SkillPackageUnavailable(
                "SKILL_PACKAGE_UNAVAILABLE: unqualified package content"
            )
        rows.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "executable": bool(path.stat().st_mode & 0o111),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    return {"sha256": digest, "files": rows}


def copy_skill_package(
    source: Path | str, destination: Path | str, expected_sha256: str
) -> dict:
    source, destination = Path(source), Path(destination)
    manifest = package_manifest(source)
    if manifest["sha256"] != expected_sha256:
        raise SkillPackageUnavailable(
            "SKILL_PACKAGE_UNAVAILABLE: package changed or resource missing"
        )
    if destination.exists() or destination.is_symlink():
        raise SkillPackageUnavailable("SKILL_PACKAGE_UNAVAILABLE: destination exists")
    # Destination must be beneath a caller-owned fresh workspace, never a symlink.
    if any(p.is_symlink() for p in destination.parents):
        raise SkillPackageUnavailable(
            "SKILL_PACKAGE_UNAVAILABLE: symlink destination parent"
        )
    shutil.copytree(source, destination)
    if package_manifest(destination) != manifest:
        raise SkillPackageUnavailable(
            "SKILL_PACKAGE_UNAVAILABLE: copied package mismatch"
        )
    return manifest
