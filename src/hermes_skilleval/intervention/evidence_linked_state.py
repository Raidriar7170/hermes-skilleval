"""Complete public request spans and conservative checkpoint-local observations.

No outcome, reference implementation or future event is accepted by this API.
Semantic associations are separately proposed and validated against these spans.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import re
import shlex

from .state import FILE, is_test_command


@dataclass
class Requirement:
    requirement_id: str
    parent_requirement: str
    verbatim_span: dict
    subject: tuple[str, ...]
    condition_text: str
    expected_text: str
    case_family: tuple[str, ...]
    status: str = "unverified"
    observation_refs: list[str] = field(default_factory=list)
    conflict: bool = False


@dataclass
class Observation:
    observation_id: str
    event_index: int
    turn_index: int | None
    command: str | None
    exit_status: int | None
    source_version: str | None
    output: str
    output_span: dict
    symbols: tuple[str, ...]
    paths: tuple[str, ...]
    kind: str
    lifecycle: str
    completeness: str
    check_scope: str | None = None
    requirement_links: list[dict] = field(default_factory=list)
    superseded_by: str | None = None


def request_ledger(request):
    """Keep complete blocks, including code fences, without a first-N cap.

    Every non-whitespace character belongs to an obligation or an unresolved
    block. Paragraphs outside normative sections are retained but not silently
    promoted into additional weighted obligations. Whole conditions stay intact.
    """
    lines = request.splitlines(keepends=True)
    blocks, start, offset, fence = [], 0, 0, False
    for line in lines:
        boundary = not fence and (
            not line.strip() or re.match(r"\s*(?:[-*] |#{1,6} )", line)
        )
        if boundary and request[start:offset].strip():
            blocks.append((start, offset))
            start = offset
        if not line.strip() and not fence:
            start = offset + len(line)
        if line.lstrip().startswith("```"):
            fence = not fence
        offset += len(line)
        if not fence and re.match(r"\s*#{1,6} ", line):
            blocks.append((start, offset))
            start = offset
    if request[start:offset].strip():
        blocks.append((start, offset))
    # Interface records often separate Type/Name/Path/Description with blank
    # lines. Keep the complete numbered declaration as one parent obligation.
    merged = []
    interface = False
    for start, end in blocks:
        text = request[start:end].strip()
        child = re.match(r"([ \t]+)[-*]\s", request[start:end])
        previous = (
            re.match(r"([ \t]*)[-*]\s", request[merged[-1][0] : merged[-1][1]])
            if merged
            else None
        )
        if child and previous and len(child[1]) > len(previous[1]):
            merged[-1] = (merged[-1][0], end)
            continue
        if text.startswith("#"):
            interface = "public interface" in text.lower()
        continuation = (
            interface
            and not text.startswith("#")
            and not re.match(r"\d+\.", text)
            and not text.startswith(
                ("Shared environment:", "Available skills:", "Execution environment:")
            )
        )
        if (
            continuation
            and merged
            and not request[merged[-1][0] : merged[-1][1]].lstrip().startswith("#")
        ):
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    blocks = merged
    requirements, unresolved = [], []
    section = ""
    normative = False
    for start, end in blocks:
        text = request[start:end]
        stripped = text.strip()
        span = {"field": "request", "start": start, "end": end}
        if stripped.startswith("#"):
            section = stripped.lower()
            normative = bool(
                re.search(r"requirements|expected|public interface", section)
            )
            unresolved.append({"span": span, "text": text, "reason": "heading"})
            continue
        if stripped.startswith(
            ("Shared environment:", "Available skills:", "Execution environment:")
        ):
            unresolved.append(
                {"span": span, "text": text, "reason": "execution_context"}
            )
            normative = False
            continue
        if re.fullmatch(
            r"No new interfaces? (?:are |is )?introduced[.\s]*", stripped, re.I
        ):
            unresolved.append(
                {"span": span, "text": text, "reason": "interface_scope_metadata"}
            )
            continue
        is_requirement = normative or bool(
            re.search(r"\b(?:must|shall|should|required to)\b", text, re.I)
        )
        if not is_requirement:
            unresolved.append(
                {"span": span, "text": text, "reason": "context_or_unresolved"}
            )
            continue
        rid = "req-" + hashlib.sha256(f"{start}:{end}:{text}".encode()).hexdigest()[:16]
        families = tuple(
            name
            for name, pattern in (
                ("list", r"\blist|\belement"),
                ("mapping", r"dict|mapping"),
                ("exception", r"error|exception|raise"),
                ("scalar", r"string|scalar"),
                ("compatibility", r"compatib|existing|unchanged"),
            )
            if re.search(pattern, text, re.I)
        ) or ("other",)
        requirements.append(
            Requirement(
                rid,
                rid,
                span,
                tuple(sorted(set(re.findall(r"`([\w.]+)`", text)))),
                text,
                text,
                families,
            )
        )
    return requirements, unresolved


def _scope(command):
    """Exact test invocation ignoring shell wrapper and environment assignments.

    Different executable paths remain distinct: success is not evidence that
    a failed interpreter is now healthy. No test-file overlap clears a failure.
    """
    try:
        args = shlex.split(command)
        if (
            len(args) >= 3
            and args[0].rsplit("/", 1)[-1] in {"sh", "bash", "zsh"}
            and "c" in args[1]
        ):
            return _scope(args[2])
    except ValueError:
        return None
    for i, arg in enumerate(args):
        exe = arg.rsplit("/", 1)[-1]
        if exe in {"pytest", "py.test"} or (
            exe.startswith("python")
            and args[i + 1 : i + 3] in [["-m", "pytest"], ["-m", "unittest"]]
        ):
            return shlex.join(args[i:])
    return None


def simple_command(command):
    """Conservatively reject compound shell text as source-version evidence."""
    try:
        args = shlex.split(command)
        if (
            len(args) >= 3
            and args[0].rsplit("/", 1)[-1] in {"sh", "bash", "zsh"}
            and "c" in args[1]
        ):
            return simple_command(args[2])
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        return (
            bool(args)
            and not any(token and all(c in ";&|<>()" for c in token) for token in lexer)
            and "$(" not in command
            and "`" not in command
            and "\n" not in command
        )
    except ValueError:
        return False


def observations(events, *, checkpoint_event_count, initial_source_version=None):
    if checkpoint_event_count != len(events):
        raise ValueError("Pass exactly the visible checkpoint prefix; no future events")
    result, version = [], initial_source_version
    turn = None
    for index, event in enumerate(events):
        params = event.get("params", {})
        if event.get("method") == "turn/completed":
            turn = (turn or 0) + 1
        if event.get("method") != "item/completed":
            continue
        item = params.get("item", {})
        kind = item.get("type")
        oid = f"event-{index}"
        if kind == "fileChange":
            paths = tuple(
                sorted(
                    c.get("path", "") for c in item.get("changes", []) if c.get("path")
                )
            )
            # A monotonic observed-change marker, not a claimed full tree digest.
            version = (
                f"observed-change-{index}"
                if item.get("status") == "completed"
                else None
            )
            result.append(
                Observation(
                    oid,
                    index,
                    turn,
                    None,
                    None,
                    version,
                    "",
                    {"event_index": index, "field": "changes"},
                    (),
                    paths,
                    "CANDIDATE_CHANGE",
                    "current",
                    "observed_change_only",
                )
            )
            for previous in result[:-1]:
                if previous.kind == "PUBLIC_CHECK_PASS":
                    # A full dependency map is unavailable. Conservatively stale
                    # all earlier support, never let a change preserve false PASS.
                    previous.lifecycle = "historical_unresolved"
            continue
        if kind != "commandExecution":
            continue
        command, output = item.get("command"), item.get("aggregatedOutput") or ""
        exit_code = item.get("exitCode")
        scope = _scope(command or "")
        assertion = bool(
            re.search(r"AssertionError|(?m:^E\s+assert)|FAILED\s+[^\n]+::", output)
        )
        environment = bool(
            re.search(
                r"error while loading shared libraries|command not found|not a git repository|No such file or directory[^\n]*\.git/HEAD",
                output,
                re.I,
            )
        )
        complete = bool(
            command and exit_code is not None and item.get("status") == "completed"
        )
        if exit_code not in (None, 0) and assertion:
            category = "FUNCTIONAL_ASSERTION"
        elif exit_code not in (None, 0) and environment:
            category = "ENV_TOOL_FAILURE"
        elif exit_code == 0 and is_test_command(command or ""):
            category = "PUBLIC_CHECK_PASS"
        elif exit_code == 0 and any(
            a.get("type") in {"read", "search"} for a in item.get("commandActions", [])
        ):
            category = "SOURCE_READ"
        else:
            category = "UNKNOWN"
        if category == "UNKNOWN" or not simple_command(command or ""):
            # Unknown shell commands may modify code without a fileChange item.
            # Missing snapshots cannot certify the previous source generation.
            version = None
            for previous in result:
                if previous.kind == "PUBLIC_CHECK_PASS":
                    previous.lifecycle = "historical_unresolved"
        paths = tuple(sorted(set(FILE.findall(command or ""))))
        nodes = tuple(
            sorted(
                set(
                    re.findall(
                        r"[\w/.-]+\.py::[\w\[\].:/-]+", output + "\n" + (command or "")
                    )
                )
            )
        )
        row = Observation(
            oid,
            index,
            turn,
            command,
            exit_code,
            version,
            output,
            {
                "event_index": index,
                "field": "aggregatedOutput",
                "start": 0,
                "end": len(output),
            },
            nodes,
            paths,
            category,
            "current" if complete and version is not None else "unknown",
            "complete" if complete else "unknown",
            scope,
        )
        if complete and category == "PUBLIC_CHECK_PASS" and scope and version:
            for previous in result:
                if (
                    previous.exit_status not in (None, 0)
                    and previous.check_scope == scope
                    and previous.source_version == version
                    and previous.completeness == "complete"
                ):
                    previous.lifecycle = "superseded"
                    previous.superseded_by = oid
        result.append(row)
    return result


def apply_links(requirements, observed, links, request):
    """Check proposal citations before using limited public evidence as status.

    Quotes validate provenance, not semantic truth; independent review remains
    required. Environment-only associations cannot establish functional failure.
    """
    reqs = {r.requirement_id: r for r in requirements}
    obs = {o.observation_id: o for o in observed}
    for link in links:
        r, o = reqs[link["requirement_id"]], obs[link["observation_id"]]
        rq, oq = link["requirement_quote"], link["observation_quote"]
        text = request[r.verbatim_span["start"] : r.verbatim_span["end"]]
        if not rq or rq not in text or not oq or oq not in o.output:
            raise ValueError("Ungrounded requirement/observation citation")
        relation = link["relation"]
        if relation not in {"CONTRADICTS", "LOCAL_SUPPORT", "CONTEXT"}:
            raise ValueError("Unknown observation relationship")
        if relation == "CONTRADICTS" and o.kind != "FUNCTIONAL_ASSERTION":
            raise ValueError("Non-functional event cannot prove contradiction")
        if relation == "LOCAL_SUPPORT" and o.kind != "PUBLIC_CHECK_PASS":
            raise ValueError("Support requires a public check")
        if relation != "CONTEXT" and not link.get("coverage_basis"):
            raise ValueError("A check exit alone does not identify coverage")
        o.requirement_links.append(link)
        r.observation_refs.append(o.observation_id)
    for r in requirements:
        active = [
            link["relation"]
            for o in observed
            if o.lifecycle == "current"
            for link in o.requirement_links
            if link["requirement_id"] == r.requirement_id
        ]
        r.conflict = "CONTRADICTS" in active and "LOCAL_SUPPORT" in active
        r.status = (
            "contradicted"
            if "CONTRADICTS" in active
            else "locally_supported"
            if "LOCAL_SUPPORT" in active
            else "unverified"
        )
    return requirements


def requirement_weights(requirements):
    """Normalize each parent before splitting: extra child clauses earn no mass."""
    parents = {}
    for r in requirements:
        parents.setdefault(r.parent_requirement, []).append(r)
    result = {}
    for rows in parents.values():
        status_weights = [
            {"contradicted": 2.0, "unverified": 1.0, "locally_supported": 0.25}[
                r.status
            ]
            for r in rows
        ]
        mass = max(status_weights)
        for r, value in zip(rows, status_weights):
            result[r.requirement_id] = mass * value / sum(status_weights)
    total = sum(result.values()) or 1
    return {k: v / total for k, v in result.items()}


def analyze(
    request, events, *, checkpoint_event_count, initial_source_version=None, links=()
):
    requirements, unresolved = request_ledger(request)
    observed = observations(
        events,
        checkpoint_event_count=checkpoint_event_count,
        initial_source_version=initial_source_version,
    )
    apply_links(requirements, observed, links, request)
    return {
        "requirements": [asdict(r) for r in requirements],
        "unresolved": unresolved,
        "observations": [asdict(o) for o in observed],
        "weights": requirement_weights(requirements),
        "environment_functional_weight": 0,
        "association_status": "PROPOSED" if links else "UNVERIFIED_NO_SEMANTIC_LINKS",
    }
