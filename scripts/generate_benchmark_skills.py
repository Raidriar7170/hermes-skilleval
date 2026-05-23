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
