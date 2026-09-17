# Frozen independent validation — review entry

The new offline check is complete; it does **not** establish a usable support policy or repair gain. Keep `native-auto`. Existing Draft PR #48 remains unmerged.

| Boundary | Result |
|---|---|
| New data | 12 cal + 12 check mechanisms, 10 frozen skills each; same three known repositories |
| Labels | Two fresh same-model contexts per split, relative weak labels, no human truth |
| New calibration | Both declared mappings FITTED; both thresholds null / NO_OPERATING_POINT |
| Offline check | 120/120 predictions before labels; 119 known + 1 UNKNOWN |
| Live support eligibility | 0/120; all 12 check environments UNKNOWN at the prediction refresh |
| A-cal minus text-cal Brier | −0.00285; paired 12-mechanism bootstrap interval [−0.03521, +0.02750] |
| C2 intervention | 0 full-K tasks, 12/12 native fallbacks; no accepted rows |
| Real repair comparison | NOT_RUN_WITH_REASON; 0/40 conditional planned calls |
| Utility/default | NO_DEMONSTRATED_GAIN / KEEP_NATIVE |

Read the [one-page Chinese recap](recap.zh.md), [method and independence limits](protocol-notes.md), and [actually exercised commands](usage.md). The active [Goal](../../goals/Hermes_PR48_Frozen_Independent_Validation_Codex_Goal.md) remains the authority.

## Main check table, relative to weak labels

Probability metrics use all 119 scored known rows; each of 12 mechanisms has equal weight after the known mask. They include readable inputs whose support qualification failed. This is not a ready-environment-only estimate. AUC below is macro over 12 defined mechanism AUCs.

| Method | Brier ↓ | Log loss ↓ | Group macro AUC ↑ |
|---|---:|---:|---:|
| A | 0.10440 | 0.34155 | 0.91609 |
| A_calibrated | 0.07932 | 0.25513 | 0.91609 |
| cheap_text | 0.10521 | 0.60316 | 0.90046 |
| cheap_text_calibrated | 0.08218 | 0.26983 | 0.90046 |
| frozen | 0.13111 | 0.40966 | 0.89244 |
| global_prior | 0.18100 | 0.55212 | 0.50000 |
| skill_only | 0.12009 | 0.61642 | 0.87285 |
| skill_prior | 0.11628 | 0.41616 | 0.90121 |

J predicts a different joint event: Brier 0.02372, with only **4 positive pairs** among 119 known. J task-specific P@2 is 0.1667 across all 12 tasks, R@2 is 1.0 on only four positive tasks; eight tasks have undefined recall. This does not prove repair utility and does not promote J into C2.

| Actual advisory set | Positive / negative / unknown | Raw known precision | Mechanism-weighted precision | Full K / fallback |
|---|---|---:|---:|---|
| B2 original rank | 10 / 13 / 1 | 0.4348 | 0.4167 | 12 / 0 |
| T2 cheap text | 17 / 7 / 0 | 0.7083 | 0.7083 | 12 / 0 |
| F2 fixed | 4 / 19 / 1 | 0.1739 | 0.1667 | 12 / 0 |
| C2 rank + A filter | 0 / 0 / 0 | null | null | 0 / 12 |

C2 known inapplicability and UNKNOWN fractions among selected items are undefined (zero selections), not evidence of zero risk. C2 pool known coverage and positive recall are zero; precision is null. All 12 B2/F2/T2 sets differ from empty C2, but these are **fallback contrasts**, not 12 successful package interventions. No package was loaded into a repair Agent. Bootstrap pool/C2 precision and C2−B2 precision have 1000/1000 undefined resamples.

## Eligibility and feasibility

All 24 environments passed initial isolated preparation; the 12 cal environments also passed the live scoring refresh. Cal has six structurally eligible contexts / 60 pairs; of these, 58 are known (9 positive, 49 negative). Even an oracle ordering can cover at most 8.5391% of the full known cal weight at precision 0.90, below required 10%. This post-cal bound ignores unknowns and threshold-order restrictions and is optimistic. No threshold is not solely evidence of poor ranking.

At check scoring, all 12 live refreshes returned UNKNOWN because Docker could not resolve the frozen named base reference. Post-label read-only inspection could resolve the bare image SHA, but both named tag/digest references failed; this establishes a reference-resolution problem, not its underlying cause. No recovery, changed eligibility, new prediction, threshold relaxation or post-label rescore was substituted. See the diagnostic below.

