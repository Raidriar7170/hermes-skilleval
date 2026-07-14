from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from hermes_skilleval.router_v2_training_pilot import (
    ADJUDICATION_PROMPT_ID,
    ADJUDICATION_PROMPT_SHA256,
    MODEL_ID,
    MODEL_REVISION,
    PR37_ADJUDICATION_SHA256,
    RATIONALE_MAX_CHARS,
    REVIEW_MODEL_ID,
    REVIEW_MODEL_PROVIDER,
    REVIEW_MODEL_SNAPSHOT,
    REVIEW_PROMPT_ID,
    REVIEW_PROMPT_SHA256,
    REVIEW_RUBRIC_ID,
    REVIEW_RUBRIC_SHA256,
    SKILL_INDEX_SHA256,
    SOURCE_CANDIDATES_SHA256,
    SOURCE_MANIFEST_SHA256,
    SOURCE_SNAPSHOT_ID,
    TRUTH_FIELDS,
    canonical_sha256,
    filter_prior_model_review,
    mine_confusions,
    validate_mining_bundle,
    validate_new_candidate_review,
    with_row_sha256,
)


ROOT = Path(__file__).parents[1]


class FakeEncoder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []
        self.model_id = MODEL_ID
        self.model_revision = MODEL_REVISION
        self.device = "cpu"
        self.thread_count = 1
        self.normalize_embeddings = True

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors[text] for text in texts]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _prompt_sha256(prompt: str) -> str:
    return _sha256(prompt.encode())


def _fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]], FakeEncoder]:
    skills: list[dict[str, Any]] = [
        {
            "id": f"skill-{index:02d}",
            "name": f"Skill {index:02d}",
            "category": "fixture",
            "description": f"Description {index:02d}",
            "trigger_terms": [f"term-{index:02d}"],
            "body": f"Body {index:02d}",
        }
        for index in range(16)
    ]
    rows = []
    for index in range(64):
        prompt = f"query-{index:02d}"
        rows.append(
            {
                "split": "train",
                "source_role": "POSITIVE",
                "task_id": f"task-{index:02d}",
                "source_record_id": f"task-{index:02d}:positive:skill-00",
                "positive_skill_id": "skill-00",
                "skill_id": "skill-00",
                "query_text": prompt,
                "prompt_text_sha256": _prompt_sha256(prompt),
                "source_record_exact_bytes_sha256": f"{index + 1:064x}",
            }
        )

    skill_texts = [
        " ".join(
            [
                skill["id"].replace("-", " "),
                skill["name"],
                skill["category"],
                skill["description"],
                " ".join(skill["trigger_terms"]),
                skill["body"],
            ]
        )
        for skill in skills
    ]
    vectors: dict[str, list[float]] = {}
    for index, text in enumerate(skill_texts):
        vector = [0.0] * 16
        vector[index] = 1.0
        vectors[text] = vector
    for index, row in enumerate(rows):
        vector = [0.0] * 16
        vector[0] = 0.9
        vector[1] = 0.3
        vector[2] = 0.3
        vector[3] = 0.1
        vectors[row["query_text"]] = vector
    return rows, skills, FakeEncoder(vectors)


def _source_bindings(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
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
        for row in rows
    ]


def _skill_bindings(skills: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "skill_id": skill["id"],
            "skill_record_sha256": canonical_sha256(skill),
            "skill_text_sha256": canonical_sha256(
                " ".join(
                    [
                        skill["id"].replace("-", " "),
                        skill["name"],
                        skill["category"],
                        skill["description"],
                        " ".join(skill["trigger_terms"]),
                        skill["body"],
                    ]
                )
            ),
        }
        for skill in skills
    ]


def _mine_args(
    rows: list[dict[str, Any]], skills: list[dict[str, Any]], encoder: FakeEncoder
) -> dict[str, Any]:
    return {
        "source_rows": rows,
        "skills": skills,
        "encoder": encoder,
        "model_file_manifest": [
            {"path": "model.safetensors", "size": 1, "sha256": "a" * 64}
        ],
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_candidates_sha256": SOURCE_CANDIDATES_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "skill_index_sha256": SKILL_INDEX_SHA256,
        "expected_source_bindings": _source_bindings(rows),
        "expected_skill_bindings": _skill_bindings(skills),
    }


