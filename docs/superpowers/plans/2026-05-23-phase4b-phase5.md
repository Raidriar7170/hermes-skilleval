# Phase 4B and Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add selective verification-gated routing, then add an offline failure-driven skill metadata improvement loop.

**Architecture:** Phase 4B extends `VerificationGatedRouter` with optional confidence filtering and adds selective metrics to result records and reports. Phase 5 adds a focused improvement module plus CLI command that proposes metadata patch records and writes a patched skill index for evaluation.

**Tech Stack:** Python 3.11, argparse CLI, JSONL/Markdown artifacts, pytest, optional `sentence-transformers` backend.

---

## File Structure

- Modify `src/hermes_skilleval/routers/gated.py`: add selective filtering and confidence validation.
- Modify `src/hermes_skilleval/metrics.py`: add accepted-count, coverage, selection-rate, abstention, accepted-recall, and negative-accepted helpers.
- Modify `src/hermes_skilleval/cli.py`: add selective CLI flags, write new result fields, and later add `improve-skills`.
- Modify `src/hermes_skilleval/report.py`: display selective metrics when present.
- Modify `src/hermes_skilleval/comparison.py`: aggregate selective metrics with backward-compatible fallbacks.
- Create `src/hermes_skilleval/self_improvement.py`: deterministic patch proposal and patched-index writing.
- Add or modify tests in `tests/test_gated_router.py`, `tests/test_metrics.py`, `tests/test_cli_smoke.py`, `tests/test_report.py`, `tests/test_comparison.py`, and `tests/test_self_improvement.py`.
- Add docs and committed demo outputs under `docs/phase4b.md`, `docs/phase5.md`, `docs/demo/phase4b-selective-routing`, and `docs/demo/phase5-self-improvement`.

## Task 1: Phase 4B Selective Router

- [ ] Add failing tests showing selective `VerificationGatedRouter` suppresses weak cross-category candidates while default mode remains unchanged.
- [ ] Run the targeted router tests and confirm the new tests fail.
- [ ] Implement `selective` and `min_confidence` in `routers/gated.py`.
- [ ] Run targeted router tests and confirm they pass.

## Task 2: Selective Metrics and CLI

- [ ] Add failing metrics tests for `coverage`, `selection_rate_at_5`, `abstention_rate`, `accepted_recall_at_5`, and `negative_accepted_rate`.
- [ ] Add failing CLI smoke test for `compare --routers gated-selective=gated:... --selective --min-confidence 0.5`.
- [ ] Implement metric helpers and write the new fields from `_result_record`.
- [ ] Wire CLI flags into `_gated_router`.
- [ ] Run targeted metrics and CLI tests.

## Task 3: Selective Reports and Benchmark

- [ ] Extend report and comparison output to include selective metrics.
- [ ] Run full pytest.
- [ ] Run a warm-cache Phase 4B comparison into `docs/demo/phase4b-selective-routing`.
- [ ] Write `docs/phase4b.md` and update README/resume notes.
- [ ] Commit Phase 4B.

## Task 4: Phase 5 Self-Improvement Proposal

- [ ] Add failing tests for deterministic patch proposal from failure records.
- [ ] Implement `self_improvement.py` patch proposal and patched-index writer.
- [ ] Add `skilleval improve-skills` CLI command.
- [ ] Run targeted self-improvement and CLI tests.

## Task 5: Phase 5 Evaluation Artifact

- [ ] Run the improvement command on Phase 4B outputs.
- [ ] Evaluate the patched index against the benchmark.
- [ ] Write `docs/phase5.md`, update README/resume notes, and commit Phase 5.
- [ ] Run final full verification and audit the goal requirements.
