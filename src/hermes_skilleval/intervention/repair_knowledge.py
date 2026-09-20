"""Repository/version maintenance facts, extracted without a task or answer input.

Extraction is deliberately conservative: quoted contracts and observed guards,
not model-generated diagnoses. The source manifest is a pre-repair allowlist.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def token_count(text: str) -> int:
    import tiktoken

    return len(tiktoken.get_encoding("o200k_base").encode(text))


@dataclass(frozen=True)
class SourceSpan:
    path_or_public_url: str
    revision: str
    line_start: int
    line_end: int
    exact_excerpt: str


@dataclass(frozen=True)
class RepairKnowledgeUnit:
    unit_id: str
    repository: str
    source_revision: str
    kind: str
    applies_to: tuple[str, ...]
    preconditions: tuple[str, ...]
    statement: str
    verification_pattern: str | None
    source_spans: tuple[SourceSpan, ...]
    claim_role: str
    version_status: str
    dependencies: tuple[str, ...]
    serialized_payload: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["source_spans"] = tuple(SourceSpan(**s) for s in value["source_spans"])
        for key in ("applies_to", "preconditions", "dependencies"):
            value[key] = tuple(value[key])
        return cls(**value)


MAINTENANCE = re.compile(
    r"\b(?:must|cannot|raises?|errors?|except|invalid|preserv\w*|ensure\w*|"
    r"constraint\w*|required|default|return\w*|fail\w*|empty|None|type|unique)\b",
    re.I,
)


def _fragments(path, text):
    """Whole docstrings/paragraphs and complete guard branches, never conclusions alone."""
    lines = text.splitlines(keepends=True)
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        imports = tuple(
            sorted(
                {
                    n.module
                    for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module
                }
                | {
                    a.name
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Import)
                    for a in n.names
                }
            )
        )
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            symbol = path.removesuffix(".py").replace("/", ".") + "." + node.name
            if ast.get_docstring(node, clean=False):
                doc = node.body[0]
                yield (
                    doc.lineno,
                    doc.end_lineno,
                    symbol,
                    "documented_contract",
                    "invariant",
                    imports,
                )
            # A guard's complete condition accompanies its raise. Do not turn
            # this implementation into a normative contract.
            for child in node.body:
                if isinstance(child, ast.If) and any(
                    isinstance(n, ast.Raise) for n in ast.walk(child)
                ):
                    yield (
                        child.lineno,
                        child.end_lineno,
                        symbol,
                        "existing_behavior",
                        "precondition",
                        imports,
                    )
    elif path.endswith((".md", ".rst", ".txt")):
        # Paragraphs remain verbatim; version/change logs are excluded by caller.
        start = 0
        for i in range(len(lines) + 1):
            if i == len(lines) or not lines[i].strip():
                if i > start:
                    yield start + 1, i, path, "documented_contract", "invariant", ()
                start = i + 1


def build_units(base_corpus, source_manifest, *, limit=40, count_tokens=token_count):
    """Extract an issue-independent, round-robin set of complete source facts.

    Manifest entries must be produced from an exact base tree, not a working
    repair checkout. Unknown or conflicting versions do not enter this builder.
    No reference/test-patch path is ever discovered by recursive traversal.
    """
    manifest = source_manifest
    if set(manifest) - {"repository", "revision", "scope", "files", "license"}:
        raise ValueError("builder manifest contains non-corpus fields")
    if manifest["scope"] != "pre_repair_base" or not re.fullmatch(
        r"[0-9a-f]{40}", manifest["revision"]
    ):
        raise ValueError("exact pre-repair revision required")
    root = Path(base_corpus).resolve()
    buckets = {}
    for name, identity in sorted(manifest["files"].items()):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid corpus path")
        if any(
            p in {"reference", "hidden", "test_patch", ".git"} for p in relative.parts
        ):
            raise ValueError("forbidden corpus source")
        path = root / relative
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError("corpus path escapes base")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != identity:
            raise ValueError("corpus source changed")
        try:
            text = data.decode()
        except UnicodeError:
            continue
        if re.search(r"(?:change.?log|release.?notes|history)", name, re.I):
            continue
        lines = text.splitlines(keepends=True)
        bucket = []
        for start, end, symbol, role, kind, dependencies in _fragments(name, text):
            excerpt = "".join(lines[start - 1 : end])
            if not MAINTENANCE.search(excerpt) or len(excerpt.strip()) < 55:
                continue
            span = SourceSpan(name, manifest["revision"], start, end, excerpt)
            unit_id = (
                "rku-"
                + digest(
                    json.dumps([manifest["repository"], asdict(span)], sort_keys=True)
                )[:20]
            )
            qualifier = (
                "Documented contract (quoted)"
                if role == "documented_contract"
                else "Observed implementation; correctness is NOT established"
            )
            payload = (
                f"[{unit_id}] {qualifier}\nApplies to: {symbol}\n"
                f"Source: {manifest['repository']}@{manifest['revision']}:{name}:{start}-{end}\n"
                "Conditions and statement (complete source fragment):\n" + excerpt
            )
            # Reject oversize atoms instead of dropping a prerequisite or quote.
            if count_tokens(payload) > 500:
                continue
            bucket.append(
                RepairKnowledgeUnit(
                    unit_id,
                    manifest["repository"],
                    manifest["revision"],
                    kind,
                    (symbol,),
                    (
                        "See complete quoted source conditions; no additional conditions inferred.",
                    ),
                    excerpt,
                    None,
                    (span,),
                    role,
                    "supported",
                    dependencies,
                    payload,
                )
            )
        if bucket:
            # Allocate across maintenance components, then files. A repository
            # with many alphabetically early files must not crowd out later
            # components before the first round completes.
            component = "/".join(Path(name).parts[:3])
            buckets.setdefault(component, []).extend(bucket)
    # Round-robin prevents one large module from exhausting the library budget.
    units = []
    while buckets and len(units) < limit:
        for name in list(buckets):
            units.append(buckets[name].pop(0))
            if not buckets[name]:
                del buckets[name]
            if len(units) == limit:
                break
    return units


PACK_HEADER = "Public maintenance knowledge. Verify applicability against the request and current code; quoted implementation is not proof of correctness.\n\n"


def render_units(units):
    return (
        PACK_HEADER + "\n\n".join(u.serialized_payload for u in units) if units else ""
    )
