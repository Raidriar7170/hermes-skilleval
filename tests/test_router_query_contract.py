from __future__ import annotations

import hashlib
import inspect
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from hermes_skilleval.embedding_training import export_embedding_diagnostics
from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.cross_encoder import CrossEncoderReranker
from hermes_skilleval.routers.embedding import EmbeddingRouter, HashingEmbeddingModel
from hermes_skilleval.routers.gated import VerificationGatedRouter
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.routers.keyword import KeywordRouter, _score
from hermes_skilleval.routers.verification import skill_text
from hermes_skilleval.skill_index import save_skill_index


PROMPT = "Use prompt-native evidence to choose the debugging skill."
METADATA_FIELDS = (
    "id",
    "category",
    "difficulty",
    "robustness_tags",
    "split",
    "family",
)
DECISION_RECORD_FIELDS = (
    "router",
    "selected_skill_ids",
    "scores",
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "precision_at_5",
    "mrr",
    "ndcg_at_5",
    "negative_hit_rate",
    "accepted_count",
    "coverage",
    "selection_rate_at_5",
    "abstention_rate",
    "accepted_recall_at_5",
    "negative_accepted_rate",
)


def test_router_query_text_preserves_nonempty_prompt_bytes():
    assert list(inspect.signature(router_query_text).parameters) == ["prompt"]
    assert router_query_text(PROMPT) == PROMPT

    # The loader owns normalization; the formatter must never normalize again.
    padded_prompt = "  already loader-normalized  "
    assert router_query_text(padded_prompt) == padded_prompt


def test_router_query_text_rejects_empty_or_metadata_capable_inputs():
    invalid_inputs: tuple[object, ...] = ("", "   ", None, 7, {}, [], _task())
    for invalid in invalid_inputs:
        with pytest.raises((TypeError, ValueError)):
            router_query_text(invalid)  # type: ignore[arg-type]


def test_keyword_category_term_receives_only_ordinary_lexical_overlap_weight():
    skill = Skill(
        id="candidate",
        name="Candidate",
        path="/skills/candidate/SKILL.md",
        category="routing",
        description="Select a candidate.",
        body="Choose from prompt evidence.",
        trigger_terms=[],
        token_count_estimate=8,
    )

    assert _score(Counter({"routing": 1}), skill) == pytest.approx(1.0 + math.log1p(1))


@pytest.mark.parametrize("metadata_field", METADATA_FIELDS)
def test_embedding_export_and_router_ignore_each_task_metadata_field(metadata_field):
    skills = _skills()
    baseline = _task()
    mutated = _mutated_task(baseline, metadata_field)

    baseline_pairs, _ = export_embedding_diagnostics(
        tasks=[baseline], skills=skills, input_paths={}
    )
    mutated_pairs, _ = export_embedding_diagnostics(
        tasks=[mutated], skills=skills, input_paths={}
    )
    assert {row["query_text"] for row in baseline_pairs + mutated_pairs} == {PROMPT}
    assert _supervision(baseline_pairs) == _supervision(mutated_pairs)

    baseline_model = CapturingEmbeddingModel()
    mutated_model = CapturingEmbeddingModel()
    baseline_result = EmbeddingRouter(model=baseline_model).route(
        baseline, skills, top_k=2
    )
    mutated_result = EmbeddingRouter(model=mutated_model).route(
        mutated, skills, top_k=2
    )

    assert baseline_model.calls[0] == mutated_model.calls[0] == [PROMPT]
    _assert_same_decision(baseline_result, mutated_result)


@pytest.mark.parametrize("metadata_field", METADATA_FIELDS)
def test_keyword_hybrid_and_gated_ignore_each_task_metadata_field(metadata_field):
    skills = _skills()
    baseline = _task()
    mutated = _mutated_task(baseline, metadata_field)

    for router in (KeywordRouter(), HybridRouter()):
        _assert_same_decision(
            router.route(baseline, skills, top_k=2),
            router.route(mutated, skills, top_k=2),
        )

    base_router = FixedRouter(
        [skill.id for skill in skills],
        {skill.id: 0.75 for skill in skills},
    )
    gated = VerificationGatedRouter(
        base_router=base_router,
        selective=True,
        min_confidence=0.0,
        contrastive_selective=True,
        min_evidence=0.0,
    )
    _assert_same_decision(
        gated.route(baseline, skills, top_k=2),
        gated.route(mutated, skills, top_k=2),
    )


