import json
from pathlib import Path

import pytest
from hermes_skilleval.repo_routing.advisory_study import schedule, select, load_catalog
from hermes_skilleval.repo_routing.advisory_capture import (
    capture_complete,
    inventory,
    reconstruct,
)


def test_schedule_balanced_fresh():
    rows = schedule()
    assert len(rows) == 32 and len({r["run_id"] for r in rows}) == 32
    assert all(r["timeout"] == 600 for r in rows)
    for t in {r["task_id"] for r in rows}:
        for arm in ("N", "F2", "T2", "J2"):
            assert sorted(
                r["repeat"] for r in rows if r["task_id"] == t and r["arm"] == arm
            ) == [1, 2]


def test_advisory_without_calibration_labels_or_semantic_filter():
    registry = {"skills": [{"id": s} for s in ["z", "b", "a"]]}
    rows = [
        {"skill_id": s, "text": 0.01, "joint": 0.001, "label": "UNKNOWN"}
        for s in ["z", "b", "a"]
    ]
    r = select("J2", registry, {}, "repo", rows)
    assert r["ranked_ids"] == ["a", "b"] and r["presented_ids"] == ["b", "a"]
    assert r["support_certified"] is False
    rows[0]["label"] = "APPLICABLE"
    assert select("J2", registry, {}, "repo", rows) == r
    with pytest.raises(ValueError):
        select("T2", registry, {}, "repo", rows[:-1])


def test_full_hidden_binary_deletion_and_mode_capture(tmp_path):
    import shutil

    base = tmp_path / "base"
    base.mkdir()
    (base / "old.txt").write_text("old")
    (base / "keep").write_text("keep")
    candidate = tmp_path / "candidate"
    shutil.copytree(base, candidate)
    (candidate / "old.txt").unlink()
    (candidate / "keep").chmod(0o755)
    (candidate / ".codex").mkdir()
    (candidate / ".codex/config.toml").write_text("forbidden")
    (candidate / "binary").write_bytes(b"\x00\xff")
    cap = capture_complete(base, candidate, tmp_path / "capture")
    assert cap["changed_files"] == [".codex/config.toml", "binary", "keep", "old.txt"]
    patch = tmp_path / "capture/candidate.patch"
    assert b".codex/config.toml" in patch.read_bytes()
    reconstruct(base, patch, tmp_path / "rebuilt", inventory(candidate))


def test_large_existing_source_retained(tmp_path):
    import shutil

    base = tmp_path / "base"
    base.mkdir()
    (base / "large").write_bytes(b"x" * 5_000_001)
    candidate = tmp_path / "candidate"
    shutil.copytree(base, candidate)
    cap = capture_complete(base, candidate, tmp_path / "capture")
    assert cap["changed_files"] == []
    assert inventory(base) == inventory(tmp_path / "capture/snapshot")


def test_catalog_verifies_legacy_bytes_without_rewriting():
    root = Path(__file__).resolve().parents[1]
    source = root / "configs/conditional-applicability-v1/registry.json"
    before = source.read_bytes()
    result = load_catalog(source, source.parent)
    assert len(result["skills"]) == 10
    assert result["legacy_registry_id"] == json.loads(before)["registry_id"]
    assert source.read_bytes() == before


def test_resume_never_repeats_completed_or_uncertain_attempt(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from hermes_skilleval.repo_routing import advisory_study as study
    from hermes_skilleval._maintenance import execution

    cell = schedule()[0]
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "public-tasks.json").write_text("[]")
    out = tmp_path / "runs"
    folder = out / cell["run_id"]
    (folder / "capture").mkdir(parents=True)
    patch = folder / "capture/candidate.patch"
    patch.write_bytes(b"")
    recommendations = tmp_path / "recommendations.json"
    recommendations.write_text("{}")
    monkeypatch.setattr(study, "verify_lock", lambda a: ({"schedule": [cell]}, {}, {}))
    monkeypatch.setattr(
        execution, "run_agent", lambda **kw: pytest.fail("must never call model")
    )
    args = SimpleNamespace(
        tasks=tasks,
        private_root=tmp_path / "private",
        workspace_root=tmp_path / "workspace",
        output=out,
        assets=tmp_path / "assets",
        recommendations=recommendations,
    )
    record = {
        **cell,
        "result": "SUCCESS",
        "patch_sha256": study.sha(patch),
        "recommendations_sha256": study.sha(recommendations),
    }
    (folder / "result.json").write_text(json.dumps(record))
    study.run(args)
    record["result"] = "UNKNOWN"
    (folder / "result.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="unresolved attempt"):
        study.run(args)
    record["run_id"] = "other"
    (folder / "result.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="binding mismatch"):
        study.run(args)


def test_symlink_payload_preserved_before_policy_rejection(tmp_path):
    from hermes_skilleval.repository_profile import RepositoryProfile, validate_changes

    base = tmp_path / "base"
    base.mkdir()
    (base / "source.py").write_text("x=1")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "source.py").write_text("x=1")
    (candidate / "tests").mkdir()
    (candidate / "tests/leak").symlink_to("/not-readable-by-controller")
    cap = capture_complete(base, candidate, tmp_path / "capture")
    assert (
        b"/not-readable-by-controller"
        in (tmp_path / "capture/candidate.patch").read_bytes()
    )
    profile = RepositoryProfile(
        "x",
        {"x": "."},
        "x",
        "main",
        "x",
        "fixed",
        ("tests",),
        {
            "version": "operations-v1",
            "rules": [{"path": "tests", "operations": ["add"]}],
        },
    )
    with pytest.raises(ValueError, match="symlink rejected"):
        validate_changes(
            profile,
            cap["changed_files"],
            before=cap["before"],
            after=cap["after"],
            candidate=tmp_path / "capture/snapshot",
        )
