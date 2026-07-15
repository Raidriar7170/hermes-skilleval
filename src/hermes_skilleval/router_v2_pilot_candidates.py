from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from hermes_skilleval.router_v2_training_pilot import (
    MODEL_ID,
    MODEL_REVISION,
    SKILL_INDEX_SHA256,
    SOURCE_CANDIDATES_SHA256,
    SOURCE_MANIFEST_SHA256,
    SOURCE_SNAPSHOT_ID,
    TRUTH_FIELDS,
    canonical_sha256,
    validate_mining_bundle,
    with_row_sha256,
)


TRAIN_USAGE = "TRAIN_HARD_NEGATIVE_CANDIDATE"
HELDOUT_USAGE = "HELD_OUT_EVAL_ONLY"
SELECTOR_VERSION = "taxonomy-lexical-v1"
MINING_ROUND = 1
EXPECTED_TRAIN_CANDIDATE_COUNT = 43
EXPECTED_HELDOUT_CANDIDATE_COUNT = 16
EXPECTED_CANDIDATE_COUNT = 59
EXPECTED_RETAINED_TASK_COUNT = 21

SOURCE_MANIFEST_PATH = Path("data/router-v2-v4/source-manifest.json")
SOURCE_CANDIDATES_PATH = Path("data/router-v2-v4/source-candidates.jsonl")
SKILL_INDEX_PATH = Path("docs/demo/phase9-real-skill-library-migration/skills.json")
MINING_DIR = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001/mining"
)
MINING_ROWS_PATH = MINING_DIR / "mining.jsonl"
MINING_MANIFEST_PATH = MINING_DIR / "mining-manifest.json"
PRIOR_FILTER_PATH = MINING_DIR / "prior-review-filter.json"
MINING_JSONL_SHA256 = "29d20c95f1e280de2a24875ea3cfbf4fd5fbae8fb513d749c13da3ab2df21f88"
MINING_MANIFEST_SHA256 = (
    "1eba5a66f5065ae6792f43c2c8b186db2628d33a2a7c2a0d9f0e0787935e6a2d"
)
PRIOR_FILTER_SHA256 = "d8bffc89872f5795e7a366e3ff1f01de6a1a04e120e09c2ef01bb223b81025cc"

TOKEN_RE = re.compile(r"[a-z0-9]+")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
EIGHT_DECIMAL = re.compile(r"-?\d+\.\d{8}\Z")

MANIFEST_TRUTH_FIELDS: dict[str, object] = {
    **TRUTH_FIELDS,
    "can_start_internal_training": False,
    "can_start_production_training": False,
    "blind_v2_eligible": False,
    "heldout_mining_eligible": False,
    "heldout_training_eligible": False,
}

COMMON_ROW_FIELDS = {
    "schema_version",
    "usage",
    "candidate_id",
    "candidate_sha256",
    "task_id",
    "query_text",
    "prompt_sha256",
    "positive_source_record_id",
    "positive_source_record_exact_bytes_sha256",
    "gold_skill_id",
    "candidate_skill_id",
    "gold_skill_record_sha256",
    "candidate_skill_record_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "skill_index_sha256",
    "skill_bindings_sha256",
    "row_sha256",
}
TRAIN_ROW_FIELDS = COMMON_ROW_FIELDS | {
    "mining_round",
    "authored_hard_negative_skill_id",
    "authored_hard_negative_source_record_id",
    "candidate_rank",
    "gold_score",
    "candidate_score",
    "score_margin",
    "baseline_hard",
    "mining_row_sha256",
    "mining_jsonl_sha256",
    "mining_manifest_sha256",
    "model_id",
    "model_revision",
    "model_file_manifest_sha256",
}
HELDOUT_ROW_FIELDS = COMMON_ROW_FIELDS | {
    "selector_version",
    "selector_top_3",
    "candidate_selector_rank",
    "token_overlap_count",
    "token_jaccard",
    "baseline_scores_read",
    "heldout_mining_eligible",
    "heldout_training_eligible",
}