@pytest.mark.parametrize("metadata_field", METADATA_FIELDS)
def test_cross_encoder_inputs_and_decision_ignore_each_task_metadata_field(
    metadata_field,
):
    skills = _skills()
    baseline = _task()
    mutated = _mutated_task(baseline, metadata_field)
    base_router = FixedRouter(
        [skill.id for skill in skills],
        {skill.id: 0.75 for skill in skills},
    )
    model = CapturingCrossEncoderModel()
    router = CrossEncoderReranker(
        base_router=base_router,
        model=model,
        candidate_pool_size=2,
    )

    baseline_result = router.route(baseline, skills, top_k=2)
    baseline_pairs = model.calls[-1]
    mutated_result = router.route(mutated, skills, top_k=2)
    mutated_pairs = model.calls[-1]

    expected_pairs = [(PROMPT, skill_text(skill)) for skill in skills]
    assert baseline_pairs == mutated_pairs == expected_pairs
    assert all("LEAK_" not in query for query, _skill_text in baseline_pairs)
    _assert_same_decision(baseline_result, mutated_result)


@pytest.mark.parametrize("metadata_field", METADATA_FIELDS)
def test_cli_eval_and_compare_ignore_each_task_metadata_field(
    metadata_field, monkeypatch, tmp_path
):
    import hermes_skilleval.cli as cli_module
    import hermes_skilleval.routers.embedding as embedding_module
    import hermes_skilleval.routers.keyword as keyword_module

    skills = _skills()
    baseline = _task()
    mutated = _mutated_task(baseline, metadata_field)
    index_path = tmp_path / "skills.json"
    save_skill_index(skills, index_path)
    baseline_tasks = _write_cli_tasks(tmp_path / "baseline-tasks", baseline)
    mutated_tasks = _write_cli_tasks(tmp_path / "mutated-tasks", mutated)

    captured: dict[str, list[str]] = {"embedding": [], "keyword": []}
    _capture_module_queries(monkeypatch, embedding_module, captured["embedding"])
    _capture_module_queries(monkeypatch, keyword_module, captured["keyword"])

    baseline_eval = tmp_path / "baseline-eval"
    mutated_eval = tmp_path / "mutated-eval"
    _run_cli_eval(cli_module, index_path, baseline_tasks, baseline_eval)
    _run_cli_eval(cli_module, index_path, mutated_tasks, mutated_eval)
    _assert_same_record_decision(
        _read_jsonl_record(baseline_eval / "results.jsonl"),
        _read_jsonl_record(mutated_eval / "results.jsonl"),
    )

    baseline_compare = tmp_path / "baseline-compare"
    mutated_compare = tmp_path / "mutated-compare"
    _run_cli_compare(cli_module, index_path, baseline_tasks, baseline_compare)
    _run_cli_compare(cli_module, index_path, mutated_tasks, mutated_compare)
    for router_name in ("embedding", "keyword"):
        _assert_same_record_decision(
            _read_jsonl_record(baseline_compare / router_name / "results.jsonl"),
            _read_jsonl_record(mutated_compare / router_name / "results.jsonl"),
        )

    assert captured["embedding"] == [PROMPT] * 4
    assert captured["keyword"] == [PROMPT] * 2
    assert all(
        "LEAK_" not in query for queries in captured.values() for query in queries
    )


@pytest.mark.parametrize("metadata_field", METADATA_FIELDS)
@pytest.mark.parametrize("router_id", ("keyword", "hybrid"))
def test_stage2_final_export_uses_real_loaders_and_production_router(
    router_id, metadata_field, monkeypatch, tmp_path
):
    import hermes_skilleval.live_agent_skillsbench as stage2_module
    import hermes_skilleval.routers.hybrid as hybrid_module
    import hermes_skilleval.routers.keyword as keyword_module

    baseline_root = _write_stage2_inputs(tmp_path / "baseline-real", _task())
    mutated_root = _write_stage2_inputs(
        tmp_path / "mutated-real", _mutated_task(_task(), metadata_field)
    )
    captured: list[str] = []
    _capture_module_queries(monkeypatch, keyword_module, captured)
    if router_id == "hybrid":
        _capture_module_queries(monkeypatch, hybrid_module, captured)
    monkeypatch.setattr(
        stage2_module,
        "_stage2_export_code_provenance",
        lambda: {
            "commit": "d" * 40,
            "tag": "v0.3-query-contract-test",
            "dirty": False,
            "dirty_paths": [],
        },
    )

    baseline_predictions = _run_stage2_final_export(
        stage2_module, baseline_root, tmp_path / "baseline-output", router_id
    )
    mutated_predictions = _run_stage2_final_export(
        stage2_module, mutated_root, tmp_path / "mutated-output", router_id
    )

    assert _ordered_predictions(baseline_predictions) == _ordered_predictions(
        mutated_predictions
    )
    assert captured
    assert set(captured) == {PROMPT}
    assert all("LEAK_" not in query for query in captured)


