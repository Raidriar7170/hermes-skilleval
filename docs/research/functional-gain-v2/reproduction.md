# Functional-v2 commands and evidence boundaries

The actual runtime was Python 3.12.2 at `/opt/anaconda3/bin/python`, Codex 0.154.0,
`gpt-5.6-sol` with medium reasoning and the inherited 600-second active budget.
The v2 entry point is `hermes-intervention functional-v2` or
`python -m hermes_skilleval.intervention.functional_cli`. Legacy commands remain
unchanged. Run from this checkout. Public exports can be checked without private
source or model files:

```sh
python -m hermes_skilleval.intervention.functional_cli replay \
  --records artifacts/functional-gain-v2/matrix/records.json \
  --objective configs/functional-gain-v2/objective-lock.json \
  --public-root artifacts/functional-gain-v2/matrix
```

Repeat with `panels`, `delays`, `collection` or `native` in both record/root paths.
This verifies saved patch/checker identities and labels; it does not rerun the
Agent or independently execute the source tests.

The actual private coordinator used the following arguments (shown with a
variables for the fixed private root and encoder; replace the two illustrative local paths). Assets, session credentials and model
weights are deliberately not shipped. Do not invoke these commands as a new
benchmark using partially reconstructed inputs; use the frozen manifest.

```sh
TASK_PRIVATE=/path/to/hermes-functional-gain-v2-private
TASK_ENCODER=/path/to/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.functional_cli evaluate \
  --phase release \
  --protocol "$TASK_PRIVATE/collection-protocol-v1.json" \
  --objective configs/functional-gain-v2/objective-lock.json \
  --tasks "$TASK_PRIVATE/collection-tasks-v1" \
  --output "$TASK_PRIVATE/evaluation-v1" \
  --skills configs/conditional-applicability-v1/skills \
  --payloads configs/adaptive-skill-intervention-v1/payloads \
  --encoder "$TASK_ENCODER" --models "$TASK_PRIVATE/models-v1"
```

The same arguments ran the phases `matrix`, `panels`, `delays`, in that order,
before `release`. The interrupted matrix was resumed once against the same
output directory, which preserves existing results and the interrupted UNKNOWN.
No completed sample was rerun. Release executed hidden acceptance only after all
raw registered categories were present.

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.functional_cli summarize \
  --protocol "$TASK_PRIVATE/collection-protocol-v1.json" \
  --objective configs/functional-gain-v2/objective-lock.json \
  --collection "$TASK_PRIVATE/collection-v1" \
  --roster configs/functional-gain-v2/realized-collection-roster-v1.json \
  --evaluation "$TASK_PRIVATE/evaluation-v1" \
  --models "$TASK_PRIVATE/models-v1" --output "$TASK_PRIVATE/final-report-v1.json"
```

Exports used `export --records .../{matrix,panel,delay}-records.json` with
`--group {matrix,panels,delays}`, the same objective, and corresponding
`artifacts/functional-gain-v2/{matrix,panels,delays}` output directories.
The committed output contains original patch bytes and compact verdict/JUnit
evidence. Public report path keys and panel raw states are deliberately reduced;
source identities and the reduction boundary are recorded explicitly.

Focused checks, actual full local pytest, strict OpenSpec validation, independent
read-only review and package installation are recorded in execution-notes.md.
Live experiments and training are not part of normal CI; CI cannot establish
functional utility. This study's frozen outcomes must not be replaced by later
runs or interpreted as a release/promotion authorization.
