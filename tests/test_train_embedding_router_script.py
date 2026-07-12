import builtins
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.training_input import (
    TrainingInputError,
    TrainingInputHandoff,
    ValidatedTrainingExample,
    load_training_input,
)
from training_input_test_support import (
    make_accepted_row,
    sha256_bytes,
    write_synthetic_training_package,
)


SCRIPT_PATH = Path("scripts/train_embedding_router.py")


def test_train_script_cli_output_root_overrides_config_root(monkeypatch, tmp_path):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    config_root = tmp_path / "config-root"
    cli_root = tmp_path / "cli-root"
    config = _write_minimal_training_config(
        tmp_path,
        output_dir="models/minilm",
        output_root=str(config_root),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_embedding_router.py",
            "--config",
            str(config),
            "--output-root",
            str(cli_root),
        ],
    )

    assert module.main() == 0

    assert (cli_root / "models" / "minilm" / "config.json").is_file()
    assert not config_root.exists()


def test_train_script_uses_relative_config_root_from_process_cwd(
    monkeypatch,
    tmp_path,
):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    config_dir = tmp_path / "config-dir"
    config_dir.mkdir()
    config = _write_minimal_training_config(
        config_dir,
        output_dir="models/minilm",
        output_root="portable-output",
    )
    process_cwd = tmp_path / "process-cwd"
    process_cwd.mkdir()
    monkeypatch.chdir(process_cwd)
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    assert module.main() == 0

    expected = process_cwd / "portable-output" / "models" / "minilm"
    assert (expected / "config.json").is_file()
    assert not (config_dir / "portable-output").exists()


def test_train_script_defaults_output_root_to_a100_user_root(monkeypatch, tmp_path):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    monkeypatch.setattr(module, "Path", _mapping_path_factory(tmp_path))
    config = _write_minimal_training_config(
        tmp_path,
        output_dir="phase14/models/minilm",
    )
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    assert module.main() == 0

    expected = tmp_path / "mapped-mnt" / "phase14" / "models" / "minilm"
    assert (expected / "config.json").is_file()


def test_train_script_records_selected_root_in_manifest_and_summary(
    monkeypatch,
    tmp_path,
):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    output_root = tmp_path / "portable-output"
    config = _write_minimal_training_config(
        tmp_path,
        output_dir="models/minilm",
        output_root=str(output_root),
    )
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    assert module.main() == 0

    canonical_root = output_root.resolve(strict=False)
    canonical_output = (canonical_root / "models" / "minilm").resolve(strict=False)
    summary = json.loads((canonical_output / "train-run-summary.json").read_text())
    manifest = json.loads((canonical_output / "model-manifest.json").read_text())
    assert summary["schema_version"] == "router-training-data-v2-train-run-summary-v3"
    assert summary["artifact_version"] == 3
    assert summary["policy_id"] == "router-training-data-v2-training-admission-v3"
    assert summary["artifact_type"] == "router-training-data-v2-train-run-summary"
    assert "phase" not in summary
    assert manifest["schema_version"] == "router-training-data-v2-model-manifest-v3"
    assert manifest["artifact_version"] == 3
    assert manifest["policy_id"] == "router-training-data-v2-training-admission-v3"
    assert manifest["artifact_type"] == "router-training-data-v2-model-manifest"
    assert "phase" not in manifest
    assert summary["output_root"] == str(canonical_root)
    assert summary["output_dir"] == str(canonical_output)
    assert manifest["model_dir"] == summary["output_dir"]


def test_train_script_rejects_cli_root_mismatch_before_imports_or_writes(
    monkeypatch,
    tmp_path,
):
    module = _load_train_script()
    config_root = tmp_path / "config-root"
    cli_root = tmp_path / "cli-root"
    config = _write_minimal_training_config(
        tmp_path,
        output_dir=str(config_root / "models" / "minilm"),
        output_root=str(config_root),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_embedding_router.py",
            "--config",
            str(config),
            "--output-root",
            str(cli_root),
        ],
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)

    with pytest.raises(
        SystemExit,
        match=rf"output_dir must be under {cli_root.resolve(strict=False)}/",
    ):
        module.main()

    assert dependency_imports == []
    assert not config_root.exists()
    assert not cli_root.exists()


