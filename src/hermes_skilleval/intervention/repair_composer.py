"""Shared retrieval, MMR and non-monotone budgeted public-obligation coverage."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations
import math
import re

from .repair_knowledge import RepairKnowledgeUnit, render_units, token_count


def words(text):
    return re.findall(r"[a-z_][a-z_0-9]+", text.lower())


def lexical(a, b):
    x, y = set(words(a)), set(words(b))
    return len(x & y) / math.sqrt(len(x) * len(y)) if x and y else 0.0


@dataclass(frozen=True)
class Obligation:
    id: str
    statement: str
    source_ref: str
    status: str
    related_symbols: tuple[str, ...]


def extract_obligations(public_state):
    """Verbatim public spans, deterministic, no inferred root cause or hidden test.

    Public failures remain unresolved observations; request spans remain
    unverified. We never promote general test success to obligation support.
    """
    result = []
    failure = public_state.failure_text or ""
    fields = [("request", public_state.request, "unverified")]
    if public_state.public_test_failure_seen and failure:
        fields.insert(0, ("failure_text", failure, "contradicted"))
    for field, text, status in fields:
        # Keep offsets into the exact public State, not an invented paraphrase.
        spans = list(re.finditer(r"[^\n]+", text))
        requirements_start = text.find("## Public requirements\n")
        requirements_end = text.find("## Public interface\n")
        if field == "request" and requirements_start >= 0:
            # Preserve wrapped conditions within a complete requirement bullet.
            bullets = list(
                re.finditer(
                    r"(?m)^[ \t]*[-*]\s+[^\n]*(?:\n(?![ \t]*[-*]\s|\s*$|##)[^\n]+)*",
                    text,
                )
            )
            requirement_bullets = [
                m for m in bullets if requirements_start < m.start() < requirements_end
            ]
            if requirement_bullets:
                spans = requirement_bullets + [
                    m
                    for m in spans
                    if not requirements_start < m.start() < requirements_end
                ]
            spans.sort(
                key=lambda m: (
                    not (requirements_start < m.start() < requirements_end),
                    m.start(),
                )
            )
        if field == "failure_text":
            spans = [
                m
                for m in spans
                if re.search(r"assert|error|failed|exception", m[0], re.I)
            ][-2:]
        for match in spans:
            statement = match[0]
            if len(statement.strip()) < 20 or len(statement) > 1500:
                continue
            explicit_requirement = (
                requirements_start >= 0
                and requirements_start < match.start() < requirements_end
            )
            if (
                field == "request"
                and not explicit_requirement
                and not re.search(
                    r"must|should|when|expect|preserv|return|error|fail|support|invalid|instead|without|cannot|ensure",
                    statement,
                    re.I,
                )
            ):
                continue
            result.append(
                Obligation(
                    f"g{len(result) + 1}",
                    statement,
                    f"{field}:{match.start()}:{match.end()}",
                    status,
                    tuple(sorted(set(re.findall(r"`([\w.]+)`", statement)))),
                )
            )
            if len(result) == 6:
                return result
    return result


class CompleteEncoder:
    """Frozen MiniLM with token chunks averaged over all retained input tokens.

    Avoid the inherited encoder's first-256-only behavior for long units/query.
    No training, and no answer/identity feature enters representation.
    """

    def __init__(self, encoder):
        self.encoder = encoder
        self.cache = {}
        self.encoding_records = {}

    def encode(self, text):
        if text not in self.cache:
            e = self.encoder
            ids = e.tokenizer.encode(text, add_special_tokens=False)
            size = e.max_length - e.tokenizer.num_special_tokens_to_add(False)
            chunks = [ids[i : i + size] for i in range(0, len(ids), size)] or [[]]
            vectors = []
            with e.torch.no_grad():
                for chunk in chunks:
                    # Frozen MiniLM uses BERT CLS/SEP. Construct token IDs directly
                    # so no decode/re-tokenize step loses source bytes and this
                    # works with the installed Transformers 5 tokenizer API.
                    input_ids = e.torch.tensor(
                        [[e.tokenizer.cls_token_id, *chunk, e.tokenizer.sep_token_id]]
                    )
                    tokens = {
                        "input_ids": input_ids,
                        "attention_mask": e.torch.ones_like(input_ids),
                    }
                    states = e.model(**tokens).last_hidden_state
                    mask = tokens["attention_mask"].unsqueeze(-1)
                    vectors.append((states * mask).sum(1)[0] / mask.sum().clamp(min=1))
                weights = e.torch.tensor([max(1, len(c)) for c in chunks])
                mean = (e.torch.stack(vectors) * weights[:, None]).sum(
                    0
                ) / weights.sum()
                self.cache[text] = e.torch.nn.functional.normalize(mean, dim=0)
            self.encoding_records[text] = {
                "input_tokens": len(ids),
                "retained_tokens": len(ids),
                "chunks": len(chunks),
            }
        return self.cache[text]


@dataclass(frozen=True)
class Candidate:
    unit: RepairKnowledgeUnit
    relevance: float
    coverage: tuple[float, ...]
    exposure: float | None
    retrieval: dict


@dataclass(frozen=True)
class CandidatePool:
    candidates: tuple[Candidate, ...]
    overlap: tuple[tuple[float, ...], ...]
    obligations: tuple[Obligation, ...]
    query: str


def _bm25(query, documents):
    tokens = [Counter(words(d)) for d in documents]
    lengths = [sum(t.values()) for t in tokens]
    average = sum(lengths) / max(1, len(tokens)) or 1
    result = [0.0] * len(tokens)
    for word in set(words(query)):
        df = sum(word in t for t in tokens)
        idf = math.log(1 + (len(tokens) - df + 0.5) / (df + 0.5))
        for i, counts in enumerate(tokens):
            tf = counts[word]
            result[i] += (
                idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths[i] / average))
            )
    maximum = max(result, default=0) or 1
    return [v / maximum for v in result]


def retrieve_common(
    public_state,
    obligations,
    units,
    *,
    encoder,
    repository,
    revision,
    visible_text=None,
    limit=24,
):
    units = sorted(
        (
            u
            for u in units
            if u.repository == repository
            and u.source_revision == revision
            and u.version_status != "conflict"
        ),
        key=lambda u: u.unit_id,
    )
    query = "\n".join(
        (
            public_state.request,
            public_state.repo_facts,
            public_state.failure_text or "",
            public_state.source_snippets,
            public_state.diff_summary,
            *[o.statement for o in obligations],
        )
    )
    if not units:
        return CandidatePool((), (), tuple(obligations), query)
    # Facts/conditions only: exclude hashes, IDs and line references from similarity.
    texts = [u.statement for u in units]
    vectors = [encoder.encode(t) for t in texts]
    q = encoder.encode(query)
    g = [encoder.encode(o.statement) for o in obligations]
    bm25 = _bm25(query, texts)

    def cosine(a, b):
        return max(0.0, min(1.0, float(a @ b)))

    rows = []
    for i, u in enumerate(units):
        symbols = " ".join((*u.applies_to, *u.dependencies))
        symbol_match = lexical(query, symbols)
        vector = cosine(q, vectors[i])
        relevance = 0.6 * vector + 0.3 * bm25[i] + 0.1 * symbol_match
        coverage = tuple(
            0.7 * cosine(v, vectors[i]) + 0.3 * lexical(o.statement, u.statement)
            for o, v in zip(obligations, g)
        )
        # Exact visible line overlap measures exposure, not understanding. Missing
        # history is unknown, not a measured zero. Unknown has neutral penalty.
        lines = [
            s.strip()
            for span in u.source_spans
            for s in span.exact_excerpt.splitlines()
            if s.strip()
        ]
        seen = (
            set(s.strip() for s in visible_text.splitlines())
            if visible_text is not None
            else None
        )
        exposure = (
            sum(s in seen for s in lines) / len(lines)
            if seen is not None and lines
            else None
        )
        rows.append(
            Candidate(
                u,
                relevance,
                coverage,
                exposure,
                {"vector": vector, "bm25": bm25[i], "symbol_dependency": symbol_match},
            )
        )
    selected = sorted(
        range(len(rows)), key=lambda i: (-rows[i].relevance, units[i].unit_id)
    )[:limit]
    overlap = tuple(
        tuple(
            0.7 * cosine(vectors[i], vectors[j]) + 0.3 * lexical(texts[i], texts[j])
            for j in selected
        )
        for i in selected
    )
    return CandidatePool(
        tuple(rows[i] for i in selected), overlap, tuple(obligations), query
    )


def objective(pool, indices, *, no_gap=False, no_exposure=False):
    weights = [
        {"contradicted": 2, "unverified": 1, "locally_supported": 0.25}[o.status]
        for o in pool.obligations
    ]
    denom = sum(weights) or 1
    coverage = (
        sum(
            w
            / denom
            * max((pool.candidates[i].coverage[j] for i in indices), default=0)
            for j, w in enumerate(weights)
        )
        if not no_gap
        else 0.0
    )
    relevance = 0.10 * sum(pool.candidates[i].relevance for i in indices)
    redundancy = 0.10 * sum(pool.overlap[i][j] for i, j in combinations(indices, 2))
    exposure = (
        0.05 * sum(pool.candidates[i].exposure or 0 for i in indices)
        if not no_exposure
        else 0.0
    )
    return {
        "coverage": coverage,
        "relevance": relevance,
        "redundancy_penalty": redundancy,
        "exposure_penalty": exposure,
        "total": coverage + relevance - redundancy - exposure,
    }


@dataclass(frozen=True)
class KnowledgePack:
    method: str
    indices: tuple[int, ...]
    units: tuple[RepairKnowledgeUnit, ...]
    tokens: int
    scores: dict
    decisions: tuple[dict, ...]

    def to_dict(self):
        return asdict(self)


def render_pack(pack):
    return render_units(pack.units)


def _tokens(pool, indices, count_tokens):
    return count_tokens(render_units([pool.candidates[i].unit for i in indices]))


def _pack(pool, selected, method, decisions, count_tokens, **terms):
    units = tuple(pool.candidates[i].unit for i in selected)
    return KnowledgePack(
        method,
        tuple(selected),
        units,
        count_tokens(render_units(units)),
        objective(pool, selected, **terms),
        tuple(decisions),
    )


def select_mmr(
    pool,
    public_state=None,
    obligations=None,
    token_budget=1200,
    *,
    count_tokens=token_count,
):
    selected, decisions = [], []
    while len(selected) < 4:
        feasible = [
            i
            for i in range(len(pool.candidates))
            if i not in selected
            and _tokens(pool, selected + [i], count_tokens) <= token_budget
        ]
        if not feasible:
            break

        def score(i):
            return 0.7 * pool.candidates[i].relevance - 0.3 * max(
                (pool.overlap[i][j] for j in selected), default=0
            )

        i = min(feasible, key=lambda i: (-score(i), pool.candidates[i].unit.unit_id))
        if score(i) <= 0:
            break
        decisions.append({"unit_id": pool.candidates[i].unit.unit_id, "mmr": score(i)})
        selected.append(i)
    return _pack(pool, selected, "M", decisions, count_tokens)


def select_gap_cover(
    pool,
    public_state=None,
    obligations=None,
    token_budget=1200,
    *,
    no_gap=False,
    no_exposure=False,
    count_tokens=token_count,
):
    if not pool.obligations:
        baseline = select_mmr(
            pool, token_budget=token_budget, count_tokens=count_tokens
        )
        return KnowledgePack(
            "H-fallback-M",
            baseline.indices,
            baseline.units,
            baseline.tokens,
            baseline.scores,
            baseline.decisions,
        )
    terms = dict(no_gap=no_gap, no_exposure=no_exposure)

    def value(s):
        return objective(pool, s, **terms)["total"]

    selected, decisions = [], []
    while len(selected) < 4:
        feasible = [
            i
            for i in range(len(pool.candidates))
            if i not in selected
            and _tokens(pool, selected + [i], count_tokens) <= token_budget
        ]
        if not feasible:
            break
        base = value(selected)
        marginal = {i: value(selected + [i]) - base for i in feasible}
        ratio = {
            i: marginal[i]
            / max(
                1,
                _tokens(pool, selected + [i], count_tokens)
                - _tokens(pool, selected, count_tokens),
            )
            for i in feasible
        }
        i = min(feasible, key=lambda i: (-ratio[i], pool.candidates[i].unit.unit_id))
        if marginal[i] <= 0:
            break
        candidate = pool.candidates[i]
        decisions.append(
            {
                "unit_id": candidate.unit.unit_id,
                "marginal": marginal[i],
                "per_token": ratio[i],
                "coverage_by_obligation": dict(
                    zip([o.id for o in pool.obligations], candidate.coverage)
                ),
                "visible_exposure": candidate.exposure,
                "version_status": candidate.unit.version_status,
                "overlap_with_selected": {
                    pool.candidates[j].unit.unit_id: pool.overlap[i][j]
                    for j in selected
                },
            }
        )
        selected.append(i)
    singles = [
        i
        for i in range(len(pool.candidates))
        if _tokens(pool, [i], count_tokens) <= token_budget
    ]
    if singles:
        best = min(
            singles, key=lambda i: (-value([i]), pool.candidates[i].unit.unit_id)
        )
        if value([best]) > value(selected):
            selected = [best]
            decisions.append(
                {"best_singleton_replaced_greedy": pool.candidates[best].unit.unit_id}
            )
    method = "H-no-gap" if no_gap else "H-no-exposure" if no_exposure else "H"
    return _pack(pool, selected, method, decisions, count_tokens, **terms)


def exhaustive_optimum(pool, token_budget=1200, *, count_tokens=token_count, **terms):
    if len(pool.candidates) > 12:
        raise ValueError("exhaustive verification is for small pools only")
    best, value = (), 0.0
    for size in range(1, min(4, len(pool.candidates)) + 1):
        for indices in combinations(range(len(pool.candidates)), size):
            score = objective(pool, indices, **terms)["total"]
            if score > value and _tokens(pool, indices, count_tokens) <= token_budget:
                best, value = indices, score
    return {"indices": best, "objective": value}
