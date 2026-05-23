from dataclasses import dataclass
from pathlib import Path
import shutil

import yaml


DEFAULT_SKILL_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "skills"


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    category: str
    name: str
    description: str
    use_cases: tuple[str, ...]


SKILLS = [
    SkillSpec(
        "systematic-debugging",
        "coding",
        "Systematic Debugging",
        "Diagnose failing tests, runtime errors, flaky behavior, and regressions.",
        (
            "Reproduce a failure and isolate the root cause.",
            "Investigate nondeterministic model evaluation metrics.",
            "Debug cache invalidation, import path, or concurrency failures.",
        ),
    ),
    SkillSpec(
        "test-driven-development",
        "coding",
        "Test-Driven Development",
        "Implement behavior by writing failing tests before production code.",
        (
            "Add parser options while keeping public APIs stable.",
            "Refactor utility functions while preserving behavior.",
            "Fix YAML validation or small pure functions with regression tests.",
        ),
    ),
    SkillSpec(
        "research-paper-summary",
        "research",
        "Research Paper Summary",
        "Summarize machine learning papers with claims, methods, metrics, and limits.",
        (
            "Extract dataset, method, metric, and conclusion from speech papers.",
            "Identify evidence, limitations, and open questions.",
        ),
    ),
    SkillSpec(
        "literature-review",
        "research",
        "Literature Review",
        "Compare related papers and organize prior work into a clear research narrative.",
        (
            "Build related-work sections for agent benchmarks.",
            "Compare common evaluation weaknesses across papers.",
        ),
    ),
    SkillSpec(
        "citation-checking",
        "research",
        "Citation Checking",
        "Check whether citations support empirical claims and flag unsupported statements.",
        (
            "Verify cited evidence for technical claims.",
            "Separate empirical support from background references.",
        ),
    ),
    SkillSpec(
        "academic-writing",
        "research",
        "Academic Writing",
        "Rewrite research prose to be clear, concise, precise, and appropriately cautious.",
        (
            "Polish abstracts, results paragraphs, and experiment notes.",
            "Avoid overstating conclusions beyond the evidence.",
        ),
    ),
    SkillSpec(
        "data-analysis",
        "data-analysis",
        "Data Analysis",
        "Analyze tabular data, compute summary statistics, and explain anomalies.",
        (
            "Inspect CSV files and benchmark result tables.",
            "Explain trends, outliers, and aggregate metrics.",
        ),
    ),
    SkillSpec(
        "python-data-analysis",
        "data-analysis",
        "Python Data Analysis",
        "Clean datasets and create reproducible Python transformations and charts.",
        (
            "Handle missing values in dataframes.",
            "Create charts from benchmark results.",
        ),
    ),
    SkillSpec(
        "mlflow",
        "mlops",
        "MLflow",
        "Track, compare, and package machine learning experiment runs with MLflow.",
        (
            "Compare training runs and changed hyperparameters.",
            "Record model evaluation metrics in an experiment tracker.",
        ),
    ),
    SkillSpec(
        "wandb",
        "mlops",
        "Weights and Biases",
        "Inspect W&B experiment tracking logs, checkpoints, and validation metrics.",
        (
            "Summarize the best checkpoint by validation metric.",
            "Review model training logs and experiment dashboards.",
        ),
    ),
    SkillSpec(
        "docker",
        "mlops",
        "Docker",
        "Package applications and model evaluation jobs into reproducible containers.",
        (
            "Build Docker images for benchmark or model jobs.",
            "Capture runtime dependencies for reproducible evaluation.",
        ),
    ),
    SkillSpec(
        "ascii-art",
        "creative",
        "ASCII Art",
        "Create small text diagrams, visual explanations, and terminal-friendly art.",
        (
            "Draw workflow diagrams in plain text.",
            "Represent concepts with compact ASCII visuals.",
        ),
    ),
    SkillSpec(
        "baoyu-comic",
        "creative",
        "Baoyu Comic",
        "Turn technical anecdotes into concise multi-panel comic concepts.",
        (
            "Draft four-panel comic scripts.",
            "Convert product or engineering stories into comic beats.",
        ),
    ),
    SkillSpec(
        "songwriting-and-ai-music",
        "creative",
        "Songwriting and AI Music",
        "Write lyrics, hooks, choruses, melodies, and prompts for AI music tools.",
        (
            "Create an upbeat chorus.",
            "Turn a theme into song lyrics or generation prompts.",
        ),
    ),
    SkillSpec(
        "creative-ideation",
        "creative",
        "Creative Ideation",
        "Generate divergent ideas, concepts, alternatives, and creative directions.",
        (
            "Brainstorm concepts for open-ended creative tasks.",
            "Explore multiple directions before choosing an approach.",
        ),
    ),
    SkillSpec(
        "popular-web-designs",
        "design",
        "Popular Web Designs",
        "Design contemporary web layouts, visual systems, and polished interface patterns.",
        (
            "Create landing page or product UI directions.",
            "Choose typography, layout, and visual hierarchy.",
        ),
    ),
    SkillSpec(
        "macos-computer-use",
        "productivity",
        "macOS Computer Use",
        "Operate macOS applications, windows, files, and desktop workflows.",
        (
            "Use local apps to complete UI tasks.",
            "Navigate system interfaces and desktop automation.",
        ),
    ),
    SkillSpec(
        "apple-reminders",
        "productivity",
        "Apple Reminders",
        "Create, organize, and manage reminder lists for personal tasks.",
        (
            "Prepare reminder lists for presentations.",
            "Track action items and deadlines.",
        ),
    ),
    SkillSpec(
        "google-calendar",
        "productivity",
        "Google Calendar",
        "Schedule meetings, focused work blocks, and calendar events without conflicts.",
        (
            "Find free time and create calendar blocks.",
            "Avoid conflicts with existing meetings.",
        ),
    ),
    SkillSpec(
        "note-taking",
        "productivity",
        "Note Taking",
        "Turn notes into action items, decisions, summaries, and unresolved questions.",
        (
            "Structure meeting notes.",
            "Extract follow-ups and decisions from rough text.",
        ),
    ),
    SkillSpec(
        "skill-routing",
        "agent",
        "Skill Routing",
        "Select the most relevant agent skill for a user request before execution.",
        ("Compare task intent against skill descriptions.", "Resolve near-duplicate skills in a library."),
    ),
    SkillSpec(
        "verifier-gated-routing",
        "agent",
        "Verifier-Gated Routing",
        "Filter or rerank candidate skills using deterministic verification evidence.",
        ("Reject low-confidence skill candidates.", "Gate selected skills before agent execution."),
    ),
    SkillSpec(
        "self-improvement-harness",
        "agent",
        "Self-Improvement Harness",
        "Use failure records to propose, apply, and evaluate skill metadata patches.",
        ("Generate patch proposals from routing misses.", "Accept patches only when metrics do not regress."),
    ),
    SkillSpec(
        "tool-planning",
        "agent",
        "Tool Planning",
        "Plan safe tool calls and execution order for agent workflows.",
        ("Choose file reads, tests, and patch operations.", "Break tasks into verifiable tool steps."),
    ),
    SkillSpec(
        "context-management",
        "agent",
        "Context Management",
        "Compress long interaction history into useful state for future agent turns.",
        ("Summarize prior commits and remaining risks.", "Preserve task state across resumptions."),
    ),
    SkillSpec(
        "prompt-engineering",
        "agent",
        "Prompt Engineering",
        "Rewrite vague instructions into precise, testable agent prompts.",
        ("Clarify success criteria.", "Reduce ambiguity in tool-use instructions."),
    ),
    SkillSpec(
        "vector-search",
        "retrieval",
        "Vector Search",
        "Build and query embedding indexes for semantic retrieval.",
        ("Retrieve nearest skill candidates.", "Compare query embeddings against indexed documents."),
    ),
    SkillSpec(
        "rag",
        "retrieval",
        "Retrieval-Augmented Generation",
        "Answer questions using retrieved context with source-grounded reasoning.",
        ("Retrieve benchmark documentation.", "Cite retrieved evidence in generated answers."),
    ),
    SkillSpec(
        "cross-encoder-reranking",
        "retrieval",
        "Cross-Encoder Reranking",
        "Rerank retrieved candidates with a pairwise neural relevance model.",
        ("Resolve similar skill descriptions.", "Improve top-choice ranking after embedding retrieval."),
    ),
    SkillSpec(
        "embedding-finetuning",
        "retrieval",
        "Embedding Fine-Tuning",
        "Adapt embedding models using labeled retrieval failures and contrastive pairs.",
        ("Fine-tune on routing misses.", "Measure retrieval gains against off-the-shelf embeddings."),
    ),
    SkillSpec(
        "dataset-curation",
        "evaluation",
        "Dataset Curation",
        "Create balanced benchmark datasets with labels, splits, and negative examples.",
        ("Build held-out routing sets.", "Check category balance and label coverage."),
    ),
    SkillSpec(
        "llm-judge-evaluation",
        "evaluation",
        "LLM Judge Evaluation",
        "Design judge rubrics and analyze model-graded evaluation outputs.",
        ("Write skill-match judge rubrics.", "Compare judge outputs with labeled failures."),
    ),
    SkillSpec(
        "evaluation-suite-design",
        "evaluation",
        "Evaluation Suite Design",
        "Design benchmark suites with metrics, splits, and robustness diagnostics.",
        ("Report recall, coverage, and negative hits.", "Prevent training-set leakage."),
    ),
    SkillSpec(
        "error-analysis",
        "evaluation",
        "Error Analysis",
        "Cluster failures and explain model or router error patterns.",
        ("Group top-1 misses and negative hits.", "Summarize candidate-vs-baseline trade-offs."),
    ),
    SkillSpec(
        "speech-transcription",
        "multimodal",
        "Speech Transcription",
        "Transcribe audio into text with timestamps and speaker-aware structure.",
        ("Transcribe meeting recordings.", "Preserve timestamps for review."),
    ),
    SkillSpec(
        "asr-evaluation",
        "multimodal",
        "ASR Evaluation",
        "Evaluate speech recognition output with WER and error diagnostics.",
        ("Compute word error rate.", "Identify substitutions and deletions."),
    ),
    SkillSpec(
        "audio-preprocessing",
        "multimodal",
        "Audio Preprocessing",
        "Clean, normalize, chunk, and prepare audio before transcription.",
        ("Normalize noisy recordings.", "Split long audio into model-friendly chunks."),
    ),
    SkillSpec(
        "multimodal-alignment",
        "multimodal",
        "Multimodal Alignment",
        "Align speech, text, image, or video signals for multimodal benchmarks.",
        ("Align transcript spans with frames.", "Match audio segments to slide timestamps."),
    ),
    SkillSpec(
        "image-captioning",
        "multimodal",
        "Image Captioning",
        "Generate concise descriptions for images, screenshots, and figures.",
        ("Caption UI screenshots.", "Describe figures from research papers."),
    ),
    SkillSpec(
        "github-actions",
        "infra",
        "GitHub Actions",
        "Create CI workflows that run tests and package checks.",
        ("Run pytest on every push.", "Gate package publication on CI success."),
    ),
    SkillSpec(
        "python-packaging",
        "infra",
        "Python Packaging",
        "Package Python projects with optional dependencies and console scripts.",
        ("Configure editable installs.", "Publish CLI packages with extras."),
    ),
    SkillSpec(
        "model-serving",
        "infra",
        "Model Serving",
        "Serve local or remote ML models behind inference endpoints.",
        ("Serve embedding models.", "Track endpoint latency and errors."),
    ),
    SkillSpec(
        "distributed-training",
        "infra",
        "Distributed Training",
        "Plan and run multi-GPU training jobs for model adaptation.",
        ("Use 8xA100 machines efficiently.", "Coordinate data, checkpoints, and launch configs."),
    ),
    SkillSpec(
        "cuda-profiling",
        "infra",
        "CUDA Profiling",
        "Profile GPU memory, kernels, and throughput for ML workloads.",
        ("Find memory bottlenecks.", "Measure slow reranker training kernels."),
    ),
    SkillSpec(
        "observability",
        "infra",
        "Observability",
        "Instrument systems with logs, counters, metrics, and latency traces.",
        ("Monitor router latency.", "Track cache hit rate and accepted-skill counts."),
    ),
]


def generate_skills(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    expected_dirs = {skill.skill_id for skill in SKILLS}
    for child in root.glob("*/*"):
        if child.is_dir() and child.name not in expected_dirs:
            shutil.rmtree(child)

    for skill in SKILLS:
        skill_dir = root / skill.category / skill.skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(_render_skill(skill), encoding="utf-8")


def _render_skill(skill: SkillSpec) -> str:
    metadata = {
        "name": skill.name,
        "description": skill.description,
    }
    lines = [
        "---",
        yaml.safe_dump(metadata, sort_keys=False).strip(),
        "---",
        f"# {skill.name}",
        "",
        skill.description,
        "",
        "## Use Cases",
        "",
    ]
    lines.extend(f"- {use_case}" for use_case in skill.use_cases)
    lines.append("")
    return "\n".join(lines)


def main(root: Path | None = None) -> None:
    generate_skills(root or DEFAULT_SKILL_ROOT)


if __name__ == "__main__":
    main()
