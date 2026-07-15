from __future__ import annotations

import builtins
import json
import math
import os
import shutil
import subprocess
import sys
import types
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import hermes_skilleval.router_v2_pilot_runtime as runtime


ROOT = Path(__file__).parents[1]
BASE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001"
)
PACKAGE = BASE / "package/router-v2-v4-internal-training-package-001"
TRAINING_COMMIT = "d" * 40
DEPENDENCIES = {
    "numpy": "2.1.0",
    "python": "3.12.0",
    "scikit-learn": "1.6.0",
    "sentence-transformers": "3.4.1",
    "torch": "2.5.1",
    "transformers": "4.48.2",
}


def test_training_framework_imports_are_mypy_safe_without_optional_dependencies(
    tmp_path: Path,
) -> None:
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("import torch")
        or "from sentence_transformers import SentenceTransformer, losses" in line
    ]
    probe = tmp_path / "optional_training_import_probe.py"
    probe.write_text(
        "def load() -> None:\n" + "".join(f"    {line}\n" for line in import_lines),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-site-packages", str(probe)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert len(import_lines) == 2
    assert result.returncode == 0, result.stdout + result.stderr


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


def _contract_plan_config(
    root: Path, *, arm: str = "C", seed: int = 7170
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    handoff = runtime.load_and_seal_internal_package(root)
    plan = runtime.build_skill_unique_plan(handoff, seed=seed, epochs=3)
    config = runtime.build_frozen_config(
        handoff=handoff,
        plan=plan,
        arm=arm,
        seed=seed,
        training_code_git_commit=TRAINING_COMMIT,
        dependency_versions=DEPENDENCIES,
        output_dir=f"arm-{arm}/seed-{seed}",
    )
    return handoff, plan, config


def _resign_example(example: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in example.items() if key != "fingerprint"}
    return {**value, "fingerprint": runtime.canonical_sha256(value)}


def _resign(value: dict[str, Any], field: str) -> dict[str, Any]:
    return {
        **value,
        field: runtime.canonical_sha256(
            {key: item for key, item in value.items() if key != field}
        ),
    }


def test_sealed_handoff_binds_skill_id_and_rejects_fingerprint_drift(
    tmp_path: Path,
) -> None:
    root = _copy_contract(tmp_path)
    handoff = runtime.load_and_seal_internal_package(root)

    assert handoff["positive_count"] == 64
    assert handoff["hard_negative_count"] == 52
    assert len(handoff["examples"]) == 116
    assert all("skill_id" in row and row["skill_id"] for row in handoff["examples"])
    assert runtime.validate_sealed_handoff(handoff) == handoff
    assert not (root / PACKAGE / "heldout-labels.jsonl").exists()

    tampered = deepcopy(handoff)
    tampered["examples"][0]["skill_id"] = "changed-skill"
    with pytest.raises(ValueError, match="example fingerprint mismatch"):
        runtime.validate_sealed_handoff(tampered)

    resigned = deepcopy(handoff)
    resigned["examples"][0]["skill_id"] = "changed-skill"
    resigned["examples"][0] = _resign_example(resigned["examples"][0])
    resigned["examples_sha256"] = runtime.canonical_sha256(resigned["examples"])
    with pytest.raises(ValueError, match="handoff fingerprint mismatch"):
        runtime.validate_sealed_handoff(resigned)


def test_skill_unique_sampler_is_deterministic_complete_and_collision_free(
    tmp_path: Path,
) -> None:
    root = _copy_contract(tmp_path)
    handoff = runtime.load_and_seal_internal_package(root)

    first = runtime.build_skill_unique_plan(handoff, seed=7170, epochs=3)
    second = runtime.build_skill_unique_plan(handoff, seed=7170, epochs=3)
    other = runtime.build_skill_unique_plan(handoff, seed=7171, epochs=3)

    assert first == second and first != other
    assert first["sampler_version"] == "skill-unique-v1"
    assert len(first["batches"]) == 12
    positives = {
        row["fingerprint"]
        for row in handoff["examples"]
        if row["supervision_label"] == "POSITIVE"
    }
    by_fingerprint = {row["fingerprint"]: row for row in handoff["examples"]}
    for epoch in range(3):
        batches = [row for row in first["batches"] if row["epoch"] == epoch]
        emitted = [item for batch in batches for item in batch["example_fingerprints"]]
        assert set(emitted) == positives and len(emitted) == 64
        assert all(len(batch["example_fingerprints"]) <= 16 for batch in batches)
        assert all(
            len(
                {
                    by_fingerprint[item]["skill_id"]
                    for item in batch["example_fingerprints"]
                }
            )
            == len(batch["example_fingerprints"])
            for batch in batches
        )
    assert runtime.validate_skill_unique_plan(first, handoff) == first

    collision = deepcopy(first)
    collision["batches"][0]["example_fingerprints"][1] = collision["batches"][0][
        "example_fingerprints"
    ][0]
    collision["plan_sha256"] = runtime.canonical_sha256(
        {key: value for key, value in collision.items() if key != "plan_sha256"}
    )
    with pytest.raises(ValueError, match="coverage or skill collision"):
        runtime.validate_skill_unique_plan(collision, handoff)

    reordered = deepcopy(first)
    reordered["batches"][0], reordered["batches"][1] = (
        reordered["batches"][1],
        reordered["batches"][0],
    )
    reordered["plan_sha256"] = runtime.canonical_sha256(
        {key: value for key, value in reordered.items() if key != "plan_sha256"}
    )
    with pytest.raises(ValueError, match="exact canonical batches"):
        runtime.validate_skill_unique_plan(reordered, handoff)


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_frozen_config_binds_exact_arm_lineage_and_rejects_drift(
    tmp_path: Path, arm: str
) -> None:
    root = _copy_contract(tmp_path)
    handoff, plan, config = _contract_plan_config(root, arm=arm)

    assert runtime.validate_frozen_config(config, handoff, plan) == config
    assert (config["epochs"], config["batch_size"]) == (3, 16)
    assert (config["learning_rate"], config["hard_negative_margin"]) == (
        "0.00002000",
        "1.50000000",
    )
    expected_mode = {
        "A": "EVALUATION_ONLY",
        "B": "POSITIVE_ONLY",
        "C": "POSITIVE_AND_HARD_NEGATIVE",
    }[arm]
    assert config["training_mode"] == expected_mode
    assert config["dependency_versions"] == DEPENDENCIES
    assert all(config[field] == value for field, value in runtime.TRUTH_FIELDS.items())

    for field, value in (
        ("seed", 9999),
        ("epochs", 4),
        ("sampler_plan_sha256", "0" * 64),
        ("accepted_pairs_sha256", "1" * 64),
    ):
        drifted = {**config, field: value}
        with pytest.raises(ValueError):
            runtime.validate_frozen_config(drifted, handoff, plan)


def test_preflight_is_framework_cuda_and_write_side_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_contract(tmp_path)
    handoff, plan, config = _contract_plan_config(root)
    mining = json.loads((root / BASE / "mining/mining-manifest.json").read_text())
    model_files = mining["model_file_manifest"]
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)
    imported: list[str] = []
    real_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "torch" or name.startswith("sentence_transformers"):
            imported.append(name)
            raise AssertionError("framework import during preflight")
        return real_import(name, *args, **kwargs)

    def forbidden_write(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("filesystem write during preflight")

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(
            is_available=lambda: (_ for _ in ()).throw(
                AssertionError("CUDA queried during preflight")
            )
        )
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(Path, "mkdir", forbidden_write)
    monkeypatch.setattr(Path, "write_text", forbidden_write)
    monkeypatch.setattr(Path, "write_bytes", forbidden_write)

    result = runtime.preflight_for_test(
        repository_root=root,
        config=config,
        base_model_path=tmp_path / "model-snapshot",
        output_root=authorized,
        training_code_git_commit=TRAINING_COMMIT,
        dependency_versions=DEPENDENCIES,
        model_file_manifest=model_files,
    )

    assert imported == []
    assert result["preflight_status"] == "PASS"
    assert result["training_executed"] is False
    line = runtime.canonical_json_line(result)
    assert line.endswith("\n") and line.count("\n") == 1
    assert json.loads(line) == result


def test_preflight_rejects_lineage_dependency_model_and_output_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_contract(tmp_path)
    _, _, config = _contract_plan_config(root)
    mining = json.loads((root / BASE / "mining/mining-manifest.json").read_text())
    model_files = mining["model_file_manifest"]
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)
    arguments = {
        "repository_root": root,
        "config": config,
        "base_model_path": tmp_path / "model-snapshot",
        "output_root": authorized,
        "training_code_git_commit": TRAINING_COMMIT,
        "dependency_versions": DEPENDENCIES,
        "model_file_manifest": model_files,
    }

    for field, value, message in (
        ("training_code_git_commit", "e" * 40, "training code Git commit"),
        (
            "dependency_versions",
            {**DEPENDENCIES, "torch": "drift"},
            "dependency versions",
        ),
        ("model_file_manifest", [], "base model snapshot"),
        ("output_root", Path("relative-output"), "output root"),
    ):
        drifted = {**arguments, field: value}
        with pytest.raises(ValueError, match=message):
            runtime.preflight_for_test(**drifted)


def test_arm_a_never_imports_training_framework_and_summaries_bind_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_contract(tmp_path)
    handoff, plan, config = _contract_plan_config(root, arm="A")
    real_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "torch" or name.startswith("sentence_transformers"):
            raise AssertionError("Arm A imported a training framework")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    summary = runtime.build_run_summary(
        config,
        handoff,
        plan,
        {
            "training_executed": False,
            "status": "EVALUATION_METADATA_WRITTEN",
            "device": "evaluation-only",
            "optimizer_step_count": 0,
            "hard_negative_optimizer_step_count": 0,
            "trained_example_count": 0,
            "loss_values": [],
            "model_file_manifest": [],
        },
    )
    model_manifest = runtime.build_model_manifest_contract(
        config, summary, handoff, plan
    )
    assert summary["config_sha256"] == config["config_sha256"]
    assert summary["handoff_fingerprint"] == handoff["handoff_fingerprint"]
    assert model_manifest["run_summary_sha256"] == summary["summary_sha256"]
    assert all(
        summary[field] == model_manifest[field] == value
        for field, value in runtime.TRUTH_FIELDS.items()
    )
    for field in (
        "data_manifest_sha256",
        "accepted_pairs_sha256",
        "mining_rows_sha256",
        "mining_manifest_sha256",
        "package_code_git_commit",
        "training_code_git_commit",
        "base_model_id",
        "base_model_revision",
        "base_model_file_manifest_sha256",
        "sampler_version",
        "sampler_plan_sha256",
        "dependency_versions",
    ):
        assert summary[field] == config[field]
        assert model_manifest[field] == config[field]

    forged_summary = {**summary, "training_executed": True}
    forged_summary["summary_sha256"] = runtime.canonical_sha256(
        {key: value for key, value in forged_summary.items() if key != "summary_sha256"}
    )
    with pytest.raises(ValueError, match="Arm A"):
        runtime.validate_run_summary(forged_summary, config, handoff, plan)

    forged_status = {**summary, "runtime_status": "FORGED_SUCCESS"}
    forged_status["summary_sha256"] = runtime.canonical_sha256(
        {key: value for key, value in forged_status.items() if key != "summary_sha256"}
    )
    with pytest.raises(ValueError, match="execution contract"):
        runtime.validate_run_summary(forged_status, config, handoff, plan)

    for field, value in (
        ("schema_version", "forged"),
        ("arm", "B"),
        ("seed", 7171),
        ("training_mode", "forged"),
        ("positive_count", 63),
        ("hard_negative_count", 51),
        ("output_dir", "arm-A/seed-7171"),
        ("config_sha256", "1" * 64),
        ("handoff_fingerprint", "2" * 64),
        ("accepted_pairs_sha256", "3" * 64),
    ):
        tampered = _resign({**summary, field: value}, "summary_sha256")
        with pytest.raises(ValueError, match="run summary"):
            runtime.validate_run_summary(tampered, config, handoff, plan)

    forged_manifest = {**model_manifest, "run_summary_sha256": "0" * 64}
    forged_manifest["model_manifest_sha256"] = runtime.canonical_sha256(
        {
            key: value
            for key, value in forged_manifest.items()
            if key != "model_manifest_sha256"
        }
    )
    with pytest.raises(ValueError, match="validated summary binding"):
        runtime.validate_model_manifest_contract(
            forged_manifest, config, summary, handoff, plan
        )

    for field, value in (
        ("schema_version", "forged"),
        ("arm", "B"),
        ("seed", 7171),
        ("output_dir", "arm-A/seed-7171"),
        ("config_sha256", "4" * 64),
        ("model_file_manifest_sha256", "5" * 64),
    ):
        tampered = _resign({**model_manifest, field: value}, "model_manifest_sha256")
        with pytest.raises(ValueError, match="model manifest"):
            runtime.validate_model_manifest_contract(
                tampered, config, summary, handoff, plan
            )


def test_canonical_json_and_summary_reject_nonfinite_losses(tmp_path: Path) -> None:
    root = _copy_contract(tmp_path)
    handoff, plan, config = _contract_plan_config(root, arm="B")
    model_files = [{"path": "model.bin", "sha256": "a" * 64, "size": 1}]
    summary = runtime.build_run_summary(
        config,
        handoff,
        plan,
        {
            "training_executed": True,
            "status": "TRAINING_COMPLETED",
            "device": "cpu",
            "optimizer_step_count": 12,
            "hard_negative_optimizer_step_count": 0,
            "trained_example_count": 64,
            "loss_values": [0.25] * 12,
            "model_file_manifest": model_files,
        },
    )
    for value in (math.nan, math.inf, -math.inf, True):
        losses = list(summary["loss_values"])
        losses[0] = value
        tampered = {**summary, "loss_values": losses}
        with pytest.raises(ValueError, match="finite"):
            runtime.validate_run_summary(tampered, config, handoff, plan)
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            runtime.canonical_json_line({"loss": value})

    forged_files = [{"path": "../escape", "sha256": "not-hex", "size": True}]
    tampered_files = {
        **summary,
        "model_file_manifest": forged_files,
        "model_file_manifest_sha256": runtime.canonical_sha256(forged_files),
    }
    tampered_files = _resign(tampered_files, "summary_sha256")
    with pytest.raises(ValueError, match="model files"):
        runtime.validate_run_summary(tampered_files, config, handoff, plan)


@pytest.mark.parametrize(
    ("surface", "field", "forged_value"),
    (
        ("config", "seed", 7170.0),
        ("config", "epochs", 3.0),
        ("config", "human_reviewer_count", False),
        ("preflight", "seed", 7170.0),
        ("preflight", "training_executed", 0),
        ("preflight", "files_written", False),
        ("preflight", "human_reviewer_count", False),
        ("summary", "seed", 7170.0),
        ("summary", "training_executed", 0),
        ("summary", "positive_count", 64.0),
        ("summary", "optimizer_step_count", False),
        ("summary", "human_reviewer_count", False),
        ("manifest", "seed", 7170.0),
        ("manifest", "training_executed", 0),
        ("manifest", "human_reviewer_count", False),
    ),
)
def test_contract_validators_reject_resigned_numeric_type_confusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    field: str,
    forged_value: Any,
) -> None:
    root = _copy_contract(tmp_path)
    handoff, plan, config = _contract_plan_config(root, arm="A")
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)
    model_files = runtime._model_manifest(root)
    preflight_result = runtime.preflight_for_test(
        repository_root=root,
        config=config,
        base_model_path=tmp_path / "base-model",
        output_root=authorized,
        training_code_git_commit=TRAINING_COMMIT,
        dependency_versions=DEPENDENCIES,
        model_file_manifest=model_files,
    )
    summary = runtime.build_run_summary(
        config,
        handoff,
        plan,
        {
            "training_executed": False,
            "status": "EVALUATION_METADATA_WRITTEN",
            "device": "evaluation-only",
            "optimizer_step_count": 0,
            "hard_negative_optimizer_step_count": 0,
            "trained_example_count": 0,
            "loss_values": [],
            "model_file_manifest": [],
        },
    )
    manifest = runtime.build_model_manifest_contract(config, summary, handoff, plan)

    with pytest.raises(ValueError):
        if surface == "config":
            forged = _resign({**config, field: forged_value}, "config_sha256")
            runtime.validate_frozen_config(forged, handoff, plan)
        elif surface == "preflight":
            forged = {**preflight_result, field: forged_value}
            runtime.validate_preflight_result(forged, config, handoff, plan)
        elif surface == "summary":
            forged = _resign({**summary, field: forged_value}, "summary_sha256")
            runtime.validate_run_summary(forged, config, handoff, plan)
        else:
            forged = _resign({**manifest, field: forged_value}, "model_manifest_sha256")
            runtime.validate_model_manifest_contract(
                forged, config, summary, handoff, plan
            )


