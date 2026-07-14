from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hermes_skilleval.router_v2_training_pilot import MODEL_ID, MODEL_REVISION


ROOT = Path(__file__).parents[1]
SCRIPT_PATH = ROOT / "scripts/mine_router_v2_confusions.py"


class FakeEncoder:
    model_id = MODEL_ID
    model_revision = MODEL_REVISION
    device = "cpu"
    thread_count = 1
    normalize_embeddings = True

    def __init__(
        self, skill_count: int, prompt_vectors: dict[str, list[float]]
    ) -> None:
        self.skill_count = skill_count
        self.prompt_vectors = prompt_vectors
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if len(texts) == self.skill_count:
            return [
                [1.0 if row == column else 0.0 for column in range(self.skill_count)]
                for row in range(self.skill_count)
            ]
        return [self.prompt_vectors[text] for text in texts]


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mine_router_v2_confusions_script", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_frozen_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    paths = [
        Path("data/router-v2-v4/source-manifest.json"),
        Path("data/router-v2-v4/source-candidates.jsonl"),
        Path("docs/demo/phase9-real-skill-library-migration/skills.json"),
        Path(
            "artifacts/router-v2-v4/model-only-pilot/"
            "router-v2-v4-codex-model-only-pilot-001/"
            "adjudication.model-opinions.jsonl"
        ),
    ]
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


def _fake_runtime(root: Path, tmp_path: Path) -> tuple[FakeEncoder, Path]:
    skills = json.loads(
        (root / "docs/demo/phase9-real-skill-library-migration/skills.json").read_text()
    )
    skills.sort(key=lambda skill: skill["id"])
    source_rows = [
        json.loads(line)
        for line in (root / "data/router-v2-v4/source-candidates.jsonl")
        .read_text()
        .splitlines()
    ]
    skill_positions = {skill["id"]: index for index, skill in enumerate(skills)}
    negatives = {
        row["task_id"]: row["skill_id"]
        for row in source_rows
        if row["split"] == "train" and row["source_role"] == "HARD_NEGATIVE_CANDIDATE"
    }
    prompt_vectors: dict[str, list[float]] = {}
    for row in source_rows:
        if row["split"] != "train" or row["source_role"] != "POSITIVE":
            continue
        vector = [0.0] * len(skills)
        vector[skill_positions[row["positive_skill_id"]]] = 0.9
        vector[skill_positions[negatives[row["task_id"]]]] = math.sqrt(0.19)
        prompt_vectors[row["query_text"]] = vector

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    weights = snapshot / "weights.bin"
    weights.write_bytes(b"frozen-model-weights")
    (snapshot / "model.safetensors").symlink_to(weights.name)
    return FakeEncoder(len(skills), prompt_vectors), snapshot


def _assert_canonical_lf(path: Path) -> None:
    payload = path.read_bytes()
    assert payload.endswith(b"\n")
    for line in payload.splitlines(keepends=True):
        value = json.loads(line)
        expected = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
        assert line == expected


def test_script_import_is_runtime_dependency_lazy() -> None:
    before = {name: name in sys.modules for name in ("torch", "sentence_transformers")}
    _load_script()
    assert {name: name in sys.modules for name in before} == before


def test_run_mining_writes_only_validated_canonical_outputs(tmp_path: Path) -> None:
    module = _load_script()
    root = _copy_frozen_repo(tmp_path)
    encoder, snapshot = _fake_runtime(root, tmp_path)
    output_dir = tmp_path / "output"

    result = module.run_mining(
        repository_root=root,
        output_dir=output_dir,
        adapter_factory=lambda: (encoder, snapshot),
    )

    assert result["validation_status"] == "PASS"
    assert encoder.calls and [len(call) for call in encoder.calls] == [16, 64]
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "mining-manifest.json",
        "mining.jsonl",
        "prior-review-filter.json",
    ]
    for path in output_dir.iterdir():
        _assert_canonical_lf(path)
    manifest = json.loads((output_dir / "mining-manifest.json").read_text())
    mining_bytes = (output_dir / "mining.jsonl").read_bytes()
    assert manifest["mining_jsonl_sha256"] == hashlib.sha256(mining_bytes).hexdigest()
    assert manifest["model_file_manifest"] == sorted(
        manifest["model_file_manifest"], key=lambda row: row["path"]
    )
    model_record = next(
        row
        for row in manifest["model_file_manifest"]
        if row["path"] == "model.safetensors"
    )
    assert model_record == {
        "path": "model.safetensors",
        "size": len(b"frozen-model-weights"),
        "sha256": hashlib.sha256(b"frozen-model-weights").hexdigest(),
    }
    report = json.loads((output_dir / "prior-review-filter.json").read_text())
    assert (report["supported_count"], report["disputed_count"]) == (35, 29)
    assert report["retained_count"] == 35


