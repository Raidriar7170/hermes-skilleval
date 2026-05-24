# Phase 7A Cross-Encoder Reranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pretrained cross-encoder reranker router, benchmark it against Phase 6B baselines, and document whether learned pairwise verification improves Hermes SkillEval routing.

**Architecture:** Keep embedding retrieval as the first-stage candidate generator. Extract Phase 6B evidence and selective acceptance into a shared verifier helper, then add a `cross-encoder` router that reranks embedding candidates with pairwise model scores and optionally applies the same contrastive acceptance policy. CLI comparison/report/failure-analysis flows remain the benchmark surface.

**Tech Stack:** Python 3.11, pytest, argparse CLI, JSONL/Markdown benchmark artifacts, optional `sentence-transformers` `CrossEncoder`, single-GPU A100 execution via `CUDA_VISIBLE_DEVICES=3`.

---

## File Structure

- Create `src/hermes_skilleval/routers/verification.py`
  - Own shared task/skill text builders, lexical evidence scoring, confidence normalization, and selective contrastive acceptance.
- Modify `src/hermes_skilleval/routers/gated.py`
  - Import shared helpers from `verification.py`.
  - Preserve existing `VerificationGatedRouter` behavior and public constructor.
- Create `src/hermes_skilleval/routers/cross_encoder.py`
  - Add `CrossEncoderModel`, `SentenceTransformerCrossEncoderModel`, `StaticCrossEncoderModel`, and `CrossEncoderReranker`.
- Modify `src/hermes_skilleval/routers/__init__.py`
  - Export the new router class if the package already exposes router symbols.
- Modify `src/hermes_skilleval/cli.py`
  - Add `cross-encoder` router specs and CLI options.
  - Instantiate the new router with embedding retrieval and optional sentence-transformers pairwise scoring.
- Create `tests/test_verification_helpers.py`
  - Verify shared helper parity for contrastive acceptance.
- Create `tests/test_cross_encoder_router.py`
  - Verify candidate pooling, reranking, deterministic ties, selective filtering, and optional dependency behavior without GPU or network.
- Modify `tests/test_gated_router.py`
  - Keep existing gated behavior passing after helper extraction.
- Modify `tests/test_cli_smoke.py`
  - Add CLI smoke tests for `cross-encoder` eval and compare specs.
- Create `docs/phase7a.md`
  - Summarize design, GPU safety, commands, metrics, result interpretation, and resume value.
- Create `docs/demo/phase7a-cross-encoder/`
  - Store benchmark artifacts generated during remote validation.
- Modify `README.md`, `docs/demo/README.md`, and `docs/resume.md`
  - Add Phase 7A references and final project status.
- Modify this plan file as tasks are completed.

## Task 1: Extract Shared Verification Helpers

**Files:**
- Create: `src/hermes_skilleval/routers/verification.py`
- Create: `tests/test_verification_helpers.py`
- Modify: `src/hermes_skilleval/routers/gated.py`
- Test: `tests/test_verification_helpers.py`, `tests/test_gated_router.py`

- [x] **Step 1: Write failing helper tests**

Create `tests/test_verification_helpers.py` with:

```python
from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.routers.verification import (
    confidence,
    prompt_evidence_score,
    select_candidates,
    verification_score,
)


def test_verification_score_prefers_matching_category_and_prompt_terms():
    task = _task(
        "coding-debugging-001",
        "coding",
        "Diagnose a failing pytest suite and isolate the runtime error.",
    )
    relevant = _skill(
        "systematic-debugging",
        "coding",
        "Systematic Debugging",
        "Diagnose failing tests and runtime errors.",
    )
    irrelevant = _skill(
        "songwriting-and-ai-music",
        "creative",
        "Songwriting",
        "Write melodies and lyrics.",
    )

    assert verification_score(task, relevant, 0.1) > verification_score(task, irrelevant, 0.9)


def test_prompt_evidence_uses_prompt_not_category_bonus():
    task = _task(
        "research-claims",
        "research",
        "Verify that each cited paper supports the empirical claims.",
    )
    citation = _skill(
        "citation-checking",
        "research",
        "Citation Checking",
        "Verify cited evidence and empirical claims.",
    )
    literature = _skill(
        "literature-review",
        "research",
        "Literature Review",
        "Compare related papers and organize prior work.",
    )

    assert prompt_evidence_score(task, citation) > prompt_evidence_score(task, literature)


def test_select_candidates_filters_weak_same_category_negative():
    task = _task(
        "robustness-ambiguous-005",
        "research",
        "Verify that each cited paper actually supports a draft's empirical claims.",
    )
    citation = _skill(
        "citation-checking",
        "research",
        "Citation Checking",
        "Verify cited evidence for empirical claims.",
    )
    literature = _skill(
        "literature-review",
        "research",
        "Literature Review",
        "Compare related papers and organize prior work.",
    )

    selected = select_candidates(
        task,
        [citation, literature],
        {"citation-checking": 90.0, "literature-review": 90.0},
        min_confidence=0.5,
        contrastive_selective=True,
        contrastive_margin=3.0,
        min_evidence=2.0,
    )

    assert [skill.id for skill in selected] == ["citation-checking"]


def test_confidence_clamps_to_unit_interval():
    assert confidence(-10.0) == 0.0
    assert confidence(50.0) == 0.5
    assert confidence(120.0) == 1.0


def _skill(skill_id, category, name, description):
    return Skill(
        id=skill_id,
        name=name,
        path=f"/skills/{skill_id}/SKILL.md",
        category=category,
        description=description,
        body=description,
        trigger_terms=description.lower().split(),
        token_count_estimate=8,
    )


def _task(task_id, category, prompt):
    return BenchmarkTask(
        id=task_id,
        category=category,
        difficulty="medium",
        prompt=prompt,
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )
```

- [x] **Step 2: Run helper tests to verify RED**

Run:

```bash
pytest tests/test_verification_helpers.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hermes_skilleval.routers.verification'`.

- [x] **Step 3: Add shared verification implementation**

Create `src/hermes_skilleval/routers/verification.py` with:

```python
from __future__ import annotations

import math
import re
from collections import Counter

from hermes_skilleval.models import BenchmarkTask, Skill


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def verification_score(task: BenchmarkTask, skill: Skill, base_score: float) -> float:
    query_terms = terms(f"{task.category} {task.prompt}")
    skill_terms = terms(skill_text(skill))
    lexical_score = weighted_overlap(query_terms, skill_terms)
    category_score = 100.0 if same_category(task, skill) else 0.0
    exact_id_score = 3.0 if prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return category_score + exact_id_score + lexical_score + base_score


def select_candidates(
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
        if confidence(scores[skill.id]) < min_confidence:
            continue
        if contrastive_selective and accepted and same_category(task, skill):
            evidence = prompt_evidence_score(task, skill)
            same_category_evidence = [
                accepted_evidence[accepted_skill.id]
                for accepted_skill in accepted
                if same_category(task, accepted_skill)
            ]
            if same_category_evidence:
                best_evidence = max(same_category_evidence)
                if evidence < min_evidence:
                    continue
                if best_evidence - evidence > contrastive_margin:
                    continue
        accepted.append(skill)
        accepted_evidence[skill.id] = prompt_evidence_score(task, skill)
    return accepted


def prompt_evidence_score(task: BenchmarkTask, skill: Skill) -> float:
    query_terms = terms(task.prompt)
    skill_terms = terms(skill_text(skill))
    lexical_score = weighted_overlap(query_terms, skill_terms)
    exact_id_score = 3.0 if prompt_mentions_skill_id(task.prompt, skill.id) else 0.0
    return lexical_score + exact_id_score


def confidence(score: float) -> float:
    return max(0.0, min(1.0, score / 100.0))


def task_text(task: BenchmarkTask) -> str:
    return " ".join([task.id.replace("-", " "), task.category, task.prompt])


def skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.id.replace("-", " "),
            skill.name,
            skill.category or "",
            skill.description,
            " ".join(skill.trigger_terms),
            skill.body,
        ]
    )


def terms(text: str) -> Counter[str]:
    return Counter(term.lower() for term in WORD_RE.findall(text) if len(term) >= 3)


def weighted_overlap(
    query_terms: Counter[str],
    skill_terms: Counter[str],
) -> float:
    if not query_terms or not skill_terms:
        return 0.0
    overlap = set(query_terms) & set(skill_terms)
    return sum(
        query_terms[term] * (1.0 + math.log1p(skill_terms[term]))
        for term in sorted(overlap)
    )


def same_category(task: BenchmarkTask, skill: Skill) -> bool:
    return (skill.category or "").casefold() == task.category.casefold()


def prompt_mentions_skill_id(prompt: str, skill_id: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(skill_id)}(?![A-Za-z0-9_-])"
    return re.search(pattern, prompt, flags=re.IGNORECASE) is not None
```

