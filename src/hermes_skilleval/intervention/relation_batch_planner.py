"""Measured conservative batch envelopes and fresh-thread relation transport."""

from __future__ import annotations

import json
from pathlib import Path
import time

from .budgeted_relation_session import (
    DeadlineSession,
    batch_payload,
    parse_relation_response,
)
from .diagnostic import home_auth
from .relation_store import atomic_json
from .source_relation import identity

MODEL = "gpt-5.6-sol"
IMAGE = "hermes-repair-knowledge-executor:v1"


class ObservedSession(DeadlineSession):
    def receive(self, timeout):
        event = super().receive(timeout)
        event["_observed_monotonic"] = time.monotonic()
        return event


def partial_messages(events, deadline):
    rows = []
    late = []
    for event in events:
        item = event.get("params", {}).get("item", {})
        if (
            event.get("method") != "item/completed"
            or item.get("type") != "agentMessage"
        ):
            continue
        try:
            parsed = parse_relation_response(json.loads(item["text"])["summary"])
            values = parsed.get("relations", parsed.get("rows", []))
            if isinstance(values, list):
                target = (
                    rows
                    if event.get("_observed_monotonic", float("inf")) <= deadline
                    else late
                )
                target.extend(values)
        except (ValueError, KeyError, TypeError):
            continue
    return {"relations": rows}, {"relations": late}


class CostEnvelope:
    def __init__(self, observations, lifecycle):
        self.observations = observations
        self.lifecycle = lifecycle

    def estimate(self, size, length, *, cold=False):
        target = max(2, size)
        rows = [
            r
            for r in self.observations
            if r["lifecycle"] == self.lifecycle and r["size"] == target
        ]
        success = [
            r for r in rows if r["status"] == "COMPLETED" and r.get("valid_rows", 0) > 0
        ]
        if not success:
            return float("inf")
        # No regression fit on tiny correlated sample. Scale conservatively above observed length.
        values = [
            r["request_seconds"] * max(1.0, length / max(1, r["payload_chars"]))
            for r in rows
        ]
        setup = (
            max((r.get("setup_seconds", 0.0) for r in rows), default=0.0)
            if cold
            else 0.0
        )
        return max(values) + setup

    def choose(self, ranked, length_fn, remaining, *, cold=False):
        for size in (8, 2, 1):
            if len(ranked) < size:
                continue
            batch = ranked[:size]
            estimate = self.estimate(size, length_fn(batch), cold=cold)
            if 1.25 * estimate + 5 <= remaining:
                return batch, estimate
        return [], None


