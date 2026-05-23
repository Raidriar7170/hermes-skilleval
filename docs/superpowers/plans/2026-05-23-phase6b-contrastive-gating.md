# Phase 6B Contrastive Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an ambiguity-aware contrastive selective gate that suppresses weak same-category skill candidates exposed by the Phase 6A robustness benchmark.

**Architecture:** Keep the existing gated router's retrieval and reranking path intact. Add a second acceptance-only evidence score for selective routing, wire it through CLI flags, then benchmark contrastive gated MiniLM against the Phase 6A selective gated baseline. The router must not use task gold or negative labels at routing time.

**Tech Stack:** Python 3.11, pytest, argparse CLI, JSONL benchmark artifacts, optional `sentence-transformers` MiniLM backend.

---

## File Structure

- Modify `src/hermes_skilleval/routers/gated.py`
  - Add contrastive gating constructor options.
  - Add pure helpers for prompt evidence and contrastive acceptance.
  - Preserve existing selective behavior when contrastive mode is disabled.
- Modify `src/hermes_skilleval/cli.py`
  - Add `--contrastive-selective`, `--contrastive-margin`, and `--min-evidence`.
  - Pass those values into `VerificationGatedRouter`.
- Modify `tests/test_gated_router.py`
  - Add unit tests for weak same-category negative suppression.
  - Add unit tests for keeping strong second same-category candidates.
  - Add constructor validation tests.
- Modify `tests/test_cli_smoke.py`
  - Add CLI wiring coverage for the new flags.
- Create `docs/demo/phase6b-contrastive-gating/`
  - Store Phase 6B result artifacts.
- Create `docs/phase6b.md`
  - Explain the algorithm, result, and remaining trade-offs.
- Modify `README.md`, `docs/demo/README.md`, and `docs/resume.md`
  - Add Phase 6B references and resume-ready metrics.
- Modify `docs/superpowers/plans/2026-05-23-phase6b-contrastive-gating.md`
  - Check off tasks as implementation progresses.

## Task 1: Contrastive Router Unit Tests

**Files:**
- Modify: `tests/test_gated_router.py`
- Later modify: `src/hermes_skilleval/routers/gated.py`

- [ ] **Step 1: Write failing tests for same-category contrastive acceptance**

Append these tests above `test_non_selective_gated_router_keeps_requested_candidate_count` in `tests/test_gated_router.py`:

```python
def test_contrastive_selective_filters_same_category_weak_evidence():
    skills = [
        _skill(
            "citation-checking",
            "research",
            "Citation Checking",
            "Verify cited evidence for empirical claims.",
        ),
        _skill(
            "literature-review",
            "research",
            "Literature Review",
            "Compare related papers and organize prior work.",
        ),
    ]
    task = _task(
        "robustness-ambiguous-005",
        "research",
        "Verify that each cited paper actually supports a draft's empirical claims.",
        ["citation-checking"],
        ["literature-review"],
    )
    base_router = StubRouter(
        ["citation-checking", "literature-review"],
        {"citation-checking": 0.9, "literature-review": 0.9},
    )

    result = VerificationGatedRouter(
        base_router=base_router,
        selective=True,
        min_confidence=0.5,
        contrastive_selective=True,
        contrastive_margin=3.0,
        min_evidence=2.0,
    ).route(task, skills, top_k=5)

    assert result.selected_skill_ids == ["citation-checking"]


def test_contrastive_selective_keeps_same_category_candidate_with_strong_evidence():
    skills = [
        _skill(
            "citation-checking",
            "research",
            "Citation Checking",
            "Verify cited evidence and citations for empirical claims.",
        ),
        _skill(
            "literature-review",
            "research",
            "Literature Review",
            "Compare related papers and organize prior work.",
        ),
    ]
    task = _task(
        "research-combined",
        "research",
        "Compare related papers and verify that each citation supports the empirical claims.",
        ["citation-checking", "literature-review"],
        [],
    )
    base_router = StubRouter(
        ["citation-checking", "literature-review"],
        {"citation-checking": 0.9, "literature-review": 0.9},
    )

    result = VerificationGatedRouter(
        base_router=base_router,
        selective=True,
        min_confidence=0.5,
        contrastive_selective=True,
        contrastive_margin=6.0,
        min_evidence=2.0,
    ).route(task, skills, top_k=5)

    assert result.selected_skill_ids == [
        "citation-checking",
        "literature-review",
    ]


def test_gated_router_rejects_invalid_contrastive_thresholds():
    base_router = StubRouter([], {})

    for kwargs in (
        {"contrastive_margin": -0.1},
        {"min_evidence": -0.1},
    ):
        try:
            VerificationGatedRouter(
                base_router=base_router,
                contrastive_selective=True,
                **kwargs,
            )
        except ValueError as error:
            assert "contrastive" in str(error) or "min_evidence" in str(error)
        else:
            raise AssertionError("expected contrastive threshold validation error")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
pytest tests/test_gated_router.py::test_contrastive_selective_filters_same_category_weak_evidence tests/test_gated_router.py::test_contrastive_selective_keeps_same_category_candidate_with_strong_evidence tests/test_gated_router.py::test_gated_router_rejects_invalid_contrastive_thresholds -q
```