- [x] **Step 4: Refactor gated router to use shared helpers**

In `src/hermes_skilleval/routers/gated.py`, remove local `math`, `re`, `Counter`, `WORD_RE`, `_verification_score`, `_select_candidates`, `_prompt_evidence_score`, `_confidence`, `_terms`, `_weighted_overlap`, `_skill_text`, `_same_category`, and `_prompt_mentions_skill_id`. Add:

```python
from hermes_skilleval.routers.verification import (
    select_candidates,
    verification_score,
)
```

Update score construction:

```python
        scores = {
            skill.id: verification_score(
                task,
                skill,
                float(base_result.scores.get(skill.id, 0.0)),
            )
            for skill in skills
        }
```

Update selective filtering:

```python
            ranked_candidates = select_candidates(
                task,
                ranked_candidates,
                scores,
                min_confidence=self.min_confidence,
                contrastive_selective=self.contrastive_selective,
                contrastive_margin=self.contrastive_margin,
                min_evidence=self.min_evidence,
            )
```

- [x] **Step 5: Run targeted tests**

Run:

```bash
pytest tests/test_verification_helpers.py tests/test_gated_router.py -q
```

Expected: PASS.

- [x] **Step 6: Commit helper extraction**

Run:

```bash
git add src/hermes_skilleval/routers/verification.py src/hermes_skilleval/routers/gated.py tests/test_verification_helpers.py
git commit -m "refactor: share verification gating helpers"
```

## Task 2: Add Cross-Encoder Router

**Files:**
- Create: `src/hermes_skilleval/routers/cross_encoder.py`
- Create: `tests/test_cross_encoder_router.py`
- Test: `tests/test_cross_encoder_router.py`

- [x] **Step 1: Write failing cross-encoder router tests**

Create `tests/test_cross_encoder_router.py` with tests for:

