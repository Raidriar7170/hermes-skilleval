# Public repair-family pilot candidates

The initial 20 candidates were chosen using public maintenance behavior, installation
scope and licenses before any Agent condition ran. They are not 20 established
algorithm observations. One final-test candidate failed reference qualification and was replaced by a
new public CLI family before any Agent results were observed; all 21 candidate
records remain. The intended qualified allocation is 8 rank-train, 2 rank-dev,
4 gate-fit, 2 gate-calibration and 4 final-test families. `simonw/csv-diff` appears
only in final-test (2 families). Prior repo-portability tasks are excluded.

Request files paraphrase the linked public upstream changes and retain public
implementation guidance when relevant. They are controller-written requests,
not verbatim issue reports. Historical fixes may have appeared in pretraining.
Distinct SQL default decoding fixes remain together in rank-train; distinct FTS
introspection fixes remain together in gate-fit. No paraphrases or multiple tests
are counted as extra independent families.

## Boundaries

- Training reads only the public requests and repair-before snapshots of the
  rank partitions. Reference commits and trusted files are controller-only.
- Gate feedback is collected after R freezes. Fit, calibration and final-test
  remain separate. Final requests may enter frozen inference, never training.
- Qualification verifies only the declared behavior and protected regression
  tests. It does not establish Agent success or routing utility.
- Full upstream sources and tests are fetched privately by the existing
  `prepare_spec` controller. No third-party full dataset or weights are included.
- Locally authored minimal trusted tests are MIT under the Hermes repository
  license. Tests referenced from upstream retain the upstream license:
  sqlite-utils and csv-diff Apache-2.0; csvkit MIT.

## Preparation and qualification

From a checkout with Hermes installed, clone the public upstream repository
named in each spec into an isolated data directory. The pinned reference commit
and its first parent define the task. Do not install the upstream globally.
Build the supplementary dependency image once:

```sh
docker build -t hermes-repo-aware-data:v1 -f configs/repo-aware-routing/DataQualification.Dockerfile .
```

For each spec, use the existing preparation and qualification commands. Example
with a rank-train candidate, and caller-chosen private directories:

```sh
python -m hermes_skilleval._maintenance.prepare_spec \
  --spec configs/repo-aware-routing/tasks/sqlite-utils-escaped-default.json \
  --upstream "$UPSTREAM" --output "$TASK_ROOT"
python -m hermes_skilleval._maintenance.qualify \
  --task-root "$TASK_ROOT" --output "$QUALIFICATION_ROOT" \
  --oracle public-bug-behavior upstream-reference
```

A qualification is accepted only when all four cells are valid, target is red
on base and green on reference, both regression cells are green, and base/ref
collected IDs match. All first-attempt failures remain in the qualification
summary. Collection/installation failures are not functional negatives.
The existing verifier builds the real entry point and executes candidate package
imports in a network-disabled, read-only, capability-dropped Docker container.
The supplementary image inherits `hermes-two-repo-clean:v3` and installs exactly
`dictdiffer==0.9.0` and `pytest-runner==6.0.1`; it does not introduce another runner.

Explicit profile for the held-out repository: package `csv_diff` at `.`, console
entry point `csv_diff.cli:cli`, console name `csv-diff`. The generic profile and
trusted harness already support this shape; product layout validation may need
to admit this supported profile explicitly.

## Public evidence recomputation

```sh
python scripts/repo_aware/recompute_qualification.py
```

This recomputes verdicts from exported JUnit case outcomes, collection IDs and
build/canary facts. It validates archive integrity and arithmetic; it does not
re-run upstream source or prove source identity independently. Full qualification
reproduction uses the existing controller commands above. Exported JUnit removes
container hostnames; raw JUnit SHA-256 is retained separately.
