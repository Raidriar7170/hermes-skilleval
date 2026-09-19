# Frozen comparison results

All 96 scheduled trajectories completed: eight held-out mechanisms, six methods, two repeats. There are no missing final labels. **Every final patch passed the target and protected regression checks. All final quality differences are file-policy failures.** “Qualified patch” below means target AND regression AND file-policy acceptance; it must not be described as semantic repair success alone.

| Method | Qualified patches | Policy failures | Mean utility | Mean active seconds | Injections |
|---|---:|---:|---:|---:|---:|
| N0 | 9/16 | 7 | 0.551666 | 130.01 | 0 |
| S1 static | 9/16 | 7 | 0.538218 | 114.55 | 16 |
| R1 rule | 11/16 | 5 | 0.662700 | 123.11 | 16 |
| H-myopic | 12/16 | 4 | 0.736505 | 110.02 | 5 |
| H-no-state | 10/16 | 6 | 0.609807 | 114.36 | 6 |
| H-full | 12/16 | 4 | 0.733704 | 121.72 | 7 |

The full policy improves observed composite utility over N0 by 0.182039, with an eight-task paired percentile-bootstrap 95% interval [0.053146, 0.367518]. Qualified-patch difference is 3/16 (18.75 percentage points), interval [6.25, 37.5] points. This is a small, stochastic, mechanism-held-out comparison within three known repositories; it is neither repository transfer nor contamination-free evidence. Repeats are averaged within tasks before bootstrapping, not counted as 16 independent tasks. Intervals are descriptive, unstable at eight tasks, and not multiple-comparison adjusted.

| H-full minus comparator | Utility difference | Task-bootstrap 95% interval |
|---|---:|---:|
| S1 | 0.195486 | [-0.111606, 0.507274] |
| R1 | 0.071004 | [-0.176448, 0.381723] |
| H-myopic | -0.002800 | [-0.315461, 0.246557] |
| H-no-state | 0.123897 | [-0.316890, 0.562421] |

There is **no demonstrated incremental state or waiting-model utility**. H-full ties myopic qualified-patch count and has slightly lower mean utility. No-state also changes candidate retrieval, so its difference cannot isolate representation alone. Development gain prediction did not beat the cheap skill/stage prior. Skill-versus-generic collection utility difference is -0.047449, interval [-0.139215, 0.031400] over 16 tasks: specialized guidance is not demonstrated superior to a reminder.

## Actual model use and no-op

H-full made seven injections (E0: 2, E1: 2, E2: 3), 22 WAIT decisions and nine terminal model no-ops. Its wait head was actually consulted 26 times. However, no observed positive best-gain action was blocked by the wait value: every WAIT is also explainable by nonpositive predicted immediate gain. `TRAINED_AND_USED` describes actual computation and decision inputs, not demonstrated causal benefit from waiting. H-myopic's shared reason string `WAIT_MODEL_DECISION` means defer with no positive gain; that arm does not call the wait model.

The predeclared development-only forced-E2 diagnostic contains five observed pairs across four tasks. Allowing no-op exceeds forced injection by 0.014680 utility, interval [0.004902, 0.019689], entirely a cost difference with unchanged qualified-patch outcomes. It is an offline supported-action diagnostic, not a seventh end-to-end arm or an estimate of full WAIT trajectory value. The state-only head was trained, saved and reloaded as an offline diagnostic; it is not an extra final policy.

## Three actual trajectory categories

These are illustrative retained samples, not selected additional experiments. Collection contains 88 valid skill/no-op pairs: three qualified-patch rescues, eight damages and 77 ties; two skill pairs are unknown. Generic reminders are excluded from those counts. Train-only fitting counts in the data card include reminders and use a different denominator.

- **Early quality benefit:** not observed at E0 (zero rescues, seven damages, 34 ties). Small positive cost differences must not be relabeled as repaired failures.
- **Later-only observed benefit:** training task sqlite-utils #339, `sqlite-ingest`, repeat 1. E0 utility difference is -1.019382 (skill violates policy, no-op qualifies); E1 is -0.021560 (both violate policy); E2 is +0.976439 (skill qualifies, no-op violates policy). The E2 skill patch implements lookup extra values in `sqlite_utils/db.py` and tests; no-op additionally edits prohibited `docs/python-api.rst`. This demonstrates a realized stage-dependent composite outcome, not a semantic repair rescue or a guaranteed timing effect. The E2 [skill patch](../../../artifacts/adaptive-skill-intervention-v1/collection/sqlite-utils-issue-339/E2/r1/sqlite-ingest/candidate.patch) and [no-op patch](../../../artifacts/adaptive-skill-intervention-v1/collection/sqlite-utils-issue-339/E2/r1/NO_INTERVENTION/candidate.patch) are retained with checks and matched-prefix records.
- **Suitable for no intervention:** development sqlite-utils #368 E2 repeat 1. All actions qualify; no-op utility 0.994761 exceeds ingest 0.974992, fulltext 0.984010 and reminder 0.994710. The full model predicts both skill gains negative and chooses no-op in the development diagnostic. This supports cost avoidance on this observed state, not proof that guidance can never help the task.

For an actual final-policy sequence, sqlite-utils #352 H-full repeat 2 waits at E0 (wait 0.143204) and E1 (0.187724), then injects sqlite-schema at E2 (predicted gain 0.214248, terminal wait zero). The payload is observed in the model input and a real patch is captured. Earlier gains are negative, so this example establishes end-to-end wiring rather than a wait-head causal win.

## Cost and evidence coverage

Training including encoder/features, nested fits, development selection and the state-only diagnostic took 30.899 wall seconds / 30.447 process-CPU seconds; Agent collection is separate. Counterfactual tails consumed 17,160.803 activity seconds; native prefixes are separately recorded. Shared encoder/catalog setup consumed 2.161 seconds outside all arms' trajectory budgets. Per-trajectory learned-head loading, copying, state extraction, retrieval, checkpoints, scoring and execution consume the same original 600-second budget. All 96 final runs have component timing records; older collection component timing is unavailable.

Provider-reported request tokens: collection tails 70,978,841; native prefixes 7,451,580; final trajectories 35,957,933. Full completed-turn usage coverage is respectively 179/180, 15/16 and 96/96. These totals include repeated/cached input and are not dollar cost. Guidance lengths use the frozen proxy tokenizer. Monetary billing remains unavailable. An overloaded native #234 turn re-emitted unchanged prior counters under a new turn ID; the exporter excludes that stale event while retaining the failed turn's usage-coverage gap. This accounting repair changes no execution, label or model.

[Machine-readable results](../../../artifacts/adaptive-skill-intervention-v1/results.json), [collection records](../../../artifacts/adaptive-skill-intervention-v1/collection-records.json), and [final records](../../../artifacts/adaptive-skill-intervention-v1/evaluation-records.json) contain full denominators, decisions, overhead, patches and verifier identities. Portable replay proves consistency with captured verifier evidence; fresh behavior re-execution requires the retained private source bases.

Architecture, matched-prefix execution, real fitting/reload and the frozen comparison are implemented. The measured outcome is **OBSERVED_GAIN_WITH_LIMITATIONS** for the file-policy-inclusive comparison against N0 only. State/wait incremental utility remains unestablished. **KEEP_EXISTING_DEFAULT**; no deployment or default promotion follows.
