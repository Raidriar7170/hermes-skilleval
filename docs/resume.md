# Hermes SkillEval Resume Notes

## One-Line Pitch

Built a Python evaluation and release-gate harness for Hermes-style agent skill
routing, turning a self-built skill/task corpus into reproducible router
metrics, blind-validation evidence, and a conservative default-router decision.

## Resume Bullets

- Recommended conservative Router V2 bullet: built a preregistered
  `MODEL_ONLY_PILOT` training/evaluation pipeline across three arms and three
  seeds; preserved a fail-closed `KEEP_BASELINE` decision when the single
  held-out evaluation attempt stopped before inference on an immutable-model
  copy guard. `human_reviewer_count=0`; no SOTA, production, release, or
  blind-v2 claim.

- Built `Hermes SkillEval`, a 419-test Python CLI harness for benchmarking
  Hermes-style agent skill routing over an 80-task / 45-skill self-built corpus,
  with Markdown skill indexing, keyword/hybrid/embedding/gated/cross-encoder
  routers, Recall@K, MRR, NDCG, Negative Hit Rate, JSONL traces, Markdown
  reports, and static dashboard artifacts.
- Added a blind-validation and release-gate flow that compared
  `baseline-minilm` with `finetuned-embedding` on 16 held-out migration tasks,
  detected ranking and negative-skill regressions despite unchanged Recall@5,
  kept `baseline-minilm` as the default via `KEEP_BASELINE`, and reproduced the
  decision through a Phase 18 release manifest.

## Short Resume Version

Hermes SkillEval is an offline agent-skill routing evaluation harness. It
indexes Hermes-style `SKILL.md` libraries, evaluates multiple router families,
tracks both relevance and negative-skill risk, and turns blind-validation
results into a conservative release decision. The current public evidence is
not "fine-tuning won"; it is that blind validation found regressions and the
release gate refused to promote `finetuned-embedding` as the default.

## Interview Talking Points

- **Problem:** Agent systems can accumulate many similar skills. High Recall@K
  alone is not enough if the router also selects tempting but wrong negative
  skills.
- **Architecture:** Skill parser and task loader feed a shared router
  interface; routers emit scored selections; metrics, JSONL traces, Markdown
  reports, dashboards, and release manifests make each run reviewable.
- **Metrics:** Negative Hit Rate is tracked alongside Recall@K, MRR, and
  NDCG@5 because a router that retrieves the gold skill while also accepting a
  harmful negative skill is still risky for agent execution.
- **Phase 14 lesson:** Fine-tuning produced a plausible candidate router and
  useful provenance, but it was not the final proof. A trained artifact still
  needed held-out and blind validation before it could become the default.
- **Phase 16/17 judgment:** Phase 16 blind validation preserved Recall@5 but
  worsened MRR, NDCG@5, Negative Hit Rate, and Negative Accepted Rate. Phase 17
  converted that evidence into `KEEP_BASELINE`, leaving `baseline-minilm` as
  the default and recording `approved_for_default: false` for
  `finetuned-embedding`.
- **Phase 18 reproducibility:** The release-check command reruns the selector
  and public artifact guard, then writes a manifest with artifact hashes so the
  default-router decision can be reproduced locally and in CI shape.
- **Engineering depth:** The project covers offline baselines, optional neural
  retrieval, verifier-gated reranking, cross-encoder reranking, calibration,
  failure analysis, regression guards, static HTML inspection, and public
  wording boundaries.

## Evidence Links

- Phase 16 blind validation:
  [`docs/demo/phase16-blind-validation/comparison.md`](demo/phase16-blind-validation/comparison.md)
- Phase 17 release selector:
  [`docs/demo/phase17-calibrated-release-selector/release-decision.md`](demo/phase17-calibrated-release-selector/release-decision.md)
- Phase 18 reproducibility manifest:
  [`docs/demo/phase18-ci-release-reproducibility/release-manifest.md`](demo/phase18-ci-release-reproducibility/release-manifest.md)
- Release handoff:
  [`docs/release-handoff.md`](release-handoff.md)
- Interview overview:
  [`docs/interview-project-overview.html`](interview-project-overview.html)

## Suggested GitHub Description

Offline CLI benchmark and release-gate harness for evaluating Hermes-style
agent skill routing with negative controls, reproducible reports, and
blind-validation default-router decisions.

## Claims To Avoid

- Present this as a self-built Hermes-style benchmark, not a standard public benchmark.
- Keep the boundary as not a SOTA claim and not production readiness.
- Do not say the fine-tuned router replaced the baseline.
- Do not describe Phase 18 as model-quality proof; it proves the release
  evidence chain is reproducible.

## Future Extension Bullets

- Add an external blind pack to test whether the self-built Hermes-style corpus
  generalizes beyond the current project framing.
- Add calibrated acceptance or rollback logic before reconsidering any
  fine-tuned router as a default.
- Extend offline metadata patch ranking into human-reviewed source
  `SKILL.md` edits.