@dataclass(frozen=True)
class CandidateInputs:
    source_rows: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    skill_bindings: list[dict[str, str]]
    skill_bindings_sha256: str
    mining_rows: list[dict[str, Any]]
    mining_manifest: dict[str, Any]
    mining_jsonl_sha256: str
    mining_manifest_sha256: str
    prior_report: dict[str, Any]
    prior_report_sha256: str
    retained_task_ids: frozenset[str]


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


def _load_json(payload: bytes, *, label: str, canonical: bool) -> Any:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc
    value = _json_loads_exact(text, label)
    if canonical and payload != _canonical_line(value):
        raise ValueError(f"{label} is not canonical JSON with LF")
    return value


def _load_jsonl(
    payload: bytes, *, label: str
) -> tuple[list[dict[str, Any]], list[bytes]]:
    if not payload or not payload.endswith(b"\n"):
        raise ValueError(f"{label} must use one LF per row")
    rows: list[dict[str, Any]] = []
    lines = payload.splitlines(keepends=True)
    for index, line in enumerate(lines, start=1):
        if not line.endswith(b"\n"):
            raise ValueError(f"{label} line {index} is missing LF")
        try:
            text = line[:-1].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} line {index} is not UTF-8") from exc
        row = _json_loads_exact(text, f"{label} line {index}")
        if not isinstance(row, dict):
            raise ValueError(f"{label} line {index} must be an object")
        if line != _canonical_line(row):
            raise ValueError(f"{label} line {index} is not canonical JSONL")
        rows.append(row)
    return rows, lines


def _resolve_inputs(root: Path) -> dict[str, Path]:
    fixed = {
        "source_manifest": SOURCE_MANIFEST_PATH,
        "source_candidates": SOURCE_CANDIDATES_PATH,
        "skill_index": SKILL_INDEX_PATH,
        "mining_rows": MINING_ROWS_PATH,
        "mining_manifest": MINING_MANIFEST_PATH,
        "prior_filter": PRIOR_FILTER_PATH,
    }
    resolved: dict[str, Path] = {}
    for label, relative in fixed.items():
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"fixed {label} path must be repository-relative")
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError(f"fixed {label} path must stay inside repository root")
        if not target.is_file():
            raise ValueError(f"fixed {label} path must be a regular file")
        resolved[label] = target
    return resolved


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


def _skill_bindings(skills: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "skill_id": skill["id"],
            "skill_record_sha256": canonical_sha256(skill),
            "skill_text_sha256": canonical_sha256(_skill_text(skill)),
        }
        for skill in skills
    ]


def _source_bindings(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {
            "task_id": row["task_id"],
            "source_record_id": row["source_record_id"],
            "source_record_exact_bytes_sha256": row["source_record_exact_bytes_sha256"],
            "prompt_sha256": row["prompt_text_sha256"],
            "positive_skill_id": row["positive_skill_id"],
            "split": "train",
            "source_role": "POSITIVE",
        }
        for row in source_rows
        if row["split"] == "train" and row["source_role"] == "POSITIVE"
    ]


