# Phase 6A Robustness Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Hermes SkillEval into an 80-task, 45-skill robustness benchmark with dev/test split metadata.

**Architecture:** Extend the benchmark generators and task model metadata, then regenerate committed benchmark directories. Router and metric behavior stays unchanged except result records include split/tag fields for downstream reporting.

**Tech Stack:** Python 3.11, PyYAML, pytest, Markdown/JSONL benchmark artifacts.

---

## Task 1: Task Metadata Model

- [ ] Add failing tests that generated tasks contain `split` and `robustness_tags`.
- [ ] Add optional `split` and `robustness_tags` to `BenchmarkTask`.
- [ ] Update `task_loader.py` to validate optional metadata and default legacy tasks to `dev` and `["legacy"]`.
- [ ] Add split/tag fields to CLI result records.

## Task 2: Expanded Generators

- [ ] Add failing tests for 80 generated tasks and 45 generated skills.
- [ ] Update `generate_benchmark_tasks.py` to write 50 additional robustness tasks.
- [ ] Update `generate_benchmark_skills.py` to write 25 additional skill files.
- [ ] Run both generators to refresh `benchmarks/tasks` and `benchmarks/skills`.

## Task 3: Phase 6A Benchmark Artifact

- [ ] Run indexing for the expanded generated skill library.
- [ ] Run a router comparison into `docs/demo/phase6a-robustness`.
- [ ] Write failure analysis for the expanded benchmark.
- [ ] Write `docs/phase6a.md` and update README/resume notes.

## Task 4: Verification and Commit

- [ ] Run full pytest.
- [ ] Confirm generated counts and split/tag metadata from committed files.
- [ ] Commit Phase 6A.
