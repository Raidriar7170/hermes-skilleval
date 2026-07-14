from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any, Protocol


MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
SKILL_INDEX_SHA256 = "c67a786a6dcdc6f71716894f22f8ba409c38ec0954a07143b09a0372159ccaf5"
PR37_ADJUDICATION_SHA256 = (
    "4b5ef89a47e9e821b20f06bb4539ab4ac5f4ccb3fc05c36b1887158489591ff2"
)
SOURCE_SNAPSHOT_ID = "router-v2-v4-source-38afe7d5b2500d4a"
SOURCE_CANDIDATES_SHA256 = (
    "5fa7e7feb1a5fedc2cf8bcc8adf17afe3356f9d4614b2848b0d74f88718e3d2a"
)
SOURCE_MANIFEST_SHA256 = (
    "330f13d58833450293374f91e253dadf452b5a7d5233a4aa025984e09b0ed511"
)
RATIONALE_MAX_CHARS = 500

TRUTH_FIELDS: dict[str, object] = {
    "review_mode": "MODEL_ONLY_PILOT",
    "human_reviewer_count": 0,
    "model_review_pass_count": 2,
    "model_adjudication_enabled": True,
    "independent_human_review": False,
    "model_correlation_risk": True,
    "release_eligible": False,
    "router_decision": "KEEP_BASELINE",
}

_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EIGHT_DECIMAL = re.compile(r"-?\d+\.\d{8}\Z")
_PASS_SCHEMA = "router-v2-new-candidate-model-pass-v1"
_ADJUDICATION_SCHEMA = "router-v2-new-candidate-model-adjudication-v1"
_ALLOWED_USAGES = {"TRAIN_HARD_NEGATIVE_CANDIDATE", "HELD_OUT_EVAL_ONLY"}
_ALLOWED_OPINIONS = {
    "HARD_NEGATIVE_ROLE_SUPPORTED",
    "HARD_NEGATIVE_ROLE_DISPUTED",
    "MODEL_UNCERTAIN",
}
_PR37_OPINIONS = {
    "HARD_NEGATIVE_ROLE_SUPPORTED",
    "HARD_NEGATIVE_ROLE_DISPUTED",
}
_FORBIDDEN_REVIEW_FIELDS = {
    "accepted",
    "decision",
    "human_decision",
    "human_reviewer",
    "reviewed_by",
    "reviewer",
    "training_label",
}
_FORBIDDEN_CLAIMS = (
    "human-reviewed",
    "human-accepted",
    "human accepted",
    "人工审核完成",
    "reviewer is the project owner",
    "reviewer 是项目所有者",
    "reviewer 是项目所有者本人",
    "independent human review",
    "production-ready data",
    "production release",
    "router promotion",
    "release claim",
    "blind-v2 conclusion",
    "blind-v2 final conclusion",
    "blind-v2 最终结论",
    "生产发布",
    "人工标注数据",
    "简历中的人工审核 claim",
    "resume human-review claim",
    "résumé human-review claim",
)
_MODEL_FILE_FIELDS = {"path", "size", "sha256"}
_SOURCE_BINDING_FIELDS = {
    "task_id",
    "source_record_id",
    "source_record_exact_bytes_sha256",
    "prompt_sha256",
    "positive_skill_id",
    "split",
    "source_role",
}
_SKILL_BINDING_FIELDS = {
    "skill_id",
    "skill_record_sha256",
    "skill_text_sha256",
}
_PASS_FIELDS = set(TRUTH_FIELDS) | {
    "schema_version",
    "candidate_id",
    "candidate_sha256",
    "usage",
    "pass_id",
    "pass_run_id",
    "pass_isolation",
    "model_opinion",
    "rationale",
    "row_sha256",
}
_ADJUDICATION_FIELDS = set(TRUTH_FIELDS) | {
    "schema_version",
    "candidate_id",
    "candidate_sha256",
    "usage",
    "pass_1_row_sha256",
    "pass_2_row_sha256",
    "pass_1_model_opinion",
    "pass_2_model_opinion",
    "opinions_agree",
    "adjudicated_model_opinion",
    "rationale",
    "row_sha256",
}
_MINING_ROW_FIELDS = {
    "schema_version",
    "task_id",
    "source_record_id",
    "source_record_exact_bytes_sha256",
    "gold_skill_id",
    "prompt_sha256",
    "scores",
    "gold_rank",
    "top_3_non_gold",
    "candidate_skill_id",
    "candidate_rank",
    "score_margin",
    "baseline_hard",
    "model_id",
    "model_revision",
    "model_file_manifest_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "source_bindings_sha256",
    "skill_index_sha256",
    "skill_bindings_sha256",
    "row_sha256",
}
_MINING_MANIFEST_FIELDS = {
    "schema_version",
    "model_id",
    "model_revision",
    "device",
    "thread_count",
    "normalize_embeddings",
    "model_file_manifest",
    "model_file_manifest_sha256",
    "source_snapshot_id",
    "source_candidates_sha256",
    "source_manifest_sha256",
    "source_bindings",
    "source_bindings_sha256",
    "skill_index_sha256",
    "skill_bindings",
    "skill_bindings_sha256",
    "row_count",
    "rows_sha256",
}


