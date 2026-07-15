from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from hermes_skilleval.router_v2_pilot_candidates import validate_candidate_bundle
from hermes_skilleval.router_v2_training_pilot import (
    TRUTH_FIELDS,
    canonical_sha256,
    validate_new_candidate_review,
    with_row_sha256,
)


REVIEW_FREEZE_GIT_COMMIT = "ca314241ac8ab3b9f6bb148b1e78189813252ee8"
BASE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001"
)
CANONICAL_OUTPUT_PATH = BASE / "package/router-v2-v4-internal-training-package-001"
FIXED_INPUT_PATHS: dict[str, Path] = {
    "source_manifest": Path("data/router-v2-v4/source-manifest.json"),
    "source_candidates": Path("data/router-v2-v4/source-candidates.jsonl"),
    "skill_index": Path("docs/demo/phase9-real-skill-library-migration/skills.json"),
    "mining_rows": BASE / "mining/mining.jsonl",
    "mining_manifest": BASE / "mining/mining-manifest.json",
    "prior_filter": BASE / "mining/prior-review-filter.json",
    "candidates": BASE / "candidates/round-1/candidates.jsonl",
    "candidate_manifest": BASE / "candidates/round-1/candidate-manifest.json",
    "review_rubric": BASE / "review/review-rubric.json",
    "pass_1_opinions": BASE / "review/round-1/pass-1.model-opinions.jsonl",
    "pass_2_opinions": BASE / "review/round-1/pass-2.model-opinions.jsonl",
    "adjudication_decisions": BASE / "review/round-1/adjudication.decisions.jsonl",
    "adjudication_opinions": BASE / "review/round-1/adjudication.model-opinions.jsonl",
}
FIXED_INPUT_SHA256: dict[str, str] = {
    "source_manifest": "330f13d58833450293374f91e253dadf452b5a7d5233a4aa025984e09b0ed511",
    "source_candidates": "5fa7e7feb1a5fedc2cf8bcc8adf17afe3356f9d4614b2848b0d74f88718e3d2a",
    "skill_index": "c67a786a6dcdc6f71716894f22f8ba409c38ec0954a07143b09a0372159ccaf5",
    "mining_rows": "29d20c95f1e280de2a24875ea3cfbf4fd5fbae8fb513d749c13da3ab2df21f88",
    "mining_manifest": "1eba5a66f5065ae6792f43c2c8b186db2628d33a2a7c2a0d9f0e0787935e6a2d",
    "prior_filter": "d8bffc89872f5795e7a366e3ff1f01de6a1a04e120e09c2ef01bb223b81025cc",
    "candidates": "1f0f9d62061dc6563accd3aa2270ea58e011df4388aab6e0ad8bfa8b5982370b",
    "candidate_manifest": "519386b105f63a13d9029a3451fc6ac2dfbe4792dbaad8f94cc3fb6c9b8df131",
    "review_rubric": "63e629c820394b66be9eea6509e39986d73e7ccac0ef101e760c5fbadae5ed07",
    "pass_1_opinions": "29c4b33b56b14a5a7f056976ca42d10f7ecbc5d3a4ca38eed36e54ec21373348",
    "pass_2_opinions": "9495058925600dc3a6e3a34ead0a2167ae009c443effe4bd3369921c9a0173ce",
    "adjudication_decisions": "9ad438cefb2c550da1f467a6839bcf9cdb87b9a43987f1055001fc38b3997392",
    "adjudication_opinions": "4ca083648fafa97f0dc66dbd3823bfe95e4a07266fb2e724e9c8da8a1910e400",
}

