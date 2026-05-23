import json

import pytest

from hermes_skilleval.failure_analysis import write_failure_analysis_report


def _record(router, task_id, selected, gold, negative):
    return {
        "task_id": task_id,
        "category": "coding",
        "difficulty": "medium",
        "router": router,
        "selected_skill_ids": selected,
        "scores": {skill_id: 1.0 for skill_id in selected},
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": 1.0,
        "recall_at_1": 1.0 if selected and selected[0] in gold else 0.0,
        "recall_at_3": len(set(selected[:3]) & set(gold)) / len(gold),
        "recall_at_5": len(set(selected[:5]) & set(gold)) / len(gold),
        "precision_at_5": len(set(selected[:5]) & set(gold)) / 5,
        "mrr": _mrr(selected, gold),
        "ndcg_at_5": 1.0,
        "negative_hit_rate": 1.0 if set(selected[:5]) & set(negative) else 0.0,
    }


def _mrr(selected, gold):
    gold_set = set(gold)
    for index, skill_id in enumerate(selected, start=1):
        if skill_id in gold_set:
            return 1 / index
    return 0.0


def _write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )


def test_write_failure_analysis_report_summarizes_failure_modes_and_deltas(tmp_path):
    hashing = tmp_path / "hashing.jsonl"
    minilm = tmp_path / "minilm.jsonl"
    _write_jsonl(
        hashing,
        [
            _record(
                "embedding-hashing",
                "task-001",
                ["wrong-skill", "negative-skill", "gold-skill"],
                ["gold-skill"],
                ["negative-skill"],
            ),
            _record(
                "embedding-hashing",
                "task-002",
                ["gold-a", "wrong-skill", "gold-b"],
                ["gold-a", "gold-b"],
                [],
            ),
        ],
    )
    _write_jsonl(
        minilm,
        [
            _record(
                "embedding-minilm",
                "task-001",
                ["gold-skill", "wrong-skill"],
                ["gold-skill"],
                ["negative-skill"],
            ),
            _record(
                "embedding-minilm",
                "task-002",
                ["wrong-skill", "gold-a", "gold-b"],
                ["gold-a", "gold-b"],
                [],
            ),
        ],
    )
    output = tmp_path / "failure-analysis.md"

    write_failure_analysis_report(
        {
            "embedding-hashing": hashing,
            "embedding-minilm": minilm,
        },
        output,
        baseline="embedding-hashing",
        candidate="embedding-minilm",
    )

    text = output.read_text(encoding="utf-8")
    assert "# Hermes SkillEval Failure Analysis" in text
    assert "| embedding-hashing | 2 | 1 | 0 | 1 | 1 |" in text
    assert "| embedding-minilm | 2 | 1 | 0 | 0 | 1 |" in text
    assert "| Recall@5 | 1.000 | 1.000 | +0.000 |" in text
    assert "| MRR | 0.667 | 0.750 | +0.083 |" in text
    assert "| task-001 | improved | negative-hit@5: negative-skill; top1-miss | ok |" in text
    assert "| task-002 | regressed | ok | top1-miss |" in text


def test_write_failure_analysis_report_rejects_mismatched_task_sets(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(first, [_record("first", "task-001", ["gold"], ["gold"], [])])
    _write_jsonl(second, [_record("second", "task-002", ["gold"], ["gold"], [])])

    with pytest.raises(ValueError, match="same task ids"):
        write_failure_analysis_report(
            {"first": first, "second": second},
            tmp_path / "failure-analysis.md",
        )


def test_write_failure_analysis_report_marks_candidate_tradeoffs(tmp_path):
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write_jsonl(
        baseline,
        [
            _record(
                "baseline",
                "task-001",
                ["wrong-skill", "gold-skill"],
                ["gold-skill"],
                ["negative-skill"],
            )
        ],
    )
    _write_jsonl(
        candidate,
        [
            _record(
                "candidate",
                "task-001",
                ["gold-skill", "negative-skill"],
                ["gold-skill"],
                ["negative-skill"],
            )
        ],
    )
    output = tmp_path / "failure-analysis.md"

    write_failure_analysis_report(
        {"baseline": baseline, "candidate": candidate},
        output,
        baseline="baseline",
        candidate="candidate",
    )

    text = output.read_text(encoding="utf-8")
    assert (
        "| task-001 | trade-off | top1-miss | negative-hit@5: negative-skill |"
        in text
    )
