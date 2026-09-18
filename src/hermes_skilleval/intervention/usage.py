"""Read public usage notifications, excluding replayed history on resume/fork."""

import hashlib
import json
from pathlib import Path


def reported_usage(run):
    counters = (
        "totalTokens",
        "inputTokens",
        "cachedInputTokens",
        "cacheWriteInputTokens",
        "outputTokens",
        "reasoningOutputTokens",
    )
    totals = dict.fromkeys(counters, 0)
    started, completed, observed, seen = set(), set(), set(), set()
    evidence = {}
    updates = 0
    for path in sorted(Path(run).glob("turn-*/events.jsonl")):
        evidence[str(path.relative_to(run))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        active = None
        previous = {}
        for line in path.read_text().splitlines():
            event = json.loads(line)
            method, params = event.get("method"), event.get("params", {})
            if method == "turn/started":
                active = params["turn"]["id"]
                started.add(active)
            elif method == "turn/completed":
                completed.add(params["turn"]["id"])
                active = None
            elif method == "thread/tokenUsage/updated":
                thread, turn = params["threadId"], params["turnId"]
                usage = params["tokenUsage"]
                total, last = usage["total"], usage["last"]
                before = previous.get(thread)
                previous[thread] = total
                if turn != active:
                    continue
                key = (thread, turn, json.dumps(total, sort_keys=True))
                if key in seen:
                    continue
                seen.add(key)
                if before is not None and any(
                    total[k] - before[k] != last[k] for k in counters
                ):
                    raise ValueError(
                        "usage notification is not an additive request update"
                    )
                if any(not isinstance(last[k], int) or last[k] < 0 for k in counters):
                    raise ValueError("invalid reported usage")
                for k in counters:
                    totals[k] += last[k]
                observed.add(turn)
                updates += 1
    return {
        "scope": "public app-server request usage observed during started turns; excludes replayed prefix usage; not a billing statement",
        "tokens": totals if updates else None,
        "request_updates": updates,
        "started_turns": len(started),
        "completed_turns": len(completed),
        "turns_with_usage": len(observed),
        "all_started_turns_completed_with_usage": bool(started)
        and started <= completed & observed,
        "evidence_sha256": evidence,
    }