def test_run_mining_fails_without_output_side_effects(tmp_path: Path) -> None:
    module = _load_script()
    root = _copy_frozen_repo(tmp_path)
    encoder, snapshot = _fake_runtime(root, tmp_path)
    output_dir = tmp_path / "output"
    called = False

    def adapter_factory() -> tuple[FakeEncoder, Path]:
        nonlocal called
        called = True
        return encoder, snapshot

    candidates = root / "data/router-v2-v4/source-candidates.jsonl"
    candidates.write_bytes(candidates.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source candidates SHA-256"):
        module.run_mining(
            repository_root=root,
            output_dir=output_dir,
            adapter_factory=adapter_factory,
        )
    assert not called
    assert not output_dir.exists()

    candidates.write_bytes(
        (ROOT / "data/router-v2-v4/source-candidates.jsonl").read_bytes()
    )
    output_dir.mkdir()
    marker = output_dir / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="output directory must not exist"):
        module.run_mining(
            repository_root=root,
            output_dir=output_dir,
            adapter_factory=adapter_factory,
        )
    assert marker.read_text() == "keep"

    with pytest.raises(ValueError, match="duplicate JSON key"):
        module._load_jsonl_bytes(b'{"a":1,"a":2}\n', label="fixture")


def test_fixed_inputs_reject_outside_symlink_before_any_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_script()
    root = _copy_frozen_repo(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    manifest = root / "data/router-v2-v4/source-manifest.json"
    manifest.unlink()
    manifest.symlink_to(outside)
    reads: list[Path] = []
    original_read_bytes = Path.read_bytes

    def probed_read_bytes(path: Path) -> bytes:
        reads.append(path.resolve(strict=False))
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", probed_read_bytes)
    with pytest.raises(ValueError, match="inside repository root"):
        module.run_mining(
            repository_root=root,
            output_dir=tmp_path / "output",
            adapter_factory=lambda: pytest.fail("adapter must not be loaded"),
        )
    assert reads == []
    assert not (tmp_path / "output").exists()

    monkeypatch.setattr(
        module,
        "run_mining",
        lambda **kwargs: pytest.fail(f"run_mining called with {kwargs}"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mine_router_v2_confusions.py",
            "--output-dir",
            str(tmp_path / "unused"),
            "--source-manifest",
            str(outside),
        ],
    )
    with pytest.raises(SystemExit):
        module.main()


def test_staging_write_failure_leaves_no_output_or_staging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_script()
    root = _copy_frozen_repo(tmp_path)
    encoder, snapshot = _fake_runtime(root, tmp_path)
    output_dir = tmp_path / "output"
    original_write_bytes = Path.write_bytes
    staging_writes = 0

    def failing_write_bytes(path: Path, payload: bytes) -> int:
        nonlocal staging_writes
        if path.parent.name.startswith(".output.staging-"):
            staging_writes += 1
            if staging_writes == 2:
                raise OSError("simulated second-file write failure")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", failing_write_bytes)
    with pytest.raises(OSError, match="second-file"):
        module.run_mining(
            repository_root=root,
            output_dir=output_dir,
            adapter_factory=lambda: (encoder, snapshot),
        )
    assert not output_dir.exists()
    assert list(tmp_path.glob(".output.staging-*")) == []


def test_real_adapter_uses_exact_local_cpu_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_script()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "model.safetensors").write_bytes(b"weights")
    calls: dict[str, Any] = {}

    def snapshot_download(model_id: str, **kwargs: Any) -> str:
        calls["snapshot"] = (model_id, kwargs)
        return str(snapshot)

    class FakeTorch:
        @staticmethod
        def set_num_threads(count: int) -> None:
            calls["threads"] = count

        @staticmethod
        def set_num_interop_threads(count: int) -> None:
            calls["interop_threads"] = count

        @staticmethod
        def get_num_threads() -> int:
            return int(calls.get("threads", 0))

        @staticmethod
        def get_num_interop_threads() -> int:
            return int(calls.get("interop_threads", 0))

    class FakeSentenceTransformer:
        def __init__(self, model_id: str, **kwargs: Any) -> None:
            calls["model"] = (model_id, kwargs)

        def encode(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
            calls["encode"] = (texts, kwargs)
            return [[1.0] for _ in texts]

    for name in (
        "TOKENIZERS_PARALLELISM",
        "RAYON_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=snapshot_download),
    )
    monkeypatch.setitem(sys.modules, "torch", FakeTorch())
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    adapter, resolved_snapshot = module._load_real_adapter()
    assert resolved_snapshot == snapshot
    assert calls["snapshot"] == (
        MODEL_ID,
        {"revision": MODEL_REVISION, "local_files_only": True},
    )
    assert calls["threads"] == 1
    assert calls["interop_threads"] == 1
    assert {
        name: module.os.environ[name]
        for name in (
            "TOKENIZERS_PARALLELISM",
            "RAYON_NUM_THREADS",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
        )
    } == {
        "TOKENIZERS_PARALLELISM": "false",
        "RAYON_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    assert calls["model"] == (
        MODEL_ID,
        {
            "revision": MODEL_REVISION,
            "local_files_only": True,
            "device": "cpu",
        },
    )
    assert adapter.encode(["x"]) == [[1.0]]
    assert calls["encode"] == (
        ["x"],
        {
            "normalize_embeddings": True,
            "show_progress_bar": False,
            "convert_to_numpy": True,
        },
    )

    class BadTorch(FakeTorch):
        @staticmethod
        def get_num_threads() -> int:
            return 2

    monkeypatch.setitem(sys.modules, "torch", BadTorch())
    with pytest.raises(ValueError, match="thread configuration"):
        module._load_real_adapter()
