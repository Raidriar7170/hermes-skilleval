from pathlib import Path

import pytest

from hermes_skilleval.skill_parser import parse_skill_file, scan_skills


FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_parse_skill_with_frontmatter():
    skill = parse_skill_file(FIXTURES / "coding" / "systematic-debugging" / "SKILL.md", FIXTURES)

    assert skill.id == "systematic-debugging"
    assert skill.name == "systematic-debugging"
    assert skill.category == "coding"
    assert "diagnosing failing tests" in skill.description
    assert "hypothesis-driven" in skill.body
    assert "debugging" in skill.trigger_terms
    assert skill.token_count_estimate > 0


def test_parse_skill_with_crlf_frontmatter(tmp_path):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "coding" / "crlf-skill"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_bytes(
        b"---\r\n"
        b"name: CRLF Skill\r\n"
        b"description: Handles Windows line endings.\r\n"
        b"---\r\n"
        b"# CRLF Skill Body\r\n"
        b"This body content should survive.\r\n"
    )

    skill = parse_skill_file(skill_path, skills_root)

    assert skill.id == "crlf-skill"
    assert skill.name == "CRLF Skill"
    assert skill.category == "coding"
    assert skill.description == "Handles Windows line endings."
    assert skill.body.splitlines() == [
        "# CRLF Skill Body",
        "This body content should survive.",
    ]


def test_parse_skill_rejects_malformed_frontmatter_with_path_context(tmp_path):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "coding" / "bad-skill"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        "---\n"
        "name: Bad Skill\n"
        "description: [unterminated\n"
        "---\n"
        "# Bad Skill\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        parse_skill_file(skill_path, skills_root)

    message = str(exc_info.value)
    assert "malformed skill frontmatter" in message
    assert str(skill_path) in message
    assert "SKILL.md" in message


def test_parse_skill_without_frontmatter_uses_fallbacks():
    skill = parse_skill_file(
        FIXTURES / "creative" / "songwriting-and-ai-music" / "SKILL.md",
        FIXTURES,
    )

    assert skill.id == "songwriting-and-ai-music"
    assert skill.name == "Songwriting and AI Music"
    assert skill.category == "creative"
    assert skill.description == "Use when writing lyrics, melodies, hooks, or prompts for music generation."


def test_scan_skills_recursively():
    skills = scan_skills(FIXTURES)
    ids = {skill.id for skill in skills}

    assert ids == {
        "systematic-debugging",
        "test-driven-development",
        "songwriting-and-ai-music",
    }
