"""Bounded static facts from an explicitly supplied source snapshot, never Git history."""

from __future__ import annotations

import ast
import configparser
import os
import hashlib
import json
import re
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

VERSION = "repo-context-v1"


@dataclass(frozen=True)
class ContextBudget:
    max_entries: int = 4096
    max_files: int = 128
    max_file_bytes: int = 131072
    max_total_bytes: int = 2097152
    max_snippets: int = 12
    snippet_chars: int = 400
    summary_chars: int = 7000

    def __post_init__(self):
        if any(v <= 0 for v in asdict(self).values()):
            raise ValueError("positive context budgets required")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def extract(
    root: Path, request: str, environment: dict, budget=None, cache: Path | None = None
):
    start = time.monotonic()
    budget = budget or ContextBudget()
    root = root.resolve()
    if not root.is_dir() or not request.strip():
        raise ValueError("snapshot directory and public request required")
    # Explicit allowlist excludes reference/target controller data and credentials.
    forbidden = {
        ".git",
        ".codex",
        ".agents",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "reference",
        "target",
        "trusted",
        "artifacts",
        "runs",
    }
    paths, pending, enumerated = [], [root], 0
    enumeration_truncated = False
    while pending:
        directory = pending.pop()
        entries = []
        with os.scandir(directory) as stream:
            for entry in stream:
                enumerated += 1
                if enumerated > budget.max_entries:
                    enumeration_truncated = True
                    break
                entries.append(entry)
        for entry in sorted(entries, key=lambda v: v.name):
            if (
                entry.name in forbidden
                or entry.name.startswith(".")
                or entry.is_symlink()
            ):
                continue
            path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False) and (
                path.suffix == ".py"
                or path.name
                in {"pyproject.toml", "setup.cfg", "README.md", "CONTRIBUTING.md"}
            ):
                paths.append(path)
        if enumeration_truncated:
            break
    paths.sort()
    terms = set(re.findall(r"[A-Za-z_]\w{2,}", request.lower()))
    paths.sort(
        key=lambda p: (
            p.name not in {"pyproject.toml", "setup.cfg"},
            -len(terms & set(re.findall(r"\w+", str(p.relative_to(root)).lower()))),
            str(p.relative_to(root)),
        )
    )
    contents, hashes, missing = {}, {}, []
    if enumeration_truncated:
        missing.append({"path": ".", "reason": "enumeration_budget"})
    total = 0
    for path in paths[: budget.max_files]:
        name = path.relative_to(root).as_posix()
        size = path.stat().st_size
        if size > budget.max_file_bytes or total + size > budget.max_total_bytes:
            missing.append({"path": name, "reason": "byte_budget"})
            continue
        data = path.read_bytes()
        total += len(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
        try:
            contents[name] = data.decode("utf-8")
        except UnicodeDecodeError:
            missing.append({"path": name, "reason": "encoding"})
    key = digest(
        [
            VERSION,
            hashes,
            request,
            environment,
            asdict(budget),
            [str(p.relative_to(root)) for p in paths],
        ]
    )
    if cache and cache.exists():
        saved = json.loads(cache.read_text())
        if saved.get("cache_key") == key:
            saved["cost"] = {
                "wall_seconds": time.monotonic() - start,
                "bytes_read": total,
                "cache_hit": True,
            }
            return saved
    facts, symbols, tests = [], [], []
    imports: set[str] = set()
    for name, text in contents.items():
        lines = text.splitlines()
        if name == "pyproject.toml":
            try:
                config = tomllib.loads(text)
                for command, symbol in sorted(
                    config.get("project", {}).get("scripts", {}).items()
                ):
                    line = next(
                        (
                            i + 1
                            for i, v in enumerate(lines)
                            if command in v and str(symbol) in v
                        ),
                        None,
                    )
                    facts.append(
                        {
                            "kind": "cli",
                            "command": command,
                            "symbol": symbol,
                            "evidence": f"{name}:{line}",
                        }
                    )
            except (tomllib.TOMLDecodeError, AttributeError):
                missing.append({"path": name, "reason": "toml_parse"})
        if name == "setup.cfg":
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read_string(text)
                raw = parser.get("options.entry_points", "console_scripts", fallback="")
                for item in raw.splitlines():
                    if "=" in item:
                        command, symbol = (v.strip() for v in item.split("=", 1))
                        line = next(
                            (
                                i + 1
                                for i, v in enumerate(lines)
                                if command in v and symbol in v
                            ),
                            None,
                        )
                        facts.append(
                            {
                                "kind": "cli",
                                "command": command,
                                "symbol": symbol,
                                "evidence": f"{name}:{line}",
                            }
                        )
            except configparser.Error:
                missing.append({"path": name, "reason": "setup_cfg_parse"})
        if name.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                missing.append({"path": name, "reason": "ast_parse"})
                continue
            if ("/test" in "/" + name or name.startswith("tests/")) and terms & set(
                re.findall(r"\w+", text.lower())
            ):
                tests.append(name)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.update(a.name.split(".")[0] for a in node.names)
                    if isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module.split(".")[0])
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    words = set(
                        re.findall(r"[a-z]+", node.name.lower().replace("_", " "))
                    )
                    if node.name.lower() in terms or words & terms:
                        symbols.append(
                            {
                                "symbol": node.name,
                                "path": name,
                                "lines": [node.lineno, node.end_lineno],
                                "snippet": "\n".join(
                                    lines[
                                        node.lineno - 1 : min(
                                            node.lineno + 6,
                                            node.end_lineno or node.lineno,
                                        )
                                    ]
                                )[: budget.snippet_chars],
                            }
                        )
    symbols.sort(key=lambda s: (s["path"], s["lines"][0]))
    result = {
        "schema": VERSION,
        "cache_key": key,
        "snapshot_id": digest(hashes),
        "public_request_hash": hashlib.sha256(request.encode()).hexdigest(),
        "entrypoints": facts,
        "matched_symbols": symbols[: budget.max_snippets],
        "related_public_tests": sorted(tests)[:12],
        "imports": sorted(imports),
        "environment": environment,
        "missing": missing,
        "files_scanned": len(contents),
        "entries_enumerated": enumerated,
        "supported": any(name.endswith(".py") for name in contents) and not missing,
        "support_reason": "python_static_layout"
        if any(name.endswith(".py") for name in contents) and not missing
        else "unsupported_or_incomplete_context",
        "source_hashes": hashes,
        "truncated": bool(
            missing
            or len(paths) > budget.max_files
            or len(symbols) > budget.max_snippets
        ),
        "cost": {
            "wall_seconds": time.monotonic() - start,
            "bytes_read": total,
            "cache_hit": False,
        },
    }
    summary = json.dumps(
        {
            k: result[k]
            for k in [
                "entrypoints",
                "matched_symbols",
                "related_public_tests",
                "environment",
                "missing",
            ]
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    result["summary"] = summary[: budget.summary_chars]
    if len(summary) > budget.summary_chars:
        result["truncated"] = True
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def shared_prompt(request, context):
    return (
        request
        + "\n\nPublic pre-repair repository facts (static, incomplete; verify against source):\n"
        + context["summary"]
    )
