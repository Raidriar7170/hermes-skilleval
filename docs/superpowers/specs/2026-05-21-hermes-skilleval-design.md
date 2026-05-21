# Hermes SkillEval Design

## Overview

Hermes SkillEval is an independent Python CLI harness for evaluating skill selection in Hermes-style agent skill libraries. The MVP does not modify Hermes Agent and does not require an LLM API key. It reads a skills directory, builds a local skill index, loads benchmark tasks with gold skill labels, runs multiple routing strategies, and generates reproducible metrics reports.

The first version focuses on skill selection evaluation rather than full agent execution. This keeps the system deterministic, testable, and useful as a foundation for later stages such as real Hermes execution, verifier-gated task completion, and self-improving skill patches.

## Goals

- Parse at least 100 skills from a Hermes-compatible `skills/**/SKILL.md` tree.
- Load a curated benchmark set of 30 tasks across coding, research, data analysis, MLOps, creative, and productivity scenarios.
- Compare routing strategies using reproducible metrics.
- Generate JSONL run records and a Markdown report with aggregate metrics and failure cases.
- Keep the MVP offline-first: no required LLM, no required network, no required Hermes installation.

## Non-Goals

- Running Hermes Agent end to end.
- Calling LLM judges or external model APIs.
- Automatically editing or promoting skills.
- Building a web dashboard.
- Training a learned reranker.

These are planned second-stage extensions after the independent routing harness is stable.

## Architecture

The MVP is a standalone Python package named `hermes-skilleval`. It exposes a CLI with three primary commands:

```bash
skilleval index --skills-path /path/to/hermes/skills
skilleval eval --tasks benchmarks/tasks --router hybrid --top-k 5
skilleval report --runs runs/latest
```

Data flow:

```text
Hermes skills/
        |
        v
Skill Indexer  -->  JSON index
        |
        v
Benchmark Tasks  -->  Router  -->  Top-k selected skills
        |                         |
        v                         v
Gold labels / verifier       Metrics logger
        |
        v
Markdown report
```

The indexer treats Hermes skills as an external corpus. The benchmark loader treats tasks as local, versioned test data. Routers consume the same `Skill` and `BenchmarkTask` objects so strategies can be compared without changing evaluation code.

## File Structure

```text
hermes-skilleval/
  pyproject.toml
  README.md
  src/hermes_skilleval/
    __init__.py
    cli.py
    models.py
    skill_parser.py
    skill_index.py
    task_loader.py
    routers/
      __init__.py
      base.py
      keyword.py
      embedding.py
      hybrid.py
    metrics.py
    report.py
    storage.py
  benchmarks/
    tasks/
      example-coding-001/
        task.yaml
        prompt.md
  tests/
    test_skill_parser.py
    test_task_loader.py
    test_keyword_router.py
    test_metrics.py
    fixtures/
      skills/
      tasks/
  docs/
    superpowers/
      specs/
      plans/
```

## Components

### `models.py`

Defines the core dataclasses used throughout the system:

- `Skill`
- `BenchmarkTask`
- `RouteResult`
- `EvalRun`
- `MetricSummary`

Dataclasses are preferred for the MVP to keep dependencies light and object behavior explicit.

### `skill_parser.py`

Recursively scans a skills directory for `SKILL.md` files. It extracts the skill id, display name, category, description, body, trigger terms, and approximate token count. If frontmatter or metadata is missing, it falls back to the directory name and the first meaningful paragraph.

### `skill_index.py`

Builds a local index from parsed skills. The MVP writes a JSON index because it is easy to inspect and simple to test. SQLite can be added after the routing and metrics contracts are stable.

### `task_loader.py`

Loads benchmark tasks from directories containing `task.yaml` and `prompt.md`. It validates required fields and raises path-specific errors for malformed tasks.

### `routers/`

Provides a shared router interface and comparable routing implementations:

- `keyword`: token overlap or BM25-like scoring.
- `embedding`: optional semantic scoring interface, unavailable unless dependencies are installed.
- `hybrid`: combines keyword and embedding scores when embeddings are available; otherwise falls back to keyword plus metadata heuristics.

### `metrics.py`

Computes routing metrics:

- `Recall@k`
- `Precision@k`
- `MRR`
- `NDCG@k`
- `Negative Hit Rate`
- `Coverage`
- Mean and p95 routing latency

### `report.py`

Reads run records and writes a Markdown report. Reports include aggregate metrics, per-category breakdowns, router comparisons, and top failure cases.

### `storage.py`

Handles filesystem layout for generated artifacts:

- `index/skills.json`
- `runs/<timestamp>/results.jsonl`
- `runs/<timestamp>/summary.json`
- `runs/<timestamp>/report.md`

