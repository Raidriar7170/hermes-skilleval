from pathlib import Path
import importlib.util

import yaml

from hermes_skilleval.task_loader import load_tasks
from hermes_skilleval.skill_parser import scan_skills


GENERATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_benchmark_tasks.py"
SPEC = importlib.util.spec_from_file_location("generate_benchmark_tasks", GENERATOR_PATH)
assert SPEC is not None
assert SPEC.loader is not None
generate_benchmark_tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_benchmark_tasks)
SKILL_GENERATOR_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "generate_benchmark_skills.py"
)


def test_generation_removes_stale_task_directories(tmp_path):
    stale_dir = tmp_path / "removed-task"
    stale_dir.mkdir()
    (stale_dir / "task.yaml").write_text(
        "id: removed-task\n"
        "category: coding\n"
        "difficulty: easy\n"
        "gold_skills:\n"
        "  - systematic-debugging\n"
        "negative_skills: []\n"
        "verifier: skill_selection\n",
        encoding="utf-8",
    )
    (stale_dir / "prompt.md").write_text("stale prompt\n", encoding="utf-8")
    keep_file = tmp_path / "README.md"
    keep_file.write_text("not a task directory\n", encoding="utf-8")

    generate_benchmark_tasks.main(root=tmp_path)

    assert not stale_dir.exists()
    assert keep_file.exists()
    assert len(list(tmp_path.glob("*/task.yaml"))) == 80


def test_generated_directory_names_match_task_yaml_ids(tmp_path):
    generate_benchmark_tasks.main(root=tmp_path)

    task_dirs = sorted(path for path in tmp_path.iterdir() if path.is_dir())

    assert len(task_dirs) == 80
    for task_dir in task_dirs:
        task_yaml = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        assert task_dir.name == task_yaml["id"]


def test_generated_tasks_load_from_temp_root(tmp_path):
    generate_benchmark_tasks.main(root=tmp_path)

    tasks = load_tasks(tmp_path)

    assert len(tasks) == 80
    assert {task.split for task in tasks} == {"dev", "test"}
    assert all(task.robustness_tags for task in tasks)


def test_generated_tasks_include_split_and_robustness_tags(tmp_path):
    generate_benchmark_tasks.main(root=tmp_path)

    splits = set()
    tags = set()
    for task_yaml_path in tmp_path.glob("*/task.yaml"):
        task_yaml = yaml.safe_load(task_yaml_path.read_text(encoding="utf-8"))
        assert task_yaml["split"] in {"dev", "test"}
        assert isinstance(task_yaml["robustness_tags"], list)
        assert task_yaml["robustness_tags"]
        splits.add(task_yaml["split"])
        tags.update(task_yaml["robustness_tags"])

    assert splits == {"dev", "test"}
    assert "ambiguous-skill-pair" in tags
    assert "heldout-generalization" in tags


def test_default_task_root_is_anchored_to_script_location():
    expected_root = (
        Path(generate_benchmark_tasks.__file__).resolve().parents[1]
        / "benchmarks"
        / "tasks"
    )

    assert generate_benchmark_tasks.DEFAULT_TASK_ROOT == expected_root


def test_generated_benchmark_skills_cover_all_task_labels(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "generate_benchmark_skills",
        SKILL_GENERATOR_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    generate_benchmark_skills = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generate_benchmark_skills)

    generate_benchmark_skills.main(root=tmp_path)

    skills = scan_skills(tmp_path)
    skill_ids = {skill.id for skill in skills}
    task_labels = {
        label
        for _, _, _, gold_skills, negative_skills, _, _, _ in generate_benchmark_tasks.all_task_specs()
        for label in gold_skills + negative_skills
    }

    assert task_labels <= skill_ids
    assert len(skills) == 45
    assert len(skills) == len(generate_benchmark_skills.SKILLS)
    assert "systematic-debugging" in skill_ids
    assert "citation-checking" in skill_ids
