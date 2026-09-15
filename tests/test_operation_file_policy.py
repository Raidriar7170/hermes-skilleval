from dataclasses import replace
import shutil

import pytest
from hermes_skilleval.file_policy import disclosure, relative_path
from hermes_skilleval.repository_profile import CSVKIT, profile_for, validate_changes
from hermes_skilleval.repository_maintenance import capture, rebuild
from hermes_skilleval._maintenance.prompts import maintenance_prompt

POLICY = {
    "version": "operations-v1",
    "rules": [
        {"path": "csvkit", "operations": ["add", "modify", "delete"]},
        {"path": "tests", "operations": ["add", "modify"]},
        {
            "path": "examples",
            "operations": ["add"],
            "data_only": True,
            "max_bytes": 1000,
        },
    ],
}
PROFILE = replace(CSVKIT, file_policy=POLICY)


def candidate(tmp_path, name, content="a,b\n1,2\n", delete=False):
    base = tmp_path / "base"
    base.mkdir()
    (base / "csvkit").mkdir()
    (base / "csvkit/__init__.py").write_text("")
    if delete:
        (base / name).parent.mkdir(parents=True, exist_ok=True)
        (base / name).write_text(content)
    work = tmp_path / "work"
    shutil.copytree(base, work)
    p = work / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.unlink() if delete else p.write_text(content)
    cap = capture(base, work, tmp_path / "capture")
    return base, work, cap


def validate(work, cap):
    validate_changes(
        PROFILE,
        cap["changed_files"],
        before=cap["base_manifest"],
        after=cap["candidate_manifest"],
        candidate=work,
    )


@pytest.mark.parametrize(
    "name,content",
    [
        ("examples/sample.csv", "a,b\n1,2\n"),
        ("examples/sample.json", '{"a": 1}'),
        ("tests/test_added.py", "def test_ok(): assert True"),
    ],
)
def test_disclosed_policy_capture_and_rebuild_agree(tmp_path, name, content):
    base, work, cap = candidate(tmp_path, name, content)
    validate(work, cap)
    rebuild(
        base,
        tmp_path / "capture/candidate.patch",
        tmp_path / "rebuilt",
        cap["candidate_manifest"],
        cap["candidate_modes"],
    )
    assert disclosure(POLICY) in maintenance_prompt("request", PROFILE)
    assert (tmp_path / "rebuilt" / name).read_text() == content


@pytest.mark.parametrize(
    "name,content,delete",
    [
        ("examples/sample.py", "pass", False),
        ("examples/sample.csv", "#!/bin/sh\necho bad", False),
        ("examples/sample.csv", "x" * 1001, False),
        ("examples/original.csv", "x", True),
        ("tests/conftest.py", "pass", False),
        ("tests_evil/test.py", "pass", False),
        ("docs/README.md", "unauthorized", False),
        ("auth.json", "{}", False),
    ],
)
def test_rejected_patch_retained(tmp_path, name, content, delete):
    _, work, cap = candidate(tmp_path, name, content, delete)
    with pytest.raises(ValueError):
        validate(work, cap)
    assert (tmp_path / "capture/candidate.patch").stat().st_size > 0
    assert name in cap["changed_files"]


@pytest.mark.parametrize(
    "path",
    ["/tests/a", "../tests/a", "tests/../a", "tests//a", "tests\\a", "tests/a\n"],
)
def test_ambiguous_paths_rejected(path):
    with pytest.raises(ValueError):
        relative_path(path)


def test_legacy_profile_remains_default_deny_for_examples():
    assert "file_policy" not in CSVKIT.to_dict()
    old = profile_for({"repository": CSVKIT.repository, "profile": CSVKIT.to_dict()})
    with pytest.raises(ValueError, match="illegal patch path"):
        validate_changes(old, ["examples/sample.csv"])
    validate_changes(old, ["tests/test_added.py"])


def test_executable_mode_and_symlink_rejected(tmp_path):
    _, work, cap = candidate(tmp_path, "examples/sample.csv")
    path = work / "examples/sample.csv"
    path.chmod(0o755)
    with pytest.raises(ValueError, match="mode"):
        validate(work, cap)
    path.unlink()
    path.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        validate(work, cap)