def _mine() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, skills, encoder = _fixture()
    return mine_confusions(**_mine_args(rows, skills, encoder))


def _validate_mined(
    rows: list[dict[str, Any]], manifest: dict[str, Any]
) -> dict[str, Any]:
    source_rows, skills, _ = _fixture()
    return validate_mining_bundle(
        rows,
        manifest,
        expected_source_bindings=_source_bindings(source_rows),
        expected_skill_bindings=_skill_bindings(skills),
    )


def test_miner_is_frozen_train_only_and_records_complete_quantized_lineage() -> None:
    rows, skills, encoder = _fixture()
    mined, manifest = mine_confusions(**_mine_args(rows, skills, encoder))

    assert MODEL_ID == "sentence-transformers/all-MiniLM-L6-v2"
    assert MODEL_REVISION == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    assert len(mined) == 64
    assert len(encoder.calls) == 2
    first = mined[0]
    assert len(first["scores"]) == 16
    assert first["scores"][0] == {"skill_id": "skill-00", "score": "0.90000000"}
    assert first["scores"][1:3] == [
        {"skill_id": "skill-01", "score": "0.30000000"},
        {"skill_id": "skill-02", "score": "0.30000000"},
    ]
    assert first["gold_rank"] == 1
    assert len(first["top_3_non_gold"]) == 3
    assert first["candidate_skill_id"] == "skill-01"
    assert first["candidate_rank"] == 2
    assert first["score_margin"] == "0.60000000"
    assert first["baseline_hard"] is True
    assert first["prompt_sha256"] == _prompt_sha256("query-00")
    assert first["skill_index_sha256"] == SKILL_INDEX_SHA256
    assert first["model_id"] == MODEL_ID
    assert first["model_revision"] == MODEL_REVISION
    assert first["source_bindings_sha256"] == manifest["source_bindings_sha256"]
    assert first["skill_bindings_sha256"] == manifest["skill_bindings_sha256"]
    assert first["model_file_manifest_sha256"] == manifest["model_file_manifest_sha256"]
    assert manifest["source_bindings"] == _source_bindings(rows)
    assert manifest["skill_bindings"] == _skill_bindings(skills)
    assert _validate_mined(mined, manifest)["validation_status"] == "PASS"


def test_miner_rejects_noncanonical_model_file_manifest_before_encoder_use() -> None:
    invalid_manifests: list[list[dict[str, Any]]] = [
        [],
        [{"path": "model.safetensors", "size": 1, "sha256": "a" * 64, "x": 1}],
        [{"path": "/model.safetensors", "size": 1, "sha256": "a" * 64}],
        [{"path": "../model.safetensors", "size": 1, "sha256": "a" * 64}],
        [{"path": "model\\weights.bin", "size": 1, "sha256": "a" * 64}],
        [{"path": "model.safetensors", "size": -1, "sha256": "a" * 64}],
        [{"path": "model.safetensors", "size": True, "sha256": "a" * 64}],
        [{"path": "model.safetensors", "size": 1, "sha256": "A" * 64}],
        [
            {"path": "z.bin", "size": 1, "sha256": "a" * 64},
            {"path": "a.bin", "size": 1, "sha256": "b" * 64},
        ],
    ]
    for model_file_manifest in invalid_manifests:
        rows, skills, encoder = _fixture()
        args = _mine_args(rows, skills, encoder)
        args["model_file_manifest"] = model_file_manifest
        with pytest.raises(ValueError, match="model file manifest"):
            mine_confusions(**args)
        assert encoder.calls == []


@pytest.mark.parametrize(
    "split", ["calibration", "non_blind_test", "Phase16", "blind-v2"]
)
def test_miner_rejects_forbidden_splits_before_encoder_use(split: str) -> None:
    rows, skills, encoder = _fixture()
    rows[0]["split"] = split

    with pytest.raises(ValueError, match="train POSITIVE"):
        mine_confusions(**_mine_args(rows, skills, encoder))

    assert encoder.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_id", "other-model"),
        ("model_revision", "0" * 40),
        ("device", "cuda"),
        ("thread_count", 2),
        ("normalize_embeddings", False),
    ],
)
def test_miner_rejects_unfrozen_scorer_before_encoder_use(
    field: str, value: object
) -> None:
    rows, skills, encoder = _fixture()
    setattr(encoder, field, value)

    with pytest.raises(ValueError, match="scorer provenance"):
        mine_confusions(**_mine_args(rows, skills, encoder))

    assert encoder.calls == []