class CapturingEmbeddingModel:
    cache_key = "query-contract-capture"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.delegate = HashingEmbeddingModel(dimensions=128)

    def encode_batch(self, texts):
        batch = list(texts)
        self.calls.append(batch)
        return self.delegate.encode_batch(batch)


class CapturingCrossEncoderModel:
    cache_key = "query-contract-cross-encoder"

    def __init__(self) -> None:
        self.calls: list[list[tuple[str, str]]] = []

    def score_pairs(self, pairs):
        batch = list(pairs)
        self.calls.append(batch)
        return [float(index) for index, _pair in enumerate(batch, start=1)]


class FixedRouter(SkillRouter):
    name = "fixed"

    def __init__(self, selected_skill_ids: list[str], scores: dict[str, float]):
        self.selected_skill_ids = selected_skill_ids
        self.scores = scores

    def route(self, task, skills, top_k):
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=self.selected_skill_ids[:top_k],
            scores=dict(self.scores),
            latency_ms=0.0,
        )


def _task() -> BenchmarkTask:
    task = BenchmarkTask(
        id="baseline-task",
        category="baseline-category",
        difficulty="easy",
        prompt=PROMPT,
        gold_skills=["systematic-debugging"],
        negative_skills=["leak-category-skill"],
        verifier="skill_selection",
        split="dev",
        robustness_tags=["baseline-tag"],
    )
    object.__setattr__(task, "family", "baseline-family")
    return task


def _mutated_task(task: BenchmarkTask, metadata_field: str) -> BenchmarkTask:
    if metadata_field == "id":
        mutated = replace(task, id="LEAK_TASK_ID")
    elif metadata_field == "category":
        mutated = replace(task, category="LEAK_CATEGORY")
    elif metadata_field == "difficulty":
        mutated = replace(task, difficulty="LEAK_DIFFICULTY")
    elif metadata_field == "robustness_tags":
        mutated = replace(task, robustness_tags=["LEAK_ROBUSTNESS"])
    elif metadata_field == "split":
        mutated = replace(task, split="test")
    elif metadata_field == "family":
        mutated = replace(task)
    else:
        raise AssertionError(f"unknown metadata field: {metadata_field}")
    family = "LEAK_FAMILY" if metadata_field == "family" else "baseline-family"
    object.__setattr__(mutated, "family", family)
    return mutated


def _skills() -> list[Skill]:
    return [
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="/skills/systematic-debugging/SKILL.md",
            category="baseline-category",
            description="Use prompt-native evidence to debug failures.",
            body="Choose the debugging skill from prompt evidence.",
            trigger_terms=["debugging", "prompt-native"],
            token_count_estimate=12,
        ),
        Skill(
            id="leak-category-skill",
            name="Leak Category Skill",
            path="/skills/leak-category-skill/SKILL.md",
            category="LEAK_CATEGORY",
            description="LEAK_TASK_ID LEAK_DIFFICULTY LEAK_ROBUSTNESS LEAK_FAMILY",
            body="Metadata must not select this skill.",
            trigger_terms=["LEAK_CATEGORY"],
            token_count_estimate=12,
        ),
    ]


def _supervision(rows):
    return sorted(
        (row["skill_id"], row["candidate_type"], row["source_annotation"])
        for row in rows
    )


def _assert_same_decision(left: RouteResult, right: RouteResult) -> None:
    assert left.scores == right.scores
    assert left.selected_skill_ids == right.selected_skill_ids


def _write_cli_tasks(root: Path, task: BenchmarkTask) -> Path:
    task_root = root / "task"
    task_root.mkdir(parents=True)
    task_yaml = {
        "id": task.id,
        "category": task.category,
        "difficulty": task.difficulty,
        "gold_skills": task.gold_skills,
        "negative_skills": task.negative_skills,
        "verifier": task.verifier,
        "split": task.split,
        "robustness_tags": task.robustness_tags,
        "family": getattr(task, "family"),
    }
    (task_root / "task.yaml").write_text(
        yaml.safe_dump(task_yaml, sort_keys=True), encoding="utf-8"
    )
    (task_root / "prompt.md").write_text(task.prompt, encoding="utf-8")
    return root


