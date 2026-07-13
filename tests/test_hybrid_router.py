from pathlib import Path
import time

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.keyword import KeywordRouter
from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.task_loader import load_task


SKILLS = Path(__file__).parent / "fixtures" / "skills"
TASKS = Path(__file__).parent / "fixtures" / "tasks"


def test_hybrid_router_works_without_embedding_dependency():
    skills = scan_skills(SKILLS)
    task = load_task(TASKS / "python-debugging-001")

    result = HybridRouter().route(task, skills, top_k=3)

    assert result.router == "hybrid"
    assert "systematic-debugging" in result.selected_skill_ids[:2]


def test_hybrid_router_prompt_skill_id_boost_is_case_insensitive():
    skills = [
        Skill(
            id="systematic-debugging",
            name="Systematic Debugging",
            path="/skills/systematic-debugging/SKILL.md",
            category="coding",
            description="Diagnose failing tests and runtime errors.",
            body="Reproduce failures and isolate root causes.",
            trigger_terms=["debugging"],
            token_count_estimate=12,
        ),
        Skill(
            id="test-driven-development",
            name="Test Driven Development",
            path="/skills/test-driven-development/SKILL.md",
            category="coding",
            description="Write a failing test before code.",
            body="Red green refactor.",
            trigger_terms=["testing"],
            token_count_estimate=10,
        ),
    ]
    task = BenchmarkTask(
        id="explicit-skill-id",
        category="uncategorized",
        difficulty="easy",
        prompt="Use SYSTEMATIC-DEBUGGING for this one.",
        gold_skills=["systematic-debugging"],
        negative_skills=[],
        verifier="skill_selection",
    )

    result = HybridRouter().route(task, skills, top_k=2)

    assert result.selected_skill_ids[0] == "systematic-debugging"
    assert result.scores["systematic-debugging"] >= 2.0


def test_hybrid_router_latency_includes_reranking_work(monkeypatch):
    class SlowSkillId:
        @property
        def id(self):
            time.sleep(0.002)
            return "slow-skill"

    task = BenchmarkTask(
        id="latency",
        category="coding",
        difficulty="easy",
        prompt="No explicit skill mention.",
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )
    skills = [SlowSkillId()]

    def fast_keyword_route(self, task, skills, top_k):
        return RouteResult(
            task_id=task.id,
            router="keyword",
            selected_skill_ids=["slow-skill"],
            scores={"slow-skill": 0.0},
            latency_ms=0.0,
        )

    monkeypatch.setattr(KeywordRouter, "route", fast_keyword_route)

    result = HybridRouter().route(task, skills, top_k=1)

    assert result.latency_ms >= 1.0