def test_miner_rejects_drifted_source_or_skill_binding_before_encoder_use() -> None:
    rows, skills, encoder = _fixture()
    source_bindings = _source_bindings(rows)
    source_bindings[0]["prompt_sha256"] = "0" * 64
    args = _mine_args(rows, skills, encoder)
    args["expected_source_bindings"] = source_bindings
    with pytest.raises(ValueError, match="source binding"):
        mine_confusions(**args)
    assert encoder.calls == []

    rows, skills, encoder = _fixture()
    skill_bindings = _skill_bindings(skills)
    skill_bindings[0]["skill_text_sha256"] = "0" * 64
    args = _mine_args(rows, skills, encoder)
    args["expected_skill_bindings"] = skill_bindings
    with pytest.raises(ValueError, match="skill binding"):
        mine_confusions(**args)
    assert encoder.calls == []


def test_mining_validation_fails_closed_on_hash_or_score_drift() -> None:
    rows, manifest = _mine()
    drifted = deepcopy(rows)
    drifted[0]["score_margin"] = "0.05000001"
    drifted[0] = with_row_sha256(drifted[0])
    with pytest.raises(ValueError, match="score margin"):
        _validate_mined(drifted, manifest)

    bad_manifest = {**manifest, "skill_index_sha256": "0" * 64}
    with pytest.raises(ValueError, match="skill index SHA-256"):
        _validate_mined(rows, bad_manifest)


def test_mining_validator_rejects_resigned_valid_looking_binding_drift() -> None:
    rows, manifest = _mine()
    source_drift = deepcopy(manifest)
    source_drift["source_bindings"][0]["source_record_exact_bytes_sha256"] = "f" * 64
    source_drift["source_bindings_sha256"] = canonical_sha256(
        source_drift["source_bindings"]
    )
    with pytest.raises(ValueError, match="expected source bindings"):
        _validate_mined(rows, source_drift)

    skill_drift = deepcopy(manifest)
    skill_drift["skill_bindings"][0]["skill_record_sha256"] = "f" * 64
    skill_drift["skill_bindings_sha256"] = canonical_sha256(
        skill_drift["skill_bindings"]
    )
    with pytest.raises(ValueError, match="expected skill bindings"):
        _validate_mined(rows, skill_drift)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row["scores"].pop(), "exactly 16"),
        (lambda row: row["scores"][0].update(score="0.9000000"), "eight-decimal"),
        (lambda row: row.update(candidate_rank=7), "candidate rank"),
        (lambda row: row.update(gold_rank=7), "gold rank"),
        (lambda row: row.update(top_3_non_gold=[]), "top-three"),
    ],
)
def test_mining_validation_recomputes_all_ranked_fields(
    mutation: Any, message: str
) -> None:
    rows, manifest = _mine()
    drifted = deepcopy(rows)
    mutation(drifted[0])
    drifted[0] = with_row_sha256(drifted[0])
    with pytest.raises(ValueError, match=message):
        _validate_mined(drifted, manifest)


@pytest.mark.parametrize("bad_vector", [[], [float("nan")] * 16, [0.0] * 16])
def test_miner_rejects_invalid_encoder_vectors(bad_vector: list[float]) -> None:
    rows, skills, encoder = _fixture()
    encoder.vectors[rows[0]["query_text"]] = bad_vector
    with pytest.raises(ValueError, match="encoder vectors"):
        mine_confusions(**_mine_args(rows, skills, encoder))


def test_miner_rejects_scaled_non_unit_encoder_vectors() -> None:
    rows, skills, encoder = _fixture()
    prompt = rows[0]["query_text"]
    encoder.vectors[prompt] = [value * 2 for value in encoder.vectors[prompt]]
    with pytest.raises(ValueError, match="unit-normalized"):
        mine_confusions(**_mine_args(rows, skills, encoder))


