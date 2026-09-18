"""Real checkpoint chains and paired tails, with post-execution acceptance only."""

from __future__ import annotations

from dataclasses import replace
import difflib
import json
from pathlib import Path
import shutil
import time

from .session import Session, NEUTRAL, CWD, SCRATCH, IMAGE, dump, inventory, snapshot
from .state import observe, opportunity, prefix_digest

GENERIC = (
    "Review your current work carefully against the user request. Check the relevant "
    "behavior and regressions, address any remaining problems, and deliver the result."
)


def read_task_profile(task):
    return json.loads((task / "task.json").read_text())["profile"]


def final_message(events):
    texts = [
        e["params"]["item"].get("text", "")
        for e in events
        if e.get("method") == "item/completed"
        and e.get("params", {}).get("item", {}).get("type") == "agentMessage"
        and e["params"]["item"].get("phase") == "final_answer"
    ]
    return texts[-1] if texts else ""


def task_complete(events):
    try:
        return (
            json.loads(final_message(events)).get("segment_status") == "TASK_COMPLETE"
        )
    except (ValueError, AttributeError):
        return False


def source_observation(base, candidate):
    from hermes_skilleval.repo_routing.advisory_capture import (
        inventory as source_inventory,
    )

    before, after = source_inventory(base), source_inventory(candidate)
    changed = sorted(
        k for k in before.keys() | after.keys() if before.get(k) != after.get(k)
    )
    diffs, snippets = [], []
    for name in changed:
        p, q = Path(base) / name, Path(candidate) / name
        if p.is_symlink() or q.is_symlink():
            continue
        try:
            old = p.read_text() if p.exists() else ""
            new = q.read_text() if q.exists() else ""
        except (UnicodeError, OSError):
            continue
        diffs.extend(
            difflib.unified_diff(
                old.splitlines(), new.splitlines(), fromfile=name, tofile=name
            )
        )
        snippets.append(name + "\n" + new[:2000])
    return changed, "\n".join(diffs)[:20000], "\n".join(snippets)[:10000]


def state_for(task, root, events, stage, turns, remaining, total):
    changed, diff, source = source_observation(task / "base", root / "source")
    if not source:
        # Public snippets from actually observed tool output, never hidden assets.
        source = "\n".join(
            e["params"]["item"].get("aggregatedOutput", "")
            for e in events
            if e.get("method") == "item/completed"
            and e.get("params", {}).get("item", {}).get("type") == "commandExecution"
        )[-5000:]
    meta = json.loads((task / "task.json").read_text())
    return observe(
        request=(task / "request.txt").read_text(),
        repo_facts=json.dumps(meta["profile"]["packages"]),
        stage=stage,
        turn_index=turns,
        remaining=remaining,
        total=total,
        events=events,
        changed=changed,
        diff=diff,
        source=source,
    )


def prepare_root(task, root):
    root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(task / "base", root / "source", symlinks=True)
    for reserved in (".git", ".codex", ".agents"):
        (root / "source" / reserved).mkdir(exist_ok=True)
    (root / "scratch").mkdir()
    for reserved in (".git", ".codex", ".agents"):
        (root / "scratch" / reserved).mkdir()


def checkpoint(root, name, state, session_meta, events, candidates):
    meta = {
        **session_meta,
        "state": state.to_dict(),
        "candidates": candidates,
        "remaining_seconds": state.remaining_seconds,
        "total_seconds": state.total_seconds,
        "visible_events": events,
        "cwd_mapping": {"source": CWD, "scratch": SCRATCH},
        "environment_profile": {
            "image": IMAGE,
            "source_write": True,
            "skills_readonly": True,
            "tool_network": False,
        },
    }
    return snapshot(
        root / "source", root / "scratch", root / "checkpoints" / name, meta
    )