Expected: FAIL because `VerificationGatedRouter.__init__()` does not accept `contrastive_selective`, `contrastive_margin`, or `min_evidence`.

- [ ] **Step 3: Add router constructor options and validation**

In `src/hermes_skilleval/routers/gated.py`, update `VerificationGatedRouter.__init__`:

```python
    def __init__(
        self,
        base_router: SkillRouter | None = None,
        candidate_pool_size: int = 10,
        selective: bool = False,
        min_confidence: float = 0.5,
        contrastive_selective: bool = False,
        contrastive_margin: float = 6.0,
        min_evidence: float = 2.0,
    ) -> None:
        if candidate_pool_size <= 0:
            raise ValueError("candidate_pool_size must be positive")
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if contrastive_margin < 0.0:
            raise ValueError("contrastive_margin must be non-negative")
        if min_evidence < 0.0:
            raise ValueError("min_evidence must be non-negative")
        self.base_router = base_router or EmbeddingRouter()
        self.candidate_pool_size = candidate_pool_size
        self.selective = selective
        self.min_confidence = min_confidence
        self.contrastive_selective = contrastive_selective
        self.contrastive_margin = contrastive_margin
        self.min_evidence = min_evidence
```

- [ ] **Step 4: Add prompt evidence and candidate acceptance helpers**

In `src/hermes_skilleval/routers/gated.py`, replace the current selective list comprehension:

```python
        if self.selective:
            ranked_candidates = [
                skill
                for skill in ranked_candidates
                if _confidence(scores[skill.id]) >= self.min_confidence
            ]
```

with:

```python
        if self.selective:
            ranked_candidates = _select_candidates(
                task,
                ranked_candidates,
                scores,
                min_confidence=self.min_confidence,
                contrastive_selective=self.contrastive_selective,
                contrastive_margin=self.contrastive_margin,
                min_evidence=self.min_evidence,
            )
```

Add these helpers below `_verification_score`:

```python
def _select_candidates(
    task: BenchmarkTask,
    ranked_candidates: list[Skill],
    scores: dict[str, float],
    *,
    min_confidence: float,
    contrastive_selective: bool,
    contrastive_margin: float,
    min_evidence: float,
) -> list[Skill]:
    accepted: list[Skill] = []
    accepted_evidence: dict[str, float] = {}
    for skill in ranked_candidates:
        if _confidence(scores[skill.id]) < min_confidence:
            continue
        if contrastive_selective and accepted and _same_category(task, skill):
            evidence = _prompt_evidence_score(task, skill)
            same_category_evidence = [
                accepted_evidence[accepted_skill.id]
                for accepted_skill in accepted
                if _same_category(task, accepted_skill)
            ]
            if same_category_evidence:
                best_evidence = max(same_category_evidence)
                if evidence < min_evidence:
                    continue
                if best_evidence - evidence > contrastive_margin:
                    continue
        accepted.append(skill)
        accepted_evidence[skill.id] = _prompt_evidence_score(task, skill)
    return accepted


def _prompt_evidence_score(task: BenchmarkTask, skill: Skill) -> float:
    query_terms = _terms(task.prompt)
    skill_terms = _terms(_skill_text(skill))
    lexical_score = _weighted_overlap(query_terms, skill_terms)
    exact_id_score = 3.0 if _prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return lexical_score + exact_id_score
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```bash
pytest tests/test_gated_router.py::test_contrastive_selective_filters_same_category_weak_evidence tests/test_gated_router.py::test_contrastive_selective_keeps_same_category_candidate_with_strong_evidence tests/test_gated_router.py::test_gated_router_rejects_invalid_contrastive_thresholds -q
```

Expected: PASS.

- [ ] **Step 6: Run existing gated router tests**

Run:

```bash
pytest tests/test_gated_router.py -q
```

Expected: all gated router tests pass.

- [ ] **Step 7: Commit router behavior**

Run:

```bash
git add src/hermes_skilleval/routers/gated.py tests/test_gated_router.py
git commit -m "feat: add contrastive gated selection"
```

## Task 2: CLI Wiring

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing CLI wiring test**

Append this test after `test_cli_eval_gated_router_supports_selective_confidence_filter` in `tests/test_cli_smoke.py`:

```python
def test_cli_eval_gated_router_passes_contrastive_options(tmp_path, monkeypatch):
    from hermes_skilleval.routers.gated import VerificationGatedRouter

    captured = {}
    original_init = VerificationGatedRouter.__init__

    def capture_init(self, *args, **kwargs):
        captured.update(kwargs)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(VerificationGatedRouter, "__init__", capture_init)
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "contrastive-run"

    assert (
        main(
            [
                "index",
                "--skills-path",
                str(FIXTURES / "skills"),
                "--output",
                str(index_path),
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--router",
                "gated",
                "--selective",
                "--contrastive-selective",
                "--contrastive-margin",
                "4.5",
                "--min-evidence",
                "1.5",
                "--gated-pool-size",
                "3",
                "--top-k",
                "3",
                "--output-dir",
                str(run_dir),
            ]
        )
        == 0
    )

    assert captured["selective"] is True
    assert captured["contrastive_selective"] is True
    assert captured["contrastive_margin"] == 4.5
    assert captured["min_evidence"] == 1.5
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_eval_gated_router_passes_contrastive_options -q
```

Expected: FAIL with an argparse error for unrecognized `--contrastive-selective`, `--contrastive-margin`, or `--min-evidence`.

- [ ] **Step 3: Add CLI arguments**

In `src/hermes_skilleval/cli.py`, extend `_add_gated_args`:

```python
    parser.add_argument(
        "--contrastive-selective",
        action="store_true",
        help="apply ambiguity-aware selective gating to same-category candidates",
    )
    parser.add_argument(
        "--contrastive-margin",
        type=float,
        default=6.0,
        help="maximum evidence gap allowed for contrastive same-category acceptance",
    )
    parser.add_argument(
        "--min-evidence",
        type=float,
        default=2.0,
        help="minimum prompt evidence for non-first same-category candidates",
    )
```

- [ ] **Step 4: Pass CLI arguments into the gated router**

In `_gated_router`, update the constructor call:

```python
    return VerificationGatedRouter(
        base_router=_embedding_router(args),
        candidate_pool_size=candidate_pool_size,
        selective=getattr(args, "selective", False),
        min_confidence=getattr(args, "min_confidence", 0.5),
        contrastive_selective=getattr(args, "contrastive_selective", False),
        contrastive_margin=getattr(args, "contrastive_margin", 6.0),
        min_evidence=getattr(args, "min_evidence", 2.0),
    )
```

- [ ] **Step 5: Run CLI wiring test**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_eval_gated_router_passes_contrastive_options -q
```

Expected: PASS.