def test_train_script_rejects_existing_file_config_root_before_imports_or_writes(
    monkeypatch,
    tmp_path,
):
    module = _load_train_script()
    root_file = tmp_path / "root-file"
    root_file.write_text("not a directory\n", encoding="utf-8")
    config = _write_minimal_training_config(
        tmp_path,
        output_dir="models/minilm",
        output_root=str(root_file),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["train_embedding_router.py", "--config", str(config)],
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)

    with pytest.raises(SystemExit, match="output_root must be a directory"):
        module.main()

    assert dependency_imports == []
    assert not (root_file / "models" / "minilm").exists()


def test_train_script_rejects_existing_file_cli_root_before_imports_or_writes(
    monkeypatch,
    tmp_path,
):
    module = _load_train_script()
    root_file = tmp_path / "root-file"
    root_file.write_text("not a directory\n", encoding="utf-8")
    config_root = tmp_path / "config-root"
    config = _write_minimal_training_config(
        tmp_path,
        output_dir="models/minilm",
        output_root=str(config_root),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_embedding_router.py",
            "--config",
            str(config),
            "--output-root",
            str(root_file),
        ],
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)

    with pytest.raises(SystemExit, match="output_root must be a directory"):
        module.main()

    assert dependency_imports == []
    assert not config_root.exists()
    assert not (root_file / "models" / "minilm").exists()


def test_train_script_rejects_non_path_config_root_before_imports_or_writes(
    monkeypatch,
    tmp_path,
):
    module = _load_train_script()
    config = _write_minimal_training_config(
        tmp_path,
        output_dir="models/minilm",
        output_root=7170,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["train_embedding_router.py", "--config", str(config)],
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)

    with pytest.raises(SystemExit, match="output_root must be a path"):
        module.main()

    assert dependency_imports == []
    assert not (tmp_path / "models" / "minilm").exists()


def test_train_script_runs_manual_training_loop_with_fake_dependencies(
    monkeypatch, tmp_path: Path
):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    monkeypatch.setattr(module, "Path", _mapping_path_factory(tmp_path))

    training_input_manifest = write_synthetic_training_package(
        tmp_path / "training-input-package",
        rows=[
            make_accepted_row(
                1,
                overrides={
                    "query_text": "open dashboard",
                    "skill_text": "browser smoke testing",
                },
            ),
            make_accepted_row(
                2,
                overrides={
                    "query_text": "validate before claiming",
                    "skill_text": "verification before completion",
                },
            ),
            make_accepted_row(
                3,
                supervision_label="HARD_NEGATIVE",
                overrides={
                    "query_text": "open dashboard",
                    "skill_text": "systematic debugging",
                },
            ),
        ],
    )
    config = tmp_path / "train-config.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "sentence-transformers/all-MiniLM-L6-v2",
                "batch_size": 1,
                "epochs": 1,
                "hard_negative_margin": 1.5,
                "learning_rate": 2e-5,
                "output_dir": "/mnt/data/minghongsun/phase14/models/minilm",
                "seed": 7170,
                "training_input_manifest": str(training_input_manifest),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    assert module.main() == 0

    mapped_output = tmp_path / "mapped-mnt" / "phase14" / "models" / "minilm"
    summary = json.loads((mapped_output / "train-run-summary.json").read_text())
    assert summary["trained_pair_count"] == 2
    assert summary["trained_hard_negative_pair_count"] == 1
    assert summary["hard_negative_margin"] == 1.5
    assert summary["hard_negative_optimizer_step_count"] == 1
    assert summary["optimizer_step_count"] == 3
    assert summary["device"] == "cuda"
    assert summary["final_loss"] == 0.25
    assert (mapped_output / "config.json").exists()
    model_manifest = mapped_output / "model-manifest.json"
    assert model_manifest.exists()
    assert json.loads(model_manifest.read_text())["file_count"] == 1
    assert getattr(sys.modules["torch"], "seed_value") == 7170
    assert FakeOptimizer.instances[0].lr == 2e-5
    assert FakeLossValue.backward_count == 3
    assert FakeContrastiveLoss.labels_seen == [[0]]
    assert FakeContrastiveLoss.margin_seen == 1.5
    assert FakeSentenceTransformer.save_kwargs == {"create_model_card": False}