def _load_inputs(repository_root: Path | str) -> CandidateInputs:
    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root must be a directory")
    paths = _resolve_inputs(root)
    payloads = {name: path.read_bytes() for name, path in paths.items()}

    if _sha256(payloads["source_manifest"]) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source manifest SHA-256 mismatch")
    if _sha256(payloads["source_candidates"]) != SOURCE_CANDIDATES_SHA256:
        raise ValueError("source candidates SHA-256 mismatch")
    if _sha256(payloads["skill_index"]) != SKILL_INDEX_SHA256:
        raise ValueError("skill index SHA-256 mismatch")
    if _sha256(payloads["mining_rows"]) != MINING_JSONL_SHA256:
        raise ValueError("mining JSONL file SHA-256 mismatch")
    if _sha256(payloads["mining_manifest"]) != MINING_MANIFEST_SHA256:
        raise ValueError("mining manifest file SHA-256 mismatch")
    if _sha256(payloads["prior_filter"]) != PRIOR_FILTER_SHA256:
        raise ValueError("prior-review filter file SHA-256 mismatch")

    source_manifest = _load_json(
        payloads["source_manifest"], label="source manifest", canonical=False
    )
    if (
        not isinstance(source_manifest, dict)
        or source_manifest.get("snapshot_id") != SOURCE_SNAPSHOT_ID
        or not isinstance(source_manifest.get("records"), list)
        or len(source_manifest["records"]) != 192
    ):
        raise ValueError("source manifest snapshot or record count mismatch")
    source_rows, source_lines = _load_jsonl(
        payloads["source_candidates"], label="source candidates"
    )
    if len(source_rows) != 192:
        raise ValueError("source candidates must contain exactly 192 rows")
    restored_rows: list[dict[str, Any]] = []
    for index, (record, row, line) in enumerate(
        zip(source_manifest["records"], source_rows, source_lines, strict=True), start=1
    ):
        if not isinstance(record, dict):
            raise ValueError(f"source manifest record {index} is invalid")
        exact_hash = _sha256(line)
        if record.get("source_record_exact_bytes_sha256") != exact_hash:
            raise ValueError(f"source record {index} exact hash mismatch")
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
        query = row.get("query_text")
        if not isinstance(query, str) or _sha256(query.encode("utf-8")) != row.get(
            "prompt_text_sha256"
        ):
            raise ValueError(f"source record {index} prompt hash mismatch")
        restored_rows.append({**row, "source_record_exact_bytes_sha256": exact_hash})

    skills_value = _load_json(
        payloads["skill_index"], label="skill index", canonical=False
    )
    if not isinstance(skills_value, list) or len(skills_value) != 16:
        raise ValueError("skill index must contain exactly 16 rows")
    skills: list[dict[str, Any]] = []
    for skill in skills_value:
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), str):
            raise ValueError("skill index row is invalid")
        skills.append(skill)
    if len({skill["id"] for skill in skills}) != 16:
        raise ValueError("skill index contains duplicate ids")
    skills.sort(key=lambda skill: skill["id"])
    bindings = _skill_bindings(skills)
    bindings_sha = canonical_sha256(bindings)

    mining_manifest = _load_json(
        payloads["mining_manifest"], label="mining manifest", canonical=True
    )
    if not isinstance(mining_manifest, dict):
        raise ValueError("mining manifest must be an object")
    mining_jsonl_sha = _sha256(payloads["mining_rows"])
    if mining_manifest.get("mining_jsonl_sha256") != mining_jsonl_sha:
        raise ValueError("mining JSONL SHA-256 mismatch")
    mining_rows, _ = _load_jsonl(payloads["mining_rows"], label="mining rows")
    train_positives = [
        row
        for row in restored_rows
        if row["split"] == "train" and row["source_role"] == "POSITIVE"
    ]
    source_bindings = _source_bindings(train_positives)
    validate_mining_bundle(
        mining_rows,
        mining_manifest,
        expected_source_bindings=source_bindings,
        expected_skill_bindings=bindings,
    )

    prior_report = _load_json(
        payloads["prior_filter"], label="prior-review filter", canonical=True
    )
    if not isinstance(prior_report, dict):
        raise ValueError("prior-review filter must be an object")
    unhashed_report = {
        key: value for key, value in prior_report.items() if key != "report_sha256"
    }
    if prior_report.get("report_sha256") != canonical_sha256(unhashed_report):
        raise ValueError("prior-review report SHA-256 mismatch")
    if (
        prior_report.get("supported_count") != 35
        or prior_report.get("disputed_count") != 29
        or prior_report.get("retained_count") != EXPECTED_RETAINED_TASK_COUNT
        or prior_report.get("mining_rows_sha256") != mining_manifest.get("rows_sha256")
    ):
        raise ValueError("prior-review report counts or mining binding mismatch")
    retained_source_ids = prior_report.get("retained_source_record_ids")
    authored_by_source_id = {
        row["source_record_id"]: row
        for row in restored_rows
        if row["split"] == "train" and row["source_role"] == "HARD_NEGATIVE_CANDIDATE"
    }
    if (
        not isinstance(retained_source_ids, list)
        or len(retained_source_ids) != EXPECTED_RETAINED_TASK_COUNT
        or len(set(retained_source_ids)) != EXPECTED_RETAINED_TASK_COUNT
    ):
        raise ValueError("prior-review retained source ids mismatch")
    retained_task_ids: set[str] = set()
    for source_id in retained_source_ids:
        if not isinstance(source_id, str):
            raise ValueError("prior-review retained source id must be a string")
        task_id, separator, skill_id = source_id.partition(":hard-negative-candidate:")
        authored_row = authored_by_source_id.get(source_id)
        if (
            not separator
            or authored_row is None
            or authored_row["task_id"] != task_id
            or authored_row["skill_id"] != skill_id
        ):
            raise ValueError(
                "prior-review retained source id is not frozen authored data"
            )
        retained_task_ids.add(task_id)
    if len(retained_task_ids) != EXPECTED_RETAINED_TASK_COUNT:
        raise ValueError("prior-review retained task ids must be unique")
    return CandidateInputs(
        source_rows=restored_rows,
        skills=skills,
        skill_bindings=bindings,
        skill_bindings_sha256=bindings_sha,
        mining_rows=mining_rows,
        mining_manifest=mining_manifest,
        mining_jsonl_sha256=mining_jsonl_sha,
        mining_manifest_sha256=_sha256(payloads["mining_manifest"]),
        prior_report=prior_report,
        prior_report_sha256=_sha256(payloads["prior_filter"]),
        retained_task_ids=frozenset(retained_task_ids),
    )


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def select_heldout_candidate(
    source_row: dict[str, Any], skills: list[dict[str, Any]]
) -> dict[str, Any]:
    gold_id = source_row.get("positive_skill_id")
    query = source_row.get("query_text")
    by_id = {skill.get("id"): skill for skill in skills}
    if (
        not isinstance(gold_id, str)
        or gold_id not in by_id
        or not isinstance(query, str)
    ):
        raise ValueError("heldout source identity is invalid")
    gold = by_id[gold_id]
    non_gold = [skill for skill in skills if skill.get("id") != gold_id]
    same_category = [
        skill for skill in non_gold if skill.get("category") == gold.get("category")
    ]
    pool = same_category or non_gold
    query_tokens = _tokens(query)
    scored: list[dict[str, Any]] = []
    for skill in pool:
        skill_tokens = _tokens(_skill_text(skill))
        overlap = len(query_tokens & skill_tokens)
        union = query_tokens | skill_tokens
        jaccard = Decimal(overlap) / Decimal(len(union)) if union else Decimal(0)
        scored.append(
            {
                "skill_id": skill["id"],
                "token_overlap_count": overlap,
                "token_jaccard": f"{jaccard.quantize(Decimal('0.00000000')):.8f}",
            }
        )
    scored.sort(
        key=lambda item: (
            -item["token_overlap_count"],
            -Decimal(item["token_jaccard"]),
            item["skill_id"],
        )
    )
    if not scored:
        raise ValueError("heldout selector has no non-gold candidate")
    return {**scored[0], "selector_top_3": scored[:3]}


