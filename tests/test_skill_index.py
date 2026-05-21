from pathlib import Path

import pytest

from hermes_skilleval.skill_index import load_skill_index, save_skill_index
from hermes_skilleval.skill_parser import scan_skills


FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_save_and_load_skill_index(tmp_path):
    skills = scan_skills(FIXTURES)
    output = tmp_path / "skills.json"

    save_skill_index(skills, output)
    loaded = load_skill_index(output)

    assert loaded == skills


def test_load_skill_index_rejects_non_list_json(tmp_path):
    index = tmp_path / "skills.json"
    index.write_text('{"id": "not-a-list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="skill index JSON must be a list"):
        load_skill_index(index)


def test_load_skill_index_rejects_non_object_list_entry(tmp_path):
    index = tmp_path / "skills.json"
    index.write_text('["not-an-object"]', encoding="utf-8")

    with pytest.raises(ValueError, match=r"skills\.json item 0 must be an object"):
        load_skill_index(index)


def test_load_skill_index_rejects_missing_required_field(tmp_path):
    index = tmp_path / "skills.json"
    index.write_text(
        """
        [
          {
            "id": "systematic-debugging",
            "name": "Systematic Debugging",
            "path": "/skills/systematic-debugging/SKILL.md",
            "category": "coding",
            "description": "Diagnose failures.",
            "trigger_terms": ["debugging"],
            "token_count_estimate": 12
          }
        ]
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"skills\.json item 0 missing fields: body"):
        load_skill_index(index)


def test_load_skill_index_rejects_unknown_field(tmp_path):
    index = tmp_path / "skills.json"
    index.write_text(
        """
        [
          {
            "id": "systematic-debugging",
            "name": "Systematic Debugging",
            "path": "/skills/systematic-debugging/SKILL.md",
            "category": "coding",
            "description": "Diagnose failures.",
            "body": "Find root causes.",
            "trigger_terms": ["debugging"],
            "token_count_estimate": 12,
            "extra": "nope"
          }
        ]
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"skills\.json item 0 unknown fields: extra"):
        load_skill_index(index)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("trigger_terms", '"debugging"', "trigger_terms must be a list of strings"),
        ("trigger_terms", '["debugging", 3]', "trigger_terms must be a list of strings"),
        ("token_count_estimate", '"12"', "token_count_estimate must be an int"),
        ("token_count_estimate", "true", "token_count_estimate must be an int"),
    ],
)
def test_load_skill_index_rejects_wrong_field_type(tmp_path, field, value, match):
    index = tmp_path / "skills.json"
    valid_json = {
        "id": '"systematic-debugging"',
        "name": '"Systematic Debugging"',
        "path": '"/skills/systematic-debugging/SKILL.md"',
        "category": '"coding"',
        "description": '"Diagnose failures."',
        "body": '"Find root causes."',
        "trigger_terms": '["debugging"]',
        "token_count_estimate": "12",
    }
    valid_json[field] = value
    fields = ",\n".join(f'"{key}": {field_value}' for key, field_value in valid_json.items())
    index.write_text(f"[{{{fields}}}]", encoding="utf-8")

    with pytest.raises(ValueError, match=rf"skills\.json item 0 {match}"):
        load_skill_index(index)
