import builtins
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/train_embedding_router.py")


def test_train_script_cli_output_root_overrides_config_root(monkeypatch, tmp_path):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    monkeypatch.setattr(module, "write_model_manifest", lambda **kwargs: {})
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
    monkeypatch.setattr(module, "write_model_manifest", lambda **kwargs: {})
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
    monkeypatch.setattr(module, "write_model_manifest", lambda **kwargs: {})
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
    dependency_imports = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("sentence_transformers"):
            dependency_imports.append(name)
            raise AssertionError(f"dependency imported before path validation: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(
        SystemExit,
        match=rf"output_dir must be under {cli_root.resolve(strict=False)}/",
    ):
        module.main()

    assert dependency_imports == []
    assert not config_root.exists()
    assert not cli_root.exists()


def test_train_script_runs_manual_training_loop_with_fake_dependencies(
    monkeypatch, tmp_path: Path
):
    module = _load_train_script()
    _install_fake_training_modules(monkeypatch)
    monkeypatch.setattr(module, "Path", _mapping_path_factory(tmp_path))

    training_pairs = tmp_path / "training-pairs.jsonl"
    training_pairs.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "query_text": "open dashboard",
                        "skill_text": "browser smoke testing",
                        "label": 1,
                        "split": "dev",
                    }
                ),
                json.dumps(
                    {
                        "query_text": "validate before claiming",
                        "skill_text": "verification before completion",
                        "label": 1,
                        "split": "train",
                    }
                ),
                json.dumps(
                    {
                        "query_text": "open dashboard",
                        "skill_text": "systematic debugging",
                        "label": 0,
                        "split": "dev",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
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
                "training_pairs": str(training_pairs),
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

    training_pairs = tmp_path / "training-pairs.jsonl"
    training_pairs.write_text(
        json.dumps(
            {
                "query_text": "open dashboard",
                "skill_text": "browser smoke testing",
                "label": 1,
                "split": "dev",
            }
        )
        + "\n",
        encoding="utf-8",
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
                "training_pairs": str(training_pairs),
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

    training_pairs = tmp_path / "training-pairs.jsonl"
    training_pairs.write_text(
        json.dumps(
            {
                "query_text": "open dashboard",
                "skill_text": "browser smoke testing",
                "label": 1,
                "split": "dev",
            }
        )
        + "\n",
        encoding="utf-8",
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
                "training_pairs": str(training_pairs),
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
    output_root: str | None = None,
) -> Path:
    training_pairs = directory / "training-pairs.jsonl"
    training_pairs.write_text(
        json.dumps(
            {
                "query_text": "open dashboard",
                "skill_text": "browser smoke testing",
                "label": 1,
                "split": "dev",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    payload = {
        "base_model": "sentence-transformers/all-MiniLM-L6-v2",
        "batch_size": 1,
        "epochs": 1,
        "learning_rate": 2e-5,
        "output_dir": output_dir,
        "seed": 7170,
        "training_pairs": str(training_pairs),
    }
    if output_root is not None:
        payload["output_root"] = output_root
    config = directory / "train-config.json"
    config.write_text(json.dumps(payload), encoding="utf-8")
    return config


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