def test_train_script_rejects_nonpositive_batch_size(monkeypatch, tmp_path: Path):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    monkeypatch.setattr(module, "Path", _mapping_path_factory(tmp_path))

    training_input_manifest = write_synthetic_training_package(
        tmp_path / "training-input-package"
    )
    config = tmp_path / "train-config.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "sentence-transformers/all-MiniLM-L6-v2",
                "batch_size": 0,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "/mnt/data/minghongsun/phase14/models/minilm",
                "seed": 7170,
                "training_input_manifest": str(training_input_manifest),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    with pytest.raises(SystemExit, match="batch_size must be positive"):
        module.main()


def test_train_script_rejects_output_dir_traversal(monkeypatch, tmp_path: Path):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    monkeypatch.setattr(module, "Path", _mapping_path_factory(tmp_path))

    training_input_manifest = write_synthetic_training_package(
        tmp_path / "training-input-package"
    )
    config = tmp_path / "train-config.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "sentence-transformers/all-MiniLM-L6-v2",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "/mnt/data/minghongsun/../leak/model",
                "seed": 7170,
                "training_input_manifest": str(training_input_manifest),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    with pytest.raises(
        SystemExit, match="output_dir must be under /mnt/data/minghongsun/"
    ):
        module.main()

    assert not (tmp_path / "leak" / "model").exists()


def test_train_script_rejects_legacy_pairs_before_framework_or_output(
    monkeypatch, tmp_path: Path
):
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    module = _load_train_script()
    legacy_pairs = tmp_path / "diagnostic-pairs.jsonl"
    legacy_pairs.write_text(
        json.dumps(
            {
                "query_text": "diagnostic only",
                "skill_text": "not accepted",
                "label": 1,
                "accepted_for_training": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "output-root"
    config = tmp_path / "legacy-config.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "model",
                "output_root": str(output_root),
                "seed": 7170,
                "training_pairs": str(legacy_pairs),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    with pytest.raises(SystemExit, match="training_input_manifest.*required"):
        module.main()

    assert dependency_imports == []
    assert not output_root.exists()


@pytest.mark.parametrize("invalid_layer", ["manifest", "path", "report", "row"])
def test_train_script_all_gate_layers_fail_before_framework_or_output(
    monkeypatch, tmp_path: Path, invalid_layer: str
):
    package = tmp_path / f"invalid-{invalid_layer}"
    if invalid_layer == "manifest":
        manifest = write_synthetic_training_package(
            package, manifest_overrides={"bypass": True}
        )
    elif invalid_layer == "path":
        manifest = write_synthetic_training_package(
            package,
            accepted_pairs_overrides={"path": "../accepted-pairs.jsonl"},
        )
    elif invalid_layer == "report":
        manifest = write_synthetic_training_package(
            package, report_overrides={"can_start_training": False}
        )
    else:
        invalid_row = make_accepted_row()
        invalid_row["label"] = 1
        manifest = write_synthetic_training_package(package, rows=[invalid_row])

    output_root = tmp_path / f"output-{invalid_layer}"
    config = tmp_path / f"config-{invalid_layer}.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "model",
                "output_root": str(output_root),
                "seed": 7170,
                "training_input_manifest": str(manifest),
            }
        ),
        encoding="utf-8",
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    module = _load_train_script()
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    with pytest.raises(SystemExit, match="TRAINING_INPUT_INVALID"):
        module.main()

    assert dependency_imports == []
    assert not output_root.exists()


def test_train_script_rejects_current_canonical_blocked_report_before_side_effects(
    monkeypatch, tmp_path: Path
):
    module = _load_train_script()
    package = tmp_path / "blocked-package"
    manifest = write_synthetic_training_package(package)
    canonical_report = Path(
        "docs/demo/router-training-data-v2-qualification-pack/qualification-report.json"
    ).read_bytes()
    canonical_payload = json.loads(canonical_report)
    assert canonical_payload["can_start_training"] is False
    assert len(canonical_payload["blocker_codes"]) == 8
    assert canonical_payload["counts"]["accepted_train_pair_count"] == 0
    (package / "qualification-report.json").write_bytes(canonical_report)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["qualification_report"]["sha256"] = sha256_bytes(canonical_report)
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    output_root = tmp_path / "output-root"
    config = tmp_path / "blocked-config.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "model",
                "output_root": str(output_root),
                "seed": 7170,
                "training_input_manifest": str(manifest),
            }
        ),
        encoding="utf-8",
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    with pytest.raises(SystemExit, match="can_start_training must be true"):
        module.main()

    assert dependency_imports == []
    assert not output_root.exists()