ACCEPTED_ROW_FIELDS = {
    "schema_version",
    "example_id",
    "query_text",
    "query_sha256",
    "positive_source_record_id",
    "positive_source_record_exact_bytes_sha256",
    "gold_skill_id",
    "skill_id",
    "skill_text",
    "skill_text_sha256",
    "skill_record_sha256",
    "label",
    "role",
    "evidence_source",
    "hard_negative_id",
    "hard_negative_sha256",
    "candidate_rank",
    "score_margin",
    "mining_row_sha256",
    "review_binding_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "skill_index_sha256",
    "model_id",
    "model_revision",
    "model_file_manifest_sha256",
    "row_sha256",
}
HELDOUT_ROW_FIELDS = {
    "schema_version",
    "candidate_id",
    "candidate_sha256",
    "task_id",
    "query_text",
    "query_sha256",
    "positive_source_record_id",
    "positive_source_record_exact_bytes_sha256",
    "gold_skill_id",
    "gold_skill_record_sha256",
    "candidate_skill_id",
    "candidate_skill_text",
    "candidate_skill_text_sha256",
    "candidate_skill_record_sha256",
    "usage",
    "training_eligible",
    "mining_eligible",
    "adjudication_row_sha256",
    "pass_1_row_sha256",
    "pass_2_row_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "skill_index_sha256",
    "row_sha256",
}
PACKAGE_TRUTH_FIELDS: dict[str, object] = {
    **TRUTH_FIELDS,
    "can_start_internal_training": True,
    "can_start_production_training": False,
    "blind_v2_eligible": False,
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_line(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _load_json(payload: bytes, *, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid UTF-8 JSON") from exc


def _load_jsonl(
    payload: bytes, *, label: str
) -> tuple[list[dict[str, Any]], list[bytes]]:
    if not payload or not payload.endswith(b"\n"):
        raise ValueError(f"{label} must use one LF per row")
    rows: list[dict[str, Any]] = []
    lines = payload.splitlines(keepends=True)
    for index, line in enumerate(lines, start=1):
        try:
            row = json.loads(line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} line {index} is invalid") from exc
        if not isinstance(row, dict) or line != _canonical_line(row):
            raise ValueError(f"{label} line {index} is not canonical JSONL")
        rows.append(row)
    return rows, lines


def _git_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_status_porcelain(root: Path) -> str:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _clean_code_commit(root: Path) -> str:
    code_git_commit = _git_head(root)
    if re.fullmatch(r"[0-9a-f]{40}", code_git_commit) is None:
        raise ValueError("repository HEAD must be a lowercase 40-hex commit")
    if _git_status_porcelain(root) != "":
        raise ValueError("repository must be completely clean before package build")
    return code_git_commit


def _resolve_inputs(root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for label, relative in FIXED_INPUT_PATHS.items():
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"fixed {label} path must be repository-relative")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"fixed {label} path must stay inside repository root")
        paths[label] = path
    return paths


def _load_inputs(repository_root: Path | str) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root must be a directory")
    paths = _resolve_inputs(root)
    payloads = {label: path.read_bytes() for label, path in paths.items()}

    # Every frozen byte binding and the code base are checked before any parse.
    for label, expected in FIXED_INPUT_SHA256.items():
        if _sha256(payloads[label]) != expected:
            display = label.replace("_", " ")
            raise ValueError(f"{display} SHA-256 mismatch")
    source_manifest = _load_json(payloads["source_manifest"], label="source manifest")
    source_rows, source_lines = _load_jsonl(
        payloads["source_candidates"], label="source candidates"
    )
    skills = _load_json(payloads["skill_index"], label="skill index")
    mining_rows, _ = _load_jsonl(payloads["mining_rows"], label="mining rows")
    mining_manifest = _load_json(payloads["mining_manifest"], label="mining manifest")
    prior_filter = _load_json(payloads["prior_filter"], label="prior filter")
    candidates, _ = _load_jsonl(payloads["candidates"], label="candidates")
    candidate_manifest = _load_json(
        payloads["candidate_manifest"], label="candidate manifest"
    )
    pass_1, _ = _load_jsonl(payloads["pass_1_opinions"], label="pass 1 opinions")
    pass_2, _ = _load_jsonl(payloads["pass_2_opinions"], label="pass 2 opinions")
    decisions, _ = _load_jsonl(
        payloads["adjudication_decisions"], label="adjudication decisions"
    )
    adjudications, _ = _load_jsonl(
        payloads["adjudication_opinions"], label="adjudication opinions"
    )

    if not isinstance(source_manifest, dict) or not isinstance(
        source_manifest.get("records"), list
    ):
        raise ValueError("source manifest records are invalid")
    records = source_manifest["records"]
    if len(records) != len(source_rows) or len(source_rows) != 192:
        raise ValueError("source manifest and candidates must contain 192 rows")
    restored_rows: list[dict[str, Any]] = []
    for index, (record, row, line) in enumerate(
        zip(records, source_rows, source_lines, strict=True), start=1
    ):
        if not isinstance(record, dict):
            raise ValueError(f"source manifest record {index} is invalid")
        exact_sha = _sha256(line)
        for field in (
            "source_record_id",
            "source_role",
            "split",
            "positive_skill_id",
            "skill_id",
            "prompt_text_sha256",
        ):
            if record.get(field) != row.get(field):
                raise ValueError(f"source record {index} {field} mismatch")
        if record.get("source_record_exact_bytes_sha256") != exact_sha:
            raise ValueError(f"source record {index} exact bytes mismatch")
        query = row.get("query_text")
        if not isinstance(query, str) or _sha256(query.encode()) != row.get(
            "prompt_text_sha256"
        ):
            raise ValueError(f"source record {index} query hash mismatch")
        restored_rows.append({**row, "source_record_exact_bytes_sha256": exact_sha})

    if not isinstance(skills, list) or len(skills) != 16:
        raise ValueError("skill index must contain exactly 16 rows")
    if not all(
        isinstance(skill, dict) and isinstance(skill.get("id"), str) for skill in skills
    ):
        raise ValueError("skill index rows are invalid")
    if len({skill["id"] for skill in skills}) != 16:
        raise ValueError("skill index contains duplicate ids")

    if not isinstance(candidate_manifest, dict):
        raise ValueError("candidate manifest must be an object")
    validate_candidate_bundle(candidates, candidate_manifest, repository_root=root)
    validate_new_candidate_review(pass_1, pass_2, adjudications)
    if len(decisions) != len(adjudications):
        raise ValueError("adjudication decisions do not cover all opinions")
    for decision, opinion in zip(decisions, adjudications, strict=True):
        expected_decision = {
            "candidate_id": opinion["candidate_id"],
            "adjudicated_model_opinion": opinion["adjudicated_model_opinion"],
            "rationale": opinion["rationale"],
        }
        if decision != expected_decision:
            raise ValueError("adjudication decision and opinion mismatch")

    if not isinstance(mining_manifest, dict) or not isinstance(prior_filter, dict):
        raise ValueError("mining lineage inputs must be objects")
    return {
        "root": root,
        "source_manifest": source_manifest,
        "source_rows": restored_rows,
        "skills": skills,
        "mining_rows": mining_rows,
        "mining_manifest": mining_manifest,
        "prior_filter": prior_filter,
        "candidates": candidates,
        "candidate_manifest": candidate_manifest,
        "pass_1": pass_1,
        "pass_2": pass_2,
        "adjudications": adjudications,
    }


def _skill_text(skill: dict[str, Any]) -> str:
    return " ".join(
        [
            skill["id"].replace("-", " "),
            skill["name"],
            skill["category"],
            skill["description"],
            " ".join(skill["trigger_terms"]),
            skill["body"],
        ]
    )


def _common_lineage(inputs: dict[str, Any]) -> dict[str, Any]:
    manifest = inputs["mining_manifest"]
    return {
        "source_snapshot_id": manifest["source_snapshot_id"],
        "source_candidates_sha256": manifest["source_candidates_sha256"],
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "skill_index_sha256": manifest["skill_index_sha256"],
        "model_id": manifest["model_id"],
        "model_revision": manifest["model_revision"],
        "model_file_manifest_sha256": manifest["model_file_manifest_sha256"],
    }


def _accepted_row(
    *,
    positive: dict[str, Any],
    skill: dict[str, Any],
    label: int,
    role: str,
    evidence_source: str,
    hard_negative_id: str | None,
    hard_negative_sha256: str | None,
    candidate_rank: int | None,
    score_margin: str | None,
    mining_row_sha256: str | None,
    review_binding_sha256: str | None,
    lineage: dict[str, Any],
) -> dict[str, Any]:
    text = _skill_text(skill)
    return with_row_sha256(
        {
            "schema_version": "router-v2-internal-accepted-pair-v1",
            "example_id": positive["task_id"],
            "query_text": positive["query_text"],
            "query_sha256": positive["prompt_text_sha256"],
            "positive_source_record_id": positive["source_record_id"],
            "positive_source_record_exact_bytes_sha256": positive[
                "source_record_exact_bytes_sha256"
            ],
            "gold_skill_id": positive["positive_skill_id"],
            "skill_id": skill["id"],
            "skill_text": text,
            "skill_text_sha256": canonical_sha256(text),
            "skill_record_sha256": canonical_sha256(skill),
            "label": label,
            "role": role,
            "evidence_source": evidence_source,
            "hard_negative_id": hard_negative_id,
            "hard_negative_sha256": hard_negative_sha256,
            "candidate_rank": candidate_rank,
            "score_margin": score_margin,
            "mining_row_sha256": mining_row_sha256,
            "review_binding_sha256": review_binding_sha256,
            **lineage,
        }
    )


def _build_rows(
    inputs: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    skills = {skill["id"]: skill for skill in inputs["skills"]}
    positives = sorted(
        (
            row
            for row in inputs["source_rows"]
            if row["split"] == "train" and row["source_role"] == "POSITIVE"
        ),
        key=lambda row: row["task_id"],
    )
    if len(positives) != 64:
        raise ValueError("frozen source must contain exactly 64 train positives")
    positive_by_task = {row["task_id"]: row for row in positives}
    mining_by_task = {row["task_id"]: row for row in inputs["mining_rows"]}
    candidate_by_id = {row["candidate_id"]: row for row in inputs["candidates"]}
    adjudication_by_id = {row["candidate_id"]: row for row in inputs["adjudications"]}
    lineage = _common_lineage(inputs)

    accepted = [
        _accepted_row(
            positive=positive,
            skill=skills[positive["positive_skill_id"]],
            label=1,
            role="POSITIVE",
            evidence_source="FROZEN_TRAIN_POSITIVE",
            hard_negative_id=None,
            hard_negative_sha256=None,
            candidate_rank=None,
            score_margin=None,
            mining_row_sha256=None,
            review_binding_sha256=None,
            lineage=lineage,
        )
        for positive in positives
    ]

    retained_ids = inputs["prior_filter"].get("retained_source_record_ids")
    if not isinstance(retained_ids, list) or len(retained_ids) != 21:
        raise ValueError("prior retained hard negatives must contain exactly 21 rows")
    source_by_id = {row["source_record_id"]: row for row in inputs["source_rows"]}
    old_rows: list[dict[str, Any]] = []
    for source_id in retained_ids:
        negative = source_by_id[source_id]
        positive = positive_by_task[negative["task_id"]]
        mining = mining_by_task[negative["task_id"]]
        if (
            negative["split"] != "train"
            or negative["source_role"] != "HARD_NEGATIVE_CANDIDATE"
            or mining["baseline_hard"] is not True
        ):
            raise ValueError("prior retained row is not a train baseline-hard negative")
        score_by_skill = {row["skill_id"]: row["score"] for row in mining["scores"]}
        rank_by_skill = {
            row["skill_id"]: index for index, row in enumerate(mining["scores"], 1)
        }
        margin = Decimal(score_by_skill[positive["positive_skill_id"]]) - Decimal(
            score_by_skill[negative["skill_id"]]
        )
        old_rows.append(
            _accepted_row(
                positive=positive,
                skill=skills[negative["skill_id"]],
                label=0,
                role="HARD_NEGATIVE",
                evidence_source="PRIOR_RETAINED_SUPPORTED_BASELINE_HARD",
                hard_negative_id=source_id,
                hard_negative_sha256=negative["source_record_exact_bytes_sha256"],
                candidate_rank=rank_by_skill[negative["skill_id"]],
                score_margin=f"{margin:.8f}",
                mining_row_sha256=mining["row_sha256"],
                review_binding_sha256=inputs["prior_filter"]["report_sha256"],
                lineage=lineage,
            )
        )

    supported_train_ids = [
        row["candidate_id"]
        for row in inputs["adjudications"]
        if row["usage"] == "TRAIN_HARD_NEGATIVE_CANDIDATE"
        and row["adjudicated_model_opinion"] == "HARD_NEGATIVE_ROLE_SUPPORTED"
    ]
    if len(supported_train_ids) != 31:
        raise ValueError("round-1 supported train hard negatives must contain 31 rows")
    new_rows: list[dict[str, Any]] = []
    for candidate_id in supported_train_ids:
        candidate = candidate_by_id[candidate_id]
        positive = positive_by_task[candidate["task_id"]]
        review = adjudication_by_id[candidate_id]
        new_rows.append(
            _accepted_row(
                positive=positive,
                skill=skills[candidate["candidate_skill_id"]],
                label=0,
                role="HARD_NEGATIVE",
                evidence_source="ROUND_1_ADJUDICATED_SUPPORTED",
                hard_negative_id=candidate_id,
                hard_negative_sha256=candidate["candidate_sha256"],
                candidate_rank=candidate["candidate_rank"],
                score_margin=candidate["score_margin"],
                mining_row_sha256=candidate["mining_row_sha256"],
                review_binding_sha256=review["row_sha256"],
                lineage=lineage,
            )
        )
    hard_negatives = sorted([*old_rows, *new_rows], key=lambda row: row["example_id"])
    if (
        len(hard_negatives) != 52
        or len({row["example_id"] for row in hard_negatives}) != 52
    ):
        raise ValueError("hard-negative union must contain 52 unique tasks")

    heldout_ids = [
        row["candidate_id"]
        for row in inputs["adjudications"]
        if row["usage"] == "HELD_OUT_EVAL_ONLY"
        and row["adjudicated_model_opinion"] == "HARD_NEGATIVE_ROLE_SUPPORTED"
    ]
    if len(heldout_ids) != 9:
        raise ValueError("supported heldout labels must contain exactly 9 rows")
    heldout: list[dict[str, Any]] = []
    for candidate_id in heldout_ids:
        candidate = candidate_by_id[candidate_id]
        review = adjudication_by_id[candidate_id]
        skill = skills[candidate["candidate_skill_id"]]
        text = _skill_text(skill)
        heldout.append(
            with_row_sha256(
                {
                    "schema_version": "router-v2-internal-heldout-label-v1",
                    "candidate_id": candidate_id,
                    "candidate_sha256": candidate["candidate_sha256"],
                    "task_id": candidate["task_id"],
                    "query_text": candidate["query_text"],
                    "query_sha256": candidate["prompt_sha256"],
                    "positive_source_record_id": candidate["positive_source_record_id"],
                    "positive_source_record_exact_bytes_sha256": candidate[
                        "positive_source_record_exact_bytes_sha256"
                    ],
                    "gold_skill_id": candidate["gold_skill_id"],
                    "gold_skill_record_sha256": candidate["gold_skill_record_sha256"],
                    "candidate_skill_id": candidate["candidate_skill_id"],
                    "candidate_skill_text": text,
                    "candidate_skill_text_sha256": canonical_sha256(text),
                    "candidate_skill_record_sha256": candidate[
                        "candidate_skill_record_sha256"
                    ],
                    "usage": "HELD_OUT_EVAL_ONLY",
                    "training_eligible": False,
                    "mining_eligible": False,
                    "adjudication_row_sha256": review["row_sha256"],
                    "pass_1_row_sha256": review["pass_1_row_sha256"],
                    "pass_2_row_sha256": review["pass_2_row_sha256"],
                    "source_snapshot_id": candidate["source_snapshot_id"],
                    "source_candidates_sha256": candidate["source_candidates_sha256"],
                    "source_manifest_sha256": candidate["source_manifest_sha256"],
                    "skill_index_sha256": candidate["skill_index_sha256"],
                }
            )
        )
    heldout.sort(key=lambda row: row["candidate_id"])
    valid_pool_gold_coverage = sorted(
        {row["gold_skill_id"] for row in [*old_rows, *new_rows]}
    )
    return [*accepted, *hard_negatives], heldout, valid_pool_gold_coverage


def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[key]) for row in rows).items()))


