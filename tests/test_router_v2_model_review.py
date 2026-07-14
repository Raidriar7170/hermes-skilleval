from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).parents[1]
TRUTH = {
    "review_mode": "MODEL_ONLY_PILOT",
    "human_reviewer_count": 0,
    "model_review_pass_count": 2,
    "model_adjudication_enabled": True,
    "independent_human_review": False,
    "model_correlation_risk": True,
    "release_eligible": False,
    "router_decision": "KEEP_BASELINE",
    "human_review_status": "REVIEW_REQUIRED",
    "admission_effect": "NONE",
    "can_start_preflight": False,
    "can_start_training": False,
}


def _module():
    try:
        return importlib.import_module("hermes_skilleval.router_v2_model_review")
    except ModuleNotFoundError:
        pytest.fail("router_v2_model_review validator module is missing")


def _canonical(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _with_row_hash(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["row_sha256"] = _sha256(_canonical(result))
    return result


def _opinion_for(role: str, *, disputed: bool = False) -> str:
    stem = {
        "POSITIVE": "POSITIVE",
        "HARD_NEGATIVE_CANDIDATE": "HARD_NEGATIVE",
        "NO_SKILL_CANDIDATE": "NO_SKILL",
    }[role]
    return f"{stem}_ROLE_{'DISPUTED' if disputed else 'SUPPORTED'}"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_bytes(b"".join(_canonical(row) for row in rows))


def _rewrite_jsonl_row(path: Path, index: int, update: dict[str, Any]) -> None:
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[index].update(update)
    rows[index].pop("row_sha256", None)
    rows[index] = _with_row_hash(rows[index])
    _write_jsonl(path, rows)


def _rewrite_json_document(path: Path, update: dict[str, Any]) -> None:
    document = json.loads(path.read_text())
    document.update(update)
    path.write_bytes(_canonical(document))


def _make_complete_pilot(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    source_dir = repository / "data/router-v2-v4"
    source_dir.mkdir(parents=True)
    for name in ("source-candidates.jsonl", "source-manifest.json"):
        shutil.copyfile(ROOT / "data/router-v2-v4" / name, source_dir / name)

    rubric_path = repository / "docs/router-v2-model-only-review-rubric-v1.md"
    rubric_path.parent.mkdir()
    rubric_path.write_text("# Stable test rubric\n", encoding="utf-8")

    pilot_dir = (
        repository
        / "artifacts/router-v2-v4/model-only-pilot/router-v2-v4-codex-pilot-001"
    )
    pilot_dir.mkdir(parents=True)
    manifest = json.loads((source_dir / "source-manifest.json").read_text())
    source_records = manifest["records"]
    rubric_sha256 = _sha256(rubric_path.read_bytes())

    pass_rows: dict[str, list[dict[str, Any]]] = {}
    for pass_id, run_id in (
        ("MODEL_PASS_1", "codex-model-pass-1-run-001"),
        ("MODEL_PASS_2", "codex-model-pass-2-run-001"),
    ):
        rows = []
        for record in source_records:
            row = {
                **TRUTH,
                "schema_version": "router-v2-model-opinion-row-v1",
                "pilot_id": "router-v2-v4-codex-pilot-001",
                "pass_id": pass_id,
                "pass_run_id": run_id,
                "pass_isolation": "OTHER_PASS_OUTPUT_NOT_PROVIDED",
                "source_record_id": record["source_record_id"],
                "source_record_exact_bytes_sha256": record[
                    "source_record_exact_bytes_sha256"
                ],
                "source_role": record["source_role"],
                "model_opinion": _opinion_for(record["source_role"]),
                "rationale": "Role matches the frozen query and skill context.",
                "model_provider": "OpenAI",
                "model_id": "UNAVAILABLE",
                "model_snapshot": "UNAVAILABLE",
                "prompt_id": "router-v2-model-only-rubric-v1",
                "prompt_sha256": "UNAVAILABLE",
                "rubric_sha256": rubric_sha256,
            }
            rows.append(_with_row_hash(row))
        pass_rows[pass_id] = rows

    pass_1_path = pilot_dir / "pass-1.model-opinions.jsonl"
    pass_2_path = pilot_dir / "pass-2.model-opinions.jsonl"
    _write_jsonl(pass_1_path, pass_rows["MODEL_PASS_1"])
    _write_jsonl(pass_2_path, pass_rows["MODEL_PASS_2"])

    adjudication_rows = []
    for record, pass_1, pass_2 in zip(
        source_records,
        pass_rows["MODEL_PASS_1"],
        pass_rows["MODEL_PASS_2"],
        strict=True,
    ):
        row = {
            **TRUTH,
            "schema_version": "router-v2-model-adjudication-row-v1",
            "pilot_id": "router-v2-v4-codex-pilot-001",
            "source_record_id": record["source_record_id"],
            "source_record_exact_bytes_sha256": record[
                "source_record_exact_bytes_sha256"
            ],
            "source_role": record["source_role"],
            "pass_1_row_sha256": pass_1["row_sha256"],
            "pass_2_row_sha256": pass_2["row_sha256"],
            "pass_1_model_opinion": pass_1["model_opinion"],
            "pass_2_model_opinion": pass_2["model_opinion"],
            "opinions_agree": True,
            "adjudicated_model_opinion": pass_1["model_opinion"],
            "rationale": "Both isolated model passes support the frozen role.",
            "adjudicator_model_provider": "OpenAI",
            "adjudicator_model_id": "UNAVAILABLE",
            "adjudicator_model_snapshot": "UNAVAILABLE",
            "adjudication_prompt_id": "router-v2-model-only-adjudication-v1",
            "adjudication_prompt_sha256": "UNAVAILABLE",
            "rubric_sha256": rubric_sha256,
        }
        adjudication_rows.append(_with_row_hash(row))
    adjudication_path = pilot_dir / "adjudication.model-opinions.jsonl"
    _write_jsonl(adjudication_path, adjudication_rows)

    pilot_manifest = {
        **TRUTH,
        "schema_version": "router-v2-model-review-pilot-manifest-v1",
        "pilot_id": "router-v2-v4-codex-pilot-001",
        "source_snapshot_id": "router-v2-v4-source-38afe7d5b2500d4a",
        "source_commit": "751bb678bf9fb63a357ff3667e3508a0f5ed83a2",
        "source_candidates_sha256": _sha256(
            (source_dir / "source-candidates.jsonl").read_bytes()
        ),
        "source_manifest_sha256": _sha256(
            (source_dir / "source-manifest.json").read_bytes()
        ),
        "source_row_count": 192,
        "rubric_path": "docs/router-v2-model-only-review-rubric-v1.md",
        "rubric_sha256": rubric_sha256,
        "pass_1": {
            "path": "pass-1.model-opinions.jsonl",
            "sha256": _sha256(pass_1_path.read_bytes()),
            "row_count": 192,
            "pass_id": "MODEL_PASS_1",
            "pass_run_id": "codex-model-pass-1-run-001",
        },
        "pass_2": {
            "path": "pass-2.model-opinions.jsonl",
            "sha256": _sha256(pass_2_path.read_bytes()),
            "row_count": 192,
            "pass_id": "MODEL_PASS_2",
            "pass_run_id": "codex-model-pass-2-run-001",
        },
        "adjudication": {
            "path": "adjudication.model-opinions.jsonl",
            "sha256": _sha256(adjudication_path.read_bytes()),
            "row_count": 192,
        },
        "non_actions": [
            "accepted_pairs",
            "blind_v2",
            "human_review",
            "model_training",
            "preflight",
            "qualification",
            "release",
            "review_decisions",
            "router_promotion",
            "training_input",
        ],
    }
    (pilot_dir / "pilot-manifest.json").write_bytes(_canonical(pilot_manifest))

    summary = {
        **TRUTH,
        "schema_version": "router-v2-model-review-pilot-summary-v1",
        "pilot_id": "router-v2-v4-codex-pilot-001",
        "source_row_count": 192,
        "pass_1_row_count": 192,
        "pass_2_row_count": 192,
        "adjudication_row_count": 192,
        "agreement_count": 192,
        "disagreement_count": 0,
        "model_uncertain_count": 0,
        "result": "MODEL_AUDIT_RECORDED_NO_ADMISSION_EFFECT",
    }
    (pilot_dir / "summary.json").write_bytes(_canonical(summary))
    return repository, pilot_dir


def test_complete_model_only_pilot_validates(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)

    result = _module().validate_router_v2_model_review_pilot(
        repository_root=repository,
        pilot_dir=pilot_dir,
    )

    assert result == {
        **TRUTH,
        "pilot_id": "router-v2-v4-codex-pilot-001",
        "source_row_count": 192,
        "agreement_count": 192,
        "disagreement_count": 0,
        "model_uncertain_count": 0,
        "validation_status": "PASS",
    }


@pytest.mark.parametrize(
    ("relative_path", "index", "update", "message"),
    [
        (
            "pass-1.model-opinions.jsonl",
            0,
            {"review_mode": "HUMAN_REVIEW"},
            "truth field review_mode",
        ),
        (
            "pass-1.model-opinions.jsonl",
            0,
            {"source_record_exact_bytes_sha256": "0" * 64},
            "source row identity",
        ),
        (
            "pass-1.model-opinions.jsonl",
            0,
            {"model_opinion": "HARD_NEGATIVE_ROLE_SUPPORTED"},
            "not valid for source role POSITIVE",
        ),
        (
            "pass-1.model-opinions.jsonl",
            0,
            {"reviewer": "project-owner"},
            "forbidden field reviewer",
        ),
    ],
)
def test_rejects_truth_source_role_and_human_semantic_drift(
    tmp_path: Path,
    relative_path: str,
    index: int,
    update: dict[str, Any],
    message: str,
):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    _rewrite_jsonl_row(pilot_dir / relative_path, index, update)

    with pytest.raises(ValueError, match=message):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


def test_rejects_noncanonical_jsonl_even_when_json_is_equivalent(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    path = pilot_dir / "pass-1.model-opinions.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    with pytest.raises(ValueError, match="canonical JSONL"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


def test_rejects_reused_pass_run_identity(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    path = pilot_dir / "pilot-manifest.json"
    manifest = json.loads(path.read_text())
    manifest["pass_2"]["pass_run_id"] = manifest["pass_1"]["pass_run_id"]
    path.write_bytes(_canonical(manifest))

    with pytest.raises(ValueError, match="distinct pass run identities"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


def test_rejects_adjudication_hash_or_agreement_drift(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    _rewrite_jsonl_row(
        pilot_dir / "adjudication.model-opinions.jsonl",
        0,
        {"pass_1_row_sha256": "0" * 64, "opinions_agree": False},
    )

    with pytest.raises(ValueError, match="adjudication pass-1 row hash"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


def test_rejects_review_decisions_and_noncanonical_pilot_path(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    (repository / "data/router-v2-v4/review-decisions.csv").write_text("forbidden\n")

    with pytest.raises(ValueError, match="review-decisions.csv is forbidden"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )

    (repository / "data/router-v2-v4/review-decisions.csv").unlink()
    outside = repository / "artifacts/copied-pilot"
    shutil.copytree(pilot_dir, outside)
    with pytest.raises(ValueError, match="model-only pilot path"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=outside,
        )


def test_rejects_missing_or_inferred_provenance(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    _rewrite_jsonl_row(
        pilot_dir / "pass-2.model-opinions.jsonl", 0, {"model_snapshot": ""}
    )

    with pytest.raises(ValueError, match="model_snapshot must be explicit"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


def test_validation_cli_emits_canonical_fail_closed_summary(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_router_v2_model_review.py"),
            "--repository-root",
            str(repository),
            "--pilot-dir",
            str(pilot_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        **TRUTH,
        "pilot_id": "router-v2-v4-codex-pilot-001",
        "source_row_count": 192,
        "agreement_count": 192,
        "disagreement_count": 0,
        "model_uncertain_count": 0,
        "validation_status": "PASS",
    }


@pytest.mark.parametrize(
    "claim",
    [
        "production release",
        "生产发布",
        "router promotion",
        "release claim",
        "blind-v2 final conclusion",
        "blind-v2 最终结论",
        "human-annotated data",
        "人工标注数据",
        "resume human-review claim",
        "résumé human-review claim",
        "简历中的人工审核 claim",
        "project-owner reviewer",
        "reviewer 是项目所有者本人",
        "blind-v2 conclusion",
        "human annotation promotion",
    ],
)
def test_rejects_explicit_prohibited_claim_surfaces_in_pass_rows(
    tmp_path: Path, claim: str
):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    _rewrite_jsonl_row(
        pilot_dir / "pass-1.model-opinions.jsonl", 0, {"rationale": claim}
    )

    with pytest.raises(ValueError, match="forbidden human or release claim"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


def test_rejects_prohibited_claims_in_adjudication_and_summary(tmp_path: Path):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    _rewrite_jsonl_row(
        pilot_dir / "adjudication.model-opinions.jsonl",
        0,
        {"rationale": "blind-v2 final conclusion"},
    )
    with pytest.raises(ValueError, match="forbidden human or release claim"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )

    repository, pilot_dir = _make_complete_pilot(tmp_path / "summary-case")
    _rewrite_json_document(
        pilot_dir / "summary.json", {"result": "生产发布 release claim"}
    )
    with pytest.raises(ValueError, match="forbidden human or release claim"):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )


@pytest.mark.parametrize(
    ("file_name", "field", "value", "message"),
    [
        (
            "pass-1.model-opinions.jsonl",
            "prompt_sha256",
            "not-a-hash",
            "prompt_sha256 must be UNAVAILABLE or lowercase 64-hex",
        ),
        (
            "pass-2.model-opinions.jsonl",
            "prompt_sha256",
            "A" * 64,
            "prompt_sha256 must be UNAVAILABLE or lowercase 64-hex",
        ),
        (
            "adjudication.model-opinions.jsonl",
            "adjudication_prompt_sha256",
            "not-a-hash",
            "adjudication_prompt_sha256 must be UNAVAILABLE or lowercase 64-hex",
        ),
        (
            "pass-1.model-opinions.jsonl",
            "model_id",
            "   ",
            "model_id must be explicit or UNAVAILABLE",
        ),
        (
            "adjudication.model-opinions.jsonl",
            "adjudicator_model_id",
            "\t",
            "adjudicator_model_id must be explicit or UNAVAILABLE",
        ),
    ],
)
def test_rejects_invalid_prompt_hashes_and_whitespace_provenance(
    tmp_path: Path,
    file_name: str,
    field: str,
    value: str,
    message: str,
):
    repository, pilot_dir = _make_complete_pilot(tmp_path)
    _rewrite_jsonl_row(pilot_dir / file_name, 0, {field: value})

    with pytest.raises(ValueError, match=message):
        _module().validate_router_v2_model_review_pilot(
            repository_root=repository,
            pilot_dir=pilot_dir,
        )