```python
from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.cross_encoder import (
    CrossEncoderReranker,
    SentenceTransformerCrossEncoderModel,
    StaticCrossEncoderModel,
)


class StubRouter(SkillRouter):
    name = "stub"

    def __init__(self, selected_skill_ids, scores):
        self.selected_skill_ids = selected_skill_ids
        self.scores = scores
        self.requested_top_k = None

    def route(self, task, skills, top_k):
        self.requested_top_k = top_k
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=self.selected_skill_ids[:top_k],
            scores=self.scores,
            latency_ms=0.0,
        )


def test_cross_encoder_reranks_embedding_candidates():
    skills = [
        _skill("systematic-debugging", "coding", "Systematic Debugging", "Diagnose runtime failures."),
        _skill("test-driven-development", "coding", "Test-Driven Development", "Preserve behavior through tests."),
        _skill("ascii-art", "creative", "ASCII Art", "Draw terminal art."),
    ]
    task = _task("coding-debugging-001", "coding", "Fix a failing pytest suite by debugging the runtime error.")
    base_router = StubRouter(
        ["test-driven-development", "systematic-debugging", "ascii-art"],
        {"test-driven-development": 0.9, "systematic-debugging": 0.8, "ascii-art": 0.7},
    )
    model = StaticCrossEncoderModel(
        {
            ("coding-debugging-001 coding Fix a failing pytest suite by debugging the runtime error.", "systematic debugging coding diagnose runtime failures diagnose runtime failures"): 4.0,
            ("coding-debugging-001 coding Fix a failing pytest suite by debugging the runtime error.", "test driven development coding preserve behavior through tests preserve behavior through tests"): 2.0,
            ("coding-debugging-001 coding Fix a failing pytest suite by debugging the runtime error.", "ascii art creative draw terminal art draw terminal art"): -1.0,
        }
    )

    result = CrossEncoderReranker(
        base_router=base_router,
        model=model,
        candidate_pool_size=3,
    ).route(task, skills, top_k=2)

    assert result.router == "cross-encoder"
    assert result.selected_skill_ids == ["systematic-debugging", "test-driven-development"]
    assert base_router.requested_top_k == 3
    assert result.scores["systematic-debugging"] > result.scores["test-driven-development"]


def test_cross_encoder_ties_fall_back_to_base_rank_then_skill_id():
    skills = [
        _skill("beta", "coding", "Beta", "Debug tests."),
        _skill("alpha", "coding", "Alpha", "Debug tests."),
    ]
    task = _task("tie", "coding", "Debug tests.")
    base_router = StubRouter(["beta", "alpha"], {"beta": 0.7, "alpha": 0.7})
    model = StaticCrossEncoderModel(default_score=1.0)

    result = CrossEncoderReranker(base_router=base_router, model=model).route(task, skills, top_k=2)

    assert result.selected_skill_ids == ["beta", "alpha"]


def test_cross_encoder_selective_mode_can_abstain_from_weak_candidates():
    skills = [
        _skill("systematic-debugging", "coding", "Systematic Debugging", "Diagnose failing tests."),
        _skill("ascii-art", "creative", "ASCII Art", "Draw terminal art."),
    ]
    task = _task("weak", "coding", "Debug failing tests.")
    base_router = StubRouter(["systematic-debugging", "ascii-art"], {"systematic-debugging": 0.9, "ascii-art": 0.8})
    model = StaticCrossEncoderModel(default_score=0.1)

    result = CrossEncoderReranker(
        base_router=base_router,
        model=model,
        selective=True,
        min_confidence=0.5,
    ).route(task, skills, top_k=5)

    assert result.selected_skill_ids == []


def test_cross_encoder_rejects_invalid_thresholds():
    base_router = StubRouter([], {})
    model = StaticCrossEncoderModel()

    for kwargs in (
        {"candidate_pool_size": 0},
        {"min_confidence": -0.1},
        {"min_confidence": 1.1},
        {"cross_encoder_batch_size": 0},
        {"contrastive_margin": -0.1},
        {"min_evidence": -0.1},
    ):
        try:
            CrossEncoderReranker(base_router=base_router, model=model, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected validation error for {kwargs}")


def test_sentence_transformer_cross_encoder_calls_optional_dependency(monkeypatch):
    calls = []

    class FakeCrossEncoder:
        def __init__(self, model_name):
            calls.append(("init", model_name))

        def predict(self, pairs, batch_size=16):
            calls.append(("predict", list(pairs), batch_size))
            return [3.0, 1.0]

    import sys
    import types

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(CrossEncoder=FakeCrossEncoder))

    model = SentenceTransformerCrossEncoderModel("fake-reranker", batch_size=8)
    scores = model.score_pairs([("task", "skill-a"), ("task", "skill-b")])

    assert scores == [3.0, 1.0]
    assert calls == [
        ("init", "fake-reranker"),
        ("predict", [("task", "skill-a"), ("task", "skill-b")], 8),
    ]


def _skill(skill_id, category, name, description):
    return Skill(
        id=skill_id,
        name=name,
        path=f"/skills/{skill_id}/SKILL.md",
        category=category,
        description=description,
        body=description,
        trigger_terms=description.lower().split(),
        token_count_estimate=8,
    )


def _task(task_id, category, prompt):
    return BenchmarkTask(
        id=task_id,
        category=category,
        difficulty="medium",
        prompt=prompt,
        gold_skills=[],
        negative_skills=[],
        verifier="skill_selection",
    )
```

- [x] **Step 2: Run cross-encoder tests to verify RED**

Run:

```bash
pytest tests/test_cross_encoder_router.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hermes_skilleval.routers.cross_encoder'`.

- [x] **Step 3: Implement cross-encoder model wrappers and router**

Create `src/hermes_skilleval/routers/cross_encoder.py` with a focused implementation:

```python
from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Protocol

from hermes_skilleval.models import BenchmarkTask, RouteResult, Skill
from hermes_skilleval.routers.base import SkillRouter
from hermes_skilleval.routers.embedding import EmbeddingDependencyError, EmbeddingRouter
from hermes_skilleval.routers.verification import (
    select_candidates,
    skill_text,
    task_text,
)


class CrossEncoderModel(Protocol):
    cache_key: str

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[float]:
        raise NotImplementedError


class SentenceTransformerCrossEncoderModel:
    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        if batch_size <= 0:
            raise ValueError("cross_encoder_batch_size must be positive")
        try:
            from sentence_transformers import CrossEncoder
        except (ImportError, ModuleNotFoundError) as exc:
            raise EmbeddingDependencyError(
                "sentence-transformers cross-encoder backend requires optional dependency; "
                'install with: python -m pip install -e ".[embedding]"'
            ) from exc

        self.model_name = model_name
        self.batch_size = batch_size
        self.cache_key = f"sentence-transformers-cross-encoder:{model_name}"
        self.model = CrossEncoder(model_name)

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[float]:
        pair_list = list(pairs)
        scores = self.model.predict(pair_list, batch_size=self.batch_size)
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        return [float(score) for score in scores]


class StaticCrossEncoderModel:
    def __init__(
        self,
        scores: dict[tuple[str, str], float] | None = None,
        default_score: float = 0.0,
    ) -> None:
        self.scores = scores or {}
        self.default_score = default_score
        self.cache_key = "static-cross-encoder"

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[float]:
        return [float(self.scores.get(pair, self.default_score)) for pair in pairs]


class CrossEncoderReranker(SkillRouter):
    name = "cross-encoder"

    def __init__(
        self,
        base_router: SkillRouter | None = None,
        model: CrossEncoderModel | None = None,
        candidate_pool_size: int = 10,
        selective: bool = False,
        min_confidence: float = 0.5,
        contrastive_selective: bool = False,
        contrastive_margin: float = 6.0,
        min_evidence: float = 2.0,
        cross_encoder_batch_size: int = 16,
    ) -> None:
        if candidate_pool_size <= 0:
            raise ValueError("candidate_pool_size must be positive")
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        if contrastive_margin < 0.0:
            raise ValueError("contrastive_margin must be non-negative")
        if min_evidence < 0.0:
            raise ValueError("min_evidence must be non-negative")
        if cross_encoder_batch_size <= 0:
            raise ValueError("cross_encoder_batch_size must be positive")
        self.base_router = base_router or EmbeddingRouter()
        self.model = model or SentenceTransformerCrossEncoderModel(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            batch_size=cross_encoder_batch_size,
        )
        self.candidate_pool_size = candidate_pool_size
        self.selective = selective
        self.min_confidence = min_confidence
        self.contrastive_selective = contrastive_selective
        self.contrastive_margin = contrastive_margin
        self.min_evidence = min_evidence

    def route(self, task: BenchmarkTask, skills: list[Skill], top_k: int) -> RouteResult:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be positive")
        if not skills:
            raise ValueError("skill index is empty")

        started = time.perf_counter()
        candidate_k = min(len(skills), max(top_k, self.candidate_pool_size))
        base_result = self.base_router.route(task, skills, candidate_k)
        skill_by_id = {skill.id: skill for skill in skills}
        candidate_ids = [
            skill_id
            for skill_id in base_result.selected_skill_ids
            if skill_id in skill_by_id
        ]
        if not candidate_ids:
            candidate_ids = [skill.id for skill in skills[:candidate_k]]

        candidates = [skill_by_id[skill_id] for skill_id in candidate_ids]
        query_text = task_text(task)
        pair_scores = self.model.score_pairs(
            (query_text, skill_text(skill)) for skill in candidates
        )
        scores = {skill.id: -1_000_000.0 for skill in skills}
        for skill, score in zip(candidates, pair_scores, strict=True):
            scores[skill.id] = score

        base_rank = {skill_id: index for index, skill_id in enumerate(candidate_ids)}
        ranked_candidates = sorted(
            candidates,
            key=lambda skill: (-scores[skill.id], base_rank[skill.id], skill.id),
        )
        if self.selective:
            ranked_candidates = select_candidates(
                task,
                ranked_candidates,
                scores,
                min_confidence=self.min_confidence,
                contrastive_selective=self.contrastive_selective,
                contrastive_margin=self.contrastive_margin,
                min_evidence=self.min_evidence,
            )

        latency_ms = (time.perf_counter() - started) * 1000
        return RouteResult(
            task_id=task.id,
            router=self.name,
            selected_skill_ids=[skill.id for skill in ranked_candidates[:top_k]],
            scores=scores,
            latency_ms=latency_ms,
        )
```

- [x] **Step 4: Run cross-encoder tests**

Run:

```bash
pytest tests/test_cross_encoder_router.py -q
```

Expected: PASS.

- [x] **Step 5: Commit cross-encoder router**