def _build_manifest(
    accepted: list[dict[str, Any]],
    heldout: list[dict[str, Any]],
    accepted_payload: bytes,
    heldout_payload: bytes,
    *,
    code_git_commit: str,
    valid_pool_gold_coverage: list[str],
) -> dict[str, Any]:
    positives = [row for row in accepted if row["role"] == "POSITIVE"]
    negatives = [row for row in accepted if row["role"] == "HARD_NEGATIVE"]
    coverage = sorted({row["gold_skill_id"] for row in negatives})
    prior = [
        row
        for row in negatives
        if row["evidence_source"] == "PRIOR_RETAINED_SUPPORTED_BASELINE_HARD"
    ]
    new = [
        row
        for row in negatives
        if row["evidence_source"] == "ROUND_1_ADJUDICATED_SUPPORTED"
    ]
    return {
        "schema_version": "router-v2-internal-data-manifest-v1",
        "review_freeze_git_commit": REVIEW_FREEZE_GIT_COMMIT,
        "code_git_commit": code_git_commit,
        "input_artifact_sha256": FIXED_INPUT_SHA256,
        "accepted_pairs_jsonl_sha256": _sha256(accepted_payload),
        "heldout_labels_jsonl_sha256": _sha256(heldout_payload),
        "accepted_rows_sha256": canonical_sha256(accepted),
        "heldout_rows_sha256": canonical_sha256(heldout),
        "counts": {
            "accepted_pair_count": len(accepted),
            "positive_count": len(positives),
            "hard_negative_count": len(negatives),
            "prior_retained_hard_negative_count": len(prior),
            "round_1_supported_hard_negative_count": len(new),
            "heldout_supported_count": len(heldout),
            "supplement_count": 0,
        },
        "positive_count_by_skill": _distribution(positives, "gold_skill_id"),
        "hard_negative_count_by_gold_skill": _distribution(negatives, "gold_skill_id"),
        "hard_negative_count_by_candidate_skill": _distribution(negatives, "skill_id"),
        "hard_negative_gold_skill_coverage": coverage,
        "hard_negative_gold_skill_coverage_count": len(coverage),
        "valid_hard_negative_gold_skill_coverage": valid_pool_gold_coverage,
        "valid_hard_negative_gold_skill_coverage_count": len(valid_pool_gold_coverage),
        "hard_negative_gold_skill_coverage_maximized": coverage
        == valid_pool_gold_coverage,
        "supplement_required": False,
        "supplement_reason": "52 adjudicated supported hard negatives satisfy the 48 minimum",
        "training_exclusions": [
            "calibration",
            "test",
            "non_blind_test",
            "no_skill",
            "disputed",
            "ambiguous",
            "unsupported",
            "easy_negative",
        ],
        "non_actions": [
            "blind_v2",
            "gpu",
            "production_training",
            "release",
            "training_execution",
        ],
        **PACKAGE_TRUTH_FIELDS,
    }


