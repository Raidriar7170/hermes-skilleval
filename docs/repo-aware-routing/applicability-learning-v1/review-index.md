# Review order and evidence boundary

1. [Results](results.md): layered status, denominators, three result tables, limitations and conditional execution decision.
2. [Data card](data-card.md): public sampling, complete catalog, split/groups, two-context weak labels and provenance.
3. [Model card](model-card.md): actual pointwise objective, base/adapter identity, selection and calibration boundaries.
4. [Usage](usage.md): records-only replay, installed model entrypoint and independent reproduction recipe.
5. [Chinese retrospective](retrospective.md): five conceptual distinctions; not certification of the user's understanding.
6. [Work log](work-log.md): inherited scope, review corrections and actual verification.

Authoritative inputs are under `configs/conditional-applicability-v1/`; evidence is under `artifacts/conditional-applicability-v1/`. Start with `dataset-manifest.json`, `annotation-provenance.json`, `development-identifiability.json`, `model-freeze.json`, `calibration.json`, `results.json`, and `execution-index.json`. `check-score-index.json` names every raw comparison stream. `records-bindings.json` binds the records-only replay inputs; it does not prove semantic label truth or repeat model inference.

Independent review was read-only. Before opening cal/check predictions it examined group weighting, strict public inputs, training/reload, fit-only baselines, frozen scorer identities, calibration/records/runtime agreement and the separate original-rank B2/C2 comparison. Corrections and their limits are preserved in the work log. A code-review pass is not experimental evidence.

Old pilot and r-repair-v1 remain distinct historical sections of Draft PR #48. No merge, release, default-policy promotion, model-weight publication or old-evidence rewrite is authorized by this study's completion.

Final offline evidence review independently recomputed 40 rows with zero model calls, checked all six private checkpoint hashes against the freeze and all six zero-error reload records, and cross-checked the principal metrics/denominators/error cases against the public tables. No material issue was found within that boundary. It did not retrain or re-infer, certify label truth, or pre-certify later push/CI. See [Human Brief](human-brief.md) for the Chinese claim boundary.
