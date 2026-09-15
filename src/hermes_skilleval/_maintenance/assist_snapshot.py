"""Consistent current-byte snapshot, independent of HEAD and of the source index."""

from pathlib import Path
import hashlib
import os
import re
import subprocess
from hermes_skilleval.file_policy import relative_path
from hermes_skilleval.repository_maintenance import EXCLUDED_PARTS, copy_manifest

EXCLUDED = EXCLUDED_PARTS | {"build", "dist", "venv", ".env", ".idea", ".vscode"}
LARGE_SUFFIXES = {".safetensors", ".pt", ".pth", ".bin", ".onnx", ".log"}
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"
)


def git(repo, *args):
    return subprocess.check_output(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(repo),
            *args,
        ],
        stderr=subprocess.PIPE,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def source_state(repo):
    # Git status uses the index read-only; the full index bytes also protect staged content.
    index = Path(git(repo, "rev-parse", "--git-path", "index").decode().strip())
    if not index.is_absolute():
        index = repo / index
    return {
        "head": git(repo, "rev-parse", "HEAD").decode().strip(),
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "status": git(
            repo,
            "-c",
            "core.fsmonitor=false",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ).decode(),
    }


def inspect_source(repo, include=(), exclude=()):
    repo = repo.resolve()
    if (
        Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        != repo
    ):
        raise ValueError("--repo must be the Git repository root")
    if git(repo, "ls-files", "-u"):
        raise ValueError("unmerged input index")
    before = source_state(repo)
    tracked = set(filter(None, git(repo, "ls-files", "-z").decode().split("\0")))
    untracked = set(
        filter(
            None,
            git(repo, "ls-files", "--others", "--exclude-standard", "-z")
            .decode()
            .split("\0"),
        )
    )
    include, exclude = set(include), set(exclude)
    for name in include | exclude:
        relative_path(name)
    if not include <= untracked or not exclude <= tracked:
        raise ValueError(
            "include_untracked must name present nonignored files; exclude_input must name tracked files"
        )
    files, modes, excluded = {}, {}, []
    for name in sorted(tracked | include):
        rel = relative_path(name)
        p = repo / name
        if not p.exists() and not p.is_symlink():
            continue  # An existing staged/unstaged deletion is part of the baseline.
        if name in exclude:
            excluded.append(name)
            continue
        if (
            any(part in EXCLUDED or part.endswith(".egg-info") for part in rel.parts)
            or p.suffix.lower() in LARGE_SUFFIXES
            or p.name in {"auth.json", "credentials.json"}
            or p.name.startswith(".env.")
        ):
            raise ValueError(
                "excluded input requires explicit exclude_input acknowledgement: "
                + name
            )
        if any(
            (repo.joinpath(*rel.parts[:i])).is_symlink()
            for i in range(1, len(rel.parts) + 1)
        ):
            raise ValueError("source symlink unsupported: " + name)
        if not p.is_file() or p.stat().st_size > 5_000_000:
            raise ValueError("unsupported input file/type/size: " + name)
        content = p.read_bytes()
        if SECRET.search(content):
            raise ValueError("sensitive input detected: " + name)
        files[name] = hashlib.sha256(content).hexdigest()
        modes[name] = p.stat().st_mode & 0o777
    if source_state(repo) != before:
        raise ValueError("source index/status changed during inspection")
    return {
        "git": before,
        "files": files,
        "modes": modes,
        "excluded": excluded,
        "untracked_not_included": sorted(untracked - include),
        "snapshot_sha256": hashlib.sha256(
            __import__("json").dumps([files, modes], sort_keys=True).encode()
        ).hexdigest(),
    }


def snapshot(repo, destination, expected, include=(), exclude=()):
    destination.mkdir(parents=True, exist_ok=False)
    copy_manifest(repo, destination, expected["files"])
    if inspect_source(repo, include, exclude) != expected:
        raise ValueError("source changed during snapshot; no Agent started")
