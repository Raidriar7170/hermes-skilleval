import json
from pathlib import Path

import pytest

from hermes_skilleval.diagnostics import (
    scan_diagnostic_source,
    write_scan_artifact,
)


def test_scan_markdown_skill_folder_writes_source_annotated_records(tmp_path: Path):
    source = tmp_path / "skills"
    _write_skill(
        source / "coding" / "systematic-debugging" / "SKILL.md",
        name="systematic-debugging",
        description="Use when diagnosing failing tests with a hypothesis-driven debug loop.",
        body=(
            "Use when tests fail, errors repeat, or logs need structured analysis.\n"
            "Avoid when the task is a greenfield feature with no observed failure."
        ),
    )
    _write_skill_without_frontmatter(
        source / "creative" / "prompt-polish" / "SKILL.md",
        "# Prompt Polish\nUse when refining prompts.\n",
    )

    output = tmp_path / "scan.json"
    artifact = write_scan_artifact(source, output)

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == artifact
    assert saved["artifact_type"] == "diagnostic_scan"
    assert saved["schema_version"] == "diagnostic.v1"
    assert saved["summary"] == {
        "skill_count": 2,
        "source_types": {"markdown_skill": 2},
        "warning_count": 1,
    }

    debug_record = _skill(saved, "systematic-debugging")
    assert debug_record["source"]["type"] == "markdown_skill"
    assert debug_record["source"]["file_path"].endswith("systematic-debugging/SKILL.md")
    assert debug_record["source"]["relative_path"] == "coding/systematic-debugging/SKILL.md"
    assert debug_record["routing_cues"]["negative_boundary_terms"] == ["avoid"]
    assert debug_record["parser_warnings"] == []

    fallback_record = _skill(saved, "prompt-polish")
    assert fallback_record["name"] == "Prompt Polish"
    assert "missing frontmatter" in fallback_record["parser_warnings"][0]


def test_scan_mcp_tool_schema_writes_tool_like_skill_records(tmp_path: Path):
    source = tmp_path / "mcp.json"
    source.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "browser_smoke_test",
                        "description": "Run browser smoke checks against local pages.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "Local page URL to test.",
                                },
                                "screenshot": {"type": "boolean"},
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    artifact = scan_diagnostic_source(source)

    assert artifact["summary"]["source_types"] == {"mcp_tool_schema": 1}
    record = artifact["skills"][0]
    assert record["id"] == "browser_smoke_test"
    assert record["category"] == "mcp-tool"
    assert record["description"] == "Run browser smoke checks against local pages."
    assert "url:string" in record["routing_cues"]["input_schema_terms"]
    assert record["source"]["type"] == "mcp_tool_schema"


def test_scan_propagates_mcp_parser_warnings(tmp_path: Path):
    source = tmp_path / "mcp.json"
    source.write_text(
        json.dumps({"tools": [{"name": "thin_tool", "inputSchema": []}]}),
        encoding="utf-8",
    )

    artifact = scan_diagnostic_source(source)

    record = artifact["skills"][0]
    assert record["parser_warnings"] == [
        "missing description",
        "inputSchema is not an object",
    ]
    assert artifact["summary"]["warning_count"] == 2


def test_scan_rejects_unsupported_source_shape(tmp_path: Path):
    source = tmp_path / "notes.txt"
    source.write_text("not a skill source", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported skill source shape"):
        scan_diagnostic_source(source)


def _write_skill(path: Path, *, name: str, description: str, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )


def _write_skill_without_frontmatter(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")


def _skill(artifact: dict, skill_id: str) -> dict:
    return next(skill for skill in artifact["skills"] if skill["id"] == skill_id)
