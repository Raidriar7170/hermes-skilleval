from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill


def test_skill_dataclass_fields():
    skill = Skill(
        id="systematic-debugging",
        name="Systematic Debugging",
        path="/tmp/skills/systematic-debugging/SKILL.md",
        category="coding",
        description="Debug failures systematically.",
        body="Use a hypothesis-driven debugging loop.",
        trigger_terms=["debugging", "failure"],
        token_count_estimate=8,
    )

    assert skill.id == "systematic-debugging"
    assert skill.category == "coding"
    assert skill.token_count_estimate == 8


def test_benchmark_task_dataclass_fields():
    task = BenchmarkTask(
        id="python-debugging-001",
        category="coding",
        difficulty="easy",
        prompt="A Python test suite is failing.",
        gold_skills=["systematic-debugging"],
        negative_skills=["songwriting-and-ai-music"],
        verifier="skill_selection",
    )

    assert task.gold_skills == ["systematic-debugging"]
    assert task.negative_skills == ["songwriting-and-ai-music"]


def test_route_result_dataclass_fields():
    result = RouteResult(
        task_id="python-debugging-001",
        router="keyword",
        selected_skill_ids=["systematic-debugging"],
        scores={"systematic-debugging": 1.0},
        latency_ms=2.5,
    )

    assert result.router == "keyword"
    assert result.scores["systematic-debugging"] == 1.0
