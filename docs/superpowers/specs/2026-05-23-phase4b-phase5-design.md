# Phase 4B and Phase 5 Design

## Goal

Complete two follow-up stages for Hermes SkillEval:

- Phase 4B: selective verification-gated routing that can return fewer than
  `top_k` skills when verifier confidence is low.
- Phase 5: failure-driven skill metadata improvement with an auditable
  propose/apply/evaluate loop.

## Phase 4B Design

Phase 4B extends the existing `VerificationGatedRouter`. The default behavior
stays unchanged: `gated` still returns up to `top_k` candidates. When
`--selective` is enabled, the router filters reranked candidates by normalized
confidence before selecting the final list.

Confidence is derived from the gated verification score. Same-category skills
receive a large category score in Phase 4A, so `min(score / 100, 1.0)` provides
a deterministic confidence signal that keeps category-supported skills and
suppresses weak cross-category filler candidates. The default selective
threshold is `0.5`.

CLI additions:

- `--selective`: enable confidence filtering for `gated`.
- `--min-confidence`: confidence threshold in `[0.0, 1.0]`.

Metrics additions are written for every result record:

- `accepted_count`: number of returned skills.
- `coverage`: `1.0` when at least one skill is accepted, else `0.0`.
- `selection_rate_at_5`: accepted count divided by 5.
- `abstention_rate`: `1.0` when no skills are accepted, else `0.0`.
- `accepted_recall_at_5`: recall over the accepted list.
- `negative_accepted_rate`: whether any accepted skill is benchmark-negative.

The existing ranking metrics remain unchanged for backward compatibility.

## Phase 5 Design

Phase 5 adds a new offline self-improvement command:

```bash
skilleval improve-skills \
  --runs docs/demo/phase4b-selective-routing \
  --router gated-minilm-selective \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --output docs/demo/phase5-self-improvement/patches.json
```

The command reads failure cases from a router run and proposes metadata-only
patches. It does not change source skill files. Patch proposals include:

- `skill_id`
- `field`
- `before`
- `after`
- `reason`
- `source_task_ids`

The first implementation focuses on deterministic trigger-term and description
patches derived from failure evidence. A companion apply step writes a patched
copy of the skill index, so benchmark runs can compare before and after without
mutating `benchmarks/skills`.

Acceptance is evaluation-gated: a patch set is useful only if rerunning the
benchmark shows no regression in Recall@1, MRR, NDCG@5, and Negative Hit Rate,
while improving at least one targeted failure. The command records accepted or
rejected status in Markdown documentation.

## Non-Goals

- No LLM calls are required.
- No original `SKILL.md` files are modified in Phase 5.
- No benchmark gold or negative labels are used by routers at runtime.
- No remote GPU hardware is required for Phase 4B or the first Phase 5 loop.

## Validation

- Unit tests cover selective filtering and invalid thresholds.
- CLI smoke tests cover `--selective` and `--min-confidence`.
- Metrics/report/comparison tests cover the new selective fields.
- Demo artifacts are committed under:
  - `docs/demo/phase4b-selective-routing`
  - `docs/demo/phase5-self-improvement`