def test_train_script_crosses_validated_handoff_boundary_once_without_framework(
    monkeypatch, tmp_path: Path
):
    module = _load_train_script()
    rows = [
        make_accepted_row(1),
        make_accepted_row(2, supervision_label="HARD_NEGATIVE"),
    ]
    manifest = write_synthetic_training_package(
        tmp_path / "synthetic-package", rows=rows
    )
    output_root = tmp_path / "output-root"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "model",
                "output_root": str(output_root),
                "seed": 7170,
                "training_input_manifest": str(manifest),
            }
        ),
        encoding="utf-8",
    )
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    captured = []

    def fake_downstream(*, config, handoff, output_root, output_dir):
        captured.append(handoff)
        grouped = {
            label: [
                (router_query_text(example.query_text), example.skill_text)
                for example in handoff.examples
                if example.supervision_label == label
            ]
            for label in ("POSITIVE", "HARD_NEGATIVE")
        }
        assert grouped["POSITIVE"] == [(rows[0]["query_text"], rows[0]["skill_text"])]
        assert grouped["HARD_NEGATIVE"] == [
            (rows[1]["query_text"], rows[1]["skill_text"])
        ]
        return 0

    monkeypatch.setattr(module, "_run_validated_training", fake_downstream)
    monkeypatch.setattr(
        sys, "argv", ["train_embedding_router.py", "--config", str(config)]
    )

    assert module.main() == 0

    assert len(captured) == 1
    assert isinstance(captured[0].examples, tuple)
    assert dependency_imports == []
    assert not output_root.exists()


def test_training_handoff_constructors_reject_arbitrary_seals_before_side_effects(
    monkeypatch, tmp_path: Path
):
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    output_root = tmp_path / "forged-output"

    with pytest.raises(TrainingInputError, match="validation seal"):
        ValidatedTrainingExample(
            accepted_record_id="forged",
            query_text="forged prompt",
            skill_text="forged skill",
            supervision_label="POSITIVE",
            _validation_seal=object(),
            _content_fingerprint="0" * 64,
        )
    with pytest.raises(TrainingInputError, match="validation seal"):
        TrainingInputHandoff(
            package_id="forged-package",
            examples=(),
            _validation_seal=object(),
            _content_fingerprint="0" * 64,
        )

    assert dependency_imports == []
    assert not output_root.exists()


def test_object_new_forged_handoff_is_rejected_as_first_downstream_operation(
    monkeypatch, tmp_path: Path
):
    module = _load_train_script()
    forged_example = object.__new__(ValidatedTrainingExample)
    object.__setattr__(forged_example, "accepted_record_id", "forged")
    object.__setattr__(forged_example, "query_text", "forged prompt")
    object.__setattr__(forged_example, "skill_text", "forged skill")
    object.__setattr__(forged_example, "supervision_label", "POSITIVE")
    forged_handoff = object.__new__(TrainingInputHandoff)
    object.__setattr__(forged_handoff, "package_id", "forged-package")
    object.__setattr__(forged_handoff, "examples", (forged_example,))
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    output_root = tmp_path / "forged-output"

    with pytest.raises(TrainingInputError, match="validation seal"):
        module._run_validated_training(
            config={
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "seed": 7170,
            },
            handoff=forged_handoff,
            output_root=str(output_root),
            output_dir=str(output_root / "model"),
        )

    assert dependency_imports == []
    assert not output_root.exists()


