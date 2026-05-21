from pathlib import Path
import importlib.util

import yaml

from hermes_skilleval.task_loader import load_tasks


GENERATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_benchmark_tasks.py"
SPEC = importlib.util.spec_from_file_location("generate_benchmark_tasks", GENERATOR_PATH)
assert SPEC is not None
assert SPEC.loader is not None
generate_benchmark_tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_benchmark_tasks)


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
    assert len(list(tmp_path.glob("*/task.yaml"))) == 30


def test_generated_directory_names_match_task_yaml_ids(tmp_path):
    generate_benchmark_tasks.main(root=tmp_path)

    task_dirs = sorted(path for path in tmp_path.iterdir() if path.is_dir())

    assert len(task_dirs) == 30
    for task_dir in task_dirs:
        task_yaml = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        assert task_dir.name == task_yaml["id"]


def test_generated_tasks_load_from_temp_root(tmp_path):
    generate_benchmark_tasks.main(root=tmp_path)

    tasks = load_tasks(tmp_path)

    assert len(tasks) == 30


def test_default_task_root_is_anchored_to_script_location():
    expected_root = (
        Path(generate_benchmark_tasks.__file__).resolve().parents[1]
        / "benchmarks"
        / "tasks"
    )

    assert generate_benchmark_tasks.DEFAULT_TASK_ROOT == expected_root
