import json

import pytest

from hermes_skilleval.report import write_markdown_report


def test_write_markdown_report_includes_metrics_and_failures(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "python-debugging-001",
                        "router": "keyword",
                        "selected_skill_ids": ["systematic-debugging"],
                        "gold_skills": ["systematic-debugging"],
                        "negative_skills": ["songwriting-and-ai-music"],
                        "latency_ms": 1.0,
                    }
                ),
                json.dumps(
                    {
                        "task_id": "research-001",
                        "router": "keyword",
                        "selected_skill_ids": ["songwriting-and-ai-music"],
                        "gold_skills": ["research"],
                        "negative_skills": ["songwriting-and-ai-music"],
                        "latency_ms": 3.0,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.md"

    write_markdown_report(results, output)
    text = output.read_text(encoding="utf-8")

    assert "# Hermes SkillEval Report" in text
    assert "Recall@1" in text
    assert "python-debugging-001" in text
    assert "research-001" in text


def test_write_markdown_report_rejects_empty_results(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match=str(results)):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_creates_parent_directories(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(
        json.dumps(
            {
                "task_id": "python-debugging-001",
                "router": "keyword",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": 2.0,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "nested" / "reports" / "report.md"

    write_markdown_report(results, output)

    assert output.exists()
