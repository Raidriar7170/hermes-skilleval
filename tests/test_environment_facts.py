import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_skilleval.repo_routing import environment_facts as facts
from hermes_skilleval.repo_routing import decision_cli
from hermes_skilleval.repo_routing.context import digest


def fixtures(tmp_path):
    profile = json.loads(
        Path("configs/environment-readiness-v1/profile.json").read_text()
    )
    task = next(
        t
        for t in json.loads(
            Path("artifacts/conditional-applicability-v1/tasks.json").read_text()
        )
        if t["split"] == "cal"
    )
    (tmp_path / "source.py").write_text("pass\n")
    observations = [
        {"probe_id": r["id"], "state": "SATISFIED", "details": {}}
        for r in profile["requirements"]
    ]
    record = {
        "schema": facts.SCHEMA,
        "task_id": task["task_id"],
        "repository": task["repository"],
        "source_revision": task["source_revision"],
        "scope": facts.SCOPE,
        "profile_identity": digest(profile),
        "probe_identity": facts.probe_identity(),
        "execution_authority": "NONE",
        "requirements": profile["requirements"],
        "snapshot_identity": digest(facts.source_files(tmp_path)),
        "runner_identity": "sha256:" + "a" * 64,
        "wheelhouse_identity": digest(facts.source_files(tmp_path)),
        "observations": observations,
    }
    return profile, task, record


def test_required_conditions_derived_not_summary(tmp_path):
    profile, _, record = fixtures(tmp_path)
    record["required_conditions_state"] = "SATISFIED"
    observations = record["observations"]
    assert facts.reduce_conditions(profile["requirements"], observations) == "SATISFIED"
    observations[1]["state"] = "UNKNOWN"  # pip check alone doesn't prove import
    assert facts.reduce_conditions(profile["requirements"], observations) == "UNKNOWN"
    observations[1]["state"] = "UNSATISFIED"
    assert (
        facts.reduce_conditions(profile["requirements"], observations) == "UNSATISFIED"
    )
    observations.append({"probe_id": "optional_fts", "state": "UNSATISFIED"})
    assert (
        facts.reduce_conditions(profile["requirements"], observations) == "UNSATISFIED"
    )
    observations[1]["state"] = "SATISFIED"
    assert facts.reduce_conditions(profile["requirements"], observations) == "SATISFIED"


def test_boolean_file_never_verified(tmp_path):
    p = tmp_path / "facts.json"
    p.write_text('{"task": true}')
    with pytest.raises(ValueError, match="structured probe records"):
        decision_cli.measured_environments(SimpleNamespace(environment_facts=p), [])


@pytest.mark.parametrize(
    "field",
    [
        "source_revision",
        "profile_identity",
        "snapshot_identity",
        "probe_identity",
        "repository",
    ],
)
def test_mismatches_before_any_execution(tmp_path, monkeypatch, field):
    profile, task, record = fixtures(tmp_path)
    record[field] = "wrong"
    monkeypatch.setattr(
        facts, "prepare", lambda *a, **k: pytest.fail("execution before binding")
    )
    with pytest.raises(ValueError, match="mismatch"):
        facts.verify_record(record, task, tmp_path, profile, wheelhouse=tmp_path)


def test_live_refresh_cannot_trust_state_or_supplied_image(tmp_path, monkeypatch):
    profile, task, record = fixtures(tmp_path)
    actual = {
        "runner_identity": record["runner_identity"],
        "required_conditions_state": "UNSATISFIED",
        "observations": record["observations"],
        "probe_run": {},
    }
    calls = []

    def prepare(*args, **kwargs):
        calls.append(kwargs)
        return actual

    monkeypatch.setattr(facts, "prepare", prepare)
    result = facts.verify_record(record, task, tmp_path, profile, wheelhouse=tmp_path)
    assert result["state"] == "UNSATISFIED"
    assert calls == [{"offline": True, "wheelhouse": tmp_path}]
    assert (
        facts.verify_record(record, task, tmp_path, profile, refresh=False)["state"]
        == "UNKNOWN"
    )
    actual["runner_identity"] = "different"
    with pytest.raises(ValueError, match="reconstructed recipe"):
        facts.verify_record(record, task, tmp_path, profile, wheelhouse=tmp_path)


