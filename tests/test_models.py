from hermes_skilleval.models import (
    BenchmarkTask,
    EvalRun,
    MetricSummary,
    RouteResult,
    Skill,
)


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


def test_eval_run_dataclass_fields():
    task = BenchmarkTask(
        id="python-debugging-001",
        category="coding",
        difficulty="easy",
        prompt="A Python test suite is failing.",
        gold_skills=["systematic-debugging"],
        negative_skills=["songwriting-and-ai-music"],
        verifier="skill_selection",
    )
    result = RouteResult(
        task_id="python-debugging-001",
        router="keyword",
        selected_skill_ids=["systematic-debugging"],
        scores={"systematic-debugging": 1.0},
        latency_ms=2.5,
    )

    run = EvalRun(task=task, result=result, warnings=["low confidence"])

    assert run.task.id == "python-debugging-001"
    assert run.result.router == "keyword"
    assert run.warnings == ["low confidence"]


def test_metric_summary_dataclass_fields():
    summary = MetricSummary(
        router="keyword",
        task_count=30,
        recall_at_1=0.4,
        recall_at_3=0.7,
        recall_at_5=0.8,
        precision_at_5=0.3,
        mrr=0.6,
        ndcg_at_5=0.75,
        negative_hit_rate=0.1,
        average_latency_ms=3.2,
    )

    assert summary.router == "keyword"
    assert summary.task_count == 30
    assert summary.ndcg_at_5 == 0.75


def test_cli_main_returns_one_and_prints_help_without_command(capsys):
    from hermes_skilleval.cli import main

    assert main([]) == 1
    assert "usage: skilleval" in capsys.readouterr().out
