"""Deadline-bounded helper adapter over the existing isolated Session."""

import json
from pathlib import Path
import time

from .diagnostic import home_auth
from .relation_store import atomic_json
from .session import Session
from .source_relation import PROMPT, identity

BATCH_PROMPT = (
    PROMPT.replace(
        "a list containing every pair.", "a list containing only every requested pair."
    )
    + "\nReturn only requested_pairs. No tools or repair suggestions. Do not classify other pairs. Transport v2 supplies each full source text once."
)


class DeadlineSession(Session):
    def __init__(self, *args, deadline, **kwargs):
        super().__init__(*args, **kwargs)
        self.deadline = deadline

    def rpc(self, method, params, timeout=45):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Helper absolute deadline")
        return super().rpc(method, params, timeout=min(timeout, remaining))

    def cancel(self):
        if self.active and self.thread_id and self.last_turn_id:
            # Cancellation has its own bounded completion allowance; all time is charged.
            self.deadline = time.monotonic() + 2
            try:
                self.rpc(
                    "turn/interrupt",
                    {"threadId": self.thread_id, "turnId": self.last_turn_id},
                    timeout=2,
                )
                return "INTERRUPT_ACKNOWLEDGED"
            except (RuntimeError, TimeoutError, BrokenPipeError):
                return "INTERRUPT_FAILED_CONTAINER_STOP_REQUIRED"
        return "NO_KNOWN_ACTIVE_TURN"


def batch_payload(ledger, pool, requested):
    rids, uids = {p[0] for p in requested}, {p[1] for p in requested}
    return {
        "prompt": BATCH_PROMPT,
        "requested_pairs": requested,
        "requirements": [
            r for r in ledger["requirements"] if r["requirement_id"] in rids
        ],
        "units": [
            {
                "unit_id": c.unit.unit_id,
                "role": c.unit.claim_role,
                "symbols": list(c.unit.applies_to),
                "conditions": list(c.unit.preconditions),
                "text": c.unit.statement,
                "sources": [
                    {
                        "path": s.path_or_public_url,
                        "revision": s.revision,
                        "line_start": s.line_start,
                        "line_end": s.line_end,
                    }
                    for s in c.unit.source_spans
                ],
            }
            for c in pool.candidates
            if c.unit.unit_id in uids
        ],
    }


def parse_relation_response(text):
    """Keep complete JSON array prefix rows if transport truncates the final row."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re

        match = re.match(r'\s*\{\s*"(relations|rows)"\s*:\s*\[', text)
        if match is None:
            raise
        decoder = json.JSONDecoder()
        rows = []
        cursor = match.end()
        while cursor < len(text):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            try:
                row, cursor = decoder.raw_decode(text, cursor)
            except json.JSONDecodeError:
                break
            rows.append(row)
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor == len(text) or text[cursor] != ",":
                break
            cursor += 1
        if not rows:
            raise ValueError("No complete relation rows in malformed response")
        return {
            match.group(1): rows,
            "transport_status": "PARTIAL_JSON_PREFIX",
            "unparsed_suffix": text[cursor:],
        }


def call_batch(
    ledger,
    pool,
    requested,
    output,
    *,
    seconds=20,
    model="gpt-5.6-sol",
    image="hermes-repair-knowledge-executor:v1",
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    payload = batch_payload(ledger, pool, requested)
    started = time.monotonic()
    meta = {
        "started_timestamp": time.time(),
        "deadline_seconds": seconds,
        "input_identity": identity(payload),
        "payload": payload,
        "model": model,
        "effort": "medium",
        "status": "ACTIVE",
    }
    atomic_json(output / "input.json", meta)
    empty = output / "empty"
    for root in (empty, output / "scratch"):
        for reserved in (".git", ".codex", ".agents"):
            (root / reserved).mkdir(parents=True, exist_ok=True)
    session = None
    auth = None
    try:
        home, auth = home_auth(output)
        session = DeadlineSession(
            empty,
            output / "scratch",
            home,
            empty,
            output / "server",
            image=image,
            model=model,
            deadline=started + seconds,
        )
        meta["container_name"] = session.name
        atomic_json(output / "input.json", meta)
        with session:
            advertised = session.rpc("model/list", {"includeHidden": True}).get(
                "data", []
            )
            if not any((r.get("model") or r.get("id")) == model for r in advertised):
                raise ValueError("Frozen helper model unavailable")
            session.start()
            try:
                turn = session.turn(
                    "No tools. Put requested JSON inside summary; TASK_COMPLETE.\n"
                    + json.dumps(payload),
                    max(0, session.deadline - time.monotonic()),
                )
            finally:
                meta["cancellation"] = session.cancel()
            forbidden = {"commandExecution", "fileChange", "mcpToolCall", "webSearch"}
            if any(
                e.get("method") == "item/completed"
                and e.get("params", {}).get("item", {}).get("type") in forbidden
                for e in session.events
            ):
                raise ValueError("Forbidden helper tool use")
            messages = [
                i["text"]
                for i in turn.get("items", [])
                if i.get("type") == "agentMessage"
            ]
            atomic_json(output / "raw.json", {"messages": messages})
            value = parse_relation_response(json.loads(messages[-1])["summary"])
            atomic_json(output / "result.json", value)
            meta["status"] = "COMPLETED"
            return value
    except BaseException as exc:
        meta["status"] = "ERROR"
        meta["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        if auth is not None:
            auth.unlink(missing_ok=True)
        meta["seconds"] = time.monotonic() - started
        meta["completed_timestamp"] = time.time()
        meta["no_running_tool_confirmation"] = getattr(session, "stopped", False)
        atomic_json(output / "cost.json", meta)
