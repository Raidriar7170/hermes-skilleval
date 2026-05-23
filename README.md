# Hermes SkillEval

Hermes SkillEval is an offline CLI harness for evaluating skill routing in
Hermes-style agent skill libraries.

The project indexes `skills/**/SKILL.md`, loads labeled benchmark tasks,
compares routing strategies, and writes JSONL records plus Markdown reports
with deterministic routing metrics and latency metadata. It does not require
Hermes Agent, network access, or an LLM API key.

## Highlights

- Parses Hermes-style skill files with YAML frontmatter, fallback metadata,
  category inference, trigger terms, and token estimates.
- Evaluates keyword and hybrid skill routers with deterministic ranking,
  top-k validation, score traces, and latency tracking.
- Reports Recall@1, Recall@3, Recall@5, Precision@5, MRR, NDCG@5,
  Negative Hit Rate, top selected skills, and failure cases.
- Includes a 30-task benchmark corpus and a reproducible generator that keeps
  the committed benchmark directory in sync with its source list.
- Provides robust CLI error handling, schema validation, Markdown escaping,
  and pytest coverage for parser, loader, router, metrics, report, and CLI
  edge cases.

## Quickstart

Install in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Index a skills directory:

```bash
skilleval index --skills-path /path/to/hermes/skills --output index/skills.json
```

Run an evaluation:

```bash
skilleval eval \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --router hybrid \
  --top-k 5 \
  --output-dir runs/latest
```

Generate a report:

```bash
skilleval report --runs runs/latest
```

Run tests:

```bash
pytest -v
```

## Demo

A committed demo run is available at
[`docs/demo/benchmark-hybrid/report.md`](docs/demo/benchmark-hybrid/report.md).
It was generated with the tiny fixture skill library in `tests/fixtures/skills`
against the 30 built-in benchmark tasks, so it is a smoke/demo artifact rather
than a production routing score.

To regenerate it:

```bash
skilleval index --skills-path tests/fixtures/skills --output docs/demo/skills.json
skilleval eval --index docs/demo/skills.json --tasks benchmarks/tasks --router hybrid --top-k 5 --output-dir docs/demo/benchmark-hybrid
skilleval report --runs docs/demo/benchmark-hybrid
```

## Benchmark Corpus

The built-in benchmark suite lives in `benchmarks/tasks`. Each task directory
contains:

- `task.yaml`: task id, category, difficulty, gold skill labels, negative skill
  labels, and verifier type.
- `prompt.md`: the user request to route.

Regenerate the corpus from its source list:

```bash
python scripts/generate_benchmark_tasks.py
```

## Architecture

```text
skills/**/SKILL.md      benchmarks/tasks
        |                       |
        v                       v
  skill_parser.py        task_loader.py
        |                       |
        +----------+------------+
                   v
             CLI eval command
                   |
       +-----------+-----------+
       v                       v
 keyword router           hybrid router
       |                       |
       +-----------+-----------+
                   v
          metrics + JSONL results
                   |
                   v
             Markdown report
```

Core modules:

- `skill_parser.py`: Hermes-style skill discovery and parsing.
- `task_loader.py`: benchmark task loading and validation.
- `routers/keyword.py`: deterministic lexical baseline.
- `routers/hybrid.py`: offline hybrid router with category and explicit skill-id
  boosts.
- `metrics.py`: ranking metrics and negative-skill checks.
- `report.py`: validated JSONL-to-Markdown reporting.
- `cli.py`: `index`, `eval`, and `report` commands.

## Scope

This MVP evaluates skill selection only. Real Hermes execution, LLM judges,
embedding retrieval, automatic skill patching, and web dashboards are planned
future extensions.

## Portfolio Notes

Resume-ready project framing and interview talking points are in
[`docs/resume.md`](docs/resume.md).
