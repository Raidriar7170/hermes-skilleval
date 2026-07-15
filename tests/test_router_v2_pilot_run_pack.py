from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import hermes_skilleval.router_v2_pilot_run_pack as run_pack
from hermes_skilleval import router_v2_pilot_runtime as runtime


ROOT = Path(__file__).parents[1]
BASE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001"
)
PACKAGE = BASE / "package/router-v2-v4-internal-training-package-001"
TEST_COMMIT = "d" * 40
DEPENDENCIES = {
    "numpy": "2.1.0",
    "python": "3.12.0",
    "scikit-learn": "1.6.0",
    "sentence-transformers": "3.4.1",
    "torch": "2.5.1",
    "transformers": "4.48.2",
}


def _copy_contract(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in (
        PACKAGE / "accepted-pairs.jsonl",
        PACKAGE / "data-manifest.json",
        BASE / "mining/mining.jsonl",
        BASE / "mining/mining-manifest.json",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


def _json(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    assert isinstance(value, dict)
    assert payload.decode() == runtime.canonical_json_line(value)
    return value


def test_run_pack_documents_are_deterministic_complete_and_self_validating(
    tmp_path: Path,
) -> None:
    root = _copy_contract(tmp_path)
    first = run_pack.build_run_pack_documents(
        root,
        training_code_git_commit=TEST_COMMIT,
        dependency_versions=DEPENDENCIES,
    )
    second = run_pack.build_run_pack_documents(
        root,
        training_code_git_commit=TEST_COMMIT,
        dependency_versions=DEPENDENCIES,
    )
    assert first == second

    expected_payloads = {
        "sealed-handoff.json",
        *(f"sampler-plan-seed-{seed}.json" for seed in (7170, 7171, 7172)),
        *(
            f"config-arm-{arm}-seed-{seed}.json"
            for arm in "ABC"
            for seed in (7170, 7171, 7172)
        ),
    }
    assert set(first) == {*expected_payloads, "run-pack-manifest.json"}
    handoff = _json(first["sealed-handoff.json"])
    assert runtime.validate_sealed_handoff(handoff) == handoff

    plans: dict[int, dict[str, Any]] = {}
    for seed in (7170, 7171, 7172):
        plan = _json(first[f"sampler-plan-seed-{seed}.json"])
        assert runtime.validate_skill_unique_plan(plan, handoff) == plan
        plans[seed] = plan
        for arm in "ABC":
            config = _json(first[f"config-arm-{arm}-seed-{seed}.json"])
            assert runtime.validate_frozen_config(config, handoff, plan) == config
            assert config["output_dir"] == f"arm-{arm}/seed-{seed}"
            assert config["training_code_git_commit"] == TEST_COMMIT
            assert config["dependency_versions"] == DEPENDENCIES

    manifest = _json(first["run-pack-manifest.json"])
    assert run_pack.validate_run_pack_documents(first) == manifest
    assert manifest["schema_version"] == "router-v2-pilot-run-pack-manifest-v1"
    assert manifest["training_code_git_commit"] == TEST_COMMIT
    assert manifest["handoff_fingerprint"] == handoff["handoff_fingerprint"]
    assert manifest["row_fingerprints"] == [
        row["fingerprint"] for row in handoff["examples"]
    ]
    assert all(
        manifest[field] == value for field, value in runtime.TRUTH_FIELDS.items()
    )
    file_rows = {row["path"]: row for row in manifest["payload_files"]}
    assert set(file_rows) == expected_payloads
    for path, payload in first.items():
        if path == "run-pack-manifest.json":
            continue
        assert file_rows[path] == {
            "path": path,
            "sha256": run_pack.sha256_bytes(payload),
            "size": len(payload),
        }


def test_run_pack_rejects_input_drift_dirty_repo_and_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drift_root = _copy_contract(tmp_path / "drift")
    accepted = drift_root / PACKAGE / "accepted-pairs.jsonl"
    accepted.write_bytes(accepted.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="accepted.*SHA-256"):
        run_pack.build_run_pack_documents(
            drift_root,
            training_code_git_commit=TEST_COMMIT,
            dependency_versions=DEPENDENCIES,
        )

    root = _copy_contract(tmp_path / "publish")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "x@y.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    monkeypatch.setattr(run_pack, "dependency_versions", lambda: DEPENDENCIES)
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    execution_root = authorized / "execution"
    execution_root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)

    dirty = root / "dirty.txt"
    dirty.write_text("dirty")
    with pytest.raises(ValueError, match="clean"):
        run_pack.build_run_pack(root, execution_root=execution_root)
    assert not (execution_root / run_pack.RUN_PACK_RELATIVE_PATH).exists()
    dirty.unlink()

    monkeypatch.setattr(run_pack, "resolve_authorized_output_root", lambda _: root)
    with pytest.raises(ValueError, match="outside repository"):
        run_pack.build_run_pack(root, execution_root=root)
    monkeypatch.setattr(
        run_pack,
        "resolve_authorized_output_root",
        runtime.resolve_authorized_output_root,
    )

    clean_commit = runtime._clean_git_commit(root)
    manifest = run_pack.build_run_pack(root, execution_root=execution_root)
    output = execution_root / run_pack.RUN_PACK_RELATIVE_PATH
    assert output.is_dir()
    assert run_pack.validate_run_pack_directory(output) == manifest
    assert not list(output.parent.glob(f".{output.name}.staging-*"))
    assert runtime._clean_git_commit(root) == clean_commit

    handoff = json.loads((output / "sealed-handoff.json").read_text())
    plan = json.loads((output / "sampler-plan-seed-7170.json").read_text())
    config = json.loads((output / "config-arm-A-seed-7170.json").read_text())
    model_files = runtime._model_manifest(root)
    result = runtime.preflight_for_test(
        repository_root=root,
        config=config,
        base_model_path=tmp_path / "model-snapshot",
        output_root=execution_root,
        training_code_git_commit=clean_commit,
        dependency_versions=DEPENDENCIES,
        model_file_manifest=model_files,
    )
    assert runtime.validate_sealed_handoff(handoff) == handoff
    assert runtime.validate_skill_unique_plan(plan, handoff) == plan
    assert result["preflight_status"] == "PASS"
    with pytest.raises(ValueError, match="must not.*exist"):
        run_pack.build_run_pack(root, execution_root=execution_root)


def test_run_pack_rejects_resigned_manifest_bool_and_config_float_seed(
    tmp_path: Path,
) -> None:
    root = _copy_contract(tmp_path)
    documents = run_pack.build_run_pack_documents(
        root,
        training_code_git_commit=TEST_COMMIT,
        dependency_versions=DEPENDENCIES,
    )
    manifest = json.loads(documents["run-pack-manifest.json"])
    manifest["human_reviewer_count"] = False
    manifest["manifest_sha256"] = runtime.canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    forged_manifest = {
        **documents,
        "run-pack-manifest.json": runtime.canonical_json_line(manifest).encode(),
    }
    with pytest.raises(ValueError, match="manifest"):
        run_pack.validate_run_pack_documents(forged_manifest)

    config_path = "config-arm-A-seed-7170.json"
    config = json.loads(documents[config_path])
    config["seed"] = 7170.0
    config["config_sha256"] = runtime.canonical_sha256(
        {key: value for key, value in config.items() if key != "config_sha256"}
    )
    forged_config = {
        **documents,
        config_path: runtime.canonical_json_line(config).encode(),
    }
    with pytest.raises(ValueError, match="seed|hyperparameter"):
        run_pack.validate_run_pack_documents(forged_config)


def test_run_pack_cli_help_has_no_output_side_effect(tmp_path: Path) -> None:
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_router_v2_pilot_run_pack.py"),
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert "repository-root" in result.stdout
    assert "execution-root" in result.stdout
    assert before == sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
