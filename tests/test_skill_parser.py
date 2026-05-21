from pathlib import Path

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
