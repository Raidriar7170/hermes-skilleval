import json

import pytest

from hermes_skilleval.comparison import write_comparison_report


def _record(router, recall_at_5, latency_ms):
    return {
        "task_id": "task-001",
        "router": router,
        "selected_skill_ids": ["systematic-debugging"],
        "gold_skills": ["systematic-debugging"],
        "negative_skills": [],
        "latency_ms": latency_ms,
        "recall_at_1": recall_at_5,
        "recall_at_3": recall_at_5,
        "recall_at_5": recall_at_5,
        "precision_at_5": 0.2,
        "mrr": recall_at_5,
        "ndcg_at_5": recall_at_5,
        "negative_hit_rate": 0.0,
    }


def test_write_comparison_report_summarizes_router_metrics(tmp_path):
    keyword = tmp_path / "keyword.jsonl"
    embedding = tmp_path / "embedding.jsonl"
    keyword.write_text(json.dumps(_record("keyword", 0.0, 2.0)), encoding="utf-8")
    embedding.write_text(json.dumps(_record("embedding", 1.0, 4.0)), encoding="utf-8")
    output = tmp_path / "comparison.md"

    write_comparison_report(
        {"keyword": keyword, "embedding": embedding},
        output,
    )

    text = output.read_text(encoding="utf-8")
    assert "# Hermes SkillEval Router Comparison" in text
    assert "| embedding | 1 | 1.000 | 1.000 | 1.000 | 0.200 | 1.000 | 1.000 | 0.000 | 4.000 |" in text
    assert "| keyword | 1 | 0.000 | 0.000 | 0.000 | 0.200 | 0.000 | 0.000 | 0.000 | 2.000 |" in text


def test_write_comparison_report_rejects_empty_router_results(tmp_path):
    with pytest.raises(ValueError, match="router_results must not be empty"):
        write_comparison_report({}, tmp_path / "comparison.md")


def test_write_comparison_report_rejects_empty_result_file(tmp_path):
    results = tmp_path / "empty.jsonl"
    results.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="no result records"):
        write_comparison_report({"keyword": results}, tmp_path / "comparison.md")
