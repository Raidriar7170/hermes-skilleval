import json

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.self_improvement import (
    apply_skill_patches,
    propose_skill_patches,
    write_acceptance_report,
    write_patch_report,
    write_patches_json,
)
from hermes_skilleval.skill_index import load_skill_index, save_skill_index


def test_propose_skill_patches_adds_prompt_terms_to_gold_skill_on_top1_miss():
    skills = [
        _skill(
            "test-driven-development",
            "coding",
            ["test", "driven", "development"],
        ),
        _skill("systematic-debugging", "coding", ["systematic", "debugging"]),
    ]
    tasks = [
        _task(
            "coding-debugging-009",
            "coding",
            "Refactor a utility function while preserving behavior through tests.",
            ["test-driven-development"],
        )
    ]
    records = [
        _record(
            "coding-debugging-009",
            ["systematic-debugging", "test-driven-development"],
            ["test-driven-development"],
        )
    ]

    patches = propose_skill_patches(records, skills, tasks)

    assert len(patches) == 1
    patch = patches[0]
    assert patch.skill_id == "test-driven-development"
    assert patch.field == "trigger_terms"
    assert patch.source_task_ids == ["coding-debugging-009"]
    assert "refactor" in patch.after
    assert "preserving" in patch.after
    assert patch.before == ["test", "driven", "development"]


def test_apply_skill_patches_returns_patched_copy_without_mutating_original():
    skill = _skill("python-data-analysis", "data-analysis", ["python", "data"])
    patch = propose_skill_patches(
        [
            _record(
                "data-mlops-006",
                ["data-analysis", "python-data-analysis"],
                ["python-data-analysis"],
            )
        ],
        [skill, _skill("data-analysis", "data-analysis", ["data", "analysis"])],
        [
            _task(
                "data-mlops-006",
                "data-analysis",
                "Create a chart from tabular benchmark results.",
                ["python-data-analysis"],
            )
        ],
    )[0]

    patched = apply_skill_patches([skill], [patch])

    assert skill.trigger_terms == ["python", "data"]
    assert patched[0].trigger_terms != skill.trigger_terms
    assert "chart" in patched[0].trigger_terms
    assert "tabular" in patched[0].trigger_terms


def test_write_patches_json_report_and_patched_index(tmp_path):
    skill = _skill("test-driven-development", "coding", ["test"])
    task = _task(
        "coding-debugging-009",
        "coding",
        "Refactor behavior through tests.",
        ["test-driven-development"],
    )
    patch = propose_skill_patches(
        [_record(task.id, ["systematic-debugging"], ["test-driven-development"])],
        [skill],
        [task],
    )[0]
    patches_path = tmp_path / "patches.json"
    report_path = tmp_path / "patches.md"
    patched_index_path = tmp_path / "patched-skills.json"

    write_patches_json([patch], patches_path)
    write_patch_report([patch], report_path)
    save_skill_index(apply_skill_patches([skill], [patch]), patched_index_path)

    payload = json.loads(patches_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")
    patched = load_skill_index(patched_index_path)

    assert payload["patch_count"] == 1
    assert payload["patches"][0]["skill_id"] == "test-driven-development"
    assert "| test-driven-development | trigger_terms | proposed |" in report
    assert "refactor" in patched[0].trigger_terms


def test_write_acceptance_report_accepts_non_regressing_improvement(tmp_path):
    baseline = [
        _metric_record(
            recall_at_1=0.5,
            mrr=0.75,
            ndcg_at_5=0.8,
            negative_hit_rate=0.1,
        )
    ]
    candidate = [
        _metric_record(
            recall_at_1=1.0,
            mrr=1.0,
            ndcg_at_5=1.0,
            negative_hit_rate=0.1,
        )
    ]
    output = tmp_path / "acceptance.md"

    status = write_acceptance_report(
        baseline,
        candidate,
        output,
        baseline_name="before",
        candidate_name="patched",
    )

    text = output.read_text(encoding="utf-8")
    assert status == "accepted"
    assert "- Status: accepted" in text
    assert "| Recall@1 | 0.500 | 1.000 | +0.500 |" in text


def test_write_acceptance_report_rejects_metric_regression(tmp_path):
    baseline = [_metric_record(recall_at_1=1.0, negative_hit_rate=0.0)]
    candidate = [_metric_record(recall_at_1=1.0, negative_hit_rate=1.0)]

    status = write_acceptance_report(
        baseline,
        candidate,
        tmp_path / "acceptance.md",
        baseline_name="before",
        candidate_name="patched",
    )

    assert status == "rejected"


def _skill(skill_id, category, trigger_terms):
    return Skill(
        id=skill_id,
        name=skill_id.replace("-", " ").title(),
        path=f"benchmarks/skills/{category}/{skill_id}/SKILL.md",
        category=category,
        description=f"{skill_id} description",
        body=f"# {skill_id}",
        trigger_terms=trigger_terms,
        token_count_estimate=20,
    )


def _task(task_id, category, prompt, gold):
    return BenchmarkTask(
        id=task_id,
        category=category,
        difficulty="easy",
        prompt=prompt,
        gold_skills=gold,
        negative_skills=[],
        verifier="skill_selection",
    )


def _record(task_id, selected, gold):
    return {
        "task_id": task_id,
        "category": "coding",
        "router": "embedding-minilm",
        "selected_skill_ids": selected,
        "gold_skills": gold,
        "negative_skills": [],
    }


def _metric_record(
    *,
    recall_at_1=1.0,
    mrr=1.0,
    ndcg_at_5=1.0,
    negative_hit_rate=0.0,
):
    return {
        "recall_at_1": recall_at_1,
        "mrr": mrr,
        "ndcg_at_5": ndcg_at_5,
        "negative_hit_rate": negative_hit_rate,
    }
