from __future__ import annotations

import json
from pathlib import Path

from hermes_skilleval.release_manifest import (
    build_release_manifest,
    sha256_file,
    write_release_manifest,
)


def _decision() -> dict[str, object]:
    return {
        "phase": "Phase 17",
        "artifact_type": "phase17-calibrated-release-selector",
        "decision": "KEEP_BASELINE",
        "selected_router": "baseline-minilm",
        "baseline_router": "baseline-minilm",
        "candidate_router": "finetuned-embedding",
        "approved_for_default": False,
        "regression_count": 2,
        "task_count": 16,
        "metric_deltas": {
            "recall_at_5": 0.0,
            "mrr": -0.03125,
            "ndcg_at_5": -0.023067,
            "negative_hit_rate": 0.0625,
            "negative_accepted_rate": 0.0625,
        },
    }


def _release_summary() -> dict[str, object]:
    return {
        "status": "PASS",
        "match_count": 0,
        "checks": [
            {
                "name": "required_paths",
                "status": "PASS",
                "ok": True,
                "message": "all required paths exist",
                "details": [],
            }
        ],
        "matches": {"sensitive": [], "overclaims": [], "checkpoints": []},
    }


def test_sha256_file_is_deterministic(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text('{"status": "PASS"}\n', encoding="utf-8")

    assert sha256_file(artifact) == sha256_file(artifact)
    assert len(sha256_file(artifact)) == 64


def test_build_release_manifest_records_decision_and_artifact_hashes(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    task_decisions_path = tmp_path / "task-decisions.jsonl"
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")
    task_decisions_path.write_text('{"task_id": "a"}\n', encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path, task_decisions_path],
        command_records=[
            {
                "name": "select-release-router",
                "argv": ["skilleval", "select-release-router"],
                "outputs": [str(decision_path)],
            }
        ],
    )

    assert manifest["phase"] == "Phase 18"
    assert manifest["artifact_type"] == "phase18-ci-release-reproducibility-pack"
    assert manifest["status"] == "PASS"
    assert manifest["release_decision"]["decision"] == "KEEP_BASELINE"
    assert manifest["release_decision"]["selected_router"] == "baseline-minilm"
    assert manifest["release_check"]["status"] == "PASS"
    assert [artifact["path"] for artifact in manifest["artifacts"]] == [
        str(decision_path),
        str(release_summary_path),
        str(task_decisions_path),
    ]
    assert all(artifact["sha256"] for artifact in manifest["artifacts"])


def test_build_release_manifest_requires_phase17_decision(tmp_path: Path) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    decision = {**_decision(), "artifact_type": "wrong"}
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path],
        command_records=[],
    )

    assert manifest["status"] == "REVIEW_REQUIRED"
    assert (
        "decision artifact_type is not phase17-calibrated-release-selector"
        in manifest["reasons"]
    )


def test_build_release_manifest_requires_current_phase18_release_reading(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    decision = {
        **_decision(),
        "decision": "APPROVE_CANDIDATE",
        "selected_router": "finetuned-embedding",
        "approved_for_default": True,
    }
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path],
        command_records=[],
    )

    assert manifest["status"] == "REVIEW_REQUIRED"
    assert "decision must remain KEEP_BASELINE for Phase 18" in manifest["reasons"]
    assert "selected_router must remain baseline-minilm for Phase 18" in manifest[
        "reasons"
    ]
    assert "approved_for_default must remain false for Phase 18" in manifest["reasons"]


def test_build_release_manifest_requires_release_summary_pass(tmp_path: Path) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    release_summary = {**_release_summary(), "status": "REVIEW_REQUIRED"}
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    release_summary_path.write_text(json.dumps(release_summary), encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path],
        command_records=[],
    )

    assert manifest["status"] == "REVIEW_REQUIRED"
    assert "release check status is not PASS" in manifest["reasons"]


def test_build_release_manifest_records_missing_artifact(tmp_path: Path) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    missing_path = tmp_path / "missing.jsonl"
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path, missing_path],
        command_records=[],
    )

    assert manifest["status"] == "REVIEW_REQUIRED"
    assert f"missing artifact: {missing_path}" in manifest["reasons"]
    assert manifest["artifacts"][-1] == {
        "path": str(missing_path),
        "exists": False,
        "size_bytes": 0,
        "sha256": None,
    }


def test_write_release_manifest_writes_json_and_markdown(tmp_path: Path) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    output_dir = tmp_path / "phase18"
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")

    manifest = write_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path],
        command_records=[],
        output_dir=output_dir,
    )

    assert manifest["status"] == "PASS"
    manifest_json = json.loads((output_dir / "release-manifest.json").read_text())
    manifest_md = (output_dir / "release-manifest.md").read_text(encoding="utf-8")
    assert manifest_json["release_decision"]["decision"] == "KEEP_BASELINE"
    assert "# Phase 18 Release Reproducibility Manifest" in manifest_md
    assert "`baseline-minilm`" in manifest_md
