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

    assert [skill.id for skill in loaded] == [skill.id for skill in skills]


def test_load_skill_index_rejects_non_list_json(tmp_path):
    index = tmp_path / "skills.json"
    index.write_text('{"id": "not-a-list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="skill index JSON must be a list"):
        load_skill_index(index)
