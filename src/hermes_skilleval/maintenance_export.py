"""Allowlisted public derivatives from local replay evidence; excludes raw traces."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sanitized(data):
    # Remove host paths without deleting public command semantics.
    text = data.decode("utf-8")
    text = re.sub(r'/Users/[^/\s"\']+', "<local-home>", text)
    return text.encode()


def public_check(data):
    text = data.decode("utf-8")
    if re.search(
        r"/Users/|/home/[^ /]+/|gh[pousr]_[A-Za-z0-9]{20,}|sk-proj-[A-Za-z0-9_-]+|-----BEGIN [^-]*PRIVATE KEY-----",
        text,
    ):
        raise ValueError(
            "public export contains sensitive pattern; review and reverify before publication"
        )


def validate_originals(run_dir, task_root, qualification, record, task, q):
    if q.get("qualified") is not True:
        raise ValueError("original qualification invalid")
    if any(
        record.get(k) != task.get(k) or q.get(k) != task.get(k)
        for k in ["task_id", "base_commit"]
    ):
        raise ValueError("original task/base binding mismatch")
    if record.get("qualification_sha256") != digest(Path(qualification).read_bytes()):
        raise ValueError("original qualification digest mismatch")
    if q["qualification_binding"]["task_sha256"] != digest(
        (task_root / "task.json").read_bytes()
    ):
        raise ValueError("original task digest mismatch")
    launch = json.loads((run_dir / "started.json").read_text())
    if any(
        record.get(k) != launch.get(k)
        for k in ["run_id", "task_id", "base_commit", "arm", "registry_id"]
    ):
        raise ValueError("original launch binding mismatch")
    patch = run_dir / "saved-capture/candidate.patch"
    if patch.exists():
        capture = json.loads((run_dir / "saved-capture.json").read_text())
        if digest(patch.read_bytes()) != record.get("patch_sha256") or capture[
            "patch_sha256"
        ] != record.get("patch_sha256"):
            raise ValueError("original patch digest mismatch")
    for kind in ["target", "regression"]:
        file = run_dir / "verification" / kind / "junit.xml"
        if file.exists():
            for filename in ["result.json", "junit.xml"]:
                expected = record.get("check_evidence", {}).get(kind, {}).get(filename)
                if expected != digest((file.parent / filename).read_bytes()):
                    raise ValueError("original run/check digest mismatch")
            check = json.loads((file.parent / "result.json").read_text())
            if check["evidence_sha256"]["junit.xml"] != digest(file.read_bytes()):
                raise ValueError("original JUnit digest mismatch")
            if sorted(c["id"] for c in check["cases"]) != sorted(q["test_ids"][kind]):
                raise ValueError("original test collection mismatch")
    if record.get("verifier_valid"):
        original = json.loads((run_dir / "verification/run.json").read_text())
        if any(
            original.get(k) != record.get(k)
            for k in [
                "task_id",
                "arm",
                "base_commit",
                "patch_sha256",
                "verifier_valid",
                "resolved",
                "check_evidence",
            ]
        ):
            raise ValueError("original verification binding mismatch")


def export_run(run_dir, task_root, qualification, destination, attempt=1):
    run_dir = Path(run_dir)
    task_root = Path(task_root)
    destination = Path(destination)
    record = json.loads((run_dir / "run.json").read_text())
    task = json.loads((task_root / "task.json").read_text())
    q = json.loads(Path(qualification).read_text())
    validate_originals(run_dir, task_root, qualification, record, task, q)
    destination.mkdir(parents=True, exist_ok=False)
    row = {
        k: task[k]
        for k in ["task_id", "repository", "family_id", "split", "base_commit"]
    }
    row.update(
        arm=record["arm"],
        attempt=attempt,
        run_id=record["run_id"],
        execution_status=record["execution_status"],
        usage=record.get("usage"),
        timed_out=record.get("timed_out"),
        exit_code=record.get("exit_code"),
        timeout_seconds=record.get("timeout"),
        cost_usd=None,
        reverification=record.get("reverification"),
        policy_rejected=str(record.get("error", "")).startswith("illegal patch path:"),
        expected_test_ids=q["test_ids"],
        selected_ids=record.get("selected_ids"),
        derivation="SANITIZED_DERIVATIVE",
        files={},
        timing={
            k: record.get(k)
            for k in [
                "execution_seconds",
                "package_prepare_seconds",
                "capture_seconds",
                "finalize_seconds",
                "pipeline_wall_seconds",
            ]
        },
    )
    sources = {
        "patch": run_dir / "saved-capture/candidate.patch",
        "target": run_dir / "verification/target/junit.xml",
        "regression": run_dir / "verification/regression/junit.xml",
    }
    for label, source in sources.items():
        if not source.exists():
            continue
        data = source.read_bytes()
        public = data if label == "patch" else sanitized(data)
        name = "candidate.patch" if label == "patch" else label + ".xml"
        public_check(public)
        (destination / name).write_bytes(public)
        row["files"][label] = {
            "path": destination.name + "/" + name,
            "sha256": digest(public),
            "original_sha256": digest(data),
        }
    binding = {
        k: row[k] for k in ["task_id", "arm", "attempt", "run_id", "base_commit"]
    }
    binding.update(
        patch_sha256=row["files"].get("patch", {}).get("sha256"),
        test_files={
            k: row["files"].get(k, {}).get("sha256") for k in ["target", "regression"]
        },
        verifier_valid=record.get("verifier_valid"),
        resolved=record.get("resolved"),
        error_status="PRESENT_LOCAL_ONLY" if record.get("error") else None,
    )
    data = (json.dumps(binding, indent=2) + "\n").encode()
    (destination / "verification.json").write_bytes(data)
    row["files"]["binding"] = {
        "path": destination.name + "/verification.json",
        "sha256": digest(data),
    }
    events = []
    event_path = run_dir / "events.jsonl"
    if event_path.exists():
        for ordinal, line in enumerate(event_path.read_text().splitlines()):
            event = json.loads(line)
            item = event.get("item") or {}
            if (
                event.get("type") == "item.completed"
                and item.get("type") == "command_execution"
            ):
                command = item.get("command", "")
                paths = sorted(
                    set(
                        re.findall(
                            r"\.agents/skills/[a-zA-Z0-9_.-]+/SKILL\.md", command
                        )
                    )
                )
                if paths:
                    events.append(
                        {
                            "event_ordinal": ordinal,
                            "type": event["type"],
                            "item_type": item["type"],
                            "referenced_skill_paths": paths,
                            "read_command_observed": bool(
                                re.search(r"\b(cat|sed|head|tail)\b", command)
                            ),
                            "exit_code": item.get("exit_code"),
                            "evidence_scope": "Observed completed command referencing SKILL.md; extent of reading inferred only from command/output, not cognitive use.",
                        }
                    )
            elif event.get("type") == "turn.completed":
                events.append(
                    {
                        "event_ordinal": ordinal,
                        "type": event["type"],
                        "usage": event.get("usage"),
                    }
                )
    (destination / "events.json").write_text(
        json.dumps(
            {
                "derivation": "SANITIZED_DERIVATIVE",
                "original_sha256": digest(event_path.read_bytes())
                if event_path.exists()
                else None,
                "events": events,
            },
            indent=2,
        )
        + "\n"
    )
    row["observed_skill_read_commands"] = len(
        [e for e in events if e["type"] == "item.completed"]
    )
    if (run_dir / "route.json").exists():
        route = json.loads((run_dir / "route.json").read_text())
        # Ranking inputs are public; do not copy host model paths or full token dumps.
        route = {
            k: route[k]
            for k in [
                "actual_router",
                "model_identity",
                "index_key",
                "skill_ids",
                "scores",
                "reranked_ids",
                "timing",
                "recommend_wall_seconds",
                "input_prompt_hash",
                "registry_id",
            ]
            if k in route
        }
        public_check(json.dumps(route).encode())
        (destination / "route.json").write_text(json.dumps(route, indent=2) + "\n")
    (destination / "record.json").write_text(json.dumps(row, indent=2) + "\n")
    return row