def _candidate_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"candidate_sha256", "row_sha256"}
    }


def _candidate_sha256(row: dict[str, Any]) -> str:
    return _sha256(_canonical_line(_candidate_payload(row)))


def _build_train_rows(inputs: CandidateInputs) -> list[dict[str, Any]]:
    positives = {
        row["task_id"]: row
        for row in inputs.source_rows
        if row["split"] == "train" and row["source_role"] == "POSITIVE"
    }
    authored = {
        row["task_id"]: row
        for row in inputs.source_rows
        if row["split"] == "train" and row["source_role"] == "HARD_NEGATIVE_CANDIDATE"
    }
    skills = {skill["id"]: skill for skill in inputs.skills}
    skill_hashes = {
        binding["skill_id"]: binding["skill_record_sha256"]
        for binding in inputs.skill_bindings
    }
    disputed = set(inputs.prior_report["excluded_disputed_source_record_ids"])
    result: list[dict[str, Any]] = []
    for mining in inputs.mining_rows:
        task_id = mining["task_id"]
        if task_id in inputs.retained_task_ids:
            continue
        positive = positives.get(task_id)
        authored_row = authored.get(task_id)
        if positive is None or authored_row is None:
            raise ValueError("mining task lacks frozen positive or authored negative")
        gold_id = mining["gold_skill_id"]
        authored_id = authored_row["skill_id"]
        scores = mining["scores"]
        selected = next(
            (item for item in scores if item["skill_id"] not in {gold_id, authored_id}),
            None,
        )
        if selected is None:
            raise ValueError("train task has no unseen non-gold candidate")
        candidate_id = selected["skill_id"]
        rank = next(
            index
            for index, item in enumerate(scores, start=1)
            if item["skill_id"] == candidate_id
        )
        gold_score = next(
            item["score"] for item in scores if item["skill_id"] == gold_id
        )
        margin = (Decimal(gold_score) - Decimal(selected["score"])).quantize(
            Decimal("0.00000000")
        )
        hard = rank <= 5 or margin <= Decimal("0.05")
        if not hard:
            raise ValueError("round-1 candidate is not baseline hard")
        source_candidate_id = f"{task_id}:hard-negative-candidate:{candidate_id}"
        if source_candidate_id in disputed:
            raise ValueError("round-1 candidate reuses a disputed source candidate")
        row: dict[str, Any] = {
            "schema_version": "router-v2-pilot-train-candidate-v1",
            "usage": TRAIN_USAGE,
            "candidate_id": f"{task_id}:round-1:{candidate_id}",
            "task_id": task_id,
            "query_text": positive["query_text"],
            "prompt_sha256": positive["prompt_text_sha256"],
            "positive_source_record_id": positive["source_record_id"],
            "positive_source_record_exact_bytes_sha256": positive[
                "source_record_exact_bytes_sha256"
            ],
            "gold_skill_id": gold_id,
            "candidate_skill_id": candidate_id,
            "gold_skill_record_sha256": skill_hashes[gold_id],
            "candidate_skill_record_sha256": skill_hashes[candidate_id],
            "source_snapshot_id": SOURCE_SNAPSHOT_ID,
            "source_candidates_sha256": SOURCE_CANDIDATES_SHA256,
            "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "skill_index_sha256": SKILL_INDEX_SHA256,
            "skill_bindings_sha256": inputs.skill_bindings_sha256,
            "mining_round": MINING_ROUND,
            "authored_hard_negative_skill_id": authored_id,
            "authored_hard_negative_source_record_id": authored_row["source_record_id"],
            "candidate_rank": rank,
            "gold_score": gold_score,
            "candidate_score": selected["score"],
            "score_margin": f"{margin:.8f}",
            "baseline_hard": hard,
            "mining_row_sha256": mining["row_sha256"],
            "mining_jsonl_sha256": inputs.mining_jsonl_sha256,
            "mining_manifest_sha256": inputs.mining_manifest_sha256,
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "model_file_manifest_sha256": inputs.mining_manifest[
                "model_file_manifest_sha256"
            ],
        }
        if candidate_id not in skills:
            raise ValueError("round-1 candidate skill is unknown")
        row["candidate_sha256"] = _candidate_sha256(row)
        result.append(with_row_sha256(row))
    return result