- [ ] **Step 6: Run relevant CLI smoke tests**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_eval_gated_router_supports_selective_confidence_filter tests/test_cli_smoke.py::test_cli_eval_gated_router_passes_contrastive_options tests/test_cli_smoke.py::test_cli_compare_supports_gated_embedding_backend_specs -q
```

Expected: PASS.

- [ ] **Step 7: Commit CLI wiring**

Run:

```bash
git add src/hermes_skilleval/cli.py tests/test_cli_smoke.py
git commit -m "feat: expose contrastive gated routing"
```

## Task 3: Phase 6B Benchmark Artifacts

**Files:**
- Create: `docs/demo/phase6b-contrastive-gating/`
- Create: `docs/demo/phase6b-contrastive-gating/contrastive-summary.md`
- Modify: generated result files under `docs/demo/phase6b-contrastive-gating/`

- [ ] **Step 1: Index the expanded benchmark skill library**

Run:

```bash
python -m hermes_skilleval.cli index \
  --skills-path benchmarks/skills \
  --output docs/demo/phase6b-contrastive-gating/skills.json
```

Expected: `Indexed 45 skills to docs/demo/phase6b-contrastive-gating/skills.json`.

- [ ] **Step 2: Run MiniLM and standard selective gated baselines**

Run:

```bash
python -m hermes_skilleval.cli compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-selective=gated:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase6b-minilm-cache.json \
  --selective \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase6b-contrastive-gating
```

Expected: `comparison.md` contains rows for `embedding-minilm` and `gated-minilm-selective`.

- [ ] **Step 3: Run contrastive gated evaluation into the same demo directory**

Run:

```bash
python -m hermes_skilleval.cli eval \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --router gated \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase6b-minilm-cache.json \
  --selective \
  --contrastive-selective \
  --contrastive-margin 6.0 \
  --min-evidence 2.0 \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase6b-contrastive-gating/gated-minilm-contrastive
python -m hermes_skilleval.cli report \
  --runs docs/demo/phase6b-contrastive-gating/gated-minilm-contrastive
```

Expected: `gated-minilm-contrastive/results.jsonl` has 80 records and `gated-minilm-contrastive/report.md` exists.

- [ ] **Step 4: Rebuild comparison report with all three result paths**

Run:

```bash
python - <<'PY'
from pathlib import Path
from hermes_skilleval.comparison import write_comparison_report

root = Path("docs/demo/phase6b-contrastive-gating")
write_comparison_report(
    {
        "embedding-minilm": root / "embedding-minilm" / "results.jsonl",
        "gated-minilm-selective": root / "gated-minilm-selective" / "results.jsonl",
        "gated-minilm-contrastive": root / "gated-minilm-contrastive" / "results.jsonl",
    },
    root / "comparison.md",
)
PY
```

Expected: `comparison.md` contains rows for all three routers.

- [ ] **Step 5: Write failure analysis**

Run:

```bash
python -m hermes_skilleval.cli analyze-failures \
  --runs docs/demo/phase6b-contrastive-gating \
  --baseline gated-minilm-selective \
  --candidate gated-minilm-contrastive \
  --output docs/demo/phase6b-contrastive-gating/failure-analysis.md
