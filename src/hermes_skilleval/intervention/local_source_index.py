"""Exact-base, task-independent source metadata and bounded complete views.

The caller supplies ONLY a legal base directory. No task/answer paths or future
checkout enter discovery. Metadata is never capped by an early unit count.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from .repair_knowledge import RepairKnowledgeUnit, SourceSpan, token_count

EXCLUDED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "vendor",
    "vendored",
    "_vendor",
    ".venv",
    "venv",
    "reference",
    "evaluation",
    "hidden",
    "test_patch",
    "dist",
    "build",
}


@dataclass
class SourceNode:
    node_id: str
    path: str
    symbol: str
    line_start: int
    line_end: int
    role: str
    kind: str
    text: str
    conditions: tuple[str, ...]
    imports: dict[str, str]
    calls: tuple[str, ...]
    content_sha256: str
    parent: str | None = None


def _id(path, symbol, start, end):
    return hashlib.sha256(json.dumps([path, symbol, start, end]).encode()).hexdigest()[
        :24
    ]


def _module(path):
    return path.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def _imports(tree, module, is_package=False):
    result = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.pop(n.name, None)
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name):
                        result.pop(child.id, None)
        if isinstance(n, ast.Import):
            for a in n.names:
                result[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0]
                )
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                parts = module.split(".") if is_package else module.split(".")[:-1]
                base = ".".join(
                    parts[: len(parts) - n.level + 1] + ([base] if base else [])
                )
            for a in n.names:
                if a.name != "*":
                    result[a.asname or a.name] = f"{base}.{a.name}"
    return result


def extract_nodes(path, text):
    lines = text.splitlines(keepends=True)
    module = _module(path)
    in_test_tree = any(p in {"test", "tests", "testing"} for p in Path(path).parts)
    public_test = in_test_tree and (
        Path(path).name.startswith("test_")
        or (
            "targets" in Path(path).parts
            and Path(path).suffix in {".yml", ".yaml", ".sh"}
        )
    )

    def make(
        start,
        end,
        symbol,
        kind,
        role,
        conditions=(),
        imports=None,
        calls=(),
        parent=None,
    ):
        excerpt = "".join(lines[start - 1 : end])
        return SourceNode(
            _id(path, symbol, start, end),
            path,
            symbol,
            start,
            end,
            role,
            kind,
            excerpt,
            tuple(conditions),
            imports or {},
            tuple(calls),
            hashlib.sha256(excerpt.encode()).hexdigest(),
            parent,
        )

    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            # Retain complete metadata even for older Python dialects.
            return [
                make(
                    1,
                    len(lines),
                    module,
                    "unparsed_module",
                    "public_test_example" if public_test else "existing_behavior",
                )
            ], "syntax_unparsed"
        imports = _imports(tree, module, path.endswith("/__init__.py"))
        nodes = []

        def visit(body, prefix, conditions=(), parent=None):
            for n in body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbol = f"{prefix}.{n.name}"
                    calls = []
                    # Never traverse nested lexical scopes as caller-owned calls.
                    scoped = []
                    pending = list(n.body)
                    shadowed = set()
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        shadowed.update(
                            a.arg
                            for a in (
                                *n.args.posonlyargs,
                                *n.args.args,
                                *n.args.kwonlyargs,
                            )
                        )
                        shadowed.update(
                            a.arg for a in (n.args.vararg, n.args.kwarg) if a
                        )
                    while pending:
                        item = pending.pop()
                        if isinstance(
                            item,
                            (
                                ast.FunctionDef,
                                ast.AsyncFunctionDef,
                                ast.ClassDef,
                                ast.Lambda,
                            ),
                        ):
                            if hasattr(item, "name"):
                                shadowed.add(item.name)
                            continue
                        if isinstance(item, ast.Name) and isinstance(
                            item.ctx, ast.Store
                        ):
                            shadowed.add(item.id)
                        if (
                            isinstance(
                                item, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)
                            )
                            and item.name
                        ):
                            shadowed.add(item.name)
                        if isinstance(item, ast.MatchMapping) and item.rest:
                            shadowed.add(item.rest)
                        if isinstance(item, (ast.Import, ast.ImportFrom)):
                            shadowed.update(
                                a.asname or a.name.split(".")[0] for a in item.names
                            )
                        scoped.append(item)
                        pending.extend(ast.iter_child_nodes(item))
                    # Classes do not execute calls inside their methods here.
                    for c in scoped:
                        if isinstance(c, ast.Call):
                            f = c.func
                            if isinstance(f, ast.Name) and f.id not in shadowed:
                                calls.append(f.id)
                            elif (
                                isinstance(f, ast.Attribute)
                                and isinstance(f.value, ast.Name)
                                and f.value.id not in shadowed
                            ):
                                calls.append(f.value.id + "." + f.attr)
                    node = make(
                        min([n.lineno] + [d.lineno for d in n.decorator_list]),
                        n.end_lineno,
                        symbol,
                        "class" if isinstance(n, ast.ClassDef) else "function",
                        "public_test_example" if public_test else "existing_behavior",
                        conditions,
                        {k: v for k, v in imports.items() if k not in shadowed},
                        calls,
                        parent,
                    )
                    nodes.append(node)
                    visit(n.body, symbol, conditions, node.node_id)
                elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                    value = n.value
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            role = (
                                "documented_contract"
                                if target.id in {"DOCUMENTATION", "EXAMPLES", "RETURN"}
                                and isinstance(value, ast.Constant)
                                and isinstance(value.value, str)
                                else "public_test_example"
                                if public_test
                                else "existing_behavior"
                            )
                            nodes.append(
                                make(
                                    n.lineno,
                                    n.end_lineno,
                                    f"{prefix}.{target.id}",
                                    "assignment",
                                    role,
                                    conditions,
                                    imports,
                                    parent=parent,
                                )
                            )
                elif (
                    isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Constant)
                    and isinstance(n.value.value, str)
                ):
                    nodes.append(
                        make(
                            n.lineno,
                            n.end_lineno,
                            prefix + ".__doc__",
                            "docstring",
                            "documented_contract",
                            conditions,
                            imports,
                            parent=parent,
                        )
                    )
                elif isinstance(n, ast.If):
                    # Whole branches preserve return paths, else and conditions.
                    nodes.append(
                        make(
                            n.lineno,
                            n.end_lineno,
                            prefix + f".branch_{n.lineno}",
                            "branch",
                            "public_test_example"
                            if public_test
                            else "existing_behavior",
                            conditions,
                            imports,
                            parent=parent,
                        )
                    )
                    # Nested definitions only; do not extract an else clause while
                    # losing the negation of its controlling condition.
                elif isinstance(n, (ast.Try, ast.For, ast.While, ast.With)):
                    nodes.append(
                        make(
                            n.lineno,
                            n.end_lineno,
                            prefix + f".block_{n.lineno}",
                            "block",
                            "public_test_example"
                            if public_test
                            else "existing_behavior",
                            conditions,
                            imports,
                            parent=parent,
                        )
                    )

        visit(tree.body, module)
        # Conditional/loop-local declarations remain searchable even when no
        # safe bounded view was extracted by the direct-body traversal above.
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        known = {(n.line_start, n.line_end, n.kind) for n in nodes}
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            if (start, node.end_lineno, kind) in known:
                continue
            ancestor = parents.get(node)
            names, conditions = [], []
            enclosing_function = None
            while ancestor is not None:
                if isinstance(
                    ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    names.append(ancestor.name)
                    if enclosing_function is None and isinstance(
                        ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        enclosing_function = ancestor
                if isinstance(ancestor, ast.If):
                    # Whole controlling branch text is retained as a condition,
                    # avoiding an invented polarity for nested else bodies.
                    conditions.append(
                        ast.get_source_segment(text, ancestor) or "unknown"
                    )
                ancestor = parents.get(ancestor)
            symbol = ".".join([module, *reversed(names), node.name])
            enclosing_id = None
            if enclosing_function is not None:
                enclosing_start = min(
                    [enclosing_function.lineno]
                    + [d.lineno for d in enclosing_function.decorator_list]
                )
                enclosing_id = next(
                    (
                        n.node_id
                        for n in nodes
                        if n.line_start == enclosing_start
                        and n.line_end == enclosing_function.end_lineno
                        and n.kind == "function"
                    ),
                    None,
                )
                # Unknown enclosing metadata remains an explicit non-packable dependency.
                enclosing_id = enclosing_id or "unresolved-enclosing-function"
            nodes.append(
                make(
                    start,
                    node.end_lineno,
                    symbol,
                    kind,
                    "public_test_example" if public_test else "existing_behavior",
                    conditions,
                    imports,
                    parent=enclosing_id,
                )
            )
        if not nodes:
            nodes = [
                make(
                    1,
                    len(lines),
                    module,
                    "module",
                    "public_test_example" if public_test else "existing_behavior",
                    imports=imports,
                )
            ]
        return nodes, "parsed"
    nodes = []
    # Whole paragraphs; fenced snippets stay together.
    start = 0
    fence = False
    for i, line in enumerate(lines + [""]):
        if line.lstrip().startswith("```"):
            fence = not fence
        if (i == len(lines) or not line.strip()) and not fence:
            if i > start:
                nodes.append(
                    make(
                        start + 1,
                        i,
                        f"{path}:{start + 1}",
                        "paragraph",
                        "public_test_example"
                        if public_test
                        else "documented_contract"
                        if Path(path).suffix in {".md", ".rst", ".txt"}
                        else "existing_behavior",
                    )
                )
            start = i + 1
    return nodes, "text"


def build_index(base, *, repository, revision):
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("Exact base revision required")
    base = Path(base).resolve()
    nodes = []
    files = {}
    excluded = {}
    parsing = {}
    for p in sorted(base.rglob("*")):
        relative = p.relative_to(base).as_posix()
        parts = Path(relative).parts
        reason = "excluded_scope" if any(x in EXCLUDED_PARTS for x in parts) else None
        if p.is_symlink():
            reason = "symlink"
        if p.is_dir():
            continue
        if reason is None and re.search(
            r"(?:change.?log|release.?notes|porting_guide)", relative, re.I
        ):
            reason = "historical_or_version_notes"
        if reason:
            excluded[relative] = reason
            continue
        data = p.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            excluded[relative] = "non_utf8"
            continue
        # Source languages and extensionless scripts are admitted by content.
        # Reject binary control bytes even when the byte stream decodes as UTF-8.
        if any(ord(c) < 32 and c not in "\t\n\r\f\b" for c in text):
            excluded[relative] = "binary"
            continue
        header = "\n".join(text.splitlines()[:80])
        if re.search(
            r"upstream vendored|vendored (?:file|copy)|based on\s*#?\s*Lib/[^\n]+ of cpython",
            header,
            re.I,
        ):
            excluded[relative] = "declared_third_party_source"
            continue
        if re.search(
            r"(?:auto.?generated|generated file|do not edit)",
            "\n".join(text.splitlines()[:10]),
            re.I,
        ):
            excluded[relative] = "declared_generated"
            continue
        files[relative] = hashlib.sha256(data).hexdigest()
        found, status = extract_nodes(relative, text)
        nodes.extend(found)
        parsing[relative] = status
    # Canonical aliases account for conventional Python source roots without
    # guessing object receiver types or dynamic dispatch.
    symbols = {}
    for n in nodes:
        if n.kind not in {"function", "class", "assignment"}:
            continue
        for alias in {n.symbol, n.symbol.removeprefix("lib.").removeprefix("src.")}:
            symbols.setdefault(alias, []).append(n.node_id)
    edges = []
    callable_ids = {n.node_id for n in nodes if n.kind in {"function", "class"}}
    for n in nodes:
        for call in n.calls:
            first, *rest = call.split(".")
            target = (
                ".".join([n.imports[first], *rest])
                if first in n.imports
                else _module(n.path) + "." + call
                if not rest
                else None
            )
            if target and len(symbols.get(target, [])) == 1:
                target_id = symbols[target][0]
                if target_id != n.node_id and target_id in callable_ids:
                    edges.append(
                        {
                            "source": n.node_id,
                            "target": target_id,
                            "kind": "direct_call",
                            "evidence": call,
                        }
                    )
        for binding, target in n.imports.items():
            if len(symbols.get(target, [])) == 1:
                edges.append(
                    {
                        "source": n.node_id,
                        "target": symbols[target][0],
                        "kind": "import_binding",
                        "evidence": binding + "=" + target,
                    }
                )
    return {
        "repository": repository,
        "revision": revision,
        "scope": "pre_repair_base",
        "files": files,
        "excluded": excluded,
        "parsing": parsing,
        "nodes": [asdict(n) for n in nodes],
        "edges": edges,
        "coverage": {
            "files": len(files),
            "nodes": len(nodes),
            "excluded_files": len(excluded),
            "no_prequery_unit_cap": True,
        },
    }


def materialize(index, node, *, max_tokens=1100, count_tokens=token_count):
    """Whole syntax unit, otherwise explicitly not packable; metadata survives."""
    if (
        node["kind"] == "assignment"
        and node["parent"]
        and node["role"] != "documented_contract"
    ):
        # A local assignment without its controlling function/test setup is not
        # a complete usable view. Parent metadata remains globally searchable.
        return None
    if node["kind"] == "function" and node["parent"]:
        parent = next(
            (n for n in index["nodes"] if n["node_id"] == node["parent"]), None
        )
        if parent is None or parent["kind"] == "function":
            # A closure needs its enclosing bindings. Retain metadata and use
            # the enclosing function view instead of a misleading bare closure.
            return None
    symbol = node["symbol"]
    text = node["text"]
    role = node["role"]
    start = node["line_start"]
    if node["kind"] in {"branch", "block"} and node["parent"]:
        parent = next(
            (n for n in index["nodes"] if n["node_id"] == node["parent"]), None
        )
        if parent is None:
            return None
        # Keep preceding guards/bindings and the enclosing signature. The
        # selected direct-body branch is whole; later behavior is not claimed.
        start = parent["line_start"]
        text = "".join(
            parent["text"].splitlines(keepends=True)[: node["line_end"] - start + 1]
        )
    span = SourceSpan(node["path"], index["revision"], start, node["line_end"], text)
    uid = "local-" + node["node_id"]
    if start != node["line_start"]:
        uid += "-" + hashlib.sha256(text.encode()).hexdigest()[:8]
    conditions = tuple(node["conditions"])
    payload = (
        f"[{uid}] Role: {role}\nApplies to: {symbol}\n"
        f"Source: {index['repository']}@{index['revision']}:{node['path']}:{start}-{node['line_end']}\n"
        f"Preconditions: {json.dumps(conditions) if conditions else 'unknown; consult complete source'}\n"
        "Complete source (existing behavior is not proof of correctness):\n" + text
    )
    if count_tokens(payload) > max_tokens:
        return None
    return RepairKnowledgeUnit(
        uid,
        index["repository"],
        index["revision"],
        node["kind"],
        (symbol,),
        conditions,
        text,
        text if role == "public_test_example" else None,
        (span,),
        role,
        "supported",
        tuple(sorted(set(node["imports"].values()))),
        payload,
    )


def include_legacy(index, base, units):
    """Keep each old source atom addressable in the full index for ablation.

    The same new view materializer is used in both full/old-subset retrieval;
    legacy score, payload and obligation fields are never used.
    """
    root = Path(base).resolve()
    existing = {
        (n["path"], n["line_start"], n["line_end"], n["role"]): n
        for n in index["nodes"]
    }
    legacy_ids = []
    for unit in units:
        if (
            unit.repository != index["repository"]
            or unit.source_revision != index["revision"]
        ):
            raise ValueError("Legacy unit base mismatch")
        for span in unit.source_spans:
            relative = Path(span.path_or_public_url)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or relative.as_posix() not in index["files"]
            ):
                raise ValueError("Legacy source outside legal index")
            path = root / relative
            if path.is_symlink():
                raise ValueError("Legacy symlink source")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != index["files"][relative.as_posix()]:
                raise ValueError("Legacy base changed")
            text = "".join(
                data.decode().splitlines(keepends=True)[
                    span.line_start - 1 : span.line_end
                ]
            )
            if text != span.exact_excerpt:
                raise ValueError("Legacy excerpt changed")
            key = (relative.as_posix(), span.line_start, span.line_end, unit.claim_role)
            node = existing.get(key)
            if node is None:
                symbol = unit.applies_to[0] if unit.applies_to else relative.as_posix()
                node = asdict(
                    SourceNode(
                        "legacy-" + unit.unit_id,
                        relative.as_posix(),
                        symbol,
                        span.line_start,
                        span.line_end,
                        unit.claim_role,
                        "legacy_complete_fragment",
                        text,
                        (),
                        {},
                        (),
                        hashlib.sha256(text.encode()).hexdigest(),
                    )
                )
                index["nodes"].append(node)
                existing[key] = node
            legacy_ids.append(node["node_id"])
    index["legacy_subset_node_ids"] = sorted(set(legacy_ids))
    index["coverage"]["nodes"] = len(index["nodes"])
    index["coverage"]["legacy_atoms"] = len(legacy_ids)
    return index