def execute(
    task,
    root,
    home,
    skills,
    *,
    total=600,
    retriever=None,
    controller=None,
    predict=None,
    from_checkpoint=None,
    payload=None,
    payload_tokens=0,
    token_counts=None,
):
    """One trajectory. `predict` receives current State only, never outcomes.

    Offline tails never make a second intervention. Policy comparisons execute
    only the chosen continuation. Files and recorded attempts are never overwritten.
    """
    task, root = Path(task), Path(root)
    started = time.monotonic()
    if from_checkpoint:
        cp = Path(from_checkpoint)
        meta = json.loads((cp / "checkpoint.json").read_text())
        root.mkdir(parents=True, exist_ok=False)
        shutil.copytree(cp / "source", root / "source", symlinks=True)
        shutil.copytree(cp / "scratch", root / "scratch", symlinks=True)
        remaining = meta["remaining_seconds"]
        total = meta["total_seconds"]
        events = list(meta["visible_events"])
        turns = meta["state"]["completed_turn_index"]
        parent = meta.get("thread_id")
        last = meta.get("last_turn_id")
        seen = [
            stage for stage in ("E0", "E1", "E2") if stage <= meta["state"]["stage"]
        ]
    else:
        prepare_root(task, root)
        remaining = total
        events = []
        turns = 0
        parent = None
        last = None
        seen = []
    initial_turns = turns
    public_turns = []
    initial_remaining = remaining
    decisions = []
    checkpoints = []
    thread_id = None
    status = "RUNNING"
    input_observed = False
    spent = 0.0
    new_events = []
    current_stage = meta["state"]["stage"] if from_checkpoint else "E0"
    dump(
        root / "started.json",
        {
            "total": total,
            "initial_remaining": initial_remaining,
            "from_checkpoint": str(from_checkpoint) if from_checkpoint else None,
            "initial_files": inventory(root / "source"),
        },
    )
    prepared = time.monotonic()
    budget_started = started
    try:
        while remaining > 0:
            remaining = initial_remaining - (time.monotonic() - budget_started)
            if remaining <= 0:
                break
            state = state_for(
                task, root, events, current_stage, turns, remaining, total
            )
            done = task_complete(new_events)
            event_stage = (
                None
                if from_checkpoint and turns == initial_turns
                else opportunity(state, seen, candidate_complete=done)
            )
            guidance = (
                payload
                if turns
                == (meta["state"]["completed_turn_index"] if from_checkpoint else 0)
                else None
            )
            if event_stage:
                state = replace(state, stage=event_stage)
                current_stage = event_stage
                seen.append(event_stage)
                if controller and controller.method == "H-no-state":
                    candidates = retriever.rank(
                        state.request + "\n" + state.repo_facts
                    )[:2]
                else:
                    candidates = retriever.candidates(state) if retriever else []
                cp = checkpoint(
                    root,
                    event_stage,
                    state,
                    {
                        "thread_id": thread_id,
                        "last_turn_id": last,
                        "no_running_tool_confirmation": True,
                        "visible_prefix_sha256": prefix_digest(public_turns),
                    },
                    events,
                    candidates,
                )
                remaining = max(
                    0.0, initial_remaining - (time.monotonic() - budget_started)
                )
                state = replace(state, remaining_seconds=remaining)
                frozen = json.loads((cp / "checkpoint.json").read_text())
                frozen.update(state=state.to_dict(), remaining_seconds=remaining)
                dump(cp / "checkpoint.json", frozen)
                checkpoints.append(str(cp))
                if controller:
                    gains, wait = (
                        predict(state, candidates)
                        if predict and controller.remaining_interventions
                        else (None, None)
                    )
                    decision = controller.decide(
                        event_stage,
                        candidates,
                        gains,
                        wait,
                        has_future=event_stage != "E2" and remaining > 0,
                        dynamic_top=retriever.dynamic_top(state),
                    )
                    decisions.append(
                        {**decision, "stage": event_stage, "state": state.to_dict()}
                    )
                    if decision["action"] == "UNAVAILABLE":
                        status = "METHOD_UNAVAILABLE"
                        break
                    if decision["action"] == "INJECT":
                        guidance = retriever.skills[decision["skill_id"]]
                        if (
                            token_counts is None
                            or decision["skill_id"] not in token_counts
                        ):
                            raise ValueError("missing frozen payload token count")
                        payload_tokens = token_counts[decision["skill_id"]]
            elif done:
                status = "COMPLETED"
                break
            text = NEUTRAL
            if parent is None and thread_id is None:
                from hermes_skilleval._maintenance.prompts import maintenance_prompt
                from hermes_skilleval.repository_profile import RepositoryProfile

                profile = RepositoryProfile(**read_task_profile(task))
                text = (
                    maintenance_prompt((task / "request.txt").read_text(), profile)
                    + "\n\n"
                    + text
                )
            if guidance:
                text += "\n\nExternal skill guidance:\n" + guidance
            with Session(
                root / "source",
                root / "scratch",
                home,
                skills,
                root / f"turn-{turns:03d}",
            ) as session:
                if thread_id:
                    session.resume(thread_id)
                elif parent:
                    fork = session.fork(parent, last)
                    actual_prefix = prefix_digest(fork["thread"]["turns"])
                    expected_prefix = meta["visible_prefix_sha256"]
                    dump(
                        root / "fork.json",
                        {
                            "visible_prefix_sha256": actual_prefix,
                            "expected_prefix_sha256": expected_prefix,
                            "matched": actual_prefix == expected_prefix,
                            "parent_thread": parent,
                            "boundary_id": last,
                        },
                    )
                    if actual_prefix != expected_prefix:
                        raise ValueError(
                            "official fork returned a different visible prefix"
                        )
                else:
                    session.start()
                thread_id = session.thread_id
                remaining_for_turn = initial_remaining - (
                    time.monotonic() - budget_started
                )
                if remaining_for_turn <= 0:
                    raise TimeoutError("budget exhausted during session setup")
                turn = session.turn(text, remaining_for_turn)
                thread_id = session.thread_id
                last = session.last_turn_id
                if turn["status"] != "completed":
                    raise RuntimeError("turn did not complete: " + turn["status"])
                history = session.rpc(
                    "thread/read", {"threadId": thread_id, "includeTurns": True}
                )
                public_turns = history["thread"]["turns"]
                dump(
                    root / f"turn-{turns:03d}" / "public-history.json",
                    {"turns": public_turns},
                )
                new_events = [
                    e for e in session.events if e.get("method") == "item/completed"
                ]
                if guidance:
                    input_observed = input_observed or any(
                        guidance
                        in "\n".join(
                            part.get("text", "")
                            for part in item.get("content", [])
                            if part.get("type") == "text"
                        )
                        for history_turn in public_turns[-1:]
                        for item in history_turn.get("items", [])
                        if item.get("type") == "userMessage"
                    )

            # Charge setup, inference, checkpoint/scoring and teardown in all arms.
            spent = time.monotonic() - budget_started
            remaining = initial_remaining - spent
            events.extend(new_events)
            turns += 1
            dump(
                root / "progress.json",
                {
                    "turns": turns,
                    "remaining": remaining,
                    "thread_id": thread_id,
                    "last_turn_id": last,
                    "decisions": decisions,
                },
            )
    except TimeoutError as exc:
        status = "TIMEOUT"
        dump(root / "error.json", {"error": str(exc)})
    except Exception as exc:
        status = "EXECUTOR_ERROR"
        dump(root / "error.json", {"type": type(exc).__name__, "error": str(exc)})
    if status == "RUNNING":
        status = "COMPLETED" if task_complete(new_events) else "TIMEOUT"
    elapsed = time.monotonic() - budget_started
    result = {
        "status": status,
        "thread_id": thread_id,
        "last_turn_id": last,
        "turns": turns,
        "total_seconds": total,
        "initial_remaining": initial_remaining,
        "tail_seconds": elapsed,
        "preparation_seconds": prepared - started,
        "prefix_seconds": total - initial_remaining,
        "model_input_observed": input_observed,
        "injected": bool(payload) or any(d["action"] == "INJECT" for d in decisions),
        "payload_tokens": payload_tokens,
        "checkpoints": checkpoints,
        "decisions": decisions,
    }
    dump(root / "execution.json", result)
    return result


