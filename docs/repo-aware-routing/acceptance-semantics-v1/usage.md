# Exercised installed entrypoints

Python >=3.11 is required; this run used a clean Python 3.12 wheel environment
with only the base PyYAML dependency. Run from outside the repository. Set
`REPO` to the public checkout, `TASKS` to the preserved original `tasks-v2`
directory and `RUNS` to its original `runs` directory. `NEW` must be a new,
controller-owned local directory outside all original assets. Paths are explicit;
no personal home directory or model weight path is compiled into the adapter.

```sh
python -m pip wheel --no-deps "$REPO" -w "$NEW/wheels"
python -m venv "$NEW/installed"
"$NEW/installed/bin/pip" install "$NEW"/wheels/*.whl
cd /tmp
CLI="$NEW/installed/bin/hermes-maintain"
"$CLI" acceptance-review inventory \
  --legacy "$REPO/artifacts/advisory-utility-replay-v1" \
  --config "$REPO/configs/acceptance-semantics-v1" \
  --tasks "$TASKS" --runs "$RUNS" --output "$NEW/inventory.json"
"$CLI" acceptance-review validate \
  --legacy "$REPO/artifacts/advisory-utility-replay-v1" \
  --config "$REPO/configs/acceptance-semantics-v1" \
  --output "$NEW/unused"
"$CLI" acceptance-review records \
  --legacy "$REPO/artifacts/advisory-utility-replay-v1" \
  --config "$REPO/configs/acceptance-semantics-v1" \
  --output "$REPO/artifacts/acceptance-semantics-v1"
```

`records` and `summarize` recompute the same JSON: complete denominator,
legacy JUnit, new process observations, exact CSV matrices and all entrypoint
transitions. They never start Docker, agents or models. `--output` denotes the
existing evidence directory for these read-only actions. The three rendered
comparison tables are in [results.md](results.md).

The actual original-candidate execution used this exact argument shape:

```sh
"$CLI" acceptance-review revalidate \
  --legacy "$REPO/artifacts/advisory-utility-replay-v1" \
  --config "$REPO/configs/acceptance-semantics-v1" \
  --tasks "$TASKS" --runs "$RUNS" --output "$NEW/executions"
```

The installed smoke used the same command with `--first` and a separate fresh
`--output "$NEW/installed-smoke"`. It always selects frozen `candidate-01`
(csvkit F2 r1). That one extra execution is an installation check, not a 17th
independent candidate or best-repeat selection. Completed outputs are verified
and preserved on resume; incomplete directories stop without overwriting them.
Missing original assets cannot be recreated by a repair model.

Control qualification ran the following before freeze (using separate output
roots for retained engineering attempts):

```sh
"$CLI" acceptance-review validate \
  --legacy "$REPO/artifacts/advisory-utility-replay-v1" \
  --config "$REPO/configs/acceptance-semantics-v1" \
  --tasks "$TASKS" --output "$NEW/controls"
```

With `--tasks`, validate executes independent synthetic Python entry packages,
CSV oracle counterexamples, actual base/reference XLSX conversions and entrypoint
controls in the original pinned image. Without `--tasks`, it only verifies the
frozen identities. `freeze.json` records the reviewed source modules, fixtures,
semantics, roster, image and validation digest; editing them invalidates replay.
Fixture generation is exposed in `acceptance_controls.fixtures`; the committed
new workbook uses deterministic stdlib OOXML ZIP generation. Original workbook
bytes were copied from the hash-bound original trusted fixture, not regenerated.

Public export ran:

```sh
"$CLI" acceptance-review publish \
  --legacy "$REPO/artifacts/advisory-utility-replay-v1" \
  --config "$REPO/configs/acceptance-semantics-v1" \
  --runs "$NEW/executions" --output "$NEW/public-results"
```

It copies scoped observations/JUnit only; no source tree, model, private prompt
or original raw archive is duplicated. The public `runs.json` references original
patch paths/hashes. Host verdicts are recomputed from captured process/output
observations, not candidate-supplied success JSON.