def test_clean_git_commit_disables_optional_locks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        calls.append((command, kwargs["env"]))
        output = TRAINING_COMMIT + "\n" if "rev-parse" in command else ""
        return types.SimpleNamespace(stdout=output)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert runtime._clean_git_commit(Path("/repo")) == TRAINING_COMMIT
    assert len(calls) == 2
    assert all(command[:2] == ["git", "--no-optional-locks"] for command, _ in calls)
    assert all(env["GIT_OPTIONAL_LOCKS"] == "0" for _, env in calls)


def test_output_root_containment_symlink_and_no_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir()
    (authorized / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)

    project = authorized / "project"
    project.mkdir(mode=0o700)
    assert runtime.resolve_authorized_output_root(project) == project
    with pytest.raises(ValueError, match="authorized output root"):
        runtime.resolve_authorized_output_root(outside)
    with pytest.raises(ValueError, match="symlink prefix"):
        runtime.resolve_authorized_output_root(authorized / "escape" / "run")

    existing = authorized / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        runtime.resolve_training_output_dir(authorized, "existing")

    missing = authorized / "missing"
    with pytest.raises(ValueError, match="pre-existing"):
        runtime.resolve_authorized_output_root(missing)

    symlink_root = tmp_path / "symlink-root"
    symlink_root.symlink_to(authorized, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        runtime.resolve_authorized_output_root(symlink_root)

    insecure = authorized / "insecure"
    insecure.mkdir(mode=0o777)
    insecure.chmod(0o777)
    with pytest.raises(ValueError, match="group/other writable"):
        runtime.resolve_authorized_output_root(insecure)

    identity_dir = authorized / "identity"
    identity_dir.mkdir(mode=0o700)
    identity = runtime._secure_directory_identity(identity_dir, "identity")
    identity_dir.rename(authorized / "identity-old")
    identity_dir.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="identity drift"):
        runtime._verify_secure_directory_identity(identity_dir, identity, "identity")