def _prior_review_fixture() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    source_rows = [
        json.loads(line)
        for line in (ROOT / "data/router-v2-v4/source-candidates.jsonl")
        .read_text()
        .splitlines()
        if json.loads(line)["source_role"] == "HARD_NEGATIVE_CANDIDATE"
        and json.loads(line)["split"] == "train"
    ]
    adjudication_path = (
        ROOT
        / "artifacts/router-v2-v4/model-only-pilot/router-v2-v4-codex-model-only-pilot-001/adjudication.model-opinions.jsonl"
    )
    adjudications = [
        json.loads(line) for line in adjudication_path.read_text().splitlines()
    ]
    mining_rows = []
    for source in source_rows:
        candidate_skill_id = source["skill_id"]
        other_ids = [
            f"fixture-other-{index:02d}"
            for index in range(15)
            if f"fixture-other-{index:02d}"
            not in {source["positive_skill_id"], candidate_skill_id}
        ][:14]
        positive_source_record_id = (
            f"{source['task_id']}:positive:{source['positive_skill_id']}"
        )
        mining_rows.append(
            with_row_sha256(
                {
                    "task_id": source["task_id"],
                    "source_record_id": positive_source_record_id,
                    "gold_skill_id": source["positive_skill_id"],
                    "scores": [
                        {
                            "skill_id": source["positive_skill_id"],
                            "score": "0.90000000",
                        },
                        {"skill_id": other_ids[0], "score": "0.88000000"},
                        {"skill_id": candidate_skill_id, "score": "0.86000000"},
                        *[
                            {
                                "skill_id": skill_id,
                                "score": f"0.{70 - index:02d}000000",
                            }
                            for index, skill_id in enumerate(other_ids[1:])
                        ],
                    ],
                    "candidate_skill_id": candidate_skill_id,
                    "candidate_rank": 99,
                    "score_margin": "9.00000000",
                }
            )
        )
    return mining_rows, source_rows, adjudications


def test_prior_review_filter_keeps_only_supported_baseline_hard_rows() -> None:
    mining_rows, source_rows, adjudications = _prior_review_fixture()
    assert mining_rows[0]["source_record_id"] != source_rows[0]["source_record_id"]

    report = filter_prior_model_review(
        mining_rows=mining_rows,
        source_rows=source_rows,
        adjudication_rows=adjudications,
    )

    assert report["review_mode"] == "MODEL_ONLY_PILOT"
    assert report["adjudication_sha256"] == PR37_ADJUDICATION_SHA256
    assert report["supported_count"] == 35
    assert report["disputed_count"] == 29
    assert report["retained_count"] == 35
    assert not set(report["retained_source_record_ids"]) & set(
        report["excluded_disputed_source_record_ids"]
    )
    assert report["report_sha256"] == canonical_sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )


