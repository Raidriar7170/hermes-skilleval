"""Compact candidate/verdict exports and zero-model records-only recomputation."""

import hashlib
import json
from pathlib import Path
import shutil

from .functional_collection import verify_row
from .functional_outcomes import load_objective, outcomes
from .records import verify_public_artifacts
from .session import dump
from .study import read
from .usage import reported_usage


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(records_path, objective_path, *, public_root=None):
    objective = load_objective(objective_path)
    bundle = read(records_path)
    declared = (
        bundle.get("objective_sha256")
        or bundle.get("identity", {}).get("objective_sha256")
        or bundle.get("policy_freeze", {}).get("objective_sha256")
    )
    if declared != objective["sha256"]:
        raise ValueError("records objective identity mismatch")
    statuses = {}
    for row in bundle["rows"]:
        if public_root is None:
            actual = verify_row(row)
        else:
            root = Path(public_root) / row["evidence_path"]
            if row["y_functional"] is not None and not row.get("patch_sha256"):
                raise ValueError("functional label without complete captured patch")
            verification = verify_public_artifacts(
                {**row, "quality": None}, Path(public_root)
            )
            if read(root / "checks.json") != row["checks"]:
                raise ValueError("portable checks mismatch")
            if row.get("model_calls") and "status" not in row["model_calls"]:
                calls = read(root / "model-calls.json")
                if calls != row["model_calls"] or calls["method"] != row["method"]:
                    raise ValueError("portable model call receipt mismatch")
                if row["method"] == "H-myopic-v2" and calls["wait_calls"] != 0:
                    raise ValueError("portable myopic receipt includes wait calls")
            if (root / "fork.json").exists():
                fork = read(root / "fork.json")
                if (
                    not fork["matched"]
                    or fork["visible_prefix_sha256"] != fork["expected_prefix_sha256"]
                ):
                    raise ValueError("portable fork prefix mismatch")
            actual = outcomes(
                row["execution"],
                row["checks"],
                integrity=row["verifier_integrity_status"],
            )
            actual["verification"] = verification
        for field in (
            "y_target",
            "y_regression",
            "y_functional",
            "file_policy_status",
            "qualified_delivery",
            "verifier_integrity_status",
            "execution_status",
        ):
            if actual[field] != row[field]:
                raise ValueError("functional record recomputation mismatch: " + field)
        status = (
            actual["verifier_integrity_status"]
            if public_root is None
            else row["verifier_integrity_status"]
        )
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "status": "RECORDS_ONLY_RECOMPUTED",
        "records": len(bundle["rows"]),
        "integrity_counts": statuses,
        "agent_calls": 0,
        "model_calls": 0,
        "new_verifier_executions": 0,
        "scope": "saved captured candidate/verdict integrity; not a fresh Agent or source re-execution",
    }


def export(records_path, objective_path, output, *, group):
    objective = load_objective(objective_path)
    replay_result = replay(records_path, objective_path)
    raw = Path(records_path).read_bytes()
    bundle = json.loads(raw)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    public = []
    for row in bundle["rows"]:
        run = Path(row["run"])
        tag = (
            (row["method"] + "-r" + str(row["repeat"]))
            if "method" in row
            else (
                row.get("stage", "native")
                + "-r"
                + str(row.get("repeat", 1))
                + "-"
                + row["action"]
            )
        )
        relative = Path(group) / row["task_id"] / tag
        dest = output / relative
        dest.mkdir(parents=True)
        source = Path(row.get("checks_root", run.parent / (run.name + "-checks")))
        execution = {
            k: v
            for k, v in row["execution"].items()
            if k not in ("checkpoints", "decisions", "thread_id", "last_turn_id")
        }
        thread = row["execution"].get("thread_id")
        execution["thread_id"] = (
            hashlib.sha256(thread.encode()).hexdigest() if thread else None
        )
        execution["decisions"] = [
            {k: v for k, v in d.items() if k != "state"}
            for d in row["execution"].get("decisions", [])
        ]
        fields = (
            "task_id",
            "split",
            "family",
            "stage",
            "state_id",
            "repeat",
            "action",
            "method",
            "binding_sha256",
            "candidates",
            "candidate_payloads",
            "intervention_mode",
            "panel_lock_sha256",
            "reference_samples",
            "model_calls",
            "y_target",
            "y_regression",
            "y_functional",
            "file_policy_status",
            "file_policy_reason",
            "qualified_delivery",
            "execution_status",
            "verifier_integrity_status",
        )
        record = {k: row[k] for k in fields if k in row}
        record.setdefault("repeat", 1)
        record.update(
            execution=execution,
            evidence_path=relative.as_posix(),
            reported_usage=reported_usage(run),
        )
        record["checks"] = {
            kind: {
                k: v
                for k, v in check.items()
                if k in ("valid", "passed", "cases", "returncode", "error", "reason")
            }
            for kind, check in row["checks"].items()
        }
        if (source / "acceptance.json").exists():
            capture = read(source / "acceptance.json").get("capture")
            if capture:
                shutil.copyfile(
                    source / "capture/candidate.patch", dest / "candidate.patch"
                )
                record.update(
                    patch_sha256=capture["patch_sha256"],
                    changed_files=capture["changed_files"],
                )
        for kind in ("target", "regression"):
            for name in ("junit.xml", "collected.json"):
                if (source / kind / name).exists():
                    shutil.copyfile(source / kind / name, dest / (kind + "-" + name))
        if (run / "fork.json").exists():
            fork = read(run / "fork.json")
            for key in ("parent_thread", "boundary_id"):
                if fork.get(key):
                    fork[key] = hashlib.sha256(fork[key].encode()).hexdigest()
            dump(dest / "fork.json", fork)
        calls_path = run.parent / (run.name + "-model-calls.json")
        if calls_path.exists():
            shutil.copyfile(calls_path, dest / "model-calls.json")
        dump(dest / "checks.json", record["checks"])
        record["artifact_sha256"] = {
            p.name: sha(p) for p in dest.iterdir() if p.is_file()
        }
        public.append(record)
    result = {
        "objective_sha256": objective["sha256"],
        "source_records_sha256": hashlib.sha256(raw).hexdigest(),
        "private_replay": replay_result,
        "rows": public,
        "planned": bundle.get("planned"),
        "scope": "complete original candidate patches and compact verifier outputs; no session transcript/source copy/weights",
    }
    dump(output / "records.json", result)
    dump(
        output / "public-replay.json",
        replay(output / "records.json", objective_path, public_root=output),
    )
    return {
        "exported": len(public),
        "output": str(output),
        "agent_calls": 0,
        "model_calls": 0,
    }