def test_output_root_component_open_rejects_preexisting_and_late_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_tree = tmp_path / "real-tree"
    real_tree.mkdir(mode=0o700)
    (real_tree / "output").mkdir(mode=0o700)
    linked_tree = tmp_path / "linked-tree"
    linked_tree.symlink_to(real_tree, target_is_directory=True)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", linked_tree / "output")
    with pytest.raises(ValueError, match="symlink"):
        runtime.resolve_authorized_output_root(linked_tree / "output")

    level_one = tmp_path / "level-one"
    level_two = level_one / "level-two"
    level_two.mkdir(parents=True, mode=0o700)
    outside = tmp_path / "outside-late"
    outside.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", level_two)
    real_openat = runtime._openat_directory
    swapped = False

    def swap_before_next_component(parent_fd: int, name: str, label: str) -> int:
        nonlocal swapped
        fd = real_openat(parent_fd, name, label)
        if name == "level-one" and not swapped:
            swapped = True
            level_two.rename(level_one / "level-two-old")
            level_two.symlink_to(outside, target_is_directory=True)
        return fd

    monkeypatch.setattr(runtime, "_openat_directory", swap_before_next_component)
    with pytest.raises(ValueError, match="symlink"):
        runtime.resolve_authorized_output_root(level_two)


def test_atomic_output_staging_cleans_failure_retries_and_preserves_race_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)
    attempts = 0

    def flaky_writer(staging: Path) -> None:
        nonlocal attempts
        attempts += 1
        (staging / "partial").write_text("partial")
        if attempts == 1:
            raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        runtime._atomic_output_publish(authorized, "arm-A/seed-7170", flaky_writer)
    assert not (authorized / "arm-A/seed-7170").exists()
    assert list((authorized / "arm-A").glob(".seed-7170.staging-*")) == []

    published = runtime._atomic_output_publish(
        authorized, "arm-A/seed-7170", flaky_writer
    )
    assert (published / "partial").read_text() == "partial"

    def racing_publish(parent_fd: int, source_name: str, target_name: str) -> None:
        os.mkdir(target_name, mode=0o700, dir_fd=parent_fd)
        target = authorized / "arm-A" / target_name
        (target / "racer").write_text("preserve")
        raise FileExistsError("late target")

    monkeypatch.setattr(runtime, "_atomic_publish_noreplace_dirfd", racing_publish)

    def write_raced_output(staging: Path) -> None:
        (staging / "ours").write_text("do not publish")

    with pytest.raises(FileExistsError, match="late target"):
        runtime._atomic_output_publish(
            authorized,
            "arm-A/seed-7171",
            write_raced_output,
        )
    race_target = authorized / "arm-A/seed-7171"
    assert (race_target / "racer").read_text() == "preserve"
    assert not (race_target / "ours").exists()
    assert list((authorized / "arm-A").glob(".seed-7171.staging-*")) == []