```

Expected: `failure-analysis.md` contains a Candidate vs Baseline section comparing selective and contrastive gated MiniLM.

- [ ] **Step 6: Generate contrastive summary and assert acceptance criteria**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

ROOT = Path("docs/demo/phase6b-contrastive-gating")
ROUTERS = ["embedding-minilm", "gated-minilm-selective", "gated-minilm-contrastive"]

def read_records(router):
    path = ROOT / router / "results.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

def mean(records, field):
    return sum(float(record[field]) for record in records) / len(records)

def ambiguous(records):
    return [
        record
        for record in records
        if "ambiguous-skill-pair" in record.get("robustness_tags", [])
        and record.get("split") == "test"
    ]

rows = {}
for router in ROUTERS:
    records = read_records(router)
    rows[router] = {
        "tasks": len(records),
        "recall_at_1": mean(records, "recall_at_1"),
        "recall_at_5": mean(records, "recall_at_5"),
        "mrr": mean(records, "mrr"),
        "ndcg_at_5": mean(records, "ndcg_at_5"),
        "negative_hit_rate": mean(records, "negative_hit_rate"),
        "selection_rate_at_5": mean(records, "selection_rate_at_5"),
        "ambiguous_negative_hit_rate": mean(ambiguous(records), "negative_hit_rate"),
        "ambiguous_selection_rate_at_5": mean(ambiguous(records), "selection_rate_at_5"),
    }

baseline = rows["gated-minilm-selective"]
candidate = rows["gated-minilm-contrastive"]
assert candidate["negative_hit_rate"] < baseline["negative_hit_rate"]
assert candidate["ambiguous_negative_hit_rate"] < baseline["ambiguous_negative_hit_rate"]
assert candidate["recall_at_1"] >= baseline["recall_at_1"] - 0.02
assert candidate["recall_at_5"] >= 0.95

lines = [
    "# Phase 6B Contrastive Gating Summary",
    "",
    "## Router Summary",
    "",
    "| Router | Tasks | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 | Ambiguous Negative Hit Rate |",
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
]
for router in ROUTERS:
    row = rows[router]
    lines.append(
        f"| {router} | {row['tasks']} | {row['recall_at_1']:.3f} | "
        f"{row['recall_at_5']:.3f} | {row['mrr']:.3f} | "
        f"{row['ndcg_at_5']:.3f} | {row['negative_hit_rate']:.3f} | "
        f"{row['selection_rate_at_5']:.3f} | "
        f"{row['ambiguous_negative_hit_rate']:.3f} |"
    )
lines.extend(
    [
        "",
        "## Acceptance Check",
        "",
        f"- Full Negative Hit Rate delta: {candidate['negative_hit_rate'] - baseline['negative_hit_rate']:+.3f}",
        f"- Ambiguous Negative Hit Rate delta: {candidate['ambiguous_negative_hit_rate'] - baseline['ambiguous_negative_hit_rate']:+.3f}",
        f"- Recall@1 delta: {candidate['recall_at_1'] - baseline['recall_at_1']:+.3f}",
        f"- Recall@5: {candidate['recall_at_5']:.3f}",
    ]
)
(ROOT / "contrastive-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print((ROOT / "contrastive-summary.md").read_text(encoding="utf-8"))
PY
```

Expected: script exits 0 and writes `contrastive-summary.md`.

- [ ] **Step 7: Commit benchmark artifacts**

Run:

```bash
git add docs/demo/phase6b-contrastive-gating
git commit -m "test: add phase6b contrastive benchmark run"
```

## Task 4: Documentation and Resume Notes

**Files:**
- Create: `docs/phase6b.md`
- Modify: `README.md`
- Modify: `docs/demo/README.md`
- Modify: `docs/resume.md`

- [ ] **Step 1: Create Phase 6B documentation from generated summary**

Run this script after `docs/demo/phase6b-contrastive-gating/contrastive-summary.md` exists:

```bash
python - <<'PY'
from pathlib import Path

summary_path = Path("docs/demo/phase6b-contrastive-gating/contrastive-summary.md")
summary_lines = summary_path.read_text(encoding="utf-8").splitlines()
table_lines = []
inside_table = False
for line in summary_lines:
    if line.startswith("| Router |"):
        inside_table = True
    if inside_table:
        if line.startswith("|"):
            table_lines.append(line)
        elif table_lines:
            break

content = [
    "# Phase 6B: Contrastive Selective Gating",
    "",
    "Phase 6B adds an ambiguity-aware selective gate to the verification-gated MiniLM router. It targets the same-category negative skills exposed by the Phase 6A robustness benchmark without adding training, cross-encoders, or LLM judges.",
    "",
    "## What Changed",
    "",
    "- Added `--contrastive-selective` to gated routing.",
    "- Added `--contrastive-margin` and `--min-evidence` thresholds.",
    "- Kept existing `--selective --min-confidence` behavior backward compatible.",
    "- Added a committed benchmark run in `docs/demo/phase6b-contrastive-gating`.",
    "",
    "## Result",
    "",
    "The committed run compares `embedding-minilm`, `gated-minilm-selective`, and `gated-minilm-contrastive`.",
    "",
    *table_lines,
    "",
    "## Interpretation",
    "",
    "Contrastive selective gating keeps the high-confidence top choice from the Phase 6A gated router, then rejects later same-category candidates when their prompt evidence is too weak relative to the best accepted candidate. This is designed to lower negative-hit rate on ambiguous skill pairs, even when selection rate decreases.",
    "",
    "## Reproduce",
    "",
    "Run the commands in `docs/superpowers/plans/2026-05-23-phase6b-contrastive-gating.md`, Task 3.",
]
Path("docs/phase6b.md").write_text("\n".join(content) + "\n", encoding="utf-8")
PY
```

