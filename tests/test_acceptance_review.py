import subprocess
import sys
import zipfile

import pytest

from hermes_skilleval.repo_routing import acceptance_review as a
from hermes_skilleval.repo_routing.acceptance_controls import semantic_controls
from hermes_skilleval.repo_routing.acceptance_probe import command


def test_csv_independent_negative_controls(tmp_path):
    results = semantic_controls(tmp_path / "controls")
    assert len(results) == 10
    assert results["correct_alternate_names"]["observed"] == "PASS"
    assert all(
        v["observed"] == "FAIL"
        for k, v in results.items()
        if k != "correct_alternate_names"
    )


def test_csv_preserves_whitespace_order_and_multiplicity(tmp_path):
    expected = [[["h"], [" x"], [" x"], ["y"]]]
    p = tmp_path / "any.csv"
    p.write_text("h\n x\n x\ny\n")
    assert a.judge_csv(0, p.read_text(), tmp_path, expected)["status"] == "PASS"
    for content in ["h\nx\nx\ny\n", "h\n x\ny\n", "h\ny\n x\n x\n"]:
        p.write_text(content)
        assert a.judge_csv(0, content, tmp_path, expected)["status"] == "FAIL"


def test_deterministic_fixture(tmp_path):
    a.make_xlsx(tmp_path / "one.xlsx")
    a.make_xlsx(tmp_path / "two.xlsx")
    assert a.sha(tmp_path / "one.xlsx") == a.sha(tmp_path / "two.xlsx")
    with zipfile.ZipFile(tmp_path / "one.xlsx") as z:
        assert "xl/worksheets/sheet2.xml" in z.namelist()


def test_dispatch_and_unknown_entry():
    assert "run_module('sqlite_utils'," in command("package", ["--help"])[3]
    assert "run_module('sqlite_utils.cli'," in command("submodule", ["--help"])[3]
    assert (
        "from sqlite_utils.cli import cli; cli()" in command("console", ["--help"])[3]
    )
    with pytest.raises(KeyError):
        command("arbitrary-shell", [])
    assert a.judge_entry(0, "Usage: fake", "help")["status"] == "PASS"
    assert a.judge_entry(0, "Usage: fake", "function")["status"] == "FAIL"
    assert a.judge_entry(None, "Usage: fake", "help")["status"] == "UNKNOWN"
    assert (
        a.judge_entry(1, '[{"table":"acceptance_items"}]', "function")["status"]
        == "FAIL"
    )


def test_empty_junit_rejected(tmp_path):
    p = tmp_path / "report.xml"
    p.write_text("<testsuite/>")
    with pytest.raises(ValueError, match="empty JUnit"):
        a.xml_cases(p)


def test_frozen_fixture_mismatch(tmp_path):
    (tmp_path / "fixture").write_text("original")
    a.write(tmp_path / "freeze.json", dict(files=a.bound_files(tmp_path), modules={}))
    a.verify_freeze(tmp_path)
    (tmp_path / "fixture").write_text("changed")
    with pytest.raises(ValueError, match="fixture/contract"):
        a.verify_freeze(tmp_path)


def test_reconstruct_preserves_whole_patch_and_rejects_wrong_base(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "file").write_text("old\n")
    patch = tmp_path / "patch"
    patch.write_text(
        "diff --git a/file b/file\n--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n"
    )
    expected = tmp_path / "expected"
    expected.mkdir()
    (expected / "file").write_text("new\n")
    a.reconstruct(base, patch, tmp_path / "rebuilt", a.source_inventory(expected))
    (base / "file").write_text("wrong\n")
    with pytest.raises(subprocess.CalledProcessError):
        a.reconstruct(base, patch, tmp_path / "bad", a.source_inventory(expected))


