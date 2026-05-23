import sys
import types

import pytest

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.routers.embedding import (
    EmbeddingRouter,
    SentenceTransformerEmbeddingModel,
)


def test_embedding_router_ranks_semantically_relevant_skill_first():
    skills = [
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="/skills/systematic-debugging/SKILL.md",
            category="coding",
            description="Diagnose failing tests and runtime errors.",
            body="Reproduce failures, isolate root causes, and verify fixes.",
            trigger_terms=["debugging", "failing", "tests"],
            token_count_estimate=12,
        ),
        Skill(
            id="songwriting-and-ai-music",
            name="Songwriting",
            path="/skills/songwriting/SKILL.md",
            category="creative",
            description="Write lyrics and music prompts.",
            body="Create hooks, melodies, verses, and chorus ideas.",
            trigger_terms=["lyrics", "music"],
            token_count_estimate=9,
        ),
    ]
    task = BenchmarkTask(
        id="python-debugging-001",
        category="coding",
        difficulty="easy",
        prompt="A Python test suite is failing and needs debugging.",
        gold_skills=["systematic-debugging"],
        negative_skills=["songwriting-and-ai-music"],
        verifier="skill_selection",
    )

    result = EmbeddingRouter().route(task, skills, top_k=2)

    assert result.router == "embedding"
    assert result.selected_skill_ids[0] == "systematic-debugging"
    assert result.scores["systematic-debugging"] > result.scores["songwriting-and-ai-music"]
    assert result.latency_ms >= 0.0


def test_embedding_router_orders_ties_by_skill_id():
    skills = [
        Skill(
            id="zeta",
            name="Zeta",
            path="/skills/zeta/SKILL.md",
            category="music",
            description="Compose melodies.",
            body="Write harmony and rhythm.",
            trigger_terms=["song"],
            token_count_estimate=8,
        ),
        Skill(
            id="alpha",
            name="Alpha",
            path="/skills/alpha/SKILL.md",
            category="creative",
            description="Draft visual concepts.",
            body="Sketch layouts and palettes.",
            trigger_terms=["design"],
            token_count_estimate=8,
        ),
    ]
    task = BenchmarkTask(
        id="zero-overlap",
        category="astronomy",
        difficulty="easy",
        prompt="Measure a telescope parallax observation.",
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )

    result = EmbeddingRouter().route(task, skills, top_k=2)

    assert result.selected_skill_ids == ["alpha", "zeta"]


@pytest.mark.parametrize("top_k", [0, -1])
def test_embedding_router_rejects_non_positive_top_k(top_k):
    task = BenchmarkTask(
        id="invalid-top-k",
        category="coding",
        difficulty="easy",
        prompt="Debug a failure.",
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )
    skills = [
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="/skills/systematic-debugging/SKILL.md",
            category="coding",
            description="Diagnose failing tests.",
            body="Reproduce and isolate.",
            trigger_terms=["debugging"],
            token_count_estimate=8,
        )
    ]

    with pytest.raises(ValueError, match="top_k must be positive"):
        EmbeddingRouter().route(task, skills, top_k=top_k)


def test_embedding_router_rejects_empty_skill_index():
    task = BenchmarkTask(
        id="empty",
        category="coding",
        difficulty="easy",
        prompt="Debug a failure.",
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )

    with pytest.raises(ValueError, match="skill index is empty"):
        EmbeddingRouter().route(task, [], top_k=5)


def test_sentence_transformer_backend_calls_optional_dependency(monkeypatch):
    calls = []

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            calls.append(("init", model_name))

        def encode(self, sentences, normalize_embeddings=True):
            calls.append(("encode", list(sentences), normalize_embeddings))
            return [[1.0, 0.0], [0.0, 1.0]]

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    model = SentenceTransformerEmbeddingModel("fake-model")
    vectors = model.encode_batch(["debug failing tests", "write a song"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert calls == [
        ("init", "fake-model"),
        ("encode", ["debug failing tests", "write a song"], True),
    ]


def test_sentence_transformer_backend_reports_missing_optional_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(RuntimeError, match="sentence-transformers"):
        SentenceTransformerEmbeddingModel("missing-model")


def test_embedding_router_caches_skill_vectors_between_routes(tmp_path):
    class CountingModel:
        def __init__(self):
            self.cache_key = "counting-model"
            self.calls = []

        def encode_batch(self, texts):
            texts = list(texts)
            self.calls.append(texts)
            return [
                [1.0, 0.0] if "debug" in text.lower() else [0.0, 1.0]
                for text in texts
            ]

    skill = Skill(
        id="systematic-debugging",
        name="Systematic Debugging",
        path="/skills/systematic-debugging/SKILL.md",
        category="coding",
        description="Debug failing tests.",
        body="Reproduce and isolate.",
        trigger_terms=["debug"],
        token_count_estimate=8,
    )
    task = BenchmarkTask(
        id="debug-task",
        category="coding",
        difficulty="easy",
        prompt="Debug failing tests.",
        gold_skills=["systematic-debugging"],
        negative_skills=[],
        verifier="skill_selection",
    )
    model = CountingModel()
    router = EmbeddingRouter(model=model, cache_path=tmp_path / "embeddings.json")

    router.route(task, [skill], top_k=1)
    router.route(task, [skill], top_k=1)

    assert len(model.calls) == 3
    assert len(model.calls[0]) == 1
    assert len(model.calls[1]) == 1
    assert len(model.calls[2]) == 1
    assert (tmp_path / "embeddings.json").exists()