## Data Model

```python
@dataclass
class Skill:
    id: str
    name: str
    path: str
    category: str | None
    description: str
    body: str
    trigger_terms: list[str]
    token_count_estimate: int
```

```python
@dataclass
class BenchmarkTask:
    id: str
    category: str
    difficulty: str
    prompt: str
    gold_skills: list[str]
    negative_skills: list[str]
    verifier: str
```

```python
@dataclass
class RouteResult:
    task_id: str
    router: str
    selected_skill_ids: list[str]
    scores: dict[str, float]
    latency_ms: float
```

## Benchmark Task Format

Each benchmark task lives in its own directory:

```text
benchmarks/tasks/python-debugging-001/
  task.yaml
  prompt.md
```

Example `task.yaml`:

```yaml
id: python-debugging-001
category: coding
difficulty: easy
gold_skills:
  - systematic-debugging
  - test-driven-development
negative_skills:
  - songwriting-and-ai-music
  - ascii-art
verifier: skill_selection
```

Example `prompt.md`:

```markdown
A Python test suite is failing after a refactor. Investigate the failure, identify the root cause, write a regression test, and implement the minimal fix.
```

The MVP benchmark contains 30 manually labeled tasks:

- 10 coding/debugging tasks.
- 8 research/writing tasks.
- 6 data analysis or MLOps tasks.
- 6 creative/productivity tasks used as boundary cases and distractors.

Manual labels are the source of truth for the MVP. LLM-assisted label review can be added later, but it must not replace the human-labeled benchmark.

## Metrics

`Recall@k` measures whether top-k results include one or more gold skills.

`Precision@k` measures how many selected top-k skills are gold skills.

`MRR` rewards ranking the first gold skill near the top.

`NDCG@k` handles tasks with multiple gold skills and rewards better ordering.

`Negative Hit Rate` measures how often explicitly wrong skills appear in top-k results.

`Coverage` measures whether the router over-selects a small set of popular skills.

`Latency` records routing time per task and per router.

The report must show both aggregate metrics and failure examples. Averages alone are not enough to understand router behavior.

## Error Handling

If `skills_path` does not exist or is not a directory, the CLI exits with a clear path-specific error.

If no `SKILL.md` files are found, the CLI exits with a message explaining the expected `skills/**/SKILL.md` structure.

If skill metadata is missing, parsing continues using deterministic fallbacks.

If a task is malformed, loading fails with the task path and missing field name.

If a gold skill does not exist in the index, evaluation continues, records a warning, and surfaces the mismatch in the report.

If the embedding router is requested without required dependencies, the CLI exits with an actionable message and suggests running `keyword` or installing the embedding extra.

If report input is missing, the CLI exits with a message telling the user to run `skilleval eval` first.

## Testing Strategy

The MVP is developed test-first.

`test_skill_parser.py` verifies frontmatter parsing, fallback metadata extraction, and recursive skill discovery.

`test_task_loader.py` verifies loading `task.yaml` plus `prompt.md`, missing-field errors, and list parsing for gold and negative skills.

`test_keyword_router.py` verifies that obvious keyword matches rank the expected skill in top-k, latency is recorded, and empty skill indexes fail clearly.

`test_metrics.py` verifies `Recall@k`, `Precision@k`, `MRR`, `NDCG@k`, and `Negative Hit Rate`, including multi-gold tasks.

`test_report.py` verifies Markdown report generation from JSONL run records, including metrics tables and failure cases.

All tests must run without network access, without Hermes installed, and without LLM credentials.

## MVP Acceptance Criteria

- The CLI can parse at least 100 skills from a Hermes-compatible skills directory.
- The repository includes 30 benchmark tasks in the approved task format.
- The CLI supports `index`, `eval`, and `report` commands.
- The evaluation command compares at least `keyword` and `hybrid` routers.
- Evaluation writes JSONL run records.
- Reporting writes a Markdown report.
- Reports include `Recall@1`, `Recall@3`, `Recall@5`, `MRR`, `NDCG@5`, `Negative Hit Rate`, average latency, and top failure cases.
- Unit tests cover parser, task loader, keyword router, metrics, and report generation.
- README includes a copy-paste quickstart.
- The MVP requires no network, no LLM API key, and no Hermes runtime installation.

## Future Extensions

After the MVP is stable, the project can add:

- Hermes CLI execution integration.
- Programmatic task verifiers for real agent outputs.
- LLM-as-judge as a fallback verifier with evidence requirements.
- Trace-based skill patch generation.
- Regression-gated skill promotion and quarantine.
- SQLite FTS and vector indexing.
- Web dashboard.
- Learned reranker or preference-tuned skill router.

