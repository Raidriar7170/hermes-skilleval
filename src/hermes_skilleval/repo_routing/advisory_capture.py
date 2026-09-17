"""Study-only complete source capture; preserves hidden forbidden edits before rejection."""

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

# These are declared runtime artifacts, inventoried separately, never source.
RUNTIME = {".tmp", "__pycache__", ".pytest_cache", ".hypothesis"}


def inventory(root, *, runtime=False):
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(base) / name
            rel = p.relative_to(root).as_posix()
            if not runtime and any(x in RUNTIME for x in Path(rel).parts):
                continue
            mode = p.lstat().st_mode
            if stat.S_ISDIR(mode):
                continue
            if stat.S_ISLNK(mode):
                content = os.readlink(p).encode()
                kind = "symlink"
            elif stat.S_ISREG(mode):
                content = p.read_bytes()
                kind = "file"
            else:
                content = b""
                kind = "special"
            result[rel] = {
                "sha256": hashlib.sha256(content).hexdigest(),
                "mode": stat.S_IMODE(mode),
                "kind": kind,
                "bytes": len(content),
            }
    return result


def copy_files(source, dest, listing):
    for rel, item in listing.items():
        if item["kind"] == "special":
            raise ValueError("special file retained in raw inventory: " + rel)
        p, q = Path(source) / rel, Path(dest) / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        if item["kind"] == "symlink":
            q.symlink_to(os.readlink(p))
        else:
            shutil.copy2(p, q)


def capture_complete(base, candidate, output, injected=None):
    before = inventory(base)
    if injected:
        if before.keys() & injected.keys():
            raise ValueError("base overlaps injected skills")
        before = {**before, **injected}
    after = inventory(candidate)
    # Git metadata is never a permitted candidate payload; preserve separately.
    if any(".git" in Path(x).parts for x in before.keys() | after.keys()):
        raise ValueError(
            "unexpected Git metadata; candidate retained, no accepted patch"
        )
    output.mkdir(parents=True, exist_ok=False)
    copy_files(candidate, output / "snapshot", after)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        copy_files(base, root, inventory(base))
        if injected:
            copy_files(candidate, root, injected)

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(root), *args], stderr=subprocess.STDOUT
            )

        git("init", "-q")
        git("add", "-f", ".")
        git(
            "-c",
            "user.name=Study",
            "-c",
            "user.email=study@localhost",
            "commit",
            "-qm",
            "base",
        )
        for p in root.iterdir():
            if p.name != ".git":
                shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
        copy_files(output / "snapshot", root, after)
        git("add", "-A", "-f", ".")
        patch = git("diff", "--cached", "--binary", "--full-index", "--no-ext-diff")
    (output / "candidate.patch").write_bytes(patch)
    changed = sorted(
        k for k in before.keys() | after.keys() if before.get(k) != after.get(k)
    )
    return {
        "before": before,
        "after": after,
        "changed_files": changed,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
    }


def reconstruct(base, patch, output, expected):
    copy_files(base, output, inventory(base))
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
    if inventory(output) != expected:
        raise ValueError("reconstructed candidate differs")