def test_import_has_no_heavy_or_execution_imports():
    code = "import sys; from hermes_skilleval.repo_routing import acceptance_review; assert not any(x in sys.modules for x in ('torch','transformers','peft','hermes_skilleval.repo_routing.advisory_study'))"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_verdict_does_not_depend_on_arm_label(tmp_path):
    (tmp_path / "n.csv").write_text("h\nvalue\n")
    observations = [
        a.judge_csv(0, "h\nvalue\n", tmp_path, [[["h"], ["value"]]])
        for arm in ("N", "F2", "T2", "J2")
    ]
    assert all(v == observations[0] for v in observations)


@pytest.mark.parametrize(
    "key,value",
    [
        ("entry", "package"),
        ("argv", ["--help"]),
        ("source_mount", "/system"),
        ("cleanup_confirmed", False),
    ],
)
def test_distinct_entry_metadata_tamper(key, value):
    p = dict(
        entry="submodule",
        argv=["tables", "/fixture"],
        source_mount="/input",
        cleanup_confirmed=True,
    )
    a.validate_process(p, "submodule", ["tables", "/fixture"])
    p[key] = value
    with pytest.raises(ValueError, match="entry/argv/source/cleanup"):
        a.validate_process(p, "submodule", ["tables", "/fixture"])


def test_host_symlink_never_hashed_or_published(tmp_path):
    secret = tmp_path / "host-sentinel"
    secret.write_text("must not read")
    output = tmp_path / "output"
    output.mkdir()
    (output / "leak.csv").symlink_to(secret)
    with pytest.raises((ValueError, OSError)):
        a.sha(output / "leak.csv")
    with pytest.raises(ValueError, match="OUTPUT_BOUNDARY"):
        a.safe_files(output)
    (output / "leak.csv").unlink()
    (output / "dir").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="OUTPUT_BOUNDARY"):
        a.safe_files(output)


def test_duplicate_junit_rejected(tmp_path):
    p = tmp_path / "junit.xml"
    p.write_text(
        '<testsuite><testcase classname="x" name="y"/><testcase classname="x" name="y"/></testsuite>'
    )
    with pytest.raises(ValueError, match="duplicate"):
        a.xml_cases(p)


@pytest.mark.parametrize(
    "field,value", [("image_id", "wrong"), ("returncode", 1), ("identity", {})]
)
def test_legacy_runtime_tamper(field, value):
    p = dict(
        image_id="frozen",
        returncode=0,
        passed=True,
        identity=dict(
            source={"sqlite_utils": "/input/sqlite_utils"},
            cli_source="/input/sqlite_utils/cli.py",
            candidate_root_on_sys_path=False,
        ),
    )
    a.validate_legacy(p, "frozen", "sqlite_utils")
    p[field] = value
    with pytest.raises((ValueError, KeyError)):
        a.validate_legacy(p, "frozen", "sqlite_utils")


def _public_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (
        root / "artifacts/advisory-utility-replay-v1",
        root / "configs/acceptance-semantics-v1",
        root / "artifacts/acceptance-semantics-v1",
    )


def test_records_no_subprocess_or_model(monkeypatch):
    legacy, config, output = _public_paths()

    def forbidden(*args, **kwargs):
        raise AssertionError("execution forbidden in records")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    assert (
        a.records(legacy, config, output)["candidate_revalidation"]
        == "COMPLETED_16_OF_16"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "counter",
        "entry",
        "legacy_image",
        "legacy_returncode",
        "reproduction",
        "junit_unbound",
        "patch",
    ],
)
def test_public_records_reject_semantic_tamper(tmp_path, mutation):
    import shutil

    legacy, config, original = _public_paths()
    out = tmp_path / "evidence"
    shutil.copytree(original, out)
    rows = a.read(out / "runs.json")
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = rows[0]
    elif mutation == "counter":
        rows[0]["new_repair_agent_calls"] = 1
    elif mutation == "legacy_image":
        rows[0]["legacy_replayed"]["target"]["image_id"] = "wrong"
    elif mutation == "legacy_returncode":
        rows[0]["legacy_replayed"]["target"]["returncode"] = 1
    elif mutation == "reproduction":
        rows[0]["legacy_reproduction"] = "LEGACY_REPRODUCTION_MISMATCH"
    elif mutation == "patch":
        rows[0]["patch_sha256"] = "0" * 64
    elif mutation == "entry":
        r = next(r for r in rows if r["task_id"] == a.TASKS[1])
        process = r["obligations"]["submodule_help"]["process"]
        process["entry"] = "package"
        a.write(out / r["alias"] / "behavior/submodule_help/process.json", process)
    a.write(out / "runs.json", rows)
    index = a.read(out / "evidence-index.json")
    index["files"] = {name: a.sha(out / name) for name in index["files"]}
    if mutation == "junit_unbound":
        index["files"].pop(rows[0]["alias"] + "/behavior.xml")
    a.write(out / "evidence-index.json", index)
    with pytest.raises(ValueError):
        a.records(legacy, config, out)


