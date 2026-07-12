from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.routers.verification import (
    confidence,
    prompt_evidence_score,
    select_candidates,
    verification_score,
)


def test_verification_score_prefers_matching_prompt_terms():
    task = _task(
        "coding-debugging-001",
        "coding",
        "Diagnose a failing pytest suite and isolate the runtime error.",
    )
    relevant = _skill(
        "systematic-debugging",
        "coding",
        "Systematic Debugging",
        "Diagnose failing tests and runtime errors.",
    )
    irrelevant = _skill(
        "songwriting-and-ai-music",
        "creative",
        "Songwriting",
        "Write melodies and lyrics.",
    )

    assert verification_score(task, relevant, 0.1) > verification_score(
        task,
        irrelevant,
        0.9,
    )


def test_prompt_evidence_uses_prompt_not_category_bonus():
    task = _task(
        "research-claims",
        "research",
        "Verify that each cited paper supports the empirical claims.",
    )
    citation = _skill(
        "citation-checking",
        "research",
        "Citation Checking",
        "Verify cited evidence and empirical claims.",
    )
    literature = _skill(
        "literature-review",
        "research",
        "Literature Review",
        "Compare related papers and organize prior work.",
    )

    assert prompt_evidence_score(task, citation) > prompt_evidence_score(
        task,
        literature,
    )


def test_select_candidates_filters_weak_same_category_negative():
    task = _task(
        "robustness-ambiguous-005",
        "research",
        "Verify that each cited paper actually supports a draft's empirical claims.",
    )
    citation = _skill(
        "citation-checking",
        "research",
        "Citation Checking",
        "Verify cited evidence for empirical claims.",
    )
    literature = _skill(
        "literature-review",
        "research",
        "Literature Review",
        "Compare related papers and organize prior work.",
    )

    selected = select_candidates(
        task,
        [citation, literature],
        {"citation-checking": 90.0, "literature-review": 90.0},
        min_confidence=0.5,
        contrastive_selective=True,
        contrastive_margin=3.0,
        min_evidence=2.0,
    )

    assert [skill.id for skill in selected] == ["citation-checking"]


def test_confidence_clamps_to_unit_interval():
    assert confidence(-10.0) == 0.0
    assert confidence(50.0) == 0.5
    assert confidence(120.0) == 1.0


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
