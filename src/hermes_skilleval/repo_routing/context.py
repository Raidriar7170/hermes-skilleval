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


@dataclass(frozen=True)
class FragmentBudget:
    """Separate discovery, scanning, parsing and presentation limits for v2."""

    max_entries: int = 4096
    max_files: int = 96
    scan_total_bytes: int = 4194304
    scan_file_bytes: int = 524288
    parse_bytes: int = 262144
    max_hits: int = 256
    max_snippets: int = 8
    snippet_lines: int = 48
    output_bytes: int = 16000
    scan_seconds: float = 5.0

    def __post_init__(self):
        if any(v <= 0 for v in asdict(self).values()):
            raise ValueError("positive fragment budgets required")


def extract_fragments(root, request, environment, budget=None):
    """Re-extract bounded current bytes; never trust a cache for unread regions.

    Full-file hashes are emitted only when every byte was read. Windows are
    literal source, not purported AST relationships. Unknown coverage stays partial.
    """
    budget = budget or FragmentBudget()
    root = Path(root).resolve()
    if not root.is_dir() or not request.strip():
        raise ValueError("snapshot directory and public request required")
    started = time.monotonic()
    excluded = {
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
    explicit = set(re.findall(r"[\w/-]+\.py\b", request))
    terms = set(re.findall(r"[a-zA-Z_]\w{2,}", request.lower()))
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "should",
        "must",
        "when",
        "not",
        "without",
        "existing",
        "public",
        "python",
        "return",
    }
    terms -= stop
    paths, missing, pending, entries = [], [], [root], 0
    while pending and entries < budget.max_entries:
        directory = pending.pop(0)
        batch = []
        try:
            with os.scandir(directory) as stream:
                for entry in stream:
                    entries += 1
                    if entries > budget.max_entries:
                        missing.append(
                            {
                                "path": ".",
                                "reason": "enumeration_budget",
                                "critical": False,
                            }
                        )
                        break
                    batch.append(entry)
        except OSError:
            missing.append(
                {
                    "path": directory.relative_to(root).as_posix(),
                    "reason": "directory_unreadable",
                    "critical": False,
                }
            )
            continue
        for entry in sorted(batch, key=lambda e: e.name):
            if (
                entry.name.startswith(".")
                or entry.name in excluded
                or entry.is_symlink()
            ):
                continue
            path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False) and (
                path.suffix == ".py" or path.name in {"pyproject.toml", "setup.cfg"}
            ):
                paths.append(path)

    def priority(path):
        name = path.relative_to(root).as_posix()
        return (
            name not in explicit,
            name.startswith(("tests/", "test/")),
            -len(terms & set(re.findall(r"\w+", name.lower()))),
            name,
        )

    paths.sort(key=priority)
    available = {p.relative_to(root).as_posix() for p in paths}
    for name in sorted(explicit - available):
        missing.append(
            {"path": name, "reason": "explicit_path_unavailable", "critical": True}
        )
    scanned, hits, total, fragments, sources = [], 0, 0, [], {}
    for path in paths[: budget.max_files]:
        name = path.relative_to(root).as_posix()
        critical = name in explicit
        remaining = min(budget.scan_file_bytes, budget.scan_total_bytes - total)
        if remaining <= 0 or time.monotonic() - started > budget.scan_seconds:
            missing.append(
                {"path": name, "reason": "scan_budget", "critical": critical}
            )
            continue
        try:
            # O_NOFOLLOW protects a final-component symlink swap; ancestry is
            # checked too. Concurrent metadata changes invalidate this extraction.
            if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
                raise OSError("symlink")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                data = stream.read(remaining)
                after = os.fstat(stream.fileno())
            current = path.stat(follow_symlinks=False)

            def signature(stat):
                return stat.st_ino, stat.st_size, stat.st_mtime_ns

            if signature(before) != signature(after) or signature(after) != signature(
                current
            ):
                missing.append(
                    {
                        "path": name,
                        "reason": "concurrent_modification",
                        "critical": True,
                    }
                )
                continue
        except OSError:
            missing.append({"path": name, "reason": "read_error", "critical": critical})
            continue
        total += len(data)
        complete = len(data) == before.st_size
        sources[name] = {
            "bytes_read": len(data),
            "size": before.st_size,
            "read_sha256": hashlib.sha256(data).hexdigest(),
            "full_file_sha256": hashlib.sha256(data).hexdigest() if complete else None,
            "unscanned_bytes": [len(data), before.st_size] if not complete else None,
        }
        scanned.append(name)
        if not complete:
            missing.append(
                {"path": name, "reason": "file_scan_budget", "critical": critical}
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            missing.append({"path": name, "reason": "encoding", "critical": critical})
            continue
        lines = text.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line.encode()))
        declarations = []
        if complete and len(data) <= budget.parse_bytes and name.endswith(".py"):
            try:
                tree = ast.parse(text)
                declarations = [
                    (n.lineno, n.end_lineno, n.name)
                    for n in ast.walk(tree)
                    if isinstance(
                        n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
                ]
            except (SyntaxError, ValueError, RecursionError):
                missing.append(
                    {
                        "path": name,
                        "reason": "ast_parse_raw_windows_used",
                        "critical": False,
                    }
                )
        if not declarations:
            declarations = [
                (i + 1, min(i + budget.snippet_lines, len(lines)), m.group(1))
                for i, line in enumerate(lines)
                if (m := re.match(r"\s*(?:async\s+)?(?:def|class)\s+(\w+)", line))
            ]
        for first, last, symbol in declarations:
            words = set(symbol.lower().split("_"))
            relevance = 10 * (symbol.lower() in terms) + len(words & terms)
            if symbol[:1].isupper():
                relevance *= 0.25
            if name.startswith(("tests/", "test/")):
                relevance *= 0.5
            if not relevance:
                continue
            hits += 1
            if hits > budget.max_hits:
                break
            end = min(last, first + budget.snippet_lines - 1)
            snippet = "".join(lines[first - 1 : end])
            fragments.append(
                {
                    "path": name,
                    "symbol": symbol,
                    "lines": [first, end],
                    "bytes": [offsets[first - 1], offsets[end]],
                    "snippet": snippet,
                    "source_sha256": sources[name]["read_sha256"],
                    "kind": "literal_source_window",
                    "declaration_complete": end == last and complete,
                    "relevance": relevance,
                    "critical_path": critical,
                }
            )
        if hits > budget.max_hits:
            missing.append({"path": name, "reason": "hit_budget", "critical": critical})
            break
    for path in paths[budget.max_files :]:
        name = path.relative_to(root).as_posix()
        missing.append(
            {"path": name, "reason": "file_count_budget", "critical": name in explicit}
        )
    fragments.sort(
        key=lambda f: (-f["critical_path"], -f["relevance"], f["path"], f["lines"][0])
    )
    chosen, output_used = [], 0
    for fragment in fragments:
        cost = len(fragment["snippet"].encode())
        if (
            len(chosen) >= budget.max_snippets
            or output_used + cost > budget.output_bytes
        ):
            continue
        chosen.append(fragment)
        output_used += cost
    critical_missing = [m for m in missing if m["critical"]]
    state = (
        "unavailable"
        if any(
            m["reason"]
            in {
                "explicit_path_unavailable",
                "read_error",
                "concurrent_modification",
                "encoding",
            }
            for m in critical_missing
        )
        else ("partial" if critical_missing or not chosen else "usable")
    )
    # A hit is a concrete fact, not proof of complete coverage. Hard limits are
    # observable uncertainty even when no explicit path was requested.
    if state == "usable" and any(
        m["reason"]
        in {"enumeration_budget", "scan_budget", "file_scan_budget", "hit_budget"}
        for m in missing
    ):
        state = "partial"
    sections = [
        f"Context state: {state}. Network: {environment.get('network', 'unknown')}. Source windows are incomplete; verify conditions in source."
    ]
    for f in chosen:
        sections.append(f"{f['path']}:{f['lines'][0]}-{f['lines'][1]}\n{f['snippet']}")
    summary = "\n".join(sections)
    identity = digest(
        ["repo-context-v2", request, environment, asdict(budget), sources]
    )
    return {
        "schema": "repo-context-v2",
        "state": state,
        "supported": state == "usable",
        "support_reason": state,
        "cache_key": identity,
        "snapshot_id": digest(sources),
        "snapshot_scope": "bounded_read_bytes_only; unread changes not observed; no cache reuse",
        "public_request_hash": hashlib.sha256(request.encode()).hexdigest(),
        "matched_symbols": chosen,
        "entrypoints": [],
        "related_public_tests": [],
        "imports": [],
        "environment": environment,
        "missing": missing,
        "source_hashes": sources,
        "summary": summary,
        "files_scanned": len(scanned),
        "entries_enumerated": entries,
        "truncated": bool(missing or len(chosen) < len(fragments)),
        "budget": asdict(budget),
        "cost": {
            "wall_seconds": time.monotonic() - started,
            "bytes_read": total,
            "output_bytes": output_used,
            "cache_hit": False,
        },
    }