class RelationTransport:
    """One sequence owns a process; each call always starts an independent thread."""

    def __init__(self, root, *, lifecycle="reuse", deadline=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.lifecycle, self.deadline = lifecycle, deadline
        self.session = None
        self.auth = None
        self.setup_seconds = 0.0
        self.cleanup_seconds = 0.0
        self.thread_ids = []
        self.sequence_started = time.monotonic()

    def open(self, output, deadline):
        start = time.monotonic()
        empty = output / "empty"
        for p in (empty, output / "scratch"):
            for name in (".git", ".codex", ".agents"):
                (p / name).mkdir(parents=True, exist_ok=True)
        home, self.auth = home_auth(output)
        self.session = ObservedSession(
            empty,
            output / "scratch",
            home,
            empty,
            output / "server",
            image=IMAGE,
            model=MODEL,
            deadline=deadline,
        )
        self.session.__enter__()
        init_done = time.monotonic()
        models = self.session.rpc("model/list", {"includeHidden": True}).get("data", [])
        if not any((m.get("model") or m.get("id")) == MODEL for m in models):
            raise ValueError("Frozen helper model unavailable")
        self.setup_seconds = time.monotonic() - start
        return {
            "process_connection_seconds": init_done - start,
            "model_directory_seconds": time.monotonic() - init_done,
        }

    def stop_process(self):
        start = time.monotonic()
        try:
            if self.session:
                self.session.close()
        finally:
            if self.auth:
                self.auth.unlink(missing_ok=True)
            self.auth = None
            self.session = None
            self.cleanup_seconds += time.monotonic() - start

    def call(self, ledger, pool, requested, output, *, seconds=90, prompt=None):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        deadline = min(started + seconds, self.deadline or float("inf"))
        payload = batch_payload(ledger, pool, requested)
        if prompt:
            payload["prompt"] = prompt
        encoded = json.dumps(payload)
        meta = {
            "lifecycle": self.lifecycle,
            "size": len(requested),
            "payload_chars": len(encoded),
            "input_identity": identity(payload),
            "model": MODEL,
            "effort": "medium",
            "status": "ACTIVE",
            "started_timestamp": time.time(),
            "first_token_seconds": None,
            "setup_seconds": 0.0,
            "fresh_thread": False,
        }
        atomic_json(output / "input.json", payload)
        value = {}
        event_start = 0
        result_arrived = None
        try:
            meta["prepare_seconds"] = time.monotonic() - started
            if self.session is None:
                meta.update(self.open(output, deadline))
                meta["setup_seconds"] = self.setup_seconds
            s = self.session
            s.deadline = deadline
            s.last_turn_id = None
            event_start = len(s.events)
            t = time.monotonic()
            thread = s.start()["thread"]
            meta["thread_seconds"] = time.monotonic() - t
            if thread.get("turns") or s.thread_id in self.thread_ids:
                raise ValueError("Thread is not new and empty")
            self.thread_ids.append(s.thread_id)
            meta["fresh_thread"] = True
            meta["thread_id"] = s.thread_id
            t = time.monotonic()
            turn = s.turn(
                "No tools. Put requested JSON inside summary; TASK_COMPLETE.\n"
                + encoded,
                max(0, deadline - time.monotonic()),
            )
            result_arrived = time.monotonic()
            meta["response_seconds"] = result_arrived - t
            messages = [
                i["text"]
                for i in turn.get("items", [])
                if i.get("type") == "agentMessage"
            ]
            atomic_json(output / "raw.json", {"messages": messages})
            t = time.monotonic()
            value = {"relations": []}
            for message in messages:
                parsed = parse_relation_response(json.loads(message)["summary"])
                value["relations"].extend(
                    parsed.get("relations", parsed.get("rows", []))
                )
            meta["parse_seconds"] = time.monotonic() - t
            meta["status"] = "COMPLETED"
        except (
            RuntimeError,
            TimeoutError,
            ValueError,
            KeyError,
            IndexError,
            BrokenPipeError,
        ) as exc:
            meta["status"] = "ERROR"
            meta["error"] = type(exc).__name__ + ": " + str(exc)
            meta["censored"] = isinstance(exc, TimeoutError)
            if self.session:
                value, late_value = partial_messages(
                    self.session.events[event_start:], self.deadline or deadline
                )
                if value["relations"]:
                    result_arrived = min(deadline, self.deadline or deadline)
                atomic_json(output / "late.json", late_value)
        finally:
            s = self.session
            if s:
                events = s.events[event_start:]
                forbidden = {
                    "commandExecution",
                    "fileChange",
                    "mcpToolCall",
                    "webSearch",
                }
                if any(
                    e.get("params", {}).get("item", {}).get("type") in forbidden
                    for e in events
                ):
                    value = {}
                    meta.update(status="ERROR", error="Forbidden helper tool use")
                meta["usage_events"] = [
                    e["params"]
                    for e in events
                    if e.get("method") == "thread/tokenUsage/updated"
                ]
                meta["usage"] = (
                    meta["usage_events"][-1].get("tokenUsage", {}).get("total")
                    if meta["usage_events"]
                    else None
                )
                t = time.monotonic()
                meta["cancellation"] = s.cancel()
                meta["cancel_seconds"] = time.monotonic() - t
            meta["request_seconds"] = time.monotonic() - started - meta["setup_seconds"]
            if self.lifecycle == "cold" or meta["status"] != "COMPLETED":
                self.stop_process()
                meta["no_running_tool_confirmation"] = True
            meta["seconds"] = time.monotonic() - started
            if self.lifecycle == "cold":
                meta["request_seconds"] = meta["seconds"] - meta["setup_seconds"]
            meta["completed_timestamp"] = time.time()
            meta["late"] = result_arrived is None or result_arrived > (
                self.deadline or float("inf")
            )
            atomic_json(output / "result.json", value)
            atomic_json(output / "cost.json", meta)
        return value, meta

    def close(self):
        self.stop_process()
        atomic_json(
            self.root / "sequence.json",
            {
                "seconds": time.monotonic() - self.sequence_started,
                "cleanup_seconds": self.cleanup_seconds,
                "thread_ids": self.thread_ids,
                "fresh_threads_unique": len(set(self.thread_ids))
                == len(self.thread_ids),
                "no_running_tool_confirmation": True,
            },
        )