def _validate_row_shapes(
    accepted: list[dict[str, Any]], heldout: list[dict[str, Any]]
) -> None:
    if len(accepted) != 116 or len(heldout) != 9:
        raise ValueError("package must contain exactly 116 accepted and 9 heldout rows")
    positives = [row for row in accepted if row.get("role") == "POSITIVE"]
    negatives = [row for row in accepted if row.get("role") == "HARD_NEGATIVE"]
    if len(positives) != 64:
        raise ValueError("package must contain exactly 64 positives")
    if not 48 <= len(negatives) <= 64:
        raise ValueError("package must contain between 48 and 64 hard negatives")
    if accepted != [*positives, *negatives]:
        raise ValueError("accepted rows must place positives before hard negatives")
    if any(set(row) != ACCEPTED_ROW_FIELDS for row in accepted):
        raise ValueError("accepted row fields mismatch")
    if any(set(row) != HELDOUT_ROW_FIELDS for row in heldout):
        raise ValueError("heldout row fields mismatch")
    if any(with_row_sha256(row) != row for row in [*accepted, *heldout]):
        raise ValueError("package row SHA-256 mismatch")
    if any(row["label"] != (1 if row["role"] == "POSITIVE" else 0) for row in accepted):
        raise ValueError("accepted row role and label mismatch")
    if len({row["example_id"] for row in negatives}) != len(negatives):
        raise ValueError("hard-negative tasks must be unique")
    if any(
        row["usage"] != "HELD_OUT_EVAL_ONLY"
        or row["training_eligible"] is not False
        or row["mining_eligible"] is not False
        for row in heldout
    ):
        raise ValueError("heldout eligibility boundary mismatch")