@pytest.mark.parametrize("mutation", ["example_field", "examples", "package_id"])
def test_low_level_mutation_of_genuine_handoff_fails_fingerprint_before_side_effects(
    monkeypatch, tmp_path: Path, mutation: str
):
    module = _load_train_script()
    manifest = write_synthetic_training_package(tmp_path / f"genuine-{mutation}")
    handoff = load_training_input(manifest)
    if mutation == "example_field":
        object.__setattr__(handoff.examples[0], "query_text", "tampered prompt")
    elif mutation == "examples":
        object.__setattr__(handoff, "examples", ())
    else:
        object.__setattr__(handoff, "package_id", "tampered-package")
    dependency_imports = _guard_training_dependency_imports(monkeypatch)
    output_root = tmp_path / f"tampered-output-{mutation}"

    with pytest.raises(TrainingInputError, match="content fingerprint"):
        module._run_validated_training(
            config={
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "seed": 7170,
            },
            handoff=handoff,
            output_root=str(output_root),
            output_dir=str(output_root / "model"),
        )

    assert dependency_imports == []
    assert not output_root.exists()


@pytest.mark.parametrize("invalid_layer", ["manifest", "row"])
def test_invalid_package_subprocess_never_imports_shadow_frameworks_or_writes_output(
    tmp_path: Path, invalid_layer: str
):
    package = tmp_path / f"subprocess-{invalid_layer}"
    if invalid_layer == "manifest":
        manifest = write_synthetic_training_package(
            package, manifest_overrides={"bypass": True}
        )
    else:
        row = make_accepted_row()
        row["label"] = 1
        manifest = write_synthetic_training_package(package, rows=[row])
    output_root = tmp_path / f"subprocess-output-{invalid_layer}"
    config = tmp_path / f"subprocess-config-{invalid_layer}.json"
    config.write_text(
        json.dumps(
            {
                "base_model": "unused",
                "batch_size": 1,
                "epochs": 1,
                "learning_rate": 2e-5,
                "output_dir": "model",
                "output_root": str(output_root),
                "seed": 7170,
                "training_input_manifest": str(manifest),
            }
        ),
        encoding="utf-8",
    )
    import_sentinel = tmp_path / f"framework-imported-{invalid_layer}"
    shadow_root = tmp_path / f"shadow-{invalid_layer}"
    sentence_transformers = shadow_root / "sentence_transformers"
    sentence_transformers.mkdir(parents=True)
    shadow_body = (
        "from pathlib import Path\n"
        f"Path({str(import_sentinel)!r}).write_text('imported', encoding='utf-8')\n"
    )
    (shadow_root / "torch.py").write_text(shadow_body, encoding="utf-8")
    (sentence_transformers / "__init__.py").write_text(shadow_body, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(shadow_root), str(Path.cwd() / "src"), env.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH.resolve()), "--config", str(config)],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "TRAINING_INPUT_INVALID" in result.stderr
    assert not import_sentinel.exists()
    assert not output_root.exists()