def _build_heldout_rows(inputs: CandidateInputs) -> list[dict[str, Any]]:
    heldout_sources = [
        row
        for row in inputs.source_rows
        if row["split"] == "non_blind_test" and row["source_role"] == "POSITIVE"
    ]
    if len(heldout_sources) != 16:
        raise ValueError(
            "heldout selector requires exactly 16 non-blind-test positives"
        )
    skill_hashes = {
        binding["skill_id"]: binding["skill_record_sha256"]
        for binding in inputs.skill_bindings
    }
    result: list[dict[str, Any]] = []
    for source in heldout_sources:
        selected = select_heldout_candidate(source, inputs.skills)
        gold_id = source["positive_skill_id"]
        candidate_id = selected["skill_id"]
        row: dict[str, Any] = {
            "schema_version": "router-v2-pilot-heldout-candidate-v1",
            "usage": HELDOUT_USAGE,
            "candidate_id": f"{source['task_id']}:held-out-eval-only:{candidate_id}",
            "task_id": source["task_id"],
            "query_text": source["query_text"],
            "prompt_sha256": source["prompt_text_sha256"],
            "positive_source_record_id": source["source_record_id"],
            "positive_source_record_exact_bytes_sha256": source[
                "source_record_exact_bytes_sha256"
            ],
            "gold_skill_id": gold_id,
            "candidate_skill_id": candidate_id,
            "gold_skill_record_sha256": skill_hashes[gold_id],
            "candidate_skill_record_sha256": skill_hashes[candidate_id],
            "source_snapshot_id": SOURCE_SNAPSHOT_ID,
            "source_candidates_sha256": SOURCE_CANDIDATES_SHA256,
            "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "skill_index_sha256": SKILL_INDEX_SHA256,
            "skill_bindings_sha256": inputs.skill_bindings_sha256,
            "selector_version": SELECTOR_VERSION,
            "selector_top_3": selected["selector_top_3"],
            "candidate_selector_rank": 1,
            "token_overlap_count": selected["token_overlap_count"],
            "token_jaccard": selected["token_jaccard"],
            "baseline_scores_read": False,
            "heldout_mining_eligible": False,
            "heldout_training_eligible": False,
        }
        row["candidate_sha256"] = _candidate_sha256(row)
        result.append(with_row_sha256(row))
    return result


