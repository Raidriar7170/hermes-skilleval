"""Capture and verify a stopped, already-executed trial; never calls an Agent."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from hermes_skilleval.repository_profile import profile_for, validate_changes
from hermes_skilleval.repository_maintenance import capture, rebuild, manifest
from hermes_skilleval._maintenance.check import check, stopped, identity


def write(p, obj):
    p.write_text(json.dumps(obj, indent=2) + "\n")


def binding(task_root):
    return {
        "task_sha256": hashlib.sha256(
            (task_root / "task.json").read_bytes()
        ).hexdigest(),
        "trusted_manifest": {
            str(p.relative_to(task_root / "trusted")): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in (task_root / "trusted").rglob("*")
            if p.is_file()
        },
        "image_id": identity(
            profile_for(json.loads((task_root / "task.json").read_text())).image
        ),
        "harness_sha256": hashlib.sha256(
            Path(__file__).with_name("trusted_harness.py").read_bytes()
        ).hexdigest(),
        "verifier_source": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                Path(__file__).with_name("check.py"),
                Path(__file__).parent.parent / "repository_profile.py",
                Path(__file__).parent.parent / "repository_maintenance.py",
            ]
        },
    }


def finalize(executor, task_root, qualification, output):
    started_clock = time.monotonic()
    record = json.loads(executor.read_text())
    task = json.loads((task_root / "task.json").read_text())
    q = json.loads(qualification.read_text())
    output.mkdir(parents=True, exist_ok=False)
    record.update(
        derived_from=str(executor),
        resolved=None,
        patch_applies=None,
        verifier_valid=False,
        qualification_sha256=hashlib.sha256(qualification.read_bytes()).hexdigest(),
    )
    try:
        started_file = executor.parent / "started.json"
        if started_file.exists():
            launch = json.loads(started_file.read_text())
            if any(
                launch.get(k) != record.get(k)
                for k in ["run_id", "task_id", "arm", "registry_id", "base_commit"]
            ):
                raise RuntimeError("launch task/arm binding mismatch")
        if not q["qualified"] or q["qualification_binding"] != binding(task_root):
            raise RuntimeError("qualification binding changed")
        if any(
            record.get(k) != task.get(k) or q.get(k) != task.get(k)
            for k in ["task_id", "base_commit"]
        ):
            raise RuntimeError("executor task/base binding mismatch")
        if manifest(task_root / "base") != q["base_manifest"]:
            raise RuntimeError("qualified base changed")
        capture_clock = time.monotonic()
        name = (
            "hermes-utility-"
            + hashlib.sha256(record["run_id"].encode()).hexdigest()[:16]
        )
        stopped(name)
        saved = executor.parent / "saved-capture"
        if (executor.parent / "saved-capture.json").exists():
            cap = json.loads((executor.parent / "saved-capture.json").read_text())
            if (
                hashlib.sha256((saved / "candidate.patch").read_bytes()).hexdigest()
                != cap["patch_sha256"]
                or manifest(saved / "snapshot") != cap["candidate_manifest"]
            ):
                raise RuntimeError("saved patch identity changed")
        else:
            cap = capture(task_root / "base", Path(record["workspace"]), saved)
            write(executor.parent / "saved-capture.json", cap)
        record["capture_seconds"] = time.monotonic() - capture_clock
        write(output / "capture.json", cap)
        record.update(
            patch_sha256=cap["patch_sha256"], changed_files=cap["changed_files"]
        )
        if task.get("profile"):
            validate_changes(profile_for(task), cap["changed_files"])
        rebuild(
            task_root / "base",
            saved / "candidate.patch",
            output / "rebuilt",
            cap["candidate_manifest"],
            cap.get("candidate_modes"),
        )
        record["patch_applies"] = True
        results = {
            name: check(
                output / "rebuilt",
                task_root / "trusted",
                output / name,
                task[name + "_selector"],
                test_file=task["trusted_test_file"],
                profile=profile_for(task),
            )
            for name in ["target", "regression"]
        }
        record["check_evidence"] = {
            kind: {
                filename: hashlib.sha256(
                    (output / kind / filename).read_bytes()
                ).hexdigest()
                for filename in ["result.json", "junit.xml"]
                if (output / kind / filename).is_file()
            }
            for kind in results
        }
        valid = all(
            r["valid"] and sorted(c["id"] for c in r["cases"]) == q["test_ids"][name]
            for name, r in results.items()
        )
        record.update(
            verifier_valid=valid,
            resolved=all(r["passed"] for r in results.values())
            if valid and record["execution_status"] == "STARTED"
            else None,
        )
    except ValueError as exc:
        record.update(
            resolved=False
            if "symlink rejected" in str(exc)
            or "oversized candidate" in str(exc)
            or "illegal patch path" in str(exc)
            else None,
            patch_applies=False,
            error=str(exc),
        )
    except Exception as exc:
        record.update(error=str(exc))
    record["finalize_seconds"] = time.monotonic() - started_clock
    write(output / "run.json", record)
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--executor", type=Path, required=True)
    p.add_argument("--task-root", type=Path, required=True)
    p.add_argument("--qualification", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    r = finalize(a.executor, a.task_root, a.qualification, a.output)
    print(
        json.dumps(
            {
                k: r.get(k)
                for k in [
                    "run_id",
                    "resolved",
                    "patch_applies",
                    "verifier_valid",
                    "error",
                    "changed_files",
                ]
            },
            indent=2,
        )
    )
