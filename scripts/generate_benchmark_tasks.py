from __future__ import annotations

from pathlib import Path

import yaml


TASKS = [
    ("coding-debugging-001", "coding", "easy", ["systematic-debugging", "test-driven-development"], ["songwriting-and-ai-music"], "A Python test suite is failing after a refactor. Reproduce the failure, identify the root cause, write a regression test, and implement the minimal fix."),
    ("coding-debugging-002", "coding", "medium", ["systematic-debugging"], ["ascii-art"], "A CLI command sometimes exits successfully without writing its expected output file. Diagnose the bug and propose a minimal fix with tests."),
    ("coding-debugging-003", "coding", "medium", ["test-driven-development"], ["songwriting-and-ai-music"], "Add a new parser option to an existing Python package using test-driven development and keep the public API stable."),
    ("coding-debugging-004", "coding", "hard", ["systematic-debugging"], ["creative-ideation"], "A race condition appears in a concurrent worker queue only under load. Design a debugging plan that isolates the timing issue."),
    ("coding-debugging-005", "coding", "easy", ["test-driven-development"], ["baoyu-comic"], "Implement a small pure function and prove its behavior using failing tests first."),
    ("coding-debugging-006", "coding", "medium", ["systematic-debugging"], ["songwriting-and-ai-music"], "A cache invalidation change caused stale results in a web service. Find the failing path and add a regression test."),
    ("coding-debugging-007", "coding", "medium", ["test-driven-development", "systematic-debugging"], ["ascii-art"], "A YAML loader accepts malformed input silently. Define expected behavior, write tests, and fix validation."),
    ("coding-debugging-008", "coding", "hard", ["systematic-debugging"], ["popular-web-designs"], "A model evaluation script produces nondeterministic metrics between identical runs. Investigate sources of randomness and propose fixes."),
    ("coding-debugging-009", "coding", "easy", ["test-driven-development"], ["songwriting-and-ai-music"], "Refactor a utility function while preserving behavior through tests."),
    ("coding-debugging-010", "coding", "medium", ["systematic-debugging"], ["creative-ideation"], "A dependency upgrade broke an import path. Diagnose the compatibility issue and suggest a targeted patch."),
    ("research-writing-001", "research", "easy", ["research-paper-summary"], ["test-driven-development"], "Summarize a machine learning paper with key claims, evidence, limitations, and open questions."),
    ("research-writing-002", "research", "medium", ["literature-review"], ["songwriting-and-ai-music"], "Compare three papers on agent skill learning and identify common evaluation weaknesses."),
    ("research-writing-003", "research", "medium", ["citation-checking"], ["ascii-art"], "Check whether a technical claim is supported by the cited source and flag unsupported statements."),
    ("research-writing-004", "research", "easy", ["academic-writing"], ["macos-computer-use"], "Rewrite an abstract to be clearer, more concise, and more specific about the method and result."),
    ("research-writing-005", "research", "hard", ["literature-review", "citation-checking"], ["songwriting-and-ai-music"], "Build a structured related-work section for agent benchmarks and cite each comparison accurately."),
    ("research-writing-006", "research", "medium", ["research-paper-summary"], ["test-driven-development"], "Extract the dataset, method, metric, and conclusion from a speech recognition paper."),
    ("research-writing-007", "research", "easy", ["academic-writing"], ["ascii-art"], "Turn rough experiment notes into a polished results paragraph without overstating the conclusion."),
    ("research-writing-008", "research", "medium", ["citation-checking"], ["creative-ideation"], "Identify which citations in a draft support empirical claims and which only provide background context."),
    ("data-mlops-001", "data-analysis", "easy", ["data-analysis"], ["songwriting-and-ai-music"], "Analyze a CSV file, compute summary statistics, and explain anomalies in the results."),
    ("data-mlops-002", "mlops", "medium", ["mlflow"], ["ascii-art"], "Compare two model training runs and identify which hyperparameters changed."),
    ("data-mlops-003", "mlops", "medium", ["wandb"], ["baoyu-comic"], "Inspect experiment tracking logs and summarize the best checkpoint by validation metric."),
    ("data-mlops-004", "data-analysis", "medium", ["python-data-analysis"], ["songwriting-and-ai-music"], "Clean a dataset with missing values and produce a reproducible transformation script."),
    ("data-mlops-005", "mlops", "hard", ["docker", "mlflow"], ["creative-ideation"], "Package a model evaluation job in Docker and record metrics in an experiment tracker."),
    ("data-mlops-006", "data-analysis", "easy", ["python-data-analysis"], ["macos-computer-use"], "Create a chart from tabular benchmark results and explain the trend."),
    ("creative-productivity-001", "creative", "easy", ["ascii-art"], ["systematic-debugging"], "Create a small ASCII diagram explaining a three-step workflow."),
    ("creative-productivity-002", "creative", "medium", ["baoyu-comic"], ["mlflow"], "Turn a short technical anecdote into a four-panel comic concept."),
    ("creative-productivity-003", "creative", "easy", ["songwriting-and-ai-music"], ["test-driven-development"], "Write a short chorus for an upbeat song about debugging late at night."),
    ("productivity-001", "productivity", "easy", ["apple-reminders"], ["citation-checking"], "Create a reminder list for preparing a research presentation."),
    ("productivity-002", "productivity", "medium", ["google-calendar"], ["ascii-art"], "Schedule a focused work block and avoid conflicts with existing meetings."),
    ("productivity-003", "productivity", "medium", ["note-taking"], ["docker"], "Turn meeting notes into action items, decisions, and unresolved questions."),
]


def main() -> None:
    root = Path("benchmarks/tasks")
    root.mkdir(parents=True, exist_ok=True)
    for task_id, category, difficulty, gold_skills, negative_skills, prompt in TASKS:
        task_dir = root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        task_yaml = {
            "id": task_id,
            "category": category,
            "difficulty": difficulty,
            "gold_skills": gold_skills,
            "negative_skills": negative_skills,
            "verifier": "skill_selection",
        }
        (task_dir / "task.yaml").write_text(
            yaml.safe_dump(task_yaml, sort_keys=False),
            encoding="utf-8",
        )
        (task_dir / "prompt.md").write_text(prompt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