def _load_train_script():
    spec = importlib.util.spec_from_file_location("train_embedding_router", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_minimal_training_config(
    directory: Path,
    *,
    output_dir: str,
    output_root: object | None = None,
) -> Path:
    training_input_manifest = write_synthetic_training_package(
        directory / "training-input-package"
    )
    payload = {
        "base_model": "sentence-transformers/all-MiniLM-L6-v2",
        "batch_size": 1,
        "epochs": 1,
        "learning_rate": 2e-5,
        "output_dir": output_dir,
        "seed": 7170,
        "training_input_manifest": str(training_input_manifest),
    }
    if output_root is not None:
        payload["output_root"] = output_root
    config = directory / "train-config.json"
    config.write_text(json.dumps(payload), encoding="utf-8")
    return config


def _guard_training_dependency_imports(monkeypatch):
    dependency_imports = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("sentence_transformers"):
            dependency_imports.append(name)
            raise AssertionError(f"dependency imported before path validation: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    return dependency_imports


def _mapping_path_factory(tmp_path: Path):
    real_path = Path

    class MappingPath:
        def __new__(cls, value):
            text = str(value)
            if text == "/mnt/data/minghongsun":
                return real_path(tmp_path / "mapped-mnt")
            if text.startswith("/mnt/data/minghongsun/"):
                relative = text.removeprefix("/mnt/data/minghongsun/")
                return real_path(tmp_path / "mapped-mnt" / relative)
            return real_path(value)

    return MappingPath


def _install_fake_training_modules(monkeypatch) -> None:
    FakeOptimizer.instances = []
    FakeLossValue.backward_count = 0
    FakeContrastiveLoss.labels_seen = []
    FakeContrastiveLoss.margin_seen = None
    FakeSentenceTransformer.save_kwargs = None

    fake_torch = types.ModuleType("torch")
    setattr(fake_torch, "seed_value", None)
    setattr(fake_torch, "cuda", types.SimpleNamespace(is_available=lambda: True))
    setattr(
        fake_torch, "empty", lambda length, device: FakeTensor([0] * length, device)
    )
    setattr(
        fake_torch, "zeros", lambda length, device: FakeTensor([0] * length, device)
    )
    setattr(
        fake_torch, "manual_seed", lambda seed: setattr(fake_torch, "seed_value", seed)
    )
    setattr(fake_torch, "optim", types.SimpleNamespace(AdamW=FakeOptimizer))

    sentence_transformers = types.ModuleType("sentence_transformers")
    setattr(sentence_transformers, "SentenceTransformer", FakeSentenceTransformer)
    sentence_transformer_module = types.ModuleType(
        "sentence_transformers.sentence_transformer"
    )
    losses_module = types.ModuleType(
        "sentence_transformers.sentence_transformer.losses"
    )
    setattr(
        losses_module, "MultipleNegativesRankingLoss", FakeMultipleNegativesRankingLoss
    )
    setattr(losses_module, "ContrastiveLoss", FakeContrastiveLoss)
    setattr(sentence_transformer_module, "losses", losses_module)

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers.sentence_transformer",
        sentence_transformer_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers.sentence_transformer.losses",
        losses_module,
    )


class FakeTensor:
    def __init__(self, value, device: str = "cpu"):
        self.value = value
        self.device = device

    def to(self, device: str):
        return FakeTensor(self.value, device)


class FakeSentenceTransformer:
    save_kwargs: dict[str, object] | None = None

    def __init__(self, base_model: str):
        self.base_model = base_model
        self.device = "cpu"
        self.trained = False

    def to(self, device: str):
        self.device = device
        return self

    def parameters(self):
        return [object()]

    def train(self):
        self.trained = True

    def tokenize(self, texts: list[str]):
        return {"input_ids": FakeTensor(texts)}

    def save(self, output_dir: str, **kwargs):
        type(self).save_kwargs = kwargs
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "config.json").write_text("{}\n", encoding="utf-8")


class FakeOptimizer:
    instances: list["FakeOptimizer"] = []

    def __init__(self, parameters, lr: float):
        self.parameters = list(parameters)
        self.lr = lr
        self.step_count = 0
        self.instances.append(self)

    def zero_grad(self):
        pass

    def step(self):
        assert FakeLossValue.backward_count > self.step_count
        self.step_count += 1


class FakeMultipleNegativesRankingLoss:
    def __init__(self, model):
        self.model = model

    def __call__(self, features, labels):
        assert self.model.trained is True
        assert labels.device == self.model.device
        for feature in features:
            assert feature["input_ids"].device == self.model.device
        return FakeLossValue(0.5)


class FakeContrastiveLoss:
    labels_seen: list[list[int]] = []
    margin_seen: float | None = None

    def __init__(self, model, margin: float):
        self.model = model
        type(self).margin_seen = margin

    def __call__(self, features, labels):
        assert self.model.trained is True
        assert labels.device == self.model.device
        self.labels_seen.append(labels.value)
        for feature in features:
            assert feature["input_ids"].device == self.model.device
        return FakeLossValue(0.25)


class FakeLossValue:
    backward_count = 0

    def __init__(self, value: float):
        self.value = value

    def backward(self):
        type(self).backward_count += 1

    def detach(self):
        return self

    def cpu(self):
        return self

    def __float__(self):
        return self.value
