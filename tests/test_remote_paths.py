import pytest

from hermes_skilleval import remote_paths


def test_validate_path_within_root_resolves_relative_path_under_local_root(tmp_path):
    root = tmp_path / "outputs"

    result = remote_paths.validate_path_within_root(
        "models/router",
        root=root,
        field="output_dir",
    )

    assert result == str((root / "models/router").resolve(strict=False))


def test_validate_path_within_root_accepts_contained_absolute_path(tmp_path):
    root = tmp_path / "outputs"
    candidate = root / "models" / "router"

    result = remote_paths.validate_path_within_root(
        candidate,
        root=root,
        field="output_dir",
    )

    assert result == str(candidate.resolve(strict=False))


def test_validate_path_within_root_rejects_sibling_prefix_escape(tmp_path):
    root = tmp_path / "outputs"
    sibling = tmp_path / "outputs-copy" / "router"

    with pytest.raises(
        ValueError,
        match=rf"output_dir must be under {root.resolve(strict=False)}/",
    ):
        remote_paths.validate_path_within_root(
            sibling,
            root=root,
            field="output_dir",
        )


def test_validate_path_within_root_rejects_parent_traversal(tmp_path):
    root = tmp_path / "outputs"

    with pytest.raises(
        ValueError,
        match=rf"output_dir must be under {root.resolve(strict=False)}/",
    ):
        remote_paths.validate_path_within_root(
            "../escape/router",
            root=root,
            field="output_dir",
        )


def test_validate_path_within_root_rejects_existing_symlink_escape(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(
        ValueError,
        match=rf"output_dir must be under {root.resolve(strict=False)}/",
    ):
        remote_paths.validate_path_within_root(
            "linked/router",
            root=root,
            field="output_dir",
        )


def test_validate_a100_user_path_remains_compatible():
    path = "/mnt/data/minghongsun/hermes-skilleval-phase14/models/router"

    assert remote_paths.validate_a100_user_path(path, field="model_dir") == path


def test_validate_a100_user_path_uses_generic_containment(monkeypatch):
    calls = []

    def fake_validate(path, *, root, field):
        calls.append((path, root, field))
        return "/canonical/model"

    monkeypatch.setattr(remote_paths, "validate_path_within_root", fake_validate)

    assert (
        remote_paths.validate_a100_user_path("models/router", field="model_dir")
        == "/canonical/model"
    )
    assert calls == [
        ("models/router", remote_paths.A100_USER_ROOT, "model_dir"),
    ]
