from __future__ import annotations

from pathlib import Path
import shutil

import yaml


DEFAULT_TASK_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "tasks"

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

ROBUSTNESS_TASKS = [
    ("agent-workflows-001", "agent", "easy", ["skill-routing"], ["creative-ideation"], "Choose the right skill for a user request that mixes code review, benchmarks, and documentation.", "dev", ["agent-routing", "ambiguous-skill-pair"]),
    ("agent-workflows-002", "agent", "medium", ["verifier-gated-routing"], ["ascii-art"], "Design a verifier gate that rejects unrelated skills before an agent executes a plan.", "dev", ["verification-gate", "negative-suppression"]),
    ("agent-workflows-003", "agent", "medium", ["self-improvement-harness"], ["note-taking"], "Use failed routing records to propose skill metadata patches and rerun evaluation.", "dev", ["self-improvement", "metadata-patching"]),
    ("agent-workflows-004", "agent", "easy", ["tool-planning"], ["songwriting-and-ai-music"], "Plan which tools an agent should call to inspect files, run tests, and summarize results.", "dev", ["tool-use", "planning"]),
    ("agent-workflows-005", "agent", "medium", ["context-management"], ["docker"], "Compress a long debugging conversation into state needed for the next agent turn.", "dev", ["context", "long-context"]),
    ("agent-workflows-006", "agent", "easy", ["prompt-engineering"], ["cuda-profiling"], "Rewrite an agent instruction so it is specific, testable, and avoids ambiguous tool use.", "dev", ["prompting", "instruction-following"]),
    ("agent-workflows-007", "agent", "hard", ["skill-routing", "verifier-gated-routing"], ["popular-web-designs"], "Route a task through a skill selector and add a verification gate for low-confidence candidates.", "dev", ["agent-routing", "verification-gate", "ambiguous-skill-pair"]),
    ("agent-workflows-008", "agent", "hard", ["self-improvement-harness", "error-analysis"], ["baoyu-comic"], "Analyze routing failures and design a self-improvement loop that accepts only non-regressing patches.", "dev", ["self-improvement", "failure-analysis"]),
    ("agent-workflows-009", "agent", "medium", ["tool-planning"], ["apple-reminders"], "Break a local repository investigation into safe file reads, tests, and patch operations.", "dev", ["tool-use", "planning"]),
    ("agent-workflows-010", "agent", "medium", ["context-management"], ["citation-checking"], "Summarize prior commits and remaining risks so a resumed coding agent can continue reliably.", "dev", ["context", "resume-state"]),
    ("agent-workflows-011", "agent", "easy", ["prompt-engineering"], ["literature-review"], "Turn a vague automation request into a precise agent prompt with success criteria.", "dev", ["prompting", "requirements"]),
    ("agent-workflows-012", "agent", "medium", ["verifier-gated-routing"], ["creative-ideation"], "Define pass/fail checks for an agent benchmark before claiming a task is complete.", "dev", ["verification-gate", "evaluation"]),
    ("retrieval-eval-001", "retrieval", "easy", ["vector-search"], ["google-calendar"], "Build an embedding index for skill descriptions and retrieve the nearest candidates.", "dev", ["retrieval", "embedding"]),
    ("retrieval-eval-002", "retrieval", "medium", ["rag"], ["songwriting-and-ai-music"], "Design a retrieval-augmented answer flow that cites retrieved benchmark documentation.", "dev", ["retrieval", "rag"]),
    ("retrieval-eval-003", "retrieval", "medium", ["cross-encoder-reranking"], ["data-analysis"], "Rerank embedding candidates with a cross-encoder to resolve similar skill descriptions.", "dev", ["reranking", "ambiguous-skill-pair"]),
    ("retrieval-eval-004", "retrieval", "hard", ["embedding-finetuning"], ["docker"], "Fine-tune an embedding model on routing failures and evaluate retrieval improvements.", "dev", ["embedding", "finetuning"]),
    ("retrieval-eval-005", "evaluation", "medium", ["dataset-curation"], ["baoyu-comic"], "Curate a held-out routing benchmark with balanced categories and negative labels.", "dev", ["dataset", "heldout-generalization"]),
    ("retrieval-eval-006", "evaluation", "medium", ["llm-judge-evaluation"], ["ascii-art"], "Write an LLM judge rubric for deciding whether a selected skill matches a task.", "dev", ["llm-judge", "evaluation"]),
    ("retrieval-eval-007", "evaluation", "hard", ["evaluation-suite-design"], ["note-taking"], "Design a benchmark suite that reports recall, negative hits, coverage, and split-level robustness.", "dev", ["evaluation", "robustness"]),
    ("retrieval-eval-008", "evaluation", "medium", ["error-analysis"], ["creative-ideation"], "Cluster router failures into top-1 misses, missing gold skills, and negative hits.", "dev", ["failure-analysis", "diagnostics"]),
    ("retrieval-eval-009", "retrieval", "hard", ["rag", "citation-checking"], ["prompt-engineering"], "Answer a literature question using retrieved sources and verify that each citation supports the claim.", "test", ["retrieval", "citation", "heldout-generalization"]),
    ("retrieval-eval-010", "retrieval", "hard", ["vector-search", "cross-encoder-reranking"], ["apple-reminders"], "Retrieve candidate skills with embeddings and rerank them to fix a near-duplicate mismatch.", "test", ["retrieval", "reranking", "heldout-generalization"]),
    ("retrieval-eval-011", "evaluation", "medium", ["dataset-curation", "evaluation-suite-design"], ["macos-computer-use"], "Create a test split for agent skill routing and define metrics that prevent training-set leakage.", "test", ["dataset", "evaluation", "heldout-generalization"]),
    ("retrieval-eval-012", "evaluation", "medium", ["llm-judge-evaluation", "error-analysis"], ["songwriting-and-ai-music"], "Use judge outputs and failure clusters to explain why a router selected the wrong skill.", "test", ["llm-judge", "failure-analysis", "heldout-generalization"]),
    ("multimodal-asr-001", "multimodal", "easy", ["speech-transcription"], ["academic-writing"], "Transcribe a short audio clip and preserve timestamps for downstream review.", "test", ["asr", "heldout-generalization"]),
    ("multimodal-asr-002", "multimodal", "medium", ["asr-evaluation"], ["songwriting-and-ai-music"], "Evaluate ASR output with WER and identify repeated substitution errors.", "test", ["asr", "evaluation", "heldout-generalization"]),
    ("multimodal-asr-003", "multimodal", "medium", ["audio-preprocessing"], ["ascii-art"], "Normalize noisy audio and split it into chunks before transcription.", "test", ["audio", "preprocessing", "heldout-generalization"]),
    ("multimodal-asr-004", "multimodal", "hard", ["multimodal-alignment"], ["docker"], "Align transcript segments with video frames for a multimodal benchmark.", "test", ["multimodal", "alignment", "heldout-generalization"]),
    ("multimodal-asr-005", "multimodal", "easy", ["image-captioning"], ["citation-checking"], "Generate concise captions for UI screenshots in a benchmark report.", "test", ["vision", "captioning", "heldout-generalization"]),
    ("multimodal-asr-006", "multimodal", "hard", ["asr-evaluation", "speech-transcription"], ["google-calendar"], "Transcribe a meeting recording and compute WER against a reference transcript.", "test", ["asr", "evaluation", "heldout-generalization"]),
    ("multimodal-asr-007", "multimodal", "medium", ["audio-preprocessing", "multimodal-alignment"], ["test-driven-development"], "Clean an audio track and align speech spans to slide timestamps.", "test", ["audio", "alignment", "heldout-generalization"]),
    ("multimodal-asr-008", "multimodal", "medium", ["image-captioning", "research-paper-summary"], ["mlflow"], "Caption figures from a paper and summarize the main experimental takeaway.", "test", ["vision", "research", "heldout-generalization"]),
    ("infra-ops-001", "infra", "easy", ["github-actions"], ["baoyu-comic"], "Create a CI workflow that runs pytest for the skill routing harness.", "test", ["ci", "heldout-generalization"]),
    ("infra-ops-002", "infra", "medium", ["python-packaging"], ["note-taking"], "Package the CLI project with optional dependencies for embedding experiments.", "test", ["packaging", "heldout-generalization"]),
    ("infra-ops-003", "infra", "medium", ["model-serving"], ["academic-writing"], "Serve a local embedding model behind a simple inference endpoint.", "test", ["serving", "heldout-generalization"]),
    ("infra-ops-004", "infra", "hard", ["distributed-training"], ["apple-reminders"], "Plan an 8xA100 distributed training job for embedding distillation.", "test", ["distributed-training", "gpu", "heldout-generalization"]),
    ("infra-ops-005", "infra", "hard", ["cuda-profiling"], ["creative-ideation"], "Profile GPU memory and kernel time for a slow reranker training loop.", "test", ["gpu", "profiling", "heldout-generalization"]),
    ("infra-ops-006", "infra", "medium", ["observability"], ["ascii-art"], "Add logs and counters to monitor router latency and accepted-skill counts.", "test", ["observability", "heldout-generalization"]),
    ("infra-ops-007", "infra", "medium", ["github-actions", "python-packaging"], ["songwriting-and-ai-music"], "Publish a Python package only after CI passes tests on multiple versions.", "test", ["ci", "packaging", "heldout-generalization"]),
    ("infra-ops-008", "infra", "hard", ["model-serving", "observability"], ["literature-review"], "Deploy an embedding service and track latency, error rate, and cache hit ratio.", "test", ["serving", "observability", "heldout-generalization"]),
    ("robustness-ambiguous-001", "coding", "medium", ["systematic-debugging"], ["test-driven-development"], "A flaky integration test fails only in CI. Isolate the cause before changing implementation.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-002", "coding", "medium", ["test-driven-development"], ["systematic-debugging"], "Add a new behavior to a parser by writing the failing tests before implementation.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-003", "mlops", "medium", ["mlflow"], ["wandb"], "Log model parameters, artifacts, and evaluation metrics to an MLflow tracking server.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-004", "mlops", "medium", ["wandb"], ["mlflow"], "Inspect W&B charts to identify which checkpoint has the best validation score.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-005", "research", "medium", ["citation-checking"], ["literature-review"], "Verify that each cited paper actually supports a draft's empirical claims.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-006", "research", "medium", ["literature-review"], ["citation-checking"], "Compare related papers and organize their contributions into a coherent prior-work narrative.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-007", "data-analysis", "medium", ["python-data-analysis"], ["data-analysis"], "Write a pandas script that cleans missing values and produces a saved chart.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-008", "data-analysis", "medium", ["data-analysis"], ["python-data-analysis"], "Explain anomalies and summary statistics in a benchmark CSV without writing code.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-009", "agent", "medium", ["skill-routing"], ["tool-planning"], "Select the correct skill for a request before deciding which tools the agent should call.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
    ("robustness-ambiguous-010", "agent", "medium", ["verifier-gated-routing"], ["llm-judge-evaluation"], "Gate selected skills with deterministic checks rather than asking a judge to grade final prose.", "test", ["ambiguous-skill-pair", "heldout-generalization"]),
]


def all_task_specs():
    return [_normalize_task(task) for task in TASKS + ROBUSTNESS_TASKS]


def generate_tasks(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    task_specs = all_task_specs()
    task_ids = {task[0] for task in task_specs}
    for child in root.iterdir():
        if child.is_dir() and child.name not in task_ids:
            shutil.rmtree(child)

    for (
        task_id,
        category,
        difficulty,
        gold_skills,
        negative_skills,
        prompt,
        split,
        robustness_tags,
    ) in task_specs:
        task_dir = root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        task_yaml = {
            "id": task_id,
            "category": category,
            "difficulty": difficulty,
            "gold_skills": gold_skills,
            "negative_skills": negative_skills,
            "verifier": "skill_selection",
            "split": split,
            "robustness_tags": robustness_tags,
        }
        (task_dir / "task.yaml").write_text(
            yaml.safe_dump(task_yaml, sort_keys=False),
            encoding="utf-8",
        )
        (task_dir / "prompt.md").write_text(prompt + "\n", encoding="utf-8")


def main(root: Path | None = None) -> None:
    generate_tasks(root or DEFAULT_TASK_ROOT)


def _normalize_task(task):
    if len(task) == 6:
        task_id, category, difficulty, gold_skills, negative_skills, prompt = task
        return (
            task_id,
            category,
            difficulty,
            gold_skills,
            negative_skills,
            prompt,
            "dev",
            _legacy_tags(task_id, gold_skills),
        )
    return task


def _legacy_tags(task_id: str, gold_skills: list[str]) -> list[str]:
    tags = ["legacy"]
    if len(gold_skills) > 1:
        tags.append("ambiguous-skill-pair")
    if task_id.startswith("coding"):
        tags.append("coding")
    elif task_id.startswith("research"):
        tags.append("research")
    elif task_id.startswith("data"):
        tags.append("data-mlops")
    return tags


if __name__ == "__main__":
    main()
