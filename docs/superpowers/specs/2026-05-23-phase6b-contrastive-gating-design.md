# Phase 6B Contrastive Gating Design

## Goal

Phase 6B improves Hermes SkillEval's verification-gated router on the
same-category ambiguous skill pairs exposed by Phase 6A.

The concrete objective is to reduce accepted negative skills on held-out
ambiguous-pair tasks while preserving the top-choice gains from the existing
selective gated MiniLM router.

## Motivation

Phase 6A expanded the benchmark to 80 tasks and 45 skills. The expanded run
showed that selective gated MiniLM is strong overall:

- Recall@1: 0.881
- Recall@5: 0.981
- MRR: 0.985
- Selection Rate@5: 0.715

It also exposed a focused weakness. The gated router gives every same-category
candidate a large category bonus. That suppresses cross-category filler skills,
but it can retain near-neighbor negatives such as:

- `citation-checking` vs `literature-review`
- `mlflow` vs `wandb`
- `systematic-debugging` vs `test-driven-development`
- `skill-routing` vs `tool-planning`

These are useful failures because they look like real agent-skill routing
problems rather than benchmark noise.

## Scope

- Add an ambiguity-aware selective gating mode to the existing gated router.
- Keep the current `gated` router available and backward compatible.
- Add CLI options for enabling and tuning the new mode.
- Add tests for same-category negative suppression and CLI wiring.
- Add a committed Phase 6B demo run under `docs/demo/phase6b-contrastive-gating`.
- Update README, Phase docs, and resume notes with the new result.

## Non-Goals

- No model training or fine-tuning.
- No cross-encoder dependency.
- No LLM judge.
- No benchmark expansion.
- No source `SKILL.md` editing.

## Proposed Approach

Use a contrastive selective gate after reranking.

The existing gated router already computes a verification score for every skill:

```text
category_score + exact_id_score + lexical_score + base_embedding_score
```

Phase 6B adds an additional evidence view used only for selective acceptance:

```text
evidence_score = lexical_overlap(task prompt, skill text) + exact_id_bonus
```

When contrastive gating is enabled, the router still ranks candidates with the
existing verification score. It then accepts candidates as follows:

1. Always evaluate candidates in reranked order.
2. Accept the first candidate if it passes the existing confidence threshold.
3. For later candidates in the same task category, require enough evidence
   relative to the best accepted candidate.
4. Reject same-category candidates whose evidence is much weaker than the best
   accepted evidence, even if their category bonus keeps the total verification
   score high.
5. Keep the existing cross-category confidence filter unchanged.

This keeps the phase deterministic and Mac-friendly. It also directly targets
the Phase 6A failure mode: same-category negatives that receive the same +100
category bonus as the gold skill.

## Configuration

Add these gated-router options:

- `--contrastive-selective`: enable ambiguity-aware acceptance.
- `--contrastive-margin`: maximum allowed evidence gap from the best accepted
  candidate before a same-category candidate is rejected. Default: `6.0`.
- `--min-evidence`: minimum evidence score for accepting non-first
  same-category candidates. Default: `2.0`.

The defaults are conservative. They reduce obvious same-category negative
acceptance without turning the router into a top-1-only system.

## Expected Behavior

For a task whose prompt says:

```text
Verify that each cited paper actually supports a draft's empirical claims.
```

The existing selective gated router can accept both:

- `citation-checking`
- `literature-review`

The contrastive gate keeps `citation-checking` and rejects
`literature-review` if the literature-review evidence is below the configured
margin or minimum evidence threshold.

For genuinely multi-skill tasks where two skills both have prompt evidence, the
gate keeps both. For example, a task that explicitly asks to retrieve sources
and verify citations can still accept both `rag` and `citation-checking`.

## Metrics and Acceptance Criteria

The Phase 6B demo compares:

- `embedding-minilm`
- `gated-minilm-selective`
- `gated-minilm-contrastive`

Acceptance criteria:

- Full benchmark Negative Hit Rate improves versus `gated-minilm-selective`.
- Held-out ambiguous-pair Negative Hit Rate improves versus
  `gated-minilm-selective`.
- Full benchmark Recall@1 is not lower than `gated-minilm-selective` by more
  than 0.02 absolute.
- Full benchmark Recall@5 remains at least 0.95.
- Selection Rate@5 may decrease, because abstaining from weak candidates is the
  purpose of this phase.
- Full `pytest` passes.

## Data Flow

```text
task + skills
    |
    v
base embedding router retrieves candidate pool
    |
    v
existing gated reranker computes verification scores
    |
    v
contrastive selective gate computes prompt evidence
    |
    v
accepted selected_skill_ids + unchanged score traces
    |
    v
JSONL metrics, comparison report, failure analysis
```

## Implementation Notes

- Keep all scoring helpers in `src/hermes_skilleval/routers/gated.py` unless
  the file becomes difficult to follow.
- Add small pure helper functions for evidence scoring and contrastive
  acceptance so unit tests can cover behavior without invoking MiniLM.
- Preserve existing `--selective --min-confidence` behavior when
  `--contrastive-selective` is not enabled.
- Do not use gold or negative labels at routing time.
- Store diagnostic output in existing `scores`; do not change the result schema
  unless tests show a clear need.

## Risks

- Over-filtering may hurt Recall@5 on multi-skill tasks. The acceptance criteria
  allows lower Selection Rate@5 but requires Recall@5 to remain at least 0.95.
- Simple lexical evidence may miss paraphrases. This is acceptable for Phase 6B
  because the phase is a deterministic baseline before cross-encoder or
  fine-tuned embedding work.
- Default thresholds may need one benchmark run to tune. Threshold tuning must
  use aggregate Phase 6A/6B metrics rather than task labels inside the router.

## Validation

- Unit tests demonstrate that contrastive selective gating rejects a
  same-category negative with weak prompt evidence.
- Unit tests demonstrate that it keeps a second same-category candidate when
  evidence is strong enough.
- CLI tests demonstrate the new options are wired into `skilleval eval` and
  `skilleval compare`.
- Demo artifacts show full benchmark and failure-analysis deltas.
- Documentation explains why Phase 6B is an algorithmic improvement over Phase
  6A rather than another benchmark expansion.
