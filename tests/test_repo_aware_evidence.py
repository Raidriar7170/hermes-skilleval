"""Negative controls for the public evidence verifier, not research observations."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "repo_evidence",
    Path(__file__).parents[1] / "scripts/repo_aware/recompute_execution.py",
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(tmp_path):
    patch = tmp_path / "patch"
    patch.write_text("test fixture patch")
    xml = tmp_path / "test.xml"
    xml.write_text('<testsuite><testcase classname="a" name="b"/></testsuite>')
    files = [{"path": "SKILL.md", "size": 1, "executable": False, "sha256": "a" * 64}]
    package = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    check = {
        k: True
        for k in (
            "build_ok",
            "canary_ok",
            "collection_ok",
            "image_matches",
            "candidate_import_isolated",
            "run_hashes_match",
        )
    }
    check.update(
        status="EXPORTED",
        junit="test.xml",
        junit_sha256=hashlib.sha256(xml.read_bytes()).hexdigest(),
        expected_ids=["a::b"],
        returncode=0,
    )
    cell = dict(
        run_id="run",
        actual_run_id="run",
        policy="repo-aware",
        actual_arm="R",
        action="R",
        routing_skill_ids=["skill"],
        selected_ids=["skill"],
        mounted_packages=[dict(skill_id="skill", package_sha256=package, files=files)],
        registry_id="registry",
        r_version="version",
        execution_status="STARTED",
        binding={
            k: True
            for k in (
                "single_launch",
                "launch_protocol_matches",
                "task_and_base_match",
                "qualification_matches",
                "registry_matches",
                "policy_matches",
                "r_version_present",
                "patch_applies",
                "finalize_no_error",
            )
        },
        patch=dict(
            status="EXPORTED",
            run_binding_matches=True,
            path="patch",
            sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
        ),
        checks={"target": check, "regression": check},
    )
    return cell, {"skill": package}


@pytest.mark.parametrize(
    "mutation",
    ["run", "arm", "selection", "mount", "package", "file", "version", "registry"],
)
def test_identity_tampering_is_unknown(tmp_path, mutation):
    cell, packages = fixture(tmp_path)
    assert module.quality(cell, tmp_path, True, "version", "registry", packages) == (
        1,
        [],
    )
    bad = copy.deepcopy(cell)
    if mutation == "run":
        bad["actual_run_id"] = "other"
    elif mutation == "arm":
        bad["actual_arm"] = "N"
    elif mutation == "selection":
        bad["routing_skill_ids"] = []
    elif mutation == "mount":
        bad["mounted_packages"][0]["skill_id"] = "other"
    elif mutation == "package":
        bad["mounted_packages"][0]["package_sha256"] = "b" * 64
    elif mutation == "file":
        bad["mounted_packages"][0]["files"][0]["sha256"] = "b" * 64
    elif mutation == "version":
        bad["r_version"] = "other"
    elif mutation == "registry":
        bad["registry_id"] = "other"
    result, reasons = module.quality(
        bad, tmp_path, True, "version", "registry", packages
    )
    assert result is None and reasons


def test_committed_public_tables_recompute():
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "scripts/repo_aware/check_public.py"],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def test_task_difficulty_without_action_contrast_keeps_native():
    from scripts.repo_aware.gate_recipe import train
    from hermes_skilleval.repo_routing.gate import FEATURES, decide

    def rows(split, families):
        return [
            {
                "split": split,
                "repair_family": family,
                "action": action,
                "quality": label,
                "features": [float(label)] * len(FEATURES),
                "seconds": 10 + i,
                "tokens": 20 + i,
                "source": "real_execution",  # Unit fixture only, never study evidence.
                "r_version": "unit-fixture",
            }
            for family, label in families
            for i, action in enumerate(("N", "F", "R"))
        ]

    model = train(
        rows("gate-fit", [("a", 0), ("b", 1)]),
        rows("gate-calibration", [("c", 0), ("d", 1)]),
        "unit-fixture",
    )
    assert model["quality_action_contrast_families"] == 0
    decision = decide([0.0] * len(FEATURES), model, "unit-fixture")
    assert decision["action"] == "N"
    assert decision["fallback_reason"] == "gate_data_signal_insufficient"
