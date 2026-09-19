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