def test_changed_dependency_inventory_rejected(tmp_path, monkeypatch):
    profile, task, record = fixtures(tmp_path)
    old = next(o for o in record["observations"] if o["probe_id"] == "dependencies")
    old["details"]["inventory_sha256"] = "old"
    actual = {
        "runner_identity": record["runner_identity"],
        "observations": copy.deepcopy(record["observations"]),
    }
    next(o for o in actual["observations"] if o["probe_id"] == "dependencies")[
        "details"
    ]["inventory_sha256"] = "new"
    monkeypatch.setattr(facts, "prepare", lambda *a, **k: actual)
    with pytest.raises(ValueError, match="dependencies changed"):
        facts.verify_record(record, task, tmp_path, profile, wheelhouse=tmp_path)


def test_output_limit_and_timeout():
    import sys

    result = facts.bounded_run([sys.executable, "-c", 'print("x" * 400000)'], 5)
    assert result["error"] == "OutputLimitExceeded"
    assert len(result["output"]) <= 256000
    result = facts.bounded_run([sys.executable, "-c", "import time;time.sleep(3)"], 0.1)
    assert result["error"] == "TimeoutExpired"


def test_source_symlink_rejected(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path.parent)
    with pytest.raises(ValueError, match="symlink"):
        facts.source_files(tmp_path)


def test_prepared_identity_excludes_timing_but_binds_semantics():
    from hermes_skilleval.repo_routing.calibration_preflight import input_identity

    task = {
        "request": "raw request",
        "source_revision": "revision",
        "context": {
            "schema": "repo-context-prose-span-v2",
            "summary": "text",
            "cost": {"wall_seconds": 1},
        },
    }
    a = input_identity([task], [], {})
    task["context"]["cost"]["wall_seconds"] = 5
    assert input_identity([task], [], {}) == a
    task["context"]["summary"] = "changed text"
    assert input_identity([task], [], {}) != a


def test_missing_environment_blocks_before_tokenizer_on_repaired_context(
    tmp_path, monkeypatch
):
    tasks, skills, _ = decision_cli.study(decision_cli.DEFAULT)
    tasks = [t for t in tasks if t["split"] == "cal"]
    for t in tasks:
        t["context"]["state"] = "usable"
        t["context"]["missing"] = []
    monkeypatch.setattr(decision_cli, "study", lambda root: (tasks, skills, "id"))
    monkeypatch.setattr(
        decision_cli,
        "tokenize",
        lambda *a, **k: pytest.fail("tokenizer before environment"),
    )
    monkeypatch.setattr(decision_cli, "validate_selected", lambda *a: None)
    contract = tmp_path / "contract.json"
    contract.write_text('{"decision_target": "applicability"}')
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes-applicability",
            "aligned-score",
            "--config",
            str(tmp_path / "absent.json"),
            "--contract",
            str(contract),
            "--output",
            str(tmp_path / "out.json"),
        ],
    )
    with pytest.raises(SystemExit) as e:
        decision_cli.main()
    assert e.value.code == 2
    result = json.loads((tmp_path / "out.json").read_text())
    assert result["model_constructions"] == 0
    assert result["calibration"]["context_known_group_upper_bound"] == 4


def test_tokenizer_axes_are_selected_before_a_preflight(tmp_path, monkeypatch):
    tasks, skills, _ = decision_cli.study(decision_cli.DEFAULT)
    tasks = [t for t in tasks if t["split"] == "cal"]
    contract = tmp_path / "contract.json"
    contract.write_text('{"decision_target":"applicability"}')
    config = tmp_path / "config.json"
    config.write_text("{}")
    monkeypatch.setattr(decision_cli, "validate_selected", lambda *a: None)
    seen = []
    monkeypatch.setattr(
        decision_cli, "tokenize", lambda *a, **kw: seen.append(kw["axes"]) or {}
    )
    args = SimpleNamespace(
        root=decision_cli.DEFAULT,
        operation="cal-score",
        split="cal",
        snapshots=None,
        contract=contract,
        tokenizer_config=config,
        environment_facts=None,
        output=tmp_path / "out.json",
    )
    decision_cli.run_preflight(args)
    assert list(seen[0]) == ["applicability"]


def test_missing_pinned_base_is_unknown_not_pass_or_dependency_failure(
    tmp_path, monkeypatch
):
    profile, task, record = fixtures(tmp_path)

    def unavailable(*args, **kwargs):
        raise ValueError("base image unavailable: None")

    monkeypatch.setattr(facts, "prepare", unavailable)
    result = facts.verify_record(record, task, tmp_path, profile, wheelhouse=tmp_path)
    assert result["state"] == "UNKNOWN"
    assert "base image unavailable" in result["reason"]
