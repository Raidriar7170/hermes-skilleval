from pathlib import Path

from hermes_skilleval.routers.hybrid import HybridRouter
from hermes_skilleval.skill_parser import scan_skills
from hermes_skilleval.task_loader import load_task


SKILLS = Path(__file__).parent / "fixtures" / "skills"
TASKS = Path(__file__).parent / "fixtures" / "tasks"


def test_hybrid_router_works_without_embedding_dependency():
    skills = scan_skills(SKILLS)
    task = load_task(TASKS / "python-debugging-001")

    result = HybridRouter().route(task, skills, top_k=3)

    assert result.router == "hybrid"
    assert "systematic-debugging" in result.selected_skill_ids[:2]