class Encoder(Protocol):
    model_id: str
    model_revision: str
    device: str
    thread_count: int
    normalize_embeddings: bool

    def encode(self, texts: list[str]) -> list[list[float]]: ...


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def with_row_sha256(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key != "row_sha256"}
    result["row_sha256"] = canonical_sha256(result)
    return result


def _score(value: float) -> str:
    return f"{Decimal(str(value)).quantize(Decimal('0.00000000')):.8f}"


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


def _actual_source_bindings(source_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    bindings: list[dict[str, str]] = []
    for row in source_rows:
        query = row.get("query_text")
        prompt_hash = row.get("prompt_text_sha256")
        if not isinstance(query, str) or not query or not isinstance(prompt_hash, str):
            raise ValueError("source binding requires prompt text and SHA-256")
        if hashlib.sha256(query.encode("utf-8")).hexdigest() != prompt_hash:
            raise ValueError("source binding prompt SHA-256 mismatch")
        source_record_id = row.get("source_record_id")
        exact_bytes_sha256 = row.get("source_record_exact_bytes_sha256")
        if not isinstance(source_record_id, str) or not isinstance(
            exact_bytes_sha256, str
        ):
            raise ValueError("source binding fields are invalid")
        binding: dict[str, str] = {
            "task_id": row["task_id"],
            "source_record_id": source_record_id,
            "source_record_exact_bytes_sha256": exact_bytes_sha256,
            "prompt_sha256": prompt_hash,
            "positive_skill_id": row["positive_skill_id"],
            "split": row["split"],
            "source_role": row["source_role"],
        }
        if not all(
            _HEX_SHA256.fullmatch(value)
            for key, value in binding.items()
            if key in {"source_record_exact_bytes_sha256", "prompt_sha256"}
        ):
            raise ValueError("source binding fields are invalid")
        if any(
            not isinstance(binding[key], str) or not binding[key]
            for key in ("task_id", "source_record_id", "positive_skill_id")
        ):
            raise ValueError("source binding fields are invalid")
        if binding["split"] != "train" or binding["source_role"] != "POSITIVE":
            raise ValueError("source binding must be train POSITIVE")
        bindings.append(binding)
    source_ids = [binding["source_record_id"] for binding in bindings]
    task_ids = [binding["task_id"] for binding in bindings]
    if source_ids != sorted(source_ids) or len(set(source_ids)) != len(source_ids):
        raise ValueError("source bindings must use unique canonical order")
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("source bindings must use unique task identities")
    return bindings


def _actual_skill_bindings(skills: list[dict[str, Any]]) -> list[dict[str, str]]:
    bindings = [
        {
            "skill_id": skill["id"],
            "skill_record_sha256": canonical_sha256(skill),
            "skill_text_sha256": canonical_sha256(_skill_text(skill)),
        }
        for skill in skills
    ]
    skill_ids = [binding["skill_id"] for binding in bindings]
    if skill_ids != sorted(skill_ids) or len(set(skill_ids)) != len(skill_ids):
        raise ValueError("skill bindings must use unique canonical order")
    return bindings


def _validate_model_file_manifest(manifest: object) -> list[dict[str, Any]]:
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("model file manifest must be a non-empty list")
    paths: list[str] = []
    for record in manifest:
        if not isinstance(record, dict) or set(record) != _MODEL_FILE_FIELDS:
            raise ValueError(
                "model file manifest records require path, size, and sha256"
            )
        path = record.get("path")
        size = record.get("size")
        sha256 = record.get("sha256")
        if not isinstance(path, str) or not path or "\\" in path:
            raise ValueError("model file manifest path must be relative POSIX")
        parsed = PurePosixPath(path)
        if (
            parsed.is_absolute()
            or any(part in {"", ".", ".."} for part in parsed.parts)
            or str(parsed) != path
        ):
            raise ValueError("model file manifest path must be relative POSIX")
        if type(size) is not int or size < 0:
            raise ValueError("model file manifest size must be a nonnegative integer")
        if not isinstance(sha256, str) or not _HEX_SHA256.fullmatch(sha256):
            raise ValueError("model file manifest SHA-256 must be lowercase 64-hex")
        paths.append(path)
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        raise ValueError(
            "model file manifest paths must be unique and canonically sorted"
        )
    return manifest


def _validate_scorer_provenance(encoder: Encoder) -> None:
    expected: tuple[tuple[str, object], ...] = (
        ("model_id", MODEL_ID),
        ("model_revision", MODEL_REVISION),
        ("device", "cpu"),
        ("thread_count", 1),
        ("normalize_embeddings", True),
    )
    if any(
        getattr(encoder, field, None) != value
        or type(getattr(encoder, field, None)) is not type(value)
        for field, value in expected
    ):
        raise ValueError("scorer provenance does not match the frozen CPU contract")


def _validate_vectors(
    skill_vectors: list[list[float]], prompt_vectors: list[list[float]]
) -> None:
    if len(skill_vectors) != 16 or len(prompt_vectors) != 64:
        raise ValueError("encoder vectors have an unexpected count")
    vectors = [*skill_vectors, *prompt_vectors]
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1 or not dimensions or next(iter(dimensions)) == 0:
        raise ValueError("encoder vectors must have one non-zero dimension")
    for vector in vectors:
        if (
            not all(isinstance(value, (int, float)) for value in vector)
            or not all(math.isfinite(float(value)) for value in vector)
            or not any(float(value) != 0.0 for value in vector)
        ):
            raise ValueError("encoder vectors must be finite and non-zero")
        norm = math.sqrt(sum(float(value) ** 2 for value in vector))
        if abs(norm - 1.0) > 1e-5:
            raise ValueError("encoder vectors must be unit-normalized")


def mine_confusions(
    *,
    source_rows: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    encoder: Encoder,
    model_file_manifest: list[dict[str, Any]],
    source_snapshot_id: str,
    source_candidates_sha256: str,
    source_manifest_sha256: str,
    skill_index_sha256: str,
    expected_source_bindings: list[dict[str, str]],
    expected_skill_bindings: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(source_rows) != 64 or any(
        row.get("split") != "train" or row.get("source_role") != "POSITIVE"
        for row in source_rows
    ):
        raise ValueError("mining requires exactly 64 train POSITIVE rows")
    if len(skills) != 16 or len({skill.get("id") for skill in skills}) != 16:
        raise ValueError("mining requires exactly 16 frozen skills")
    if (
        source_snapshot_id != SOURCE_SNAPSHOT_ID
        or source_candidates_sha256 != SOURCE_CANDIDATES_SHA256
        or source_manifest_sha256 != SOURCE_MANIFEST_SHA256
    ):
        raise ValueError("frozen source lineage mismatch")
    if skill_index_sha256 != SKILL_INDEX_SHA256:
        raise ValueError("frozen skill index SHA-256 mismatch")
    _validate_scorer_provenance(encoder)
    validated_model_file_manifest = _validate_model_file_manifest(model_file_manifest)

    source_bindings = _actual_source_bindings(source_rows)
    if source_bindings != expected_source_bindings:
        raise ValueError("source binding does not match the frozen expectation")
    skill_bindings = _actual_skill_bindings(skills)
    if skill_bindings != expected_skill_bindings:
        raise ValueError("skill binding does not match the frozen expectation")
    skill_vectors = encoder.encode([_skill_text(skill) for skill in skills])
    prompt_vectors = encoder.encode([row["query_text"] for row in source_rows])
    _validate_vectors(skill_vectors, prompt_vectors)

    model_file_manifest_sha256 = canonical_sha256(validated_model_file_manifest)
    source_bindings_sha256 = canonical_sha256(source_bindings)
    skill_bindings_sha256 = canonical_sha256(skill_bindings)
    mined: list[dict[str, Any]] = []
    for source, prompt_vector in zip(source_rows, prompt_vectors, strict=True):
        ranked = sorted(
            (
                {
                    "skill_id": skill["id"],
                    "score": _score(
                        sum(
                            float(left) * float(right)
                            for left, right in zip(
                                prompt_vector, skill_vector, strict=True
                            )
                        )
                    ),
                }
                for skill, skill_vector in zip(skills, skill_vectors, strict=True)
            ),
            key=lambda item: (-Decimal(item["score"]), item["skill_id"]),
        )
        gold_id = source["positive_skill_id"]
        gold_rank = next(
            index
            for index, item in enumerate(ranked, start=1)
            if item["skill_id"] == gold_id
        )
        non_gold = [item for item in ranked if item["skill_id"] != gold_id]
        candidate = non_gold[0]
        candidate_rank = ranked.index(candidate) + 1
        margin = Decimal(ranked[gold_rank - 1]["score"]) - Decimal(candidate["score"])
        mined.append(
            with_row_sha256(
                {
                    "schema_version": "router-v2-confusion-mining-row-v1",
                    "task_id": source["task_id"],
                    "source_record_id": source["source_record_id"],
                    "source_record_exact_bytes_sha256": source[
                        "source_record_exact_bytes_sha256"
                    ],
                    "gold_skill_id": gold_id,
                    "prompt_sha256": source["prompt_text_sha256"],
                    "scores": ranked,
                    "gold_rank": gold_rank,
                    "top_3_non_gold": non_gold[:3],
                    "candidate_skill_id": candidate["skill_id"],
                    "candidate_rank": candidate_rank,
                    "score_margin": f"{margin.quantize(Decimal('0.00000000')):.8f}",
                    "baseline_hard": candidate_rank <= 5 or margin <= Decimal("0.05"),
                    "model_id": MODEL_ID,
                    "model_revision": MODEL_REVISION,
                    "model_file_manifest_sha256": model_file_manifest_sha256,
                    "source_snapshot_id": source_snapshot_id,
                    "source_candidates_sha256": source_candidates_sha256,
                    "source_manifest_sha256": source_manifest_sha256,
                    "source_bindings_sha256": source_bindings_sha256,
                    "skill_index_sha256": skill_index_sha256,
                    "skill_bindings_sha256": skill_bindings_sha256,
                }
            )
        )

    manifest = {
        "schema_version": "router-v2-confusion-mining-manifest-v1",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "device": "cpu",
        "thread_count": 1,
        "normalize_embeddings": True,
        "model_file_manifest": validated_model_file_manifest,
        "model_file_manifest_sha256": model_file_manifest_sha256,
        "source_snapshot_id": source_snapshot_id,
        "source_candidates_sha256": source_candidates_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "source_bindings": source_bindings,
        "source_bindings_sha256": source_bindings_sha256,
        "skill_index_sha256": skill_index_sha256,
        "skill_bindings": skill_bindings,
        "skill_bindings_sha256": skill_bindings_sha256,
        "row_count": len(mined),
        "rows_sha256": canonical_sha256(mined),
    }
    return mined, manifest


def _validate_score_rows(row: dict[str, Any], expected_skill_ids: set[str]) -> None:
    scores = row.get("scores")
    if not isinstance(scores, list) or len(scores) != 16:
        raise ValueError("each mining row must contain exactly 16 scores")
    if any(
        not isinstance(item, dict)
        or set(item) != {"skill_id", "score"}
        or not isinstance(item["skill_id"], str)
        or not isinstance(item["score"], str)
        for item in scores
    ):
        raise ValueError("score entries have invalid fields")
    if len({item["skill_id"] for item in scores}) != 16:
        raise ValueError("each mining row must contain exactly 16 unique skill scores")
    if {item["skill_id"] for item in scores} != expected_skill_ids:
        raise ValueError("score skill identities do not match frozen skill bindings")
    if any(not _EIGHT_DECIMAL.fullmatch(item["score"]) for item in scores):
        raise ValueError("scores must use eight-decimal quantization")
    try:
        expected_ranked = sorted(
            scores, key=lambda item: (-Decimal(item["score"]), item["skill_id"])
        )
    except InvalidOperation as exc:
        raise ValueError("scores must use finite eight-decimal values") from exc
    if scores != expected_ranked:
        raise ValueError("score ranking mismatch")

    gold_id = row.get("gold_skill_id")
    candidate_id = row.get("candidate_skill_id")
    gold_rank = next(
        (index for index, item in enumerate(scores, 1) if item["skill_id"] == gold_id),
        None,
    )
    non_gold = [item for item in scores if item["skill_id"] != gold_id]
    if gold_rank is None:
        raise ValueError("gold skill is absent from scores")
    if row.get("gold_rank") != gold_rank:
        raise ValueError("gold rank mismatch")
    if row.get("top_3_non_gold") != non_gold[:3]:
        raise ValueError("top-three non-gold scores mismatch")
    if not non_gold or candidate_id != non_gold[0]["skill_id"]:
        raise ValueError("candidate skill must be the top non-gold score")
    candidate_rank = next(
        index
        for index, item in enumerate(scores, 1)
        if item["skill_id"] == candidate_id
    )
    if row.get("candidate_rank") != candidate_rank:
        raise ValueError("candidate rank mismatch")
    gold_score = Decimal(scores[gold_rank - 1]["score"])
    candidate_score = Decimal(scores[candidate_rank - 1]["score"])
    expected_margin = (gold_score - candidate_score).quantize(Decimal("0.00000000"))
    if row.get("score_margin") != f"{expected_margin:.8f}":
        raise ValueError("score margin mismatch")
    expected_hard = candidate_rank <= 5 or expected_margin <= Decimal("0.05")
    if row.get("baseline_hard") is not expected_hard:
        raise ValueError("baseline-hard classification mismatch")


def _validate_source_binding_list(value: object, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 64:
        raise ValueError(f"{label} source bindings must contain exactly 64 rows")
    for binding in value:
        if not isinstance(binding, dict) or set(binding) != _SOURCE_BINDING_FIELDS:
            raise ValueError(f"{label} source binding fields are invalid")
        if any(
            not isinstance(binding.get(field), str) or not binding[field]
            for field in _SOURCE_BINDING_FIELDS
        ):
            raise ValueError(f"{label} source binding values are invalid")
        if binding["split"] != "train" or binding["source_role"] != "POSITIVE":
            raise ValueError(f"{label} source binding must be train POSITIVE")
        for field in ("source_record_exact_bytes_sha256", "prompt_sha256"):
            if not _HEX_SHA256.fullmatch(binding[field]):
                raise ValueError(f"{label} source binding SHA-256 is invalid")
        expected_id = f"{binding['task_id']}:positive:{binding['positive_skill_id']}"
        if binding["source_record_id"] != expected_id:
            raise ValueError(f"{label} source binding canonical positive id mismatch")
    source_ids = [binding["source_record_id"] for binding in value]
    task_ids = [binding["task_id"] for binding in value]
    if (
        source_ids != sorted(source_ids)
        or len(set(source_ids)) != 64
        or len(set(task_ids)) != 64
    ):
        raise ValueError(f"{label} source bindings are not unique and ordered")
    return value


def _validate_skill_binding_list(value: object, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 16:
        raise ValueError(f"{label} skill bindings must contain exactly 16 rows")
    for binding in value:
        if not isinstance(binding, dict) or set(binding) != _SKILL_BINDING_FIELDS:
            raise ValueError(f"{label} skill binding fields are invalid")
        skill_id = binding.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id:
            raise ValueError(f"{label} skill binding identity is invalid")
        for field in ("skill_record_sha256", "skill_text_sha256"):
            digest = binding.get(field)
            if not isinstance(digest, str) or not _HEX_SHA256.fullmatch(digest):
                raise ValueError(f"{label} skill binding SHA-256 is invalid")
    skill_ids = [binding["skill_id"] for binding in value]
    if skill_ids != sorted(skill_ids) or len(set(skill_ids)) != 16:
        raise ValueError(f"{label} skill bindings are not unique and ordered")
    return value


def validate_mining_bundle(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    expected_source_bindings: list[dict[str, str]],
    expected_skill_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    if set(manifest) != _MINING_MANIFEST_FIELDS:
        raise ValueError("mining manifest fields do not match the exact schema")
    if manifest.get("schema_version") != "router-v2-confusion-mining-manifest-v1":
        raise ValueError("mining manifest schema version mismatch")
    if len(rows) != 64 or manifest.get("row_count") != 64:
        raise ValueError("mining bundle must contain exactly 64 rows")
    expected_manifest = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "device": "cpu",
        "thread_count": 1,
        "normalize_embeddings": True,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_candidates_sha256": SOURCE_CANDIDATES_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "skill_index_sha256": SKILL_INDEX_SHA256,
    }
    for field, expected in expected_manifest.items():
        if manifest.get(field) != expected or type(manifest.get(field)) is not type(
            expected
        ):
            label = "skill index SHA-256" if field == "skill_index_sha256" else field
            raise ValueError(f"mining manifest {label} mismatch")
    model_file_manifest = _validate_model_file_manifest(
        manifest.get("model_file_manifest")
    )
    if manifest.get("model_file_manifest_sha256") != canonical_sha256(
        model_file_manifest
    ):
        raise ValueError("model file manifest SHA-256 mismatch")

    source_bindings = _validate_source_binding_list(
        manifest.get("source_bindings"), label="mining manifest"
    )
    trusted_source_bindings = _validate_source_binding_list(
        expected_source_bindings, label="expected"
    )
    if source_bindings != trusted_source_bindings:
        raise ValueError("mining manifest does not match expected source bindings")
    if manifest.get("source_bindings_sha256") != canonical_sha256(source_bindings):
        raise ValueError("source bindings SHA-256 mismatch")

    skill_bindings = _validate_skill_binding_list(
        manifest.get("skill_bindings"), label="mining manifest"
    )
    trusted_skill_bindings = _validate_skill_binding_list(
        expected_skill_bindings, label="expected"
    )
    if skill_bindings != trusted_skill_bindings:
        raise ValueError("mining manifest does not match expected skill bindings")
    skill_ids = [binding["skill_id"] for binding in skill_bindings]
    if manifest.get("skill_bindings_sha256") != canonical_sha256(skill_bindings):
        raise ValueError("skill bindings SHA-256 mismatch")

    expected_skill_ids = set(skill_ids)
    for row, source_binding in zip(rows, source_bindings, strict=True):
        if set(row) != _MINING_ROW_FIELDS:
            raise ValueError("mining row fields do not match the exact schema")
        if row.get("schema_version") != "router-v2-confusion-mining-row-v1":
            raise ValueError("mining row schema version mismatch")
        _validate_score_rows(row, expected_skill_ids)
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("mining row task id is invalid")
        expected_source_fields = {
            "task_id": source_binding["task_id"],
            "source_record_id": source_binding["source_record_id"],
            "source_record_exact_bytes_sha256": source_binding[
                "source_record_exact_bytes_sha256"
            ],
            "prompt_sha256": source_binding["prompt_sha256"],
            "gold_skill_id": source_binding["positive_skill_id"],
        }
        if any(
            row.get(field) != expected
            for field, expected in expected_source_fields.items()
        ):
            raise ValueError("mining row source binding mismatch")
        for field in (
            "model_id",
            "model_revision",
            "source_snapshot_id",
            "source_candidates_sha256",
            "source_manifest_sha256",
            "source_bindings_sha256",
            "skill_index_sha256",
            "skill_bindings_sha256",
            "model_file_manifest_sha256",
        ):
            if row.get(field) != manifest.get(field):
                raise ValueError(f"mining row {field} lineage mismatch")
        if with_row_sha256(row) != row:
            raise ValueError("mining row SHA-256 mismatch")
    if manifest.get("rows_sha256") != canonical_sha256(rows):
        raise ValueError("mining rows SHA-256 mismatch")
    return {"validation_status": "PASS"}


def _legacy_pr37_row_hash(row: dict[str, Any]) -> str:
    unhashed = {key: value for key, value in row.items() if key != "row_sha256"}
    payload = (
        json.dumps(unhashed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_jsonl_sha256(rows: list[dict[str, Any]]) -> str:
    payload = b"".join(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        for row in rows
    )
    return hashlib.sha256(payload).hexdigest()


def _validate_prior_scores(scores: object) -> list[dict[str, Any]]:
    if not isinstance(scores, list) or len(scores) != 16:
        raise ValueError("prior mining scores must contain exactly 16 rows")
    if any(
        not isinstance(item, dict)
        or set(item) != {"skill_id", "score"}
        or not isinstance(item.get("skill_id"), str)
        or not item["skill_id"]
        or not isinstance(item.get("score"), str)
        or not _EIGHT_DECIMAL.fullmatch(item["score"])
        for item in scores
    ):
        raise ValueError("prior mining scores must use finite eight-decimal values")
    score_ids = [item["skill_id"] for item in scores]
    if len(set(score_ids)) != 16:
        raise ValueError("prior mining scores must contain unique skill identities")
    expected = sorted(
        scores, key=lambda item: (-Decimal(item["score"]), item["skill_id"])
    )
    if scores != expected:
        raise ValueError("prior mining scores must be canonically sorted")
    return scores


def filter_prior_model_review(
    *,
    mining_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    adjudication_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(adjudication_rows) != 192:
        raise ValueError("PR #37 filter requires the complete 192-row adjudication")
    if _canonical_jsonl_sha256(adjudication_rows) != PR37_ADJUDICATION_SHA256:
        raise ValueError("PR #37 full adjudication SHA-256 mismatch")
    hard_negative_adjudications = [
        row
        for row in adjudication_rows
        if row.get("source_role") == "HARD_NEGATIVE_CANDIDATE"
    ]
    if not (
        len(mining_rows) == len(source_rows) == len(hard_negative_adjudications) == 64
    ):
        raise ValueError("PR #37 filter requires exactly 64 train candidates")

    retained: list[str] = []
    disputed: list[str] = []
    supported_count = 0
    disputed_count = 0
    seen: set[str] = set()
    for mined, source, adjudication in zip(
        mining_rows, source_rows, hard_negative_adjudications, strict=True
    ):
        source_record_id = source.get("source_record_id")
        if not isinstance(source_record_id, str) or not source_record_id:
            raise ValueError("prior review source identity is invalid")
        if source_record_id in seen:
            raise ValueError("duplicate PR #37 source record")
        seen.add(source_record_id)
        task_id = source.get("task_id")
        candidate_id = source.get("skill_id")
        gold_id = source.get("positive_skill_id")
        if not all(
            isinstance(value, str) and value
            for value in (task_id, candidate_id, gold_id)
        ):
            raise ValueError("prior review skill identity is invalid")
        expected_hard_negative_id = f"{task_id}:hard-negative-candidate:{candidate_id}"
        if source_record_id != expected_hard_negative_id:
            raise ValueError(
                "prior review canonical hard-negative source identity mismatch"
            )
        if (
            source.get("split") != "train"
            or source.get("source_role") != "HARD_NEGATIVE_CANDIDATE"
            or mined.get("task_id") != task_id
            or mined.get("gold_skill_id") != gold_id
            or adjudication.get("source_record_id") != source_record_id
            or adjudication.get("source_role") != "HARD_NEGATIVE_CANDIDATE"
        ):
            raise ValueError("prior review identity mismatch")
        if _canonical_jsonl_sha256([source]) != adjudication.get(
            "source_record_exact_bytes_sha256"
        ):
            raise ValueError("PR #37 source row exact-bytes SHA-256 mismatch")
        if with_row_sha256(mined) != mined:
            raise ValueError("prior mining row SHA-256 mismatch")
        _validate_truth(adjudication)
        opinion = adjudication.get("adjudicated_model_opinion")
        if opinion not in _PR37_OPINIONS:
            raise ValueError("PR #37 opinion must be supported or disputed")
        if adjudication.get("row_sha256") != _legacy_pr37_row_hash(adjudication):
            raise ValueError("PR #37 adjudication row SHA-256 mismatch")

        expected_positive_source_id = f"{task_id}:positive:{gold_id}"
        if mined.get("source_record_id") != expected_positive_source_id:
            raise ValueError(
                "prior mining row canonical positive source identity mismatch"
            )
        scores = _validate_prior_scores(mined.get("scores"))
        score_ids = [item["skill_id"] for item in scores]
        try:
            candidate_rank = score_ids.index(candidate_id) + 1
            gold_rank = score_ids.index(gold_id) + 1
            candidate_score = Decimal(scores[candidate_rank - 1]["score"])
            gold_score = Decimal(scores[gold_rank - 1]["score"])
        except (ValueError, KeyError, InvalidOperation) as exc:
            raise ValueError("prior candidate must be found in full scores") from exc
        margin = gold_score - candidate_score

        if opinion == "HARD_NEGATIVE_ROLE_SUPPORTED":
            supported_count += 1
            if candidate_rank <= 5 or margin <= Decimal("0.05"):
                retained.append(source_record_id)
        else:
            disputed_count += 1
            disputed.append(source_record_id)
    if supported_count != 35 or disputed_count != 29:
        raise ValueError(
            "PR #37 opinion counts must be exactly 35 supported and 29 disputed"
        )

    report: dict[str, Any] = {
        **TRUTH_FIELDS,
        "adjudication_sha256": PR37_ADJUDICATION_SHA256,
        "mining_rows_sha256": canonical_sha256(mining_rows),
        "source_rows_sha256": canonical_sha256(source_rows),
        "adjudication_rows_sha256": canonical_sha256(adjudication_rows),
        "supported_count": supported_count,
        "disputed_count": disputed_count,
        "retained_count": len(retained),
        "retained_source_record_ids": retained,
        "excluded_disputed_source_record_ids": disputed,
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def _validate_truth(row: dict[str, Any]) -> None:
    for key, expected in TRUTH_FIELDS.items():
        if row.get(key) != expected or type(row.get(key)) is not type(expected):
            raise ValueError(f"truth field {key} mismatch")


def _validate_review_row(
    row: dict[str, Any], *, expected_fields: set[str], expected_schema: str
) -> None:
    forbidden = sorted(set(row) & _FORBIDDEN_REVIEW_FIELDS)
    if forbidden:
        raise ValueError(f"review row contains forbidden field {forbidden[0]}")
    if set(row) != expected_fields:
        raise ValueError("review row fields do not match the exact schema")
    if row.get("schema_version") != expected_schema:
        raise ValueError("review row schema version mismatch")
    _validate_truth(row)
    if row.get("usage") not in _ALLOWED_USAGES:
        raise ValueError("review row usage is invalid")
    candidate_id = row.get("candidate_id")
    candidate_sha = row.get("candidate_sha256")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate identity must be explicit")
    if not isinstance(candidate_sha, str) or not _HEX_SHA256.fullmatch(candidate_sha):
        raise ValueError("candidate SHA-256 is invalid")
    rationale = row.get("rationale")
    if (
        not isinstance(rationale, str)
        or not rationale.strip()
        or len(rationale) > RATIONALE_MAX_CHARS
    ):
        raise ValueError("rationale must be non-empty and bounded")
    string_values = [
        value.casefold() for value in row.values() if isinstance(value, str)
    ]
    if any(claim in value for value in string_values for claim in _FORBIDDEN_CLAIMS):
        raise ValueError("rationale contains a forbidden claim")
    if with_row_sha256(row) != row:
        raise ValueError("review row SHA-256 mismatch")


def validate_new_candidate_review(
    pass_1: list[dict[str, Any]],
    pass_2: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
) -> dict[str, Any]:
    count = len(pass_1)
    if count == 0 or len(pass_2) != count or len(adjudications) != count:
        raise ValueError("two passes and adjudication must cover identical candidates")

    for row in pass_1:
        _validate_review_row(
            row, expected_fields=_PASS_FIELDS, expected_schema=_PASS_SCHEMA
        )
        if row.get("pass_id") != "MODEL_PASS_1":
            raise ValueError("pass 1 identity mismatch")
        if row.get("model_opinion") not in _ALLOWED_OPINIONS:
            raise ValueError("pass 1 opinion is invalid")
    for row in pass_2:
        _validate_review_row(
            row, expected_fields=_PASS_FIELDS, expected_schema=_PASS_SCHEMA
        )
        if row.get("pass_id") != "MODEL_PASS_2":
            raise ValueError("pass 2 identity mismatch")
        if row.get("model_opinion") not in _ALLOWED_OPINIONS:
            raise ValueError("pass 2 opinion is invalid")
    for row in adjudications:
        _validate_review_row(
            row,
            expected_fields=_ADJUDICATION_FIELDS,
            expected_schema=_ADJUDICATION_SCHEMA,
        )
        if (
            row.get("pass_1_model_opinion") not in _ALLOWED_OPINIONS
            or row.get("pass_2_model_opinion") not in _ALLOWED_OPINIONS
        ):
            raise ValueError("adjudication pass opinion is invalid")
        if row.get("adjudicated_model_opinion") not in _ALLOWED_OPINIONS:
            raise ValueError("adjudicated opinion is invalid")

    identity_lists = [
        [row["candidate_id"] for row in rows]
        for rows in (pass_1, pass_2, adjudications)
    ]
    if any(identities != sorted(identities) for identities in identity_lists):
        raise ValueError("review rows must use canonical candidate order")
    if any(len(set(identities)) != count for identities in identity_lists):
        raise ValueError("review rows contain duplicate candidate identities")
    if not identity_lists[0] == identity_lists[1] == identity_lists[2]:
        raise ValueError("candidate identity mismatch")

    run_1 = {row.get("pass_run_id") for row in pass_1}
    run_2 = {row.get("pass_run_id") for row in pass_2}
    if (
        any(
            not isinstance(run_id, str) or not run_id.strip()
            for run_id in run_1 | run_2
        )
        or len(run_1) != 1
        or len(run_2) != 1
        or run_1 == run_2
    ):
        raise ValueError("model passes require non-empty distinct pass run identities")

    for first, second, adjudication in zip(pass_1, pass_2, adjudications, strict=True):
        identity = (first["candidate_sha256"], first["usage"])
        if identity != (second["candidate_sha256"], second["usage"]) or identity != (
            adjudication["candidate_sha256"],
            adjudication["usage"],
        ):
            raise ValueError("candidate identity mismatch")
        if (
            first.get("pass_isolation") != "OTHER_PASS_OUTPUT_NOT_PROVIDED"
            or second.get("pass_isolation") != "OTHER_PASS_OUTPUT_NOT_PROVIDED"
        ):
            raise ValueError("pass isolation mismatch")
        if (
            adjudication.get("pass_1_row_sha256") != first["row_sha256"]
            or adjudication.get("pass_2_row_sha256") != second["row_sha256"]
        ):
            raise ValueError("adjudication pass-row hash mismatch")
        if adjudication.get("pass_1_model_opinion") != first.get(
            "model_opinion"
        ) or adjudication.get("pass_2_model_opinion") != second.get("model_opinion"):
            raise ValueError("adjudication opinion mismatch")
        expected_agreement = first["model_opinion"] == second["model_opinion"]
        if adjudication.get("opinions_agree") is not expected_agreement:
            raise ValueError("adjudication agreement mismatch")
        if expected_agreement and adjudication.get(
            "adjudicated_model_opinion"
        ) != first.get("model_opinion"):
            raise ValueError("adjudicated opinion disagrees with agreeing passes")
    return {**TRUTH_FIELDS, "candidate_count": count, "validation_status": "PASS"}