def test_atomic_output_rejects_late_parent_identity_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)

    def swap_parent(staging: Path) -> None:
        (staging / "partial").write_text("partial")
        parent = authorized / "arm-B"
        parent.rename(authorized / "arm-B-old")
        parent.mkdir(mode=0o700)

    with pytest.raises(ValueError, match="identity drift"):
        runtime._atomic_output_publish(authorized, "arm-B/seed-7170", swap_parent)
    assert not (authorized / "arm-B/seed-7170").exists()
    assert list((authorized / "arm-B-old").glob(".seed-7170.staging-*")) == []


def test_executor_runs_frozen_b_and_c_and_arm_a_metadata_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_contract(tmp_path)
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)
    handoff, plan_a, config_a = _contract_plan_config(root, arm="A")
    base_model = tmp_path / "base-model"
    base_model.mkdir()
    expected_model_files = runtime._model_manifest(root)
    real_snapshot_model_files = runtime.snapshot_model_files

    def controlled_snapshot(path: Path | str) -> list[dict[str, Any]]:
        if Path(path).resolve() == base_model.resolve():
            return expected_model_files
        if Path(path).name == "base-model-input":
            return [] if reject_copied_snapshot else expected_model_files
        return real_snapshot_model_files(path)

    monkeypatch.setattr(runtime, "_clean_git_commit", lambda _: TRAINING_COMMIT)
    monkeypatch.setattr(runtime, "dependency_versions", lambda: DEPENDENCIES)
    monkeypatch.setattr(runtime, "snapshot_model_files", controlled_snapshot)
    real_copytree = shutil.copytree
    latest_source_tamper: Path | None = None
    copy_generation = 0

    def copy_then_replace_source(source: Path, target: Path, *, symlinks: bool) -> Path:
        nonlocal copy_generation, latest_source_tamper
        copied = real_copytree(source, target, symlinks=symlinks)
        copy_generation += 1
        latest_source_tamper = source / f"late-source-tamper-{copy_generation}"
        latest_source_tamper.write_text("tampered after validated copy")
        return copied

    monkeypatch.setattr(runtime.shutil, "copytree", copy_then_replace_source)

    def checked_preflight(config: dict[str, Any]) -> dict[str, Any]:
        return runtime.preflight_for_test(
            repository_root=root,
            config=config,
            base_model_path=base_model,
            output_root=authorized,
            training_code_git_commit=TRAINING_COMMIT,
            dependency_versions=DEPENDENCIES,
            model_file_manifest=expected_model_files,
        )

    reject_copied_snapshot = False

    class FakeTensor:
        def to(self, device: str) -> FakeTensor:
            return self

    class FakeLossValue:
        def backward(self) -> None:
            return None

        def detach(self) -> FakeLossValue:
            return self

        def cpu(self) -> FakeLossValue:
            return self

        def __float__(self) -> float:
            return 0.25

    class FakeLoss:
        calls = 0

        def __init__(self, model: Any, margin: float | None = None) -> None:
            self.margin = margin

        def __call__(self, features: Any, labels: Any) -> FakeLossValue:
            FakeLoss.calls += 1
            return FakeLossValue()

    class FakeOptimizer:
        steps = 0

        def __init__(self, parameters: Any, lr: float) -> None:
            assert lr == 2e-5

        def zero_grad(self) -> None:
            return None

        def step(self) -> None:
            FakeOptimizer.steps += 1

    class FakeModel:
        def __init__(self, path: str) -> None:
            model_input = Path(path)
            assert model_input.name == "base-model-input"
            assert model_input.parent.name.startswith(".seed-")
            assert latest_source_tamper is not None
            assert not (model_input / latest_source_tamper.name).exists()
            self.device = "cpu"

        def to(self, device: str) -> FakeModel:
            self.device = device
            return self

        def train(self) -> None:
            return None

        def parameters(self) -> list[Any]:
            return []

        def tokenize(self, texts: list[str]) -> dict[str, FakeTensor]:
            assert all(isinstance(text, str) and text for text in texts)
            return {"tokens": FakeTensor()}

        def save(self, path: str, create_model_card: bool = False) -> None:
            target = Path(path)
            (target / "model.bin").write_bytes(b"fake-model")

    seed_calls: list[int] = []
    fake_torch = types.ModuleType("torch")
    fake_torch.manual_seed = lambda seed: seed_calls.append(seed)  # type: ignore[attr-defined]
    fake_torch.use_deterministic_algorithms = lambda enabled: None  # type: ignore[attr-defined]
    fake_torch.cuda = types.SimpleNamespace(  # type: ignore[attr-defined]
        is_available=lambda: False, manual_seed_all=lambda seed: seed_calls.append(seed)
    )
    fake_torch.backends = types.SimpleNamespace(  # type: ignore[attr-defined]
        cudnn=types.SimpleNamespace(deterministic=False, benchmark=True)
    )
    fake_torch.optim = types.SimpleNamespace(AdamW=FakeOptimizer)  # type: ignore[attr-defined]
    fake_torch.empty = lambda length, device: [0] * length  # type: ignore[attr-defined]
    fake_torch.zeros = lambda length, device: [0] * length  # type: ignore[attr-defined]
    sentence_transformers = types.ModuleType("sentence_transformers")
    sentence_transformers.SentenceTransformer = FakeModel  # type: ignore[attr-defined]
    losses = types.SimpleNamespace(
        MultipleNegativesRankingLoss=FakeLoss, ContrastiveLoss=FakeLoss
    )
    sentence_transformers.losses = losses  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)

    result_a = runtime.execute_training_run(
        config_a,
        handoff,
        plan_a,
        repository_root=root,
        preflight_result=checked_preflight(config_a),
        base_model_path=base_model,
        output_root=authorized,
    )
    assert result_a["training_executed"] is False
    assert result_a["optimizer_step_count"] == 0
    assert FakeLoss.calls == FakeOptimizer.steps == 0

    for arm, expected_steps, expected_count in (("B", 12, 64), ("C", 24, 116)):
        FakeLoss.calls = FakeOptimizer.steps = 0
        handoff, plan, config = _contract_plan_config(root, arm=arm)
        result = runtime.execute_training_run(
            config,
            handoff,
            plan,
            repository_root=root,
            preflight_result=checked_preflight(config),
            base_model_path=base_model,
            output_root=authorized,
        )
        assert result["training_executed"] is True
        assert result["optimizer_step_count"] == expected_steps
        assert result["trained_example_count"] == expected_count
        assert FakeLoss.calls == FakeOptimizer.steps == expected_steps
        assert result["model_file_manifest_sha256"] == runtime.canonical_sha256(
            result["model_file_manifest"]
        )
    assert seed_calls and set(seed_calls) == {7170}

    reject_copied_snapshot = True
    handoff, plan, config = _contract_plan_config(root, arm="B", seed=7171)
    with pytest.raises(ValueError, match="copied base model snapshot"):
        runtime.execute_training_run(
            config,
            handoff,
            plan,
            repository_root=root,
            preflight_result=checked_preflight(config),
            base_model_path=base_model,
            output_root=authorized,
        )
    assert not (authorized / "arm-B/seed-7171").exists()
    assert list((authorized / "arm-B").glob(".seed-7171.staging-*")) == []


