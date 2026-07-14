from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from hermes_skilleval.router_v2_training_pilot import (
    ADJUDICATION_PROMPT_ID,
    ADJUDICATION_PROMPT_SHA256,
    RATIONALE_MAX_CHARS,
    REVIEW_MODEL_ID,
    REVIEW_MODEL_PROVIDER,
    REVIEW_MODEL_SNAPSHOT,
    REVIEW_PROMPT_ID,
    REVIEW_PROMPT_SHA256,
    REVIEW_RUBRIC_ID,
    REVIEW_RUBRIC_SHA256,
    TRUTH_FIELDS,
    _ADJUDICATION_SCHEMA,
    _ALLOWED_OPINIONS,
    _FORBIDDEN_CLAIMS,
    _PASS_FIELDS,
    _PASS_SCHEMA,
    _validate_review_row,
    validate_new_candidate_review,
    with_row_sha256,
)


MODEL_PROVIDER = REVIEW_MODEL_PROVIDER
MODEL_ID = REVIEW_MODEL_ID
MODEL_SNAPSHOT = REVIEW_MODEL_SNAPSHOT
RUBRIC_ID = REVIEW_RUBRIC_ID

CANDIDATE_DIR = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001/candidates/round-1"
)
CANDIDATES_PATH = CANDIDATE_DIR / "candidates.jsonl"
CANDIDATE_MANIFEST_PATH = CANDIDATE_DIR / "candidate-manifest.json"
RUBRIC_PATH = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001/review/review-rubric.json"
)
CANDIDATES_SHA256 = "1f0f9d62061dc6563accd3aa2270ea58e011df4388aab6e0ad8bfa8b5982370b"
CANDIDATE_MANIFEST_SHA256 = (
    "519386b105f63a13d9029a3451fc6ac2dfbe4792dbaad8f94cc3fb6c9b8df131"
)
EXPECTED_CANDIDATE_COUNT = 59
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PASS_ISOLATION = "OTHER_PASS_OUTPUT_NOT_PROVIDED"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_line(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _json_loads_exact(text: str, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON") from exc


def _load_json(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc
    value = _json_loads_exact(text, label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if payload != _canonical_line(value):
        raise ValueError(f"{label} must be canonical JSON with LF")
    return value


def _load_jsonl(payload: bytes, *, label: str) -> list[dict[str, Any]]:
    if not payload or not payload.endswith(b"\n"):
        raise ValueError(f"{label} must use one LF per row")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(payload.splitlines(keepends=True), start=1):
        try:
            text = line[:-1].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} line {index} is not UTF-8") from exc
        value = _json_loads_exact(text, f"{label} line {index}")
        if not isinstance(value, dict):
            raise ValueError(f"{label} line {index} must be an object")
        if line != _canonical_line(value):
            raise ValueError(f"{label} line {index} must be canonical JSONL")
        rows.append(value)
    return rows


def _resolve_repo_file(root: Path, relative: Path, *, label: str) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"fixed {label} path must be repository-relative")
    target = (root / relative).resolve(strict=True)
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError(f"fixed {label} path must be a file inside repository root")
    return target


def _load_candidate_contract(
    repository_root: Path | str,
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root must be a directory")
    candidates_path = _resolve_repo_file(
        root, CANDIDATES_PATH, label="candidate bundle"
    )
    manifest_path = _resolve_repo_file(
        root, CANDIDATE_MANIFEST_PATH, label="candidate manifest"
    )
    rubric_path = _resolve_repo_file(root, RUBRIC_PATH, label="review rubric")
    candidate_payload = candidates_path.read_bytes()
    manifest_payload = manifest_path.read_bytes()
    rubric_payload = rubric_path.read_bytes()
    if _sha256(candidate_payload) != CANDIDATES_SHA256:
        raise ValueError("candidate bundle pinned SHA-256 mismatch")
    if _sha256(manifest_payload) != CANDIDATE_MANIFEST_SHA256:
        raise ValueError("candidate manifest pinned SHA-256 mismatch")
    if _sha256(rubric_payload) != REVIEW_RUBRIC_SHA256:
        raise ValueError("review rubric pinned SHA-256 mismatch")

    candidates = _load_jsonl(candidate_payload, label="candidate bundle")
    manifest = _load_json(manifest_payload, label="candidate manifest")
    rubric = _load_json(rubric_payload, label="review rubric")
    if len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError("candidate bundle must contain exactly 59 rows")
    if (
        manifest.get("candidate_count") != EXPECTED_CANDIDATE_COUNT
        or manifest.get("candidates_jsonl_sha256") != CANDIDATES_SHA256
        or manifest.get("train_count") != 43
        or manifest.get("heldout_count") != 16
    ):
        raise ValueError("candidate manifest count or bundle binding mismatch")
    candidate_ids: list[str] = []
    for row in candidates:
        candidate_id = row.get("candidate_id")
        candidate_sha = row.get("candidate_sha256")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(candidate_sha, str)
            or not HEX_SHA256.fullmatch(candidate_sha)
            or row.get("usage")
            not in {"TRAIN_HARD_NEGATIVE_CANDIDATE", "HELD_OUT_EVAL_ONLY"}
            or with_row_sha256(row) != row
        ):
            raise ValueError("candidate bundle row identity or hash mismatch")
        candidate_ids.append(candidate_id)
    if len(set(candidate_ids)) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError("candidate bundle ids must be unique")
    _validate_rubric(rubric)
    return root, candidates, rubric


def _validate_rubric(rubric: dict[str, Any]) -> None:
    expected = {
        "schema_version": "router-v2-review-rubric-v1",
        "rubric_id": RUBRIC_ID,
        "review_prompt_id": REVIEW_PROMPT_ID,
        "adjudication_prompt_id": ADJUDICATION_PROMPT_ID,
        "opinion_allowlist": sorted(_ALLOWED_OPINIONS),
        "truth": TRUTH_FIELDS,
    }
    for field, value in expected.items():
        actual = rubric.get(field)
        if field == "opinion_allowlist" and isinstance(actual, list):
            actual = sorted(actual)
        if actual != value:
            raise ValueError(f"review rubric field {field} mismatch")
    for field, opinion_field in (
        ("pass_decision_fields", "model_opinion"),
        ("adjudication_decision_fields", "adjudicated_model_opinion"),
    ):
        decision_fields = rubric.get(field)
        if (
            not isinstance(decision_fields, list)
            or any(not isinstance(value, str) for value in decision_fields)
            or len(decision_fields) != 3
            or set(decision_fields) != {"candidate_id", opinion_field, "rationale"}
        ):
            raise ValueError(f"review rubric field {field} mismatch")
    review_prompt = rubric.get("review_prompt")
    adjudication_prompt = rubric.get("adjudication_prompt")
    if (
        not isinstance(review_prompt, str)
        or _sha256(review_prompt.encode("utf-8")) != REVIEW_PROMPT_SHA256
        or not isinstance(adjudication_prompt, str)
        or _sha256(adjudication_prompt.encode("utf-8")) != ADJUDICATION_PROMPT_SHA256
    ):
        raise ValueError("review rubric prompt SHA-256 mismatch")


def _load_decisions(
    decisions_path: Path | str,
    candidates: list[dict[str, Any]],
    *,
    fields: set[str],
    opinion_field: str,
) -> list[dict[str, str]]:
    path = Path(decisions_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("decision path must be a regular file")
    values = _load_jsonl(path.read_bytes(), label="decision input")
    if len(values) != len(candidates):
        raise ValueError("decision input candidate coverage mismatch")
    if any(set(value) != fields for value in values):
        raise ValueError("decision input rows must use exact fields")
    candidate_ids = [row["candidate_id"] for row in candidates]
    decision_ids = [value.get("candidate_id") for value in values]
    if set(decision_ids) != set(candidate_ids):
        raise ValueError("decision input candidate coverage mismatch")
    if decision_ids != candidate_ids:
        raise ValueError("decision input candidate order mismatch")

    decisions: list[dict[str, str]] = []
    for value in values:
        opinion = value.get(opinion_field)
        rationale = value.get("rationale")
        if opinion not in _ALLOWED_OPINIONS:
            raise ValueError("decision input opinion is invalid")
        if not isinstance(rationale, str):
            raise ValueError("decision input rationale must be text")
        stripped = rationale.strip()
        if not stripped or len(stripped) > RATIONALE_MAX_CHARS:
            raise ValueError("decision input rationale must be 1..500 stripped chars")
        folded = stripped.casefold()
        if any(claim in folded for claim in _FORBIDDEN_CLAIMS):
            raise ValueError("decision input rationale contains a forbidden claim")
        decisions.append(
            {
                "candidate_id": value["candidate_id"],
                opinion_field: opinion,
                "rationale": stripped,
            }
        )
    return decisions


def _target_path(output_path: Path | str) -> Path:
    target = Path(output_path).resolve(strict=False)
    if target.exists() or target.is_symlink():
        raise ValueError("output target must not exist")
    return target


def _write_atomic(target: Path, rows: list[dict[str, Any]]) -> str:
    payload = b"".join(_canonical_line(row) for row in rows)
    _load_jsonl(payload, label="assembled review output")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=str(target.parent))
    )
    try:
        staged_file = staging / target.name
        staged_file.write_bytes(payload)
        if target.exists() or target.is_symlink():
            raise ValueError("output target must not exist")
        staged_file.rename(target)
    finally:
        if staging.exists() or staging.is_symlink():
            shutil.rmtree(staging)
    return _sha256(payload)


def _validate_pass_rows(
    rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    expected_pass_id: str,
) -> None:
    if len(rows) != len(candidates):
        raise ValueError("model pass candidate bundle coverage mismatch")
    for row, candidate in zip(rows, candidates, strict=True):
        _validate_review_row(
            row,
            expected_fields=_PASS_FIELDS,
            expected_schema=_PASS_SCHEMA,
        )
        if row.get("pass_id") != expected_pass_id:
            raise ValueError("model pass identity mismatch")
        if row.get("model_opinion") not in _ALLOWED_OPINIONS:
            raise ValueError("model pass opinion is invalid")
        if row.get("pass_isolation") != PASS_ISOLATION:
            raise ValueError("model pass isolation mismatch")
        if (
            row.get("candidate_id") != candidate.get("candidate_id")
            or row.get("candidate_sha256") != candidate.get("candidate_sha256")
            or row.get("usage") != candidate.get("usage")
        ):
            raise ValueError("model pass candidate bundle binding mismatch")
    run_ids = {row.get("pass_run_id") for row in rows}
    if len(run_ids) != 1 or any(
        not isinstance(run_id, str) or not run_id.strip() for run_id in run_ids
    ):
        raise ValueError("model pass requires one non-empty run identity")


def assemble_pass_review(
    *,
    repository_root: Path | str,
    pass_id: str,
    pass_run_id: str,
    decisions_path: Path | str,
    output_path: Path | str,
) -> dict[str, Any]:
    target = _target_path(output_path)
    if pass_id not in {"MODEL_PASS_1", "MODEL_PASS_2"}:
        raise ValueError("pass id must be MODEL_PASS_1 or MODEL_PASS_2")
    if not isinstance(pass_run_id, str) or not pass_run_id.strip():
        raise ValueError("pass run id must be non-empty")
    _, candidates, rubric = _load_candidate_contract(repository_root)
    decisions = _load_decisions(
        decisions_path,
        candidates,
        fields=set(rubric["pass_decision_fields"]),
        opinion_field="model_opinion",
    )
    rows = [
        with_row_sha256(
            {
                **TRUTH_FIELDS,
                "schema_version": _PASS_SCHEMA,
                "candidate_id": candidate["candidate_id"],
                "candidate_sha256": candidate["candidate_sha256"],
                "usage": candidate["usage"],
                "pass_id": pass_id,
                "pass_run_id": pass_run_id.strip(),
                "pass_isolation": PASS_ISOLATION,
                "model_provider": MODEL_PROVIDER,
                "model_id": MODEL_ID,
                "model_snapshot": MODEL_SNAPSHOT,
                "review_prompt_id": REVIEW_PROMPT_ID,
                "review_prompt_sha256": REVIEW_PROMPT_SHA256,
                "rubric_id": RUBRIC_ID,
                "rubric_sha256": REVIEW_RUBRIC_SHA256,
                "model_opinion": decision["model_opinion"],
                "rationale": decision["rationale"],
            }
        )
        for candidate, decision in zip(candidates, decisions, strict=True)
    ]
    _validate_pass_rows(rows, candidates, expected_pass_id=pass_id)
    output_sha = _write_atomic(target, rows)
    return {
        **TRUTH_FIELDS,
        "candidate_count": len(rows),
        "pass_id": pass_id,
        "output_sha256": output_sha,
        "validation_status": "PASS",
    }


def assemble_adjudication_review(
    *,
    repository_root: Path | str,
    pass_1_path: Path | str,
    pass_2_path: Path | str,
    decisions_path: Path | str,
    output_path: Path | str,
) -> dict[str, Any]:
    target = _target_path(output_path)
    _, candidates, rubric = _load_candidate_contract(repository_root)
    pass_1 = _load_jsonl(
        Path(pass_1_path).resolve(strict=True).read_bytes(), label="model pass 1"
    )
    pass_2 = _load_jsonl(
        Path(pass_2_path).resolve(strict=True).read_bytes(), label="model pass 2"
    )
    _validate_pass_rows(pass_1, candidates, expected_pass_id="MODEL_PASS_1")
    _validate_pass_rows(pass_2, candidates, expected_pass_id="MODEL_PASS_2")
    if {row["pass_run_id"] for row in pass_1} == {row["pass_run_id"] for row in pass_2}:
        raise ValueError("model passes require distinct pass run identities")
    decisions = _load_decisions(
        decisions_path,
        candidates,
        fields=set(rubric["adjudication_decision_fields"]),
        opinion_field="adjudicated_model_opinion",
    )
    rows = [
        with_row_sha256(
            {
                **TRUTH_FIELDS,
                "schema_version": _ADJUDICATION_SCHEMA,
                "candidate_id": candidate["candidate_id"],
                "candidate_sha256": candidate["candidate_sha256"],
                "usage": candidate["usage"],
                "adjudicator_model_provider": MODEL_PROVIDER,
                "adjudicator_model_id": MODEL_ID,
                "adjudicator_model_snapshot": MODEL_SNAPSHOT,
                "adjudication_prompt_id": ADJUDICATION_PROMPT_ID,
                "adjudication_prompt_sha256": ADJUDICATION_PROMPT_SHA256,
                "rubric_id": RUBRIC_ID,
                "rubric_sha256": REVIEW_RUBRIC_SHA256,
                "pass_1_row_sha256": first["row_sha256"],
                "pass_2_row_sha256": second["row_sha256"],
                "pass_1_model_opinion": first["model_opinion"],
                "pass_2_model_opinion": second["model_opinion"],
                "opinions_agree": first["model_opinion"] == second["model_opinion"],
                "adjudicated_model_opinion": decision["adjudicated_model_opinion"],
                "rationale": decision["rationale"],
            }
        )
        for candidate, first, second, decision in zip(
            candidates, pass_1, pass_2, decisions, strict=True
        )
    ]
    validation = validate_new_candidate_review(pass_1, pass_2, rows)
    output_sha = _write_atomic(target, rows)
    return {**validation, "output_sha256": output_sha}
