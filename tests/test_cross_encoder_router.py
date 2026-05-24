import sys
import types

import pytest

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.cross_encoder import (
    CrossEncoderReranker,
    SentenceTransformerCrossEncoderModel,
    StaticCrossEncoderModel,
)
from hermes_skilleval.routers.verification import skill_text, task_text


class StubRouter(SkillRouter):
    name = "stub"

    def __init__(self, selected_skill_ids, scores):
        self.selected_skill_ids = selected_skill_ids
        self.scores = scores
        self.requested_top_k = None

    def route(self, task, skills, top_k):
        self.requested_top_k = top_k
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=self.selected_skill_ids[:top_k],
            scores=self.scores,
            latency_ms=0.0,
        )


def test_cross_encoder_reranks_embedding_candidates():
    skills = [
        _skill(
            "systematic-debugging",
            "coding",
            "Systematic Debugging",
            "Diagnose runtime failures.",
        ),
        _skill(
            "test-driven-development",
            "coding",
            "Test-Driven Development",
            "Preserve behavior through tests.",
        ),
        _skill("ascii-art", "creative", "ASCII Art", "Draw terminal art."),
    ]
    task = _task(
        "coding-debugging-001",
        "coding",
        "Fix a failing pytest suite by debugging the runtime error.",
    )
    base_router = StubRouter(
        ["test-driven-development", "systematic-debugging", "ascii-art"],
        {
            "test-driven-development": 0.9,
            "systematic-debugging": 0.8,
            "ascii-art": 0.7,
        },
    )
    model = StaticCrossEncoderModel(
        {
            (task_text(task), skill_text(skills[0])): 4.0,
            (task_text(task), skill_text(skills[1])): 2.0,
            (task_text(task), skill_text(skills[2])): -1.0,
        }
    )

    result = CrossEncoderReranker(
        base_router=base_router,
        model=model,
        candidate_pool_size=3,
    ).route(task, skills, top_k=2)

    assert result.router == "cross-encoder"
    assert result.selected_skill_ids == [
        "systematic-debugging",
        "test-driven-development",
    ]
    assert base_router.requested_top_k == 3
    assert result.scores["systematic-debugging"] > result.scores[
        "test-driven-development"
    ]


def test_cross_encoder_ties_fall_back_to_base_rank_then_skill_id():
    skills = [
        _skill("beta", "coding", "Beta", "Debug tests."),
        _skill("alpha", "coding", "Alpha", "Debug tests."),
    ]
    task = _task("tie", "coding", "Debug tests.")
    base_router = StubRouter(["beta", "alpha"], {"beta": 0.7, "alpha": 0.7})
    model = StaticCrossEncoderModel(default_score=1.0)

    result = CrossEncoderReranker(base_router=base_router, model=model).route(
        task,
        skills,
        top_k=2,
    )

    assert result.selected_skill_ids == ["beta", "alpha"]


def test_cross_encoder_selective_mode_can_abstain_from_weak_candidates():
    skills = [
        _skill(
            "systematic-debugging",
            "coding",
            "Systematic Debugging",
            "Diagnose failing tests.",
        ),
        _skill("ascii-art", "creative", "ASCII Art", "Draw terminal art."),
    ]
    task = _task("weak", "coding", "Debug failing tests.")
    base_router = StubRouter(
        ["systematic-debugging", "ascii-art"],
        {"systematic-debugging": 0.9, "ascii-art": 0.8},
    )
    model = StaticCrossEncoderModel(default_score=-10.0)

    result = CrossEncoderReranker(
        base_router=base_router,
        model=model,
        selective=True,
        min_confidence=0.5,
    ).route(task, skills, top_k=5)

    assert result.selected_skill_ids == []


def test_cross_encoder_rejects_invalid_thresholds():
    base_router = StubRouter([], {})
    model = StaticCrossEncoderModel()

    for kwargs in (
        {"candidate_pool_size": 0},
        {"min_confidence": -0.1},
        {"min_confidence": 1.1},
        {"cross_encoder_batch_size": 0},
        {"contrastive_margin": -0.1},
        {"min_evidence": -0.1},
    ):
        with pytest.raises(ValueError):
            CrossEncoderReranker(base_router=base_router, model=model, **kwargs)


def test_sentence_transformer_cross_encoder_calls_optional_dependency(monkeypatch):
    calls = []

    class FakeCrossEncoder:
        def __init__(self, model_name):
            calls.append(("init", model_name))

        def predict(self, pairs, batch_size=16):
            calls.append(("predict", list(pairs), batch_size))
            return [3.0, 1.0]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(CrossEncoder=FakeCrossEncoder),
    )

    model = SentenceTransformerCrossEncoderModel("fake-reranker", batch_size=8)
    scores = model.score_pairs([("task", "skill-a"), ("task", "skill-b")])

    assert scores == [3.0, 1.0]
    assert calls == [
        ("init", "fake-reranker"),
        ("predict", [("task", "skill-a"), ("task", "skill-b")], 8),
    ]


def test_sentence_transformer_cross_encoder_reports_missing_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(RuntimeError, match="cross-encoder backend"):
        SentenceTransformerCrossEncoderModel("missing-reranker")


def _skill(skill_id, category, name, description):
    return Skill(
        id=skill_id,
        name=name,
        path=f"/skills/{skill_id}/SKILL.md",
        category=category,
        description=description,
        body=description,
        trigger_terms=description.lower().split(),
        token_count_estimate=8,
    )


def _task(task_id, category, prompt):
    return BenchmarkTask(
        id=task_id,
        category=category,
        difficulty="medium",
        prompt=prompt,
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )
