"""Deterministic observations from completed public tool events only."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import shlex


@dataclass(frozen=True)
class State:
    request: str
    repo_facts: str
    stage: str
    completed_turn_index: int
    remaining_seconds: float
    total_seconds: float
    files_read: tuple[str, ...]
    files_changed: tuple[str, ...]
    diff_summary: str
    public_test_command: str | None
    public_test_exit: int | None
    failure_text: str | None
    recent_tool_errors: tuple[str, ...]
    repeated_error_count: int
    public_tests_run: int
    public_test_failure_seen: bool
    observed_pass_count: int | None
    observed_fail_count: int | None
    source_snippets: str
    observed_skill_reads: tuple[str, ...]
    text_original_chars: int
    text_retained_chars: int

    def to_dict(self):
        return asdict(self)

    def text(self):
        return json.dumps(
            {
                k: v
                for k, v in self.to_dict().items()
                if k not in ("request", "repo_facts")
            },
            ensure_ascii=False,
        )

    def numeric(self):
        missing = self.public_test_exit is None
        return [
            self.remaining_seconds / self.total_seconds,
            float(self.stage == "E0"),
            float(self.stage == "E1"),
            float(self.stage == "E2"),
            min(len(self.files_read), 30) / 30,
            min(len(self.files_changed), 20) / 20,
            min(self.public_tests_run, 10) / 10,
            float(missing),
            float(not missing and self.public_test_exit != 0),
            min(self.repeated_error_count, 5) / 5,
            min(len(self.observed_skill_reads), 10) / 10,
        ]


def is_test_command(command):
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    # Unwrap the observed shell invocation; do not interpret quoted search data.
    if (
        len(words) >= 3
        and words[0].rsplit("/", 1)[-1] in ("sh", "bash", "zsh")
        and "c" in words[1]
    ):
        return is_test_command(words[2])
    for segment in re.split(r"&&|\|\||;", command):
        try:
            args = shlex.split(segment)
        except ValueError:
            continue
        while args and ("=" in args[0] or args[0] in ("env", "command")):
            args.pop(0)
        if not args:
            continue
        exe = args[0].rsplit("/", 1)[-1]
        if exe in ("pytest", "tox", "nox", "py.test"):
            return True
        if (
            exe.startswith("python")
            and len(args) > 2
            and args[1] == "-m"
            and args[2] in ("pytest", "unittest")
        ):
            return True
        if exe in ("uv", "poetry") and len(args) > 2 and args[1] == "run":
            if is_test_command(shlex.join(args[2:])):
                return True
    return False


FILE = re.compile(r"(?<![\w/])(?:[\w.-]+/)*[\w.-]+\.(?:py|md|rst|toml|yaml|json|csv)\b")


def observe(
    *,
    request,
    repo_facts,
    stage,
    turn_index,
    remaining,
    total,
    events,
    changed=(),
    diff="",
    source="",
    text_limit=10000,
):
    commands = [
        e["params"]["item"]
        for e in events
        if e.get("method") == "item/completed"
        and e.get("params", {}).get("item", {}).get("type") == "commandExecution"
    ]
    tests = [c for c in commands if is_test_command(c.get("command", ""))]
    failures = [c for c in commands if c.get("exitCode") not in (None, 0)]
    last_test = tests[-1] if tests else None
    errors = [(c.get("aggregatedOutput") or "")[-2000:] for c in failures[-4:]]
    signatures = [
        re.sub(r"\b\d+\b", "#", (e or str(c.get("command", ""))).strip())
        for e, c in zip(errors, failures[-4:])
    ]
    repeated = max(Counter(signatures).values(), default=0)
    reads = sorted({f for c in commands for f in FILE.findall(c.get("command", ""))})
    skill_reads = sorted({f for f in reads if "SKILL.md" in f})
    raw_failure = (
        (last_test.get("aggregatedOutput") or "")
        if last_test and last_test.get("exitCode")
        else "\n".join(errors)
    )
    if not raw_failure.strip():
        raw_failure = ""
    # Independent per-field limits ensure errors and real source survive together.
    cap = text_limit // 4
    retained = [raw_failure[-cap:], diff[:cap], source[:cap], "\n".join(errors)[-cap:]]
    return State(
        request,
        repo_facts,
        stage,
        turn_index,
        max(0, remaining),
        total,
        tuple(reads),
        tuple(sorted(changed)),
        retained[1],
        last_test.get("command") if last_test else None,
        last_test.get("exitCode") if last_test else None,
        retained[0] or None,
        tuple(retained[3].splitlines()),
        repeated,
        len(tests),
        any(c.get("exitCode") not in (None, 0) for c in tests),
        sum(c.get("exitCode") == 0 for c in tests) if tests else None,
        sum(c.get("exitCode") not in (None, 0) for c in tests) if tests else None,
        retained[2],
        tuple(skill_reads),
        len(raw_failure) + len(diff) + len(source) + sum(map(len, errors)),
        sum(map(len, retained)),
    )


def opportunity(state, seen, *, candidate_complete=False):
    """At most E0/E1/E2; coincident events are merged into the final opportunity."""
    if not seen:
        return "E0"
    if "E2" not in seen and (
        candidate_complete or state.remaining_seconds <= 0.25 * state.total_seconds
    ):
        return "E2"
    if (
        "E1" not in seen
        and "E2" not in seen
        and (state.public_test_failure_seen or state.repeated_error_count >= 2)
    ):
        return "E1"
    return None


def visible_prefix(turns):
    """Normalize public typed history, excluding IDs and reasoning items."""
    visible = []
    for turn in turns:
        items = []
        for item in turn.get("items", []):
            if item.get("type") == "reasoning":
                continue
            items.append(
                {
                    k: v
                    for k, v in item.items()
                    if k not in ("id", "processId", "durationMs", "clientId")
                }
            )
        visible.append(items)
    return visible


def prefix_digest(turns):
    return hashlib.sha256(
        json.dumps(visible_prefix(turns), sort_keys=True).encode()
    ).hexdigest()
