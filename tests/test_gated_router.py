from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.gated import VerificationGatedRouter


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


def test_gated_router_demotes_category_mismatched_candidates():
    skills = [
        _skill(
            "ascii-art",
            "creative",
            "ASCII Art",
            "Create text diagrams and terminal art.",
        ),
        _skill(
            "systematic-debugging",
            "coding",
            "Systematic Debugging",
            "Diagnose failing tests, runtime errors, and CLI bugs.",
        ),
    ]
    task = _task(
        "coding-debugging-002",
        "coding",
        "A CLI command exits without writing output. Diagnose the bug with tests.",
        ["systematic-debugging"],
        ["ascii-art"],
    )
    base_router = StubRouter(
        ["ascii-art", "systematic-debugging"],
        {"ascii-art": 0.9, "systematic-debugging": 0.8},
    )

    result = VerificationGatedRouter(base_router=base_router).route(task, skills, top_k=2)

    assert result.router == "gated"
    assert result.selected_skill_ids == ["systematic-debugging", "ascii-art"]
    assert result.scores["systematic-debugging"] > result.scores["ascii-art"]


def test_gated_router_uses_prompt_evidence_within_same_category():
    skills = [
        _skill(
            "systematic-debugging",
            "coding",
            "Systematic Debugging",
            "Diagnose runtime failures and isolate root causes.",
        ),
        _skill(
            "test-driven-development",
            "coding",
            "Test-Driven Development",
            "Refactor behavior safely by writing tests first.",
        ),
    ]
    task = _task(
        "coding-debugging-009",
        "coding",
        "Refactor a utility function while preserving behavior through tests.",
        ["test-driven-development"],
        ["songwriting-and-ai-music"],
    )
    base_router = StubRouter(
        ["systematic-debugging", "test-driven-development"],
        {"systematic-debugging": 0.55, "test-driven-development": 0.54},
    )

    result = VerificationGatedRouter(base_router=base_router).route(task, skills, top_k=2)

    assert result.selected_skill_ids == [
        "test-driven-development",
        "systematic-debugging",
    ]
    assert base_router.requested_top_k == 2


def test_gated_router_requests_larger_candidate_pool_than_top_k():
    skills = [
        _skill("a", "coding", "A", "alpha"),
        _skill("b", "coding", "B", "bravo"),
        _skill("c", "coding", "C", "charlie"),
    ]
    task = _task("pool", "coding", "alpha", ["a"], [])
    base_router = StubRouter(["a", "b", "c"], {"a": 0.3, "b": 0.2, "c": 0.1})

    VerificationGatedRouter(base_router=base_router, candidate_pool_size=3).route(
        task,
        skills,
        top_k=1,
    )

    assert base_router.requested_top_k == 3


def test_selective_gated_router_filters_low_confidence_cross_category_candidates():
    skills = [
        _skill(
            "systematic-debugging",
            "coding",
            "Systematic Debugging",
            "Diagnose failing tests and command-line bugs.",
        ),
        _skill(
            "test-driven-development",
            "coding",
            "Test-Driven Development",
            "Preserve behavior through focused tests.",
        ),
        _skill(
            "ascii-art",
            "creative",
            "ASCII Art",
            "Create terminal illustrations.",
        ),
    ]
    task = _task(
        "coding-debugging-002",
        "coding",
        "A CLI command exits without writing output. Diagnose the bug with tests.",
        ["systematic-debugging"],
        ["ascii-art"],
    )
    base_router = StubRouter(
        ["systematic-debugging", "test-driven-development", "ascii-art"],
        {
            "systematic-debugging": 0.8,
            "test-driven-development": 0.7,
            "ascii-art": 0.6,
        },
    )

    result = VerificationGatedRouter(
        base_router=base_router,
        selective=True,
        min_confidence=0.5,
    ).route(task, skills, top_k=5)

    assert result.selected_skill_ids == [
        "systematic-debugging",
        "test-driven-development",
    ]
    assert "ascii-art" not in result.selected_skill_ids


def test_non_selective_gated_router_keeps_requested_candidate_count():
    skills = [
        _skill("systematic-debugging", "coding", "Systematic Debugging", "debug bugs"),
        _skill("ascii-art", "creative", "ASCII Art", "draw terminals"),
    ]
    task = _task("coding-debugging-002", "coding", "debug a CLI", ["systematic-debugging"], ["ascii-art"])
    base_router = StubRouter(
        ["systematic-debugging", "ascii-art"],
        {"systematic-debugging": 0.8, "ascii-art": 0.6},
    )

    result = VerificationGatedRouter(base_router=base_router).route(
        task,
        skills,
        top_k=2,
    )

    assert result.selected_skill_ids == ["systematic-debugging", "ascii-art"]


def test_gated_router_rejects_invalid_min_confidence():
    base_router = StubRouter([], {})

    try:
        VerificationGatedRouter(
            base_router=base_router,
            selective=True,
            min_confidence=1.1,
        )
    except ValueError as error:
        assert "min_confidence" in str(error)
    else:
        raise AssertionError("expected min_confidence validation error")


def _skill(skill_id, category, name, description):
    return Skill(
        id=skill_id,
        name=name,
        path=f"/skills/{category}/{skill_id}/SKILL.md",
        category=category,
        description=description,
        body=description,
        trigger_terms=skill_id.split("-"),
        token_count_estimate=16,
    )


def _task(task_id, category, prompt, gold, negative):
    return BenchmarkTask(
        id=task_id,
        category=category,
        difficulty="medium",
        prompt=prompt,
        gold_skills=gold,
        negative_skills=negative,
        verifier="skill_selection",
    )
