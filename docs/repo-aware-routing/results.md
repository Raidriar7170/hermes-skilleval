# Repo-aware cost routing: final pilot results

## Decision

`implementation=COMPLETE` · `training=DATA_SIGNAL_INSUFFICIENT` · `evidence_level=PILOT` · `utility=INCONCLUSIVE` · `deployment_recommendation=KEEP_NATIVE` · `publication=PUSHED_DRAFT_PR`

The implementation, real LoRA training/reload, gate fitting/calibration, replay and product auto path ran. No adaptive routing gain was demonstrated. This is a completed bounded pilot with insufficient learning signal, not a validated full algorithm or promotion. The gate observed zero within-family action-quality contrasts and conservatively returned N. The learned set scorer found no supported set; always-R paid retrieval cost then also returned N. Training loss, successful patches and zero-heavy branches do not establish utility.

[Draft PR48](https://github.com/Raidriar7170/hermes-skilleval/pull/48) inherits PR47 at `e7535896137b7e58fb55de52cc34e94b1afd5ff4`; PR47 is separate. [Method](method.md), [recipe and entry points](usage.md), [one-page retrospective](retrospective.md).

## 1. Rank, context and selection ablations

Two disjoint development families; labels are `model_judged_text`, not execution causal labels. Same 0.6B backbone and candidate pool in each row. Request-only inference reuses the trained checkpoint; there is no separate request-only training run.

| Reranker | Input | Mean Recall@2 | Mean MRR |
|---|---|---:|---:|
| Original | request | 0.00 | 0.292 |
| Original | request + static context | 0.50 | 0.750 |
| LoRA trained | request | 0.00 | 0.292 |
| LoRA trained | request + static context | 0.50 | 0.500 |

[Raw scores, labels, inputs and variants](../../artifacts/repo-aware-routing/training/rank-dev.json). No incremental rank gain from training was observed. Simple byte dedup equals Top2 because the five packages are distinct. Complementarity and budget variants returned empty sets on both families; this does not show a useful set-selection gain. The exact finite-pool optimizer is implemented and checked against exhaustive oracles, but that guarantee concerns its proxy objective only.

Real execution controls: N−, N+, S+ and R+ each succeeded 2/2; learned same-K Top2 succeeded 2/2 on the same development families. [Development](../../artifacts/repo-aware-routing/development/results.json), [equal-K](../../artifacts/repo-aware-routing/development-equal-k/results.json). Same-K results are separated from variable-K budget results. All final R+ runs executed learned scoring and budget search but fell back to N; no successful learned subset intervention is claimed. Native fallback exposes five packages and is outside the R subset K≤4 / 4000 potential-loading-token limit.

## 2. Five-arm final comparison

Four final families, one predeclared execution per arm, shared sourced Agent context. Final gate/config/R identities were sealed before the first launch. S+ retrieval uses request-only text. Values are family-weighted observed means, including the R unknown run in cost denominators. Token totals are input + output; cached input is a subset of input, reasoning is not double-added. Dollar cost is unavailable.

| Arm | Known successes / planned | Unknown | Quality bounds | Mean wall seconds | Mean total tokens |
|---|---:|---:|---:|---:|---:|
| N+ native | 3/4 | 0 | 75–75% | 147.41 | 445,804 |
| F+ fixed two skills | 3/4 | 0 | 75–75% | 180.97 | 607,100 |
| S+ original strong retrieval | 3/4 | 0 | 75–75% | 142.12 | 427,606 |
| R+ always learned retrieval/set | 3/4 | 1 | 75–100% | 158.55 | 447,940 |
| H+ learned pre-retrieval gate | 3/4 | 0 | 75–75% | 185.98 | 653,140 |

[Recomputed rows](../../artifacts/repo-aware-routing/final-test/results.json), [analysis and paired intervals](../../artifacts/repo-aware-routing/final-test/analysis.json), [all launches and artifact bindings](../../artifacts/repo-aware-routing/final-test/index.json).

R's migration-stop-validation patch included a temporary path rejected by the inherited verifier (`illegal patch path: tmpuw09axgl/migrations.py`); independent target/regression outcomes are unavailable. It remains unknown, with the failed reconstruction preserved. It is neither credited as success nor used to label all skills negative. The other arms failed that family's protected checks. No completed execution was rerun or selected away.

H quality ties N/F/S on all four families, and R on three comparable families, with one unknown pair. The quality paired-bootstrap interval degenerates to [0,0] on this tiny sample; it cannot establish equivalence or the predeclared 0.05 noninferiority margin. H−N wall difference is +38.57 seconds (descriptive family-bootstrap 95% interval +6.23 to +82.39), tokens +207,336 (+46,338 to +362,300). These one-run pilot observations show no cost gain, and are not robust latency or population estimates.

**Unseen repository:** csv-diff was absent from training, fitting and calibration. All five arms passed its two final families (2/2 each). H averaged 150.48 seconds / 453,476 tokens versus N 87.79 / 190,353. Two families in one held-out repository do not establish generalization.

## 3. Gate behavior and risk

| Measure | Observed |
|---|---|
| Fit | 12 real N/F/R rows, 4 families; 9 success / 3 failure; 0 unknown |
| Within-family action-quality contrasts | 0/4 families; `INSUFFICIENT` |
| Separate calibration | 6 rows, 2 families; N/F Brier 0.935, R 0.488; probability claim false |
| Final requested H actions | N 4, F 0, R 0 |
| Final H fallbacks | unsupported context 2; insufficient gate signal 2 |
| Actual model predictions recorded | 4/4 |
| Cheap branches with zero constructors / encoder queries / reranker forwards | 4/4 |
| Final R realized actions | N 4/4 after unsupported set; heavy scoring ran |
| Observed H quality losses vs N/F/S | 0/4, insufficient to certify safety |

[Gate model and freeze](../../artifacts/repo-aware-routing/gate/model.json), [fit execution](../../artifacts/repo-aware-routing/gate-fit/results.json), [calibration execution](../../artifacts/repo-aware-routing/gate-calibration/results.json). The gate fits action-conditional quality, elapsed-time and token models; actual fit/normalization/calibration bytes and source recipe hashes are sealed. Zero action contrast forced conservative deployment even though real coefficients were fitted. This is not evidence that the model learned when R is needed. The no-action-contrast recipe was completed after fit-data inspection but before fitting and final execution, explicitly disclosed in [method](method.md).

## Training, execution and reproducibility

Real training: 8 weighted text preference pairs, 2 epochs / 16 steps, LoRA r=8/alpha=16/dropout=.05 on q_proj/v_proj, AdamW 5e-5, seed 7170, MPS float32, 1024 tokens. 1,146,880 trainable parameters; 112 tensors changed; finite nonzero gradients; independent adapter reload matched with maximum score error 0. [Training summary](../../artifacts/repo-aware-routing/training/summary.json), [environment](../../artifacts/repo-aware-routing/training/environment.json). Original training wall duration was not separately instrumented and remains null. Adapter stays local; pinned upstream revisions and reproduction recipe are public.

Study ledger: 8 development + 2 equal-K + 12 fit + 6 calibration + 20 final = **48 real research Agent executions**. Four additional prelaunch failures started no Agent and remain in [prelaunch evidence](../../artifacts/repo-aware-routing/development-prelaunch/results.json). One separate real product assist is an engineering check, not a 49th independent research observation. Qualification retained 21 candidates / 30 attempts / 20 qualified families. No new paid provider, remote GPU or reset credit was used; billed dollars are unknown.

All published tables are rebuilt by `python scripts/repo_aware/check_public.py` without Torch, private traces, weights or inference. It verifies artifact/package/patch/JUnit identities, denominators, sealed gate feedback and actual final decisions. Public JUnit contains case IDs/outcomes with stack streams removed; original hashes are retained. This recomputes records, not the original subscribed Agent calls. Full replication of stochastic Agent outcomes is not promised.

[Clean wheel evidence](../../artifacts/repo-aware-routing/installation/clean-wheel.json) records installed package bytes and no heavy dependencies. Product assist and separate component profiles are linked from the [review index](review-index.md). The wheel build commit may precede final documentation commits; its runtime tree and installed bytes are checked against final HEAD. Same-final-HEAD CI and final closure digest are reported on PR48.

## Product acceptance

A separately installed wheel executed one real `--policy auto` assist on the public empty-input request: engineering COMPLETE, accepted patch, independent reconstruction MATCHED_CAPTURE, source unchanged, container cleanup confirmed. The target moved from fail to pass and protected regression remained pass. `empty-input=CHECKED_PASS`; `other-behavior=NOT_VERIFIED`; `resolved=null`. The frozen gate produced N with `gate_data_signal_insufficient` and all heavy counters zero. [Actual record](../../artifacts/repo-aware-routing/assist/record.json), [patch](../../artifacts/repo-aware-routing/assist/candidate.patch). No qualification/reference answer was supplied to the assist command.

## Separate component timing diagnostic

After all Agent executions ended, two route-only calls per policy profiled the existing frozen implementation. R cold-process / warm-process route wall time was 6.653 / 3.986 seconds; auto was 0.088 / 0.081 seconds. R constructor/index stage was 1.204 / 1.251 seconds, retrieval 0.649 / 0.413, reranker/selection 2.380 / 2.236. R calls were 2 constructors, 1 query, 10 forwards each; auto calls remained zero. Static extraction was about 0.08 seconds; full per-function profiler records include model loading, index, set selection and gate.

These are [cProfile diagnostics](../../artifacts/repo-aware-routing/performance/repo-aware.json), with instrumentation overhead, overlapping inclusive function measurements and warm asset caches. Models reload on the second call; there is no physical cold-disk or persistent serving benchmark. Stage wall timers and profiler function totals have different accounting and must not be summed or substituted for end-to-end Agent costs. Original training and collection costs are not amortized into a speedup claim.
