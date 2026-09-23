"""Synthetic record-boundary checks; no model calls or functional observations."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def digest(plan):
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


@pytest.fixture
def records(tmp_path, monkeypatch):
    script = (
        Path(__file__).parents[1]
        / "scripts/budgeted_relation_selection/export_results.py"
    )
    spec = importlib.util.spec_from_file_location("budgeted_export", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = {
        "status": "FROZEN",
        "execution_commit": "synthetic-test-only",
        "order_seed": 1,
        "tail_repeats": 2,
        "tasks": [
            {"instance_id": x, "mechanism": x, "base_commit": x} for x in ["one", "two"]
        ],
    }
    plan["plan_digest"] = digest(plan)
    rows = [
        dict(
            row,
            functional="UNKNOWN",
            strict_functional="UNKNOWN",
            budget_status="UNKNOWN",
            tail_budget_seconds=None,
        )
        for row in module.matrix(plan)
    ]
    monkeypatch.setattr(module, "report", lambda _: {"rows": rows})
    study, output = tmp_path / "study", tmp_path / "export"
    for task in plan["tasks"]:
        module.atomic_json(
            study / "selection" / task["instance_id"] / "selection.json",
            {"status": "LOCKED", "messages": {}, "plan_digest": plan["plan_digest"]},
        )
        module.atomic_json(
            study / "public-knowledge" / task["base_commit"] / "cost.json",
            {"seconds": 0},
        )
    for row in rows:
        module.atomic_json(
            module.cell_path(study, row) / "execution.json",
            {"status": "NOT_RUN_UNAVAILABLE"},
        )
    return module, study, plan, output, rows


def test_missing_reference_and_interrupted_helper_preserve_all_cells(records):
    module, study, plan, output, _ = records
    batch = study / "selection/one/A/batch-0000"
    module.atomic_json(batch / "input.json", {})
    (batch / "server").mkdir()
    (batch / "server/events.jsonl").write_text("{broken")
    assert len(module.export(study, plan, output)) == 12
    assert len(module.read(output / "functional-results.json")["rows"]) == 24
    helper = module.read(output / "costs.json")["helper_calls"][0]
    assert helper["status"] == "UNKNOWN_MISSING_COST"
    assert helper["usage_status"] == "UNAVAILABLE_INVALID_EVENTS"
    assert helper["events_sha256"] == module.sha(batch / "server/events.jsonl")
    rows = module.read(output / "acquisition.json")["rows"]
    assert all(row["status"] == "NOT_RUN" for row in rows)


def test_rejects_changed_plan_even_with_same_matrix(records):
    module, study, plan, output, _ = records
    changed = {**plan, "execution_commit": "changed"}
    with pytest.raises(ValueError, match="plan identity"):
        module.export(study, changed, output)
    changed["plan_digest"] = digest(changed)
    with pytest.raises(ValueError, match="another plan"):
        module.export(study, changed, output)


def test_rejects_patch_different_from_verified_capture(records):
    module, study, plan, output, rows = records
    acceptance = module.cell_path(study, rows[0]) / "acceptance"
    module.atomic_json(
        acceptance / "acceptance.json", {"capture": {"patch_sha256": "wrong"}}
    )
    (acceptance / "capture").mkdir()
    (acceptance / "capture/candidate.patch").write_text("synthetic")
    with pytest.raises(ValueError, match="patch changed"):
        module.export(study, plan, output)
