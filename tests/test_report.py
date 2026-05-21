import json

import pytest

from hermes_skilleval.report import write_markdown_report


def _write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )


def test_write_markdown_report_includes_metrics_and_failures(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "python-debugging-001",
                "router": "keyword",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": ["songwriting-and-ai-music"],
                "latency_ms": 1.0,
            },
            {
                "task_id": "research-001",
                "router": "keyword",
                "selected_skill_ids": ["songwriting-and-ai-music"],
                "gold_skills": ["research"],
                "negative_skills": ["songwriting-and-ai-music"],
                "latency_ms": 3.0,
            },
        ],
    )
    output = tmp_path / "report.md"

    write_markdown_report(results, output)
    text = output.read_text(encoding="utf-8")

    assert "# Hermes SkillEval Report" in text
    assert "Recall@1" in text
    assert "python-debugging-001" in text
    assert "research-001" in text
    assert "| Recall@1 | 0.500 |" in text
    assert "| Recall@3 | 0.500 |" in text
    assert "| Recall@5 | 0.500 |" in text
    assert "| Precision@5 | 0.100 |" in text
    assert "| MRR | 0.500 |" in text
    assert "| NDCG@5 | 0.500 |" in text
    assert "| Negative Hit Rate | 0.500 |" in text
    assert "| Average Latency (ms) | 2.000 |" in text


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


def test_write_markdown_report_escapes_markdown_table_cells(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "task|one\ncontinued",
                "router": "keyword",
                "selected_skill_ids": ["skill|pipe", "skill\nline"],
                "gold_skills": ["gold|skill"],
                "negative_skills": ["negative"],
                "latency_ms": 2.0,
            }
        ],
    )
    output = tmp_path / "report.md"

    write_markdown_report(results, output)
    text = output.read_text(encoding="utf-8")

    assert "task\\|one continued" in text
    assert "skill\\|pipe" in text
    assert "skill line" in text
    assert "gold\\|skill" in text


def test_write_markdown_report_rejects_mixed_router_results(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "task-001",
                "router": "keyword",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": 1.0,
            },
            {
                "task_id": "task-002",
                "router": "hybrid",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": 1.0,
            },
        ],
    )

    with pytest.raises(ValueError, match=rf"{results}.*hybrid.*keyword"):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_rejects_bool_latency(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "task-001",
                "router": "keyword",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": True,
            }
        ],
    )

    with pytest.raises(ValueError, match=rf"latency_ms.*numeric.*{results}.*line 1"):
        write_markdown_report(results, tmp_path / "report.md")


@pytest.mark.parametrize("latency_ms", [float("nan"), float("inf"), float("-inf")])
def test_write_markdown_report_rejects_non_finite_latency(tmp_path, latency_ms):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "task-001",
                "router": "keyword",
                "selected_skill_ids": ["systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": latency_ms,
            }
        ],
    )

    with pytest.raises(ValueError, match=rf"latency_ms.*finite.*{results}.*line 1"):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_rejects_duplicate_selected_skills(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "task-001",
                "router": "keyword",
                "selected_skill_ids": ["systematic-debugging", "systematic-debugging"],
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": 1.0,
            }
        ],
    )

    with pytest.raises(
        ValueError, match=rf"duplicate.*selected_skill_ids.*{results}.*line 1"
    ):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_rejects_malformed_jsonl(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text('{"task_id": "task-001"\n', encoding="utf-8")

    with pytest.raises(ValueError, match=rf"malformed JSONL.*{results}.*line 1"):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_rejects_non_object_jsonl_line(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ValueError, match=rf"expected object.*{results}.*line 1"):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_rejects_missing_required_fields(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(results, [{"task_id": "task-001"}])

    with pytest.raises(ValueError, match=rf"missing fields.*{results}.*line 1.*router"):
        write_markdown_report(results, tmp_path / "report.md")


def test_write_markdown_report_rejects_wrong_list_field_types(tmp_path):
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {
                "task_id": "task-001",
                "router": "keyword",
                "selected_skill_ids": "systematic-debugging",
                "gold_skills": ["systematic-debugging"],
                "negative_skills": [],
                "latency_ms": 1.0,
            }
        ],
    )

    with pytest.raises(
        ValueError, match=rf"selected_skill_ids.*list of strings.*{results}.*line 1"
    ):
        write_markdown_report(results, tmp_path / "report.md")
