"""Controller-owned filesystem patch capture independent of task Git state."""

from __future__ import annotations
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

EXCLUDED_PARTS = {
    ".git",
    ".agents",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".venv",
    "node_modules",
    ".tmp",
    ".codex",
}
EXCLUDED_SUFFIXES = {".pyc", ".db", ".sqlite", ".sqlite3", ".log"}


def manifest(root: Path, *, strict: bool = False) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(
            part in EXCLUDED_PARTS
            or part.endswith(".egg-info")
            or part.startswith("pytest-of-")
            for part in rel.parts
        ):
            continue
        if path.is_symlink():
            if strict:
                result[rel.as_posix()] = (
                    "symlink:"
                    + hashlib.sha256(str(path.readlink()).encode()).hexdigest()
                )
                continue
            raise ValueError(f"symlink rejected: {rel}")
        if not path.is_file():
            if strict and not path.is_dir():
                raise ValueError(f"special file rejected: {rel}")
            continue
        if not strict and path.suffix in EXCLUDED_SUFFIXES:
            continue
        if path.stat().st_size > 5_000_000:
            raise ValueError(f"oversized candidate file: {rel}")
        result[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def mode_manifest(root: Path, files: dict[str, str]) -> dict[str, int]:
    return {rel: (root / rel).lstat().st_mode & 0o777 for rel in files}


def copy_manifest(source: Path, dest: Path, files: dict[str, str]) -> None:
    for rel, digest in files.items():
        p = source / rel
        if digest.startswith("symlink:"):
            if (
                not p.is_symlink()
                or "symlink:" + hashlib.sha256(str(p.readlink()).encode()).hexdigest()
                != digest
            ):
                raise ValueError("source link changed during capture")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(p.readlink())
            continue
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError("source changed during capture")
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
        target.chmod(p.stat().st_mode & 0o777)


def capture(base: Path, candidate: Path, output: Path, *, strict: bool = False) -> dict:
    """Snapshot allowed source and make a binary Git patch from a private index."""
    before, after = manifest(base, strict=strict), manifest(candidate, strict=strict)
    before_modes, after_modes = (
        mode_manifest(base, before),
        mode_manifest(candidate, after),
    )
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "snapshot"
    snapshot.mkdir()
    copy_manifest(candidate, snapshot, after)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        copy_manifest(base, root, before)

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(root), *args], stderr=subprocess.STDOUT
            )

        git("init", "-q")
        git("add", "-f", ".")
        git(
            "-c",
            "user.name=Replay",
            "-c",
            "user.email=replay@localhost",
            "commit",
            "-qm",
            "trusted base",
        )
        for p in list(root.iterdir()):
            if p.name != ".git":
                shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
        copy_manifest(snapshot, root, after)
        git("add", "-A", "-f", ".")
        patch = git("diff", "--cached", "--binary", "--full-index", "--no-ext-diff")
    (output / "candidate.patch").write_bytes(patch)
    return {
        "base_manifest": before,
        "candidate_manifest": after,
        "base_modes": before_modes,
        "candidate_modes": after_modes,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "changed_files": sorted(
            k
            for k in before.keys() | after.keys()
            if before.get(k) != after.get(k)
            or before_modes.get(k) != after_modes.get(k)
        ),
    }


def rebuild(
    base: Path,
    patch: Path,
    output: Path,
    expected: dict[str, str] | None = None,
    expected_modes: dict[str, int] | None = None,
    *,
    strict: bool = False,
) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=False)
    copy_manifest(base, output, manifest(base, strict=strict))
    subprocess.run(["git", "init", "-q", str(output)], check=True, capture_output=True)
    if patch.stat().st_size:
        subprocess.run(
            ["git", "-C", str(output), "apply", "--check", str(patch.resolve())],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(output), "apply", str(patch.resolve())],
            check=True,
            capture_output=True,
        )
    actual = manifest(output, strict=strict)
    if expected is not None and actual != expected:
        raise ValueError("reconstructed source differs from captured candidate")
    if expected_modes is not None and mode_manifest(output, actual) != expected_modes:
        raise ValueError("reconstructed modes differ from captured candidate")
    return actual
