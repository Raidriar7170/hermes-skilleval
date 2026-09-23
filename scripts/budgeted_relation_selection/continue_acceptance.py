"""Resume frozen acceptance with an explicit Git permission-metadata sidecar.

Never runs a repair Agent. A failed original reconstruction remains recorded;
only non-executable permission bits absent from Git's format may be restored.
"""

import argparse
import hashlib
import json
from pathlib import Path

from hermes_skilleval.intervention.budgeted_context_study import (
    cell_path,
    evaluate,
    matrix,
)
from hermes_skilleval.intervention.budgeted_study_assets import verify
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.relation_store import atomic_json
from hermes_skilleval.intervention.repair_checks import check_source
from hermes_skilleval.repo_routing.advisory_capture import inventory, reconstruct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore_permissions(reconstructed, expected, record, patch_sha256):
    actual = inventory(reconstructed)
    differences = []
    if actual.keys() != expected.keys():
        raise ValueError("Not a permission-only reconstruction difference")
    for name in sorted(expected):
        want, got = expected[name], actual[name]
        if want == got:
            continue
        path = reconstructed / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not path.resolve().is_relative_to(reconstructed.resolve())
        ):
            raise ValueError("Unsafe reconstruction path")
        if (
            want["kind"] != "file"
            or got["kind"] != "file"
            or {k: v for k, v in want.items() if k != "mode"}
            != {k: v for k, v in got.items() if k != "mode"}
            or (want["mode"] & 0o111) != (got["mode"] & 0o111)
            or want["mode"] & 0o7000
            or got["mode"] & 0o7000
        ):
            raise ValueError("Not a non-executable permission-bit difference")
        differences.append({"path": name, "original": want, "reconstructed": got})
    if not differences:
        raise ValueError("No original reconstruction difference to recover")
    if record.exists():
        raise ValueError("Recovery already attempted; inspect original record")
    atomic_json(
        record,
        {
            "version": "git-permission-sidecar-v1",
            "original_error": "reconstructed candidate differs",
            "differences": differences,
            "content_changes": 0,
            "patch_sha256": patch_sha256,
            "original_inventory_sha256": hashlib.sha256(
                json.dumps(expected, sort_keys=True).encode()
            ).hexdigest(),
        },
    )
    for difference in differences:
        (reconstructed / difference["path"]).chmod(difference["original"]["mode"])
    if inventory(reconstructed) != expected:
        raise ValueError("Full candidate identity still differs")


def recover(task, run, overlay, image):
    output = run / "acceptance"
    snapshot = output / "capture/snapshot"
    patch = output / "capture/candidate.patch"
    if (output / "checks").exists() or (output / "acceptance.json").exists():
        raise ValueError("Not an untouched failed reconstruction")
    expected = inventory(snapshot)
    if expected != inventory(run / "source"):
        raise ValueError("Captured snapshot differs from original candidate")
    before = inventory(task / "base")
    capture = {
        "before": before,
        "after": expected,
        "changed_files": sorted(
            k
            for k in before.keys() | expected.keys()
            if before.get(k) != expected.get(k)
        ),
        "patch_sha256": sha(patch),
    }
    attempt = output / "reconstruction-attempt-2"
    attempt.mkdir(exist_ok=False)
    reconstructed = attempt / "reconstructed"
    try:
        reconstruct(task / "base", patch, reconstructed, expected)
    except ValueError as exc:
        if str(exc) != "reconstructed candidate differs":
            raise
    else:
        raise ValueError("Original reconstruction failure did not reproduce")
    sidecar = attempt / "reconstruction-metadata.json"
    restore_permissions(reconstructed, expected, sidecar, sha(patch))
    checks = check_source(
        task, reconstructed, attempt / "checks", image=image, trusted_overlay=overlay
    )
    checks["policy"] = {
        "valid": True,
        "passed": all(
            p.startswith(("lib/", "test/", "docs/")) for p in capture["changed_files"]
        ),
    }
    atomic_json(
        output / "acceptance.json",
        {
            "capture": capture,
            "checks": checks,
            "integrity": "VERIFIED",
            "reconstruction_version": "original-patch-plus-permission-sidecar-v1",
            "metadata_sidecar_sha256": sha(sidecar),
            "metadata_sidecar_path": str(sidecar.relative_to(output)),
            "check_evidence_directory": "reconstruction-attempt-2/checks",
            "execution_sha256": sha(run / "execution.json"),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["plan", "tasks", "skills", "study", "overlays"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    plan = read(args.plan)
    verify(plan, args.tasks, args.skills, args.study, overlays=args.overlays)
    cells = matrix(plan)
    if (args.study / "runner-active.json").exists() or any(
        read(cell_path(args.study, cell) / "execution.json").get("status")
        not in {"COMPLETED", "TIMEOUT", "NOT_RUN_UNAVAILABLE", "INTERRUPTED"}
        for cell in cells
    ):
        raise ValueError("Research attempts not all terminal")
    while True:
        incomplete = [
            cell
            for cell in cells
            if (cell_path(args.study, cell) / "acceptance").exists()
            and not (
                cell_path(args.study, cell) / "acceptance/acceptance.json"
            ).exists()
        ]
        for cell in incomplete:
            recover(
                args.tasks / cell["task_id"],
                cell_path(args.study, cell),
                args.overlays / cell["task_id"],
                plan["image"],
            )
            print("recovered permission metadata", cell, flush=True)
        try:
            evaluate(plan, args.tasks, args.study, args.overlays)
            break
        except ValueError as exc:
            if str(exc) != "reconstructed candidate differs":
                raise
            print("preserved failed reconstruction", flush=True)


if __name__ == "__main__":
    main()
