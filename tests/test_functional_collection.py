"""Counterexample tests for shared state identity and unchanged attempt accounting."""

import json
from pathlib import Path

import pytest

from hermes_skilleval.intervention.functional_collection import (
    bind_checkpoint,
    verify_row,
)
from hermes_skilleval.intervention.session import inventory
from hermes_skilleval.intervention.study import run_once


def checkpoint(tmp_path):
    for scope in ("source", "scratch"):
        (tmp_path / scope).mkdir()
        (tmp_path / scope / "file").write_text(scope)
    meta = {
        "no_running_tool_confirmation": True,
        "candidates": ["one", "two"],
        "files": {s: inventory(tmp_path / s) for s in ("source", "scratch")},
        "visible_prefix_sha256": "prefix",
        "remaining_seconds": 321.25,
        "state": {"stage": "E1"},
    }
    (tmp_path / "checkpoint.json").write_text(json.dumps(meta))
    return tmp_path


def test_binding_detects_payload_order_budget_and_source_changes(tmp_path):
    cp = checkpoint(tmp_path)
    payloads = {"one": "first actual payload", "two": "second actual payload"}
    first = bind_checkpoint(cp, payloads)
    assert first["initial_remaining"] == 321.25
    assert (
        bind_checkpoint(cp, {**payloads, "one": "different"})["binding_sha256"]
        != first["binding_sha256"]
    )
    meta = json.loads((cp / "checkpoint.json").read_text())
    meta["candidates"].reverse()
    (cp / "checkpoint.json").write_text(json.dumps(meta))
    assert bind_checkpoint(cp, payloads)["binding_sha256"] != first["binding_sha256"]
    (cp / "source/file").write_text("mutated")
    with pytest.raises(ValueError, match="content changed"):
        bind_checkpoint(cp, payloads)


def test_running_tool_boundary_rejected(tmp_path):
    cp = checkpoint(tmp_path)
    meta = json.loads((cp / "checkpoint.json").read_text())
    meta["no_running_tool_confirmation"] = False
    (cp / "checkpoint.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="unconfirmed"):
        bind_checkpoint(cp, {"one": "a", "two": "b"})


def test_interrupted_reserved_attempt_is_unknown_without_resampling(tmp_path):
    run = tmp_path / "attempt"
    run.mkdir()
    result = run_once(Path("unused"), run, Path("unused"), Path("unused"))
    assert result["status"] == "UNKNOWN_INTERRUPTED_ATTEMPT"
    row = verify_row({"run": str(run), "execution": result, "checks": {}})
    assert row["y_functional"] is None


def test_no_candidate_capture_cannot_support_functional_label(tmp_path):
    checks = {"policy": {"valid": True, "passed": True}}
    root = tmp_path / "checks"
    root.mkdir()
    (root / "acceptance.json").write_text(json.dumps({"checks": checks}))
    row = verify_row(
        {
            "run": str(tmp_path / "run"),
            "checks_root": str(root),
            "execution": {"status": "COMPLETED", "thread_id": "observed"},
            "checks": checks,
        }
    )
    assert row["y_functional"] is None
    assert row["verifier_integrity_status"] == "INTEGRITY_UNKNOWN"


def test_receipt_rejects_changed_source_and_wrong_guidance(tmp_path):
    from hermes_skilleval.intervention.functional_collection import verify_pair_receipt

    run = tmp_path / "task/E0/r1/skill"
    run.mkdir(parents=True)
    cp = tmp_path / "checkpoint"
    cp.mkdir()
    meta = {
        "files": {"source": {"file": "source-hash"}},
        "remaining_seconds": 300,
        "state": {"stage": "E0"},
    }
    row = {
        "run": str(run),
        "task_id": "task",
        "action": "skill",
        "repeat": 1,
        "checkpoint": str(cp),
        "candidate_payloads": [{"id": "skill", "payload": "frozen instruction"}],
        "execution": {"injected": True, "model_input_observed": True},
    }
    (run.parent / "skill-intent.json").write_text(
        json.dumps({"task_id": "task", "action": "skill", "repeat": 1})
    )
    started = {
        "initial_files": meta["files"]["source"],
        "initial_remaining": 300,
        "from_checkpoint": str(cp),
    }
    (run / "started.json").write_text(json.dumps(started))
    history = run / "turn-000/public-history.json"
    history.parent.mkdir()
    history.write_text(
        json.dumps(
            {
                "turns": [
                    {
                        "items": [
                            {
                                "type": "userMessage",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "External skill guidance:\nfrozen instruction",
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        )
    )
    verify_pair_receipt(row, meta)
    history.write_text(json.dumps({"turns": []}))
    with pytest.raises(ValueError, match="not found"):
        verify_pair_receipt(row, meta)
    started["initial_files"] = {"file": "changed"}
    (run / "started.json").write_text(json.dumps(started))
    with pytest.raises(ValueError, match="bound source"):
        verify_pair_receipt(row, meta)
