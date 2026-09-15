"""Uniform post-hoc fixture-policy sensitivity; never re-executes an Agent."""

import argparse
import hashlib
import json
from pathlib import Path

from hermes_skilleval._maintenance.check import check
from hermes_skilleval._maintenance.finalize import binding
from hermes_skilleval.repository_maintenance import manifest, rebuild
from hermes_skilleval.repository_profile import profile_for, validate_changes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run, task_root, qualification, rule_path, output):
    record = json.loads((run / "run.json").read_text())
    task = json.loads((task_root / "task.json").read_text())
    q = json.loads(qualification.read_text())
    rule = json.loads(rule_path.read_text())
    if not str(record.get("error", "")).startswith("illegal patch path:"):
        return None
    if any(record.get(k) != task.get(k) for k in ["task_id", "base_commit"]):
        raise ValueError("original task mismatch")
    if (
        sha(qualification) != record["qualification_sha256"]
        or binding(task_root) != q["qualification_binding"]
    ):
        raise ValueError("qualification binding mismatch")
    if manifest(task_root / "base") != q["base_manifest"]:
        raise ValueError("base changed")
    patch = run / "saved-capture/candidate.patch"
    capture = json.loads((run / "saved-capture.json").read_text())
    if sha(patch) != record["patch_sha256"] or sha(patch) != capture["patch_sha256"]:
        raise ValueError("patch changed")
    rejected = []
    profile = profile_for(task)
    for name in capture["changed_files"]:
        try:
            validate_changes(profile, [name])
        except ValueError:
            rejected.append(name)
    if not rejected:
        raise ValueError("policy rejection not reproduced")
    for name in rejected:
        file = run / "saved-capture/snapshot" / name
        if not (
            name.startswith("examples/")
            and Path(name).suffix in rule["allowed_suffixes"]
            and name not in q["base_manifest"]
            and file.is_file()
            and not file.is_symlink()
            and not file.stat().st_mode & 0o111
            and file.stat().st_size <= rule["max_fixture_bytes"]
        ):
            return {
                "run_id": record["run_id"],
                "eligible": False,
                "status": "POST_HOC_SENSITIVITY",
            }
    output.mkdir(parents=True, exist_ok=False)
    rebuild(
        task_root / "base",
        patch,
        output / "rebuilt",
        capture["candidate_manifest"],
        capture.get("candidate_modes"),
    )
    checks = {
        kind: check(
            output / "rebuilt",
            task_root / "trusted",
            output / kind,
            task[kind + "_selector"],
            test_file=task["trusted_test_file"],
            profile=profile,
        )
        for kind in ["target", "regression"]
    }
    valid = all(
        r["valid"] and sorted(c["id"] for c in r["cases"]) == q["test_ids"][kind]
        for kind, r in checks.items()
    )
    result = {
        "status": "POST_HOC_SENSITIVITY",
        "eligible": True,
        "run_id": record["run_id"],
        "task_id": record["task_id"],
        "arm": record["arm"],
        "original_patch_sha256": sha(patch),
        "qualification_sha256": sha(qualification),
        "task_sha256": sha(task_root / "task.json"),
        "rule_sha256": sha(rule_path),
        "relaxed_added_fixtures": rejected,
        "verifier_valid": valid,
        "resolved": all(r["passed"] for r in checks.values()) if valid else None,
        "junit_sha256": {
            kind: sha(output / kind / "junit.xml")
            for kind in checks
            if (output / kind / "junit.xml").exists()
        },
    }
    (output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "task-root", "qualification", "rule", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    print(
        json.dumps(
            audit(a.run, a.task_root, a.qualification, a.rule, a.output), indent=2
        )
    )