def accept(task, run, output):
    """Only called by collection/evaluation coordinator after all relevant tails."""
    from hermes_skilleval.repo_routing.advisory_capture import (
        capture_complete,
        reconstruct,
    )
    from hermes_skilleval._maintenance.check import check
    from hermes_skilleval.repository_profile import RepositoryProfile

    task, run, output = map(Path, (task, run, output))
    output.mkdir(parents=True, exist_ok=False)
    meta = json.loads((task / "task.json").read_text())
    profile = RepositoryProfile(**meta["profile"])
    captured = capture_complete(task / "base", run / "source", output / "capture")
    reconstruct(
        task / "base",
        output / "capture/candidate.patch",
        output / "reconstructed",
        captured["after"],
    )
    from hermes_skilleval.repository_profile import validate_changes

    policy_error = None
    try:
        validate_changes(
            profile,
            captured["changed_files"],
            before=captured["before"],
            after=captured["after"],
            candidate=output / "reconstructed",
        )
    except ValueError as exc:
        policy_error = str(exc)
    results = {
        kind: check(
            output / "reconstructed",
            task / "trusted",
            output / kind,
            selector,
            profile=profile,
            test_file=meta["trusted_test_file"],
        )
        for kind, selector in [
            ("target", meta["target_selector"]),
            ("regression", meta["regression_selector"]),
        ]
    }
    results["policy"] = {
        "valid": True,
        "passed": policy_error is None,
        "error": policy_error,
    }
    dump(output / "acceptance.json", {"capture": captured, "checks": results})
    return results


def utility(
    quality, total_seconds, elapsed_seconds, payload_tokens, guidance_budget=1200
):
    if quality is None:
        return None
    if total_seconds <= 0 or guidance_budget <= 0:
        raise ValueError("invalid global budget")
    return (
        float(quality)
        - 0.05 * min(1.0, elapsed_seconds / total_seconds)
        - 0.02 * min(1.0, payload_tokens / guidance_budget)
    )