def test_prior_review_filter_authenticates_full_adjudication_payload() -> None:
    mining_rows, source_rows, adjudications = _prior_review_fixture()
    index = next(
        index
        for index, row in enumerate(adjudications)
        if row["source_role"] == "HARD_NEGATIVE_CANDIDATE"
    )
    adjudications[index]["adjudicated_model_opinion"] = "MODEL_UNCERTAIN"
    unhashed = {
        key: value for key, value in adjudications[index].items() if key != "row_sha256"
    }
    adjudications[index]["row_sha256"] = _sha256(
        (
            json.dumps(
                unhashed,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    )
    with pytest.raises(ValueError, match="full adjudication SHA-256"):
        filter_prior_model_review(
            mining_rows=mining_rows,
            source_rows=source_rows,
            adjudication_rows=adjudications,
        )


def test_prior_review_filter_rejects_forged_positive_source_identity() -> None:
    mining_rows, source_rows, adjudications = _prior_review_fixture()
    mining_rows[0]["source_record_id"] = "forged:positive:identity"
    mining_rows[0] = with_row_sha256(mining_rows[0])
    with pytest.raises(ValueError, match="canonical positive source identity"):
        filter_prior_model_review(
            mining_rows=mining_rows,
            source_rows=source_rows,
            adjudication_rows=adjudications,
        )


def test_prior_review_filter_rejects_hn_identity_or_score_order_drift() -> None:
    mining_rows, source_rows, adjudications = _prior_review_fixture()
    source_rows[0]["skill_id"] = "different-skill"
    with pytest.raises(ValueError, match="canonical hard-negative source identity"):
        filter_prior_model_review(
            mining_rows=mining_rows,
            source_rows=source_rows,
            adjudication_rows=adjudications,
        )

    mining_rows, source_rows, adjudications = _prior_review_fixture()
    mining_rows[0]["scores"][2]["score"] = "0.10000000"
    mining_rows[0] = with_row_sha256(mining_rows[0])
    with pytest.raises(ValueError, match="canonically sorted"):
        filter_prior_model_review(
            mining_rows=mining_rows,
            source_rows=source_rows,
            adjudication_rows=adjudications,
        )


def _candidate_review_rows(
    count: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pass_rows: dict[str, list[dict[str, Any]]] = {}
    for pass_id, run_id in (("MODEL_PASS_1", "run-one"), ("MODEL_PASS_2", "run-two")):
        pass_rows[pass_id] = [
            with_row_sha256(
                {
                    **TRUTH_FIELDS,
                    "schema_version": "router-v2-new-candidate-model-pass-v1",
                    "candidate_id": f"candidate-{index}",
                    "candidate_sha256": f"{index + 1:064x}",
                    "usage": "TRAIN_HARD_NEGATIVE_CANDIDATE",
                    "pass_id": pass_id,
                    "pass_run_id": run_id,
                    "pass_isolation": "OTHER_PASS_OUTPUT_NOT_PROVIDED",
                    "model_provider": REVIEW_MODEL_PROVIDER,
                    "model_id": REVIEW_MODEL_ID,
                    "model_snapshot": REVIEW_MODEL_SNAPSHOT,
                    "review_prompt_id": REVIEW_PROMPT_ID,
                    "review_prompt_sha256": REVIEW_PROMPT_SHA256,
                    "rubric_id": REVIEW_RUBRIC_ID,
                    "rubric_sha256": REVIEW_RUBRIC_SHA256,
                    "model_opinion": "HARD_NEGATIVE_ROLE_SUPPORTED",
                    "rationale": "The candidate is a plausible but wrong skill.",
                }
            )
            for index in range(count)
        ]
    adjudications = [
        with_row_sha256(
            {
                **TRUTH_FIELDS,
                "schema_version": "router-v2-new-candidate-model-adjudication-v1",
                "candidate_id": first["candidate_id"],
                "candidate_sha256": first["candidate_sha256"],
                "usage": first["usage"],
                "adjudicator_model_provider": REVIEW_MODEL_PROVIDER,
                "adjudicator_model_id": REVIEW_MODEL_ID,
                "adjudicator_model_snapshot": REVIEW_MODEL_SNAPSHOT,
                "adjudication_prompt_id": ADJUDICATION_PROMPT_ID,
                "adjudication_prompt_sha256": ADJUDICATION_PROMPT_SHA256,
                "rubric_id": REVIEW_RUBRIC_ID,
                "rubric_sha256": REVIEW_RUBRIC_SHA256,
                "pass_1_row_sha256": first["row_sha256"],
                "pass_2_row_sha256": second["row_sha256"],
                "pass_1_model_opinion": first["model_opinion"],
                "pass_2_model_opinion": second["model_opinion"],
                "opinions_agree": first["model_opinion"] == second["model_opinion"],
                "adjudicated_model_opinion": "HARD_NEGATIVE_ROLE_SUPPORTED",
                "rationale": "Both bounded passes support the hard-negative role.",
            }
        )
        for first, second in zip(
            pass_rows["MODEL_PASS_1"], pass_rows["MODEL_PASS_2"], strict=True
        )
    ]
    return pass_rows["MODEL_PASS_1"], pass_rows["MODEL_PASS_2"], adjudications


@pytest.mark.parametrize("count", [1, 3])
def test_new_candidate_review_accepts_variable_size_two_pass_bound_schema(
    count: int,
) -> None:
    pass_1, pass_2, adjudications = _candidate_review_rows(count)
    result = validate_new_candidate_review(pass_1, pass_2, adjudications)
    assert result == {
        **TRUTH_FIELDS,
        "candidate_count": count,
        "validation_status": "PASS",
    }


def test_new_candidate_review_rejects_unbounded_rationale_or_inflated_truth() -> None:
    pass_1, pass_2, adjudications = _candidate_review_rows()
    pass_1[0]["rationale"] = "x" * (RATIONALE_MAX_CHARS + 1)
    pass_1[0] = with_row_sha256(pass_1[0])
    with pytest.raises(ValueError, match="rationale"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)

    pass_1, pass_2, adjudications = _candidate_review_rows()
    pass_1[0]["human_reviewer_count"] = 1
    pass_1[0] = with_row_sha256(pass_1[0])
    with pytest.raises(ValueError, match="truth field"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)


def test_new_candidate_review_rejects_schema_identity_opinion_and_claim_drift() -> None:
    pass_1, pass_2, adjudications = _candidate_review_rows(3)
    pass_1[0]["schema_version"] = "wrong-schema"
    pass_1[0] = with_row_sha256(pass_1[0])
    with pytest.raises(ValueError, match="schema"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)

    pass_1, pass_2, adjudications = _candidate_review_rows(3)
    pass_1.reverse()
    with pytest.raises(ValueError, match="canonical candidate order"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)

    pass_1, pass_2, adjudications = _candidate_review_rows()
    adjudications[0]["adjudicated_model_opinion"] = "POSITIVE_ROLE_SUPPORTED"
    adjudications[0] = with_row_sha256(adjudications[0])
    with pytest.raises(ValueError, match="opinion"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)

    pass_1, pass_2, adjudications = _candidate_review_rows()
    pass_1[0]["reviewer"] = "a human"
    pass_1[0] = with_row_sha256(pass_1[0])
    with pytest.raises(ValueError, match="forbidden field"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)


def test_new_candidate_review_rejects_agreement_or_usage_drift() -> None:
    pass_1, pass_2, adjudications = _candidate_review_rows()
    adjudications[0]["opinions_agree"] = False
    adjudications[0] = with_row_sha256(adjudications[0])
    with pytest.raises(ValueError, match="agreement"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)

    pass_1, pass_2, adjudications = _candidate_review_rows()
    pass_1[0]["usage"] = "TRAIN"
    pass_1[0] = with_row_sha256(pass_1[0])
    with pytest.raises(ValueError, match="usage"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)


@pytest.mark.parametrize("run_id", ["", "   "])
def test_new_candidate_review_rejects_blank_pass_run_id(run_id: str) -> None:
    pass_1, pass_2, adjudications = _candidate_review_rows()
    for row in pass_1:
        row["pass_run_id"] = run_id
        row.update(with_row_sha256(row))
    with pytest.raises(ValueError, match="pass run identities"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)


def test_new_candidate_review_rejects_blank_or_forbidden_truth_claims() -> None:
    pass_1, pass_2, adjudications = _candidate_review_rows()
    pass_1[0]["rationale"] = "   "
    pass_1[0] = with_row_sha256(pass_1[0])
    with pytest.raises(ValueError, match="rationale"):
        validate_new_candidate_review(pass_1, pass_2, adjudications)

    forbidden_claims = [
        "human-reviewed",
        "human-accepted",
        "人工审核完成",
        "reviewer 是项目所有者本人",
        "independent human review",
        "production-ready data",
        "production release",
        "router promotion",
        "release claim",
        "blind-v2 conclusion",
        "人工标注数据",
        "résumé human-review claim",
        "blind-v2 最终结论",
        "生产发布",
        "简历中的人工审核 claim",
    ]
    for claim in forbidden_claims:
        pass_1, pass_2, adjudications = _candidate_review_rows()
        pass_1[0]["rationale"] = f"This row makes a forbidden {claim}."
        pass_1[0] = with_row_sha256(pass_1[0])
        with pytest.raises(ValueError, match="forbidden claim"):
            validate_new_candidate_review(pass_1, pass_2, adjudications)


def test_canonical_hash_is_order_independent_for_object_keys() -> None:
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
