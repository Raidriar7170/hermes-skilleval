"""Real Git permission-loss reproduction, without research/model execution."""

import importlib.util
from pathlib import Path

import pytest

from hermes_skilleval.repo_routing.advisory_capture import (
    capture_complete,
    inventory,
    reconstruct,
)


@pytest.fixture
def recovery():
    spec = importlib.util.spec_from_file_location(
        "acceptance_recovery",
        Path(__file__).parents[1]
        / "scripts/budgeted_relation_selection/continue_acceptance.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_git_sidecar_restores_exact_original_metadata(tmp_path, recovery):
    base, source = tmp_path / "base", tmp_path / "source"
    base.mkdir()
    source.mkdir()
    (base / "a").write_text("same")
    (source / "a").write_text("same")
    (source / "~").mkdir()
    secret_named_empty_file = source / "~/empty"
    secret_named_empty_file.write_bytes(b"")
    secret_named_empty_file.chmod(0o600)
    capture = capture_complete(base, source, tmp_path / "capture")
    rebuilt = tmp_path / "rebuilt"
    with pytest.raises(ValueError, match="reconstructed candidate differs"):
        reconstruct(
            base, tmp_path / "capture/candidate.patch", rebuilt, capture["after"]
        )
    recovery.restore_permissions(
        rebuilt, capture["after"], tmp_path / "sidecar.json", capture["patch_sha256"]
    )
    assert inventory(rebuilt) == inventory(source)
    metadata = recovery.read(tmp_path / "sidecar.json")
    assert metadata["patch_sha256"] == capture["patch_sha256"]
    assert metadata["content_changes"] == 0
    assert metadata["differences"][0]["path"] == "~/empty"


@pytest.mark.parametrize("change", ["content", "executable", "symlink"])
def test_sidecar_rejects_non_metadata_differences(tmp_path, recovery, change):
    tree = tmp_path / "tree"
    tree.mkdir()
    path = tree / "a"
    path.write_text("original")
    expected = inventory(tree)
    if change == "content":
        path.write_text("changed")
    elif change == "executable":
        path.chmod(0o755)
    else:
        path.unlink()
        path.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError):
        recovery.restore_permissions(tree, expected, tmp_path / "sidecar.json", "test")
    assert not (tmp_path / "sidecar.json").exists()
