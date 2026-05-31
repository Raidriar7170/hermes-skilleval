from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PASS = "PASS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
PHASE18_ARTIFACT_TYPE = "phase18-ci-release-reproducibility-pack"
PHASE17_ARTIFACT_TYPE = "phase17-calibrated-release-selector"


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(
    *,
    decision_path: Path | str,
    release_check_summary_path: Path | str,
    artifact_paths: list[Path | str],
    command_records: list[dict[str, Any]],
) -> dict[str, Any]:
    decision_file = Path(decision_path)
    release_summary_file = Path(release_check_summary_path)
    decision = _read_json(decision_file)
    release_summary = _read_json(release_summary_file)
    reasons = _manifest_reasons(decision, release_summary, artifact_paths)
    status = PASS if not reasons else REVIEW_REQUIRED

    return {
        "phase": "Phase 18",
        "artifact_type": PHASE18_ARTIFACT_TYPE,
        "status": status,
        "source_phase": decision.get("phase"),
        "release_decision": {
            "decision": decision.get("decision"),
            "selected_router": decision.get("selected_router"),
            "baseline_router": decision.get("baseline_router"),
            "candidate_router": decision.get("candidate_router"),
            "approved_for_default": decision.get("approved_for_default"),
            "regression_count": decision.get("regression_count"),
            "task_count": decision.get("task_count"),
            "metric_deltas": decision.get("metric_deltas", {}),
        },
        "release_check": {
            "status": release_summary.get("status"),
            "match_count": release_summary.get("match_count"),
            "check_count": len(release_summary.get("checks", []))
            if isinstance(release_summary.get("checks"), list)
            else 0,
        },
        "commands": command_records,
        "artifacts": [_artifact_record(path) for path in artifact_paths],
        "reasons": reasons
        or ["release decision, public release check, and artifact hashes are reproducible"],
    }


def write_release_manifest(
    *,
    decision_path: Path | str,
    release_check_summary_path: Path | str,
    artifact_paths: list[Path | str],
    command_records: list[dict[str, Any]],
    output_dir: Path | str,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_check_summary_path,
        artifact_paths=artifact_paths,
        command_records=command_records,
    )
    (output / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "release-manifest.md").write_text(
        _render_manifest_markdown(manifest),
        encoding="utf-8",
    )
    return manifest


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing_path": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"_malformed": f"{path} must contain a JSON object"}
    return data


def _manifest_reasons(
    decision: dict[str, Any],
    release_summary: dict[str, Any],
    artifact_paths: list[Path | str],
) -> list[str]:
    reasons: list[str] = []
    if decision.get("_missing_path"):
        reasons.append(f"missing release decision: {decision['_missing_path']}")
    if release_summary.get("_missing_path"):
        reasons.append(f"missing release check summary: {release_summary['_missing_path']}")
    if decision.get("artifact_type") != PHASE17_ARTIFACT_TYPE:
        reasons.append("decision artifact_type is not phase17-calibrated-release-selector")
    if decision.get("decision") not in {
        "APPROVE_CANDIDATE",
        "KEEP_BASELINE",
        "REVIEW_REQUIRED",
    }:
        reasons.append("decision must be APPROVE_CANDIDATE, KEEP_BASELINE, or REVIEW_REQUIRED")
    if decision.get("decision") != "KEEP_BASELINE":
        reasons.append("decision must remain KEEP_BASELINE for Phase 18")
    if not isinstance(decision.get("selected_router"), str) or not decision.get(
        "selected_router"
    ):
        reasons.append("selected_router must be a non-empty string")
    if decision.get("selected_router") != "baseline-minilm":
        reasons.append("selected_router must remain baseline-minilm for Phase 18")
    if decision.get("candidate_router") != "finetuned-embedding":
        reasons.append("candidate_router must remain finetuned-embedding for Phase 18")
    if decision.get("approved_for_default") is not False:
        reasons.append("approved_for_default must remain false for Phase 18")
    if release_summary.get("status") != PASS:
        reasons.append("release check status is not PASS")
    for path in artifact_paths:
        if not Path(path).is_file():
            reasons.append(f"missing artifact: {path}")
    return reasons


def _artifact_record(path: Path | str) -> dict[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        return {
            "path": str(artifact),
            "exists": False,
            "size_bytes": 0,
            "sha256": None,
        }
    return {
        "path": str(artifact),
        "exists": True,
        "size_bytes": artifact.stat().st_size,
        "sha256": sha256_file(artifact),
    }


def _render_manifest_markdown(manifest: dict[str, Any]) -> str:
    release_decision = manifest["release_decision"]
    release_check = manifest["release_check"]
    artifact_rows = "\n".join(
        "| `{path}` | {size_bytes} | `{sha256}` |".format(**artifact)
        for artifact in manifest["artifacts"]
        if artifact["exists"]
    )
    if not artifact_rows:
        artifact_rows = "| None | 0 | None |"

    return "\n".join(
        [
            "# Phase 18 Release Reproducibility Manifest",
            "",
            f"- Status: `{manifest['status']}`",
            f"- Release decision: `{release_decision['decision']}`",
            f"- Selected router: `{release_decision['selected_router']}`",
            f"- Candidate router: `{release_decision['candidate_router']}`",
            f"- Approved for default: `{release_decision['approved_for_default']}`",
            f"- Release check status: `{release_check['status']}`",
            "",
            "## Reproducible Artifacts",
            "",
            "| Path | Size Bytes | SHA-256 |",
            "|---|---:|---|",
            artifact_rows,
            "",
            "## Reasons",
            "",
            *[f"- {reason}" for reason in manifest["reasons"]],
            "",
        ]
    )
