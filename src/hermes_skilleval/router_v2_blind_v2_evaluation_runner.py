from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter
from copy import deepcopy
from datetime import datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, cast

from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.router_v2_blind_v2_evaluation import (
    ARMS,
    CANONICAL_SKILL_COUNT,
    NEGATIVE_LABELED_PER_GOLD_SKILL,
    POSITIVE_TASK_COUNT,
    POSITIVE_ONLY_PER_GOLD_SKILL,
    SEEDS,
    SEMANTIC_FAMILY_COUNT,
    TASKS_PER_GOLD_SKILL,
    TEMPTING_NEGATIVE_COUNT,
    TERMINAL_STATES,
    apply_preregistered_gate,
    build_aggregate_results,
    build_failure_slices,
    build_lineage_manifest,
    build_paired_results,
    build_per_seed_result,
    build_statistics,
    canonical_sha256,
    preregistered_evaluation_contract,
    terminal_posture,
    validate_preregistration_truth,
)
from hermes_skilleval.router_v2_pilot_candidates import _skill_text
from hermes_skilleval.router_v2_pilot_evaluation import quantize8


MODEL_LOAD_SMOKE_TEXTS = (
    "synthetic blind-v2 model load query",
    "synthetic blind-v2 skill description",
)
AGENT_CONFIG_SMOKE_REQUEST_TEXT = "synthetic blind-v2 agent configuration smoke request"
AGENT_CONFIG_SMOKE_RESPONSE_TEXT = (
    "synthetic blind-v2 agent configuration smoke response"
)
QUERY_CONTRACT_VERSION = "router-v2-prompt-only-query-v1"
SKILL_REPRESENTATION_BUILDER_VERSION = (
    "router-v2-id-name-category-description-trigger-terms-body-v1"
)
FINAL_NAMESPACE_RELATIVE = Path(
    "artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/attempt-1"
)
DATASET_FREEZE_RELATIVE = Path("data/router-v2-blind-v2")
PREREGISTRATION_RELATIVE = Path("artifacts/router-v2-blind-v2/preregistration.json")
DATASET_FREEZE_FILENAMES = (
    "blind-v2-tasks.jsonl",
    "blind-v2-review-summary.json",
    "blind-v2-manifest.json",
)
PILOT_MANIFEST_RELATIVE = Path(
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-002-eval-replay/pilot-manifest.json"
)
EVALUATION_OUTPUT_FILENAMES = (
    "preregistration.json",
    "blind-v2-tasks.jsonl",
    "blind-v2-manifest.json",
    "review-summary.json",
    "per-seed.json",
    "aggregate.json",
    "paired.json",
    "statistics.json",
    "failure-slices.json",
    "evaluation-summary.json",
    "result-report.md",
    "lineage-manifest.json",
)
SMOKE_RECEIPT_ROOT = Path("/tmp/hermes-router-v2-blind-v2-smoke-receipts")
PREREGISTRATION_PARENT_COMMIT = "8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552"
HISTORICAL_HUMAN_COMMIT_A = "09ba4104a147a2f740ef69283c850f40e78a0b15"
TASK8_BASELINE_HEAD = "0998b814e82b4da164a54d0a6ce219573f037994"
EVALUATOR_SOURCE_PATHS = (
    "src/hermes_skilleval/router_v2_blind_v2_evaluation.py",
    "src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py",
    "src/hermes_skilleval/router_v2_pilot_evaluation.py",
    "scripts/run_router_v2_blind_v2_final.py",
)
EVALUATOR_FIELDS = frozenset(
    {"arms", "contract_sha256", "seeds", "source_files", "source_files_sha256"}
)
EVALUATOR_SOURCE_ROW_FIELDS = frozenset({"path", "sha256"})
REQUIRED_AGENT_PACK_FILES = (
    "blind-v2-generation.jsonl",
    "blind-v2-review-a.jsonl",
    "blind-v2-review-b.jsonl",
    "blind-v2-contamination.jsonl",
    "agent-run-metadata.json",
)
AGENT_CONFIGS = {
    "generator": {
        "model": "gpt-5.6-sol",
        "reasoning_effort": "max",
        "timeout_seconds": 1800,
    },
    "reviewer_a": {
        "model": "gpt-5.6-sol",
        "reasoning_effort": "ultra",
        "timeout_seconds": 900,
    },
    "reviewer_b": {
        "model": "gpt-5.6-luna",
        "reasoning_effort": "max",
        "timeout_seconds": 900,
    },
}
SEMANTIC_MODEL_ID = "sentence-transformers/all-mpnet-base-v2"
SEMANTIC_MODEL_REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
TOKEN_5GRAM_JACCARD_MAX = Decimal("0.80")
CHARACTER_5GRAM_JACCARD_MAX = Decimal("0.85")
SEMANTIC_COSINE_MAX = Decimal("0.90")
CONTAMINATION_SCOPES = ("train", "pilot-002", "phase16", "prior_candidate")
_SELECTION_AUTHORITY: Mapping[str, int | str] = MappingProxyType(
    {
        "selection_seed": 7170,
        "selection_order": "ascending_selection_key(candidate_id)_within_stratum",
        "max_generation_rounds": 2,
        "round_1_candidate_count": 256,
        "round_1_negative_per_skill": 12,
        "round_1_positive_only_per_skill": 4,
        "round_2_deficit_multiplier": 2,
        "final_negative_per_skill": 6,
        "final_positive_only_per_skill": 2,
    }
)
SELECTION_AUTHORITY = _SELECTION_AUTHORITY
SELECTION_SEED = cast(int, _SELECTION_AUTHORITY["selection_seed"])


def _selection_authority_document() -> dict[str, int | str]:
    return dict(_SELECTION_AUTHORITY)


GENERATOR_SYSTEM_PROMPT = (
    "You are the Generator for a preregistered Router V2 blind evaluation. "
    "Create natural English user requests for exactly one primary canonical skill. "
    "Do not mention skill IDs, skill names, gold labels, negative labels, benchmarks, "
    "routers, training, pilot data, Phase 16, Arm A, Arm C, or model behavior. For a "
    "negative-labeled candidate, choose one plausible but insufficient canonical "
    "negative skill. Use only the supplied skill definitions and quota. Do not use "
    "external memory or prior conversation. Return only JSON matching the supplied "
    "schema."
)
REVIEWER_SYSTEM_PROMPT = (
    "You are a role-isolated reviewer for one preregistered Router V2 blind candidate. "
    "Use only the supplied task text, canonical skill definitions, and rubric. "
    "Independently decide the single primary gold skill and one "
    "plausible-but-insufficient negative skill or null. Reject ambiguity, unnatural "
    "wording, label leakage, invalid negatives, and tasks with more than one equally "
    "primary skill. Do not use external memory, prior conversation, quotas, other "
    "reviews, generator labels, Router models, or model results. Return only JSON "
    "matching the supplied schema."
)
GENERATOR_RULES = {
    "language": "natural English",
    "primary_skill": "exactly one primary canonical skill",
    "label_leakage": "do not expose canonical labels in the request text",
    "negative_skill": "one plausible but insufficient canonical skill or null",
    "source_boundary": "use only the supplied canonical skill definitions and quota",
}
REVIEW_RUBRIC = {
    "natural": "The request is natural English user wording.",
    "single_primary_skill": "Exactly one canonical skill is clearly primary.",
    "no_label_leakage": "The request does not expose skill or evaluation labels.",
    "negative_confusable": (
        "A non-null negative is plausible for the wording but insufficient to fulfill "
        "the request; use null when no such negative exists."
    ),
}
AGENT_REVIEW_DECISIONS = (
    "ACCEPT",
    "REJECT_AMBIGUOUS",
    "REJECT_NOT_CONFUSABLE",
    "REJECT_UNNATURAL",
    "REJECT_LABEL_LEAKAGE",
)
AGENT_REVIEW_CONFIDENCE = ("LOW", "MEDIUM", "HIGH")
CANONICAL_SKILL_FIELDS_IN_ORDER = (
    "id",
    "name",
    "category",
    "description",
    "trigger_terms",
    "body",
)
GENERATOR_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "candidate_index",
                    "prompt_text",
                    "semantic_family_id",
                    "proposed_gold_skill_id",
                    "proposed_negative_skill_id",
                    "language",
                    "rationale",
                ],
                "properties": {
                    "candidate_index": {"type": "integer", "minimum": 0},
                    "prompt_text": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "semantic_family_id": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "proposed_gold_skill_id": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                    "proposed_negative_skill_id": {
                        "type": ["string", "null"],
                        "pattern": r"\S",
                    },
                    "language": {"const": "en"},
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": r"\S",
                    },
                },
            },
        }
    },
}
REVIEWER_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
        "natural",
        "single_primary_skill",
        "no_label_leakage",
        "negative_confusable",
        "confidence",
        "reason",
    ],
    "properties": {
        "decision": {"enum": list(AGENT_REVIEW_DECISIONS)},
        "reviewed_gold_skill_id": {
            "type": "string",
            "minLength": 1,
            "pattern": r"\S",
        },
        "reviewed_negative_skill_id": {
            "type": ["string", "null"],
            "pattern": r"\S",
        },
        "natural": {"type": "boolean"},
        "single_primary_skill": {"type": "boolean"},
        "no_label_leakage": {"type": "boolean"},
        "negative_confusable": {"type": ["boolean", "null"]},
        "confidence": {"enum": list(AGENT_REVIEW_CONFIDENCE)},
        "reason": {"type": "string", "minLength": 1, "pattern": r"\S"},
    },
    "allOf": [
        {
            "if": {
                "properties": {"reviewed_negative_skill_id": {"type": "null"}},
                "required": ["reviewed_negative_skill_id"],
            },
            "then": {"properties": {"negative_confusable": {"type": "null"}}},
            "else": {"properties": {"negative_confusable": {"type": "boolean"}}},
        }
    ],
    "oneOf": [
        {
            "properties": {
                "decision": {"const": "ACCEPT"},
                "natural": {"const": True},
                "single_primary_skill": {"const": True},
                "no_label_leakage": {"const": True},
            },
            "if": {
                "properties": {"reviewed_negative_skill_id": {"type": "string"}},
                "required": ["reviewed_negative_skill_id"],
            },
            "then": {"properties": {"negative_confusable": {"const": True}}},
        },
        {
            "properties": {
                "decision": {"const": "REJECT_AMBIGUOUS"},
                "single_primary_skill": {"const": False},
            }
        },
        {
            "properties": {
                "decision": {"const": "REJECT_NOT_CONFUSABLE"},
                "reviewed_negative_skill_id": {
                    "type": "string",
                    "pattern": r"\S",
                },
                "negative_confusable": {"const": False},
            }
        },
        {
            "properties": {
                "decision": {"const": "REJECT_UNNATURAL"},
                "natural": {"const": False},
            }
        },
        {
            "properties": {
                "decision": {"const": "REJECT_LABEL_LEAKAGE"},
                "no_label_leakage": {"const": False},
            }
        },
    ],
}
PREREGISTRATION_SCHEMA_VERSION = "router-v2-blind-v2-agent-preregistration-v2"
PREREGISTRATION_GENERATED_AT_UTC = "2026-07-18T19:53:21.592178+00:00"
COMMIT_A_BINDING = (
    "SUPERSEDING_COMMIT_A_AGENT_BINDS_THIS_DOCUMENT_AND_ALL_CHANGED_FILES"
)
COMMIT_A_CHANGED_FILES = (
    "artifacts/router-v2-blind-v2/preregistration.json",
    "docs/router-v2-blind-v2-protocol.md",
    "openspec/changes/run-router-v2-final-blind-v2/.openspec.yaml",
    "openspec/changes/run-router-v2-final-blind-v2/design.md",
    "openspec/changes/run-router-v2-final-blind-v2/proposal.md",
    "openspec/changes/run-router-v2-final-blind-v2/specs/router-v2-final-blind-v2/spec.md",
    "openspec/changes/run-router-v2-final-blind-v2/tasks.md",
    "scripts/run_router_v2_blind_v2_final.py",
    "src/hermes_skilleval/router_v2_blind_v2_evaluation.py",
    "src/hermes_skilleval/router_v2_blind_v2_evaluation_runner.py",
    "tests/test_router_v2_blind_v2_evaluation.py",
    "tests/test_router_v2_blind_v2_evaluation_runner.py",
)
PREEXISTING_MAIN_VALIDATION_AUTHORITY = MappingProxyType(
    {
        "github_validate_conclusion": "failure",
        "github_validate_run_id": 29433191147,
        "local_full_pytest": MappingProxyType({"failed": 25, "passed": 1155}),
        "not_attributed_to_blind_v2_change": True,
    }
)
PREREGISTRATION_FIELDS = frozenset(
    {
        "agent_construction",
        "agent_construction_sha256",
        "arm_c_checkpoints",
        "base_model",
        "best_seed_selection_allowed",
        "blind_v2_candidate_data_seen",
        "blind_v2_data_seen",
        "blind_v2_data_seen_compatibility",
        "blind_v2_expected_negative_labeled_task_count",
        "blind_v2_expected_task_count",
        "blind_v3_allowed",
        "commit_a_binding",
        "commit_a_changed_files",
        "current_git_commit_before_commit_a",
        "default_router_unchanged",
        "evaluation_output_namespace",
        "evaluator",
        "frozen_inputs",
        "frozen_inputs_sha256",
        "gate",
        "gate_sha256",
        "generated_at_utc",
        "historical_supersession",
        "latency_measurement_protocol",
        "metric_definitions",
        "non_actions",
        "old_phase16_prompt_files",
        "old_phase16_prompt_files_sha256",
        "origin_main_git_commit",
        "pilot_002_gate_artifact",
        "posthoc_tuning_allowed",
        "preexisting_main_validation",
        "preregistration_parent_git_commit",
        "preregistration_sha256",
        "production_ready",
        "protected_semantic_commitment",
        "protected_preregistration_subtree_sha256",
        "query_contract",
        "query_contract_sha256",
        "release_authorized",
        "release_eligible",
        "research_question",
        "retraining_allowed",
        "router_decision",
        "schema_version",
        "semantic_contamination",
        "semantic_contamination_sha256",
        "single_attempt",
        "skill_index",
        "skill_index_semantic_sha256",
        "skill_representation_builder",
        "skill_representation_builder_sha256",
        "statistics",
        "supersedes_commit",
        "threshold_change_allowed",
    }
)
PREREGISTRATION_FIELD_AUTHORITY_LEDGER = MappingProxyType(
    {
        "agent_construction": "validated_nested_exact_authority",
        "agent_construction_sha256": "validated_nested_exact_authority",
        "arm_c_checkpoints": "protected_baseline_snapshot",
        "base_model": "protected_baseline_snapshot",
        "best_seed_selection_allowed": "exact_constant",
        "blind_v2_candidate_data_seen": "exact_constant",
        "blind_v2_data_seen": "exact_constant",
        "blind_v2_data_seen_compatibility": "exact_constant",
        "blind_v2_expected_negative_labeled_task_count": "exact_constant",
        "blind_v2_expected_task_count": "exact_constant",
        "blind_v3_allowed": "exact_constant",
        "commit_a_binding": "exact_constant",
        "commit_a_changed_files": "exact_constant",
        "current_git_commit_before_commit_a": "exact_constant",
        "default_router_unchanged": "exact_constant",
        "evaluation_output_namespace": "exact_constant",
        "evaluator": "actual_file_bytes",
        "frozen_inputs": "protected_baseline_snapshot",
        "frozen_inputs_sha256": "protected_baseline_snapshot",
        "gate": "protected_baseline_snapshot",
        "gate_sha256": "protected_baseline_snapshot",
        "generated_at_utc": "exact_constant",
        "historical_supersession": "validated_nested_exact_authority",
        "latency_measurement_protocol": "validated_nested_exact_authority",
        "metric_definitions": "validated_nested_exact_authority",
        "non_actions": "validated_nested_exact_authority",
        "old_phase16_prompt_files": "protected_baseline_snapshot",
        "old_phase16_prompt_files_sha256": "protected_baseline_snapshot",
        "origin_main_git_commit": "exact_constant",
        "pilot_002_gate_artifact": "protected_baseline_snapshot",
        "posthoc_tuning_allowed": "exact_constant",
        "preexisting_main_validation": "exact_constant",
        "preregistration_parent_git_commit": "exact_constant",
        "preregistration_sha256": "validated_nested_exact_authority",
        "production_ready": "exact_constant",
        "protected_semantic_commitment": "actual_file_bytes",
        "protected_preregistration_subtree_sha256": ("protected_baseline_snapshot"),
        "query_contract": "actual_file_bytes",
        "query_contract_sha256": "actual_file_bytes",
        "release_authorized": "exact_constant",
        "release_eligible": "exact_constant",
        "research_question": "exact_constant",
        "retraining_allowed": "exact_constant",
        "router_decision": "exact_constant",
        "schema_version": "exact_constant",
        "semantic_contamination": "actual_file_bytes",
        "semantic_contamination_sha256": "actual_file_bytes",
        "single_attempt": "validated_nested_exact_authority",
        "skill_index": "actual_file_bytes",
        "skill_index_semantic_sha256": "actual_file_bytes",
        "skill_representation_builder": "actual_file_bytes",
        "skill_representation_builder_sha256": "actual_file_bytes",
        "statistics": "validated_nested_exact_authority",
        "supersedes_commit": "exact_constant",
        "threshold_change_allowed": "exact_constant",
    }
)
TASK8_RESEARCH_QUESTION = (
    "Do the unchanged Router V2 Arm C checkpoints meet the unchanged pilot-002 "
    "gate once on a preregistered 128-task Agent-constructed set accepted by two "
    "role-isolated reviewers with unanimous labels?"
)
GENERATOR_HUMAN_READABLE_RESPONSE_SCHEMA = {
    "candidates": [
        {
            "candidate_index": 0,
            "prompt_text": "natural English request",
            "semantic_family_id": "opaque family string",
            "proposed_gold_skill_id": "canonical skill id",
            "proposed_negative_skill_id": "canonical skill id or null",
            "language": "en",
            "rationale": "brief label rationale",
        }
    ]
}
REVIEWER_HUMAN_READABLE_RESPONSE_SCHEMA = {
    "decision": "ACCEPT or frozen REJECT code",
    "reviewed_gold_skill_id": "canonical skill id",
    "reviewed_negative_skill_id": "canonical skill id or null",
    "natural": True,
    "single_primary_skill": True,
    "no_label_leakage": True,
    "negative_confusable": None,
    "confidence": "LOW, MEDIUM, or HIGH",
    "reason": "brief decision rationale",
}
GENERATOR_REQUEST_SCHEMA_AUTHORITY = {
    "schema_version": "router-v2-blind-v2-generation-request-v1",
    "top_level_fields": [
        "schema_version",
        "role",
        "model",
        "reasoning_effort",
        "timeout_seconds",
        "system_prompt",
        "response_schema",
        "input",
        "request_sha256",
    ],
    "input_fields": ["canonical_skills", "rules", "quota"],
    "canonical_skill_fields": list(CANONICAL_SKILL_FIELDS_IN_ORDER),
    "quota_fields": [
        "gold_skill_id",
        "negative_quota",
        "positive_only_quota",
        "round_number",
    ],
}
REVIEWER_REQUEST_SCHEMA_AUTHORITY = {
    "schema_version": "router-v2-blind-v2-review-request-v1",
    "top_level_fields": [
        "schema_version",
        "role",
        "model",
        "reasoning_effort",
        "timeout_seconds",
        "system_prompt",
        "response_schema",
        "input",
        "request_sha256",
    ],
    "input_fields": ["task_id", "prompt_text", "canonical_skills", "rubric"],
    "canonical_skill_fields": list(CANONICAL_SKILL_FIELDS_IN_ORDER),
}
CANDIDATE_ID_RULE = (
    'first 24 hex characters of sha256(f"{round_number}:{skill_id}:'
    '{candidate_index}:{response_sha256}")'
)
SELECTION_KEY_RULE = 'sha256("7170:" + candidate_id)'
REVIEWER_SCHEDULE_RULES = {
    "reviewer_a": 'ascending sha256("review-a:7170:" + candidate_id)',
    "reviewer_b": 'ascending sha256("review-b:7171:" + candidate_id)',
}
NEGATIVE_CONFUSABLE_SEMANTICS = (
    "true when reviewed_negative_skill_id is non-null; null when the reviewer "
    "independently selects no negative"
)
PROTECTED_PREREGISTRATION_SUBTREE_SHA256 = {
    "base_model": "9c8c287edecec1d3db119afbad9468a6fe71b5c3c591e3068b9a4a3275c6cc2d",
    "arm_c_checkpoints": "09a462fe6d888bffb75ffed7187bfe397e17224227d4c2126c82eb909e95d2ce",
    "frozen_inputs": "dd2ea7dd0fe1675cb87bc6ece6cea8f330afb98c7cb52cd69676ca259e275056",
    "pilot_002_gate_artifact": "3a2641bae204676574dc2c58d15198bbd601ce8ec82a3deeca9aedb1c71cfb9a",
    "query_contract": "4e1ea3f5eb074939abccc1e8198286e55313b385545fc1c4f45e0b47bd11b2a5",
    "skill_representation_builder": "5959ad6e5c9b700cf17ccd0ccede02c3777c6e9d7c13da4a933dbae40e07faa3",
    "old_phase16_prompt_files": "e6cbc0d7aeb9f04928b635892409fe21c70a038439b875015a25ffce921fd39a",
    "gate": "19a53521277f914393fcb815e9c35a1e2e6bc549b0db49027d03e1d6cd875bba",
    "skill_index": "61349bc19f92705aa0ba0c410ffc79cee52103823a20250bd9908fa248b813f3",
}
SEMANTIC_MODEL_SNAPSHOT_PATH = (
    Path.home()
    / ".cache/huggingface/hub"
    / "models--sentence-transformers--all-mpnet-base-v2"
    / "snapshots"
    / SEMANTIC_MODEL_REVISION
)
SEMANTIC_MODEL_MATERIALIZED_FILES = (
    (
        ".gitattributes",
        1229,
        "98ccb431c012ebfe976280fbd45aea4cec7409935868ccecf3954370f96732a1",
    ),
    (
        "1_Pooling/config.json",
        190,
        "a37f83ada23e7887be6b88f4998927dbeac0038af301553c7cd5461413bf1a56",
    ),
    (
        "README.md",
        11612,
        "89a1a9c3290fe58e76c939b578c48a14331dc7bfcaaf5a53102adb183da6f96a",
    ),
    (
        "config.json",
        571,
        "d46a3e04ded82bba22528424480697d394eeda6a27484e08c5bb2bdf5906cfa0",
    ),
    (
        "config_sentence_transformers.json",
        116,
        "061ca9d39661d6c6d6de5ba27f79a1cd5770ea247f8d46412a68a498dc5ac9f3",
    ),
    (
        "data_config.json",
        39265,
        "32edcb108fc2516b920734a862ae0692bcae1c5d45d5f8d972cb0d53434a4c54",
    ),
    (
        "model.safetensors",
        437971872,
        "78c0197b6159d92658e319bc1d72e4c73a9a03dd03815e70e555c5ef05615658",
    ),
    (
        "modules.json",
        349,
        "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
    ),
    (
        "onnx/model.onnx",
        435826548,
        "74187b16d9c946fea252e120cfd7a12c5779d8b8b86838a2e4c56573c47941bd",
    ),
    (
        "onnx/model_O1.onnx",
        435730180,
        "5c0b47004076ab40bf15a2c52b98a53e985ebb84faaeeb6d2551768f96e384b0",
    ),
    (
        "onnx/model_O2.onnx",
        435666661,
        "14d01256f5f3d2245b15b596173bca4367c9405fde5700dd7fb4e110708c1793",
    ),
    (
        "onnx/model_O3.onnx",
        435666516,
        "dd55510706038d0817b7d41bf2078f01472e4865190584ad624e8ab79bbcb310",
    ),
    (
        "onnx/model_O4.onnx",
        217894954,
        "cab2a54139fc4fd5b8e2a23cb5729ee28dc44cfde685ad3356d533653e635310",
    ),
    (
        "onnx/model_qint8_arm64.onnx",
        110124379,
        "c392a9c545c7d4438a16fed8287a76a576b27eaf029c1c23bbf78a7a666d197f",
    ),
    (
        "onnx/model_qint8_avx512.onnx",
        110124379,
        "c392a9c545c7d4438a16fed8287a76a576b27eaf029c1c23bbf78a7a666d197f",
    ),
    (
        "onnx/model_qint8_avx512_vnni.onnx",
        110124379,
        "c392a9c545c7d4438a16fed8287a76a576b27eaf029c1c23bbf78a7a666d197f",
    ),
    (
        "onnx/model_quint8_avx2.onnx",
        110207323,
        "aa5c27172d77bbd1cbae3628cbac4b26d7c12adabff25d2d4285d0f29159b237",
    ),
    (
        "openvino/openvino_model.bin",
        435583684,
        "5c3279d833888eaab745e24b652126c5a71375af185ac21aa47e112e2468dec0",
    ),
    (
        "openvino/openvino_model.xml",
        432773,
        "a2912e3dbd3426b77984992953998d8026a3d2377104093079e810b53fc51bf6",
    ),
    (
        "openvino/openvino_model_qint8_quantized.bin",
        109974792,
        "fde0c650018f5e244f793316b666aaf4758d4e19072f430e59eb2bcc414895ce",
    ),
    (
        "openvino/openvino_model_qint8_quantized.xml",
        741875,
        "930bc2a849d48941bb4752d8dac018f0c0ee8709ba023e47aeab4f8bb9c25b59",
    ),
    (
        "pytorch_model.bin",
        438011953,
        "a8fd120b1a0032e70ff3d4b8ab8e46a6d01c2cb08ffe7c007a021c1788928146",
    ),
    (
        "sentence_bert_config.json",
        53,
        "cabfacded9272091a06ff595a46ef027a76ddf4ac9e77d0fcf11c605748f1667",
    ),
    (
        "special_tokens_map.json",
        239,
        "9ef40e9c160511bf3f46ceb71f1471dafa1e9473d5120bb816c36b2efa75f8ba",
    ),
    (
        "tokenizer.json",
        466021,
        "b8be2c30ba5dd723a6d5ee26d013da103d5408d92ddcb23747622f9e48f1d842",
    ),
    (
        "tokenizer_config.json",
        363,
        "67f2ff7e223518e729869bb3a70f0caf8368fe549383fc11cfe2dfb42fffc268",
    ),
    (
        "train_script.py",
        13123,
        "dea86a7066caa55d0c84c343890dfd849714b6affd8b424ba12372a091578cc8",
    ),
    (
        "vocab.txt",
        231536,
        "dbd90cb94e2247bd4d4ccaecbf616d2290e66691d7d5e5bb81f063c2d0649ada",
    ),
)
SEMANTIC_MODEL_MATERIALIZED_FILES_SHA256 = (
    "11a0b5bd48efbae208424572fe30f873a139d552582047201c96e3b6d85b7f1a"
)
_LEAKAGE_MARKERS = (
    "gold skill",
    "negative skill",
    "benchmark",
    "router",
)
_PROTECTED_MARKERS = (
    "phase16",
    "phase-16",
    "phase_16",
    "pilot-002",
    "pilot_002",
    "heldout-labels",
)


class EvaluationEncoder(Protocol):
    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]: ...


class RouteScorer(Protocol):
    def rank(self, query: str, skill_ids: list[str]) -> list[str]: ...


EncoderFactory = Callable[[str, int, Path], EvaluationEncoder]
ScorerFactory = Callable[[str, int, Path], RouteScorer]
AuthorityValidator = Callable[..., dict[str, Any]]
CommitBValidator = Callable[..., dict[str, Any]]
SemanticSimilarity = Callable[[str, str], int | float | Decimal]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _task8_text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _task8_role_authority(role: str) -> dict[str, Any]:
    _require(role in AGENT_CONFIGS, "Task 8 Agent role mismatch")
    reviewer = role != "generator"
    system_prompt = REVIEWER_SYSTEM_PROMPT if reviewer else GENERATOR_SYSTEM_PROMPT
    human_schema = (
        REVIEWER_HUMAN_READABLE_RESPONSE_SCHEMA
        if reviewer
        else GENERATOR_HUMAN_READABLE_RESPONSE_SCHEMA
    )
    response_schema = (
        REVIEWER_RESPONSE_SCHEMA if reviewer else GENERATOR_RESPONSE_SCHEMA
    )
    request_schema = (
        REVIEWER_REQUEST_SCHEMA_AUTHORITY
        if reviewer
        else GENERATOR_REQUEST_SCHEMA_AUTHORITY
    )
    authority = {
        "config": deepcopy(AGENT_CONFIGS[role]),
        "system_prompt": system_prompt,
        "system_prompt_sha256": _task8_text_sha256(system_prompt),
        "human_readable_response_schema": deepcopy(human_schema),
        "human_readable_response_schema_sha256": canonical_sha256(human_schema),
        "response_json_schema": deepcopy(response_schema),
        "response_json_schema_sha256": canonical_sha256(response_schema),
        "request_schema": deepcopy(request_schema),
        "request_schema_sha256": canonical_sha256(request_schema),
    }
    if reviewer:
        authority["negative_confusable_semantics"] = NEGATIVE_CONFUSABLE_SEMANTICS
    return authority


def _task8_agent_construction_authority() -> dict[str, Any]:
    candidate_rule = CANDIDATE_ID_RULE
    selection_rule = SELECTION_KEY_RULE
    schedules = {
        role: {
            "ordering_rule": rule,
            "ordering_rule_sha256": _task8_text_sha256(rule),
            "runtime_schedule_sha256_definition": (
                "canonical_sha256(ordered_candidate_ids)"
            ),
        }
        for role, rule in REVIEWER_SCHEDULE_RULES.items()
    }
    return {
        "schema_version": "router-v2-blind-v2-agent-construction-authority-v1",
        "review_mode": "DUAL_AGENT_UNANIMOUS_REVIEWED",
        "source_type": "AGENT_GENERATED",
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "generator": _task8_role_authority("generator"),
        "reviewer_a": _task8_role_authority("reviewer_a"),
        "reviewer_b": _task8_role_authority("reviewer_b"),
        "candidate_id": {
            "assigned_by": "controller",
            "rule": candidate_rule,
            "rule_sha256": _task8_text_sha256(candidate_rule),
        },
        "isolation": {
            "fresh_session_per_invocation": True,
            "unique_session_or_thread_id": True,
            "fork_context": False,
            "history_message_count": 0,
            "imported_memory_count": 0,
            "reviewer_candidate_count_per_session": 1,
            "generator_external_memory_allowed": False,
            "reviewer_external_memory_allowed": False,
        },
        "transport_retry": {
            "maximum_retries": 1,
            "condition": (
                "recorded transport failure with no syntactically valid response bytes"
            ),
            "fresh_session_required": True,
            "byte_identical_request_required": True,
            "identical_model_alias_required": True,
            "identical_reasoning_effort_required": True,
            "identical_prompt_hash_required": True,
            "substantive_response_retry_allowed": False,
            "fallback_model_allowed": False,
        },
        "rounds": {
            "maximum_generation_rounds": 2,
            "round_1": {
                "skill_count": CANONICAL_SKILL_COUNT,
                "request_count": CANONICAL_SKILL_COUNT,
                "candidate_count_per_skill": 16,
                "negative_labeled_per_skill": 12,
                "positive_only_per_skill": 4,
                "candidate_count": 256,
                "skill_schedule": "ascending canonical skill id",
            },
            "round_2": {
                "allowed": True,
                "deficit_only": True,
                "candidate_count_rule": "twice each final stratum deficit",
                "maximum_round_count": 1,
                "full_scan_and_dual_review_required": True,
                "rejection_feedback_allowed": False,
            },
            "round_3_allowed": False,
        },
        "reviewer_schedules": schedules,
        "selection": {
            "selection_seed": SELECTION_SEED,
            "selection_key_rule": selection_rule,
            "selection_key_rule_sha256": _task8_text_sha256(selection_rule),
            "ordering": (
                "ascending lexicographic selection key within each "
                "(gold_skill_id, negative_or_positive_only) stratum"
            ),
            "confidence_used": False,
            "rationale_used": False,
        },
        "final_dataset": {
            "task_count": POSITIVE_TASK_COUNT,
            "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
            "family_count": SEMANTIC_FAMILY_COUNT,
            "canonical_skill_count": CANONICAL_SKILL_COUNT,
            "tasks_per_gold_skill": TASKS_PER_GOLD_SKILL,
            "negative_labeled_per_gold_skill": NEGATIVE_LABELED_PER_GOLD_SKILL,
            "positive_only_per_gold_skill": POSITIVE_ONLY_PER_GOLD_SKILL,
        },
        "terminal": {
            "pre_evaluation_states": [
                "AGENT_BLIND_V2_READY_FOR_GENERATION",
                "AGENT_BLIND_V2_READY_FOR_FORMAL_ATTEMPT",
            ],
            "terminal_states": [
                "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
                "AGENT_BLIND_V2_PROTOCOL_INVALID",
                "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
                "AGENT_BLIND_V2_GATES_PASSED",
                "AGENT_BLIND_V2_GATES_NOT_PASSED",
            ],
            "terminal_posture": {
                "router_decision": "KEEP_BASELINE",
                "production_ready": False,
                "release_authorized": False,
                "default_router_unchanged": True,
            },
        },
        "same_provider_limitation": (
            "All three roles use OpenAI models; role isolation does not establish "
            "statistical independence or human-task generalization."
        ),
    }


def _task8_semantic_model_files() -> list[dict[str, Any]]:
    return [
        {"path": path, "size": size, "sha256": sha256}
        for path, size, sha256 in SEMANTIC_MODEL_MATERIALIZED_FILES
    ]


def _task8_semantic_contamination_authority() -> dict[str, Any]:
    files = _task8_semantic_model_files()
    return {
        "model_id": SEMANTIC_MODEL_ID,
        "revision": SEMANTIC_MODEL_REVISION,
        "snapshot_path": str(SEMANTIC_MODEL_SNAPSHOT_PATH),
        "materialized_model_file_count": len(files),
        "materialized_model_total_size": sum(row["size"] for row in files),
        "materialized_model_files": files,
        "materialized_model_files_sha256": SEMANTIC_MODEL_MATERIALIZED_FILES_SHA256,
        "normalized_embeddings": True,
        "prompt_text_only": True,
        "router_skill_representation_used": False,
        "scopes": ["train", "pilot-002", "phase16", "prior_candidate"],
        "normalization": "NFKC-casefold-collapse-whitespace",
        "thresholds": {
            "token_5gram_jaccard_reject_at_or_above": str(TOKEN_5GRAM_JACCARD_MAX),
            "character_5gram_jaccard_reject_at_or_above": str(
                CHARACTER_5GRAM_JACCARD_MAX
            ),
            "semantic_cosine_reject_at_or_above": str(SEMANTIC_COSINE_MAX),
        },
    }


class _DeterministicSelectionProtocolViolation(Exception):
    pass


def _require_deterministic_selection(condition: bool, message: str) -> None:
    if not condition:
        raise _DeterministicSelectionProtocolViolation(message)


def _exact_object_fields(
    value: Any, expected: set[str] | frozenset[str], label: str
) -> dict[str, Any]:
    _require(type(value) is dict, f"{label} must be an object")
    _require(set(value) == expected, f"{label} fields mismatch")
    return cast(dict[str, Any], value)


def _nonempty_string(value: Any, label: str) -> str:
    _require(type(value) is str and bool(value.strip()), f"{label} must be non-empty")
    return cast(str, value)


def _validated_canonical_skill_rows(
    canonical_skills: Any, *, exact_fields: bool
) -> list[dict[str, Any]]:
    _require(type(canonical_skills) is list, "canonical skills must be a list")
    _require(
        len(canonical_skills) == 16,
        "canonical skills must contain exactly 16 entries",
    )
    required_fields = set(CANONICAL_SKILL_FIELDS_IN_ORDER)
    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, raw_skill in enumerate(canonical_skills):
        if exact_fields:
            skill = _exact_object_fields(
                raw_skill,
                required_fields,
                f"canonical skill {index}",
            )
        else:
            _require(
                type(raw_skill) is dict,
                f"canonical skill {index} must be an object",
            )
            _require(
                required_fields.issubset(raw_skill),
                f"canonical skill {index} fields mismatch",
            )
            skill = cast(dict[str, Any], raw_skill)
        for field in ("id", "name", "category", "description", "body"):
            _nonempty_string(skill[field], f"canonical skill {index} {field}")
        trigger_terms = skill["trigger_terms"]
        _require(
            type(trigger_terms) is list,
            f"canonical skill {index} trigger_terms must be a list",
        )
        for term_index, term in enumerate(trigger_terms):
            _nonempty_string(
                term,
                f"canonical skill {index} trigger_terms item {term_index}",
            )
        skill_id = cast(str, skill["id"])
        ids.append(skill_id)
        rows.append(skill)
    _require(len(ids) == len(set(ids)), "canonical skill ids must be unique")
    return rows


def _canonical_skill_ids(canonical_skills: Any) -> set[str]:
    rows = _validated_canonical_skill_rows(canonical_skills, exact_fields=True)
    return {cast(str, skill["id"]) for skill in rows}


def _project_canonical_skills(canonical_skills: Any) -> list[dict[str, Any]]:
    rows = _validated_canonical_skill_rows(canonical_skills, exact_fields=False)
    return [
        {field: deepcopy(skill[field]) for field in CANONICAL_SKILL_FIELDS_IN_ORDER}
        for skill in rows
    ]


def _validate_canonical_json_value(value: Any, active_ids: set[int]) -> None:
    value_type = type(value)
    if value is None or value_type in {bool, int}:
        return
    if value_type is float:
        _require(math.isfinite(value), "canonical JSON numbers must be finite")
        return
    if value_type is str:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("canonical JSON strings must be valid UTF-8") from exc
        return
    if value_type not in {list, dict}:
        raise ValueError("canonical JSON contains a non-JSON value")
    identity = id(value)
    _require(identity not in active_ids, "canonical JSON must not contain a cycle")
    active_ids.add(identity)
    try:
        if value_type is list:
            for item in value:
                _validate_canonical_json_value(item, active_ids)
        else:
            for key, item in value.items():
                _require(
                    type(key) is str,
                    "canonical JSON object keys must be strings",
                )
                _validate_canonical_json_value(key, active_ids)
                _validate_canonical_json_value(item, active_ids)
    finally:
        active_ids.remove(identity)


def _canonical_contract_json_bytes(value: Any) -> bytes:
    try:
        _validate_canonical_json_value(value, set())
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (OverflowError, RecursionError, TypeError, UnicodeEncodeError) as exc:
        raise ValueError("value must be valid canonical JSON") from exc


def _canonical_contract_json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_contract_json_bytes(value)).hexdigest()


def _canonical_contract_json_equal(actual: Any, expected: Any) -> bool:
    return _canonical_contract_json_bytes(actual) == _canonical_contract_json_bytes(
        expected
    )


def _require_exact_json_authority(actual: Any, expected: Any, *, message: str) -> None:
    _require(_canonical_contract_json_equal(actual, expected), message)


def _exact_lowercase_hex(value: Any, *, length: int, label: str) -> str:
    _require(
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value),
        f"{label} must be exactly {length} lowercase hex characters",
    )
    return cast(str, value)


def _request_sha256(request: dict[str, Any]) -> str:
    payload = {key: value for key, value in request.items() if key != "request_sha256"}
    return _canonical_contract_json_sha256(payload)


def opaque_candidate_id(
    round_number: int, skill_id: str, index: int, response_sha256: str
) -> str:
    _require(
        type(round_number) is int and round_number > 0,
        "round number must be a positive integer",
    )
    _nonempty_string(skill_id, "skill id")
    _require(type(index) is int and index >= 0, "candidate index must be an integer")
    response_sha256 = _exact_lowercase_hex(
        response_sha256, length=64, label="response SHA-256"
    )
    raw = f"{round_number}:{skill_id}:{index}:{response_sha256}"
    candidate_id = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return _exact_lowercase_hex(candidate_id, length=24, label="candidate id")


def selection_key(candidate_id: str) -> str:
    candidate_id = _exact_lowercase_hex(candidate_id, length=24, label="candidate id")
    seed = cast(int, _SELECTION_AUTHORITY["selection_seed"])
    return hashlib.sha256(f"{seed}:{candidate_id}".encode()).hexdigest()


def review_schedule_key(role: str, candidate_id: str) -> str:
    _require(
        type(role) is str and role in {"reviewer_a", "reviewer_b"},
        "reviewer role mismatch",
    )
    candidate_id = _exact_lowercase_hex(candidate_id, length=24, label="candidate id")
    prefix = {"reviewer_a": "review-a:7170", "reviewer_b": "review-b:7171"}[role]
    return hashlib.sha256(f"{prefix}:{candidate_id}".encode()).hexdigest()


def _build_generator_request_payload(
    canonical_skills: list[dict[str, Any]],
    *,
    gold_skill_id: str,
    negative_quota: int,
    positive_only_quota: int,
    round_number: int = 1,
) -> dict[str, Any]:
    projected_canonical_skills = _project_canonical_skills(canonical_skills)
    canonical_ids = {cast(str, skill["id"]) for skill in projected_canonical_skills}
    _nonempty_string(gold_skill_id, "generator gold skill")
    _require(gold_skill_id in canonical_ids, "generator gold skill must be canonical")
    for label, value in (
        ("negative quota", negative_quota),
        ("positive-only quota", positive_only_quota),
    ):
        _require(type(value) is int and value >= 0, f"{label} must be an integer")
    _require(
        negative_quota + positive_only_quota > 0,
        "generator quota must request at least one candidate",
    )
    _require(
        type(round_number) is int and round_number > 0,
        "round number must be a positive integer",
    )
    config = AGENT_CONFIGS["generator"]
    payload = {
        "schema_version": "router-v2-blind-v2-generation-request-v1",
        "role": "generator",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": GENERATOR_SYSTEM_PROMPT,
        "response_schema": deepcopy(GENERATOR_RESPONSE_SCHEMA),
        "input": {
            "canonical_skills": projected_canonical_skills,
            "rules": deepcopy(GENERATOR_RULES),
            "quota": {
                "gold_skill_id": gold_skill_id,
                "negative_quota": negative_quota,
                "positive_only_quota": positive_only_quota,
                "round_number": round_number,
            },
        },
    }
    request = {**payload, "request_sha256": _canonical_contract_json_sha256(payload)}
    return validate_agent_request(request)


def build_generator_request(
    canonical_skills: list[dict[str, Any]],
    *,
    gold_skill_id: str,
    negative_quota: int,
    positive_only_quota: int,
    repository_root: Path | str,
    round_number: int = 1,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    preregistration_file = _safe_repository_regular_file(
        repository,
        PREREGISTRATION_RELATIVE,
        label="generator preregistration",
    )
    preregistration_source = preregistration_file.read_bytes()
    preregistration = _json_no_duplicate_keys(
        preregistration_source, "generator preregistration"
    )
    repository_authority = validate_commit_a_repository(repository, preregistration)
    commit_a = _exact_lowercase_hex(
        repository_authority.get("commit_a"),
        length=40,
        label="generator Commit A-agent",
    )
    _require(
        commit_a != HISTORICAL_HUMAN_COMMIT_A,
        "historical Commit A has been superseded and cannot authorize generation",
    )
    preregistration_sha256 = _sha256_bytes(preregistration_source)
    receipt = validate_agent_config_smoke_receipt(
        commit_a=commit_a,
        preregistration_sha256=preregistration_sha256,
    )
    _require(
        receipt.get("commit_a") == commit_a
        and receipt.get("preregistration_sha256") == preregistration_sha256,
        "Agent-config smoke receipt authority mismatch",
    )
    return _build_generator_request_payload(
        canonical_skills,
        gold_skill_id=gold_skill_id,
        negative_quota=negative_quota,
        positive_only_quota=positive_only_quota,
        round_number=round_number,
    )


def build_reviewer_request(
    candidate: dict[str, Any],
    canonical_skills: list[dict[str, Any]],
    *,
    role: str,
) -> dict[str, Any]:
    _require(
        type(role) is str and role in {"reviewer_a", "reviewer_b"},
        "reviewer role mismatch",
    )
    projected_canonical_skills = _project_canonical_skills(canonical_skills)
    _require(type(candidate) is dict, "candidate must be an object")
    candidate_id = _exact_lowercase_hex(
        candidate.get("candidate_id"), length=24, label="candidate id"
    )
    prompt_text = _nonempty_string(candidate.get("prompt_text"), "prompt text")
    config = AGENT_CONFIGS[role]
    payload = {
        "schema_version": "router-v2-blind-v2-review-request-v1",
        "role": role,
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "timeout_seconds": config["timeout_seconds"],
        "system_prompt": REVIEWER_SYSTEM_PROMPT,
        "response_schema": deepcopy(REVIEWER_RESPONSE_SCHEMA),
        "input": {
            "task_id": candidate_id,
            "prompt_text": prompt_text,
            "canonical_skills": projected_canonical_skills,
            "rubric": deepcopy(REVIEW_RUBRIC),
        },
    }
    request = {**payload, "request_sha256": _canonical_contract_json_sha256(payload)}
    return validate_agent_request(request)


def validate_agent_request(request: dict[str, Any]) -> dict[str, Any]:
    request = _exact_object_fields(
        request,
        {
            "schema_version",
            "role",
            "model",
            "reasoning_effort",
            "timeout_seconds",
            "system_prompt",
            "response_schema",
            "input",
            "request_sha256",
        },
        "request",
    )
    _require(
        type(request["request_sha256"]) is str
        and request["request_sha256"] == _request_sha256(request),
        "request hash mismatch",
    )
    role = request["role"]
    _require(
        type(role) is str and role in AGENT_CONFIGS,
        "agent role mismatch",
    )
    config = AGENT_CONFIGS[cast(str, role)]
    _require(request["model"] == config["model"], "request model mismatch")
    _require(
        request["reasoning_effort"] == config["reasoning_effort"],
        "request reasoning effort mismatch",
    )
    _require(
        type(request["timeout_seconds"]) is int
        and request["timeout_seconds"] == config["timeout_seconds"],
        "request timeout mismatch",
    )
    request_input = _exact_object_fields(
        request["input"],
        (
            {"canonical_skills", "rules", "quota"}
            if role == "generator"
            else {"task_id", "prompt_text", "canonical_skills", "rubric"}
        ),
        "generator input" if role == "generator" else "reviewer input",
    )
    canonical_ids = _canonical_skill_ids(request_input["canonical_skills"])
    if role == "generator":
        _require(
            request["schema_version"] == "router-v2-blind-v2-generation-request-v1",
            "generator request schema mismatch",
        )
        _require(
            request["system_prompt"] == GENERATOR_SYSTEM_PROMPT,
            "generator system prompt mismatch",
        )
        _require(
            _canonical_contract_json_equal(
                request["response_schema"], GENERATOR_RESPONSE_SCHEMA
            ),
            "generator response schema mismatch",
        )
        _require(request_input["rules"] == GENERATOR_RULES, "generator rules mismatch")
        quota = _exact_object_fields(
            request_input["quota"],
            {
                "gold_skill_id",
                "negative_quota",
                "positive_only_quota",
                "round_number",
            },
            "generator quota",
        )
        _nonempty_string(quota["gold_skill_id"], "generator gold skill")
        _require(
            quota["gold_skill_id"] in canonical_ids,
            "generator gold skill must be canonical",
        )
        for label in ("negative_quota", "positive_only_quota"):
            _require(
                type(quota[label]) is int and quota[label] >= 0,
                f"generator {label} must be an integer",
            )
        _require(
            quota["negative_quota"] + quota["positive_only_quota"] > 0,
            "generator quota must request at least one candidate",
        )
        _require(
            type(quota["round_number"]) is int and quota["round_number"] > 0,
            "generator round number must be a positive integer",
        )
    else:
        _require(
            request["schema_version"] == "router-v2-blind-v2-review-request-v1",
            "reviewer request schema mismatch",
        )
        _require(
            request["system_prompt"] == REVIEWER_SYSTEM_PROMPT,
            "reviewer system prompt mismatch",
        )
        _require(
            _canonical_contract_json_equal(
                request["response_schema"], REVIEWER_RESPONSE_SCHEMA
            ),
            "reviewer response schema mismatch",
        )
        _require(request_input["rubric"] == REVIEW_RUBRIC, "review rubric mismatch")
        _exact_lowercase_hex(request_input["task_id"], length=24, label="candidate id")
        _nonempty_string(request_input["prompt_text"], "reviewer prompt text")
    return request


_GENERATION_CANDIDATE_FIELDS = frozenset(
    {
        "candidate_id",
        "generation_round",
        "prompt_text",
        "prompt_text_sha256",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
)


def _validated_generation_source_row(
    raw_row: Any,
    *,
    projected_skills: list[dict[str, Any]],
    canonical_ids: set[str],
    label: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    row = _exact_object_fields(
        raw_row,
        {"generation_round", "gold_skill_id", "request", "invocations"},
        label,
    )
    generation_round = row["generation_round"]
    _require(
        type(generation_round) is int and generation_round > 0,
        "generation round must be a positive integer",
    )
    gold = _nonempty_string(row["gold_skill_id"], "generation gold skill")
    _require(gold in canonical_ids, "generator gold must be canonical")

    request = validate_agent_request(row["request"])
    _require(request["role"] == "generator", "generation role mismatch")
    quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
    _require(quota["gold_skill_id"] == gold, "generation request gold mismatch")
    _require(
        quota["round_number"] == generation_round,
        "generation request round mismatch",
    )
    expected_request = _build_generator_request_payload(
        projected_skills,
        gold_skill_id=cast(str, gold),
        negative_quota=cast(int, quota["negative_quota"]),
        positive_only_quota=cast(int, quota["positive_only_quota"]),
        round_number=cast(int, generation_round),
    )
    _require(
        _canonical_contract_json_equal(request, expected_request),
        "generator request must match sealed canonical skill authority",
    )
    return row, request, quota


def _derived_generator_candidates(
    response: dict[str, Any], request: dict[str, Any]
) -> list[dict[str, Any]]:
    quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
    response_sha256 = canonical_sha256(response)
    candidates: list[dict[str, Any]] = []
    for generated in sorted(
        cast(list[dict[str, Any]], response["candidates"]),
        key=lambda candidate: cast(int, candidate["candidate_index"]),
    ):
        prompt_text = cast(str, generated["prompt_text"])
        candidates.append(
            {
                "candidate_id": opaque_candidate_id(
                    cast(int, quota["round_number"]),
                    cast(str, quota["gold_skill_id"]),
                    cast(int, generated["candidate_index"]),
                    response_sha256,
                ),
                "generation_round": quota["round_number"],
                "prompt_text": prompt_text,
                "prompt_text_sha256": _sha256_bytes(prompt_text.encode("utf-8")),
                "semantic_family_id": generated["semantic_family_id"],
                "proposed_gold_skill_id": generated["proposed_gold_skill_id"],
                "proposed_negative_skill_id": generated["proposed_negative_skill_id"],
                "language": generated["language"],
                "rationale": generated["rationale"],
            }
        )
    return candidates


def _validated_reviewer_source_row(
    raw_row: Any,
    *,
    role: str,
    candidates: dict[str, dict[str, Any]],
    projected_skills: list[dict[str, Any]],
    clean_candidate_ids: set[str],
    label: str,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    row = _exact_object_fields(
        raw_row,
        {"candidate_id", "request", "invocations"},
        label,
    )
    candidate_id = _exact_lowercase_hex(
        row["candidate_id"], length=24, label="review candidate id"
    )
    _require(candidate_id in candidates, "review references unknown candidate")
    _require(
        candidate_id in clean_candidate_ids,
        "contamination-rejected candidate must not be reviewed",
    )
    request = validate_agent_request(row["request"])
    expected_request = build_reviewer_request(
        candidates[candidate_id], projected_skills, role=role
    )
    _require(
        _canonical_contract_json_equal(request, expected_request),
        "reviewer request must contain only sealed candidate input",
    )
    return row, candidate_id, request


def _validate_generator_response(
    response: Any, request: dict[str, Any]
) -> dict[str, Any]:
    response = _exact_object_fields(response, {"candidates"}, "generator response")
    candidates = response["candidates"]
    _require(type(candidates) is list, "generator candidates must be a list")
    quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
    expected_count = quota["negative_quota"] + quota["positive_only_quota"]
    _require(len(candidates) == expected_count, "generator candidate count mismatch")
    canonical_ids = _canonical_skill_ids(
        cast(dict[str, Any], request["input"])["canonical_skills"]
    )
    indexes: list[int] = []
    negative_count = 0
    fields = {
        "candidate_index",
        "prompt_text",
        "semantic_family_id",
        "proposed_gold_skill_id",
        "proposed_negative_skill_id",
        "language",
        "rationale",
    }
    for raw_candidate in candidates:
        candidate = _exact_object_fields(raw_candidate, fields, "generator candidate")
        index = candidate["candidate_index"]
        _require(
            type(index) is int and index >= 0,
            "generator candidate index must be an integer",
        )
        indexes.append(cast(int, index))
        _nonempty_string(candidate["prompt_text"], "generator prompt text")
        _nonempty_string(
            candidate["semantic_family_id"], "generator semantic family id"
        )
        gold = candidate["proposed_gold_skill_id"]
        _require(
            type(gold) is str
            and gold in canonical_ids
            and gold == quota["gold_skill_id"],
            "generator proposed gold skill mismatch",
        )
        negative = candidate["proposed_negative_skill_id"]
        _require(
            negative is None or (type(negative) is str and negative in canonical_ids),
            "generator proposed negative skill mismatch",
        )
        _require(negative != gold, "generator negative skill must differ from gold")
        negative_count += negative is not None
        _require(candidate["language"] == "en", "generator language mismatch")
        _nonempty_string(candidate["rationale"], "generator rationale")
    _require(
        set(indexes) == set(range(expected_count))
        and len(indexes) == len(set(indexes)),
        "generator candidate indexes mismatch",
    )
    _require(
        negative_count == quota["negative_quota"],
        "generator negative quota mismatch",
    )
    return response


def _validate_reviewer_response(
    response: Any, request: dict[str, Any]
) -> dict[str, Any]:
    fields = {
        "decision",
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
        "natural",
        "single_primary_skill",
        "no_label_leakage",
        "negative_confusable",
        "confidence",
        "reason",
    }
    response = _exact_object_fields(response, fields, "reviewer response")
    _require(
        type(response["decision"]) is str
        and response["decision"] in AGENT_REVIEW_DECISIONS,
        "reviewer decision mismatch",
    )
    canonical_ids = _canonical_skill_ids(
        cast(dict[str, Any], request["input"])["canonical_skills"]
    )
    gold = response["reviewed_gold_skill_id"]
    _require(
        type(gold) is str and gold in canonical_ids,
        "reviewed gold skill must be canonical",
    )
    negative = response["reviewed_negative_skill_id"]
    _require(
        negative is None or (type(negative) is str and negative in canonical_ids),
        "reviewed negative skill must be canonical or null",
    )
    _require(negative != gold, "reviewed negative skill must differ from gold")
    for field in ("natural", "single_primary_skill", "no_label_leakage"):
        _require(type(response[field]) is bool, f"reviewer {field} must be boolean")
    _require(
        (negative is None and response["negative_confusable"] is None)
        or (negative is not None and type(response["negative_confusable"]) is bool),
        "reviewer negative confusability mismatch",
    )
    _require(
        _reviewer_decision_rubric_consistent(response),
        "reviewer decision/rubric mismatch",
    )
    _require(
        type(response["confidence"]) is str
        and response["confidence"] in AGENT_REVIEW_CONFIDENCE,
        "reviewer confidence mismatch",
    )
    _nonempty_string(response["reason"], "reviewer reason")
    return response


def validate_agent_response(
    response: dict[str, Any], *, request: dict[str, Any]
) -> dict[str, Any]:
    request = validate_agent_request(request)
    if request["role"] == "generator":
        return _validate_generator_response(response, request)
    return _validate_reviewer_response(response, request)


def validate_agent_invocation_envelope(
    envelope: dict[str, Any],
    *,
    request: dict[str, Any],
    seen_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    request = validate_agent_request(request)
    _require(type(envelope) is dict, "agent invocation envelope must be an object")
    identity_fields = {"session_id", "thread_id"}.intersection(envelope)
    _require(
        len(identity_fields) == 1,
        "exactly one session/thread id is required",
    )
    expected_fields = {
        "role",
        "fork_context",
        "history_message_count",
        "imported_memory_count",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "timeout_seconds",
        "transport_retry_count",
        "request_sha256",
        "response",
        *identity_fields,
    }
    envelope = _exact_object_fields(
        envelope, expected_fields, "agent invocation envelope"
    )
    identity = _nonempty_string(
        envelope[next(iter(identity_fields))], "session/thread id"
    )
    if seen_session_ids is not None:
        _require(type(seen_session_ids) is set, "seen session ids must be a set")
        _require(identity not in seen_session_ids, "session/thread id must be unique")
    role = cast(str, request["role"])
    config = AGENT_CONFIGS[role]
    _require(envelope["role"] == role, "agent invocation role mismatch")
    _require(envelope["fork_context"] is False, "fork context must be false")
    _require(
        type(envelope["history_message_count"]) is int
        and envelope["history_message_count"] == 0,
        "history message count must be integer zero",
    )
    _require(
        type(envelope["imported_memory_count"]) is int
        and envelope["imported_memory_count"] == 0,
        "imported memory count must be integer zero",
    )
    _require(
        envelope["requested_model"] == config["model"],
        "requested model mismatch",
    )
    _require(
        envelope["returned_model"] == config["model"],
        "returned model mismatch",
    )
    _require(
        envelope["reasoning_effort"] == config["reasoning_effort"],
        "reasoning effort mismatch",
    )
    _require(
        type(envelope["timeout_seconds"]) is int
        and envelope["timeout_seconds"] == config["timeout_seconds"],
        "timeout mismatch",
    )
    retry_count = envelope["transport_retry_count"]
    _require(
        type(retry_count) is int and retry_count in {0, 1},
        "transport retry count must be integer zero or one",
    )
    _require(
        envelope["request_sha256"] == request["request_sha256"],
        "request SHA-256 mismatch",
    )
    response = validate_agent_response(envelope["response"], request=request)
    if seen_session_ids is not None:
        seen_session_ids.add(identity)
    return response


def validate_agent_response_envelope(
    envelope: dict[str, Any],
    *,
    request: dict[str, Any],
    seen_session_ids: set[str] | None = None,
) -> dict[str, Any]:
    return validate_agent_invocation_envelope(
        envelope,
        request=request,
        seen_session_ids=seen_session_ids,
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _jaccard(left: set[str], right: set[str]) -> Decimal:
    # Task 4.2 freezes two empty sets as full overlap.
    if not left and not right:
        return Decimal("1")
    context = Context(
        prec=50,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    with localcontext(context):
        return Decimal(len(left & right)) / Decimal(len(left | right))


def _token_5grams(value: str) -> set[str]:
    tokens = _normalize(value).split()
    return {
        "\u241f".join(tokens[index : index + 5])
        for index in range(max(0, len(tokens) - 4))
    }


def _character_5grams(value: str) -> set[str]:
    normalized = _normalize(value)
    return {
        normalized[index : index + 5] for index in range(max(0, len(normalized) - 4))
    }


def _canonical_decimal(value: Decimal) -> str:
    _require(type(value) is Decimal and value.is_finite(), "decimal must be finite")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in {"-0", ""}:
        return "0"
    return rendered


def _validate_deterministic_selection(
    selected: list[dict[str, Any]],
    *,
    selected_ids: set[str],
    selected_prompt_bytes: set[bytes],
    selected_normalized_prompts: set[str],
    selected_families: set[str],
    selected_negative_rows: list[dict[str, Any]],
    canonical_ids: set[str],
) -> None:
    _require_deterministic_selection(
        type(selected) is list and all(type(row) is dict for row in selected),
        "deterministic selection input must be a task list",
    )
    _require_deterministic_selection(
        len(selected) == 128, "deterministic selection must produce 128 tasks"
    )
    _require_deterministic_selection(
        len(selected_negative_rows) == 96,
        "deterministic selection must produce 96 negative-labeled tasks",
    )
    _require_deterministic_selection(
        len(selected_ids)
        == len(selected_prompt_bytes)
        == len(selected_normalized_prompts)
        == len(selected_families)
        == 128,
        "selected task, prompt, normalized prompt, and family values must be unique",
    )
    _require_deterministic_selection(
        all(row["proposed_gold_skill_id"] in canonical_ids for row in selected),
        "selected gold skills must be canonical",
    )
    for skill_id in sorted(canonical_ids):
        negative_count = sum(
            row["proposed_gold_skill_id"] == skill_id
            and row["proposed_negative_skill_id"] is not None
            for row in selected
        )
        positive_only_count = sum(
            row["proposed_gold_skill_id"] == skill_id
            and row["proposed_negative_skill_id"] is None
            for row in selected
        )
        _require_deterministic_selection(
            negative_count
            == cast(int, _SELECTION_AUTHORITY["final_negative_per_skill"]),
            "deterministic negative stratum quota mismatch",
        )
        _require_deterministic_selection(
            positive_only_count
            == cast(int, _SELECTION_AUTHORITY["final_positive_only_per_skill"]),
            "deterministic positive-only stratum quota mismatch",
        )


def _semantic_decimal(
    semantic_similarity: SemanticSimilarity, left: str, right: str
) -> Decimal:
    raw = semantic_similarity(left, right)
    _require(
        type(raw) in {int, float, Decimal} and type(raw) is not bool,
        "semantic similarity must be numeric",
    )
    value = Decimal(str(raw))
    _require(value.is_finite(), "semantic similarity must be finite")
    _require(
        Decimal("-1") <= value <= Decimal("1"),
        "semantic similarity must be between -1 and 1",
    )
    return value


def _protected_authority_summary(
    protected_prompts: dict[str, tuple[str, ...]],
    protected_family_ids: dict[str, frozenset[str]],
) -> dict[str, dict[str, int | str]]:
    summary: dict[str, dict[str, int | str]] = {}
    for scope in CONTAMINATION_SCOPES:
        prompt_bytes = sorted(
            prompt.encode("utf-8", errors="strict")
            for prompt in protected_prompts[scope]
        )
        prompt_digest = hashlib.sha256()
        for value in prompt_bytes:
            prompt_digest.update(len(value).to_bytes(8, byteorder="big"))
            prompt_digest.update(value)
        normalized_prompts = sorted(
            _normalize(prompt) for prompt in protected_prompts[scope]
        )
        family_ids = sorted(protected_family_ids[scope])
        summary[scope] = {
            "prompt_count": len(prompt_bytes),
            "prompt_bytes_sha256": prompt_digest.hexdigest(),
            "normalized_prompt_list_sha256": canonical_sha256(normalized_prompts),
            "family_count": len(family_ids),
            "family_ids_sha256": canonical_sha256(family_ids),
            "row_projection_sha256": canonical_sha256(
                {
                    "prompts": sorted(
                        protected_prompts[scope],
                        key=lambda value: value.encode("utf-8"),
                    ),
                    "family_ids": family_ids,
                }
            ),
        }
    return summary


def _validated_construction_source_files(
    value: Any, *, label: str
) -> list[dict[str, str]]:
    _require(type(value) is list and bool(value), f"{label} sources must be non-empty")
    sources: list[dict[str, str]] = []
    paths: list[str] = []
    for raw_source in value:
        source = _exact_object_fields(
            raw_source, {"path", "file_sha256"}, f"{label} source"
        )
        path = _nonempty_string(source["path"], f"{label} source path")
        _require(
            path == path.strip()
            and path == unicodedata.normalize("NFC", path)
            and not path.startswith("/")
            and "\0" not in path
            and "\\" not in path
            and all(part not in {"", ".", ".."} for part in path.split("/")),
            f"{label} source path must be normalized relative POSIX",
        )
        sha256 = _exact_lowercase_hex(
            source["file_sha256"], length=64, label=f"{label} source SHA-256"
        )
        paths.append(path)
        sources.append({"path": path, "file_sha256": sha256})
    _require(
        paths == sorted(paths, key=lambda item: item.encode("utf-8"))
        and len(paths) == len(set(paths)),
        f"{label} sources must be uniquely sorted",
    )
    return sources


def _sealed_construction_source_files(
    value: Any, *, label: str
) -> tuple[list[dict[str, str]], list[bytes]]:
    _require(type(value) is list and bool(value), f"{label} sources must be non-empty")
    public_sources: list[dict[str, str]] = []
    payloads: list[bytes] = []
    for raw_source in value:
        source = _exact_object_fields(
            raw_source,
            {"path", "file_sha256", "source_bytes_hex"},
            f"{label} sealed source",
        )
        public_source = _validated_construction_source_files(
            [
                {
                    "path": source["path"],
                    "file_sha256": source["file_sha256"],
                }
            ],
            label=label,
        )[0]
        source_bytes_hex = source["source_bytes_hex"]
        _require(
            type(source_bytes_hex) is str,
            f"{label} sealed source bytes mismatch",
        )
        try:
            payload = bytes.fromhex(source_bytes_hex)
        except ValueError as exc:
            raise ValueError(f"{label} sealed source bytes mismatch") from exc
        _require(
            payload.hex() == source_bytes_hex
            and _sha256_bytes(payload) == public_source["file_sha256"],
            f"{label} sealed source hash mismatch",
        )
        public_sources.append(public_source)
        payloads.append(payload)
    _require(
        [source["path"] for source in public_sources]
        == sorted(
            (source["path"] for source in public_sources),
            key=lambda item: item.encode("utf-8"),
        )
        and len({source["path"] for source in public_sources}) == len(public_sources),
        f"{label} sources must be uniquely sorted",
    )
    return public_sources, payloads


def _protected_inputs_from_sealed_construction_bindings(
    bindings: Any,
) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    document = _exact_object_fields(
        bindings,
        {"canonical_skill_source", "protected_scope_sources"},
        "construction input bindings",
    )
    raw_scope_sources = _exact_object_fields(
        document["protected_scope_sources"],
        {"train", "pilot-002", "phase16"},
        "protected scope source bindings",
    )
    prompts: dict[str, list[str]] = {scope: [] for scope in CONTAMINATION_SCOPES}
    family_ids: dict[str, set[str]] = {scope: set() for scope in CONTAMINATION_SCOPES}
    for scope in ("train", "pilot-002"):
        _sources, payloads = _sealed_construction_source_files(
            raw_scope_sources[scope], label=f"{scope} protected projection"
        )
        rows = [
            row
            for index, payload in enumerate(payloads)
            for row in _jsonl_no_duplicate_keys(
                payload, f"{scope} protected source {index + 1}"
            )
        ]
        for row in rows:
            prompts[scope].append(
                _nonempty_string(row.get("query_text"), f"{scope} protected prompt")
            )
            family_ids[scope].add(
                _nonempty_string(
                    row.get("positive_source_record_id"),
                    f"{scope} protected family id",
                )
            )
    _sources, phase16_payloads = _sealed_construction_source_files(
        raw_scope_sources["phase16"], label="phase16 protected projection"
    )
    try:
        prompts["phase16"] = [
            payload.decode("utf-8", errors="strict") for payload in phase16_payloads
        ]
    except UnicodeDecodeError as exc:
        raise ValueError("phase16 protected source must be UTF-8") from exc
    return prompts, family_ids


def _construction_input_authority(
    *,
    bindings: Any,
    projected_skills: list[dict[str, Any]],
    protected_prompts: dict[str, list[str]],
    protected_family_ids: dict[str, set[str]],
) -> dict[str, Any]:
    document = _exact_object_fields(
        bindings,
        {"canonical_skill_source", "protected_scope_sources"},
        "construction input bindings",
    )
    skill_sources, skill_payloads = _sealed_construction_source_files(
        [document["canonical_skill_source"]], label="canonical skill projection"
    )
    skill_rows = _json_no_duplicate_keys(
        b'{"skills":' + skill_payloads[0] + b"}",
        "canonical skill projection wrapper",
    )["skills"]
    _require(
        _project_canonical_skills(skill_rows) == projected_skills,
        "canonical skill source projection mismatch",
    )
    raw_scope_sources = _exact_object_fields(
        document["protected_scope_sources"],
        {"train", "pilot-002", "phase16"},
        "protected scope source bindings",
    )
    protected_summary = _protected_authority_summary(
        {scope: tuple(protected_prompts[scope]) for scope in CONTAMINATION_SCOPES},
        {
            scope: frozenset(protected_family_ids[scope])
            for scope in CONTAMINATION_SCOPES
        },
    )
    protected_projections: dict[str, Any] = {}
    for scope in ("train", "pilot-002", "phase16"):
        summary = protected_summary[scope]
        _require(
            cast(int, summary["prompt_count"]) > 0,
            f"{scope} protected prompt authority must be non-empty",
        )
        if scope != "phase16":
            _require(
                cast(int, summary["family_count"]) > 0,
                f"{scope} protected family authority must be non-empty",
            )
        sources, source_payloads = _sealed_construction_source_files(
            raw_scope_sources[scope], label=f"{scope} protected projection"
        )
        if scope in {"train", "pilot-002"}:
            rows = [
                row
                for index, payload in enumerate(source_payloads)
                for row in _jsonl_no_duplicate_keys(
                    payload, f"{scope} protected source {index + 1}"
                )
            ]
            _require(
                [row.get("query_text") for row in rows] == protected_prompts[scope]
                and {row.get("positive_source_record_id") for row in rows}
                == protected_family_ids[scope],
                f"{scope} protected source projection mismatch",
            )
        else:
            try:
                source_prompts = [
                    payload.decode("utf-8", errors="strict")
                    for payload in source_payloads
                ]
            except UnicodeDecodeError as exc:
                raise ValueError("phase16 protected source must be UTF-8") from exc
            _require(
                source_prompts == protected_prompts[scope],
                "phase16 protected source projection mismatch",
            )
        protected_projections[scope] = {
            "sources": sources,
            "source_file_manifest_sha256": canonical_sha256(sources),
            "row_projection_sha256": canonical_sha256(
                {
                    "prompts": sorted(
                        protected_prompts[scope],
                        key=lambda value: value.encode("utf-8"),
                    ),
                    "family_ids": sorted(protected_family_ids[scope]),
                }
            ),
            "protected_authority": deepcopy(summary),
        }
    authority = {
        "canonical_skill_projection": {
            "sources": skill_sources,
            "source_file_manifest_sha256": canonical_sha256(skill_sources),
            "row_count": len(projected_skills),
            "rows": deepcopy(projected_skills),
            "row_projection_sha256": canonical_sha256(projected_skills),
        },
        "protected_artifact_projections": protected_projections,
    }
    return {**authority, "authority_sha256": canonical_sha256(authority)}


def _construction_input_authority_from_sealed_bindings(
    bindings: Any,
    *,
    projected_skills: list[dict[str, Any]],
) -> dict[str, Any]:
    protected_prompts, protected_family_ids = (
        _protected_inputs_from_sealed_construction_bindings(bindings)
    )
    return _construction_input_authority(
        bindings=bindings,
        projected_skills=projected_skills,
        protected_prompts=protected_prompts,
        protected_family_ids=protected_family_ids,
    )


def _protected_semantic_commitment(
    construction_input_authority: dict[str, Any],
) -> dict[str, Any]:
    raw_projections = _exact_object_fields(
        construction_input_authority["protected_artifact_projections"],
        {"train", "pilot-002", "phase16"},
        "protected semantic commitment projections",
    )
    scopes = {
        scope: {
            "sources": deepcopy(raw_projections[scope]["sources"]),
            "source_file_manifest_sha256": raw_projections[scope][
                "source_file_manifest_sha256"
            ],
            "row_projection_sha256": raw_projections[scope]["row_projection_sha256"],
            "protected_authority": deepcopy(
                raw_projections[scope]["protected_authority"]
            ),
        }
        for scope in ("train", "pilot-002", "phase16")
    }
    body = {
        "schema_version": "router-v2-blind-v2-protected-semantic-commitment-v1",
        "scopes": scopes,
    }
    return {**body, "commitment_sha256": canonical_sha256(body)}


def _validated_protected_semantic_commitment(
    value: Any,
    *,
    construction_input_authority: dict[str, Any],
) -> dict[str, Any]:
    commitment = _exact_object_fields(
        value,
        {"schema_version", "scopes", "commitment_sha256"},
        "protected semantic commitment",
    )
    expected = _protected_semantic_commitment(construction_input_authority)
    _require(
        _canonical_contract_json_equal(commitment, expected),
        "protected semantic commitment mismatch",
    )
    return deepcopy(expected)


def _validated_construction_input_authority(
    value: Any,
    *,
    projected_skills: list[dict[str, Any]],
    protected_authority: dict[str, Any],
) -> dict[str, Any]:
    authority = _exact_object_fields(
        value,
        {
            "canonical_skill_projection",
            "protected_artifact_projections",
            "authority_sha256",
        },
        "construction input authority",
    )
    skill_projection = _exact_object_fields(
        authority["canonical_skill_projection"],
        {
            "sources",
            "source_file_manifest_sha256",
            "row_count",
            "rows",
            "row_projection_sha256",
        },
        "canonical skill projection authority",
    )
    skill_sources = _validated_construction_source_files(
        skill_projection["sources"], label="canonical skill projection"
    )
    _require(
        skill_projection["source_file_manifest_sha256"]
        == canonical_sha256(skill_sources)
        and skill_projection["row_count"] == len(projected_skills)
        and skill_projection["rows"] == projected_skills
        and skill_projection["row_projection_sha256"]
        == canonical_sha256(projected_skills),
        "canonical skill projection authority mismatch",
    )
    raw_projections = _exact_object_fields(
        authority["protected_artifact_projections"],
        {"train", "pilot-002", "phase16"},
        "protected artifact projections",
    )
    projections: dict[str, Any] = {}
    for scope in ("train", "pilot-002", "phase16"):
        projection = _exact_object_fields(
            raw_projections[scope],
            {
                "sources",
                "source_file_manifest_sha256",
                "row_projection_sha256",
                "protected_authority",
            },
            f"{scope} protected artifact projection",
        )
        sources = _validated_construction_source_files(
            projection["sources"], label=f"{scope} protected projection"
        )
        row_projection_sha256 = _exact_lowercase_hex(
            projection["row_projection_sha256"],
            length=64,
            label=f"{scope} row projection SHA-256",
        )
        expected_protected = protected_authority[scope]
        _require(
            projection["source_file_manifest_sha256"] == canonical_sha256(sources)
            and row_projection_sha256 == expected_protected.get("row_projection_sha256")
            and projection["protected_authority"] == expected_protected
            and type(expected_protected.get("prompt_count")) is int
            and expected_protected["prompt_count"] > 0
            and (
                scope == "phase16"
                or (
                    type(expected_protected.get("family_count")) is int
                    and expected_protected["family_count"] > 0
                )
            ),
            f"{scope} protected artifact projection authority mismatch",
        )
        projections[scope] = {
            **deepcopy(projection),
            "sources": sources,
            "row_projection_sha256": row_projection_sha256,
        }
    normalized = {
        "canonical_skill_projection": {
            **deepcopy(skill_projection),
            "sources": skill_sources,
            "rows": deepcopy(projected_skills),
        },
        "protected_artifact_projections": projections,
    }
    _require(
        authority["authority_sha256"] == canonical_sha256(normalized),
        "construction input authority hash mismatch",
    )
    return {**normalized, "authority_sha256": authority["authority_sha256"]}


def _validated_semantic_model_authority(authority: Any) -> dict[str, Any]:
    document = _exact_object_fields(
        authority,
        {"materialized_model_files", "materialized_model_files_sha256"},
        "semantic model authority",
    )
    raw_files = document["materialized_model_files"]
    _require(
        type(raw_files) is list and bool(raw_files),
        "semantic model files must be a non-empty list",
    )
    files: list[dict[str, str]] = []
    paths: list[str] = []
    for raw_file in raw_files:
        row = _exact_object_fields(raw_file, {"path", "sha256"}, "semantic model file")
        path = _nonempty_string(row["path"], "semantic model file path")
        _require(
            path == path.strip()
            and path == unicodedata.normalize("NFC", path)
            and not path.startswith("/")
            and "\0" not in path
            and "\\" not in path
            and all(part not in {"", ".", ".."} for part in path.split("/")),
            "semantic model file path must be normalized relative POSIX",
        )
        path.encode("utf-8", errors="strict")
        sha256 = _exact_lowercase_hex(
            row["sha256"], length=64, label="semantic model file SHA-256"
        )
        paths.append(path)
        files.append({"path": path, "sha256": sha256})
    _require(
        len(paths) == len(set(paths)),
        "semantic model file paths must be unique",
    )
    _require(
        paths == sorted(paths, key=lambda value: value.encode("utf-8")),
        "semantic model files must be sorted by UTF-8 path",
    )
    aggregate = _exact_lowercase_hex(
        document["materialized_model_files_sha256"],
        length=64,
        label="semantic model file aggregate SHA-256",
    )
    _require(
        aggregate == canonical_sha256(files),
        "semantic model file aggregate hash mismatch",
    )
    return {
        "materialized_model_files": files,
        "materialized_model_files_sha256": aggregate,
    }


def _scan_contamination(
    candidates: list[dict[str, Any]],
    *,
    protected_prompts: dict[str, list[str]],
    protected_family_ids: dict[str, set[str]],
    semantic_similarity: SemanticSimilarity,
    semantic_model_authority: dict[str, Any],
) -> dict[str, Any]:
    """Build deterministic non-voting contamination evidence from prompt text."""

    _require(type(candidates) is list, "scan candidates must be a list")
    _require(
        type(protected_prompts) is dict
        and set(protected_prompts) == set(CONTAMINATION_SCOPES),
        "protected prompt scopes mismatch",
    )
    _require(
        type(protected_family_ids) is dict
        and set(protected_family_ids) == set(CONTAMINATION_SCOPES),
        "protected family scopes mismatch",
    )
    _require(callable(semantic_similarity), "semantic similarity must be callable")
    model_authority = _validated_semantic_model_authority(semantic_model_authority)

    for scope in CONTAMINATION_SCOPES:
        prompts = protected_prompts[scope]
        family_ids = protected_family_ids[scope]
        _require(
            type(prompts) is list and all(type(prompt) is str for prompt in prompts),
            f"{scope} protected prompts must be a string list",
        )
        _require(
            type(family_ids) is set
            and all(type(family_id) is str for family_id in family_ids),
            f"{scope} protected family ids must be a string set",
        )

    protected_prompt_snapshot = {
        scope: tuple(protected_prompts[scope]) for scope in CONTAMINATION_SCOPES
    }
    protected_family_snapshot = {
        scope: frozenset(protected_family_ids[scope]) for scope in CONTAMINATION_SCOPES
    }
    prompt_references: dict[str, list[dict[str, Any]]] = {}
    for scope in CONTAMINATION_SCOPES:
        prompt_references[scope] = [
            {
                "prompt_text": prompt,
                "prompt_bytes": prompt.encode("utf-8", errors="strict"),
                "prompt_sha256": _sha256_bytes(prompt.encode("utf-8", errors="strict")),
                "normalized": _normalize(prompt),
                "token_5grams": _token_5grams(prompt),
                "character_5grams": _character_5grams(prompt),
            }
            for prompt in sorted(
                protected_prompt_snapshot[scope],
                key=lambda value: value.encode("utf-8"),
            )
        ]

    protected_authority = _protected_authority_summary(
        protected_prompt_snapshot, protected_family_snapshot
    )

    projected: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    for raw_candidate in candidates:
        _require(type(raw_candidate) is dict, "scan candidate must be an object")
        candidate_id = _exact_lowercase_hex(
            raw_candidate.get("candidate_id"), length=24, label="candidate id"
        )
        _require(candidate_id not in seen_candidate_ids, "candidate ids must be unique")
        seen_candidate_ids.add(candidate_id)
        generation_round = raw_candidate.get("generation_round")
        _require(
            type(generation_round) is int and generation_round > 0,
            "generation round must be a positive integer",
        )
        prompt_text = _nonempty_string(
            raw_candidate.get("prompt_text"), "candidate prompt"
        )
        prompt_bytes = prompt_text.encode("utf-8", errors="strict")
        prompt_hash = _exact_lowercase_hex(
            raw_candidate.get("prompt_text_sha256"),
            length=64,
            label="candidate prompt hash",
        )
        _require(
            prompt_hash == _sha256_bytes(prompt_bytes),
            "candidate prompt hash mismatch",
        )
        family_id = _nonempty_string(
            raw_candidate.get("semantic_family_id"), "semantic family id"
        )
        projected.append(
            {
                "candidate_id": candidate_id,
                "generation_round": generation_round,
                "prompt_text": prompt_text,
                "prompt_bytes": prompt_bytes,
                "prompt_text_sha256": prompt_hash,
                "prompt_sha256": prompt_hash,
                "normalized": _normalize(prompt_text),
                "token_5grams": _token_5grams(prompt_text),
                "character_5grams": _character_5grams(prompt_text),
                "semantic_family_id": family_id,
            }
        )

    scanner_config = {
        "required_semantic_model_id": SEMANTIC_MODEL_ID,
        "required_semantic_model_revision": SEMANTIC_MODEL_REVISION,
        **model_authority,
        "semantic_scorer_runtime_verified": False,
        "semantic_scorer_receipt_sha256": None,
        "token_5gram_jaccard_reject_at_or_above": str(TOKEN_5GRAM_JACCARD_MAX),
        "character_5gram_jaccard_reject_at_or_above": str(CHARACTER_5GRAM_JACCARD_MAX),
        "semantic_cosine_reject_at_or_above": str(SEMANTIC_COSINE_MAX),
        "normalization": "NFKC-casefold-collapse-whitespace",
        "selection_seed": _SELECTION_AUTHORITY["selection_seed"],
        "protected_authority": protected_authority,
        "protected_authority_sha256": canonical_sha256(protected_authority),
    }

    def prompt_events(
        candidate: dict[str, Any], reference: dict[str, Any], scope: str
    ) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        reference_hash = cast(str, reference["prompt_sha256"])
        if candidate["prompt_bytes"] == reference["prompt_bytes"]:
            events.append(
                {
                    "code": f"exact_prompt_bytes:{scope}",
                    "reference_sha256": reference_hash,
                }
            )
        if candidate["normalized"] == reference["normalized"]:
            events.append(
                {
                    "code": f"normalized_prompt:{scope}",
                    "reference_sha256": reference_hash,
                }
            )
        token_jaccard = _jaccard(
            cast(set[str], candidate["token_5grams"]),
            cast(set[str], reference["token_5grams"]),
        )
        if token_jaccard >= TOKEN_5GRAM_JACCARD_MAX:
            events.append(
                {
                    "code": f"token_5gram_jaccard:{scope}",
                    "reference_sha256": reference_hash,
                    "value": _canonical_decimal(token_jaccard),
                }
            )
        character_jaccard = _jaccard(
            cast(set[str], candidate["character_5grams"]),
            cast(set[str], reference["character_5grams"]),
        )
        if character_jaccard >= CHARACTER_5GRAM_JACCARD_MAX:
            events.append(
                {
                    "code": f"character_5gram_jaccard:{scope}",
                    "reference_sha256": reference_hash,
                    "value": _canonical_decimal(character_jaccard),
                }
            )
        semantic_cosine = _semantic_decimal(
            semantic_similarity,
            cast(str, candidate["prompt_text"]),
            cast(str, reference["prompt_text"]),
        )
        if semantic_cosine >= SEMANTIC_COSINE_MAX:
            events.append(
                {
                    "code": f"semantic_cosine:{scope}",
                    "reference_sha256": reference_hash,
                    "value": _canonical_decimal(semantic_cosine),
                }
            )
        return events

    events_by_id: dict[str, list[dict[str, str]]] = {
        cast(str, candidate["candidate_id"]): [] for candidate in projected
    }
    earlier_candidates: list[dict[str, Any]] = []
    for candidate in sorted(
        projected,
        key=lambda row: (
            cast(int, row["generation_round"]),
            selection_key(cast(str, row["candidate_id"])),
        ),
    ):
        candidate_id = cast(str, candidate["candidate_id"])
        events = events_by_id[candidate_id]
        for scope in CONTAMINATION_SCOPES:
            if candidate["semantic_family_id"] in protected_family_snapshot[scope]:
                family_hash = _sha256_bytes(
                    cast(str, candidate["semantic_family_id"]).encode("utf-8")
                )
                events.append(
                    {
                        "code": f"protected_family:{scope}",
                        "reference_sha256": family_hash,
                    }
                )
            for reference in prompt_references[scope]:
                events.extend(prompt_events(candidate, reference, scope))
        for winner in earlier_candidates:
            pair_events = prompt_events(candidate, winner, "current_candidate")
            if candidate["semantic_family_id"] == winner["semantic_family_id"]:
                pair_events.append(
                    {
                        "code": "protected_family:current_candidate",
                        "reference_sha256": _sha256_bytes(
                            cast(str, winner["semantic_family_id"]).encode("utf-8")
                        ),
                    }
                )
            if pair_events:
                winner_id = cast(str, winner["candidate_id"])
                events.extend(
                    {
                        **event,
                        "code": f"current_candidate:{winner_id}:{event['code']}",
                    }
                    for event in pair_events
                )
                break
        earlier_candidates.append(candidate)

    rows = []
    for candidate in projected:
        candidate_id = cast(str, candidate["candidate_id"])
        events = events_by_id[candidate_id]
        rejection_codes = sorted({event["code"] for event in events})
        decision = "REJECT" if rejection_codes else "PASS"
        evidence = {
            "candidate_id": candidate_id,
            "generation_round": candidate["generation_round"],
            "prompt_text_sha256": candidate["prompt_text_sha256"],
            "semantic_family_sha256": _sha256_bytes(
                cast(str, candidate["semantic_family_id"]).encode("utf-8")
            ),
            "scanner_config": scanner_config,
            "events": events,
        }
        rows.append(
            {
                "candidate_id": candidate_id,
                "scanner_decision": decision,
                "rejection_codes": rejection_codes,
                "evidence_sha256": canonical_sha256(evidence),
            }
        )
    return {
        "rows": rows,
        "clean_candidate_ids": [
            cast(str, candidate["candidate_id"])
            for candidate in projected
            if not events_by_id[cast(str, candidate["candidate_id"])]
        ],
        "scanner_config": scanner_config,
    }


def _validated_contamination_scanner_config(value: Any) -> dict[str, Any]:
    fields = {
        "required_semantic_model_id",
        "required_semantic_model_revision",
        "materialized_model_files",
        "materialized_model_files_sha256",
        "semantic_scorer_runtime_verified",
        "semantic_scorer_receipt_sha256",
        "token_5gram_jaccard_reject_at_or_above",
        "character_5gram_jaccard_reject_at_or_above",
        "semantic_cosine_reject_at_or_above",
        "normalization",
        "selection_seed",
        "protected_authority",
        "protected_authority_sha256",
    }
    config = _exact_object_fields(value, fields, "contamination scanner config")
    model_authority = _validated_semantic_model_authority(
        {
            "materialized_model_files": config["materialized_model_files"],
            "materialized_model_files_sha256": config[
                "materialized_model_files_sha256"
            ],
        }
    )
    _require(
        config["required_semantic_model_id"] == SEMANTIC_MODEL_ID
        and config["required_semantic_model_revision"] == SEMANTIC_MODEL_REVISION
        and config["semantic_scorer_runtime_verified"] is False
        and config["semantic_scorer_receipt_sha256"] is None
        and config["token_5gram_jaccard_reject_at_or_above"]
        == str(TOKEN_5GRAM_JACCARD_MAX)
        and config["character_5gram_jaccard_reject_at_or_above"]
        == str(CHARACTER_5GRAM_JACCARD_MAX)
        and config["semantic_cosine_reject_at_or_above"] == str(SEMANTIC_COSINE_MAX)
        and config["normalization"] == "NFKC-casefold-collapse-whitespace"
        and config["selection_seed"] == _SELECTION_AUTHORITY["selection_seed"],
        "contamination scanner configuration drift",
    )
    protected = _exact_object_fields(
        config["protected_authority"],
        set(CONTAMINATION_SCOPES),
        "contamination protected authority",
    )
    protected_fields = {
        "prompt_count",
        "prompt_bytes_sha256",
        "normalized_prompt_list_sha256",
        "family_count",
        "family_ids_sha256",
        "row_projection_sha256",
    }
    for scope in CONTAMINATION_SCOPES:
        row = _exact_object_fields(
            protected[scope], protected_fields, f"{scope} protected authority"
        )
        _require(
            type(row["prompt_count"]) is int
            and row["prompt_count"] >= 0
            and type(row["family_count"]) is int
            and row["family_count"] >= 0,
            "contamination protected authority count mismatch",
        )
        for hash_field in (
            "prompt_bytes_sha256",
            "normalized_prompt_list_sha256",
            "family_ids_sha256",
            "row_projection_sha256",
        ):
            _exact_lowercase_hex(
                row[hash_field],
                length=64,
                label=f"{scope} protected authority {hash_field}",
            )
    protected_hash = _exact_lowercase_hex(
        config["protected_authority_sha256"],
        length=64,
        label="contamination protected authority SHA-256",
    )
    _require(
        protected_hash == canonical_sha256(protected),
        "contamination protected authority hash mismatch",
    )
    return {
        **deepcopy(config),
        **model_authority,
        "protected_authority": deepcopy(protected),
        "protected_authority_sha256": protected_hash,
    }


def _contamination_audit_document(
    scan: dict[str, Any],
    *,
    source_hashes: dict[str, Any],
    candidate_count: int,
    clean_candidate_count: int,
) -> dict[str, Any]:
    scanner_config = _validated_contamination_scanner_config(scan["scanner_config"])
    rows = scan["rows"]
    _require(type(rows) is list, "contamination evidence rows mismatch")
    ledger_hash = _exact_lowercase_hex(
        source_hashes["blind-v2-contamination.jsonl"],
        length=64,
        label="contamination ledger SHA-256",
    )
    return {
        "required_semantic_model_id": scanner_config["required_semantic_model_id"],
        "required_semantic_model_revision": scanner_config[
            "required_semantic_model_revision"
        ],
        "materialized_model_files": deepcopy(
            scanner_config["materialized_model_files"]
        ),
        "materialized_model_files_sha256": scanner_config[
            "materialized_model_files_sha256"
        ],
        "semantic_scorer_runtime_verified": False,
        "semantic_scorer_receipt_sha256": None,
        "token_5gram_jaccard_reject_at_or_above": str(TOKEN_5GRAM_JACCARD_MAX),
        "character_5gram_jaccard_reject_at_or_above": str(CHARACTER_5GRAM_JACCARD_MAX),
        "semantic_cosine_reject_at_or_above": str(SEMANTIC_COSINE_MAX),
        "candidate_count": candidate_count,
        "clean_candidate_count": clean_candidate_count,
        "rejected_candidate_count": candidate_count - clean_candidate_count,
        "ledger_sha256": ledger_hash,
        "scanner_config_sha256": canonical_sha256(scanner_config),
        "protected_authority": deepcopy(scanner_config["protected_authority"]),
        "protected_authority_sha256": scanner_config["protected_authority_sha256"],
        "evidence_sha256": canonical_sha256(rows),
    }


def _json_value_no_duplicate_keys(payload: bytes, label: str) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in values:
            if key in output:
                raise ValueError(f"{label} contains duplicate key: {key}")
            output[key] = value
        return output

    try:
        decoded = payload.decode("utf-8", errors="strict")
        value = json.loads(decoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    return value


def _json_no_duplicate_keys(payload: bytes, label: str) -> dict[str, Any]:
    value = _json_value_no_duplicate_keys(payload, label)
    _require(type(value) is dict, f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _jsonl_no_duplicate_keys(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(payload.splitlines(), start=1):
        if line.strip():
            rows.append(_json_no_duplicate_keys(line, f"{label} line {index}"))
    return rows


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        result.returncode == 0,
        f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
    )
    return result.stdout.strip()


def _validated_commit_a_changed_files(
    preregistration: Mapping[str, Any],
) -> tuple[str, ...]:
    _require(
        type(preregistration.get("commit_a_binding")) is str
        and preregistration.get("commit_a_binding") == COMMIT_A_BINDING,
        "Commit A-agent binding authority mismatch",
    )
    changed_files = preregistration.get("commit_a_changed_files")
    _require_exact_json_authority(
        changed_files,
        list(COMMIT_A_CHANGED_FILES),
        message="Commit A-agent changed-file authority mismatch",
    )
    _require(
        len(COMMIT_A_CHANGED_FILES) == len(set(COMMIT_A_CHANGED_FILES)),
        "Commit A-agent code boundary is not unique",
    )
    return COMMIT_A_CHANGED_FILES


def _validate_preexisting_main_validation_authority(
    preregistration: Mapping[str, Any],
) -> None:
    actual = preregistration.get("preexisting_main_validation")
    _require(
        type(actual) is dict,
        "preexisting main validation authority mismatch",
    )
    actual = cast(dict[str, Any], actual)
    expected_fields = frozenset(PREEXISTING_MAIN_VALIDATION_AUTHORITY)
    _require(
        frozenset(actual) == expected_fields,
        "preexisting main validation field set mismatch",
    )
    local = actual.get("local_full_pytest")
    _require(
        type(local) is dict
        and frozenset(cast(dict[str, Any], local)) == {"failed", "passed"},
        "preexisting local pytest field set mismatch",
    )
    local = cast(dict[str, Any], local)
    _require(
        type(actual.get("github_validate_conclusion")) is str
        and type(actual.get("github_validate_run_id")) is int
        and type(local.get("failed")) is int
        and type(local.get("passed")) is int
        and type(actual.get("not_attributed_to_blind_v2_change")) is bool,
        "preexisting main validation type mismatch",
    )
    expected = {
        "github_validate_conclusion": PREEXISTING_MAIN_VALIDATION_AUTHORITY[
            "github_validate_conclusion"
        ],
        "github_validate_run_id": PREEXISTING_MAIN_VALIDATION_AUTHORITY[
            "github_validate_run_id"
        ],
        "local_full_pytest": dict(
            cast(
                Mapping[str, int],
                PREEXISTING_MAIN_VALIDATION_AUTHORITY["local_full_pytest"],
            )
        ),
        "not_attributed_to_blind_v2_change": (
            PREEXISTING_MAIN_VALIDATION_AUTHORITY["not_attributed_to_blind_v2_change"]
        ),
    }
    _require_exact_json_authority(
        actual,
        expected,
        message="preexisting main validation authority mismatch",
    )


def validate_commit_a_repository(
    repository_root: Path | str, preregistration: dict[str, Any]
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(
        _git(repository, "status", "--porcelain", "--untracked-files=all") == "",
        "Commit A-agent worktree must be clean",
    )
    head = _exact_lowercase_hex(
        _git(repository, "rev-parse", "HEAD"), length=40, label="Commit A-agent"
    )
    origin_main = _exact_lowercase_hex(
        _git(repository, "rev-parse", "origin/main"),
        length=40,
        label="origin/main",
    )
    expected_parent = _exact_lowercase_hex(
        preregistration.get("preregistration_parent_git_commit"),
        length=40,
        label="preregistered origin/main",
    )
    _require(
        expected_parent == PREREGISTRATION_PARENT_COMMIT,
        "preregistered origin/main authority mismatch",
    )
    _require(
        origin_main == expected_parent,
        "origin/main drift from preregistration parent authority",
    )
    _require(
        preregistration.get("supersedes_commit") == HISTORICAL_HUMAN_COMMIT_A,
        "Commit A-agent supersession mismatch",
    )
    _require(
        head != HISTORICAL_HUMAN_COMMIT_A,
        "historical Commit A has been superseded and is not active",
    )
    _require(
        _git(
            repository,
            "merge-base",
            "--is-ancestor",
            HISTORICAL_HUMAN_COMMIT_A,
            head,
        )
        == "",
        "historical Commit A must be an ancestor of Commit A-agent",
    )
    authorized_changed = _validated_commit_a_changed_files(preregistration)
    changed = _git(
        repository,
        "diff",
        "--name-only",
        "--no-renames",
        f"{expected_parent}..{head}",
    ).splitlines()
    _require(
        len(changed) == len(set(changed))
        and len(changed) == len(authorized_changed)
        and set(changed) == set(authorized_changed),
        "Commit A-agent changed-file authority mismatch",
    )
    return {
        "commit_a": head,
        "origin_main": origin_main,
        "supersedes_commit": HISTORICAL_HUMAN_COMMIT_A,
        "changed_files": sorted(changed),
    }


def validate_commit_b_repository(
    repository_root: Path | str, *, commit_a: str
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    _require(
        _git(repository, "status", "--porcelain", "--untracked-files=all") == "",
        "Commit B worktree must be clean",
    )
    commit_a = _exact_lowercase_hex(commit_a, length=40, label="Commit A-agent")
    head = _exact_lowercase_hex(
        _git(repository, "rev-parse", "HEAD"), length=40, label="Commit B"
    )
    parent_line = _git(repository, "rev-list", "--parents", "-n", "1", "HEAD").split()
    _require(
        len(parent_line) == 2 and parent_line[0] == head,
        "Commit B must have exactly one parent and cannot be a merge commit",
    )
    head_parent = _exact_lowercase_hex(
        parent_line[1],
        length=40,
        label="Commit B parent",
    )
    origin_main = _exact_lowercase_hex(
        _git(repository, "rev-parse", "origin/main"),
        length=40,
        label="origin/main",
    )
    _require(
        origin_main == PREREGISTRATION_PARENT_COMMIT,
        "Commit B lineage no longer matches preregistered origin/main",
    )
    _require(head != commit_a, "Commit B must differ from Commit A-agent")
    _require(
        head_parent == commit_a,
        "Commit B must be a direct child of Commit A-agent",
    )
    _require(
        _git(repository, "rev-list", "--count", f"{commit_a}..{head}") == "1",
        "Commit B must be exactly one commit above Commit A-agent",
    )
    _require(
        commit_a != HISTORICAL_HUMAN_COMMIT_A,
        "historical Commit A has been superseded and is not active",
    )
    _require(
        _git(
            repository,
            "merge-base",
            "--is-ancestor",
            HISTORICAL_HUMAN_COMMIT_A,
            commit_a,
        )
        == "",
        "Commit A-agent must descend from historical Commit A",
    )
    changed = _git(
        repository,
        "diff",
        "--name-only",
        "--no-renames",
        f"{commit_a}..{head}",
    ).splitlines()
    expected = {
        (DATASET_FREEZE_RELATIVE / filename).as_posix()
        for filename in DATASET_FREEZE_FILENAMES
    }
    _require(
        len(changed) == len(set(changed)) and set(changed) == expected,
        "Commit B may contain only frozen blind-v2 data",
    )
    for path in sorted(expected):
        entries = _git(repository, "ls-tree", "HEAD", "--", path).splitlines()
        _require(
            len(entries) == 1, "Commit B datasets must be ordinary committed blobs"
        )
        metadata, separator, entry_path = entries[0].partition("\t")
        parts = metadata.split()
        valid_entry = (
            separator == "\t"
            and entry_path == path
            and len(parts) == 3
            and parts[0] in {"100644", "100755"}
            and parts[1] == "blob"
            and len(parts[2]) == 40
            and all(character in "0123456789abcdef" for character in parts[2])
        )
        _require(valid_entry, "Commit B datasets must be ordinary committed blobs")
    return {
        "commit_a": commit_a,
        "commit_b": head,
        "origin_main": origin_main,
        "changed_files": sorted(changed),
    }


def _outside_repository(root: Path, repository_root: Path) -> None:
    resolved = root.resolve(strict=True)
    repository = repository_root.resolve(strict=False)
    _require(resolved.is_dir(), "agent pack root must be a directory")
    _require(
        not resolved.is_relative_to(repository),
        "agent pack root must stay outside the repository",
    )


def _required_agent_pack_file(path: Path, repository_root: Path) -> Path:
    _require(path.exists(), f"missing required agent pack file: {path.name}")
    resolved = path.resolve(strict=True)
    repository = repository_root.resolve(strict=False)
    _require(
        not resolved.is_relative_to(repository),
        f"required agent pack file must stay outside the repository: {path.name}",
    )
    _require(
        not path.is_symlink() and path.is_file() and resolved.is_file(),
        f"required agent pack path must be a regular file: {path.name}",
    )
    return resolved


def _agent_pack_protocol_invalid(
    *,
    failure_stage: str,
    failure_reason: str,
    first_read_timestamp: str,
    source_file_sha256: dict[str, str],
    agent_run_records: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    result = {
        "schema_version": "router-v2-blind-v2-agent-pack-validation-v1",
        "status": "INVALID",
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "research_conclusion": "AGENT_BLIND_V2_PROTOCOL_INVALID",
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "release_authorized": False,
        "default_router_unchanged": True,
        "first_read_timestamp": first_read_timestamp,
        "source_file_sha256": source_file_sha256,
        "model_scores_observed": False,
        "tasks": [],
    }
    if agent_run_records is not None:
        records = deepcopy(agent_run_records)
        retries = [
            retry
            for role in AGENT_CONFIGS
            for record in records[role]
            if (retry := _transport_retry_record(record, role=role)) is not None
        ]
        retries.sort(
            key=lambda row: (
                cast(str, row["role"]),
                cast(str, row["invocation_id"]),
            )
        )
        result.update(
            {
                "agent_run_records": records,
                "agent_run_evidence": {
                    role: _agent_role_run_evidence(role, records[role])
                    for role in AGENT_CONFIGS
                },
                "transport_retry_count": len(retries),
                "retry_records": retries,
            }
        )
    return result


def _agent_pack_infrastructure_inconclusive(
    *,
    failure_stage: str,
    failure_reason: str,
    first_read_timestamp: str,
    source_file_sha256: dict[str, str],
    agent_run_records: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    records = deepcopy(agent_run_records)
    retries = [
        retry
        for role in AGENT_CONFIGS
        for record in records[role]
        if (retry := _transport_retry_record(record, role=role)) is not None
    ]
    retries.sort(
        key=lambda row: (
            cast(str, row["role"]),
            cast(str, row["invocation_id"]),
        )
    )
    return {
        "schema_version": "router-v2-blind-v2-agent-pack-validation-v1",
        "status": "INCONCLUSIVE",
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "research_conclusion": "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
        "router_decision": "KEEP_BASELINE",
        "production_ready": False,
        "release_authorized": False,
        "default_router_unchanged": True,
        "first_read_timestamp": first_read_timestamp,
        "source_file_sha256": source_file_sha256,
        "model_scores_observed": False,
        "agent_run_records": records,
        "agent_run_evidence": {
            role: _agent_role_run_evidence(role, records[role])
            for role in AGENT_CONFIGS
        },
        "transport_retry_count": len(retries),
        "retry_records": retries,
        "tasks": [],
    }


def _transport_retries_exhausted(run_record: dict[str, Any]) -> bool:
    return (
        _validated_invocation_terminal_authority(run_record)
        == "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE"
    )


def _validated_invocation_terminal_authority(
    run_record: dict[str, Any],
) -> str | None:
    attempts = run_record["attempts"]
    exhausted = (
        run_record["transport_retry_count"] == 1
        and len(attempts) == 2
        and all(
            attempt["outcome"] == "TRANSPORT_FAILURE_NO_RESPONSE"
            for attempt in attempts
        )
    )
    if not exhausted:
        return None
    _require(
        run_record["outcome"] == "TRANSPORT_FAILURE_NO_RESPONSE"
        and run_record["response_sha256"] is None
        and run_record["returned_model"] is None
        and run_record["candidate_ids"] == []
        and len(run_record["session_or_thread_ids"]) == 2
        and len(set(run_record["session_or_thread_ids"])) == 2,
        "Agent invocation infrastructure terminal authority mismatch",
    )
    return "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE"


def _pack_invocation_identities(invocations: Any) -> list[str]:
    if type(invocations) is not list:
        return []
    identities: list[str] = []
    for invocation in invocations:
        if type(invocation) is not dict:
            continue
        envelope = invocation.get("envelope")
        identity_source = envelope if type(envelope) is dict else invocation
        fields = {"session_id", "thread_id"}.intersection(identity_source)
        if len(fields) != 1:
            continue
        identity = identity_source[next(iter(fields))]
        if type(identity) is str and identity.strip():
            identities.append(identity)
    return identities


def _sanitized_agent_run_record(
    *,
    role: str,
    candidate_ids: list[str],
    request: dict[str, Any],
    response: dict[str, Any] | None,
    invocations: Any,
    retry_count: int,
) -> dict[str, Any]:
    _require(
        type(candidate_ids) is list
        and all(
            _exact_lowercase_hex(value, length=24, label="candidate id") == value
            for value in candidate_ids
        )
        and len(candidate_ids) == len(set(candidate_ids)),
        "Agent run candidate identities mismatch",
    )
    identities = _pack_invocation_identities(invocations)
    config = AGENT_CONFIGS[role]
    attempts: list[dict[str, Any]] = []
    if type(invocations) is list:
        for ordinal, raw_invocation in enumerate(invocations, start=1):
            invocation = cast(dict[str, Any], raw_invocation)
            envelope = invocation.get("envelope")
            if type(envelope) is not dict:
                attempts.append(
                    {
                        "attempt_ordinal": ordinal,
                        "session_or_thread_id": identities[ordinal - 1],
                        "request_sha256": request["request_sha256"],
                        "requested_model": config["model"],
                        "returned_model": None,
                        "reasoning_effort": config["reasoning_effort"],
                        "transport_failure": True,
                        "response_bytes_present": False,
                        "response_sha256": None,
                        "outcome": "TRANSPORT_FAILURE_NO_RESPONSE",
                    }
                )
                continue
            response_sha256 = canonical_sha256(envelope["response"])
            outcome = (
                "VALID_RESPONSE"
                if ordinal == len(invocations) and response is not None
                else "SUBSTANTIVE_INVALID_RESPONSE"
            )
            attempts.append(
                {
                    "attempt_ordinal": ordinal,
                    "session_or_thread_id": identities[ordinal - 1],
                    "request_sha256": request["request_sha256"],
                    "requested_model": config["model"],
                    "returned_model": envelope["returned_model"],
                    "reasoning_effort": config["reasoning_effort"],
                    "transport_failure": False,
                    "response_bytes_present": True,
                    "response_sha256": response_sha256,
                    "outcome": outcome,
                }
            )
    if attempts:
        final_response_sha256 = attempts[-1]["response_sha256"]
        final_returned_model = attempts[-1]["returned_model"]
        final_outcome = attempts[-1]["outcome"]
    else:
        _require(
            retry_count == 0 and not identities,
            "empty Agent run cannot claim an invocation or retry",
        )
        final_response_sha256 = None
        final_returned_model = None
        final_outcome = "TRANSPORT_FAILURE_NO_RESPONSE"
    return {
        "invocation_id": cast(str, request["request_sha256"])[:24],
        "candidate_ids": list(candidate_ids),
        "request_sha256": request["request_sha256"],
        "response_sha256": final_response_sha256,
        "requested_model": config["model"],
        "returned_model": final_returned_model,
        "reasoning_effort": config["reasoning_effort"],
        "session_or_thread_ids": identities,
        "transport_retry_count": retry_count,
        "outcome": final_outcome,
        "attempts": attempts,
    }


def _transport_retry_record(
    run_record: dict[str, Any], *, role: str
) -> dict[str, Any] | None:
    if run_record["transport_retry_count"] == 0:
        return None
    identities = cast(list[str], run_record["session_or_thread_ids"])
    _require(len(identities) == 2, "transport retry must bind two sessions")
    return {
        "role": role,
        "invocation_id": run_record["invocation_id"],
        "candidate_ids": deepcopy(run_record["candidate_ids"]),
        "request_sha256": run_record["request_sha256"],
        "response_sha256": run_record["response_sha256"],
        "failed_session_or_thread_id": identities[0],
        "retry_session_or_thread_id": identities[1],
        "failed_attempt_ordinal": 1,
        "retry_attempt_ordinal": 2,
        "retry_count": 1,
    }


def _agent_role_run_evidence(
    role: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    config = AGENT_CONFIGS[role]
    prompt = GENERATOR_SYSTEM_PROMPT if role == "generator" else REVIEWER_SYSTEM_PROMPT
    response_schema = (
        GENERATOR_RESPONSE_SCHEMA if role == "generator" else REVIEWER_RESPONSE_SCHEMA
    )
    return {
        "config": deepcopy(config),
        "requested_models": [config["model"]],
        "returned_models": sorted(
            {
                cast(str, record["returned_model"])
                for record in records
                if record["returned_model"] is not None
            }
        ),
        "reasoning_effort": config["reasoning_effort"],
        "system_prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "response_schema_sha256": canonical_sha256(response_schema),
        "request_count": len(records),
        "invocation_count": sum(
            len(cast(list[str], record["session_or_thread_ids"])) for record in records
        ),
        "session_or_thread_ids": [
            identity
            for record in records
            for identity in cast(list[str], record["session_or_thread_ids"])
        ],
        "request_hashes_sha256": canonical_sha256(
            [record["request_sha256"] for record in records]
        ),
        "response_hashes_sha256": canonical_sha256(
            [
                record["response_sha256"]
                for record in records
                if record["response_sha256"] is not None
            ]
        ),
        "run_sha256": canonical_sha256(records),
    }


_REVIEWER_DECISION_PROJECTION_FIELDS = frozenset(
    {
        "candidate_id",
        "reviewer_role",
        "decision",
        "reviewed_gold_skill_id",
        "reviewed_negative_skill_id",
        "natural",
        "single_primary_skill",
        "no_label_leakage",
        "negative_confusable",
        "response_sha256",
    }
)


def _reviewer_decision_rubric_consistent(review: dict[str, Any]) -> bool:
    decision = review.get("decision")
    negative = review.get("reviewed_negative_skill_id")
    return bool(
        {
            "ACCEPT": (
                review.get("natural") is True
                and review.get("single_primary_skill") is True
                and review.get("no_label_leakage") is True
                and (negative is None or review.get("negative_confusable") is True)
            ),
            "REJECT_AMBIGUOUS": review.get("single_primary_skill") is False,
            "REJECT_NOT_CONFUSABLE": (
                negative is not None and review.get("negative_confusable") is False
            ),
            "REJECT_UNNATURAL": review.get("natural") is False,
            "REJECT_LABEL_LEAKAGE": review.get("no_label_leakage") is False,
        }.get(cast(str, decision), False)
    )


def _reviewers_unanimously_accept(
    reviews: tuple[dict[str, Any], dict[str, Any]],
    *,
    expected_labels: tuple[str, str | None],
) -> bool:
    return all(
        review.get("decision") == "ACCEPT"
        and _reviewer_decision_rubric_consistent(review)
        and (
            review.get("reviewed_gold_skill_id"),
            review.get("reviewed_negative_skill_id"),
        )
        == expected_labels
        for review in reviews
    )


def _derive_candidate_pipeline_semantics(
    candidates: dict[str, dict[str, Any]],
    *,
    clean_candidate_ids: set[str],
    review_responses: dict[str, dict[str, dict[str, Any] | None]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    accepted: list[dict[str, Any]] = []
    outcomes: dict[str, str] = {}
    for candidate_id, candidate in candidates.items():
        if candidate_id not in clean_candidate_ids:
            outcomes[candidate_id] = "REJECTED_CONTAMINATION"
            continue
        reviewer_a = review_responses["reviewer_a"].get(candidate_id)
        reviewer_b = review_responses["reviewer_b"].get(candidate_id)
        if reviewer_a is None or reviewer_b is None:
            outcomes[candidate_id] = "REJECTED_INVOCATION"
            continue
        expected_labels = (
            cast(str, candidate["proposed_gold_skill_id"]),
            cast(str | None, candidate["proposed_negative_skill_id"]),
        )
        if not _reviewers_unanimously_accept(
            (reviewer_a, reviewer_b), expected_labels=expected_labels
        ):
            outcomes[candidate_id] = "REJECTED_REVIEW"
            continue
        accepted.append(deepcopy(candidate))
        outcomes[candidate_id] = "ELIGIBLE"
    accepted.sort(key=lambda row: cast(str, row["candidate_id"]))
    return accepted, outcomes


def _deterministically_select_candidates(
    accepted: list[dict[str, Any]], canonical_ids: set[str]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for skill_id in sorted(canonical_ids):
        for stratum, quota_field in (
            ("negative", "final_negative_per_skill"),
            ("positive_only", "final_positive_only_per_skill"),
        ):
            pool = sorted(
                (
                    row
                    for row in accepted
                    if row["proposed_gold_skill_id"] == skill_id
                    and _candidate_stratum(row) == stratum
                ),
                key=lambda row: selection_key(cast(str, row["candidate_id"])),
            )
            selected.extend(
                deepcopy(pool[: cast(int, _SELECTION_AUTHORITY[quota_field])])
            )
    return selected


def _finalized_candidate_outcomes(
    outcomes: dict[str, str], selected: list[dict[str, Any]]
) -> dict[str, str]:
    selected_ids = {cast(str, row["candidate_id"]) for row in selected}
    finalized = dict(
        sorted(
            (
                candidate_id,
                ("SELECTED" if candidate_id in selected_ids else "NOT_SELECTED")
                if outcome == "ELIGIBLE"
                else outcome,
            )
            for candidate_id, outcome in outcomes.items()
        )
    )
    outcomes.clear()
    outcomes.update(finalized)
    return outcomes


def _sanitized_reviewer_decision_row(
    *,
    role: str,
    candidate_id: str,
    response: dict[str, Any] | None,
    run_record: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "candidate_id": candidate_id,
        "reviewer_role": role,
        "decision": None,
        "reviewed_gold_skill_id": None,
        "reviewed_negative_skill_id": None,
        "natural": None,
        "single_primary_skill": None,
        "no_label_leakage": None,
        "negative_confusable": None,
        "response_sha256": run_record["response_sha256"],
    }
    if response is not None:
        for field in (
            "decision",
            "reviewed_gold_skill_id",
            "reviewed_negative_skill_id",
            "natural",
            "single_primary_skill",
            "no_label_leakage",
            "negative_confusable",
        ):
            row[field] = response[field]
    return row


def _reviewer_decision_authority_document(
    rows_by_role: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    body = {
        "schema_version": "router-v2-blind-v2-reviewer-decision-authority-v1",
        "roles": deepcopy(rows_by_role),
    }
    return {**body, "authority_sha256": canonical_sha256(body)}


def _validated_reviewer_decision_authority(
    value: Any,
    *,
    candidate_labels: dict[str, tuple[str, str | None]],
    candidate_outcomes: dict[str, Any],
    reviewer_run_records: dict[str, list[dict[str, Any]]],
    canonical_ids: set[str],
) -> dict[str, Any]:
    authority = _exact_object_fields(
        value,
        {"schema_version", "roles", "authority_sha256"},
        "reviewer decision authority",
    )
    _require(
        authority["schema_version"]
        == "router-v2-blind-v2-reviewer-decision-authority-v1",
        "reviewer decision authority schema mismatch",
    )
    raw_roles = _exact_object_fields(
        authority["roles"],
        {"reviewer_a", "reviewer_b"},
        "reviewer decision authority roles",
    )
    normalized_roles: dict[str, list[dict[str, Any]]] = {}
    role_candidate_ids: dict[str, list[str]] = {}
    for role in ("reviewer_a", "reviewer_b"):
        raw_rows = raw_roles[role]
        records = reviewer_run_records[role]
        _require(
            type(raw_rows) is list and len(raw_rows) == len(records),
            f"{role} reviewer decision coverage mismatch",
        )
        rows: list[dict[str, Any]] = []
        candidate_ids: list[str] = []
        for raw_row, record in zip(raw_rows, records, strict=True):
            row = _exact_object_fields(
                raw_row,
                _REVIEWER_DECISION_PROJECTION_FIELDS,
                f"{role} reviewer decision row",
            )
            candidate_id = _exact_lowercase_hex(
                row["candidate_id"],
                length=24,
                label=f"{role} reviewer decision candidate id",
            )
            _require(
                candidate_id in candidate_labels
                and row["reviewer_role"] == role
                and record["candidate_ids"] == [candidate_id]
                and row["response_sha256"] == record["response_sha256"],
                f"{role} reviewer decision run binding mismatch",
            )
            decision = row["decision"]
            if decision is None:
                _require(
                    all(
                        row[field] is None
                        for field in (
                            "reviewed_gold_skill_id",
                            "reviewed_negative_skill_id",
                            "natural",
                            "single_primary_skill",
                            "no_label_leakage",
                            "negative_confusable",
                        )
                    )
                    and record["outcome"] != "VALID_RESPONSE"
                    and (
                        row["response_sha256"] is None
                        or _exact_lowercase_hex(
                            row["response_sha256"],
                            length=64,
                            label=f"{role} invalid response SHA-256",
                        )
                        == row["response_sha256"]
                    ),
                    f"{role} invalid reviewer decision projection mismatch",
                )
            else:
                _require(
                    decision in AGENT_REVIEW_DECISIONS
                    and record["outcome"] == "VALID_RESPONSE",
                    f"{role} reviewer decision outcome mismatch",
                )
                _exact_lowercase_hex(
                    row["response_sha256"],
                    length=64,
                    label=f"{role} reviewer response SHA-256",
                )
                reviewed_gold = row["reviewed_gold_skill_id"]
                reviewed_negative = row["reviewed_negative_skill_id"]
                _require(
                    type(reviewed_gold) is str
                    and reviewed_gold in canonical_ids
                    and (
                        reviewed_negative is None
                        or (
                            type(reviewed_negative) is str
                            and reviewed_negative in canonical_ids
                            and reviewed_negative != reviewed_gold
                        )
                    )
                    and all(
                        type(row[field]) is bool
                        for field in (
                            "natural",
                            "single_primary_skill",
                            "no_label_leakage",
                        )
                    )
                    and (
                        (
                            reviewed_negative is None
                            and row["negative_confusable"] is None
                        )
                        or (
                            reviewed_negative is not None
                            and type(row["negative_confusable"]) is bool
                        )
                    ),
                    f"{role} reviewer decision label or rubric mismatch",
                )
                _require(
                    _reviewer_decision_rubric_consistent(row),
                    f"{role} reviewer decision rubric mismatch",
                )
            candidate_ids.append(candidate_id)
            rows.append(deepcopy(row))
        _require(
            len(candidate_ids) == len(set(candidate_ids))
            and candidate_ids
            == sorted(
                candidate_ids,
                key=lambda candidate_id: review_schedule_key(role, candidate_id),
            ),
            f"{role} reviewer decision schedule mismatch",
        )
        normalized_roles[role] = rows
        role_candidate_ids[role] = candidate_ids

    reviewed_candidate_ids = set(role_candidate_ids["reviewer_a"])
    _require(
        reviewed_candidate_ids == set(role_candidate_ids["reviewer_b"])
        and reviewed_candidate_ids <= set(candidate_labels)
        and set(candidate_outcomes) == set(candidate_labels),
        "reviewer decision candidate coverage mismatch",
    )
    rows_by_role_and_id = {
        role: {row["candidate_id"]: row for row in normalized_roles[role]}
        for role in ("reviewer_a", "reviewer_b")
    }
    for candidate_id, labels in candidate_labels.items():
        if candidate_id not in reviewed_candidate_ids:
            derived_outcome = "REJECTED_CONTAMINATION"
        else:
            reviews = [
                rows_by_role_and_id[role][candidate_id]
                for role in ("reviewer_a", "reviewer_b")
            ]
            if any(review["decision"] is None for review in reviews):
                derived_outcome = "REJECTED_INVOCATION"
            elif _reviewers_unanimously_accept(
                (reviews[0], reviews[1]), expected_labels=labels
            ):
                derived_outcome = "ELIGIBLE"
            else:
                derived_outcome = "REJECTED_REVIEW"
        claimed_outcome = candidate_outcomes[candidate_id]
        _require(
            (
                derived_outcome == "ELIGIBLE"
                and claimed_outcome in {"ELIGIBLE", "SELECTED", "NOT_SELECTED"}
            )
            or claimed_outcome == derived_outcome,
            "reviewer decision candidate outcome mismatch",
        )
    normalized_body = {
        "schema_version": authority["schema_version"],
        "roles": normalized_roles,
    }
    _require(
        authority["authority_sha256"] == canonical_sha256(normalized_body),
        "reviewer decision authority hash mismatch",
    )
    return {**normalized_body, "authority_sha256": authority["authority_sha256"]}


_AGENT_ROLE_LEDGER_PATHS = {
    "generator": "blind-v2-generation.jsonl",
    "reviewer_a": "blind-v2-review-a.jsonl",
    "reviewer_b": "blind-v2-review-b.jsonl",
}


def _agent_run_identity_authority(
    records_by_role: dict[str, list[dict[str, Any]]],
    metadata_roles: dict[str, Any],
    source_file_sha256: dict[str, Any],
) -> dict[str, Any]:
    roles: dict[str, dict[str, Any]] = {}
    all_sessions: list[str] = []
    for role, config in AGENT_CONFIGS.items():
        records = records_by_role[role]
        metadata = _exact_object_fields(
            metadata_roles[role],
            {
                "config",
                "request_count",
                "invocation_count",
                "session_or_thread_ids",
                "fork_context",
                "history_message_count",
                "imported_memory_count",
            },
            f"{role} metadata",
        )
        invocation_ids = [cast(str, record["invocation_id"]) for record in records]
        candidate_ids = [
            candidate_id
            for record in records
            for candidate_id in cast(list[str], record["candidate_ids"])
        ]
        sessions = [
            identity
            for record in records
            for identity in cast(list[str], record["session_or_thread_ids"])
        ]
        _require(metadata["config"] == config, f"{role} metadata config mismatch")
        _require(
            metadata["request_count"] == len(records),
            f"{role} metadata request count mismatch",
        )
        _require(
            metadata["invocation_count"] == len(sessions),
            f"{role} metadata invocation count mismatch",
        )
        _require(
            metadata["session_or_thread_ids"] == sessions,
            f"{role} metadata session binding mismatch",
        )
        _require(
            len(invocation_ids) == len(set(invocation_ids)),
            f"{role} invocation identities must be unique",
        )
        _require(
            len(candidate_ids) == len(set(candidate_ids)),
            f"{role} candidate identities must be unique",
        )
        all_sessions.extend(sessions)
        ledger_path = _AGENT_ROLE_LEDGER_PATHS[role]
        ledger_hash = _exact_lowercase_hex(
            source_file_sha256[ledger_path],
            length=64,
            label=f"{role} ledger file SHA-256",
        )
        roles[role] = {
            "ledger_path": ledger_path,
            "ledger_file_sha256": ledger_hash,
            "invocation_ids": invocation_ids,
            "invocation_ids_sha256": canonical_sha256(invocation_ids),
            "candidate_ids": candidate_ids,
            "candidate_ids_sha256": canonical_sha256(candidate_ids),
            "request_count": len(records),
            "invocation_count": len(sessions),
            "session_or_thread_ids": sessions,
            "session_or_thread_ids_sha256": canonical_sha256(sessions),
        }
    _require(
        len(all_sessions) == len(set(all_sessions)),
        "Agent run sessions must be globally unique",
    )
    _require(
        {
            candidate_id
            for record in records_by_role["reviewer_a"]
            for candidate_id in cast(list[str], record["candidate_ids"])
        }
        == {
            candidate_id
            for record in records_by_role["reviewer_b"]
            for candidate_id in cast(list[str], record["candidate_ids"])
        },
        "reviewer candidate identity sets mismatch",
    )
    _require(
        {
            candidate_id
            for record in records_by_role["reviewer_a"]
            for candidate_id in cast(list[str], record["candidate_ids"])
        }
        <= {
            candidate_id
            for record in records_by_role["generator"]
            for candidate_id in cast(list[str], record["candidate_ids"])
        },
        "reviewer candidate identities must come from generation",
    )
    return {"roles": roles, "authority_sha256": canonical_sha256(roles)}


class _AgentPackProtocolViolation(Exception):
    pass


_PACK_PROTOCOL_FIELDS = frozenset(
    {
        "role",
        "session_id",
        "thread_id",
        "fork_context",
        "history_message_count",
        "imported_memory_count",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "timeout_seconds",
        "transport_retry_count",
        "request_sha256",
    }
)


def _pack_protocol_require(condition: bool, message: str) -> None:
    if not condition:
        raise _AgentPackProtocolViolation(message)


def _validate_pack_protocol_fields(
    value: dict[str, Any],
    *,
    request: dict[str, Any],
    require_returned_model: bool,
    require_transport_retry_count: bool,
    non_protocol_fields: set[str],
) -> set[str]:
    identity_fields = {"session_id", "thread_id"}.intersection(value)
    _pack_protocol_require(
        len(identity_fields) == 1,
        "exactly one session/thread id is required",
    )
    required_fields = {
        "role",
        "fork_context",
        "history_message_count",
        "imported_memory_count",
        "requested_model",
        "reasoning_effort",
        "timeout_seconds",
        "request_sha256",
        *identity_fields,
    }
    if require_returned_model:
        required_fields.add("returned_model")
    if require_transport_retry_count:
        required_fields.add("transport_retry_count")
    _pack_protocol_require(
        set(value) == required_fields | non_protocol_fields,
        "agent invocation protocol fields mismatch",
    )
    identity = value[next(iter(identity_fields))]
    _pack_protocol_require(
        type(identity) is str and bool(identity.strip()),
        "session/thread id must be non-empty",
    )
    role = cast(str, request["role"])
    config = AGENT_CONFIGS[role]
    _pack_protocol_require(value["role"] == role, "agent invocation role mismatch")
    _pack_protocol_require(value["fork_context"] is False, "fork context must be false")
    _pack_protocol_require(
        type(value["history_message_count"]) is int
        and value["history_message_count"] == 0,
        "history message count must be integer zero",
    )
    _pack_protocol_require(
        type(value["imported_memory_count"]) is int
        and value["imported_memory_count"] == 0,
        "imported memory count must be integer zero",
    )
    _pack_protocol_require(
        value["requested_model"] == config["model"],
        "requested model mismatch",
    )
    if "returned_model" in value:
        _pack_protocol_require(
            type(value["returned_model"]) is str
            and bool(value["returned_model"].strip()),
            "returned model must be non-empty",
        )
    _pack_protocol_require(
        value["reasoning_effort"] == config["reasoning_effort"],
        "reasoning effort mismatch",
    )
    _pack_protocol_require(
        type(value["timeout_seconds"]) is int
        and value["timeout_seconds"] == config["timeout_seconds"],
        "timeout mismatch",
    )
    _pack_protocol_require(
        value["request_sha256"] == request["request_sha256"],
        "request SHA-256 mismatch",
    )
    if "transport_retry_count" in value:
        _pack_protocol_require(
            type(value["transport_retry_count"]) is int
            and value["transport_retry_count"] in {0, 1},
            "transport retry count must be integer zero or one",
        )
    return identity_fields


def _audit_pack_invocation_protocol(
    invocation: dict[str, Any],
    *,
    request: dict[str, Any],
) -> None:
    top_level_protocol_fields = _PACK_PROTOCOL_FIELDS.intersection(invocation)
    if "envelope" in invocation and not top_level_protocol_fields:
        _pack_protocol_require(
            set(invocation)
            == {"transport_failure", "response_bytes_present", "envelope"},
            "successful invocation fields mismatch",
        )
        _pack_protocol_require(
            invocation["transport_failure"] is False,
            "successful invocation transport_failure must be false",
        )
        _pack_protocol_require(
            invocation["response_bytes_present"] is True,
            "successful invocation response_bytes_present must be true",
        )
        envelope = invocation["envelope"]
        _pack_protocol_require(
            type(envelope) is dict,
            "successful invocation envelope must be an object",
        )
        _validate_pack_protocol_fields(
            cast(dict[str, Any], envelope),
            request=request,
            require_returned_model=True,
            require_transport_retry_count=True,
            non_protocol_fields={"response"},
        )
        return
    if top_level_protocol_fields:
        _validate_pack_protocol_fields(
            invocation,
            request=request,
            require_returned_model=False,
            require_transport_retry_count=False,
            non_protocol_fields={"transport_failure", "response_bytes_present"},
        )
        _pack_protocol_require(
            invocation["transport_failure"] is True,
            "transport failure record transport_failure must be true",
        )
        _pack_protocol_require(
            invocation["response_bytes_present"] is False,
            "transport failure record response_bytes_present must be false",
        )
        return
    raise _AgentPackProtocolViolation("invocation record schema mismatch")


def _validate_pack_invocations(
    invocations: Any, *, request: dict[str, Any]
) -> tuple[dict[str, Any] | None, int]:
    if type(invocations) is not list:
        raise _AgentPackProtocolViolation("invocations must be a list")
    try:
        for invocation in invocations:
            _pack_protocol_require(
                type(invocation) is dict,
                "invocation record must be an object",
            )
            _audit_pack_invocation_protocol(
                cast(dict[str, Any], invocation),
                request=request,
            )
        _pack_protocol_require(
            len(invocations) in {1, 2},
            "Agent invocation allows one substantive attempt and at most one retry",
        )
        first = cast(dict[str, Any], invocations[0])
        success = cast(dict[str, Any], invocations[-1])
        if "envelope" not in success:
            _pack_protocol_require(
                all(
                    "envelope" not in cast(dict[str, Any], invocation)
                    for invocation in invocations
                ),
                "transport retry cannot follow a substantive response",
            )
            return None, len(invocations) - 1
        _pack_protocol_require(
            len(invocations) == 1 or "envelope" not in first,
            "a second substantive response is prohibited",
        )
        retry_count = len(invocations) - 1
        envelope = cast(dict[str, Any], success["envelope"])
        _pack_protocol_require(
            envelope["transport_retry_count"] == retry_count,
            "transport retry count does not match allowed invocation combination",
        )
        try:
            response = validate_agent_invocation_envelope(envelope, request=request)
        except (KeyError, TypeError, ValueError):
            return None, retry_count
        return response, retry_count
    except _AgentPackProtocolViolation:
        raise
    except (KeyError, TypeError, ValueError):
        return None, 0


def _preflight_invocation_terminal_authority(
    generation_rows: list[dict[str, Any]],
    review_rows_by_role: dict[str, list[dict[str, Any]]],
) -> tuple[str, dict[str, Any]] | None:
    rows_by_role = {
        "generator": generation_rows,
        "reviewer_a": review_rows_by_role["reviewer_a"],
        "reviewer_b": review_rows_by_role["reviewer_b"],
    }
    for role, rows in rows_by_role.items():
        for raw_row in rows:
            _pack_protocol_require(
                type(raw_row) is dict, "ledger row must be an object"
            )
            row = cast(dict[str, Any], raw_row)
            request = row.get("request")
            _pack_protocol_require(
                type(request) is dict,
                "ledger request must be an object",
            )
            invocations = row.get("invocations")
            if not (
                type(invocations) is list
                and len(invocations) == 2
                and all(
                    type(invocation) is dict and "envelope" not in invocation
                    for invocation in invocations
                )
            ):
                continue
            response, retry_count = _validate_pack_invocations(
                invocations,
                request=cast(dict[str, Any], request),
            )
            _require(
                response is None and retry_count == 1,
                "Agent invocation infrastructure terminal authority mismatch",
            )
            run_record = _sanitized_agent_run_record(
                role=role,
                candidate_ids=[],
                request=cast(dict[str, Any], request),
                response=None,
                invocations=invocations,
                retry_count=retry_count,
            )
            _require(
                _validated_invocation_terminal_authority(run_record)
                == "AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE",
                "Agent invocation infrastructure terminal authority mismatch",
            )
            return role, run_record
    return None


def _candidate_stratum(candidate: dict[str, Any]) -> str:
    return (
        "negative"
        if candidate["proposed_negative_skill_id"] is not None
        else "positive_only"
    )


def _stratum_counts(
    rows: list[dict[str, Any]], canonical_ids: set[str]
) -> dict[str, dict[str, int]]:
    counts = {
        skill_id: {"negative": 0, "positive_only": 0}
        for skill_id in sorted(canonical_ids)
    }
    for row in rows:
        counts[cast(str, row["proposed_gold_skill_id"])][_candidate_stratum(row)] += 1
    return counts


def _request_quota_distribution(
    quota_counts: Counter[tuple[int, str, str]],
    round_number: int,
    canonical_ids: set[str],
) -> dict[str, dict[str, int]]:
    return {
        skill_id: {
            stratum: quota_counts[(round_number, skill_id, stratum)]
            for stratum in ("negative", "positive_only")
        }
        for skill_id in sorted(canonical_ids)
    }


def _deficit_document(
    rows: list[dict[str, Any]], canonical_ids: set[str]
) -> dict[str, dict[str, int]]:
    return {
        skill_id: deficits
        for skill_id, deficits in _complete_deficit_document(
            rows, canonical_ids
        ).items()
        if any(deficits.values())
    }


def _complete_deficit_document(
    rows: list[dict[str, Any]], canonical_ids: set[str]
) -> dict[str, dict[str, int]]:
    counts = _stratum_counts(rows, canonical_ids)
    return {
        skill_id: {
            "negative": max(
                0,
                cast(int, _SELECTION_AUTHORITY["final_negative_per_skill"])
                - skill_counts["negative"],
            ),
            "positive_only": max(
                0,
                cast(int, _SELECTION_AUTHORITY["final_positive_only_per_skill"])
                - skill_counts["positive_only"],
            ),
        }
        for skill_id, skill_counts in counts.items()
    }


_GENERATION_AUTHORITY_FIELDS = {
    "schema_version",
    "source_ledger_sha256",
    "requests",
    "authority_sha256",
}
_GENERATION_AUTHORITY_REQUEST_FIELDS = {
    "invocation_id",
    "request_sha256",
    "generation_round",
    "gold_skill_id",
    "negative_quota",
    "positive_only_quota",
    "response_outcome",
    "response_sha256",
    "candidate_count",
    "candidates",
}
_GENERATION_AUTHORITY_CANDIDATE_FIELDS = {
    "candidate_index",
    "candidate_id",
    "prompt_text_sha256",
    "semantic_family_id",
    "gold_skill_id",
    "negative_skill_id",
    "stratum",
}


def _generation_authority_request_document(
    *,
    request: dict[str, Any],
    response: dict[str, Any] | None,
    run_record: dict[str, Any],
) -> dict[str, Any]:
    quota = cast(dict[str, Any], cast(dict[str, Any], request["input"])["quota"])
    response_sha256 = run_record["response_sha256"]
    candidates = []
    if response is not None:
        _require(
            type(response_sha256) is str,
            "valid generator response must bind response SHA-256",
        )
        for generated in sorted(
            cast(list[dict[str, Any]], response["candidates"]),
            key=lambda candidate: cast(int, candidate["candidate_index"]),
        ):
            negative = generated["proposed_negative_skill_id"]
            prompt_text = cast(str, generated["prompt_text"])
            candidates.append(
                {
                    "candidate_index": generated["candidate_index"],
                    "candidate_id": opaque_candidate_id(
                        cast(int, quota["round_number"]),
                        cast(str, quota["gold_skill_id"]),
                        cast(int, generated["candidate_index"]),
                        cast(str, response_sha256),
                    ),
                    "prompt_text_sha256": _sha256_bytes(
                        prompt_text.encode("utf-8", errors="strict")
                    ),
                    "semantic_family_id": generated["semantic_family_id"],
                    "gold_skill_id": generated["proposed_gold_skill_id"],
                    "negative_skill_id": negative,
                    "stratum": (
                        "negative" if negative is not None else "positive_only"
                    ),
                }
            )
    return {
        "invocation_id": run_record["invocation_id"],
        "request_sha256": run_record["request_sha256"],
        "generation_round": quota["round_number"],
        "gold_skill_id": quota["gold_skill_id"],
        "negative_quota": quota["negative_quota"],
        "positive_only_quota": quota["positive_only_quota"],
        "response_outcome": run_record["outcome"],
        "response_sha256": response_sha256,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def _generation_authority_document(
    requests: list[dict[str, Any]], *, source_ledger_sha256: str
) -> dict[str, Any]:
    document = {
        "schema_version": "router-v2-generation-authority-v1",
        "source_ledger_sha256": source_ledger_sha256,
        "requests": deepcopy(requests),
    }
    return {**document, "authority_sha256": canonical_sha256(document)}


def _validated_generation_authority(
    value: Any,
    *,
    source_ledger_sha256: str,
    canonical_ids: set[str],
    candidate_outcomes: dict[str, Any],
    generator_run_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    authority = _exact_object_fields(
        value, _GENERATION_AUTHORITY_FIELDS, "generation authority"
    )
    expected_source_hash = _exact_lowercase_hex(
        source_ledger_sha256,
        length=64,
        label="generation source ledger SHA-256",
    )
    _require(
        authority["schema_version"] == "router-v2-generation-authority-v1"
        and authority["source_ledger_sha256"] == expected_source_hash,
        "generation authority source mismatch",
    )
    unhashed = {
        key: value for key, value in authority.items() if key != "authority_sha256"
    }
    _require(
        authority["authority_sha256"] == canonical_sha256(unhashed),
        "generation authority aggregate mismatch",
    )
    raw_requests = authority["requests"]
    _require(
        type(raw_requests) is list
        and type(generator_run_records) is list
        and len(raw_requests) == len(generator_run_records),
        "generation authority request coverage mismatch",
    )
    _require(len(canonical_ids) == 16, "generation canonical skill count mismatch")

    normalized_requests: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    request_keys: list[tuple[int, str]] = []
    for raw_request, run_record in zip(
        raw_requests, generator_run_records, strict=True
    ):
        request = _exact_object_fields(
            raw_request,
            _GENERATION_AUTHORITY_REQUEST_FIELDS,
            "generation authority request",
        )
        invocation_id = _exact_lowercase_hex(
            request["invocation_id"], length=24, label="generation invocation id"
        )
        request_sha256 = _exact_lowercase_hex(
            request["request_sha256"],
            length=64,
            label="generation request SHA-256",
        )
        generation_round = request["generation_round"]
        gold_skill_id = request["gold_skill_id"]
        negative_quota = request["negative_quota"]
        positive_only_quota = request["positive_only_quota"]
        outcome = request["response_outcome"]
        response_sha256 = request["response_sha256"]
        raw_candidates = request["candidates"]
        _require(
            invocation_id == request_sha256[:24]
            and type(generation_round) is int
            and generation_round in {1, 2}
            and type(gold_skill_id) is str
            and gold_skill_id in canonical_ids
            and type(negative_quota) is int
            and negative_quota >= 0
            and type(positive_only_quota) is int
            and positive_only_quota >= 0
            and negative_quota + positive_only_quota > 0
            and outcome
            in {
                "VALID_RESPONSE",
                "SUBSTANTIVE_INVALID_RESPONSE",
                "TRANSPORT_FAILURE_NO_RESPONSE",
            }
            and type(raw_candidates) is list,
            "generation authority request semantics mismatch",
        )
        request_key = (cast(int, generation_round), cast(str, gold_skill_id))
        _require(
            request_key not in request_keys,
            "duplicate generation authority request",
        )
        request_keys.append(request_key)
        _require(
            run_record.get("invocation_id") == invocation_id
            and run_record.get("request_sha256") == request_sha256
            and run_record.get("response_sha256") == response_sha256
            and run_record.get("outcome") == outcome,
            "generation authority run binding mismatch",
        )

        normalized_candidates: list[dict[str, Any]] = []
        for raw_candidate in raw_candidates:
            candidate = _exact_object_fields(
                raw_candidate,
                _GENERATION_AUTHORITY_CANDIDATE_FIELDS,
                "generation candidate authority",
            )
            candidate_index = candidate["candidate_index"]
            candidate_id = _exact_lowercase_hex(
                candidate["candidate_id"],
                length=24,
                label="generation candidate id",
            )
            prompt_text_sha256 = _exact_lowercase_hex(
                candidate["prompt_text_sha256"],
                length=64,
                label="generation candidate prompt SHA-256",
            )
            semantic_family_id = _nonempty_string(
                candidate["semantic_family_id"],
                "generation candidate semantic family",
            )
            negative_skill_id = candidate["negative_skill_id"]
            _require(
                type(candidate_index) is int
                and candidate_index >= 0
                and candidate["gold_skill_id"] == gold_skill_id
                and (
                    negative_skill_id is None
                    or (
                        type(negative_skill_id) is str
                        and negative_skill_id in canonical_ids
                        and negative_skill_id != gold_skill_id
                    )
                )
                and candidate["stratum"]
                == ("negative" if negative_skill_id is not None else "positive_only"),
                "generation candidate authority mismatch",
            )
            _require(
                type(response_sha256) is str
                and candidate_id
                == opaque_candidate_id(
                    cast(int, generation_round),
                    cast(str, gold_skill_id),
                    cast(int, candidate_index),
                    response_sha256,
                ),
                "generation candidate opaque identity mismatch",
            )
            normalized_candidate = deepcopy(candidate)
            normalized_candidate["prompt_text_sha256"] = prompt_text_sha256
            normalized_candidate["semantic_family_id"] = semantic_family_id
            normalized_candidates.append(normalized_candidate)
            all_candidates.append(
                {
                    **normalized_candidate,
                    "generation_round": generation_round,
                    "response_sha256": response_sha256,
                }
            )

        candidate_ids = [
            cast(str, candidate["candidate_id"]) for candidate in normalized_candidates
        ]
        if outcome == "VALID_RESPONSE":
            _exact_lowercase_hex(
                response_sha256,
                length=64,
                label="generation response SHA-256",
            )
            expected_count = cast(int, negative_quota) + cast(int, positive_only_quota)
            _require(
                request["candidate_count"] == expected_count
                and len(normalized_candidates) == expected_count
                and [
                    cast(int, candidate["candidate_index"])
                    for candidate in normalized_candidates
                ]
                == list(range(expected_count))
                and sum(
                    candidate["stratum"] == "negative"
                    for candidate in normalized_candidates
                )
                == negative_quota
                and sum(
                    candidate["stratum"] == "positive_only"
                    for candidate in normalized_candidates
                )
                == positive_only_quota
                and run_record.get("candidate_ids") == candidate_ids,
                "valid generation response candidate authority mismatch",
            )
        else:
            _require(
                request["candidate_count"] == 0
                and not normalized_candidates
                and run_record.get("candidate_ids") == []
                and (
                    (
                        outcome == "TRANSPORT_FAILURE_NO_RESPONSE"
                        and response_sha256 is None
                    )
                    or (
                        outcome == "SUBSTANTIVE_INVALID_RESPONSE"
                        and _exact_lowercase_hex(
                            response_sha256,
                            length=64,
                            label="invalid generation response SHA-256",
                        )
                        == response_sha256
                    )
                ),
                "invalid generation response candidate authority mismatch",
            )
        normalized_requests.append(
            {**deepcopy(request), "candidates": normalized_candidates}
        )

    all_candidate_ids = [
        cast(str, candidate["candidate_id"]) for candidate in all_candidates
    ]
    _require(
        len(all_candidate_ids) == len(set(all_candidate_ids))
        and set(candidate_outcomes) == set(all_candidate_ids),
        "generation candidate outcome coverage mismatch",
    )
    expected_round_one_keys = [(1, skill_id) for skill_id in sorted(canonical_ids)]
    round_one_requests = [
        request for request in normalized_requests if request["generation_round"] == 1
    ]
    round_two_requests = [
        request for request in normalized_requests if request["generation_round"] == 2
    ]
    _require(
        request_keys
        == expected_round_one_keys
        + [(2, request["gold_skill_id"]) for request in round_two_requests]
        and [request["gold_skill_id"] for request in round_two_requests]
        == sorted(request["gold_skill_id"] for request in round_two_requests)
        and all(
            request["response_outcome"] == "VALID_RESPONSE"
            and request["negative_quota"]
            == _SELECTION_AUTHORITY["round_1_negative_per_skill"]
            and request["positive_only_quota"]
            == _SELECTION_AUTHORITY["round_1_positive_only_per_skill"]
            for request in round_one_requests
        ),
        "canonical generation request schedule mismatch",
    )

    def distribution(round_number: int) -> dict[str, dict[str, int]]:
        counts = {
            skill_id: {"negative": 0, "positive_only": 0}
            for skill_id in sorted(canonical_ids)
        }
        for candidate in all_candidates:
            if candidate["generation_round"] == round_number:
                counts[cast(str, candidate["gold_skill_id"])][
                    cast(str, candidate["stratum"])
                ] += 1
        return counts

    def request_distribution(round_number: int) -> dict[str, dict[str, int]]:
        counts = {
            skill_id: {"negative": 0, "positive_only": 0}
            for skill_id in sorted(canonical_ids)
        }
        for request in normalized_requests:
            if request["generation_round"] == round_number:
                counts[cast(str, request["gold_skill_id"])]["negative"] += cast(
                    int, request["negative_quota"]
                )
                counts[cast(str, request["gold_skill_id"])]["positive_only"] += cast(
                    int, request["positive_only_quota"]
                )
        return counts

    round_one_distribution = distribution(1)
    round_two_distribution = distribution(2)
    round_one_request_distribution = request_distribution(1)
    round_two_request_distribution = request_distribution(2)
    _require(
        sum(sum(counts.values()) for counts in round_one_distribution.values())
        == _SELECTION_AUTHORITY["round_1_candidate_count"]
        and round_one_distribution == round_one_request_distribution,
        "canonical round-one generation authority mismatch",
    )
    accepted_outcomes = {"ELIGIBLE", "SELECTED", "NOT_SELECTED"}
    accepted_projection = sorted(
        (
            {
                "candidate_id": candidate["candidate_id"],
                "generation_round": candidate["generation_round"],
                "candidate_index": candidate["candidate_index"],
                "response_sha256": candidate["response_sha256"],
                "prompt_text_sha256": candidate["prompt_text_sha256"],
                "semantic_family_id": candidate["semantic_family_id"],
                "gold_skill_id": candidate["gold_skill_id"],
                "negative_skill_id": candidate["negative_skill_id"],
                "stratum": candidate["stratum"],
            }
            for candidate in all_candidates
            if candidate_outcomes[candidate["candidate_id"]] in accepted_outcomes
        ),
        key=lambda candidate: cast(str, candidate["candidate_id"]),
    )
    round_one_eligible_counts = {
        skill_id: {"negative": 0, "positive_only": 0}
        for skill_id in sorted(canonical_ids)
    }
    for candidate in all_candidates:
        if (
            candidate["generation_round"] == 1
            and candidate_outcomes[candidate["candidate_id"]] in accepted_outcomes
        ):
            round_one_eligible_counts[cast(str, candidate["gold_skill_id"])][
                cast(str, candidate["stratum"])
            ] += 1
    deficits = {
        skill_id: {
            "negative": max(
                0,
                cast(int, _SELECTION_AUTHORITY["final_negative_per_skill"])
                - counts["negative"],
            ),
            "positive_only": max(
                0,
                cast(int, _SELECTION_AUTHORITY["final_positive_only_per_skill"])
                - counts["positive_only"],
            ),
        }
        for skill_id, counts in round_one_eligible_counts.items()
    }
    expected_round_two_distribution = {
        skill_id: {
            stratum: cast(int, _SELECTION_AUTHORITY["round_2_deficit_multiplier"])
            * deficit
            for stratum, deficit in counts.items()
        }
        for skill_id, counts in deficits.items()
    }
    expected_round_two_skills = [
        skill_id
        for skill_id, counts in expected_round_two_distribution.items()
        if any(counts.values())
    ]
    _require(
        [request["gold_skill_id"] for request in round_two_requests]
        == expected_round_two_skills
        and round_two_distribution == expected_round_two_distribution
        and round_two_request_distribution == expected_round_two_distribution,
        "canonical round-two generation authority mismatch",
    )
    semantics = {
        "observed_generation_rounds": {1} | ({2} if round_two_requests else set()),
        "round_1_candidate_count": sum(
            sum(counts.values()) for counts in round_one_distribution.values()
        ),
        "round_2_candidate_count": sum(
            sum(counts.values()) for counts in round_two_distribution.values()
        ),
        "round_1_distribution": round_one_distribution,
        "round_2_distribution": round_two_distribution,
        "round_1_request_quota_distribution": round_one_request_distribution,
        "round_2_request_quota_distribution": round_two_request_distribution,
        "round_1_post_pipeline_deficits": deficits,
        "accepted_projection": accepted_projection,
        "candidate_outcomes": candidate_outcomes,
    }
    normalized = {
        **deepcopy(authority),
        "requests": normalized_requests,
    }
    return normalized, semantics


_SELECTION_AUDIT_FIELDS = {
    "selection_authority",
    "selection_authority_sha256",
    "accepted_pool_sha256",
    "round_1_candidate_count",
    "round_2_candidate_count",
    "round_1_distribution",
    "round_2_distribution",
    "round_1_request_quota_distribution",
    "round_2_request_quota_distribution",
    "round_1_post_pipeline_deficits",
    "selected_candidate_ids",
    "selected_candidate_ids_sha256",
    "selected_by_stratum",
}


def _validated_selection_audit_semantics(
    value: Any,
    *,
    generation_semantics: dict[str, Any],
    selected_rows: list[dict[str, Any]],
    canonical_ids: set[str],
    id_field: str,
    gold_field: str,
    negative_field: str,
    require_complete_selection: bool,
    validate_selected_semantics: bool = True,
    selection_audit_sha256: Any | None = None,
) -> dict[str, Any]:
    selection = _exact_object_fields(value, _SELECTION_AUDIT_FIELDS, "selection audit")
    _require(len(canonical_ids) == 16, "canonical selection skill count mismatch")
    sorted_ids = sorted(canonical_ids)
    authority = _selection_authority_document()
    _require(
        selection["selection_authority"] == authority
        and selection["selection_authority_sha256"] == canonical_sha256(authority),
        "selection authority mismatch",
    )
    accepted_projection = generation_semantics["accepted_projection"]
    _require(
        type(accepted_projection) is list
        and selection["accepted_pool_sha256"] == canonical_sha256(accepted_projection),
        "accepted pool authority mismatch",
    )
    accepted_by_id = {
        cast(str, candidate["candidate_id"]): candidate
        for candidate in accepted_projection
    }
    if validate_selected_semantics:
        _require(
            len(accepted_by_id) == len(accepted_projection)
            and all(
                row[id_field] in accepted_by_id
                and row["prompt_text_sha256"]
                == accepted_by_id[cast(str, row[id_field])]["prompt_text_sha256"]
                and row["semantic_family_id"]
                == accepted_by_id[cast(str, row[id_field])]["semantic_family_id"]
                and row[gold_field]
                == accepted_by_id[cast(str, row[id_field])]["gold_skill_id"]
                and row[negative_field]
                == accepted_by_id[cast(str, row[id_field])]["negative_skill_id"]
                and ("negative" if row[negative_field] is not None else "positive_only")
                == accepted_by_id[cast(str, row[id_field])]["stratum"]
                and (
                    "source_type" not in row or row["source_type"] == "AGENT_GENERATED"
                )
                for row in selected_rows
            ),
            "selected task generation semantic mismatch",
        )

    _require(
        generation_semantics["observed_generation_rounds"]
        == ({1} | ({2} if generation_semantics["round_2_candidate_count"] else set()))
        and selection["round_1_candidate_count"]
        == generation_semantics["round_1_candidate_count"]
        == _SELECTION_AUTHORITY["round_1_candidate_count"]
        and selection["round_1_distribution"]
        == generation_semantics["round_1_distribution"]
        and selection["round_1_request_quota_distribution"]
        == generation_semantics["round_1_request_quota_distribution"],
        "round-one selection audit mismatch",
    )

    deficits = _exact_object_fields(
        selection["round_1_post_pipeline_deficits"],
        set(sorted_ids),
        "round-one post-pipeline deficits",
    )
    normalized_deficits: dict[str, dict[str, int]] = {}
    for skill_id in sorted_ids:
        counts = _exact_object_fields(
            deficits[skill_id],
            {"negative", "positive_only"},
            f"{skill_id} round-one deficit",
        )
        _require(
            all(type(count) is int and count >= 0 for count in counts.values()),
            "round-one deficit count mismatch",
        )
        normalized_deficits[skill_id] = cast(dict[str, int], counts)

    _require(
        normalized_deficits == generation_semantics["round_1_post_pipeline_deficits"],
        "round-one post-pipeline deficit authority mismatch",
    )

    expected_round_two_distribution = {
        skill_id: {
            stratum: deficit
            * cast(int, _SELECTION_AUTHORITY["round_2_deficit_multiplier"])
            for stratum, deficit in normalized_deficits[skill_id].items()
        }
        for skill_id in sorted_ids
    }
    round_two_count = sum(
        sum(counts.values()) for counts in expected_round_two_distribution.values()
    )
    _require(
        generation_semantics["round_2_distribution"] == expected_round_two_distribution
        and generation_semantics["round_2_request_quota_distribution"]
        == expected_round_two_distribution
        and selection["round_2_distribution"]
        == generation_semantics["round_2_distribution"]
        and selection["round_2_request_quota_distribution"]
        == generation_semantics["round_2_request_quota_distribution"]
        and type(selection["round_2_candidate_count"]) is int
        and selection["round_2_candidate_count"]
        == generation_semantics["round_2_candidate_count"]
        == round_two_count,
        "round-two selection audit mismatch",
    )

    selected_ids = [cast(str, row[id_field]) for row in selected_rows]
    expected_selected_ids = [
        cast(str, candidate["candidate_id"])
        for skill_id in sorted_ids
        for stratum, quota_field in (
            ("negative", "final_negative_per_skill"),
            ("positive_only", "final_positive_only_per_skill"),
        )
        for candidate in sorted(
            (
                candidate
                for candidate in accepted_projection
                if candidate["gold_skill_id"] == skill_id
                and candidate["stratum"] == stratum
            ),
            key=lambda candidate: selection_key(cast(str, candidate["candidate_id"])),
        )[: cast(int, _SELECTION_AUTHORITY[quota_field])]
    ]
    expected_selected_id_set = set(expected_selected_ids)
    selected_by_stratum = {
        skill_id: {
            stratum: [
                cast(str, row[id_field])
                for row in selected_rows
                if row[gold_field] == skill_id
                and ("negative" if row[negative_field] is not None else "positive_only")
                == stratum
            ]
            for stratum in ("negative", "positive_only")
        }
        for skill_id in sorted_ids
    }
    if require_complete_selection:
        _require(
            len(selected_ids) == POSITIVE_TASK_COUNT
            and len(set(selected_ids)) == POSITIVE_TASK_COUNT
            and sum(len(strata["negative"]) for strata in selected_by_stratum.values())
            == TEMPTING_NEGATIVE_COUNT
            and all(
                len(strata["negative"])
                == _SELECTION_AUTHORITY["final_negative_per_skill"]
                and len(strata["positive_only"])
                == _SELECTION_AUTHORITY["final_positive_only_per_skill"]
                for strata in selected_by_stratum.values()
            )
            and selected_ids == expected_selected_ids
            and all(
                generation_semantics["candidate_outcomes"][candidate_id]
                == (
                    "SELECTED"
                    if candidate_id in expected_selected_id_set
                    else "NOT_SELECTED"
                )
                for candidate_id in (
                    cast(str, candidate["candidate_id"])
                    for candidate in accepted_projection
                )
            ),
            "selected canonical quota mismatch",
        )
    else:
        _require(not selected_ids, "insufficient selection must be empty")
    _require(
        selection["selected_candidate_ids"] == selected_ids
        and selection["selected_candidate_ids_sha256"] == canonical_sha256(selected_ids)
        and selection["selected_by_stratum"] == selected_by_stratum,
        "selected identity audit mismatch",
    )
    if selection_audit_sha256 is not None:
        aggregate = _exact_lowercase_hex(
            selection_audit_sha256,
            length=64,
            label="selection audit SHA-256",
        )
        _require(
            aggregate == canonical_sha256(selection),
            "selection audit aggregate mismatch",
        )
    return deepcopy(selection)


def _selection_audit_document(
    *,
    generation_semantics: dict[str, Any],
    selected: list[dict[str, Any]],
    canonical_ids: set[str],
) -> dict[str, Any]:
    authority_document = _selection_authority_document()
    selected_ids = [cast(str, row["candidate_id"]) for row in selected]
    selected_by_stratum = {
        skill_id: {
            stratum: [
                cast(str, row["candidate_id"])
                for row in selected
                if row["proposed_gold_skill_id"] == skill_id
                and _candidate_stratum(row) == stratum
            ]
            for stratum in ("negative", "positive_only")
        }
        for skill_id in sorted(canonical_ids)
    }
    document = {
        "selection_authority": authority_document,
        "selection_authority_sha256": canonical_sha256(authority_document),
        "accepted_pool_sha256": canonical_sha256(
            generation_semantics["accepted_projection"]
        ),
        "round_1_candidate_count": generation_semantics["round_1_candidate_count"],
        "round_2_candidate_count": generation_semantics["round_2_candidate_count"],
        "round_1_distribution": deepcopy(generation_semantics["round_1_distribution"]),
        "round_2_distribution": deepcopy(generation_semantics["round_2_distribution"]),
        "round_1_request_quota_distribution": deepcopy(
            generation_semantics["round_1_request_quota_distribution"]
        ),
        "round_2_request_quota_distribution": deepcopy(
            generation_semantics["round_2_request_quota_distribution"]
        ),
        "round_1_post_pipeline_deficits": deepcopy(
            generation_semantics["round_1_post_pipeline_deficits"]
        ),
        "selected_candidate_ids": selected_ids,
        "selected_candidate_ids_sha256": canonical_sha256(selected_ids),
        "selected_by_stratum": selected_by_stratum,
    }
    return _validated_selection_audit_semantics(
        document,
        generation_semantics=generation_semantics,
        selected_rows=selected,
        canonical_ids=canonical_ids,
        id_field="candidate_id",
        gold_field="proposed_gold_skill_id",
        negative_field="proposed_negative_skill_id",
        require_complete_selection=bool(selected),
    )


def validate_agent_pack(
    root: Path | str,
    *,
    repository_root: Path | str,
    canonical_skills: list[dict[str, Any]],
    train_prompts: list[str],
    pilot_prompts: list[str],
    phase16_prompts: list[str],
    train_family_ids: set[str],
    pilot_family_ids: set[str],
    phase16_family_ids: set[str],
    prior_candidate_prompts: list[str],
    prior_candidate_family_ids: set[str],
    first_read_timestamp: str,
    semantic_similarity: SemanticSimilarity,
    semantic_model_authority: dict[str, Any],
    construction_input_bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate sealed Agent ledgers without loading Arm A/C or scoring routes."""

    projected_skills = _project_canonical_skills(canonical_skills)
    canonical_ids = _canonical_skill_ids(projected_skills)
    for label, prompts in (
        ("train prompts", train_prompts),
        ("pilot prompts", pilot_prompts),
        ("Phase 16 prompts", phase16_prompts),
        ("prior candidate prompts", prior_candidate_prompts),
    ):
        _require(
            type(prompts) is list and all(type(prompt) is str for prompt in prompts),
            f"{label} must be a string list",
        )
    for label, family_ids in (
        ("train family ids", train_family_ids),
        ("pilot family ids", pilot_family_ids),
        ("Phase 16 family ids", phase16_family_ids),
        ("prior candidate family ids", prior_candidate_family_ids),
    ):
        _require(
            type(family_ids) is set
            and all(type(family_id) is str for family_id in family_ids),
            f"{label} must be a string set",
        )
    _nonempty_string(first_read_timestamp, "first read timestamp")
    _require(callable(semantic_similarity), "semantic similarity must be callable")
    sealed_protected_prompts = {
        "train": train_prompts,
        "pilot-002": pilot_prompts,
        "phase16": phase16_prompts,
        "prior_candidate": prior_candidate_prompts,
    }
    sealed_protected_family_ids = {
        "train": train_family_ids,
        "pilot-002": pilot_family_ids,
        "phase16": phase16_family_ids,
        "prior_candidate": prior_candidate_family_ids,
    }
    construction_authority_error: ValueError | None = None
    try:
        _require(
            type(construction_input_bindings) is dict,
            "construction input bindings are required",
        )
        derived_prompts, derived_family_ids = (
            _protected_inputs_from_sealed_construction_bindings(
                construction_input_bindings
            )
        )
        _require(
            derived_prompts == sealed_protected_prompts
            and derived_family_ids == sealed_protected_family_ids,
            "parallel protected construction inputs differ from sealed bindings",
        )
        _require(
            derived_prompts["prior_candidate"] == []
            and derived_family_ids["prior_candidate"] == set(),
            "prior-candidate contamination authority must be empty unless sealed",
        )
        sealed_protected_prompts = derived_prompts
        sealed_protected_family_ids = derived_family_ids
        construction_authority = _construction_input_authority(
            bindings=construction_input_bindings,
            projected_skills=projected_skills,
            protected_prompts=sealed_protected_prompts,
            protected_family_ids=sealed_protected_family_ids,
        )
    except ValueError as exc:
        construction_authority = None
        construction_authority_error = exc

    pack_root = Path(root)
    repository_path = Path(repository_root)
    _outside_repository(pack_root, repository_path)
    required_paths = {
        filename: _required_agent_pack_file(
            pack_root / filename,
            repository_path,
        )
        for filename in REQUIRED_AGENT_PACK_FILES
    }

    source_hashes: dict[str, str] = {}
    try:
        payloads = {
            filename: required_paths[filename].read_bytes()
            for filename in REQUIRED_AGENT_PACK_FILES
        }
        source_hashes = {
            filename: _sha256_bytes(payload) for filename, payload in payloads.items()
        }
        generation_rows = _jsonl_no_duplicate_keys(
            payloads[REQUIRED_AGENT_PACK_FILES[0]], REQUIRED_AGENT_PACK_FILES[0]
        )
        review_rows_by_role = {
            "reviewer_a": _jsonl_no_duplicate_keys(
                payloads[REQUIRED_AGENT_PACK_FILES[1]],
                REQUIRED_AGENT_PACK_FILES[1],
            ),
            "reviewer_b": _jsonl_no_duplicate_keys(
                payloads[REQUIRED_AGENT_PACK_FILES[2]],
                REQUIRED_AGENT_PACK_FILES[2],
            ),
        }
        contamination_rows = _jsonl_no_duplicate_keys(
            payloads[REQUIRED_AGENT_PACK_FILES[3]],
            REQUIRED_AGENT_PACK_FILES[3],
        )
        metadata = _json_no_duplicate_keys(
            payloads[REQUIRED_AGENT_PACK_FILES[4]],
            REQUIRED_AGENT_PACK_FILES[4],
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="ledger_structure",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )
    if construction_authority_error is not None:
        return _agent_pack_protocol_invalid(
            failure_stage="contamination_ledger",
            failure_reason=str(construction_authority_error),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        metadata = _exact_object_fields(
            metadata,
            {
                "schema_version",
                "first_read_timestamp",
                "roles",
                "review_schedule_sha256",
                "selection_authority",
                "source_file_sha256",
            },
            "agent run metadata",
        )
        _require(
            metadata["schema_version"] == "router-v2-blind-v2-agent-run-metadata-v1",
            "agent run metadata schema mismatch",
        )
        _require(
            metadata["first_read_timestamp"] == first_read_timestamp,
            "first read timestamp mismatch",
        )
        metadata_source_hashes = _exact_object_fields(
            metadata["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES[:-1]),
            "metadata source hashes",
        )
        for filename in REQUIRED_AGENT_PACK_FILES[:-1]:
            _exact_lowercase_hex(
                metadata_source_hashes[filename],
                length=64,
                label=f"{filename} source hash",
            )
            _require(
                metadata_source_hashes[filename] == source_hashes[filename],
                f"{filename} source hash mismatch",
            )
        metadata_roles = _exact_object_fields(
            metadata["roles"], set(AGENT_CONFIGS), "metadata roles"
        )
        role_fields = {
            "config",
            "request_count",
            "invocation_count",
            "session_or_thread_ids",
            "fork_context",
            "history_message_count",
            "imported_memory_count",
        }
        for role, config in AGENT_CONFIGS.items():
            role_metadata = _exact_object_fields(
                metadata_roles[role], role_fields, f"{role} metadata"
            )
            role_config = _exact_object_fields(
                role_metadata["config"],
                {"model", "reasoning_effort", "timeout_seconds"},
                f"{role} config",
            )
            for field in ("model", "reasoning_effort"):
                _nonempty_string(role_config[field], f"{role} config {field}")
                _require(
                    role_config[field] == config[field],
                    f"{role} config {field} mismatch",
                )
            _require(
                type(role_config["timeout_seconds"]) is int
                and role_config["timeout_seconds"] == config["timeout_seconds"],
                f"{role} config timeout_seconds mismatch",
            )
            for field in ("request_count", "invocation_count"):
                _require(
                    type(role_metadata[field]) is int and role_metadata[field] >= 0,
                    f"{role} {field} must be a non-negative integer",
                )
            session_ids = role_metadata["session_or_thread_ids"]
            _require(
                type(session_ids) is list
                and all(type(value) is str and value.strip() for value in session_ids)
                and len(session_ids) == len(set(session_ids)),
                f"{role} session/thread metadata mismatch",
            )
            _require(role_metadata["fork_context"] is False, "fork context mismatch")
            _require(
                type(role_metadata["history_message_count"]) is int
                and role_metadata["history_message_count"] == 0,
                "history metadata mismatch",
            )
            _require(
                type(role_metadata["imported_memory_count"]) is int
                and role_metadata["imported_memory_count"] == 0,
                "memory metadata mismatch",
            )
        metadata_schedules = _exact_object_fields(
            metadata["review_schedule_sha256"],
            {"reviewer_a", "reviewer_b"},
            "review schedules",
        )
        for role in ("reviewer_a", "reviewer_b"):
            _exact_lowercase_hex(
                metadata_schedules[role], length=64, label=f"{role} schedule hash"
            )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="agent_run_metadata",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        selection_authority_document = _selection_authority_document()
        metadata_selection_authority = _exact_object_fields(
            metadata["selection_authority"],
            set(selection_authority_document),
            "selection authority",
        )
        _require(
            _canonical_contract_json_equal(
                metadata_selection_authority, selection_authority_document
            ),
            "selection authority drift",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="selection_authority",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        invocation_terminal = _preflight_invocation_terminal_authority(
            generation_rows,
            review_rows_by_role,
        )
    except _AgentPackProtocolViolation as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="invocation_protocol",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="invocation_protocol",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )
    if invocation_terminal is not None:
        role, run_record = invocation_terminal
        terminal_records: dict[str, list[dict[str, Any]]] = {
            agent_role: [] for agent_role in AGENT_CONFIGS
        }
        terminal_records[role].append(run_record)
        return _agent_pack_infrastructure_inconclusive(
            failure_stage="agent_invocation_transport",
            failure_reason=f"{role} transport retry exhausted without response",
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
            agent_run_records=terminal_records,
        )

    candidates: dict[str, dict[str, Any]] = {}
    generation_request_quota_counts: Counter[tuple[int, str, str]] = Counter()
    generation_request_keys: list[tuple[int, str]] = []
    actual_sessions: dict[str, list[str]] = {
        "generator": [],
        "reviewer_a": [],
        "reviewer_b": [],
    }
    actual_invocation_counts = dict.fromkeys(actual_sessions, 0)
    valid_transport_retry_count = 0
    sanitized_run_records: dict[str, list[dict[str, Any]]] = {
        "generator": [],
        "reviewer_a": [],
        "reviewer_b": [],
    }
    generation_authority_requests: list[dict[str, Any]] = []
    retry_records: list[dict[str, Any]] = []
    try:
        for raw_row in generation_rows:
            row, request, quota = _validated_generation_source_row(
                raw_row,
                projected_skills=projected_skills,
                canonical_ids=canonical_ids,
                label="generation row",
            )
            generation_round = cast(int, row["generation_round"])
            gold = cast(str, row["gold_skill_id"])
            request_key = (generation_round, gold)
            _require(
                request_key not in generation_request_keys,
                "generator request round/skill identities must be unique",
            )
            generation_request_keys.append(request_key)
            generation_request_quota_counts[(generation_round, gold, "negative")] += (
                cast(int, quota["negative_quota"])
            )
            generation_request_quota_counts[
                (generation_round, gold, "positive_only")
            ] += cast(int, quota["positive_only_quota"])
            invocations = row["invocations"]
            actual_sessions["generator"].extend(
                _pack_invocation_identities(invocations)
            )
            if type(invocations) is list:
                actual_invocation_counts["generator"] += len(invocations)
            response, retry_count = _validate_pack_invocations(
                invocations, request=request
            )
            derived_candidates = (
                []
                if response is None
                else _derived_generator_candidates(response, request)
            )
            run_record = _sanitized_agent_run_record(
                role="generator",
                candidate_ids=[
                    cast(str, candidate["candidate_id"])
                    for candidate in derived_candidates
                ],
                request=request,
                response=response,
                invocations=invocations,
                retry_count=retry_count,
            )
            sanitized_run_records["generator"].append(run_record)
            if _transport_retries_exhausted(run_record):
                return _agent_pack_infrastructure_inconclusive(
                    failure_stage="agent_invocation_transport",
                    failure_reason="generator transport retry exhausted without response",
                    first_read_timestamp=first_read_timestamp,
                    source_file_sha256=source_hashes,
                    agent_run_records=sanitized_run_records,
                )
            generation_authority_requests.append(
                _generation_authority_request_document(
                    request=request,
                    response=response,
                    run_record=run_record,
                )
            )
            retry_record = _transport_retry_record(run_record, role="generator")
            if retry_record is not None:
                retry_records.append(retry_record)
            valid_transport_retry_count += retry_count
            for candidate in derived_candidates:
                candidate_id = cast(str, candidate["candidate_id"])
                _require(
                    candidate_id not in candidates,
                    "candidate ids must be unique",
                )
                candidates[candidate_id] = candidate
    except _AgentPackProtocolViolation as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="invocation_protocol",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="generation_ledger",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    try:
        _require(
            all(
                round_number in {1, 2}
                for round_number, _gold in generation_request_keys
            ),
            "generation is limited to rounds one and two",
        )
        expected_round_one_request_keys = [
            (1, skill_id) for skill_id in sorted(canonical_ids)
        ]
        round_two_request_keys = [key for key in generation_request_keys if key[0] == 2]
        _require(
            generation_request_keys
            == expected_round_one_request_keys + sorted(round_two_request_keys),
            "round 1 must contain one canonical request per skill",
        )
        round_one_candidates = [
            candidate
            for candidate in candidates.values()
            if candidate["generation_round"] == 1
        ]
        round_two_candidates = [
            candidate
            for candidate in candidates.values()
            if candidate["generation_round"] == 2
        ]
        _require(
            len(round_one_candidates)
            == _SELECTION_AUTHORITY["round_1_candidate_count"],
            "round 1 must contain exactly 256 candidates",
        )
        round_one_distribution = _stratum_counts(round_one_candidates, canonical_ids)
        round_one_request_quota_distribution = _request_quota_distribution(
            generation_request_quota_counts, 1, canonical_ids
        )
        _require(
            all(
                counts
                == {
                    "negative": _SELECTION_AUTHORITY["round_1_negative_per_skill"],
                    "positive_only": _SELECTION_AUTHORITY[
                        "round_1_positive_only_per_skill"
                    ],
                }
                for counts in round_one_distribution.values()
            ),
            "round 1 per-skill stratum distribution mismatch",
        )
        _require(
            round_one_request_quota_distribution == round_one_distribution,
            "round 1 request quota authority mismatch",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="generation_rounds",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
            agent_run_records=sanitized_run_records,
        )

    try:
        for raw_row in contamination_rows:
            row = _exact_object_fields(
                raw_row,
                {
                    "candidate_id",
                    "scanner_decision",
                    "rejection_codes",
                    "evidence_sha256",
                },
                "contamination row",
            )
            _exact_lowercase_hex(
                row["candidate_id"], length=24, label="contamination candidate id"
            )
            _require(
                row["scanner_decision"] in {"PASS", "REJECT"},
                "contamination scanner decision mismatch",
            )
            _require(
                type(row["rejection_codes"]) is list
                and all(type(code) is str for code in row["rejection_codes"]),
                "contamination rejection codes mismatch",
            )
            _exact_lowercase_hex(
                row["evidence_sha256"],
                length=64,
                label="contamination evidence hash",
            )
        contamination_scan = _scan_contamination(
            list(candidates.values()),
            protected_prompts=sealed_protected_prompts,
            protected_family_ids=sealed_protected_family_ids,
            semantic_similarity=semantic_similarity,
            semantic_model_authority=semantic_model_authority,
        )
        _require(
            _canonical_contract_json_equal(
                contamination_rows, contamination_scan["rows"]
            ),
            "contamination ledger evidence mismatch",
        )
        clean_candidate_ids = set(contamination_scan["clean_candidate_ids"])
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="contamination_ledger",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    review_responses: dict[str, dict[str, dict[str, Any] | None]] = {
        "reviewer_a": {},
        "reviewer_b": {},
    }
    reviewer_decision_rows: dict[str, list[dict[str, Any]]] = {
        "reviewer_a": [],
        "reviewer_b": [],
    }
    actual_review_orders: dict[str, list[str]] = {
        "reviewer_a": [],
        "reviewer_b": [],
    }
    for role, role_rows in review_rows_by_role.items():
        try:
            for raw_row in role_rows:
                row, candidate_id, request = _validated_reviewer_source_row(
                    raw_row,
                    role=role,
                    candidates=candidates,
                    projected_skills=projected_skills,
                    clean_candidate_ids=clean_candidate_ids,
                    label=f"{role} row",
                )
                _require(
                    candidate_id not in review_responses[role],
                    "review candidate ids must be unique",
                )
                actual_review_orders[role].append(candidate_id)
                invocations = row["invocations"]
                actual_sessions[role].extend(_pack_invocation_identities(invocations))
                if type(invocations) is list:
                    actual_invocation_counts[role] += len(invocations)
                response, retry_count = _validate_pack_invocations(
                    invocations, request=request
                )
                terminal_candidate_ids = (
                    []
                    if response is None
                    and retry_count == 1
                    and all(
                        type(invocation) is dict and "envelope" not in invocation
                        for invocation in cast(list[Any], invocations)
                    )
                    else [candidate_id]
                )
                run_record = _sanitized_agent_run_record(
                    role=role,
                    candidate_ids=terminal_candidate_ids,
                    request=request,
                    response=response,
                    invocations=invocations,
                    retry_count=retry_count,
                )
                sanitized_run_records[role].append(run_record)
                reviewer_decision_rows[role].append(
                    _sanitized_reviewer_decision_row(
                        role=role,
                        candidate_id=candidate_id,
                        response=response,
                        run_record=run_record,
                    )
                )
                if _transport_retries_exhausted(run_record):
                    return _agent_pack_infrastructure_inconclusive(
                        failure_stage="agent_invocation_transport",
                        failure_reason=(
                            f"{role} transport retry exhausted without response"
                        ),
                        first_read_timestamp=first_read_timestamp,
                        source_file_sha256=source_hashes,
                        agent_run_records=sanitized_run_records,
                    )
                retry_record = _transport_retry_record(run_record, role=role)
                if retry_record is not None:
                    retry_records.append(retry_record)
                valid_transport_retry_count += retry_count
                review_responses[role][candidate_id] = response
            _require(
                set(review_responses[role]) == clean_candidate_ids,
                f"{role} must review every contamination-clean candidate",
            )
        except _AgentPackProtocolViolation as exc:
            return _agent_pack_protocol_invalid(
                failure_stage="invocation_protocol",
                failure_reason=str(exc),
                first_read_timestamp=first_read_timestamp,
                source_file_sha256=source_hashes,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return _agent_pack_protocol_invalid(
                failure_stage="reviewer_request",
                failure_reason=str(exc),
                first_read_timestamp=first_read_timestamp,
                source_file_sha256=source_hashes,
            )

    try:
        request_counts = {
            "generator": len(generation_rows),
            "reviewer_a": len(review_rows_by_role["reviewer_a"]),
            "reviewer_b": len(review_rows_by_role["reviewer_b"]),
        }
        all_actual_sessions = [
            session
            for role in ("generator", "reviewer_a", "reviewer_b")
            for session in actual_sessions[role]
        ]
        _require(
            len(all_actual_sessions) == len(set(all_actual_sessions)),
            "session/thread ids must be globally unique",
        )
        all_metadata_sessions: list[str] = []
        for role in ("generator", "reviewer_a", "reviewer_b"):
            role_metadata = cast(dict[str, Any], metadata_roles[role])
            _require(
                role_metadata["request_count"] == request_counts[role],
                f"{role} request count mismatch",
            )
            _require(
                role_metadata["invocation_count"] == actual_invocation_counts[role],
                f"{role} invocation count mismatch",
            )
            _require(
                role_metadata["session_or_thread_ids"] == actual_sessions[role],
                f"{role} session/thread binding mismatch",
            )
            all_metadata_sessions.extend(role_metadata["session_or_thread_ids"])
        _require(
            len(all_metadata_sessions) == len(set(all_metadata_sessions)),
            "metadata session/thread ids must be globally unique",
        )
        for role in ("reviewer_a", "reviewer_b"):
            expected_schedule_order = sorted(
                clean_candidate_ids,
                key=lambda value: review_schedule_key(role, value),
            )
            _require(
                actual_review_orders[role] == expected_schedule_order,
                f"{role} ledger schedule mismatch",
            )
            _require(
                metadata_schedules[role]
                == canonical_sha256(actual_review_orders[role]),
                f"{role} schedule hash mismatch",
            )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="agent_run_metadata",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    accepted, candidate_outcomes = _derive_candidate_pipeline_semantics(
        candidates,
        clean_candidate_ids=clean_candidate_ids,
        review_responses=review_responses,
    )

    round_one_accepted = [
        candidate for candidate in accepted if candidate["generation_round"] == 1
    ]
    round_one_deficits = _deficit_document(round_one_accepted, canonical_ids)
    round_two_distribution = _stratum_counts(round_two_candidates, canonical_ids)
    round_two_request_quota_distribution = _request_quota_distribution(
        generation_request_quota_counts, 2, canonical_ids
    )
    try:
        for skill_id in sorted(canonical_ids):
            deficits = round_one_deficits.get(
                skill_id, {"negative": 0, "positive_only": 0}
            )
            _require(
                round_two_distribution[skill_id]
                == {
                    stratum: deficit
                    * cast(int, _SELECTION_AUTHORITY["round_2_deficit_multiplier"])
                    for stratum, deficit in deficits.items()
                },
                "round 2 candidate count must equal twice each post-pipeline deficit",
            )
            _require(
                round_two_request_quota_distribution[skill_id]
                == round_two_distribution[skill_id],
                "round 2 request quota authority mismatch",
            )
    except (KeyError, TypeError, ValueError) as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="generation_rounds",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )

    final_deficits = _deficit_document(accepted, canonical_ids)
    contamination_audit = _contamination_audit_document(
        contamination_scan,
        source_hashes=source_hashes,
        candidate_count=len(candidates),
        clean_candidate_count=len(clean_candidate_ids),
    )

    pipeline_rejected_count = sum(
        outcome.startswith("REJECTED") for outcome in candidate_outcomes.values()
    )
    generation_authority, generation_semantics = _validated_generation_authority(
        _generation_authority_document(
            generation_authority_requests,
            source_ledger_sha256=source_hashes["blind-v2-generation.jsonl"],
        ),
        source_ledger_sha256=source_hashes["blind-v2-generation.jsonl"],
        canonical_ids=canonical_ids,
        candidate_outcomes=candidate_outcomes,
        generator_run_records=sanitized_run_records["generator"],
    )
    agent_run_identity_authority = _agent_run_identity_authority(
        sanitized_run_records,
        cast(dict[str, Any], metadata_roles),
        source_hashes,
    )
    reviewer_decision_authority = _validated_reviewer_decision_authority(
        _reviewer_decision_authority_document(reviewer_decision_rows),
        candidate_labels={
            candidate_id: (
                cast(str, candidate["proposed_gold_skill_id"]),
                cast(str | None, candidate["proposed_negative_skill_id"]),
            )
            for candidate_id, candidate in candidates.items()
        },
        candidate_outcomes=candidate_outcomes,
        reviewer_run_records={
            role: sanitized_run_records[role] for role in ("reviewer_a", "reviewer_b")
        },
        canonical_ids=canonical_ids,
    )

    common_result = {
        "schema_version": "router-v2-blind-v2-agent-pack-validation-v1",
        "transport_retry_count": valid_transport_retry_count,
        "retry_records": sorted(
            retry_records,
            key=lambda row: (
                cast(str, row["role"]),
                cast(str, row["invocation_id"]),
            ),
        ),
        "agent_roles": deepcopy(metadata_roles),
        "agent_run_records": deepcopy(sanitized_run_records),
        "generation_authority": generation_authority,
        "reviewer_decision_authority": reviewer_decision_authority,
        "agent_run_evidence": {
            role: _agent_role_run_evidence(role, sanitized_run_records[role])
            for role in AGENT_CONFIGS
        },
        "agent_run_identity_authority": agent_run_identity_authority,
        "canonical_skills_authority": deepcopy(projected_skills),
        "construction_input_authority": deepcopy(construction_authority),
        "construction_input_source_bindings": deepcopy(construction_input_bindings),
        "contamination_source_authority": {
            "scanner_config": deepcopy(contamination_scan["scanner_config"]),
            "rows": deepcopy(contamination_scan["rows"]),
            "clean_candidate_ids": list(contamination_scan["clean_candidate_ids"]),
        },
        "review_schedule_sha256": deepcopy(metadata_schedules),
        "source_file_sha256": source_hashes,
        "source_file_bytes": {
            filename: payload.hex() for filename, payload in payloads.items()
        },
        "first_read_timestamp": first_read_timestamp,
        "model_scores_observed": False,
        "contamination_audit": contamination_audit,
        "exact_three_way_agreement_count": len(accepted),
        "pipeline_rejected_candidate_count": pipeline_rejected_count,
    }
    if final_deficits:
        insufficient_selection_audit = _selection_audit_document(
            generation_semantics=generation_semantics,
            selected=[],
            canonical_ids=canonical_ids,
        )
        return {
            **common_result,
            "status": "INSUFFICIENT",
            "failure_stage": "deterministic_selection",
            "research_conclusion": "AGENT_BLIND_V2_DATASET_INSUFFICIENT",
            "router_decision": "KEEP_BASELINE",
            "production_ready": False,
            "release_authorized": False,
            "default_router_unchanged": True,
            "task_count": 0,
            "negative_labeled_task_count": 0,
            "family_count": 0,
            "excluded_candidate_count": len(candidates),
            "candidate_outcomes": dict(sorted(candidate_outcomes.items())),
            "deficits": final_deficits,
            "ledger_sha256": deepcopy(source_hashes),
            "selection_audit": insufficient_selection_audit,
            "selection_audit_sha256": canonical_sha256(insufficient_selection_audit),
            "tasks": [],
        }

    try:
        selected = _deterministically_select_candidates(accepted, canonical_ids)
        selected_ids = {cast(str, row["candidate_id"]) for row in selected}
        candidate_outcomes = _finalized_candidate_outcomes(candidate_outcomes, selected)
        selected_prompt_bytes = {
            cast(str, row["prompt_text"]).encode("utf-8") for row in selected
        }
        selected_normalized_prompts = {
            _normalize(cast(str, row["prompt_text"])) for row in selected
        }
        selected_families = {cast(str, row["semantic_family_id"]) for row in selected}
        selected_negative_rows = [
            row for row in selected if row["proposed_negative_skill_id"] is not None
        ]
        _validate_deterministic_selection(
            selected,
            selected_ids=selected_ids,
            selected_prompt_bytes=selected_prompt_bytes,
            selected_normalized_prompts=selected_normalized_prompts,
            selected_families=selected_families,
            selected_negative_rows=selected_negative_rows,
            canonical_ids=canonical_ids,
        )
        gold_counts = Counter(row["proposed_gold_skill_id"] for row in selected)
        negative_counts = Counter(
            row["proposed_negative_skill_id"] for row in selected_negative_rows
        )
        selected_selection_audit = _selection_audit_document(
            generation_semantics=generation_semantics,
            selected=selected,
            canonical_ids=canonical_ids,
        )
        return {
            **common_result,
            "status": "VALID",
            "task_count": len(selected),
            "negative_labeled_task_count": len(selected_negative_rows),
            "family_count": len(selected_families),
            "gold_distribution": dict(sorted(gold_counts.items())),
            "negative_distribution": dict(
                sorted(
                    (cast(str, key), value) for key, value in negative_counts.items()
                )
            ),
            "negative_target_coverage_count": len(negative_counts),
            "excluded_candidate_count": len(candidates) - len(selected),
            "selection_not_selected_count": sum(
                outcome == "NOT_SELECTED" for outcome in candidate_outcomes.values()
            ),
            "candidate_outcomes": dict(sorted(candidate_outcomes.items())),
            "selection_audit": selected_selection_audit,
            "selection_audit_sha256": canonical_sha256(selected_selection_audit),
            "tasks": selected,
        }
    except _DeterministicSelectionProtocolViolation as exc:
        return _agent_pack_protocol_invalid(
            failure_stage="deterministic_selection",
            failure_reason=str(exc),
            first_read_timestamp=first_read_timestamp,
            source_file_sha256=source_hashes,
        )


def _validated_agent_lineage_evidence(
    validation: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    records_by_role = validation.get("agent_run_records")
    _require(
        type(records_by_role) is dict and set(records_by_role) == set(AGENT_CONFIGS),
        "Agent run or retry evidence mismatch",
    )
    role_records = cast(dict[str, Any], records_by_role)
    validated_records: dict[str, list[dict[str, Any]]] = {}
    record_fields = {
        "invocation_id",
        "candidate_ids",
        "request_sha256",
        "response_sha256",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "session_or_thread_ids",
        "transport_retry_count",
        "outcome",
        "attempts",
    }
    attempt_fields = {
        "attempt_ordinal",
        "session_or_thread_id",
        "request_sha256",
        "requested_model",
        "returned_model",
        "reasoning_effort",
        "transport_failure",
        "response_bytes_present",
        "response_sha256",
        "outcome",
    }
    for role, config in AGENT_CONFIGS.items():
        raw_records = role_records[role]
        _require(type(raw_records) is list, "Agent run or retry evidence mismatch")
        records: list[dict[str, Any]] = []
        invocation_ids: set[str] = set()
        role_candidate_ids: set[str] = set()
        for raw_record in raw_records:
            try:
                record = _exact_object_fields(
                    raw_record, record_fields, f"{role} sanitized run record"
                )
                invocation_id = _exact_lowercase_hex(
                    record["invocation_id"], length=24, label="run invocation id"
                )
                raw_candidate_ids = record["candidate_ids"]
                _require(
                    type(raw_candidate_ids) is list,
                    "run candidate identities mismatch",
                )
                candidate_ids = [
                    _exact_lowercase_hex(
                        candidate_id, length=24, label="run candidate id"
                    )
                    for candidate_id in raw_candidate_ids
                ]
                request_sha256 = _exact_lowercase_hex(
                    record["request_sha256"], length=64, label="run request hash"
                )
                raw_response_sha256 = record["response_sha256"]
                response_sha256 = (
                    None
                    if raw_response_sha256 is None
                    else _exact_lowercase_hex(
                        raw_response_sha256,
                        length=64,
                        label="run response hash",
                    )
                )
                identities = record["session_or_thread_ids"]
                retry_count = record["transport_retry_count"]
                raw_attempts = record["attempts"]
                _require(
                    invocation_id == request_sha256[:24]
                    and invocation_id not in invocation_ids,
                    "duplicate or mismatched run invocation",
                )
                _require(
                    len(candidate_ids) == len(set(candidate_ids))
                    and not role_candidate_ids.intersection(candidate_ids),
                    "duplicate run candidate",
                )
                _require(
                    record["requested_model"] == config["model"]
                    and record["reasoning_effort"] == config["reasoning_effort"],
                    "run Agent configuration mismatch",
                )
                _require(
                    type(identities) is list
                    and all(
                        type(identity) is str
                        and bool(identity)
                        and identity.strip() == identity
                        for identity in identities
                    )
                    and len(set(identities)) == len(identities),
                    "run session binding mismatch",
                )
                _require(
                    type(retry_count) is int
                    and retry_count in {0, 1}
                    and (
                        len(identities) == retry_count + 1
                        or (retry_count == 0 and not identities)
                    ),
                    "run retry binding mismatch",
                )
                _require(
                    type(raw_attempts) is list
                    and (
                        len(raw_attempts) == retry_count + 1
                        or (retry_count == 0 and not identities and not raw_attempts)
                    ),
                    "run attempt count mismatch",
                )
                attempts: list[dict[str, Any]] = []
                for attempt_index, raw_attempt in enumerate(raw_attempts, start=1):
                    attempt = _exact_object_fields(
                        raw_attempt,
                        attempt_fields,
                        f"{role} sanitized attempt",
                    )
                    attempt_response = attempt["response_sha256"]
                    if attempt_response is not None:
                        attempt_response = _exact_lowercase_hex(
                            attempt_response,
                            length=64,
                            label="run attempt response hash",
                        )
                    _require(
                        attempt["attempt_ordinal"] == attempt_index
                        and attempt["session_or_thread_id"]
                        == identities[attempt_index - 1]
                        and attempt["request_sha256"] == request_sha256
                        and attempt["requested_model"] == config["model"]
                        and attempt["reasoning_effort"] == config["reasoning_effort"],
                        "run attempt authority mismatch",
                    )
                    if attempt["transport_failure"] is True:
                        _require(
                            attempt["response_bytes_present"] is False
                            and attempt_response is None
                            and attempt["returned_model"] is None
                            and attempt["outcome"] == "TRANSPORT_FAILURE_NO_RESPONSE",
                            "transport failure attempt mismatch",
                        )
                    else:
                        _require(
                            attempt["transport_failure"] is False
                            and attempt["response_bytes_present"] is True
                            and attempt_response is not None
                            and type(attempt["returned_model"]) is str
                            and bool(attempt["returned_model"].strip())
                            and attempt["outcome"]
                            in {"VALID_RESPONSE", "SUBSTANTIVE_INVALID_RESPONSE"},
                            "substantive response attempt mismatch",
                        )
                        if attempt["outcome"] == "VALID_RESPONSE":
                            _require(
                                attempt["returned_model"] == config["model"],
                                "valid response model mismatch",
                            )
                    attempts.append(
                        {**deepcopy(attempt), "response_sha256": attempt_response}
                    )
                if attempts:
                    _require(
                        retry_count == 0
                        or (attempts[0]["outcome"] == "TRANSPORT_FAILURE_NO_RESPONSE"),
                        "transport retry attempt sequence mismatch",
                    )
                    final_attempt = attempts[-1]
                    _require(
                        record["outcome"] == final_attempt["outcome"]
                        and response_sha256 == final_attempt["response_sha256"]
                        and record["returned_model"] == final_attempt["returned_model"],
                        "run final attempt summary mismatch",
                    )
                else:
                    _require(
                        response_sha256 is None
                        and record["returned_model"] is None
                        and record["outcome"] == "TRANSPORT_FAILURE_NO_RESPONSE",
                        "empty run summary mismatch",
                    )
                if role == "generator":
                    _require(
                        (record["outcome"] == "VALID_RESPONSE" and bool(candidate_ids))
                        or (
                            record["outcome"]
                            in {
                                "SUBSTANTIVE_INVALID_RESPONSE",
                                "TRANSPORT_FAILURE_NO_RESPONSE",
                            }
                            and not candidate_ids
                        ),
                        "generator run outcome candidate binding mismatch",
                    )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Agent run or retry evidence mismatch") from exc
            normalized_record = {
                **deepcopy(record),
                "invocation_id": invocation_id,
                "candidate_ids": candidate_ids,
                "request_sha256": request_sha256,
                "response_sha256": response_sha256,
                "attempts": attempts,
            }
            _require(
                _validated_invocation_terminal_authority(normalized_record) is None,
                "Agent invocation infrastructure terminal",
            )
            invocation_ids.add(invocation_id)
            role_candidate_ids.update(candidate_ids)
            records.append(normalized_record)
        validated_records[role] = records

    expected_evidence = {
        role: _agent_role_run_evidence(role, validated_records[role])
        for role in AGENT_CONFIGS
    }
    expected_retries = sorted(
        [
            retry
            for role, records in validated_records.items()
            for record in records
            if (retry := _transport_retry_record(record, role=role)) is not None
        ],
        key=lambda row: (cast(str, row["role"]), cast(str, row["invocation_id"])),
    )
    try:
        metadata_roles = _exact_object_fields(
            validation["agent_roles"], set(AGENT_CONFIGS), "Agent role metadata"
        )
        source_file_sha256 = _exact_object_fields(
            validation["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES),
            "Agent source file hashes",
        )
        identity_authority = _agent_run_identity_authority(
            validated_records, metadata_roles, source_file_sha256
        )
        review_schedules = _exact_object_fields(
            validation["review_schedule_sha256"],
            {"reviewer_a", "reviewer_b"},
            "review schedule hashes",
        )
        for role in ("reviewer_a", "reviewer_b"):
            schedule_candidate_ids = [
                candidate_id
                for record in validated_records[role]
                for candidate_id in cast(list[str], record["candidate_ids"])
            ]
            _require(
                review_schedules[role] == canonical_sha256(schedule_candidate_ids),
                f"{role} schedule identity mismatch",
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Agent run identity authority mismatch") from exc
    _require(
        validation.get("agent_run_evidence") == expected_evidence
        and validation.get("retry_records") == expected_retries
        and validation.get("transport_retry_count") == len(expected_retries),
        "Agent run or retry evidence mismatch",
    )
    _require(
        validation.get("agent_run_identity_authority") == identity_authority,
        "Agent run identity authority mismatch",
    )
    return validated_records, expected_evidence, expected_retries, identity_authority


def _validated_dataset_freeze_tasks(
    validation: dict[str, Any],
    *,
    generator_run_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    message = "Agent dataset selection validation mismatch"
    try:
        projected_skills = _project_canonical_skills(
            validation["canonical_skills_authority"]
        )
        _, generation_semantics = _validated_generation_authority(
            validation["generation_authority"],
            source_ledger_sha256=validation["generation_authority"][
                "source_ledger_sha256"
            ],
            canonical_ids=_canonical_skill_ids(projected_skills),
            candidate_outcomes=validation["candidate_outcomes"],
            generator_run_records=generator_run_records,
        )
        raw_tasks = validation["tasks"]
        _require(
            type(raw_tasks) is list and len(raw_tasks) == POSITIVE_TASK_COUNT,
            "selected task count mismatch",
        )
        candidate_fields = {
            "candidate_id",
            "generation_round",
            "prompt_text",
            "prompt_text_sha256",
            "semantic_family_id",
            "proposed_gold_skill_id",
            "proposed_negative_skill_id",
            "language",
            "rationale",
        }
        selected: list[dict[str, Any]] = []
        for raw_task in raw_tasks:
            task = _exact_object_fields(
                raw_task, candidate_fields, "selected Agent task"
            )
            candidate_id = _exact_lowercase_hex(
                task["candidate_id"], length=24, label="selected candidate id"
            )
            _require(
                type(task["generation_round"]) is int
                and task["generation_round"] in {1, 2},
                "selected generation round mismatch",
            )
            prompt_text = _nonempty_string(task["prompt_text"], "selected prompt")
            prompt_bytes = prompt_text.encode("utf-8", errors="strict")
            prompt_hash = _exact_lowercase_hex(
                task["prompt_text_sha256"],
                length=64,
                label="selected prompt SHA-256",
            )
            _require(
                prompt_hash == _sha256_bytes(prompt_bytes),
                "selected prompt SHA-256 mismatch",
            )
            family_id = _nonempty_string(
                task["semantic_family_id"], "selected semantic family"
            )
            gold = _nonempty_string(
                task["proposed_gold_skill_id"], "selected gold skill"
            )
            negative = task["proposed_negative_skill_id"]
            _require(
                negative is None
                or (
                    type(negative) is str
                    and bool(negative.strip())
                    and negative != gold
                ),
                "selected negative skill mismatch",
            )
            _require(task["language"] == "en", "selected task language mismatch")
            _nonempty_string(task["rationale"], "selected task rationale")
            selected.append(
                {
                    **deepcopy(task),
                    "candidate_id": candidate_id,
                    "prompt_text": prompt_text,
                    "prompt_text_sha256": prompt_hash,
                    "semantic_family_id": family_id,
                    "proposed_gold_skill_id": gold,
                }
            )

        selected_ids = [cast(str, task["candidate_id"]) for task in selected]
        selected_prompt_bytes = [
            cast(str, task["prompt_text"]).encode("utf-8") for task in selected
        ]
        normalized_prompts = [
            _normalize(cast(str, task["prompt_text"])) for task in selected
        ]
        family_ids = [cast(str, task["semantic_family_id"]) for task in selected]
        _require(
            len(set(selected_ids)) == POSITIVE_TASK_COUNT,
            "selected candidate ids must be unique",
        )
        _require(
            len(set(selected_prompt_bytes)) == POSITIVE_TASK_COUNT
            and len(set(normalized_prompts)) == POSITIVE_TASK_COUNT,
            "selected prompts must be unique",
        )
        _require(
            len(set(family_ids)) == POSITIVE_TASK_COUNT,
            "selected semantic families must be unique",
        )

        gold_counts = Counter(task["proposed_gold_skill_id"] for task in selected)
        _require(
            len(gold_counts) == 16 and set(gold_counts.values()) == {8},
            "selected per-gold task distribution mismatch",
        )
        gold_ids = sorted(cast(str, gold) for gold in gold_counts)
        selected_by_stratum = {
            gold: {
                "negative": [
                    cast(str, task["candidate_id"])
                    for task in selected
                    if task["proposed_gold_skill_id"] == gold
                    and task["proposed_negative_skill_id"] is not None
                ],
                "positive_only": [
                    cast(str, task["candidate_id"])
                    for task in selected
                    if task["proposed_gold_skill_id"] == gold
                    and task["proposed_negative_skill_id"] is None
                ],
            }
            for gold in gold_ids
        }
        _require(
            all(
                len(strata["negative"]) == 6 and len(strata["positive_only"]) == 2
                for strata in selected_by_stratum.values()
            ),
            "selected per-gold stratum distribution mismatch",
        )
        negative_tasks = [
            task for task in selected if task["proposed_negative_skill_id"] is not None
        ]
        _require(
            len(negative_tasks) == TEMPTING_NEGATIVE_COUNT,
            "selected negative task count mismatch",
        )
        expected_order = [
            task
            for gold in gold_ids
            for has_negative in (True, False)
            for task in sorted(
                (
                    row
                    for row in selected
                    if row["proposed_gold_skill_id"] == gold
                    and (row["proposed_negative_skill_id"] is not None) is has_negative
                ),
                key=lambda row: selection_key(cast(str, row["candidate_id"])),
            )
        ]
        _require(
            selected_ids
            == [cast(str, task["candidate_id"]) for task in expected_order],
            "selected candidate order mismatch",
        )

        expected_gold_distribution = dict(sorted(gold_counts.items()))
        negative_counts = Counter(
            cast(str, task["proposed_negative_skill_id"]) for task in negative_tasks
        )
        expected_negative_distribution = dict(sorted(negative_counts.items()))
        _require(
            type(validation["task_count"]) is int
            and validation["task_count"] == POSITIVE_TASK_COUNT
            and type(validation["negative_labeled_task_count"]) is int
            and validation["negative_labeled_task_count"] == len(negative_tasks)
            and type(validation["family_count"]) is int
            and validation["family_count"] == len(set(family_ids)),
            "selected task summary count mismatch",
        )
        _require(
            validation["gold_distribution"] == expected_gold_distribution
            and validation["negative_distribution"] == expected_negative_distribution
            and validation["negative_target_coverage_count"] == len(negative_counts),
            "selected task summary distribution mismatch",
        )

        candidate_outcomes = validation["candidate_outcomes"]
        _require(
            type(candidate_outcomes) is dict, "candidate outcomes must be an object"
        )
        _require(
            all(
                candidate_outcomes.get(candidate_id) == "SELECTED"
                for candidate_id in selected_ids
            ),
            "selected candidates must have SELECTED outcomes",
        )
        _require(
            validation["excluded_candidate_count"]
            == len(candidate_outcomes) - POSITIVE_TASK_COUNT,
            "excluded candidate count mismatch",
        )
        _require(
            validation["selection_not_selected_count"]
            == sum(
                outcome == "NOT_SELECTED" for outcome in candidate_outcomes.values()
            ),
            "not-selected candidate count mismatch",
        )
        _require(
            validation["pipeline_rejected_candidate_count"]
            == sum(
                type(outcome) is str and outcome.startswith("REJECTED")
                for outcome in candidate_outcomes.values()
            ),
            "pipeline rejected candidate count mismatch",
        )
        _require(
            validation["exact_three_way_agreement_count"]
            == sum(
                outcome in {"SELECTED", "NOT_SELECTED"}
                for outcome in candidate_outcomes.values()
            ),
            "three-way agreement pool count mismatch",
        )

        selection = _validated_selection_audit_semantics(
            validation["selection_audit"],
            generation_semantics=generation_semantics,
            selected_rows=selected,
            canonical_ids=set(gold_ids),
            id_field="candidate_id",
            gold_field="proposed_gold_skill_id",
            negative_field="proposed_negative_skill_id",
            require_complete_selection=True,
            validate_selected_semantics=False,
            selection_audit_sha256=validation["selection_audit_sha256"],
        )
        task_rows = [
            {
                "task_id": task["candidate_id"],
                "prompt_text": task["prompt_text"],
                "prompt_text_sha256": task["prompt_text_sha256"],
                "semantic_family_id": task["semantic_family_id"],
                "gold_skill_id": task["proposed_gold_skill_id"],
                "negative_skill_id": task["proposed_negative_skill_id"],
                "source_type": "AGENT_GENERATED",
            }
            for task in selected
        ]
        return task_rows, deepcopy(selection)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc


def _validated_agent_source_ledger_evidence(
    validation: dict[str, Any],
    *,
    semantic_similarity: SemanticSimilarity,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    message = "Agent source ledger freeze authority mismatch"
    try:
        projected_skills = _project_canonical_skills(
            validation["canonical_skills_authority"]
        )
        canonical_ids = _canonical_skill_ids(projected_skills)
        raw_payloads = _exact_object_fields(
            validation["source_file_bytes"],
            set(REQUIRED_AGENT_PACK_FILES),
            "Agent source file bytes",
        )
        source_hashes = _exact_object_fields(
            validation["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES),
            "Agent source file hashes",
        )
        payloads: dict[str, bytes] = {}
        for filename in REQUIRED_AGENT_PACK_FILES:
            payload_hex = raw_payloads[filename]
            _require(
                type(payload_hex) is str and bool(payload_hex),
                f"{filename} source bytes mismatch",
            )
            payload = bytes.fromhex(payload_hex)
            _require(
                payload.hex() == payload_hex,
                f"{filename} source byte encoding mismatch",
            )
            expected_hash = _exact_lowercase_hex(
                source_hashes[filename],
                length=64,
                label=f"{filename} source SHA-256",
            )
            _require(
                _sha256_bytes(payload) == expected_hash,
                f"{filename} source bytes hash mismatch",
            )
            payloads[filename] = payload

        generation_rows = _jsonl_no_duplicate_keys(
            payloads["blind-v2-generation.jsonl"], "blind-v2 generation ledger"
        )
        review_rows_by_role = {
            "reviewer_a": _jsonl_no_duplicate_keys(
                payloads["blind-v2-review-a.jsonl"], "blind-v2 Reviewer A ledger"
            ),
            "reviewer_b": _jsonl_no_duplicate_keys(
                payloads["blind-v2-review-b.jsonl"], "blind-v2 Reviewer B ledger"
            ),
        }
        contamination_rows = _jsonl_no_duplicate_keys(
            payloads["blind-v2-contamination.jsonl"],
            "blind-v2 contamination ledger",
        )
        metadata = _json_no_duplicate_keys(
            payloads["agent-run-metadata.json"], "Agent run metadata"
        )
        invocation_terminal = _preflight_invocation_terminal_authority(
            generation_rows,
            review_rows_by_role,
        )
        _require(
            invocation_terminal is None,
            "Agent source ledger contains an infrastructure terminal invocation",
        )
        metadata = _exact_object_fields(
            metadata,
            {
                "schema_version",
                "first_read_timestamp",
                "roles",
                "review_schedule_sha256",
                "selection_authority",
                "source_file_sha256",
            },
            "Agent run metadata",
        )
        _require(
            metadata["schema_version"] == "router-v2-blind-v2-agent-run-metadata-v1"
            and metadata["first_read_timestamp"] == validation["first_read_timestamp"]
            and metadata["roles"] == validation["agent_roles"]
            and metadata["review_schedule_sha256"]
            == validation["review_schedule_sha256"]
            and metadata["selection_authority"] == _selection_authority_document(),
            "Agent source metadata mismatch",
        )
        metadata_source_hashes = _exact_object_fields(
            metadata["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES[:-1]),
            "Agent metadata source hashes",
        )
        _require(
            all(
                metadata_source_hashes[filename] == source_hashes[filename]
                for filename in REQUIRED_AGENT_PACK_FILES[:-1]
            ),
            "Agent metadata source hash mismatch",
        )

        candidates: dict[str, dict[str, Any]] = {}
        generation_request_quota_counts: Counter[tuple[int, str, str]] = Counter()
        generation_request_keys: list[tuple[int, str]] = []
        source_records: dict[str, list[dict[str, Any]]] = {
            role: [] for role in AGENT_CONFIGS
        }
        generation_authority_requests: list[dict[str, Any]] = []
        for raw_row in generation_rows:
            row, request, quota = _validated_generation_source_row(
                raw_row,
                projected_skills=projected_skills,
                canonical_ids=canonical_ids,
                label="source generation row",
            )
            generation_round = cast(int, row["generation_round"])
            gold = cast(str, row["gold_skill_id"])
            request_key = (generation_round, gold)
            _require(
                request_key not in generation_request_keys,
                "duplicate source generation request identity",
            )
            generation_request_keys.append(request_key)
            for stratum, field in (
                ("negative", "negative_quota"),
                ("positive_only", "positive_only_quota"),
            ):
                value = quota[field]
                _require(
                    type(value) is int and value >= 0,
                    "source generator quota count mismatch",
                )
                generation_request_quota_counts[(generation_round, gold, stratum)] += (
                    value
                )
            response, retry_count = _validate_pack_invocations(
                row["invocations"], request=request
            )
            derived_candidates = (
                []
                if response is None
                else _derived_generator_candidates(response, request)
            )
            run_record = _sanitized_agent_run_record(
                role="generator",
                candidate_ids=[
                    cast(str, candidate["candidate_id"])
                    for candidate in derived_candidates
                ],
                request=request,
                response=response,
                invocations=row["invocations"],
                retry_count=retry_count,
            )
            source_records["generator"].append(run_record)
            generation_authority_requests.append(
                _generation_authority_request_document(
                    request=request,
                    response=response,
                    run_record=run_record,
                )
            )
            for candidate in derived_candidates:
                candidate_id = cast(str, candidate["candidate_id"])
                _require(
                    candidate_id not in candidates,
                    "duplicate source candidate id",
                )
                candidates[candidate_id] = candidate

        expected_round_one_request_keys = [
            (1, skill_id) for skill_id in sorted(canonical_ids)
        ]
        round_two_request_keys = [key for key in generation_request_keys if key[0] == 2]
        _require(
            all(
                round_number in {1, 2}
                for round_number, _gold in generation_request_keys
            )
            and generation_request_keys
            == expected_round_one_request_keys + sorted(round_two_request_keys),
            "source generation request schedule mismatch",
        )

        raw_contamination_authority = _exact_object_fields(
            validation["contamination_source_authority"],
            {"scanner_config", "rows", "clean_candidate_ids"},
            "contamination source authority",
        )
        scanner_config = _validated_contamination_scanner_config(
            raw_contamination_authority["scanner_config"]
        )
        authority_rows = raw_contamination_authority["rows"]
        authority_clean_ids = raw_contamination_authority["clean_candidate_ids"]
        _require(
            type(authority_rows) is list
            and type(authority_clean_ids) is list
            and contamination_rows == authority_rows,
            "contamination source evidence mismatch",
        )
        protected_prompts, protected_family_ids = (
            _protected_inputs_from_sealed_construction_bindings(
                validation["construction_input_source_bindings"]
            )
        )
        _require(
            protected_prompts["prior_candidate"] == []
            and protected_family_ids["prior_candidate"] == set(),
            "unbound prior-candidate contamination authority",
        )
        replayed_contamination = _scan_contamination(
            list(candidates.values()),
            protected_prompts=protected_prompts,
            protected_family_ids=protected_family_ids,
            semantic_similarity=semantic_similarity,
            semantic_model_authority={
                "materialized_model_files": scanner_config["materialized_model_files"],
                "materialized_model_files_sha256": scanner_config[
                    "materialized_model_files_sha256"
                ],
            },
        )
        _require(
            replayed_contamination["scanner_config"] == scanner_config
            and replayed_contamination["rows"] == contamination_rows
            and replayed_contamination["clean_candidate_ids"] == authority_clean_ids,
            "sealed contamination replay mismatch",
        )
        contamination_decisions: dict[str, str] = {}
        for raw_row in contamination_rows:
            row = _exact_object_fields(
                raw_row,
                {
                    "candidate_id",
                    "scanner_decision",
                    "rejection_codes",
                    "evidence_sha256",
                },
                "source contamination row",
            )
            candidate_id = _exact_lowercase_hex(
                row["candidate_id"],
                length=24,
                label="source contamination candidate id",
            )
            _require(
                candidate_id in candidates
                and candidate_id not in contamination_decisions
                and row["scanner_decision"] in {"PASS", "REJECT"}
                and type(row["rejection_codes"]) is list
                and all(type(code) is str for code in row["rejection_codes"]),
                "source contamination identity mismatch",
            )
            _exact_lowercase_hex(
                row["evidence_sha256"],
                length=64,
                label="source contamination evidence SHA-256",
            )
            contamination_decisions[candidate_id] = cast(str, row["scanner_decision"])
        _require(
            set(contamination_decisions) == set(candidates),
            "source contamination coverage mismatch",
        )
        clean_candidate_ids = {
            candidate_id
            for candidate_id, decision in contamination_decisions.items()
            if decision == "PASS"
        }
        _require(
            authority_clean_ids
            == [
                row["candidate_id"]
                for row in authority_rows
                if row["scanner_decision"] == "PASS"
            ]
            and set(cast(list[str], authority_clean_ids)) == clean_candidate_ids,
            "contamination clean candidate authority mismatch",
        )
        expected_contamination_audit = _contamination_audit_document(
            {"scanner_config": scanner_config, "rows": contamination_rows},
            source_hashes=source_hashes,
            candidate_count=len(candidates),
            clean_candidate_count=len(clean_candidate_ids),
        )
        _require(
            validation["contamination_audit"] == expected_contamination_audit,
            "contamination audit authority mismatch",
        )

        review_responses: dict[str, dict[str, dict[str, Any] | None]] = {
            "reviewer_a": {},
            "reviewer_b": {},
        }
        reviewer_decision_rows: dict[str, list[dict[str, Any]]] = {
            "reviewer_a": [],
            "reviewer_b": [],
        }
        actual_review_orders: dict[str, list[str]] = {
            "reviewer_a": [],
            "reviewer_b": [],
        }
        for role, raw_rows in review_rows_by_role.items():
            for raw_row in raw_rows:
                row, candidate_id, request = _validated_reviewer_source_row(
                    raw_row,
                    role=role,
                    candidates=candidates,
                    projected_skills=projected_skills,
                    clean_candidate_ids=clean_candidate_ids,
                    label=f"source {role} row",
                )
                _require(
                    candidate_id not in review_responses[role],
                    f"source {role} candidate identity mismatch",
                )
                actual_review_orders[role].append(candidate_id)
                response, retry_count = _validate_pack_invocations(
                    row["invocations"], request=request
                )
                terminal_candidate_ids = (
                    []
                    if response is None
                    and retry_count == 1
                    and all(
                        type(invocation) is dict and "envelope" not in invocation
                        for invocation in cast(list[Any], row["invocations"])
                    )
                    else [candidate_id]
                )
                run_record = _sanitized_agent_run_record(
                    role=role,
                    candidate_ids=terminal_candidate_ids,
                    request=request,
                    response=response,
                    invocations=row["invocations"],
                    retry_count=retry_count,
                )
                source_records[role].append(run_record)
                reviewer_decision_rows[role].append(
                    _sanitized_reviewer_decision_row(
                        role=role,
                        candidate_id=candidate_id,
                        response=response,
                        run_record=run_record,
                    )
                )
                review_responses[role][candidate_id] = response

            expected_order = sorted(
                clean_candidate_ids,
                key=lambda candidate_id: review_schedule_key(role, candidate_id),
            )
            _require(
                set(review_responses[role]) == clean_candidate_ids
                and actual_review_orders[role] == expected_order,
                f"source {role} coverage or schedule mismatch",
            )

        _require(
            source_records == validation["agent_run_records"],
            "source invocation evidence mismatch",
        )

        metadata_roles = _exact_object_fields(
            metadata["roles"], set(AGENT_CONFIGS), "Agent source metadata roles"
        )
        all_sessions: list[str] = []
        for role in AGENT_CONFIGS:
            role_metadata = _exact_object_fields(
                metadata_roles[role],
                {
                    "config",
                    "request_count",
                    "invocation_count",
                    "session_or_thread_ids",
                    "fork_context",
                    "history_message_count",
                    "imported_memory_count",
                },
                f"source {role} metadata",
            )
            records = source_records[role]
            sessions = [
                identity
                for record in records
                for identity in cast(list[str], record["session_or_thread_ids"])
            ]
            _require(
                role_metadata["config"] == AGENT_CONFIGS[role]
                and role_metadata["request_count"] == len(records)
                and role_metadata["invocation_count"] == len(sessions)
                and role_metadata["session_or_thread_ids"] == sessions
                and role_metadata["fork_context"] is False
                and role_metadata["history_message_count"] == 0
                and role_metadata["imported_memory_count"] == 0,
                f"source {role} metadata binding mismatch",
            )
            all_sessions.extend(sessions)
        _require(
            len(all_sessions) == len(set(all_sessions)),
            "source Agent sessions must be globally unique",
        )
        schedules = _exact_object_fields(
            metadata["review_schedule_sha256"],
            {"reviewer_a", "reviewer_b"},
            "source review schedules",
        )
        for role in ("reviewer_a", "reviewer_b"):
            _require(
                schedules[role] == canonical_sha256(actual_review_orders[role]),
                f"source {role} schedule hash mismatch",
            )

        accepted, outcomes = _derive_candidate_pipeline_semantics(
            candidates,
            clean_candidate_ids=clean_candidate_ids,
            review_responses=review_responses,
        )
        source_gold_ids = {
            cast(str, candidate["proposed_gold_skill_id"])
            for candidate in candidates.values()
        }
        _require(
            source_gold_ids == canonical_ids,
            "source generation canonical skill coverage mismatch",
        )
        gold_ids = sorted(
            {
                cast(str, candidate["proposed_gold_skill_id"])
                for candidate in candidates.values()
            }
        )

        source_generation_authority, generation_semantics = (
            _validated_generation_authority(
                _generation_authority_document(
                    generation_authority_requests,
                    source_ledger_sha256=source_hashes["blind-v2-generation.jsonl"],
                ),
                source_ledger_sha256=source_hashes["blind-v2-generation.jsonl"],
                canonical_ids=canonical_ids,
                candidate_outcomes=outcomes,
                generator_run_records=source_records["generator"],
            )
        )
        _require(
            validation["generation_authority"] == source_generation_authority,
            "source generation authority mismatch",
        )
        selected_tasks = cast(list[dict[str, Any]], validation["tasks"])
        expected_selected_tasks = _deterministically_select_candidates(
            accepted, canonical_ids
        )
        _require(
            selected_tasks == expected_selected_tasks,
            "selected tasks differ from deterministic source-ledger selection",
        )
        _require(
            all(
                task == candidates[cast(str, task["candidate_id"])]
                for task in selected_tasks
            ),
            "selected task content differs from source generation ledger",
        )
        selected_by_stratum = {
            gold: {
                stratum: [
                    cast(str, task["candidate_id"])
                    for task in selected_tasks
                    if task["proposed_gold_skill_id"] == gold
                    and _candidate_stratum(task) == stratum
                ]
                for stratum in ("negative", "positive_only")
            }
            for gold in gold_ids
        }
        outcomes = _finalized_candidate_outcomes(outcomes, selected_tasks)
        source_selection_audit = _selection_audit_document(
            generation_semantics=generation_semantics,
            selected=selected_tasks,
            canonical_ids=canonical_ids,
        )
        _require(
            source_selection_audit["selected_by_stratum"] == selected_by_stratum,
            "source selected stratum binding mismatch",
        )
        _require(
            validation["selection_audit"] == source_selection_audit
            and validation["selection_audit_sha256"]
            == canonical_sha256(source_selection_audit),
            "source-derived selection audit mismatch",
        )
        sorted_outcomes = dict(sorted(outcomes.items()))
        pipeline_rejected_count = sum(
            outcome.startswith("REJECTED") for outcome in outcomes.values()
        )
        not_selected_count = sum(
            outcome == "NOT_SELECTED" for outcome in outcomes.values()
        )
        exact_agreement_count = sum(
            outcome in {"SELECTED", "NOT_SELECTED"} for outcome in outcomes.values()
        )
        _require(
            validation["candidate_outcomes"] == sorted_outcomes
            and validation["pipeline_rejected_candidate_count"]
            == pipeline_rejected_count
            and validation["selection_not_selected_count"] == not_selected_count
            and validation["exact_three_way_agreement_count"] == exact_agreement_count
            and validation["excluded_candidate_count"]
            == pipeline_rejected_count + not_selected_count,
            "source candidate outcome aggregate mismatch",
        )
        source_reviewer_decision_authority = _reviewer_decision_authority_document(
            reviewer_decision_rows
        )
        _require(
            validation["reviewer_decision_authority"]
            == source_reviewer_decision_authority,
            "source reviewer decision authority mismatch",
        )
        reviewer_decision_authority = _validated_reviewer_decision_authority(
            source_reviewer_decision_authority,
            candidate_labels={
                candidate_id: (
                    cast(str, candidate["proposed_gold_skill_id"]),
                    cast(str | None, candidate["proposed_negative_skill_id"]),
                )
                for candidate_id, candidate in candidates.items()
            },
            candidate_outcomes=sorted_outcomes,
            reviewer_run_records={
                role: source_records[role] for role in ("reviewer_a", "reviewer_b")
            },
            canonical_ids=canonical_ids,
        )
        return (
            source_generation_authority,
            generation_semantics,
            reviewer_decision_authority,
        )
    except (
        _AgentPackProtocolViolation,
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(message) from exc


def _validate_source_invocation_terminality(validation: dict[str, Any]) -> None:
    message = "Agent source ledger freeze authority mismatch"
    try:
        raw_payloads = _exact_object_fields(
            validation["source_file_bytes"],
            set(REQUIRED_AGENT_PACK_FILES),
            "Agent source file bytes",
        )
        source_hashes = _exact_object_fields(
            validation["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES),
            "Agent source file hashes",
        )
        payloads: dict[str, bytes] = {}
        for filename in REQUIRED_AGENT_PACK_FILES:
            payload_hex = raw_payloads[filename]
            _require(
                type(payload_hex) is str and bool(payload_hex),
                f"{filename} source bytes mismatch",
            )
            payload = bytes.fromhex(payload_hex)
            _require(
                payload.hex() == payload_hex
                and _sha256_bytes(payload)
                == _exact_lowercase_hex(
                    source_hashes[filename],
                    length=64,
                    label=f"{filename} source SHA-256",
                ),
                f"{filename} source bytes hash mismatch",
            )
            payloads[filename] = payload
        generation_rows = _jsonl_no_duplicate_keys(
            payloads["blind-v2-generation.jsonl"], "blind-v2 generation ledger"
        )
        review_rows_by_role = {
            "reviewer_a": _jsonl_no_duplicate_keys(
                payloads["blind-v2-review-a.jsonl"], "blind-v2 Reviewer A ledger"
            ),
            "reviewer_b": _jsonl_no_duplicate_keys(
                payloads["blind-v2-review-b.jsonl"], "blind-v2 Reviewer B ledger"
            ),
        }
        _require(
            _preflight_invocation_terminal_authority(
                generation_rows,
                review_rows_by_role,
            )
            is None,
            "Agent source ledger contains an infrastructure terminal invocation",
        )
    except (
        _AgentPackProtocolViolation,
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(message) from exc


def build_dataset_freeze_documents(
    validation: dict[str, Any],
    *,
    commit_a: str,
    semantic_similarity: SemanticSimilarity,
) -> dict[str, bytes]:
    _require(
        type(validation) is dict,
        "Agent dataset freeze validation container mismatch",
    )
    _require(validation.get("status") == "VALID", "validated Agent pack is required")
    _require(
        callable(semantic_similarity),
        "contamination replay semantic similarity is required",
    )
    commit_a = _exact_lowercase_hex(
        commit_a,
        length=40,
        label="Commit A",
    )
    _validate_source_invocation_terminality(validation)
    projected_skills = _project_canonical_skills(
        validation["canonical_skills_authority"]
    )
    sealed_construction_input_authority = (
        _construction_input_authority_from_sealed_bindings(
            validation["construction_input_source_bindings"],
            projected_skills=projected_skills,
        )
    )
    _require(
        validation["construction_input_authority"]
        == sealed_construction_input_authority
        and all(
            validation["contamination_audit"]["protected_authority"][scope]
            == sealed_construction_input_authority["protected_artifact_projections"][
                scope
            ]["protected_authority"]
            for scope in ("train", "pilot-002", "phase16")
        ),
        "protected semantic source authority mismatch",
    )
    (
        sanitized_run_records,
        agent_run_evidence,
        retry_records,
        agent_run_identity_authority,
    ) = _validated_agent_lineage_evidence(validation)
    (
        generation_authority,
        _,
        reviewer_decision_authority,
    ) = _validated_agent_source_ledger_evidence(
        validation,
        semantic_similarity=semantic_similarity,
    )
    task_rows, deterministic_selection = _validated_dataset_freeze_tasks(
        validation,
        generator_run_records=sanitized_run_records["generator"],
    )
    task_bytes = b"".join(_canonical_json_bytes(row) for row in task_rows)

    reviewer_ledgers = {
        role: {
            "path": f"blind-v2-review-{'a' if role == 'reviewer_a' else 'b'}.jsonl",
            "sha256": validation["source_file_sha256"][
                f"blind-v2-review-{'a' if role == 'reviewer_a' else 'b'}.jsonl"
            ],
            "schedule_sha256": validation["review_schedule_sha256"][role],
        }
        for role in ("reviewer_a", "reviewer_b")
    }
    contamination = {
        **deepcopy(validation["contamination_audit"]),
        "ledger_file_sha256": validation["source_file_sha256"][
            "blind-v2-contamination.jsonl"
        ],
    }
    construction_input_authority = _validated_construction_input_authority(
        sealed_construction_input_authority,
        projected_skills=projected_skills,
        protected_authority=cast(
            dict[str, Any], validation["contamination_audit"]["protected_authority"]
        ),
    )
    protected_semantic_commitment = _protected_semantic_commitment(
        construction_input_authority
    )
    exact_three_way_agreement_count = validation["exact_three_way_agreement_count"]
    selection_not_selected_count = validation["selection_not_selected_count"]
    pipeline_rejected_candidate_count = validation["pipeline_rejected_candidate_count"]
    excluded_candidate_count = validation["excluded_candidate_count"]
    candidate_outcomes = deepcopy(validation["candidate_outcomes"])
    selected_task_source_authority = [
        {
            "task_id": row["task_id"],
            "prompt_text_sha256": row["prompt_text_sha256"],
            "semantic_family_id": row["semantic_family_id"],
            "gold_skill_id": row["gold_skill_id"],
            "negative_skill_id": row["negative_skill_id"],
            "source_type": row["source_type"],
        }
        for row in task_rows
    ]
    agent_construction = {
        "review_mode": "ISOLATED_AGENT_REVIEW",
        "source_type": "AGENT_GENERATED",
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "exact_three_way_agreement_count": exact_three_way_agreement_count,
        "selection_not_selected_count": selection_not_selected_count,
        "pipeline_rejected_candidate_count": pipeline_rejected_candidate_count,
        "excluded_candidate_count": excluded_candidate_count,
        "candidate_outcomes": candidate_outcomes,
        "construction_input_authority": construction_input_authority,
        "protected_semantic_commitment": protected_semantic_commitment,
        "selected_task_source_authority": selected_task_source_authority,
        "selected_task_source_authority_sha256": canonical_sha256(
            selected_task_source_authority
        ),
        "generation_authority": generation_authority,
        "reviewer_decision_authority": reviewer_decision_authority,
        "generation_ledger": {
            "path": "blind-v2-generation.jsonl",
            "sha256": validation["source_file_sha256"]["blind-v2-generation.jsonl"],
        },
        "reviewer_ledgers": reviewer_ledgers,
        "agent_run_metadata": {
            "path": "agent-run-metadata.json",
            "sha256": validation["source_file_sha256"]["agent-run-metadata.json"],
        },
        "sanitized_run_records": deepcopy(sanitized_run_records),
        "agent_run_identity_authority": deepcopy(agent_run_identity_authority),
        "agent_roles": deepcopy(agent_run_evidence),
        "transport_retry_count": validation["transport_retry_count"],
        "retry_records": deepcopy(retry_records),
        "contamination": contamination,
        "deterministic_selection": deterministic_selection,
        "deterministic_selection_sha256": canonical_sha256(deterministic_selection),
    }
    review_summary = {
        "schema_version": "router-v2-agent-blind-v2-review-summary-v1",
        "review_mode": "ISOLATED_AGENT_REVIEW",
        "source_type": "AGENT_GENERATED",
        "task_count": POSITIVE_TASK_COUNT,
        "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
        "family_count": POSITIVE_TASK_COUNT,
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "exact_three_way_agreement_count": exact_three_way_agreement_count,
        "selection_not_selected_count": selection_not_selected_count,
        "pipeline_rejected_candidate_count": pipeline_rejected_candidate_count,
        "excluded_candidate_count": excluded_candidate_count,
        "candidate_outcomes": candidate_outcomes,
        "agent_roles": deepcopy(agent_run_evidence),
        "reviewer_ledgers": reviewer_ledgers,
        "transport_retry_count": validation["transport_retry_count"],
        "retry_records": deepcopy(retry_records),
    }
    review_bytes = _canonical_json_bytes(review_summary)
    manifest = {
        "schema_version": "router-v2-agent-blind-v2-manifest-v1",
        "commit_a": commit_a,
        "dataset_sha256": _sha256_bytes(task_bytes),
        "tasks_file_sha256": _sha256_bytes(task_bytes),
        "task_count": POSITIVE_TASK_COUNT,
        "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
        "gold_distribution": validation["gold_distribution"],
        "negative_distribution": validation["negative_distribution"],
        "family_count": POSITIVE_TASK_COUNT,
        "human_author_count": 0,
        "human_reviewer_count": 0,
        "exact_three_way_agreement_count": exact_three_way_agreement_count,
        "selection_not_selected_count": selection_not_selected_count,
        "pipeline_rejected_candidate_count": pipeline_rejected_candidate_count,
        "excluded_candidate_count": excluded_candidate_count,
        "candidate_outcomes": candidate_outcomes,
        "source_file_sha256": validation["source_file_sha256"],
        "per_row_prompt_sha256": [row["prompt_text_sha256"] for row in task_rows],
        "blind_v2_data_first_read_timestamp": validation["first_read_timestamp"],
        "prompts_committed": True,
        "agent_construction": agent_construction,
        "model_scores_observed": False,
        "evaluation_started": False,
        "retraining_after_data_access": False,
        "gate_changed_after_data_access": False,
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    return {
        "blind-v2-tasks.jsonl": task_bytes,
        "blind-v2-review-summary.json": review_bytes,
        "blind-v2-manifest.json": manifest_bytes,
    }


def validate_frozen_dataset_documents(
    validation: dict[str, Any],
    documents: dict[str, bytes],
    *,
    semantic_similarity: SemanticSimilarity,
) -> list[dict[str, Any]]:
    _require(
        set(documents)
        == {
            "blind-v2-tasks.jsonl",
            "blind-v2-review-summary.json",
            "blind-v2-manifest.json",
        },
        "frozen dataset document set mismatch",
    )
    manifest = _json_no_duplicate_keys(
        documents["blind-v2-manifest.json"], "blind-v2 manifest"
    )
    commit_a = manifest.get("commit_a")
    _require(type(commit_a) is str, "frozen dataset Commit A binding is missing")
    rebuilt = build_dataset_freeze_documents(
        validation,
        commit_a=cast(str, commit_a),
        semantic_similarity=semantic_similarity,
    )
    for name, expected in rebuilt.items():
        _require(documents[name] == expected, f"frozen dataset bytes mismatch: {name}")
    return cast(list[dict[str, Any]], validation["tasks"])


def write_dataset_freeze(
    documents: dict[str, bytes],
    output_dir: Path | str,
    *,
    repository_root: Path | str,
) -> None:
    root = _canonical_repository_destination(
        Path(output_dir),
        Path(repository_root),
        DATASET_FREEZE_RELATIVE,
        label="dataset freeze",
    )
    _require(
        set(documents) == set(DATASET_FREEZE_FILENAMES),
        "frozen dataset document set mismatch",
    )
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in DATASET_FREEZE_FILENAMES:
        payload = documents[name]
        with (root / name).open("xb") as handle:
            handle.write(payload)


def _manifest_rows_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return _sha256_bytes(payload)


def _verify_model_files(
    model_root: Path, rows: list[dict[str, Any]], expected_hash: str
) -> None:
    _require(
        _manifest_rows_hash(rows) == expected_hash, "model file manifest hash mismatch"
    )
    for row in rows:
        relative = Path(row["path"])
        _require(
            not relative.is_absolute() and ".." not in relative.parts,
            "model file path is unsafe",
        )
        target = model_root / relative
        _require(target.is_file(), f"missing model file: {relative}")
        _require(
            target.stat().st_size == row["size"],
            f"model file size mismatch: {relative}",
        )
        _require(
            _sha256_file(target) == row["sha256"],
            f"model file hash mismatch: {relative}",
        )


def _assert_no_existing_symlink_components(path: Path, *, label: str) -> None:
    _require(path.is_absolute(), f"{label} must be absolute")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        _require(
            not current.is_symlink(),
            f"{label} path components must not be symlinks",
        )


def _canonical_repository_destination(
    requested: Path,
    repository_root: Path,
    relative: Path,
    *,
    label: str,
) -> Path:
    repository = repository_root.resolve(strict=True)
    _require(repository.is_dir(), "repository root must be a directory")
    canonical = repository / relative
    _require(
        requested.is_absolute() and requested == canonical,
        f"{label} must use the exact canonical repository path",
    )
    _assert_no_existing_symlink_components(requested, label=label)
    resolved = requested.resolve(strict=False)
    _require(resolved.is_relative_to(repository), f"{label} escapes repository")
    return requested


def _safe_repository_regular_file(
    repository_root: Path, relative: Path, *, label: str
) -> Path:
    repository = repository_root.resolve(strict=True)
    _require(
        bool(relative.parts)
        and not relative.is_absolute()
        and ".." not in relative.parts,
        f"{label} path must be repository-relative",
    )
    unresolved = repository
    for component in relative.parts:
        unresolved /= component
        _require(
            not unresolved.is_symlink(),
            f"{label} path components must not be symlinks",
        )
    resolved = unresolved.resolve(strict=True)
    _require(resolved.is_relative_to(repository), f"{label} path escapes repository")
    _require(
        unresolved.is_file() and resolved.is_file(),
        f"{label} path must be a regular file",
    )
    return resolved


def _repository_file(repository_root: Path, relative_value: Any, *, label: str) -> Path:
    _require(
        type(relative_value) is str and bool(relative_value), f"{label} path mismatch"
    )
    relative = Path(relative_value)
    _require(
        not relative.is_absolute() and ".." not in relative.parts,
        f"{label} path must be repository-relative",
    )
    resolved = (repository_root / relative).resolve(strict=True)
    _require(
        resolved.is_relative_to(repository_root.resolve(strict=True)),
        f"{label} path escapes repository",
    )
    _require(resolved.is_file(), f"{label} path must be a file")
    return resolved


def _artifact_binding(
    artifacts: list[dict[str, Any]], arm: str, seed: int
) -> dict[str, Any]:
    matches = [
        row for row in artifacts if row.get("arm") == arm and row.get("seed") == seed
    ]
    _require(len(matches) == 1, f"pilot {arm}/{seed} artifact binding mismatch")
    return matches[0]


def _verify_task8_semantic_model_snapshot() -> None:
    snapshot = SEMANTIC_MODEL_SNAPSHOT_PATH.resolve(strict=True)
    _require(snapshot.is_dir(), "preregistered semantic model snapshot is missing")
    expected = _task8_semantic_model_files()
    expected_paths = [row["path"] for row in expected]
    actual_paths = [
        path.relative_to(snapshot).as_posix()
        for path in sorted(
            snapshot.rglob("*"),
            key=lambda value: value.relative_to(snapshot).as_posix().encode("utf-8"),
        )
        if path.is_file()
    ]
    _require(
        actual_paths == expected_paths,
        "semantic model materialized file set mismatch",
    )
    for row in expected:
        relative = cast(str, row["path"])
        _require(
            ".locks/" not in relative
            and not relative.endswith(".lock")
            and ".incomplete" not in relative,
            "semantic model authority contains cache control file",
        )
        path = snapshot / relative
        _require(
            path.is_file()
            and path.stat().st_size == row["size"]
            and _sha256_file(path) == row["sha256"],
            f"semantic model materialized file mismatch: {relative}",
        )


def _protected_semantic_commitment_from_preregistration_sources(
    preregistration: Mapping[str, Any], repository: Path
) -> dict[str, Any]:
    def source(
        raw_binding: Any, *, fields: set[str], label: str
    ) -> tuple[dict[str, Any], bytes]:
        binding = _exact_object_fields(raw_binding, fields, label)
        path = _repository_file(repository, binding["path"], label=label)
        payload = path.read_bytes()
        _require(
            _sha256_bytes(payload) == binding["sha256"],
            f"{label} hash mismatch",
        )
        return binding, payload

    skill_binding, skill_payload = source(
        preregistration.get("skill_index"),
        fields={"canonical_skill_count", "path", "sha256"},
        label="protected semantic skill source",
    )
    canonical_skills = _json_value_no_duplicate_keys(
        skill_payload, "protected semantic skill source"
    )
    projected_skills = _project_canonical_skills(canonical_skills)
    _require(
        skill_binding["canonical_skill_count"] == len(projected_skills),
        "protected semantic skill count mismatch",
    )
    frozen_inputs = preregistration.get("frozen_inputs")
    _require(type(frozen_inputs) is dict, "protected semantic inputs mismatch")
    frozen_inputs = cast(dict[str, Any], frozen_inputs)
    train_binding, train_payload = source(
        frozen_inputs.get("accepted_pairs"),
        fields={"path", "sha256"},
        label="protected semantic train source",
    )
    pilot_binding, pilot_payload = source(
        frozen_inputs.get("heldout_labels"),
        fields={"path", "sha256"},
        label="protected semantic pilot source",
    )
    raw_phase16 = preregistration.get("old_phase16_prompt_files")
    _require(
        type(raw_phase16) is list and len(raw_phase16) == 16,
        "protected semantic Phase 16 sources mismatch",
    )
    phase16_sources = [
        source(
            raw_binding,
            fields={"path", "sha256"},
            label="protected semantic Phase 16 source",
        )
        for raw_binding in cast(list[Any], raw_phase16)
    ]
    construction_input_bindings = {
        "canonical_skill_source": {
            "path": skill_binding["path"],
            "file_sha256": skill_binding["sha256"],
            "source_bytes_hex": skill_payload.hex(),
        },
        "protected_scope_sources": {
            "train": [
                {
                    "path": train_binding["path"],
                    "file_sha256": train_binding["sha256"],
                    "source_bytes_hex": train_payload.hex(),
                }
            ],
            "pilot-002": [
                {
                    "path": pilot_binding["path"],
                    "file_sha256": pilot_binding["sha256"],
                    "source_bytes_hex": pilot_payload.hex(),
                }
            ],
            "phase16": [
                {
                    "path": binding["path"],
                    "file_sha256": binding["sha256"],
                    "source_bytes_hex": payload.hex(),
                }
                for binding, payload in phase16_sources
            ],
        },
    }
    construction_input_authority = _construction_input_authority_from_sealed_bindings(
        construction_input_bindings,
        projected_skills=projected_skills,
    )
    return _protected_semantic_commitment(construction_input_authority)


def validate_preregistration_authority(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    pilot_manifest_path: Path | str,
    verify_model_files: bool = True,
    canonical_path_required: bool = True,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    if canonical_path_required:
        _require(
            preregistration_file
            == (repository / PREREGISTRATION_RELATIVE).resolve(strict=True),
            "preregistration must use the canonical repository path",
        )
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    _require(
        frozenset(preregistration) == PREREGISTRATION_FIELDS,
        "preregistration field set mismatch",
    )
    _require(
        frozenset(PREREGISTRATION_FIELD_AUTHORITY_LEDGER) == PREREGISTRATION_FIELDS,
        "internal preregistration authority coverage mismatch",
    )
    semantic_sha256 = preregistration.get("preregistration_sha256")
    _require(type(semantic_sha256) is str, "preregistration semantic hash is missing")
    unhashed = {
        key: value
        for key, value in preregistration.items()
        if key != "preregistration_sha256"
    }
    _require(
        canonical_sha256(unhashed) == semantic_sha256,
        "preregistration semantic hash mismatch",
    )
    _require(
        preregistration.get("schema_version") == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema mismatch",
    )
    generated_at = preregistration.get("generated_at_utc")
    _require(type(generated_at) is str, "generated_at_utc is missing")
    try:
        parsed_generated_at = datetime.fromisoformat(cast(str, generated_at))
    except ValueError as exc:
        raise ValueError("generated_at_utc must be ISO-8601") from exc
    generated_at_offset = parsed_generated_at.utcoffset()
    _require(
        parsed_generated_at.tzinfo is not None
        and generated_at_offset is not None
        and generated_at_offset.total_seconds() == 0,
        "generated_at_utc must be UTC",
    )
    _require(
        generated_at == PREREGISTRATION_GENERATED_AT_UTC,
        "generated_at_utc authority mismatch",
    )
    _validated_commit_a_changed_files(preregistration)
    _validate_preexisting_main_validation_authority(preregistration)
    expected_historical = {
        "commit": HISTORICAL_HUMAN_COMMIT_A,
        "status": "SUPERSEDED_NON_AUTHORITATIVE",
        "previous_contract": "EXTERNAL_HUMAN_64_48",
        "retained_for": "AUDIT_HISTORY_ONLY",
        "candidate_data_seen": False,
        "formal_attempt_started": False,
    }
    _require(
        preregistration.get("supersedes_commit") == HISTORICAL_HUMAN_COMMIT_A
        and _canonical_contract_json_equal(
            preregistration.get("historical_supersession"), expected_historical
        ),
        "historical supersession authority mismatch",
    )
    for obsolete_field in (
        "superseded_before_blind_data_access",
        "superseded_pre_data_commit_a",
        "superseded_pre_data_commit_as",
        "supersession_reason",
        "router_promotion_requires_separate_human_decision",
    ):
        _require(
            obsolete_field not in preregistration,
            f"obsolete human preregistration field remains active: {obsolete_field}",
        )
    _require(
        preregistration.get("research_question") == TASK8_RESEARCH_QUESTION,
        "research question mismatch",
    )
    _require(
        preregistration.get("blind_v2_candidate_data_seen") is False
        and preregistration.get("blind_v2_data_seen") is False
        and preregistration.get("blind_v2_data_seen_compatibility")
        == "LEGACY_PRE_DATA_TRUTH_ONLY",
        "blind-v2 candidate data seen truth mismatch",
    )
    legacy_truth = deepcopy(preregistration)
    legacy_truth["schema_version"] = "router-v2-blind-v2-preregistration-v1"
    validate_preregistration_truth(legacy_truth)

    protected = {
        key: canonical_sha256(preregistration.get(key))
        for key in PROTECTED_PREREGISTRATION_SUBTREE_SHA256
    }
    _require(
        preregistration.get("protected_preregistration_subtree_sha256")
        == PROTECTED_PREREGISTRATION_SUBTREE_SHA256
        and protected == PROTECTED_PREREGISTRATION_SUBTREE_SHA256,
        "protected preregistration identity drift",
    )
    expected_protected_semantic_commitment = (
        _protected_semantic_commitment_from_preregistration_sources(
            preregistration, repository
        )
    )
    _require_exact_json_authority(
        preregistration.get("protected_semantic_commitment"),
        expected_protected_semantic_commitment,
        message="protected semantic commitment mismatch",
    )

    expected_construction = _task8_agent_construction_authority()
    construction = preregistration.get("agent_construction")
    _require(
        _canonical_contract_json_equal(construction, expected_construction)
        and preregistration.get("agent_construction_sha256")
        == canonical_sha256(expected_construction)
        and set(expected_construction["terminal"]["terminal_states"])
        == TERMINAL_STATES,
        "Agent construction authority mismatch",
    )
    expected_semantic = _task8_semantic_contamination_authority()
    semantic = preregistration.get("semantic_contamination")
    _require(
        _canonical_contract_json_equal(semantic, expected_semantic)
        and preregistration.get("semantic_contamination_sha256")
        == canonical_sha256(expected_semantic)
        and expected_semantic["materialized_model_files_sha256"]
        == canonical_sha256(expected_semantic["materialized_model_files"]),
        "semantic contamination authority mismatch",
    )

    contract = preregistered_evaluation_contract()
    _require(
        preregistration.get("preregistration_parent_git_commit")
        == PREREGISTRATION_PARENT_COMMIT
        and preregistration.get("origin_main_git_commit")
        == PREREGISTRATION_PARENT_COMMIT
        and preregistration.get("current_git_commit_before_commit_a")
        == TASK8_BASELINE_HEAD,
        "preregistration parent Git binding mismatch",
    )
    _require(
        type(preregistration.get("blind_v2_expected_task_count")) is int
        and preregistration.get("blind_v2_expected_task_count") == POSITIVE_TASK_COUNT
        and type(preregistration.get("blind_v2_expected_negative_labeled_task_count"))
        is int
        and preregistration.get("blind_v2_expected_negative_labeled_task_count")
        == TEMPTING_NEGATIVE_COUNT,
        "blind-v2 count binding mismatch",
    )
    _require_exact_json_authority(
        preregistration.get("statistics"),
        contract["statistics"],
        message="statistics binding mismatch",
    )
    _require_exact_json_authority(
        preregistration.get("latency_measurement_protocol"),
        contract["latency"],
        message="latency protocol binding mismatch",
    )
    _require_exact_json_authority(
        preregistration.get("single_attempt"),
        contract["single_attempt"],
        message="single-attempt binding mismatch",
    )
    _require_exact_json_authority(
        preregistration.get("non_actions"),
        contract["prohibited_actions"],
        message="non-action binding mismatch",
    )
    _require(
        preregistration.get("evaluation_output_namespace")
        == str(FINAL_NAMESPACE_RELATIVE),
        "canonical namespace binding mismatch",
    )
    expected_metric_definitions = {
        "raw_count_first": True,
        "positive_denominator": POSITIVE_TASK_COUNT,
        "negative_denominator": TEMPTING_NEGATIVE_COUNT,
        "fields": [
            "recall_at_1",
            "recall_at_5",
            "mrr",
            "ndcg_at_5",
            "negative_hit_at_1",
            "negative_hit_at_5",
            "first_negative_rank",
            "latency_p50_ms",
            "latency_p95_ms",
        ],
        "aggregate_mean": "arithmetic",
        "aggregate_std": "sample_n_minus_1",
    }
    _require_exact_json_authority(
        preregistration.get("metric_definitions"),
        expected_metric_definitions,
        message="metric definition binding mismatch",
    )
    for field, expected_truth in (
        ("retraining_allowed", False),
        ("threshold_change_allowed", False),
        ("best_seed_selection_allowed", False),
        ("posthoc_tuning_allowed", False),
        ("blind_v3_allowed", False),
        ("default_router_unchanged", True),
        ("production_ready", False),
        ("release_eligible", False),
        ("release_authorized", False),
    ):
        _require(
            preregistration.get(field) is expected_truth,
            f"preregistration truth binding mismatch: {field}",
        )
    _require(
        type(preregistration.get("router_decision")) is str
        and preregistration.get("router_decision") == "KEEP_BASELINE",
        "preregistration truth binding mismatch: router_decision",
    )
    _require(preregistration.get("gate") == contract["gate"], "gate binding mismatch")
    evaluator = preregistration.get("evaluator")
    _require(type(evaluator) is dict, "evaluator binding is missing")
    evaluator = cast(dict[str, Any], evaluator)
    _require(
        frozenset(evaluator) == EVALUATOR_FIELDS,
        "evaluator field set mismatch",
    )
    _require_exact_json_authority(
        evaluator.get("arms"),
        list(ARMS),
        message="evaluator arm authority mismatch",
    )
    _require_exact_json_authority(
        evaluator.get("seeds"),
        list(SEEDS),
        message="evaluator seed authority mismatch",
    )
    _require(
        evaluator.get("contract_sha256") == canonical_sha256(contract),
        "evaluator contract hash mismatch",
    )
    gate_artifact = preregistration.get("pilot_002_gate_artifact")
    _require(type(gate_artifact) is dict, "pilot-002 gate artifact binding is missing")
    gate_artifact = cast(dict[str, Any], gate_artifact)
    _require(
        gate_artifact.get("gate_semantic_sha256") == canonical_sha256(contract["gate"])
        and preregistration.get("gate_sha256")
        == canonical_sha256(preregistration["gate"]),
        "gate binding mismatch",
    )
    gate_file = _repository_file(
        repository, gate_artifact.get("path"), label="gate artifact"
    )
    _require(
        _sha256_file(gate_file) == gate_artifact.get("file_sha256"),
        "gate artifact file hash mismatch",
    )
    gate_document = _json_no_duplicate_keys(gate_file.read_bytes(), "gate artifact")
    _require(gate_document.get("gate") == contract["gate"], "gate binding mismatch")
    _require(
        gate_document.get("plan_sha256") == gate_artifact.get("plan_semantic_sha256"),
        "gate plan semantic hash mismatch",
    )

    query = preregistration.get("query_contract")
    _require(type(query) is dict, "query contract binding is missing")
    query = cast(dict[str, Any], query)
    _require(
        query.get("version") == QUERY_CONTRACT_VERSION,
        "query contract version mismatch",
    )
    query_file = _repository_file(repository, query.get("path"), label="query contract")
    _require(
        _sha256_file(query_file) == query.get("sha256")
        and preregistration.get("query_contract_sha256") == canonical_sha256(query),
        "query contract source hash mismatch",
    )
    skill_index = preregistration.get("skill_index")
    _require(type(skill_index) is dict, "skill index binding is missing")
    skill_index = cast(dict[str, Any], skill_index)
    skill_index_file = _repository_file(
        repository, skill_index.get("path"), label="skill index"
    )
    _require(
        _sha256_file(skill_index_file) == skill_index.get("sha256")
        and preregistration.get("skill_index_semantic_sha256")
        == canonical_sha256(
            _json_value_no_duplicate_keys(
                skill_index_file.read_bytes(), "canonical skill index"
            )
        ),
        "skill index hash mismatch",
    )
    skill_builder = preregistration.get("skill_representation_builder")
    _require(type(skill_builder) is dict, "skill builder binding is missing")
    skill_builder = cast(dict[str, Any], skill_builder)
    _require(
        skill_builder.get("version") == SKILL_REPRESENTATION_BUILDER_VERSION,
        "skill builder version mismatch",
    )
    skill_builder_file = _repository_file(
        repository, skill_builder.get("path"), label="skill builder"
    )
    _require(
        _sha256_file(skill_builder_file) == skill_builder.get("sha256")
        and preregistration.get("skill_representation_builder_sha256")
        == canonical_sha256(skill_builder),
        "skill builder source hash mismatch",
    )
    source_files = evaluator.get("source_files")
    _require(
        type(source_files) is list and len(source_files) == len(EVALUATOR_SOURCE_PATHS),
        "evaluator sources are missing",
    )
    source_rows = cast(list[Any], source_files)
    _require(
        all(
            type(raw_row) is dict
            and frozenset(cast(dict[str, Any], raw_row)) == EVALUATOR_SOURCE_ROW_FIELDS
            for raw_row in source_rows
        ),
        "evaluator source row field set mismatch",
    )
    source_rows = cast(list[dict[str, Any]], source_rows)
    source_paths = tuple(cast(str, row["path"]) for row in source_rows)
    _require(
        len(EVALUATOR_SOURCE_PATHS) == 4
        and len(set(EVALUATOR_SOURCE_PATHS)) == 4
        and source_paths == EVALUATOR_SOURCE_PATHS
        and len(set(source_paths)) == len(source_paths),
        "evaluator source path sequence mismatch",
    )
    expected_source_rows = []
    for relative in EVALUATOR_SOURCE_PATHS:
        source = _repository_file(repository, relative, label="evaluator source")
        expected_source_rows.append({"path": relative, "sha256": _sha256_file(source)})
    _require(
        source_rows == expected_source_rows,
        "evaluator source hash mismatch",
    )
    expected_source_aggregate = canonical_sha256(expected_source_rows)
    _require(
        evaluator.get("source_files_sha256") == expected_source_aggregate,
        "evaluator source aggregate hash mismatch",
    )

    frozen_inputs = preregistration.get("frozen_inputs")
    _require(type(frozen_inputs) is dict, "frozen input bindings are missing")
    frozen_inputs = cast(dict[str, Any], frozen_inputs)
    _require(
        preregistration.get("frozen_inputs_sha256") == canonical_sha256(frozen_inputs),
        "frozen input aggregate hash mismatch",
    )
    for key in (
        "training_data_manifest",
        "accepted_pairs",
        "heldout_labels",
        "pilot_002_manifest",
        "pilot_002_truth_erratum",
        "pilot_002_evaluation_summary",
        "pilot_002_per_seed",
        "pilot_002_result_report",
        "pilot_002_route_results",
    ):
        binding = frozen_inputs.get(key)
        _require(type(binding) is dict, f"frozen {key} binding is missing")
        binding = cast(dict[str, Any], binding)
        frozen_file = _repository_file(
            repository, binding.get("path"), label=f"frozen {key}"
        )
        _require(
            _sha256_file(frozen_file) == binding.get("sha256"),
            f"frozen {key} hash mismatch",
        )

    phase16_files = preregistration.get("old_phase16_prompt_files")
    _require(
        type(phase16_files) is list and len(phase16_files) == 16,
        "old Phase 16 prompt bindings are missing",
    )
    _require(
        preregistration.get("old_phase16_prompt_files_sha256")
        == canonical_sha256(phase16_files),
        "old Phase 16 prompt aggregate hash mismatch",
    )
    phase16_paths: set[str] = set()
    for raw_binding in cast(list[Any], phase16_files):
        _require(type(raw_binding) is dict, "old Phase 16 prompt binding mismatch")
        binding = cast(dict[str, Any], raw_binding)
        phase16_file = _repository_file(
            repository, binding.get("path"), label="old Phase 16 prompt"
        )
        relative = phase16_file.relative_to(repository).as_posix()
        _require(relative not in phase16_paths, "old Phase 16 prompt path duplicated")
        phase16_paths.add(relative)
        _require(
            _sha256_file(phase16_file) == binding.get("sha256"),
            "old Phase 16 prompt hash mismatch",
        )

    pilot_binding = cast(dict[str, Any], frozen_inputs["pilot_002_manifest"])
    pilot_file = Path(pilot_manifest_path).resolve(strict=True)
    _require(
        pilot_file
        == (repository / PILOT_MANIFEST_RELATIVE).resolve(strict=True)
        == _repository_file(
            repository, pilot_binding.get("path"), label="pilot-002 manifest"
        ),
        "pilot-002 manifest path is not preregistered",
    )
    pilot = _json_no_duplicate_keys(pilot_file.read_bytes(), "pilot-002 manifest")
    _require(
        pilot.get("manifest_sha256") == pilot_binding.get("semantic_sha256"),
        "pilot-002 manifest semantic hash mismatch",
    )

    base_binding = preregistration.get("base_model")
    _require(type(base_binding) is dict, "base model binding is missing")
    base_binding = cast(dict[str, Any], base_binding)
    base = pilot.get("base_model")
    _require(type(base) is dict, "pilot base model binding is missing")
    base = cast(dict[str, Any], base)
    _require(
        base_binding.get("model_id") == base.get("id")
        and base_binding.get("revision") == base.get("revision")
        and base_binding.get("checkpoint_path") == base.get("path")
        and base_binding.get("model_file_manifest_sha256")
        == base.get("file_manifest_sha256")
        and base_binding.get("model_files") == base.get("file_manifest_rows"),
        "base model binding mismatch",
    )
    artifacts = pilot.get("training_artifacts")
    _require(type(artifacts) is list, "pilot training artifacts are missing")
    artifacts = cast(list[dict[str, Any]], artifacts)
    arm_a_bindings = base_binding.get("per_seed_model_manifest_bindings")
    _require(
        type(arm_a_bindings) is list
        and {
            cast(dict[str, Any], row).get("seed")
            for row in cast(list[Any], arm_a_bindings)
        }
        == set(SEEDS),
        "Arm A model manifest grid mismatch",
    )
    for raw_preregistered in cast(list[Any], arm_a_bindings):
        preregistered = cast(dict[str, Any], raw_preregistered)
        actual = _artifact_binding(artifacts, "A", preregistered["seed"])
        for field in (
            "model_path",
            "model_manifest_path",
            "model_manifest_file_sha256",
            "model_manifest_sha256",
            "model_file_manifest_sha256",
        ):
            _require(
                preregistered.get(field) == actual.get(field),
                "Arm A model manifest binding mismatch",
            )
    arm_c = preregistration.get("arm_c_checkpoints")
    _require(type(arm_c) is list and len(arm_c) == 3, "Arm C bindings are missing")
    for raw_preregistered in cast(list[Any], arm_c):
        preregistered = cast(dict[str, Any], raw_preregistered)
        actual = _artifact_binding(artifacts, "C", preregistered["seed"])
        expected_checkpoint = {
            "checkpoint_path": actual["model_path"],
            "model_manifest_path": actual["model_manifest_path"],
            "model_manifest_file_sha256": actual["model_manifest_file_sha256"],
            "model_manifest_sha256": actual["model_manifest_sha256"],
            "model_file_manifest_sha256": actual["model_file_manifest_sha256"],
            "model_files": actual["model_file_manifest"],
        }
        _require(
            all(
                preregistered.get(field) == value
                for field, value in expected_checkpoint.items()
            ),
            "Arm C checkpoint binding mismatch",
        )

    if verify_model_files:
        base_path = Path(cast(str, base["path"]))
        _verify_model_files(
            base_path,
            cast(list[dict[str, Any]], base["file_manifest_rows"]),
            cast(str, base["file_manifest_sha256"]),
        )
        for arm in ARMS:
            for seed in SEEDS:
                artifact = _artifact_binding(artifacts, arm, seed)
                model_path = Path(artifact["model_path"])
                _verify_model_files(
                    model_path,
                    artifact["model_file_manifest"],
                    artifact["model_file_manifest_sha256"],
                )
                model_manifest = Path(artifact["model_manifest_path"])
                _require(
                    model_manifest.is_file()
                    and _sha256_file(model_manifest)
                    == artifact["model_manifest_file_sha256"],
                    f"{arm}/{seed} model manifest file hash mismatch",
                )
        _verify_task8_semantic_model_snapshot()
    return {
        "status": "VALID",
        "preregistration_sha256": semantic_sha256,
        "pilot_manifest_sha256": pilot_binding["sha256"],
        "preregistration_file_sha256": _sha256_file(preregistration_file),
        "model_files_verified": verify_model_files,
        "semantic_model_files_verified": verify_model_files,
    }


def read_frozen_dataset_documents(repository_root: Path | str) -> dict[str, bytes]:
    repository = Path(repository_root).resolve(strict=True)
    unresolved_root = repository
    for component in DATASET_FREEZE_RELATIVE.parts:
        unresolved_root /= component
        _require(
            not unresolved_root.is_symlink(),
            "frozen dataset path components must not be symlinks",
        )
    root = unresolved_root.resolve(strict=True)
    _require(root.is_relative_to(repository), "frozen dataset root escapes repository")
    _require(root.is_dir(), "frozen dataset root must be a directory")
    actual = {path.name for path in root.iterdir()}
    _require(
        actual == set(DATASET_FREEZE_FILENAMES),
        "frozen dataset directory must contain exactly three files",
    )
    documents: dict[str, bytes] = {}
    for filename in DATASET_FREEZE_FILENAMES:
        path = _safe_repository_regular_file(
            repository,
            DATASET_FREEZE_RELATIVE / filename,
            label="frozen dataset",
        )
        _require(path.is_relative_to(root), "frozen dataset file escapes root")
        documents[filename] = path.read_bytes()
    return documents


def build_authoritative_lineage_bindings(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    pilot_manifest_path: Path | str,
    frozen_documents: dict[str, bytes],
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    authority = validate_preregistration_authority(
        preregistration_path,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    preregistration_file = Path(preregistration_path).resolve(strict=True)
    preregistration = _json_no_duplicate_keys(
        preregistration_file.read_bytes(), "preregistration"
    )
    pilot_file = Path(pilot_manifest_path).resolve(strict=True)
    pilot = _json_no_duplicate_keys(pilot_file.read_bytes(), "pilot-002 manifest")
    blind_manifest = _json_no_duplicate_keys(
        frozen_documents["blind-v2-manifest.json"], "blind-v2 manifest"
    )
    blind_task_rows = _jsonl_no_duplicate_keys(
        frozen_documents["blind-v2-tasks.jsonl"], "blind-v2 tasks"
    )
    agent_construction = deepcopy(blind_manifest["agent_construction"])
    _require(
        type(agent_construction) is dict,
        "blind-v2 Agent construction lineage is missing",
    )
    agent_construction["review_summary_file_sha256"] = _sha256_bytes(
        frozen_documents["blind-v2-review-summary.json"]
    )
    artifacts = cast(list[dict[str, Any]], pilot["training_artifacts"])
    model_bindings = []
    for seed in SEEDS:
        for arm in ARMS:
            artifact = _artifact_binding(artifacts, arm, seed)
            model_bindings.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "model_path": artifact["model_path"],
                    "model_manifest_path": artifact["model_manifest_path"],
                    "model_manifest_file_sha256": artifact[
                        "model_manifest_file_sha256"
                    ],
                    "model_manifest_sha256": artifact["model_manifest_sha256"],
                    "model_file_manifest_sha256": artifact[
                        "model_file_manifest_sha256"
                    ],
                    "model_files": artifact["model_file_manifest"],
                }
            )
    return {
        "preregistration": {
            "path": preregistration_file.relative_to(repository).as_posix(),
            "file_sha256": authority["preregistration_file_sha256"],
            "semantic_sha256": authority["preregistration_sha256"],
        },
        "pilot_manifest": cast(dict[str, Any], preregistration["frozen_inputs"])[
            "pilot_002_manifest"
        ],
        "frozen_inputs": preregistration["frozen_inputs"],
        "old_phase16_prompt_files": preregistration["old_phase16_prompt_files"],
        "base_model": {
            "id": cast(dict[str, Any], pilot["base_model"])["id"],
            "revision": cast(dict[str, Any], pilot["base_model"])["revision"],
            "file_manifest_sha256": cast(dict[str, Any], pilot["base_model"])[
                "file_manifest_sha256"
            ],
            "model_files": cast(dict[str, Any], pilot["base_model"])[
                "file_manifest_rows"
            ],
        },
        "evaluation_models": model_bindings,
        "blind_v2_dataset": {
            "commit_a": blind_manifest["commit_a"],
            "tasks_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-tasks.jsonl"]
            ),
            "manifest_file_sha256": _sha256_bytes(
                frozen_documents["blind-v2-manifest.json"]
            ),
            "dataset_sha256": blind_manifest["dataset_sha256"],
            "source_file_sha256": blind_manifest["source_file_sha256"],
            "per_row_prompt_sha256": blind_manifest["per_row_prompt_sha256"],
            "task_rows": blind_task_rows,
        },
        "agent_construction": agent_construction,
        "skill_index": preregistration["skill_index"],
        "query_contract": preregistration["query_contract"],
        "skill_representation_builder": preregistration["skill_representation_builder"],
        "gate": preregistration["pilot_002_gate_artifact"],
        "evaluator": preregistration["evaluator"],
    }


def _validated_agent_config_smoke_invocations(
    invocations: Any,
) -> list[dict[str, Any]]:
    _require(
        type(invocations) is list and len(invocations) == len(AGENT_CONFIGS),
        "Agent-config smoke must contain exactly three provider invocations",
    )
    normalized: list[dict[str, Any]] = []
    seen_identities: set[str] = set()
    roles = [
        invocation.get("role") if type(invocation) is dict else None
        for invocation in invocations
    ]
    _require(
        roles == list(AGENT_CONFIGS),
        "Agent-config smoke role coverage mismatch",
    )
    for raw_invocation, role in zip(invocations, AGENT_CONFIGS, strict=True):
        _require(
            type(raw_invocation) is dict,
            "Agent-config smoke invocation must be an object",
        )
        identity_fields = {"session_id", "thread_id"}.intersection(raw_invocation)
        _require(
            len(identity_fields) == 1,
            "Agent-config smoke requires exactly one session/thread id",
        )
        invocation = _exact_object_fields(
            raw_invocation,
            {
                "role",
                "fork_context",
                "history_message_count",
                "imported_memory_count",
                "requested_model",
                "returned_model",
                "reasoning_effort",
                "timeout_seconds",
                "transport_retry_count",
                "request_text",
                "request_sha256",
                "response_text",
                "response_sha256",
                "timestamp_utc",
                *identity_fields,
            },
            "Agent-config smoke invocation",
        )
        identity_field = next(iter(identity_fields))
        identity = _nonempty_string(
            invocation[identity_field], "Agent-config smoke session/thread id"
        )
        _require(
            identity not in seen_identities,
            "Agent-config smoke session/thread id must be unique",
        )
        seen_identities.add(identity)
        config = AGENT_CONFIGS[role]
        _require(invocation["role"] == role, "Agent-config smoke role mismatch")
        _require(
            invocation["fork_context"] is False,
            "Agent-config smoke fork context must be false",
        )
        _require(
            type(invocation["history_message_count"]) is int
            and invocation["history_message_count"] == 0,
            "Agent-config smoke history message count must be integer zero",
        )
        _require(
            type(invocation["imported_memory_count"]) is int
            and invocation["imported_memory_count"] == 0,
            "Agent-config smoke imported memory count must be integer zero",
        )
        _require(
            invocation["requested_model"] == config["model"],
            "Agent-config smoke requested model mismatch",
        )
        _require(
            invocation["returned_model"] == config["model"],
            "Agent-config smoke returned model mismatch",
        )
        _require(
            invocation["reasoning_effort"] == config["reasoning_effort"],
            "Agent-config smoke reasoning effort mismatch",
        )
        _require(
            type(invocation["timeout_seconds"]) is int
            and invocation["timeout_seconds"] == config["timeout_seconds"],
            "Agent-config smoke timeout mismatch",
        )
        _require(
            type(invocation["transport_retry_count"]) is int
            and invocation["transport_retry_count"] == 0,
            "Agent-config smoke transport retry count mismatch",
        )
        _require(
            invocation["request_text"] == AGENT_CONFIG_SMOKE_REQUEST_TEXT
            and invocation["request_sha256"]
            == _sha256_bytes(AGENT_CONFIG_SMOKE_REQUEST_TEXT.encode("utf-8")),
            "Agent-config smoke dummy request mismatch",
        )
        _require(
            invocation["response_text"] == AGENT_CONFIG_SMOKE_RESPONSE_TEXT
            and invocation["response_sha256"]
            == _sha256_bytes(AGENT_CONFIG_SMOKE_RESPONSE_TEXT.encode("utf-8")),
            "Agent-config smoke dummy response mismatch",
        )
        _nonempty_string(invocation["timestamp_utc"], "Agent-config smoke timestamp")
        normalized.append(deepcopy(invocation))
    return normalized


def build_agent_config_smoke_receipt(
    invocations: list[dict[str, Any]],
    *,
    commit_a: str,
    preregistration_sha256: str,
) -> dict[str, Any]:
    commit_a = _exact_lowercase_hex(
        commit_a, length=40, label="Agent-config smoke Commit A-agent"
    )
    preregistration_sha256 = _exact_lowercase_hex(
        preregistration_sha256,
        length=64,
        label="Agent-config smoke preregistration SHA-256",
    )
    normalized_invocations = _validated_agent_config_smoke_invocations(invocations)
    document = {
        "schema_version": "router-v2-blind-v2-agent-config-smoke-receipt-v1",
        "smoke_status": "PASS",
        "commit_a": commit_a,
        "preregistration_sha256": preregistration_sha256,
        "provider_invocation_count": len(normalized_invocations),
        "request_text": AGENT_CONFIG_SMOKE_REQUEST_TEXT,
        "response_text": AGENT_CONFIG_SMOKE_RESPONSE_TEXT,
        "invocations": normalized_invocations,
        "benchmark_metrics_computed": False,
        "blind_v2_data_read": False,
    }
    return {**document, "receipt_sha256": canonical_sha256(document)}


def agent_config_smoke_receipt_path(commit_a: str) -> Path:
    commit_a = _exact_lowercase_hex(
        commit_a, length=40, label="Agent-config smoke Commit A-agent"
    )
    return SMOKE_RECEIPT_ROOT / "agent-config" / f"{commit_a}.json"


def write_agent_config_smoke_receipt(receipt: dict[str, Any]) -> Path:
    commit_a = receipt.get("commit_a")
    _require(
        type(commit_a) is str,
        "Agent-config smoke receipt Commit A-agent is missing",
    )
    path = agent_config_smoke_receipt_path(cast(str, commit_a))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(receipt))
    return path


def validate_agent_config_smoke_receipt(
    *, commit_a: str, preregistration_sha256: str
) -> dict[str, Any]:
    path = agent_config_smoke_receipt_path(commit_a)
    receipt = _json_no_duplicate_keys(path.read_bytes(), "Agent-config smoke receipt")
    receipt_sha256 = receipt.get("receipt_sha256")
    unhashed = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _require(
        receipt_sha256 == canonical_sha256(unhashed),
        "Agent-config smoke receipt hash mismatch",
    )
    _require(
        receipt.get("commit_a") == commit_a
        and receipt.get("preregistration_sha256") == preregistration_sha256,
        "Agent-config smoke receipt authority mismatch",
    )
    invocations = receipt.get("invocations")
    _require(
        type(invocations) is list,
        "Agent-config smoke receipt structure mismatch",
    )
    rebuilt = build_agent_config_smoke_receipt(
        cast(list[dict[str, Any]], invocations),
        commit_a=commit_a,
        preregistration_sha256=preregistration_sha256,
    )
    _require(receipt == rebuilt, "Agent-config smoke receipt structure mismatch")
    return receipt


class _LocalSentenceTransformerEncoder:
    def __init__(self, model_path: Path) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real model smoke"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )

    def encode(
        self, texts: list[str], *, normalize_embeddings: bool
    ) -> list[list[float]]:
        value = self._model.encode(texts, normalize_embeddings=normalize_embeddings)
        if hasattr(value, "tolist"):
            value = value.tolist()
        return cast(list[list[float]], value)


def run_model_load_smoke(
    pilot_manifest_path: Path | str,
    *,
    repository_root: Path | str,
) -> dict[str, Any]:
    return _run_model_load_smoke(
        pilot_manifest_path,
        repository_root=repository_root,
        encoder_factory=None,
        authority_validator=validate_preregistration_authority,
        commit_b_validator=validate_commit_b_repository,
    )


def _run_model_load_smoke(
    pilot_manifest_path: Path | str,
    *,
    repository_root: Path | str,
    encoder_factory: EncoderFactory | None,
    authority_validator: AuthorityValidator,
    commit_b_validator: CommitBValidator,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    frozen_manifest_path = _safe_repository_regular_file(
        repository,
        DATASET_FREEZE_RELATIVE / "blind-v2-manifest.json",
        label="model-load smoke frozen dataset manifest",
    )
    frozen_manifest_source = frozen_manifest_path.read_bytes()
    frozen_manifest = _json_no_duplicate_keys(
        frozen_manifest_source, "model-load smoke frozen dataset manifest"
    )
    commit_a = _exact_lowercase_hex(
        frozen_manifest.get("commit_a"),
        length=40,
        label="model-load smoke Commit A-agent",
    )
    _require(
        commit_a != HISTORICAL_HUMAN_COMMIT_A,
        "historical Commit A has been superseded and is not active",
    )
    commit_state = commit_b_validator(repository, commit_a=commit_a)
    repository_commit_a = _exact_lowercase_hex(
        commit_state.get("commit_a"),
        length=40,
        label="model-load smoke repository Commit A-agent",
    )
    commit_b = _exact_lowercase_hex(
        commit_state.get("commit_b"),
        length=40,
        label="model-load smoke Commit B",
    )
    _require(
        commit_b != commit_a,
        "model-load smoke Commit B must differ from Commit A-agent",
    )
    _require(
        repository_commit_a == commit_a,
        "model-load smoke Commit B repository authority mismatch",
    )
    preregistration_file = _safe_repository_regular_file(
        repository,
        PREREGISTRATION_RELATIVE,
        label="model-load smoke preregistration",
    )
    preregistration_source = preregistration_file.read_bytes()
    preregistration_sha256 = _sha256_bytes(preregistration_source)
    frozen_dataset_manifest_sha256 = _sha256_bytes(frozen_manifest_source)
    preregistration_authority = authority_validator(
        preregistration_file,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    _require(
        preregistration_authority.get("preregistration_file_sha256")
        == preregistration_sha256,
        "model-load smoke preregistration byte authority mismatch",
    )
    manifest = _json_no_duplicate_keys(
        Path(pilot_manifest_path).read_bytes(), "pilot manifest"
    )
    base = manifest["base_model"]
    base_path = Path(base["path"])
    _verify_model_files(
        base_path, base["file_manifest_rows"], base["file_manifest_sha256"]
    )
    c_artifacts = sorted(
        [row for row in manifest["training_artifacts"] if row.get("arm") == "C"],
        key=lambda row: row["seed"],
    )
    _require(
        [row["seed"] for row in c_artifacts] == list(SEEDS), "Arm C smoke grid mismatch"
    )
    for artifact in c_artifacts:
        model_path = Path(artifact["model_path"])
        _verify_model_files(
            model_path,
            artifact["model_file_manifest"],
            artifact["model_file_manifest_sha256"],
        )
        manifest_path = Path(artifact["model_manifest_path"])
        _require(manifest_path.is_file(), "missing model manifest")
        _require(
            _sha256_file(manifest_path) == artifact["model_manifest_file_sha256"],
            "model manifest file hash mismatch",
        )
    factory = encoder_factory or (
        lambda arm, seed, model_path: _LocalSentenceTransformerEncoder(model_path)
    )
    temporary = Path(tempfile.mkdtemp(prefix="hermes-blind-v2-model-smoke-"))
    os.chmod(temporary, 0o700)
    dimensions = []
    models = []
    try:
        materialized = temporary / "arm-A"
        shutil.copytree(base_path, materialized, symlinks=False)
        smoke_bindings = [
            {"arm": "A", "seed": 7170, "model_path": materialized},
            *[
                {
                    "arm": "C",
                    "seed": artifact["seed"],
                    "model_path": Path(artifact["model_path"]),
                }
                for artifact in c_artifacts
            ],
        ]
        for binding in smoke_bindings:
            encoder = factory(binding["arm"], binding["seed"], binding["model_path"])
            embeddings = encoder.encode(
                list(MODEL_LOAD_SMOKE_TEXTS), normalize_embeddings=True
            )
            if hasattr(embeddings, "tolist"):
                embeddings = embeddings.tolist()
            _require(
                type(embeddings) is list and len(embeddings) == 2,
                "smoke embedding row count mismatch",
            )
            _require(
                all(type(row) is list and row for row in embeddings),
                "smoke embeddings must be non-empty vectors",
            )
            dimension = len(embeddings[0])
            _require(
                all(len(row) == dimension for row in embeddings),
                "smoke embedding dimensions differ",
            )
            _require(
                all(math.isfinite(float(value)) for row in embeddings for value in row),
                "smoke embeddings must be finite",
            )
            dimensions.append(dimension)
            models.append({"arm": binding["arm"], "seed": binding["seed"]})
        _require(len(set(dimensions)) == 1, "model embedding dimensions differ")
        smoke = {
            "schema_version": "router-v2-blind-v2-model-load-smoke-v1",
            "smoke_status": "PASS",
            "models": models,
            "embedding_dimension": dimensions[0],
            "device": "cpu",
            "synthetic_strings": list(MODEL_LOAD_SMOKE_TEXTS),
            "benchmark_metrics_computed": False,
            "blind_v2_data_read": False,
        }
        return _build_model_load_smoke_receipt(
            smoke,
            commit_a=commit_a,
            commit_b=commit_b,
            preregistration_sha256=preregistration_sha256,
            frozen_dataset_manifest_sha256=frozen_dataset_manifest_sha256,
        )
    finally:
        shutil.rmtree(temporary)


def _build_model_load_smoke_receipt(
    smoke: dict[str, Any],
    *,
    commit_a: str,
    commit_b: str,
    preregistration_sha256: str,
    frozen_dataset_manifest_sha256: str,
) -> dict[str, Any]:
    _require(
        set(smoke)
        == {
            "schema_version",
            "smoke_status",
            "models",
            "embedding_dimension",
            "device",
            "synthetic_strings",
            "benchmark_metrics_computed",
            "blind_v2_data_read",
        },
        "smoke result structure mismatch",
    )
    _require(
        smoke.get("schema_version") == "router-v2-blind-v2-model-load-smoke-v1",
        "smoke schema mismatch",
    )
    _require(smoke.get("smoke_status") == "PASS", "passing smoke is required")
    _require(smoke.get("blind_v2_data_read") is False, "smoke read blind-v2 data")
    _require(
        smoke.get("benchmark_metrics_computed") is False,
        "smoke computed benchmark metrics",
    )
    _require(
        smoke.get("models")
        == [
            {"arm": "A", "seed": 7170},
            {"arm": "C", "seed": 7170},
            {"arm": "C", "seed": 7171},
            {"arm": "C", "seed": 7172},
        ],
        "smoke model grid mismatch",
    )
    _require(
        smoke.get("synthetic_strings") == list(MODEL_LOAD_SMOKE_TEXTS),
        "smoke strings mismatch",
    )
    _require(smoke.get("device") == "cpu", "smoke device must be exactly cpu")
    embedding_dimension = smoke.get("embedding_dimension")
    _require(
        type(embedding_dimension) is int and embedding_dimension > 0,
        "smoke embedding dimension must be a positive integer",
    )
    commit_a = _exact_lowercase_hex(commit_a, length=40, label="smoke Commit A-agent")
    commit_b = _exact_lowercase_hex(commit_b, length=40, label="smoke Commit B")
    _require(commit_b != commit_a, "smoke Commit B must differ from Commit A-agent")
    preregistration_sha256 = _exact_lowercase_hex(
        preregistration_sha256,
        length=64,
        label="smoke preregistration SHA-256",
    )
    frozen_dataset_manifest_sha256 = _exact_lowercase_hex(
        frozen_dataset_manifest_sha256,
        length=64,
        label="smoke frozen dataset manifest SHA-256",
    )
    document = {
        "schema_version": "router-v2-blind-v2-model-load-smoke-receipt-v2",
        "commit_a": commit_a,
        "commit_b": commit_b,
        "preregistration_sha256": preregistration_sha256,
        "frozen_dataset_manifest_sha256": frozen_dataset_manifest_sha256,
        "smoke": smoke,
    }
    return {**document, "receipt_sha256": canonical_sha256(document)}


def model_load_smoke_receipt_path(commit_a: str, commit_b: str) -> Path:
    commit_a = _exact_lowercase_hex(
        commit_a, length=40, label="model-load smoke Commit A-agent"
    )
    commit_b = _exact_lowercase_hex(
        commit_b, length=40, label="model-load smoke Commit B"
    )
    _require(
        commit_b != commit_a,
        "model-load smoke Commit B must differ from Commit A-agent",
    )
    return SMOKE_RECEIPT_ROOT / "model-load" / f"{commit_a}-{commit_b}.json"


def write_model_load_smoke_receipt(receipt: dict[str, Any]) -> Path:
    commit_a = receipt.get("commit_a")
    commit_b = receipt.get("commit_b")
    _require(type(commit_a) is str, "smoke receipt Commit A-agent is missing")
    _require(type(commit_b) is str, "smoke receipt Commit B is missing")
    path = model_load_smoke_receipt_path(cast(str, commit_a), cast(str, commit_b))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(receipt))
    return path


def validate_model_load_smoke_receipt(
    *,
    commit_a: str,
    commit_b: str,
    preregistration_sha256: str,
    frozen_dataset_manifest_sha256: str,
) -> dict[str, Any]:
    path = model_load_smoke_receipt_path(commit_a, commit_b)
    receipt = _json_no_duplicate_keys(path.read_bytes(), "model-load smoke receipt")
    receipt_sha256 = receipt.get("receipt_sha256")
    unhashed = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _require(
        receipt_sha256 == canonical_sha256(unhashed),
        "model-load smoke receipt hash mismatch",
    )
    _require(
        receipt.get("commit_a") == commit_a
        and receipt.get("commit_b") == commit_b
        and receipt.get("preregistration_sha256") == preregistration_sha256
        and receipt.get("frozen_dataset_manifest_sha256")
        == frozen_dataset_manifest_sha256,
        "model-load smoke receipt authority mismatch",
    )
    smoke = receipt.get("smoke")
    _require(type(smoke) is dict, "model-load smoke receipt structure mismatch")
    rebuilt = _build_model_load_smoke_receipt(
        cast(dict[str, Any], smoke),
        commit_a=commit_a,
        commit_b=commit_b,
        preregistration_sha256=preregistration_sha256,
        frozen_dataset_manifest_sha256=frozen_dataset_manifest_sha256,
    )
    _require(receipt == rebuilt, "model-load smoke receipt structure mismatch")
    return receipt


class _SentenceTransformerScorer:
    def __init__(self, model_path: Path, skills: list[dict[str, Any]]) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for real evaluation"
            ) from exc
        self._model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )
        self._skill_ids = [str(row["id"]) for row in skills]
        value = self._model.encode(
            [_skill_text(row) for row in skills], normalize_embeddings=True
        )
        if hasattr(value, "tolist"):
            value = value.tolist()
        self._skill_vectors = cast(list[list[float]], value)

    def rank(self, query: str, skill_ids: list[str]) -> list[str]:
        _require(skill_ids == self._skill_ids, "skill order changed during evaluation")
        value = self._model.encode([query], normalize_embeddings=True)
        if hasattr(value, "tolist"):
            value = value.tolist()
        query_vector = cast(list[list[float]], value)[0]
        scores = [
            quantize8(
                sum(
                    float(left) * float(right)
                    for left, right in zip(query_vector, vector, strict=True)
                )
            )
            for vector in self._skill_vectors
        ]
        return [
            skill_id
            for skill_id, _ in sorted(
                zip(self._skill_ids, scores, strict=True),
                key=lambda item: (-Decimal(item[1]), item[0]),
            )
        ]


_FORBIDDEN_LINEAGE_FIELDS = frozenset(
    {
        "analysis",
        "chain_of_thought",
        "human_review",
        "source_file_bytes",
        "source_bytes",
        "source_bytes_hex",
        "raw_source",
        "response",
        "raw_response",
        "response_body",
        "rationale",
        "raw_reasoning",
        "reason",
        "reasoning",
        "refusal",
        "hidden_reasoning",
    }
)


def _reject_forbidden_lineage_fields(value: Any) -> None:
    if type(value) is dict:
        for key, item in value.items():
            _require(
                type(key) is str and key not in _FORBIDDEN_LINEAGE_FIELDS,
                "forbidden legacy or raw lineage field",
            )
            _reject_forbidden_lineage_fields(item)
    elif type(value) is list:
        for item in value:
            _reject_forbidden_lineage_fields(item)


def _validated_evaluation_model_bindings(value: Any) -> list[dict[str, Any]]:
    _require(
        type(value) is list and len(value) == len(ARMS) * len(SEEDS),
        "evaluation model binding grid mismatch",
    )
    fields = {
        "arm",
        "seed",
        "model_path",
        "model_manifest_path",
        "model_manifest_file_sha256",
        "model_manifest_sha256",
        "model_file_manifest_sha256",
        "model_files",
    }
    model_file_fields = {"path", "size", "sha256"}
    bindings: list[dict[str, Any]] = []
    keys: list[tuple[str, int]] = []
    for raw_binding in value:
        binding = _exact_object_fields(raw_binding, fields, "evaluation model binding")
        arm = binding["arm"]
        seed = binding["seed"]
        _require(
            type(arm) is str and arm in ARMS and type(seed) is int and seed in SEEDS,
            "evaluation model binding identity mismatch",
        )
        for path_field in ("model_path", "model_manifest_path"):
            path = _nonempty_string(
                binding[path_field], f"evaluation model {path_field}"
            )
            _require(
                Path(path).is_absolute() and "\0" not in path,
                f"evaluation model {path_field} must be an absolute path",
            )
        for hash_field in (
            "model_manifest_file_sha256",
            "model_manifest_sha256",
            "model_file_manifest_sha256",
        ):
            _exact_lowercase_hex(
                binding[hash_field],
                length=64,
                label=f"evaluation model {hash_field}",
            )
        raw_files = binding["model_files"]
        _require(
            type(raw_files) is list and bool(raw_files),
            "evaluation model files must be a non-empty list",
        )
        files: list[dict[str, Any]] = []
        paths: list[str] = []
        for raw_file in raw_files:
            model_file = _exact_object_fields(
                raw_file, model_file_fields, "evaluation model file"
            )
            path = _nonempty_string(model_file["path"], "evaluation model file path")
            _require(
                path == path.strip()
                and path == unicodedata.normalize("NFC", path)
                and not path.startswith("/")
                and "\0" not in path
                and "\\" not in path
                and all(part not in {"", ".", ".."} for part in path.split("/")),
                "evaluation model file path must be normalized relative POSIX",
            )
            size = model_file["size"]
            _require(
                type(size) is int and size >= 0,
                "evaluation model file size mismatch",
            )
            sha256 = _exact_lowercase_hex(
                model_file["sha256"],
                length=64,
                label="evaluation model file SHA-256",
            )
            paths.append(path)
            files.append({"path": path, "size": size, "sha256": sha256})
        _require(
            paths == sorted(paths, key=lambda item: item.encode("utf-8"))
            and len(paths) == len(set(paths)),
            "evaluation model files must be uniquely sorted",
        )
        _require(
            binding["model_file_manifest_sha256"] == _manifest_rows_hash(files),
            "evaluation model file manifest hash mismatch",
        )
        keys.append((cast(str, arm), cast(int, seed)))
        bindings.append({**deepcopy(binding), "model_files": files})
    expected_keys = [(arm, seed) for seed in SEEDS for arm in ARMS]
    _require(
        keys == expected_keys and len(keys) == len(set(keys)),
        "evaluation model binding grid mismatch",
    )
    return bindings


def _validated_route_model_bindings(
    value: Any,
) -> dict[tuple[str, int], dict[str, Any]]:
    try:
        bindings = _validated_evaluation_model_bindings(value)
        return {
            (cast(str, binding["arm"]), cast(int, binding["seed"])): binding
            for binding in bindings
        }
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "evaluation model bindings must be the complete A/C seed grid"
        ) from exc


def _validated_committed_contamination(
    value: Any,
    *,
    source_file_sha256: dict[str, Any],
    candidate_outcomes: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "required_semantic_model_id",
        "required_semantic_model_revision",
        "materialized_model_files",
        "materialized_model_files_sha256",
        "semantic_scorer_runtime_verified",
        "semantic_scorer_receipt_sha256",
        "token_5gram_jaccard_reject_at_or_above",
        "character_5gram_jaccard_reject_at_or_above",
        "semantic_cosine_reject_at_or_above",
        "candidate_count",
        "clean_candidate_count",
        "rejected_candidate_count",
        "ledger_sha256",
        "scanner_config_sha256",
        "protected_authority",
        "protected_authority_sha256",
        "evidence_sha256",
        "ledger_file_sha256",
    }
    contamination = _exact_object_fields(
        value, fields, "committed contamination authority"
    )
    scanner_config = _validated_contamination_scanner_config(
        {
            "required_semantic_model_id": contamination["required_semantic_model_id"],
            "required_semantic_model_revision": contamination[
                "required_semantic_model_revision"
            ],
            "materialized_model_files": contamination["materialized_model_files"],
            "materialized_model_files_sha256": contamination[
                "materialized_model_files_sha256"
            ],
            "semantic_scorer_runtime_verified": contamination[
                "semantic_scorer_runtime_verified"
            ],
            "semantic_scorer_receipt_sha256": contamination[
                "semantic_scorer_receipt_sha256"
            ],
            "token_5gram_jaccard_reject_at_or_above": contamination[
                "token_5gram_jaccard_reject_at_or_above"
            ],
            "character_5gram_jaccard_reject_at_or_above": contamination[
                "character_5gram_jaccard_reject_at_or_above"
            ],
            "semantic_cosine_reject_at_or_above": contamination[
                "semantic_cosine_reject_at_or_above"
            ],
            "normalization": "NFKC-casefold-collapse-whitespace",
            "selection_seed": _SELECTION_AUTHORITY["selection_seed"],
            "protected_authority": contamination["protected_authority"],
            "protected_authority_sha256": contamination["protected_authority_sha256"],
        }
    )
    contamination_ledger_hash = _exact_lowercase_hex(
        source_file_sha256["blind-v2-contamination.jsonl"],
        length=64,
        label="committed contamination ledger SHA-256",
    )
    rejected_count = sum(
        outcome == "REJECTED_CONTAMINATION" for outcome in candidate_outcomes.values()
    )
    _require(
        contamination["candidate_count"] == len(candidate_outcomes)
        and contamination["clean_candidate_count"]
        == len(candidate_outcomes) - rejected_count
        and contamination["rejected_candidate_count"] == rejected_count
        and contamination["ledger_sha256"] == contamination_ledger_hash
        and contamination["ledger_file_sha256"] == contamination_ledger_hash
        and contamination["scanner_config_sha256"] == canonical_sha256(scanner_config),
        "committed contamination aggregate mismatch",
    )
    _exact_lowercase_hex(
        contamination["evidence_sha256"],
        length=64,
        label="committed contamination evidence SHA-256",
    )
    return deepcopy(contamination)


def _validated_pre_scoring_authority(
    *,
    tasks: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
    commit_a: str,
    commit_b: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_started_artifact: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    message = "pre-scoring authority mismatch"
    try:
        _exact_lowercase_hex(commit_a, length=40, label="pre-scoring Commit A")
        _exact_lowercase_hex(commit_b, length=40, label="pre-scoring Commit B")
        _exact_lowercase_hex(
            attempt_token_sha256,
            length=64,
            label="pre-scoring attempt token SHA-256",
        )
        _require(
            type(input_artifacts) is dict
            and set(input_artifacts)
            == {
                "preregistration.json",
                "blind-v2-tasks.jsonl",
                "blind-v2-manifest.json",
                "review-summary.json",
            },
            message,
        )
        frozen_tasks = _validated_evaluation_frozen_tasks(
            None,
            commit_a=commit_a,
            commit_b=commit_b,
            attempt_token_sha256=attempt_token_sha256,
            frozen_bindings=frozen_bindings,
            input_artifacts=input_artifacts,
            attempt_started_artifact=attempt_started_artifact,
        )
        projected_skills = _validate_evaluation_agent_construction_authority(
            frozen_bindings, input_artifacts, frozen_tasks
        )
        frozen_models = _validated_evaluation_model_bindings(
            frozen_bindings["evaluation_models"]
        )
        _require(
            tasks == frozen_tasks
            and _project_canonical_skills(skills) == projected_skills
            and model_bindings == frozen_models,
            message,
        )
        return (
            deepcopy(frozen_tasks),
            deepcopy(projected_skills),
            deepcopy(frozen_models),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc


def evaluate_routes(
    tasks: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    model_bindings: list[dict[str, Any]],
    *,
    commit_a: str,
    commit_b: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_started_artifact: bytes,
    scorer_factory: ScorerFactory | None = None,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> list[dict[str, Any]]:
    tasks, skills, model_bindings = _validated_pre_scoring_authority(
        tasks=tasks,
        skills=skills,
        model_bindings=model_bindings,
        commit_a=commit_a,
        commit_b=commit_b,
        attempt_token_sha256=attempt_token_sha256,
        frozen_bindings=frozen_bindings,
        input_artifacts=input_artifacts,
        attempt_started_artifact=attempt_started_artifact,
    )
    _require(
        len(tasks) == POSITIVE_TASK_COUNT,
        f"evaluation requires {POSITIVE_TASK_COUNT} tasks",
    )
    ordered_tasks = sorted(tasks, key=lambda row: row["task_id"])
    _require(
        len({row["task_id"] for row in ordered_tasks}) == POSITIVE_TASK_COUNT,
        "evaluation task ids must be unique",
    )
    ordered_skills = sorted(skills, key=lambda row: row["id"])
    skill_ids = [str(row["id"]) for row in ordered_skills]
    _require(
        len(skill_ids) == 16 and len(set(skill_ids)) == 16,
        "evaluation requires 16 skills",
    )
    binding_grid = _validated_route_model_bindings(model_bindings)
    model_grid_authority_sha256 = canonical_sha256(
        [binding_grid[(arm, seed)] for seed in SEEDS for arm in ARMS]
    )
    routes = []
    for seed in SEEDS:
        for arm in ARMS:
            binding = binding_grid[(arm, seed)]
            model_path = Path(binding["model_path"])
            scorer = (
                scorer_factory(arm, seed, model_path)
                if scorer_factory is not None
                else _SentenceTransformerScorer(model_path, ordered_skills)
            )
            for task in ordered_tasks:
                query = router_query_text(task["prompt_text"])
                scorer.rank(query, skill_ids)
                start = clock_ns()
                ranked = scorer.rank(query, skill_ids)
                end = clock_ns()
                _require(
                    len(ranked) == 16 and set(ranked) == set(skill_ids),
                    "scorer ranking must contain every skill once",
                )
                gold = task["gold_skill_id"]
                negative = task.get("negative_skill_id")
                routes.append(
                    {
                        "arm": arm,
                        "seed": seed,
                        "model_grid_authority_sha256": model_grid_authority_sha256,
                        "task_id": task["task_id"],
                        "gold_skill_id": gold,
                        "tempting_negative_skill_id": negative,
                        "semantic_family_id": task["semantic_family_id"],
                        "gold_rank": ranked.index(gold) + 1,
                        "tempting_negative_rank": (
                            ranked.index(negative) + 1 if negative is not None else None
                        ),
                        "latency_ns": end - start,
                    }
                )
    return routes


def _validated_evaluation_frozen_tasks(
    route_rows: list[dict[str, Any]] | None,
    *,
    commit_a: str,
    commit_b: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_started_artifact: bytes,
) -> list[dict[str, Any]]:
    message = "evaluation frozen task authority mismatch"
    task_fields = {
        "task_id",
        "prompt_text",
        "prompt_text_sha256",
        "semantic_family_id",
        "gold_skill_id",
        "negative_skill_id",
        "source_type",
    }
    try:
        manifest = _json_no_duplicate_keys(
            input_artifacts["blind-v2-manifest.json"], "blind-v2 manifest"
        )
        task_bytes = input_artifacts["blind-v2-tasks.jsonl"]
        raw_tasks = _jsonl_no_duplicate_keys(task_bytes, "blind-v2 tasks")
        _require(len(raw_tasks) == POSITIVE_TASK_COUNT, message)
        tasks: list[dict[str, Any]] = []
        for raw_task in raw_tasks:
            task = _exact_object_fields(raw_task, task_fields, "frozen task")
            task_id = _exact_lowercase_hex(
                task["task_id"], length=24, label="frozen task id"
            )
            prompt = _nonempty_string(task["prompt_text"], "frozen task prompt")
            prompt_hash = _exact_lowercase_hex(
                task["prompt_text_sha256"],
                length=64,
                label="frozen task prompt SHA-256",
            )
            _require(
                prompt_hash == _sha256_bytes(prompt.encode("utf-8"))
                and task["source_type"] == "AGENT_GENERATED"
                and type(task["semantic_family_id"]) is str
                and bool(task["semantic_family_id"].strip())
                and type(task["gold_skill_id"]) is str
                and bool(task["gold_skill_id"].strip())
                and (
                    task["negative_skill_id"] is None
                    or (
                        type(task["negative_skill_id"]) is str
                        and bool(task["negative_skill_id"].strip())
                        and task["negative_skill_id"] != task["gold_skill_id"]
                    )
                ),
                message,
            )
            tasks.append(
                {
                    **deepcopy(task),
                    "task_id": task_id,
                    "prompt_text": prompt,
                    "prompt_text_sha256": prompt_hash,
                }
            )
        _require(
            task_bytes == b"".join(_canonical_json_bytes(task) for task in tasks),
            message,
        )
        task_ids = [cast(str, task["task_id"]) for task in tasks]
        prompt_bytes = [
            cast(str, task["prompt_text"]).encode("utf-8", errors="strict")
            for task in tasks
        ]
        normalized_prompts = [
            _normalize(cast(str, task["prompt_text"])) for task in tasks
        ]
        family_ids = [cast(str, task["semantic_family_id"]) for task in tasks]
        gold_counts = Counter(task["gold_skill_id"] for task in tasks)
        negative_counts = Counter(
            cast(str, task["negative_skill_id"])
            for task in tasks
            if task["negative_skill_id"] is not None
        )
        _require(
            len(set(task_ids)) == POSITIVE_TASK_COUNT
            and len(set(prompt_bytes)) == POSITIVE_TASK_COUNT
            and len(set(normalized_prompts)) == POSITIVE_TASK_COUNT
            and len(set(family_ids)) == POSITIVE_TASK_COUNT
            and sum(task["negative_skill_id"] is not None for task in tasks)
            == TEMPTING_NEGATIVE_COUNT,
            message,
        )
        _require(
            len(gold_counts) == 16
            and set(gold_counts.values()) == {8}
            and all(
                sum(
                    task["gold_skill_id"] == gold
                    and task["negative_skill_id"] is not None
                    for task in tasks
                )
                == 6
                and sum(
                    task["gold_skill_id"] == gold and task["negative_skill_id"] is None
                    for task in tasks
                )
                == 2
                for gold in gold_counts
            )
            and manifest.get("gold_distribution") == dict(sorted(gold_counts.items()))
            and manifest.get("negative_distribution")
            == dict(sorted(negative_counts.items())),
            message,
        )
        task_file_sha256 = _sha256_bytes(task_bytes)
        _require(
            manifest.get("commit_a") == commit_a
            and manifest.get("dataset_sha256") == task_file_sha256
            and manifest.get("tasks_file_sha256") == task_file_sha256
            and manifest.get("per_row_prompt_sha256")
            == [task["prompt_text_sha256"] for task in tasks],
            message,
        )
        dataset_binding = frozen_bindings["blind_v2_dataset"]
        _require(
            type(dataset_binding) is dict
            and dataset_binding.get("commit_a") == commit_a
            and dataset_binding.get("tasks_file_sha256") == task_file_sha256
            and dataset_binding.get("dataset_sha256") == task_file_sha256
            and dataset_binding.get("task_rows") == tasks,
            message,
        )
        construction = manifest["agent_construction"]
        _require(type(construction) is dict, message)
        selected_source_authority = [
            {
                "task_id": task["task_id"],
                "prompt_text_sha256": task["prompt_text_sha256"],
                "semantic_family_id": task["semantic_family_id"],
                "gold_skill_id": task["gold_skill_id"],
                "negative_skill_id": task["negative_skill_id"],
                "source_type": task["source_type"],
            }
            for task in tasks
        ]
        _require(
            construction.get("selected_task_source_authority")
            == selected_source_authority
            and construction.get("selected_task_source_authority_sha256")
            == canonical_sha256(selected_source_authority),
            message,
        )
        started = _exact_object_fields(
            _json_no_duplicate_keys(attempt_started_artifact, "attempt started marker"),
            {
                "schema_version",
                "attempt_number",
                "maximum_attempts",
                "commit_a",
                "commit_b",
                "attempt_token_sha256",
            },
            "attempt started marker",
        )
        _require(
            started["schema_version"] == "router-v2-blind-v2-attempt-started-v1"
            and started["attempt_number"] == 1
            and type(started["attempt_number"]) is int
            and started["maximum_attempts"] == 1
            and type(started["maximum_attempts"]) is int
            and started["commit_a"] == commit_a
            and started["commit_b"] == commit_b
            and started["attempt_token_sha256"] == attempt_token_sha256,
            message,
        )

        if route_rows is None:
            return tasks

        _require(type(route_rows) is list, message)
        task_authority = {
            cast(str, task["task_id"]): (
                task["semantic_family_id"],
                task["gold_skill_id"],
                task["negative_skill_id"],
            )
            for task in tasks
        }
        route_grid: dict[str, set[tuple[str, int]]] = {
            task_id: set() for task_id in task_ids
        }
        evaluation_models = _validated_evaluation_model_bindings(
            frozen_bindings["evaluation_models"]
        )
        model_grid_authority_sha256 = canonical_sha256(evaluation_models)
        for row in route_rows:
            _require(type(row) is dict, message)
            route_task_id = row.get("task_id")
            _require(
                type(route_task_id) is str
                and route_task_id in task_authority
                and (
                    row.get("semantic_family_id"),
                    row.get("gold_skill_id"),
                    row.get("tempting_negative_skill_id"),
                )
                == task_authority[route_task_id]
                and row.get("arm") in ARMS
                and row.get("seed") in SEEDS
                and row.get("model_grid_authority_sha256")
                == model_grid_authority_sha256,
                message,
            )
            route_grid[cast(str, route_task_id)].add(
                (cast(str, row["arm"]), cast(int, row["seed"]))
            )
        expected_grid = {(arm, seed) for seed in SEEDS for arm in ARMS}
        _require(
            len(route_rows) == POSITIVE_TASK_COUNT * len(expected_grid)
            and all(grid == expected_grid for grid in route_grid.values()),
            message,
        )
        return tasks
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc


def _validate_evaluation_agent_construction_authority(
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    task_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    message = "evaluation Agent construction lineage mismatch"
    try:
        _require(type(frozen_bindings) is dict, message)
        _require(type(input_artifacts) is dict, message)
        frozen = _exact_object_fields(
            frozen_bindings,
            {
                "preregistration",
                "pilot_manifest",
                "frozen_inputs",
                "old_phase16_prompt_files",
                "base_model",
                "evaluation_models",
                "blind_v2_dataset",
                "agent_construction",
                "skill_index",
                "query_contract",
                "skill_representation_builder",
                "gate",
                "evaluator",
            },
            "evaluation frozen bindings",
        )
        _reject_forbidden_lineage_fields(frozen)
        _validated_evaluation_model_bindings(frozen["evaluation_models"])
        preregistration_bytes = input_artifacts["preregistration.json"]
        preregistration_binding = _exact_object_fields(
            frozen["preregistration"],
            {"path", "file_sha256", "semantic_sha256"},
            "evaluation preregistration binding",
        )
        preregistration_file_sha256 = _exact_lowercase_hex(
            preregistration_binding["file_sha256"],
            length=64,
            label="evaluation preregistration file SHA-256",
        )
        preregistration_semantic_sha256 = _exact_lowercase_hex(
            preregistration_binding["semantic_sha256"],
            length=64,
            label="evaluation preregistration semantic SHA-256",
        )
        preregistration = _json_no_duplicate_keys(
            preregistration_bytes, "evaluation preregistration"
        )
        preregistration_unhashed = {
            key: value
            for key, value in preregistration.items()
            if key != "preregistration_sha256"
        }
        _require(
            preregistration_file_sha256 == _sha256_bytes(preregistration_bytes)
            and preregistration.get("preregistration_sha256")
            == preregistration_semantic_sha256
            and canonical_sha256(preregistration_unhashed)
            == preregistration_semantic_sha256
            and preregistration.get("skill_index") == frozen["skill_index"]
            and preregistration.get("frozen_inputs") == frozen["frozen_inputs"]
            and preregistration.get("old_phase16_prompt_files")
            == frozen["old_phase16_prompt_files"],
            message,
        )
        preregistered_protected_semantic_commitment = preregistration.get(
            "protected_semantic_commitment"
        )
        manifest_bytes = input_artifacts["blind-v2-manifest.json"]
        review_summary_bytes = input_artifacts["review-summary.json"]
        dataset_document = _exact_object_fields(
            frozen["blind_v2_dataset"],
            {
                "commit_a",
                "tasks_file_sha256",
                "manifest_file_sha256",
                "dataset_sha256",
                "source_file_sha256",
                "per_row_prompt_sha256",
                "task_rows",
            },
            "evaluation blind-v2 dataset binding",
        )
        manifest_file_sha256 = _exact_lowercase_hex(
            dataset_document["manifest_file_sha256"],
            length=64,
            label="evaluation blind-v2 manifest file SHA-256",
        )
        _require(
            manifest_file_sha256 == _sha256_bytes(manifest_bytes),
            message,
        )
        manifest = _json_no_duplicate_keys(manifest_bytes, "blind-v2 manifest")
        review_summary = _json_no_duplicate_keys(
            review_summary_bytes, "blind-v2 review summary"
        )
        manifest = _exact_object_fields(
            manifest,
            {
                "schema_version",
                "commit_a",
                "dataset_sha256",
                "tasks_file_sha256",
                "task_count",
                "negative_labeled_task_count",
                "gold_distribution",
                "negative_distribution",
                "family_count",
                "human_author_count",
                "human_reviewer_count",
                "exact_three_way_agreement_count",
                "selection_not_selected_count",
                "pipeline_rejected_candidate_count",
                "excluded_candidate_count",
                "candidate_outcomes",
                "source_file_sha256",
                "per_row_prompt_sha256",
                "blind_v2_data_first_read_timestamp",
                "prompts_committed",
                "agent_construction",
                "model_scores_observed",
                "evaluation_started",
                "retraining_after_data_access",
                "gate_changed_after_data_access",
            },
            "evaluation blind-v2 manifest",
        )
        review_summary = _exact_object_fields(
            review_summary,
            {
                "schema_version",
                "review_mode",
                "source_type",
                "task_count",
                "negative_labeled_task_count",
                "family_count",
                "human_author_count",
                "human_reviewer_count",
                "exact_three_way_agreement_count",
                "selection_not_selected_count",
                "pipeline_rejected_candidate_count",
                "excluded_candidate_count",
                "candidate_outcomes",
                "agent_roles",
                "reviewer_ledgers",
                "transport_retry_count",
                "retry_records",
            },
            "evaluation blind-v2 review summary",
        )
        _reject_forbidden_lineage_fields(manifest)
        _reject_forbidden_lineage_fields(review_summary)
        _require(
            manifest["schema_version"] == "router-v2-agent-blind-v2-manifest-v1"
            and review_summary["schema_version"]
            == "router-v2-agent-blind-v2-review-summary-v1",
            message,
        )
        for field, expected_state in (
            ("prompts_committed", True),
            ("model_scores_observed", False),
            ("evaluation_started", False),
            ("retraining_after_data_access", False),
            ("gate_changed_after_data_access", False),
        ):
            _require(
                type(manifest[field]) is bool and manifest[field] is expected_state,
                message,
            )
        for document in (manifest, review_summary):
            for field, expected_count in (
                ("task_count", POSITIVE_TASK_COUNT),
                ("negative_labeled_task_count", TEMPTING_NEGATIVE_COUNT),
                ("family_count", POSITIVE_TASK_COUNT),
                ("human_author_count", 0),
                ("human_reviewer_count", 0),
            ):
                _require(
                    type(document.get(field)) is int
                    and document[field] == expected_count,
                    message,
                )
        exact_agreement_count = manifest.get("exact_three_way_agreement_count")
        _require(
            type(exact_agreement_count) is int
            and exact_agreement_count >= POSITIVE_TASK_COUNT
            and review_summary.get("exact_three_way_agreement_count")
            == exact_agreement_count,
            message,
        )
        manifest_construction = _exact_object_fields(
            manifest["agent_construction"],
            {
                "review_mode",
                "source_type",
                "human_author_count",
                "human_reviewer_count",
                "exact_three_way_agreement_count",
                "selection_not_selected_count",
                "pipeline_rejected_candidate_count",
                "excluded_candidate_count",
                "candidate_outcomes",
                "construction_input_authority",
                "protected_semantic_commitment",
                "selected_task_source_authority",
                "selected_task_source_authority_sha256",
                "generation_authority",
                "reviewer_decision_authority",
                "generation_ledger",
                "reviewer_ledgers",
                "agent_run_metadata",
                "sanitized_run_records",
                "agent_run_identity_authority",
                "agent_roles",
                "transport_retry_count",
                "retry_records",
                "contamination",
                "deterministic_selection",
                "deterministic_selection_sha256",
            },
            "evaluation Agent construction",
        )
        _require(
            manifest_construction.get("review_mode") == "ISOLATED_AGENT_REVIEW"
            and manifest_construction.get("source_type") == "AGENT_GENERATED"
            and type(manifest_construction.get("human_author_count")) is int
            and manifest_construction["human_author_count"] == 0
            and type(manifest_construction.get("human_reviewer_count")) is int
            and manifest_construction["human_reviewer_count"] == 0
            and type(manifest_construction.get("exact_three_way_agreement_count"))
            is int
            and manifest_construction["exact_three_way_agreement_count"]
            == exact_agreement_count,
            message,
        )
        _require(
            review_summary.get("review_mode") == "ISOLATED_AGENT_REVIEW"
            and review_summary.get("source_type") == "AGENT_GENERATED",
            message,
        )

        candidate_outcomes = manifest.get("candidate_outcomes")
        _require(type(candidate_outcomes) is dict, message)
        outcomes = cast(dict[str, Any], candidate_outcomes)
        _require(
            all(
                type(candidate_id) is str
                and len(candidate_id) == 24
                and all(character in "0123456789abcdef" for character in candidate_id)
                and outcome
                in {
                    "SELECTED",
                    "NOT_SELECTED",
                    "REJECTED_CONTAMINATION",
                    "REJECTED_INVOCATION",
                    "REJECTED_REVIEW",
                }
                for candidate_id, outcome in outcomes.items()
            ),
            message,
        )
        selected_task_ids = [cast(str, task["task_id"]) for task in task_rows]
        selected_count = sum(outcome == "SELECTED" for outcome in outcomes.values())
        not_selected_count = sum(
            outcome == "NOT_SELECTED" for outcome in outcomes.values()
        )
        pipeline_rejected_count = sum(
            type(outcome) is str and outcome.startswith("REJECTED")
            for outcome in outcomes.values()
        )
        aggregate_fields = {
            "exact_three_way_agreement_count": selected_count + not_selected_count,
            "selection_not_selected_count": not_selected_count,
            "pipeline_rejected_candidate_count": pipeline_rejected_count,
            "excluded_candidate_count": not_selected_count + pipeline_rejected_count,
        }
        _require(
            selected_count == POSITIVE_TASK_COUNT
            and all(
                outcomes.get(task_id) == "SELECTED" for task_id in selected_task_ids
            )
            and {
                candidate_id
                for candidate_id, outcome in outcomes.items()
                if outcome == "SELECTED"
            }
            == set(selected_task_ids)
            and all(
                document.get("candidate_outcomes") == outcomes
                and all(
                    document.get(field) == value
                    for field, value in aggregate_fields.items()
                )
                for document in (manifest, review_summary, manifest_construction)
            ),
            message,
        )
        deterministic_selection = _exact_object_fields(
            manifest_construction["deterministic_selection"],
            {
                "selection_authority",
                "selection_authority_sha256",
                "accepted_pool_sha256",
                "round_1_candidate_count",
                "round_2_candidate_count",
                "round_1_distribution",
                "round_2_distribution",
                "round_1_request_quota_distribution",
                "round_2_request_quota_distribution",
                "round_1_post_pipeline_deficits",
                "selected_candidate_ids",
                "selected_candidate_ids_sha256",
                "selected_by_stratum",
            },
            "evaluation deterministic selection authority",
        )
        _require(
            deterministic_selection.get("selected_candidate_ids") == selected_task_ids
            and deterministic_selection.get("selected_candidate_ids_sha256")
            == canonical_sha256(selected_task_ids)
            and manifest_construction.get("deterministic_selection_sha256")
            == canonical_sha256(deterministic_selection),
            message,
        )

        source_hashes = _exact_object_fields(
            manifest["source_file_sha256"],
            set(REQUIRED_AGENT_PACK_FILES),
            "evaluation Agent source file hashes",
        )
        for filename in REQUIRED_AGENT_PACK_FILES:
            _exact_lowercase_hex(
                source_hashes[filename],
                length=64,
                label=f"evaluation {filename} source SHA-256",
            )
        _require(
            dataset_document["source_file_sha256"] == source_hashes
            and dataset_document["per_row_prompt_sha256"]
            == manifest["per_row_prompt_sha256"]
            and dataset_document["task_rows"] == task_rows,
            message,
        )

        generation_ledger = _exact_object_fields(
            manifest_construction["generation_ledger"],
            {"path", "sha256"},
            "evaluation generation ledger",
        )
        agent_run_metadata = _exact_object_fields(
            manifest_construction["agent_run_metadata"],
            {"path", "sha256"},
            "evaluation Agent run metadata",
        )
        _require(
            generation_ledger["path"] == "blind-v2-generation.jsonl"
            and generation_ledger["sha256"]
            == source_hashes["blind-v2-generation.jsonl"]
            and agent_run_metadata["path"] == "agent-run-metadata.json"
            and agent_run_metadata["sha256"]
            == source_hashes["agent-run-metadata.json"],
            message,
        )

        agent_roles = manifest_construction.get("agent_roles")
        _require(
            type(agent_roles) is dict and set(agent_roles) == set(AGENT_CONFIGS),
            message,
        )
        role_evidence = cast(dict[str, Any], agent_roles)
        raw_records = manifest_construction.get("sanitized_run_records")
        _require(
            type(raw_records) is dict and set(raw_records) == set(AGENT_CONFIGS),
            message,
        )
        records_by_role = cast(dict[str, list[dict[str, Any]]], raw_records)
        reviewer_ledgers = _exact_object_fields(
            manifest_construction["reviewer_ledgers"],
            {"reviewer_a", "reviewer_b"},
            "evaluation reviewer ledgers",
        )
        review_schedule_sha256: dict[str, str] = {}
        for role, suffix in (("reviewer_a", "a"), ("reviewer_b", "b")):
            ledger = _exact_object_fields(
                reviewer_ledgers[role],
                {"path", "sha256", "schedule_sha256"},
                f"evaluation {role} ledger",
            )
            expected_path = f"blind-v2-review-{suffix}.jsonl"
            _require(
                ledger["path"] == expected_path
                and ledger["sha256"] == source_hashes[expected_path],
                message,
            )
            review_schedule_sha256[role] = _exact_lowercase_hex(
                ledger["schedule_sha256"],
                length=64,
                label=f"evaluation {role} schedule SHA-256",
            )

        identity_authority = _exact_object_fields(
            manifest_construction["agent_run_identity_authority"],
            {"roles", "authority_sha256"},
            "evaluation Agent run identity authority",
        )
        identity_roles = _exact_object_fields(
            identity_authority["roles"],
            set(AGENT_CONFIGS),
            "evaluation Agent identity roles",
        )
        metadata_roles: dict[str, dict[str, Any]] = {}
        for role in AGENT_CONFIGS:
            identity_role = _exact_object_fields(
                identity_roles[role],
                {
                    "ledger_path",
                    "ledger_file_sha256",
                    "invocation_ids",
                    "invocation_ids_sha256",
                    "candidate_ids",
                    "candidate_ids_sha256",
                    "request_count",
                    "invocation_count",
                    "session_or_thread_ids",
                    "session_or_thread_ids_sha256",
                },
                f"evaluation {role} identity authority",
            )
            metadata_roles[role] = {
                "config": deepcopy(AGENT_CONFIGS[role]),
                "request_count": identity_role["request_count"],
                "invocation_count": identity_role["invocation_count"],
                "session_or_thread_ids": deepcopy(
                    identity_role["session_or_thread_ids"]
                ),
                "fork_context": False,
                "history_message_count": 0,
                "imported_memory_count": 0,
            }

        (
            validated_records,
            expected_role_evidence,
            expected_retries,
            expected_identity_authority,
        ) = _validated_agent_lineage_evidence(
            {
                "agent_run_records": records_by_role,
                "agent_roles": metadata_roles,
                "source_file_sha256": source_hashes,
                "review_schedule_sha256": review_schedule_sha256,
                "agent_run_evidence": role_evidence,
                "retry_records": manifest_construction["retry_records"],
                "transport_retry_count": manifest_construction["transport_retry_count"],
                "agent_run_identity_authority": identity_authority,
            }
        )
        _require(
            role_evidence == expected_role_evidence
            and manifest_construction["retry_records"] == expected_retries
            and identity_authority == expected_identity_authority,
            message,
        )

        raw_construction_input_authority = cast(
            dict[str, Any], manifest_construction["construction_input_authority"]
        )
        raw_skill_projection = cast(
            dict[str, Any],
            raw_construction_input_authority["canonical_skill_projection"],
        )
        projected_skills = _project_canonical_skills(raw_skill_projection["rows"])
        canonical_ids = _canonical_skill_ids(projected_skills)
        generation_authority, generation_semantics = _validated_generation_authority(
            manifest_construction["generation_authority"],
            source_ledger_sha256=source_hashes["blind-v2-generation.jsonl"],
            canonical_ids=canonical_ids,
            candidate_outcomes=outcomes,
            generator_run_records=validated_records["generator"],
        )
        _require(
            manifest_construction["generation_authority"] == generation_authority,
            message,
        )
        generation_candidate_labels = {
            cast(str, candidate["candidate_id"]): (
                cast(str, candidate["gold_skill_id"]),
                cast(str | None, candidate["negative_skill_id"]),
            )
            for request in generation_authority["requests"]
            for candidate in request["candidates"]
        }
        _validated_reviewer_decision_authority(
            manifest_construction["reviewer_decision_authority"],
            candidate_labels=generation_candidate_labels,
            candidate_outcomes=outcomes,
            reviewer_run_records={
                role: validated_records[role] for role in ("reviewer_a", "reviewer_b")
            },
            canonical_ids=canonical_ids,
        )

        generator_ids = {
            candidate_id
            for record in validated_records["generator"]
            for candidate_id in record["candidate_ids"]
        }
        reviewer_ids = {
            role: {
                candidate_id
                for record in validated_records[role]
                for candidate_id in record["candidate_ids"]
            }
            for role in ("reviewer_a", "reviewer_b")
        }
        clean_candidate_ids = {
            candidate_id
            for candidate_id, outcome in outcomes.items()
            if outcome != "REJECTED_CONTAMINATION"
        }
        _require(
            generator_ids == set(outcomes)
            and reviewer_ids["reviewer_a"] == clean_candidate_ids
            and reviewer_ids["reviewer_b"] == clean_candidate_ids,
            message,
        )
        for role in ("reviewer_a", "reviewer_b"):
            role_candidate_ids = [
                candidate_id
                for record in validated_records[role]
                for candidate_id in record["candidate_ids"]
            ]
            _require(
                role_candidate_ids
                == sorted(
                    clean_candidate_ids,
                    key=lambda candidate_id: review_schedule_key(role, candidate_id),
                ),
                message,
            )
        for candidate_id, outcome in outcomes.items():
            role_records = [
                next(
                    (
                        record
                        for record in validated_records[role]
                        if candidate_id in record["candidate_ids"]
                    ),
                    None,
                )
                for role in AGENT_CONFIGS
            ]
            if outcome == "REJECTED_CONTAMINATION":
                _require(
                    candidate_id not in reviewer_ids["reviewer_a"]
                    and candidate_id not in reviewer_ids["reviewer_b"],
                    message,
                )
            elif outcome == "REJECTED_INVOCATION":
                _require(
                    any(
                        record is None or record.get("outcome") != "VALID_RESPONSE"
                        for record in role_records
                    ),
                    message,
                )
            else:
                _require(
                    all(
                        record is not None and record.get("outcome") == "VALID_RESPONSE"
                        for record in role_records
                    ),
                    message,
                )

        _require(
            manifest_construction.get("retry_records") == expected_retries
            and manifest_construction.get("transport_retry_count")
            == len(expected_retries),
            message,
        )

        ledger_evidence = reviewer_ledgers

        committed_contamination = _validated_committed_contamination(
            manifest_construction["contamination"],
            source_file_sha256=source_hashes,
            candidate_outcomes=outcomes,
        )
        deterministic_selection = _validated_selection_audit_semantics(
            deterministic_selection,
            generation_semantics=generation_semantics,
            selected_rows=task_rows,
            canonical_ids=canonical_ids,
            id_field="task_id",
            gold_field="gold_skill_id",
            negative_field="negative_skill_id",
            require_complete_selection=True,
            selection_audit_sha256=manifest_construction[
                "deterministic_selection_sha256"
            ],
        )
        construction_input_authority = _validated_construction_input_authority(
            raw_construction_input_authority,
            projected_skills=projected_skills,
            protected_authority=cast(
                dict[str, Any], committed_contamination["protected_authority"]
            ),
        )
        protected_semantic_commitment = _validated_protected_semantic_commitment(
            manifest_construction["protected_semantic_commitment"],
            construction_input_authority=construction_input_authority,
        )
        _require(
            preregistered_protected_semantic_commitment
            == protected_semantic_commitment,
            message,
        )
        skill_source = construction_input_authority["canonical_skill_projection"][
            "sources"
        ]
        protected_sources = construction_input_authority[
            "protected_artifact_projections"
        ]
        expected_skill_source = [
            {
                "path": cast(dict[str, Any], frozen["skill_index"])["path"],
                "file_sha256": cast(dict[str, Any], frozen["skill_index"])["sha256"],
            }
        ]
        expected_protected_sources = {
            "train": [
                {
                    "path": cast(
                        dict[str, Any],
                        cast(dict[str, Any], frozen["frozen_inputs"])["accepted_pairs"],
                    )["path"],
                    "file_sha256": cast(
                        dict[str, Any],
                        cast(dict[str, Any], frozen["frozen_inputs"])["accepted_pairs"],
                    )["sha256"],
                }
            ],
            "pilot-002": [
                {
                    "path": cast(
                        dict[str, Any],
                        cast(dict[str, Any], frozen["frozen_inputs"])["heldout_labels"],
                    )["path"],
                    "file_sha256": cast(
                        dict[str, Any],
                        cast(dict[str, Any], frozen["frozen_inputs"])["heldout_labels"],
                    )["sha256"],
                }
            ],
            "phase16": [
                {
                    "path": cast(dict[str, Any], binding)["path"],
                    "file_sha256": cast(dict[str, Any], binding)["sha256"],
                }
                for binding in cast(list[Any], frozen["old_phase16_prompt_files"])
            ],
        }
        _require(
            skill_source == expected_skill_source
            and all(
                protected_sources[scope]["sources"] == expected_protected_sources[scope]
                for scope in expected_protected_sources
            ),
            message,
        )

        _require(
            review_summary.get("agent_roles") == role_evidence
            and review_summary.get("reviewer_ledgers") == ledger_evidence
            and review_summary.get("transport_retry_count")
            == manifest_construction.get("transport_retry_count")
            and review_summary.get("retry_records")
            == manifest_construction.get("retry_records"),
            message,
        )

        expected_binding = deepcopy(manifest_construction)
        expected_binding["review_summary_file_sha256"] = _sha256_bytes(
            review_summary_bytes
        )
        _exact_object_fields(
            frozen["agent_construction"],
            set(expected_binding),
            "frozen Agent construction binding",
        )
        _require(
            frozen["agent_construction"] == expected_binding,
            message,
        )
        return projected_skills
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc


def build_evaluation_documents(
    route_rows: list[dict[str, Any]],
    *,
    commit_a: str,
    commit_b: str,
    evaluator_commit: str,
    attempt_token_sha256: str,
    frozen_bindings: dict[str, Any],
    input_artifacts: dict[str, bytes],
    attempt_artifacts: dict[str, bytes],
) -> dict[str, bytes]:
    _require(
        type(input_artifacts) is dict
        and set(input_artifacts)
        == {
            "preregistration.json",
            "blind-v2-tasks.jsonl",
            "blind-v2-manifest.json",
            "review-summary.json",
        },
        "evaluation input artifact set mismatch",
    )
    _require(
        type(attempt_artifacts) is dict
        and set(attempt_artifacts)
        == {"attempt-1.started.json", "attempt-1.terminal.json"},
        "attempt artifact set mismatch",
    )
    frozen_task_rows = _validated_evaluation_frozen_tasks(
        route_rows,
        commit_a=commit_a,
        commit_b=commit_b,
        attempt_token_sha256=attempt_token_sha256,
        frozen_bindings=frozen_bindings,
        input_artifacts=input_artifacts,
        attempt_started_artifact=attempt_artifacts["attempt-1.started.json"],
    )
    _validate_evaluation_agent_construction_authority(
        frozen_bindings, input_artifacts, frozen_task_rows
    )
    per_seed = [
        build_per_seed_result(
            [row for row in route_rows if row["arm"] == arm and row["seed"] == seed]
        )
        for seed in SEEDS
        for arm in ARMS
    ]
    aggregate = build_aggregate_results(per_seed)
    paired = build_paired_results(route_rows)
    statistics = build_statistics(route_rows)
    failures = build_failure_slices(route_rows)
    gate = apply_preregistered_gate(per_seed)
    summary = {
        "schema_version": "router-v2-blind-v2-evaluation-summary-v1",
        **gate,
        "task_count": POSITIVE_TASK_COUNT,
        "negative_labeled_task_count": TEMPTING_NEGATIVE_COUNT,
        "claim_scope": "AGENT_CONSTRUCTED_DUAL_AGENT_UNANIMOUS_BLIND_SET_ONLY",
        "same_provider_limitation": (
            "Generator gpt-5.6-sol/max, Reviewer A gpt-5.6-sol/ultra, and "
            "Reviewer B gpt-5.6-luna/max are OpenAI configurations, so their "
            "review judgments are not statistically independent."
        ),
    }
    report = (
        "# Router V2 final blind-v2\n\n"
        f"Research conclusion: `{gate['research_conclusion']}`\n\n"
        f"Dataset: {POSITIVE_TASK_COUNT} tasks, including "
        f"{TEMPTING_NEGATIVE_COUNT} negative-labeled tasks, constructed by one Agent "
        "generator and accepted only by two role-isolated Agent reviewers with unanimous "
        "labels.\n\n"
        "Limitation: Generator gpt-5.6-sol/max, Reviewer A gpt-5.6-sol/ultra, and "
        "Reviewer B gpt-5.6-luna/max are OpenAI configurations from the same provider; "
        "their judgments are not statistically independent. Scope is limited to this "
        "Agent-constructed distribution.\n\n"
        "Default router remains unchanged. This is not a production, release, or SOTA claim.\n"
    ).encode("utf-8")
    result_documents = {
        "per-seed.json": _canonical_json_bytes(per_seed),
        "aggregate.json": _canonical_json_bytes(aggregate),
        "paired.json": _canonical_json_bytes(paired),
        "statistics.json": _canonical_json_bytes(statistics),
        "failure-slices.json": _canonical_json_bytes(failures),
        "evaluation-summary.json": _canonical_json_bytes(summary),
        "result-report.md": report,
    }
    documents = {**input_artifacts, **result_documents}
    lineage = build_lineage_manifest(
        commit_a=commit_a,
        commit_b=commit_b,
        evaluator_commit=evaluator_commit,
        attempt_token_sha256=attempt_token_sha256,
        frozen_bindings=frozen_bindings,
        artifacts={**documents, **attempt_artifacts},
    )
    return {**documents, "lineage-manifest.json": _canonical_json_bytes(lineage)}


def _write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("xb") as handle:
        handle.write(_canonical_json_bytes(value))


def build_attempt_started_document(started_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "router-v2-blind-v2-attempt-started-v1",
        "attempt_number": 1,
        "maximum_attempts": 1,
        **started_payload,
    }


def build_attempt_terminal_document(artifact_count: int) -> dict[str, Any]:
    _require(
        artifact_count == len(EVALUATION_OUTPUT_FILENAMES), "artifact count mismatch"
    )
    return {
        "schema_version": "router-v2-blind-v2-attempt-terminal-v1",
        "attempt_number": 1,
        "status": "COMPLETED",
        "artifact_count": artifact_count,
    }


def _assert_output_safe(
    output_root: Path, repository_root: Path, protected_roots: list[Path]
) -> Path:
    output = _canonical_repository_destination(
        output_root,
        repository_root,
        FINAL_NAMESPACE_RELATIVE,
        label="evaluation output canonical namespace",
    )
    resolved = output.resolve(strict=False)
    for root in protected_roots:
        protected = root.resolve(strict=False)
        _require(
            not resolved.is_relative_to(protected),
            "evaluation output may not be inside a protected root",
        )
    return output


def run_single_attempt(
    output_root: Path | str,
    *,
    repository_root: Path | str,
    started_payload: dict[str, Any],
    evaluate: Callable[[], dict[str, bytes]],
    protected_roots: list[Path],
) -> dict[str, Any]:
    output = _assert_output_safe(
        Path(output_root), Path(repository_root), protected_roots
    )
    output.parent.mkdir(mode=0o700, parents=False, exist_ok=True)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    started = build_attempt_started_document(started_payload)
    _write_exclusive_json(output / "attempt-1.started.json", started)
    try:
        documents = evaluate()
        _require(type(documents) is dict, "evaluation must return artifact bytes")
        for name, payload in sorted(documents.items()):
            _require(
                type(name) is str
                and "/" not in name
                and name not in {"attempt-1.started.json", "attempt-1.terminal.json"},
                "evaluation artifact path is invalid",
            )
            _require(
                type(payload) is bytes, "evaluation artifact payload must be bytes"
            )
            with (output / name).open("xb") as handle:
                handle.write(payload)
        _require(
            set(documents) == set(EVALUATION_OUTPUT_FILENAMES),
            "evaluation output artifact set mismatch",
        )
        terminal = build_attempt_terminal_document(len(documents))
        _write_exclusive_json(output / "attempt-1.terminal.json", terminal)
        return terminal
    except BaseException as exc:
        terminal = {
            "schema_version": "router-v2-blind-v2-attempt-terminal-v1",
            "attempt_number": 1,
            "status": "INFRASTRUCTURE_FAILURE",
            **terminal_posture("AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE"),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_allowed": False,
        }
        terminal_path = output / "attempt-1.terminal.json"
        if not terminal_path.exists():
            _write_exclusive_json(terminal_path, terminal)
        raise
