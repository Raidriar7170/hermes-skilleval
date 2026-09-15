"""Explicit, operation-aware policy for future tasks; legacy profiles stay frozen."""

from pathlib import Path, PurePosixPath
import re

VERSION = "operations-v1"
OPERATIONS = {"add", "modify", "delete"}
DATA_SUFFIXES = {".csv", ".tsv", ".json", ".txt"}
PROTECTED = {
    ".git",
    ".agents",
    ".codex",
    ".github",
    ".env",
    "auth.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "conftest.py",
    "requirements.txt",
    "requirements-dev.txt",
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
}


def relative_path(name):
    if (
        not isinstance(name, str)
        or not name
        or name.startswith("/")
        or "\\" in name
        or any(ord(c) < 32 for c in name)
        or ":" in name
        or any(p in ("", ".", "..") for p in name.split("/"))
    ):
        raise ValueError("unsafe relative path: " + repr(name))
    return PurePosixPath(name)


def validate_policy(policy):
    if set(policy) != {"version", "rules"} or policy["version"] != VERSION:
        raise ValueError("unsupported file policy")
    if not isinstance(policy["rules"], list) or not policy["rules"]:
        raise ValueError("nonempty policy rules required")
    seen = set()
    for rule in policy["rules"]:
        if set(rule) - {"path", "operations", "data_only", "max_bytes"}:
            raise ValueError("unsupported policy field")
        path = relative_path(rule["path"])
        if str(path) in seen:
            raise ValueError("duplicate policy path")
        seen.add(str(path))
        if not rule["operations"] or not set(rule["operations"]) <= OPERATIONS:
            raise ValueError("invalid file operations")
        if not isinstance(rule.get("data_only", False), bool):
            raise ValueError("data_only must be boolean")
        limit = rule.get("max_bytes", 1_000_000)
        if type(limit) is not int or not 0 < limit <= 5_000_000:
            raise ValueError("invalid file size limit")
        if any(p in PROTECTED for p in path.parts):
            raise ValueError("policy cannot authorize controller/configuration paths")


def disclosure(policy):
    validate_policy(policy)
    lines = ["File policy " + VERSION + " (case-sensitive POSIX paths; default deny):"]
    for rule in policy["rules"]:
        lines.append(
            f"- {rule['path']}: {', '.join(rule['operations'])}; "
            f"max {rule.get('max_bytes', 1_000_000)} bytes; "
            + (
                "UTF-8 CSV/TSV/JSON/TXT data only, non-executable"
                if rule.get("data_only")
                else "regular files"
            )
        )
    return (
        "\n".join(lines)
        + "\nController checks, credentials, dependency/configuration files and symlinks remain protected. Renames require delete and add permission."
    )


def validate_candidate(policy, before, after, candidate, changed_files):
    validate_policy(policy)
    for name in changed_files:
        path = relative_path(name)
        if any(
            p in PROTECTED or p.startswith(".env.") or p.endswith(".lock")
            for p in path.parts
        ):
            raise ValueError("protected file: " + name)
        operation = (
            "add" if name not in before else "delete" if name not in after else "modify"
        )
        rules = [
            r
            for r in policy["rules"]
            if path == PurePosixPath(r["path"])
            or PurePosixPath(r["path"]) in path.parents
        ]
        # Most specific rule wins; a broad parent cannot override a narrower denial.
        rule = max(
            rules, key=lambda r: len(PurePosixPath(r["path"]).parts), default=None
        )
        if rule is None or operation not in rule["operations"]:
            raise ValueError(f"policy rejected {operation}: {name}")
        if operation == "delete":
            continue
        file = Path(candidate) / name
        if any(
            p.is_symlink() for p in [file, *file.parents] if p != Path(candidate).parent
        ):
            raise ValueError("symlink rejected: " + name)
        if not file.is_file():
            raise ValueError("special file rejected: " + name)
        if file.stat().st_size > rule.get("max_bytes", 1_000_000):
            raise ValueError("policy oversized file: " + name)
        if rule.get("data_only"):
            data = file.read_bytes()
            if file.suffix.lower() not in DATA_SUFFIXES or file.stat().st_mode & 0o111:
                raise ValueError("data file type/mode rejected: " + name)
            try:
                text = data.decode("utf-8")
            except UnicodeError as exc:
                raise ValueError("data must be UTF-8: " + name) from exc
            if "\x00" in text or re.search(
                r"(?im)^\s*(#!|<\?(?:php|=)|<script\b|import\s|from\s+\w+\s+import\b|(?:exec|eval)\s*\()",
                text,
            ):
                raise ValueError("executable-looking data rejected: " + name)
            if file.suffix.lower() == ".json":
                import json

                json.loads(text)