Run:

```bash
git add src/hermes_skilleval/routers/cross_encoder.py tests/test_cross_encoder_router.py
git commit -m "feat: add cross encoder reranker"
```

## Task 3: Wire Cross-Encoder Router Through CLI

**Files:**
- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_smoke.py`

- [ ] **Step 1: Add failing CLI smoke tests**

Append to `tests/test_cli_smoke.py`:

```python
def test_cli_eval_cross_encoder_router_smoke(tmp_path, monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [
                [1.0, 0.0] if "debug" in sentence.lower() else [0.0, 1.0]
                for sentence in sentences
            ]

    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs, batch_size=16):
            return [
                5.0 if "systematic debugging" in pair[1].lower() else 1.0
                for pair in pairs
            ]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=FakeSentenceTransformer,
            CrossEncoder=FakeCrossEncoder,
        ),
    )
    index_path = tmp_path / "index" / "skills.json"
    run_dir = tmp_path / "cross-encoder-run"

    assert main(["index", "--skills-path", str(FIXTURES / "skills"), "--output", str(index_path)]) == 0
    assert (
        main(
            [
                "eval",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--router",
                "cross-encoder",
                "--embedding-backend",
                "sentence-transformers",
                "--embedding-model",
                "fake-embedding",
                "--cross-encoder-model",
                "fake-reranker",
                "--cross-encoder-batch-size",
                "4",
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

    record = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8"))
    assert record["router"] == "cross-encoder"
    assert len(record["selected_skill_ids"]) <= 3
```

Also add a compare-spec test:

```python
def test_cli_compare_accepts_cross_encoder_router_spec(tmp_path, monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, sentences, normalize_embeddings=True):
            return [[1.0, 0.0] for _ in sentences]

    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs, batch_size=16):
            return [2.0 for _ in pairs]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(
            SentenceTransformer=FakeSentenceTransformer,
            CrossEncoder=FakeCrossEncoder,
        ),
    )
    index_path = tmp_path / "index" / "skills.json"
    output_dir = tmp_path / "comparison"

    assert main(["index", "--skills-path", str(FIXTURES / "skills"), "--output", str(index_path)]) == 0
    assert (
        main(
            [
                "compare",
                "--index",
                str(index_path),
                "--tasks",
                str(FIXTURES / "tasks"),
                "--routers",
                "embedding-fake=embedding:sentence-transformers,cross-fake=cross-encoder:sentence-transformers",
                "--embedding-model",
                "fake-embedding",
                "--cross-encoder-model",
                "fake-reranker",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert (output_dir / "embedding-fake" / "results.jsonl").exists()
    assert (output_dir / "cross-fake" / "results.jsonl").exists()
    assert (output_dir / "comparison.md").exists()
```

- [ ] **Step 2: Run CLI tests to verify RED**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_eval_cross_encoder_router_smoke tests/test_cli_smoke.py::test_cli_compare_accepts_cross_encoder_router_spec -q
```

Expected: FAIL because `cross-encoder` is not an accepted router name.

- [ ] **Step 3: Wire CLI router options**

Modify `src/hermes_skilleval/cli.py`:

```python
from hermes_skilleval.routers.cross_encoder import (
    CrossEncoderReranker,
    SentenceTransformerCrossEncoderModel,
)
```

Update constants:

```python
ROUTER_NAMES = ("keyword", "hybrid", "embedding", "gated", "cross-encoder")
RERANKER_BACKENDS = ("sentence-transformers",)
```

Add parser options after gated args on `eval` and `compare`:

```python
    _add_cross_encoder_args(eval_parser)
```

and:

```python
    _add_cross_encoder_args(compare_parser)
```

Define:

```python
def _add_cross_encoder_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cross-encoder-model",
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        help="sentence-transformers CrossEncoder model name or local path",
    )
    parser.add_argument(
        "--cross-encoder-batch-size",
        type=int,
        default=16,
        help="batch size for cross-encoder pair scoring",
    )
```

Update `_router`:

```python
    if name == "cross-encoder":
        return _cross_encoder_router(args)
```

Add:

```python
def _cross_encoder_router(args: argparse.Namespace | None) -> CrossEncoderReranker:
    model_name = getattr(
        args,
        "cross_encoder_model",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    batch_size = getattr(args, "cross_encoder_batch_size", 16)
    return CrossEncoderReranker(
        base_router=_embedding_router(args),
        model=SentenceTransformerCrossEncoderModel(model_name, batch_size=batch_size),
        candidate_pool_size=getattr(args, "gated_pool_size", 10),
        selective=getattr(args, "selective", False),
        min_confidence=getattr(args, "min_confidence", 0.5),
        contrastive_selective=getattr(args, "contrastive_selective", False),
        contrastive_margin=getattr(args, "contrastive_margin", 6.0),
        min_evidence=getattr(args, "min_evidence", 2.0),
        cross_encoder_batch_size=batch_size,
    )
```

Update `_parse_router_spec` to allow `cross-encoder:sentence-transformers` and reject other cross-encoder backends:

```python
    if embedding_backend is not None:
        if router_name in ("embedding", "gated"):
            if embedding_backend not in EMBEDDING_BACKENDS:
                raise ValueError(f"unknown embedding backend: {embedding_backend}")
        elif router_name == "cross-encoder":
            if embedding_backend not in RERANKER_BACKENDS:
                raise ValueError(f"unknown cross-encoder backend: {embedding_backend}")
        else:
            raise ValueError(
                "only embedding, gated, or cross-encoder router specs can include a backend"
            )
```

The backend label for `cross-encoder` is accepted for compare-label clarity. The actual cross-encoder model is controlled by `--cross-encoder-model`.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli_smoke.py::test_cli_eval_cross_encoder_router_smoke tests/test_cli_smoke.py::test_cli_compare_accepts_cross_encoder_router_spec -q
```

Expected: PASS.

- [ ] **Step 5: Commit CLI wiring**

Run:

```bash
git add src/hermes_skilleval/cli.py tests/test_cli_smoke.py
git commit -m "feat: expose cross encoder routing in cli"
```

## Task 4: Local Verification and Benchmark Artifact Commands

**Files:**
- Modify: `docs/superpowers/plans/2026-05-24-phase7a-cross-encoder-reranker.md`
- Test: full local pytest suite

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: every test passes.

- [ ] **Step 2: Run local fake/CPU smoke command if sentence-transformers is available**

Run:

```bash
skilleval --help
```

Expected: command lists `eval`, `compare`, `report`, `analyze-failures`, `improve-skills`, and `judge-improvement`.

- [ ] **Step 3: Commit checked plan progress**

Run:

```bash
git add docs/superpowers/plans/2026-05-24-phase7a-cross-encoder-reranker.md
git commit -m "docs: track phase7a implementation progress"
```

## Task 5: Remote Single-GPU Benchmark

**Files:**
- Create: `docs/demo/phase7a-cross-encoder/`
- Create: `docs/phase7a.md`
- Modify: `docs/demo/README.md`
- Modify: `docs/resume.md`
- Test: remote `nvidia-smi`, remote `pytest -q`, remote benchmark command, local artifact inspection

- [ ] **Step 1: Check remote GPU availability without modifying processes**

Run:

```bash
ssh volcano 'nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits'
```

Expected: choose one GPU with low memory and utilization. Use GPU `3` if it remains idle.

- [ ] **Step 2: Sync repository to remote workspace**

Run from local repo:

```bash
ssh volcano 'mkdir -p /root/code/hermes-skilleval'
rsync -az --delete \
  --exclude .git \
  --exclude .pytest_cache \
  --exclude __pycache__ \
  ./ volcano:/root/code/hermes-skilleval/
```

Expected: remote workspace contains current source and benchmark files.

- [ ] **Step 3: Install package on remote**

Run:

```bash
ssh volcano 'cd /root/code/hermes-skilleval && python -m pip install -e ".[dev,embedding]"'
```

Expected: install succeeds without changing GPU state.

- [ ] **Step 4: Verify tests remotely**

Run:

```bash
ssh volcano 'cd /root/code/hermes-skilleval && pytest -q'
```

Expected: full test suite passes on the remote Python environment.

- [ ] **Step 5: Run benchmark on one idle GPU**

Run:

```bash
ssh volcano 'cd /root/code/hermes-skilleval && CUDA_VISIBLE_DEVICES=3 skilleval compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-contrastive=gated:sentence-transformers,cross-encoder-minilm=cross-encoder:sentence-transformers \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache docs/demo/phase7a-cross-encoder/embedding-cache.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --selective \
  --contrastive-selective \
  --output-dir docs/demo/phase7a-cross-encoder'
```

Expected: benchmark writes `comparison.md` and router subdirectories without using GPUs other than visible GPU `3`.

- [ ] **Step 6: Generate failure analysis**

Run:

```bash
ssh volcano 'cd /root/code/hermes-skilleval && skilleval analyze-failures \
  --runs docs/demo/phase7a-cross-encoder \
  --baseline gated-minilm-contrastive \
  --candidate cross-encoder-minilm \
  --output docs/demo/phase7a-cross-encoder/failure-analysis.md'
```

Expected: failure analysis markdown is written.

- [ ] **Step 7: Copy remote artifacts back**

Run:

```bash
rsync -az volcano:/root/code/hermes-skilleval/docs/demo/phase7a-cross-encoder/ docs/demo/phase7a-cross-encoder/
```

Expected: local `docs/demo/phase7a-cross-encoder/` contains router results, reports, comparison, failure analysis, and embedding cache.

- [ ] **Step 8: Write Phase 7A summary**

Create `docs/phase7a.md` with:

```markdown
# Phase 7A: Cross-Encoder Reranker

## Goal

Phase 7A adds a pretrained cross-encoder verifier/reranker after embedding retrieval and evaluates it against the Phase 6B contrastive gated baseline.

## Hardware Safety

The remote benchmark used a single A100 selected from an idle GPU check. The run was pinned with `CUDA_VISIBLE_DEVICES=3` and did not kill or reset any existing GPU processes.

## Command

```bash
CUDA_VISIBLE_DEVICES=3 skilleval compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-contrastive=gated:sentence-transformers,cross-encoder-minilm=cross-encoder:sentence-transformers \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache docs/demo/phase7a-cross-encoder/embedding-cache.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --selective \
  --contrastive-selective \
  --output-dir docs/demo/phase7a-cross-encoder
```

## Results

Summarize the metrics from `docs/demo/phase7a-cross-encoder/comparison.md`, including Recall@1, Recall@5, MRR, NDCG@5, negative hit rate, selection rate, and latency.

## Interpretation

State whether the pretrained cross-encoder is a strict improvement, a quality-latency trade-off, or a negative result relative to `gated-minilm-contrastive`.

## Resume Value

This phase demonstrates single-GPU deployment of a learned verifier reranker, controlled GPU selection on shared A100 infrastructure, and evidence-based comparison against lexical, embedding, and contrastive routing baselines.
```

Replace the metric summary with actual values from the generated reports before committing.

- [ ] **Step 9: Update demo and resume docs**

Update `docs/demo/README.md` with a Phase 7A artifact link. Update `docs/resume.md` with Phase 7A as the latest project phase and correct the final test count from the actual `pytest -q` result.

- [ ] **Step 10: Commit benchmark docs and artifacts**

Run:

```bash
git add docs/demo/phase7a-cross-encoder docs/phase7a.md docs/demo/README.md docs/resume.md
git commit -m "docs: add phase7a cross encoder benchmark"
```

## Task 6: Final Verification and Completion Audit

**Files:**
- Inspect: source files, tests, docs, benchmark artifacts

- [ ] **Step 1: Run final local tests**

Run:

```bash
pytest -q
```

Expected: full suite passes.

- [ ] **Step 2: Inspect final git state**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: working tree is clean after committed work, and recent commits include Phase 7A design, plan, implementation, benchmark, and docs.

- [ ] **Step 3: Verify Phase 7A acceptance criteria**

Check:

```bash
test -f src/hermes_skilleval/routers/cross_encoder.py
test -f docs/demo/phase7a-cross-encoder/comparison.md
test -f docs/demo/phase7a-cross-encoder/failure-analysis.md
test -f docs/phase7a.md
rg -n "cross-encoder|Phase 7A|CUDA_VISIBLE_DEVICES=3" docs/phase7a.md docs/resume.md README.md
```

Expected: all files exist and docs mention the cross-encoder reranker and single-GPU safety.

- [ ] **Step 4: Decide if the full project is complete**

Review the active objective and the Phase 7A acceptance criteria. If every required source change, test, remote benchmark, artifact, and resume-ready document is present and verified, mark the active goal complete. If a requirement remains unverified, keep the goal active and continue with the missing work.