def test_executor_revalidates_preflight_git_dependencies_and_model_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _copy_contract(tmp_path)
    handoff, plan, config = _contract_plan_config(root, arm="A")
    expected_model_files = runtime._model_manifest(root)
    base_model = tmp_path / "empty-model"
    base_model.mkdir(mode=0o700)
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "AUTHORIZED_OUTPUT_ROOT", authorized)
    result = runtime.preflight_for_test(
        repository_root=root,
        config=config,
        base_model_path=base_model,
        output_root=authorized,
        training_code_git_commit=TRAINING_COMMIT,
        dependency_versions=DEPENDENCIES,
        model_file_manifest=expected_model_files,
    )
    monkeypatch.setattr(runtime, "_clean_git_commit", lambda _: TRAINING_COMMIT)
    monkeypatch.setattr(runtime, "dependency_versions", lambda: DEPENDENCIES)

    with pytest.raises(ValueError, match="base model snapshot"):
        runtime.execute_training_run(
            config,
            handoff,
            plan,
            repository_root=root,
            preflight_result=result,
            base_model_path=base_model,
            output_root=authorized,
        )
    assert not (authorized / "arm-A").exists()

    monkeypatch.setattr(runtime, "snapshot_model_files", lambda _: expected_model_files)
    tampered = {**result, "preflight_status": "FORGED"}
    with pytest.raises(ValueError, match="preflight"):
        runtime.execute_training_run(
            config,
            handoff,
            plan,
            repository_root=root,
            preflight_result=tampered,
            base_model_path=base_model,
            output_root=authorized,
        )
    monkeypatch.setattr(runtime, "_clean_git_commit", lambda _: "e" * 40)
    with pytest.raises(ValueError, match="Git commit"):
        runtime.execute_training_run(
            config,
            handoff,
            plan,
            repository_root=root,
            preflight_result=result,
            base_model_path=base_model,
            output_root=authorized,
        )
    assert not (authorized / "arm-A").exists()