def _run_cli_eval(cli_module, index_path: Path, tasks_path: Path, output: Path) -> None:
    assert (
        cli_module.main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(tasks_path),
                "--router",
                "embedding",
                "--top-k",
                "2",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )


def _run_cli_compare(
    cli_module, index_path: Path, tasks_path: Path, output: Path
) -> None:
    assert (
        cli_module.main(
            [
                "compare",
                "--index",
                str(index_path),
                "--tasks",
                str(tasks_path),
                "--routers",
                "embedding,keyword",
                "--top-k",
                "2",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )


def _read_jsonl_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_same_record_decision(left: dict, right: dict) -> None:
    assert {field: left[field] for field in DECISION_RECORD_FIELDS} == {
        field: right[field] for field in DECISION_RECORD_FIELDS
    }


def _capture_module_queries(monkeypatch, module, captured: list[str]) -> None:
    original = module.router_query_text

    def capture(prompt: str) -> str:
        query = original(prompt)
        captured.append(query)
        return query

    monkeypatch.setattr(module, "router_query_text", capture)


def _write_stage2_inputs(root: Path, task_template: BenchmarkTask) -> Path:
    root.mkdir(parents=True)
    tasks = []
    for index in range(4):
        task_id = (
            f"{task_template.id}_{index}"
            if task_template.id == "LEAK_TASK_ID"
            else f"baseline-task-{index}"
        )
        tasks.append(
            {
                "task_id": task_id,
                "prompt": task_template.prompt,
                "category": task_template.category,
                "difficulty": task_template.difficulty,
                "robustness_tags": task_template.robustness_tags,
                "split": task_template.split,
                "family": getattr(task_template, "family"),
                "source": "approved-query-contract-source",
                "provenance": {"upstream_task_id": f"upstream-{index}"},
            }
        )
    skills = [
        {
            "skill_id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "body": skill.body,
            "category": skill.category,
            "path": skill.path,
            "trigger_terms": skill.trigger_terms,
            "token_count_estimate": skill.token_count_estimate,
        }
        for skill in _skills()
    ]
    (root / "tasks.jsonl").write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    (root / "skills.jsonl").write_text(
        "".join(json.dumps(skill, sort_keys=True) + "\n" for skill in skills),
        encoding="utf-8",
    )
    return root


def _run_stage2_final_export(stage2_module, root: Path, output: Path, router_id: str):
    skills = [
        json.loads(line)
        for line in (root / "skills.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    config_id = f"stage2-{router_id}-query-contract"
    config = {
        "schema_version": stage2_module.STAGE2_ROUTED_PREDICTION_CONFIG_SCHEMA,
        "config_id": config_id,
        "router_id": router_id,
        "top_k": 2,
        "global_skill_registry_hash": _stage2_registry_hash(skills),
        "approval": {"source": "query-contract-test"},
    }
    config_path = output / "approved-router-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    stage2_module.write_stage2_pilot_routed_prediction_artifacts(
        tasks_manifest_path=root / "tasks.jsonl",
        global_skill_registry_path=root / "skills.jsonl",
        output_path=output / "routed.json",
        manifest_output_path=output / "manifest.json",
        router_id=router_id,
        config_id=config_id,
        top_k=2,
        approved_router_config_path=config_path,
        final_evidence=True,
    )
    return json.loads((output / "routed.json").read_text(encoding="utf-8"))[
        "predictions"
    ]


def _stage2_registry_hash(skills: list[dict]) -> str:
    records = {}
    for skill in skills:
        identity = {
            "skill_id": skill["skill_id"],
            "name": skill["name"],
            "description": skill["description"],
            "body": skill["body"],
        }
        records[skill["skill_id"]] = {
            **identity,
            "skill_hash": _canonical_hash(identity),
            "name_hash": _sha256_text(skill["name"]),
            "description_hash": _sha256_text(skill["description"]),
            "body_hash": _sha256_text(skill["body"]),
            "public_skill_text_leakage_guard": "PASS",
        }
    return _canonical_hash(dict(sorted(records.items())))


def _canonical_hash(value) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ordered_predictions(predictions: dict[str, list[str]]) -> list[list[str]]:
    return [predictions[task_id] for task_id in sorted(predictions)]