def _load_output(path: Path, *, label: str) -> tuple[list[dict[str, Any]], bytes]:
    payload = path.read_bytes()
    rows, _ = _load_jsonl(payload, label=label)
    return rows, payload


def _validate_internal_package_at(
    repository_root: Path | str,
    output_dir: Path,
    *,
    code_git_commit: str,
) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", code_git_commit) is None:
        raise ValueError("code Git commit must be lowercase 40-hex")
    inputs = _load_inputs(repository_root)
    output = output_dir.resolve(strict=True)
    if not output.is_dir():
        raise ValueError("output directory must be a directory")
    accepted, accepted_payload = _load_output(
        output / "accepted-pairs.jsonl", label="accepted pairs"
    )
    heldout, heldout_payload = _load_output(
        output / "heldout-labels.jsonl", label="heldout labels"
    )
    manifest_payload = (output / "data-manifest.json").read_bytes()
    manifest = _load_json(manifest_payload, label="data manifest")
    if not isinstance(manifest, dict) or manifest_payload != _canonical_line(manifest):
        raise ValueError("data manifest must be canonical JSON with LF")
    if manifest.get("review_freeze_git_commit") != REVIEW_FREEZE_GIT_COMMIT:
        raise ValueError("review freeze Git commit mismatch")
    if manifest.get("code_git_commit") != code_git_commit:
        raise ValueError("code Git commit mismatch")
    for field, expected in PACKAGE_TRUTH_FIELDS.items():
        if manifest.get(field) != expected or type(manifest.get(field)) is not type(
            expected
        ):
            raise ValueError(f"truth field {field} mismatch")
    _validate_row_shapes(accepted, heldout)

    heldout_ids = {row["candidate_id"] for row in heldout}
    negatives = [row for row in accepted if row["role"] == "HARD_NEGATIVE"]
    if any(row["hard_negative_id"] in heldout_ids for row in negatives):
        raise ValueError("heldout candidate leaked into accepted pairs")
    candidates = {row["candidate_id"]: row for row in inputs["candidates"]}
    source_rows = {row["source_record_id"]: row for row in inputs["source_rows"]}
    mining_rows = {row["task_id"]: row for row in inputs["mining_rows"]}
    for row in negatives:
        if row["evidence_source"] == "ROUND_1_ADJUDICATED_SUPPORTED":
            evidence = candidates.get(row["hard_negative_id"])
            if evidence is None:
                raise ValueError("candidate review link mismatch")
            if (
                row["candidate_rank"] != evidence["candidate_rank"]
                or row["score_margin"] != evidence["score_margin"]
                or row["mining_row_sha256"] != evidence["mining_row_sha256"]
            ):
                raise ValueError("rank or margin evidence mismatch")
        else:
            source = source_rows.get(row["hard_negative_id"])
            mining = mining_rows[row["example_id"]]
            if source is None:
                raise ValueError("prior source review link mismatch")
            score_by_skill = {
                score["skill_id"]: score["score"] for score in mining["scores"]
            }
            rank_by_skill = {
                score["skill_id"]: index
                for index, score in enumerate(mining["scores"], 1)
            }
            margin = Decimal(score_by_skill[row["gold_skill_id"]]) - Decimal(
                score_by_skill[row["skill_id"]]
            )
            if (
                row["candidate_rank"] != rank_by_skill[row["skill_id"]]
                or row["score_margin"] != f"{margin:.8f}"
                or row["mining_row_sha256"] != mining["row_sha256"]
            ):
                raise ValueError("rank or margin evidence mismatch")

    expected_accepted, expected_heldout, valid_pool_gold_coverage = _build_rows(inputs)
    if accepted != expected_accepted:
        raise ValueError("accepted rows do not match frozen deterministic construction")
    if heldout != expected_heldout:
        raise ValueError("heldout rows do not match frozen deterministic construction")
    expected_manifest = _build_manifest(
        expected_accepted,
        expected_heldout,
        accepted_payload,
        heldout_payload,
        code_git_commit=code_git_commit,
        valid_pool_gold_coverage=valid_pool_gold_coverage,
    )
    if manifest != expected_manifest:
        raise ValueError(
            "data manifest does not match frozen deterministic construction"
        )
    return manifest


