"""Versioned checker repair over saved executions; never invokes an Agent."""

import argparse
import copy
import hashlib
from pathlib import Path

from hermes_skilleval.intervention.records import verify_artifacts
from hermes_skilleval.intervention.rollouts import utility
from hermes_skilleval.intervention.session import dump, inventory
from hermes_skilleval.intervention.study import read, check_once, qualify_quality


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def revalidate(collection, protocol_path, tasks, output):
    protocol = read(protocol_path)
    amendment = protocol["checker_amendment"]
    original = read(collection / "records.json")
    if original["protocol_sha256"] != amendment["parent_protocol_sha256"]:
        raise ValueError("unexpected collection protocol")
    affected = set(amendment["affected_tasks"])
    rows = []
    original_rows = []
    for task in protocol["tasks"]:
        tid = task["task_id"]
        if task["split"] == "test":
            continue
        source = collection / tid / "records.json"
        bundle = read(source)
        original_rows.extend(bundle["rows"])
        if inventory(tasks / tid / "base") != task["files"]["base"]:
            raise ValueError("base identity mismatch")
        if sha(tasks / tid / "task.json") != task["profile_sha256"]:
            raise ValueError("policy profile identity mismatch")
        if inventory(tasks / tid / "trusted") != task["files"]["trusted"]:
            raise ValueError("checker identity mismatch")
        revised = copy.deepcopy(bundle)
        for index, row in enumerate(revised["rows"]):
            verify_artifacts(row)
            if tid in affected:
                old = copy.deepcopy(row)
                checks_root = output / tid / f"checks-{index:03d}"
                checks = check_once(
                    tasks / tid, Path(row["run"]), checks_root, row["execution"]
                )
                original_checks = Path(
                    old.get("checks_root", str(row["run"]) + "-checks")
                )
                old_acceptance = original_checks / "acceptance.json"
                new_acceptance = checks_root / "acceptance.json"
                if old_acceptance.exists() and new_acceptance.exists():
                    old_capture = read(old_acceptance).get("capture")
                    new_capture = read(new_acceptance).get("capture")
                    if old_capture:
                        for field in (
                            "patch_sha256",
                            "before",
                            "after",
                            "changed_files",
                        ):
                            if (
                                not new_capture
                                or old_capture[field] != new_capture[field]
                            ):
                                raise ValueError(
                                    "original captured patch identity changed"
                                )
                quality = qualify_quality(row["execution"], checks)
                elapsed = row["execution"].get("tail_seconds")
                cost = (
                    None
                    if elapsed is None
                    else elapsed + row["execution"].get("prefix_seconds", 0)
                )
                row.update(
                    checks_root=str(checks_root.resolve()),
                    checks=checks,
                    quality=quality,
                    utility=utility(
                        quality, protocol["total_seconds"], cost, row["payload_tokens"]
                    )
                    if cost is not None
                    else None,
                    previous_verdict={
                        k: old[k] for k in ("checks", "quality", "utility")
                    },
                    original_records_sha256=sha(source),
                )
                # A checker adapter repair cannot relax the original file policy.
                if checks.get("policy") != old["checks"].get("policy"):
                    raise ValueError("policy changed during checker repair")
                verify_artifacts(row)
        revised["original_records_sha256"] = sha(source)
        destination = output / tid / "records.json"
        if destination.exists() and read(destination) != revised:
            raise ValueError("immutable derivative record changed")
        dump(destination, revised)
        rows.extend(revised["rows"])
    if original_rows != original["rows"]:
        raise ValueError("original per-task records disagree with aggregate")
    result = {
        "protocol_sha256": sha(protocol_path),
        "collection_protocol_sha256": original["protocol_sha256"],
        "original_records_sha256": sha(collection / "records.json"),
        "checker_amendment": amendment,
        "rows": rows,
    }
    destination = output / "records.json"
    if destination.exists() and read(destination) != result:
        raise ValueError("immutable derivative bundle changed")
    dump(destination, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("collection", "protocol", "tasks", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    revalidate(args.collection, args.protocol, args.tasks, args.output)