Expected: `docs/phase6b.md` exists and contains the router table from `contrastive-summary.md`.

- [ ] **Step 2: Update README demo section**

In `README.md`, add a Phase 6B paragraph after the Phase 6A paragraph:

```markdown
Phase 6B adds contrastive selective gating for same-category ambiguous skills at
[`docs/demo/phase6b-contrastive-gating/comparison.md`](docs/demo/phase6b-contrastive-gating/comparison.md)
with notes in [`docs/phase6b.md`](docs/phase6b.md).
```

Also add the Phase 6B reproduction commands after the Phase 6A commands, using the commands from Task 3.

- [ ] **Step 3: Update demo README**

In `docs/demo/README.md`, add artifacts:

```markdown
- `phase6b-contrastive-gating/comparison.md`: Phase 6B comparison for MiniLM,
  selective gated MiniLM, and contrastive gated MiniLM over the 80-task
  robustness benchmark.
- `phase6b-contrastive-gating/contrastive-summary.md`: acceptance-check
  summary for negative-hit, ambiguous-pair, Recall@1, and Recall@5 deltas.
- `phase6b-contrastive-gating/failure-analysis.md`: failure-mode comparison
  between standard selective gating and contrastive selective gating.
```

- [ ] **Step 4: Update resume notes**

In `docs/resume.md`, add a resume bullet after the Phase 6A bullet. Use the generated metrics from `contrastive-summary.md`:

```markdown
- Added contrastive selective gating for ambiguous same-category skills,
  reducing full-benchmark and held-out ambiguous-pair negative-hit rates while
  preserving Recall@1 within the Phase 6B acceptance threshold and keeping
  Recall@5 above 0.95.
```

If the generated metrics are strong and stable, include exact values in this bullet.

- [ ] **Step 5: Run documentation consistency search**

Run:

```bash
rg -n "Phase 6B|phase6b|contrastive|Negative Hit Rate|Recall@5" README.md docs/phase6b.md docs/demo/README.md docs/resume.md
```

Expected: Phase 6B references appear in all four docs.

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md docs/demo/README.md docs/resume.md docs/phase6b.md docs/superpowers/plans/2026-05-23-phase6b-contrastive-gating.md
git commit -m "docs: document phase6b contrastive gating"
```

## Task 5: Final Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-phase6b-contrastive-gating.md`

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Re-run acceptance script**

Run the Python script from Task 3 Step 6 again.

Expected:

- Full Negative Hit Rate is lower for `gated-minilm-contrastive` than `gated-minilm-selective`.
- Ambiguous-pair Negative Hit Rate is lower for `gated-minilm-contrastive`.
- Recall@1 is no more than 0.02 below `gated-minilm-selective`.
- Recall@5 is at least 0.95.

- [ ] **Step 3: Confirm result file counts**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path("docs/demo/phase6b-contrastive-gating")
for router in ("embedding-minilm", "gated-minilm-selective", "gated-minilm-contrastive"):
    records = [
        json.loads(line)
        for line in (root / router / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 80, router
print("phase6b_result_counts=ok")
PY
```

Expected: `phase6b_result_counts=ok`.

- [ ] **Step 4: Check working tree**

Run:

```bash
git status --short
```

Expected: only the plan file may be modified because checkboxes were updated.

- [ ] **Step 5: Mark final plan checkboxes and amend docs commit**

After the final verification passes, check off Task 5 in this plan and amend the docs commit:

```bash
git add docs/superpowers/plans/2026-05-23-phase6b-contrastive-gating.md
git commit --amend --no-edit
```

Expected: the latest commit includes the final checked implementation plan.

## Self-Review

- Spec coverage: router behavior, CLI flags, benchmark artifacts, docs, and acceptance criteria are all mapped to tasks.
- Red-flag scan: no forbidden marker strings or unspecified implementation steps remain.
- Type consistency: the plan consistently uses `contrastive_selective`, `contrastive_margin`, and `min_evidence` for Python names, and `--contrastive-selective`, `--contrastive-margin`, and `--min-evidence` for CLI flags.
