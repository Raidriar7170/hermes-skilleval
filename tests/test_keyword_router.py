import pytest

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.routers.keyword import KeywordRouter


def test_keyword_router_ranks_relevant_skill_first():
    skills = [
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="/skills/systematic-debugging/SKILL.md",
            category="coding",
            description="Diagnose failing tests and runtime errors.",
            body="Reproduce failures and isolate root causes.",
            trigger_terms=["debugging", "failing", "tests"],
            token_count_estimate=12,
        ),
        Skill(
            id="songwriting-and-ai-music",
            name="Songwriting",
            path="/skills/songwriting/SKILL.md",
            category="creative",
            description="Write lyrics and music prompts.",
            body="Create hooks and melodies.",
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

    result = KeywordRouter().route(task, skills, top_k=2)

    assert result.selected_skill_ids[0] == "systematic-debugging"
    assert result.scores["systematic-debugging"] > result.scores["songwriting-and-ai-music"]
    assert result.latency_ms >= 0


def test_keyword_router_rejects_empty_skill_index():
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
        KeywordRouter().route(task, [], top_k=5)