Check extraction states are seven usable, two partial and three unavailable; all readable requests still received raw scores. A/J/base inputs have no token truncation; original B2 retains 1024-token semantics and truncates 111/120 rows. The check is a complete **offline text comparison**, with an unsuccessful support-eligibility branch.

The preregistered repair trigger fails independently at calibration: A has no threshold. It also fails check known acceptance/coverage, full-K C2 count and intervention count. Four tasks qualified for narrow base-red/reference-green checks before scoring, but no Agent matrix or fallback smoke ran. Runtime success, package-use effects, patch quality and cost savings remain unmeasured.

## Evidence map

Paths below are repository-relative and contain compact public records, never model weights, Docker layers, credentials or private Agent traces.

- [Protocol](../../../configs/frozen-independent-validation-v1/protocol.json): method/source hashes, original model identities, fixed budgets and trigger.
- [Recruitment](../../../artifacts/frozen-independent-validation-v1/recruitment.json): 181 non-PR candidate records and exclusions; 24 retained. [Tasks](../../../artifacts/frozen-independent-validation-v1/tasks.json), [historical index](../../../artifacts/frozen-independent-validation-v1/previously-seen.json), [source-reference audit](../../../artifacts/frozen-independent-validation-v1/historical-scan.json).
- [Environment preparation](../../../artifacts/frozen-independent-validation-v1/environment-facts.json), [post-check diagnostic](../../../artifacts/frozen-independent-validation-v1/environment-postcheck-diagnostic.json), [repair qualification](../../../artifacts/frozen-independent-validation-v1/repair-qualification.json).
- [Cal raw scores](../../../artifacts/frozen-independent-validation-v1/cal-scores.json), [policy/curves](../../../artifacts/frozen-independent-validation-v1/policy-lock.json), [cal feasibility](../../../artifacts/frozen-independent-validation-v1/cal-feasibility-analysis.json).
- [Locked check predictions](../../../artifacts/frozen-independent-validation-v1/check-scores.json), [separate prediction lock](../../../artifacts/frozen-independent-validation-v1/check-scores.lock.json), [check weak labels](../../../artifacts/frozen-independent-validation-v1/check-labels.jsonl). Both original label passes, cal labels and merge provenance sit beside these files.
- [Visibility](../../../artifacts/frozen-independent-validation-v1/visibility.json), [full results](../../../artifacts/frozen-independent-validation-v1/results.json), [zero-model records](../../../artifacts/frozen-independent-validation-v1/records.json), [independent decision reload](../../../artifacts/frozen-independent-validation-v1/decision-reload.json).
- [Post-check descriptive slices](../../../artifacts/frozen-independent-validation-v1/descriptive-slices.json): per-task/repository/skill probability metrics, actual known-mask weights, A/J/text/B2/F2 specific ranking. These are post-hoc diagnosis, not model selection or a new confirmation claim.
- [Measured/unknown costs](../../../artifacts/frozen-independent-validation-v1/cost.json), [installed wheel verification](../../../artifacts/frozen-independent-validation-v1/installed-verification.json), [engineering validation](../../../artifacts/frozen-independent-validation-v1/validation.json), [review disposition](review.md).

## Diagnostic interpretation

Within-skill AUC is defined for only four skills: A values are 1.0 (keyed CSV), 1.0 (full text), 0.8571 (debugging), 1.0 (conversion); constant skill-only is 0.5 on each. Positive counts are only 2/1/5/1. Six other skills contain one class, including verification applicable on all 12 tasks. This suggests request-dependent discrimination in this sample, but the sparse same-model labels cannot establish general task understanding or rule out skill-prior shortcuts. A/J/B2/F2 all recover the four specific positives in top two, while text recovers none; the specific task sample is too small for a stable winner claim.

## Delivery boundary

Local full suite: 1401 passed. Clean installed records: new 120 + historical 40 matched, no heavy model imports, tampered prediction hash rejected. Scope-limited lint/type checks and OpenSpec validation passed; whole-tree Ruff has two inherited unused-import findings, not changed by this study. Exact final commit CI is linked from the PR and final delivery message; local checks do not substitute for it. No merge, ready, archive, release, neural training or default change.