def test_real_cli_preflight_subprocess_has_no_side_effect_or_framework_import(
    tmp_path: Path,
) -> None:
    script_source = (ROOT / "scripts/run_router_v2_pilot.py").read_text()
    assert script_source.startswith(
        "from __future__ import annotations\n\nimport sys\n\nsys.dont_write_bytecode = True\n"
    )
    root = _copy_contract(tmp_path / "fixture")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    training_commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    handoff = runtime.load_and_seal_internal_package(root)
    plan = runtime.build_skill_unique_plan(handoff, seed=7170, epochs=3)
    config = runtime.build_frozen_config(
        handoff=handoff,
        plan=plan,
        arm="A",
        seed=7170,
        training_code_git_commit=training_commit,
        dependency_versions=DEPENDENCIES,
        output_dir="arm-A/seed-7170",
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(runtime.canonical_json_line(config))
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    marker = tmp_path / "framework-imported"
    (shadow / "torch.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('torch')\n"
    )
    package = shadow / "sentence_transformers"
    package.mkdir()
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('st')\n"
    )
    model_files = runtime._model_manifest(root)
    authorized = tmp_path / "authorized"
    authorized.mkdir(mode=0o700)
    (shadow / "sitecustomize.py").write_text(
        "import sys\n"
        "sys.dont_write_bytecode=True\n"
        "import json\n"
        "import hermes_skilleval.router_v2_pilot_runtime as runtime\n"
        f"runtime.AUTHORIZED_OUTPUT_ROOT=runtime.Path({str(authorized)!r})\n"
        f"runtime.dependency_versions=lambda:json.loads({json.dumps(DEPENDENCIES)!r})\n"
        f"runtime.snapshot_model_files=lambda path:json.loads({json.dumps(model_files)!r})\n"
    )
    package.chmod(0o555)
    shadow.chmod(0o555)

    def tree_snapshot() -> list[tuple[str, bool, int]]:
        return sorted(
            (
                path.relative_to(tmp_path).as_posix(),
                path.is_dir(),
                path.stat().st_size if path.is_file() else 0,
            )
            for path in tmp_path.rglob("*")
        )

    def source_snapshot() -> list[tuple[str, bool, int]]:
        return sorted(
            (
                path.relative_to(ROOT).as_posix(),
                path.is_dir(),
                path.stat().st_size if path.is_file() else 0,
            )
            for base in (ROOT / "src/hermes_skilleval", ROOT / "scripts")
            for path in base.rglob("*")
        )

    before = tree_snapshot()
    source_before = source_snapshot()
    environment = {
        **os.environ,
        "PYTHONPATH": f"{shadow}:{ROOT / 'src'}",
    }
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_router_v2_pilot.py"),
            "--repository-root",
            str(root),
            "--config",
            str(config_path),
            "--base-model-path",
            str(tmp_path / "fake-model"),
            "--output-root",
            str(authorized),
            "--preflight-only",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    after = tree_snapshot()
    source_after = source_snapshot()
    assert before == after
    assert source_before == source_after
    assert not marker.exists()
    assert result.stderr == ""
    assert result.stdout.endswith("\n") and result.stdout.count("\n") == 1
    assert json.loads(result.stdout)["preflight_status"] == "PASS"