def _build_rows(inputs: CandidateInputs) -> list[dict[str, Any]]:
    train = _build_train_rows(inputs)
    heldout = _build_heldout_rows(inputs)
    if (
        len(train) != EXPECTED_TRAIN_CANDIDATE_COUNT
        or len(heldout) != EXPECTED_HELDOUT_CANDIDATE_COUNT
    ):
        raise ValueError(
            "candidate bundle must contain 43 new train and 16 heldout rows"
        )
    return [*train, *heldout]


def _build_manifest(
    rows: list[dict[str, Any]], inputs: CandidateInputs
) -> dict[str, Any]:
    payload = b"".join(_canonical_line(row) for row in rows)
    return {
        **MANIFEST_TRUTH_FIELDS,
        "schema_version": "router-v2-pilot-candidate-manifest-v1",
        "selector_version": SELECTOR_VERSION,
        "mining_round": MINING_ROUND,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_candidates_sha256": SOURCE_CANDIDATES_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "skill_index_sha256": SKILL_INDEX_SHA256,
        "skill_bindings_sha256": inputs.skill_bindings_sha256,
        "mining_jsonl_sha256": inputs.mining_jsonl_sha256,
        "mining_manifest_sha256": inputs.mining_manifest_sha256,
        "prior_review_filter_sha256": inputs.prior_report_sha256,
        "candidate_count": len(rows),
        "train_count": sum(row["usage"] == TRAIN_USAGE for row in rows),
        "heldout_count": sum(row["usage"] == HELDOUT_USAGE for row in rows),
        "usage_order": [TRAIN_USAGE, HELDOUT_USAGE],
        "excluded_disputed_source_record_ids": inputs.prior_report[
            "excluded_disputed_source_record_ids"
        ],
        "candidates_jsonl_sha256": _sha256(payload),
        "rows_sha256": canonical_sha256(rows),
        "non_actions": ["blind_v2", "gpu", "model_review", "training"],
    }