def test_revalidate_and_records_have_repair_sentinels(tmp_path, monkeypatch):
    """Exercise adapter control flow; fake deterministic checks aren't study evidence."""
    from types import SimpleNamespace
    from hermes_skilleval.repo_routing import advisory_study
    from hermes_skilleval._maintenance import execution, check
    from hermes_skilleval import repository_profile

    def forbidden(*args, **kwargs):
        raise AssertionError("repair/model path called")

    monkeypatch.setattr(advisory_study, "run", forbidden)
    monkeypatch.setattr(advisory_study, "recommend", forbidden)
    monkeypatch.setattr(execution, "run_agent", forbidden)
    legacy, config, public = _public_paths()
    assert a.records(legacy, config, public)["new_repair_agent_calls"] == 0
    tasks = tmp_path / "tasks"
    runs = tmp_path / "runs"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "freeze.json").write_text("{}")
    base = tasks / "task" / "base"
    base.mkdir(parents=True)
    (base / "file").write_text("base")
    expected = a.source_inventory(base)
    a.write(runs / "run" / "capture.json", {"after": expected})
    a.write(
        tasks / "task" / "task.json",
        dict(
            target_selector="target",
            regression_selector="regression",
            trusted_test_file="test.py",
        ),
    )
    patch = tmp_path / "empty.patch"
    patch.write_text("")
    row = dict(
        affected=True,
        alias="candidate-01",
        task_id="task",
        run_id="run",
        patch_path="empty.patch",
        patch_sha256=a.sha(patch),
        rebuilt_expected_identity=a.digest(expected),
        legacy_target=True,
        legacy_regression=True,
    )
    inv = {"rows": [row]}
    a.write(cfg / "inventory.json", inv)
    monkeypatch.setattr(a, "verify_freeze", lambda _: {"image": "frozen"})
    monkeypatch.setattr(a, "inventory", lambda *args: inv)
    monkeypatch.setattr(check, "identity", lambda _: "frozen")
    monkeypatch.setattr(
        repository_profile, "profile_for", lambda _: SimpleNamespace(image="frozen")
    )
    monkeypatch.setattr(
        check,
        "check",
        lambda *args, **kwargs: dict(
            valid=True,
            passed=True,
            cases=[],
            image_id="frozen",
            returncode=0,
            identity={},
        ),
    )
    monkeypatch.setattr(
        a, "behavior", lambda *args: dict(control=dict(status="PASS", reason=None))
    )
    args = SimpleNamespace(
        config=cfg,
        legacy=tmp_path,
        tasks=tasks,
        runs=runs,
        first=False,
        output=tmp_path / "out",
    )
    a.revalidate(args)
    assert (
        a.read(args.output / "candidate-01/result.json")["new_repair_agent_calls"] == 0
    )
    # Completed result is retained byte-for-byte on resume.
    before = a.sha(args.output / "candidate-01/result.json")
    a.revalidate(args)
    assert a.sha(args.output / "candidate-01/result.json") == before
