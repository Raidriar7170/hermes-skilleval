import shutil
import subprocess
import pytest
from hermes_skilleval.repository_maintenance import capture, manifest, rebuild


def test_capture_ignores_agent_commits_and_includes_untracked(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "module.py").write_text("old\n")
    candidate = tmp_path / "candidate"
    shutil.copytree(base, candidate)
    subprocess.run(["git", "init", "-q", str(candidate)], check=True)
    (candidate / "module.py").write_text("fixed\n")
    subprocess.run(["git", "-C", str(candidate), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(candidate),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@localhost",
            "commit",
            "-qm",
            "agent commit",
        ],
        check=True,
    )
    (candidate / "new.py").write_text("new implementation\n")
    (candidate / ".agents").mkdir()
    (candidate / ".agents" / "injected").write_text("not a patch")
    record = capture(base, candidate, tmp_path / "capture")
    assert record["changed_files"] == ["module.py", "new.py"]
    assert rebuild(
        base,
        tmp_path / "capture/candidate.patch",
        tmp_path / "rebuilt",
        record["candidate_manifest"],
    ) == manifest(candidate)


def test_deletion_and_binary_file_roundtrip(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "delete.py").write_text("x")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "data.bin").write_bytes(b"\0\xff\x01")
    record = capture(base, candidate, tmp_path / "capture")
    rebuild(
        base,
        tmp_path / "capture/candidate.patch",
        tmp_path / "rebuilt",
        record["candidate_manifest"],
    )
    assert not (tmp_path / "rebuilt/delete.py").exists()


def test_candidate_symlink_rejected(tmp_path):
    (tmp_path / "escape").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="symlink"):
        manifest(tmp_path)


def test_patch_escape_rejected(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    patch = tmp_path / "escape.patch"
    patch.write_text(
        "diff --git a/../../escape b/../../escape\nnew file mode 100644\n--- /dev/null\n+++ b/../../escape\n@@ -0,0 +1 @@\n+bad\n"
    )
    with pytest.raises(subprocess.CalledProcessError):
        rebuild(base, patch, tmp_path / "rebuilt")
    assert not (tmp_path / "escape").exists()


def test_rebuild_inside_parent_git_repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    base = tmp_path / "base"
    base.mkdir()
    (base / "a.py").write_text("before\n")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "a.py").write_text("after\n")
    cap = capture(base, candidate, tmp_path / "capture")
    rebuild(
        base,
        tmp_path / "capture/candidate.patch",
        tmp_path / "nested/rebuilt",
        cap["candidate_manifest"],
    )


def test_mode_only_change_is_captured_and_verified(tmp_path):
    from hermes_skilleval.repository_maintenance import capture, rebuild

    base = tmp_path / "base"
    base.mkdir()
    (base / "tool").write_text("echo hello\n")
    (base / "tool").chmod(0o644)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "tool").write_text("echo hello\n")
    (candidate / "tool").chmod(0o755)
    cap = capture(base, candidate, tmp_path / "capture")
    assert cap["changed_files"] == ["tool"]
    rebuild(
        base,
        tmp_path / "capture/candidate.patch",
        tmp_path / "rebuilt",
        cap["candidate_manifest"],
        cap["candidate_modes"],
    )
    assert (tmp_path / "rebuilt/tool").stat().st_mode & 0o777 == 0o755