def validate_internal_package(
    repository_root: Path | str, *, code_git_commit: str
) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    return _validate_internal_package_at(
        root,
        root / CANONICAL_OUTPUT_PATH,
        code_git_commit=code_git_commit,
    )


def _write_file(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _before_publish(output_dir: Path) -> None:
    del output_dir


def _raise_rename_error(source: Path, target: Path) -> None:
    error_number = ctypes.get_errno()
    message = f"atomic no-replace publish failed: {source} -> {target}"
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, message, target)
    raise OSError(error_number, f"{message}: {os.strerror(error_number)}")


def _linux_rename_noreplace(source: Path, target: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise RuntimeError(
            "no supported no-replace atomic publish primitive: renameat2 unavailable"
        ) from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    if result != 0:
        _raise_rename_error(source, target)


def _macos_rename_noreplace(source: Path, target: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renamex_np = libc.renamex_np
    except AttributeError as exc:
        raise RuntimeError(
            "no supported no-replace atomic publish primitive: renamex_np unavailable"
        ) from exc
    renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    renamex_np.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = renamex_np(os.fsencode(source), os.fsencode(target), 0x00000004)
    if result != 0:
        _raise_rename_error(source, target)


def _atomic_publish_noreplace(source: Path, target: Path) -> None:
    if sys.platform.startswith("linux"):
        _linux_rename_noreplace(source, target)
        return
    if sys.platform == "darwin":
        _macos_rename_noreplace(source, target)
        return
    raise RuntimeError(
        f"no supported no-replace atomic publish primitive for {sys.platform}"
    )


def _build_internal_package_for_test(
    *, repository_root: Path | str, code_git_commit: str
) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", code_git_commit) is None:
        raise ValueError("code Git commit must be lowercase 40-hex")
    inputs = _load_inputs(repository_root)
    accepted, heldout, valid_pool_gold_coverage = _build_rows(inputs)
    accepted_payload = b"".join(_canonical_line(row) for row in accepted)
    heldout_payload = b"".join(_canonical_line(row) for row in heldout)
    manifest = _build_manifest(
        accepted,
        heldout,
        accepted_payload,
        heldout_payload,
        code_git_commit=code_git_commit,
        valid_pool_gold_coverage=valid_pool_gold_coverage,
    )
    manifest_payload = _canonical_line(manifest)

    root = inputs["root"]
    output = (root / CANONICAL_OUTPUT_PATH).resolve(strict=False)
    if not output.is_relative_to(root):
        raise ValueError("canonical output path must stay inside repository root")
    if output.exists() or output.is_symlink():
        raise ValueError("output directory must not exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        _write_file(staging / "accepted-pairs.jsonl", accepted_payload)
        _write_file(staging / "heldout-labels.jsonl", heldout_payload)
        _write_file(staging / "data-manifest.json", manifest_payload)
        _validate_internal_package_at(
            repository_root, staging, code_git_commit=code_git_commit
        )
        _before_publish(output)
        _atomic_publish_noreplace(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def build_internal_package(repository_root: Path | str) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    code_git_commit = _clean_code_commit(root)
    return _build_internal_package_for_test(
        repository_root=root, code_git_commit=code_git_commit
    )