def _validate_with_inputs(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    inputs: CandidateInputs,
) -> dict[str, Any]:
    if len(rows) != EXPECTED_CANDIDATE_COUNT:
        raise ValueError("candidate bundle must contain exactly 59 rows")
    if [row.get("usage") for row in rows] != [
        TRAIN_USAGE
    ] * EXPECTED_TRAIN_CANDIDATE_COUNT + [
        HELDOUT_USAGE
    ] * EXPECTED_HELDOUT_CANDIDATE_COUNT:
        raise ValueError("candidate bundle usage ordering mismatch")
    seen: set[str] = set()
    for row in rows:
        usage = row.get("usage")
        expected_fields = (
            TRAIN_ROW_FIELDS if usage == TRAIN_USAGE else HELDOUT_ROW_FIELDS
        )
        if set(row) != expected_fields:
            raise ValueError("candidate row fields mismatch")
        candidate_id = row.get("candidate_id")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or candidate_id in seen
        ):
            raise ValueError("candidate ids must be explicit and unique")
        seen.add(candidate_id)
        declared_candidate_sha = row.get("candidate_sha256")
        if (
            not isinstance(declared_candidate_sha, str)
            or not HEX_SHA256.fullmatch(declared_candidate_sha)
            or declared_candidate_sha != _candidate_sha256(row)
        ):
            raise ValueError("candidate SHA-256 mismatch")
        if with_row_sha256(row) != row:
            raise ValueError("candidate row SHA-256 mismatch")
        if row.get("gold_skill_id") == row.get("candidate_skill_id"):
            raise ValueError("candidate skill must differ from gold skill")
        if usage == TRAIN_USAGE:
            if row.get("mining_round") != 1 or row.get("baseline_hard") is not True:
                raise ValueError("train candidate must be round-1 baseline hard")
            candidate_rank = row.get("candidate_rank")
            score_margin = row.get("score_margin")
            if (
                not isinstance(candidate_rank, int)
                or candidate_rank <= 0
                or not isinstance(score_margin, str)
                or not EIGHT_DECIMAL.fullmatch(score_margin)
            ):
                raise ValueError("train candidate rank or score margin is invalid")
        else:
            if (
                row.get("baseline_scores_read") is not False
                or row.get("heldout_mining_eligible") is not False
                or row.get("heldout_training_eligible") is not False
            ):
                raise ValueError(
                    "heldout candidate must remain score-blind and isolated"
                )

    expected_rows = _build_rows(inputs)
    if rows != expected_rows:
        raise ValueError(
            "candidate rows do not match deterministic frozen construction"
        )
    expected_manifest = _build_manifest(expected_rows, inputs)
    if manifest != expected_manifest:
        raise ValueError("candidate manifest does not match frozen construction")
    if manifest.get("rows_sha256") != canonical_sha256(rows):
        raise ValueError("candidate rows SHA-256 mismatch")
    payload = b"".join(_canonical_line(row) for row in rows)
    if manifest.get("candidates_jsonl_sha256") != _sha256(payload):
        raise ValueError("candidate JSONL SHA-256 mismatch")
    for field, expected in MANIFEST_TRUTH_FIELDS.items():
        if manifest.get(field) != expected or type(manifest.get(field)) is not type(
            expected
        ):
            raise ValueError(f"candidate manifest truth field {field} mismatch")
    return {
        **MANIFEST_TRUTH_FIELDS,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "train_count": EXPECTED_TRAIN_CANDIDATE_COUNT,
        "heldout_count": EXPECTED_HELDOUT_CANDIDATE_COUNT,
        "validation_status": "PASS",
    }


def validate_candidate_bundle(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    repository_root: Path | str,
) -> dict[str, Any]:
    inputs = _load_inputs(repository_root)
    return _validate_with_inputs(rows, manifest, inputs)


def _write_outputs(
    output_dir: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]
) -> None:
    rows_payload = b"".join(_canonical_line(row) for row in rows)
    manifest_payload = _canonical_line(manifest)
    if _sha256(rows_payload) != manifest["candidates_jsonl_sha256"]:
        raise ValueError("candidate output bytes do not match manifest")
    _load_jsonl(rows_payload, label="candidate output")
    _load_json(manifest_payload, label="candidate manifest output", canonical=True)
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("output directory must not exist")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-", dir=str(output_dir.parent)
        )
    )
    try:
        (staging / "candidates.jsonl").write_bytes(rows_payload)
        (staging / "candidate-manifest.json").write_bytes(manifest_payload)
        if output_dir.exists() or output_dir.is_symlink():
            raise ValueError("output directory must not exist")
        staging.rename(output_dir)
    finally:
        if staging.exists() or staging.is_symlink():
            shutil.rmtree(staging)


def build_candidate_bundle(
    *, repository_root: Path | str, output_dir: Path | str
) -> dict[str, Any]:
    target = Path(output_dir).resolve(strict=False)
    if target.exists() or target.is_symlink():
        raise ValueError("output directory must not exist")
    inputs = _load_inputs(repository_root)
    rows = _build_rows(inputs)
    manifest = _build_manifest(rows, inputs)
    result = _validate_with_inputs(rows, manifest, inputs)
    _write_outputs(target, rows, manifest)
    return result
