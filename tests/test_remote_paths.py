from pathlib import Path

import pytest

from hermes_skilleval import remote_paths


def test_resolve_path_root_resolves_relative_root_from_process_cwd(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)

    result = remote_paths.resolve_path_root(
        "portable-output",
        field="output_root",
    )

    assert result == str((tmp_path / "portable-output").resolve(strict=False))


@pytest.mark.parametrize("use_symlink", [False, True])
def test_resolve_path_root_rejects_existing_non_directory(
    tmp_path,
    use_symlink,
):
    file_root = tmp_path / "root-file"
    file_root.write_text("not a directory\n", encoding="utf-8")
    selected_root = file_root
    if use_symlink:
        selected_root = tmp_path / "root-link"
        selected_root.symlink_to(file_root)

    with pytest.raises(ValueError, match="output_root must be a directory"):
        remote_paths.resolve_path_root(selected_root, field="output_root")


def test_resolve_path_root_rejects_non_path_value():
    with pytest.raises(ValueError, match="output_root must be a path"):
        remote_paths.resolve_path_root(7170, field="output_root")


def test_validate_path_within_root_rejects_non_path_candidate(tmp_path):
    with pytest.raises(ValueError, match="output_dir must be a path"):
        remote_paths.validate_path_within_root(
            7170,
            root=tmp_path / "portable-output",
            field="output_dir",
        )


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


def test_validate_a100_user_path_resolves_relative_path_from_cwd_inside_root(
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "a100-root"
    cwd = root / "project"
    cwd.mkdir(parents=True)
    monkeypatch.setattr(remote_paths, "A100_USER_ROOT", root)
    monkeypatch.chdir(cwd)

    result = remote_paths.validate_a100_user_path(
        "models/router",
        field="model_dir",
    )

    assert result == str((cwd / "models/router").resolve(strict=False))


def test_validate_a100_user_path_rejects_relative_path_from_cwd_outside_root(
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "a100-root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(remote_paths, "A100_USER_ROOT", root)
    monkeypatch.chdir(outside)

    with pytest.raises(
        ValueError,
        match=rf"model_dir must be under {root.resolve(strict=False)}/",
    ):
        remote_paths.validate_a100_user_path(
            "models/router",
            field="model_dir",
        )


def test_validate_a100_user_path_uses_generic_containment(monkeypatch, tmp_path):
    calls = []
    root = tmp_path / "a100-root"
    cwd = root / "project"
    cwd.mkdir(parents=True)
    monkeypatch.setattr(remote_paths, "A100_USER_ROOT", root)
    monkeypatch.chdir(cwd)

    def fake_validate(path, *, root, field):
        calls.append((path, root, field))
        return "/canonical/model"

    monkeypatch.setattr(remote_paths, "validate_path_within_root", fake_validate)

    assert (
        remote_paths.validate_a100_user_path("models/router", field="model_dir")
        == "/canonical/model"
    )
    assert len(calls) == 1
    candidate, delegated_root, field = calls[0]
    assert Path(candidate) == (cwd / "models/router").resolve(strict=False)
    assert delegated_root == root
    assert field == "model_dir"
