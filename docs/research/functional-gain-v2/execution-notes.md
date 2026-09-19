# Functional gain v2 execution record

Active contract: [complete Goal](../../goals/Hermes_ASI_v2_Functional_Gain_Same_State_Codex_Goal.md).
This is ongoing research, not a completion report. The task checklist lives only in
`openspec/changes/functional-gain-v2/tasks.md`.

## 2026-09-19: G0 and G1 start

Baseline `87fd45f85f793361da016af3650fd7eb328b1f4b`, PR #49 open/draft,
branch `codex/hermes-adaptive-skill-intervention`, clean checkout. Isolated v2
branch `codex/hermes-functional-gain-v2`; intended PR base remains v1.
Old v1 source, models, raw records and final evaluation are preserved.

Read scope: v1 implementation and train/dev evidence, public upstream source and
source metadata for historical exclusion. Write scope: v2 configs, intervention
extensions, focused tests, preparation scripts, this change and v2 evidence.
Frozen scope: v1 configurations/results/weights, upstream pilot base/reference/
trusted tests, actual payloads, encoder, executor image and 600-second model
budget. Final repository scope is the full tracked delta against the baseline;
formal final closure has not been performed.

G0 independently checks the captured public patches/JUnit and reports 180
train/dev records: 178 functional passes, 2 UNKNOWN. The 135 historical action
pairs (including reminder) contain 133 tie-pass and 2 unknown, zero functional
rescue/damage; 19 policy-only transitions. No old final matrix was rerun or used
for model selection. Public export lacks complete prefix identities and saved
waiting scores, so those diagnostic fields remain unavailable rather than
fabricated. Old labels are not reused as v2 training.

The objective lock is enforced by current decomposition, preparation,
qualification and native pilot entry points. Training and final evaluation
entry points remain pending and must enforce it too. Focused v2 outcome tests
and unchanged v1 intervention tests passed: 35 tests. This proves software
logic, not functional intervention benefit.

The initial 24-entry pool was registered before v2 Agent calls. A later complete
historical identity audit found that four initially proposed SQLite test tasks
had already been studied. `task-pool-v2.json` preserves that exclusion and
replaces those unrun final candidates once using public provenance. Original
`task-pool.json` and the first-four training pilot freeze remain intact.
Some training/development mechanisms were previously observed; their new
samples must not be described as newly discovered sources or fresh final tests.
No skill-action or final outcomes informed this correction.

First four pilot tasks qualified base-target-red/base-regression-green and
reference-target/regression-green. Five further SQLite training tasks and seven
tabular train/dev tasks also qualified. Eight corrected final tasks still need
source-to-contract coverage and qualification before final study freeze.

Preparation corrections, all before affected Agent sampling:

- Initial inherited qualifier hardcoded `test_target` and omitted SQLite target
  functions with upstream names. Its first output is retained privately and is
  not qualification evidence. The v2 qualifier executes declared target and
  regression selectors separately.
- The default shell Python was 3.9; actual preparation/trials use the installed
  Python 3.12 environment.
- Tabular checker v1 assumed a `CSVPy.input_file` before runtime setup, omitted
  `--format json` required by the historical csv-diff CLI, and passed a
  nonexistent `memory --detect-types` option (detection is default). v2 repairs
  the invocation adapters; original checks and failures remain in separate
  private preparation directories. No Agent samples were replaced.

Runtime: installed Codex 0.154.0, inherited pinned executor image, execution
model gpt-5.6-sol/medium, original skill catalog and MiniLM revision. No new
resources purchased. Observed remaining weekly quota was 50%; capacity is not
guaranteed. Old measured mean tail duration was 95.87 seconds; 416 executions
at that rate suggest roughly 11.08 hours excluding prefixes/preparation and
with substantial uncertainty. Billing remains UNKNOWN.

Eight preregistered native pilot runs are executing sequentially. Original
remaining-budget snapshots, run reservations and complete candidates are
retained. Completed attempts are reused; interrupted reservations are UNKNOWN.
Native success is not evidence for or against skill rescue until real paired
actions exist. If all four pilot tasks pass, continue the registered remaining
training pool as required by Goal section 9.

## Reproduction and continuation

Run from the v2 checkout with Python >=3.11 (`/opt/anaconda3/bin/python` was used
locally) and `PYTHONPATH=src`. Private root is the sibling
`hermes-functional-gain-v2-private`; all runtime/auth material stays outside Git.
Use the exact frozen encoder snapshot and inherited skills/payload paths.

```sh
python -m hermes_skilleval.intervention.cli functional-v2 decompose \
  --records artifacts/adaptive-skill-intervention-v1/collection-records.json \
  --objective configs/functional-gain-v2/objective-lock.json \
  --output artifacts/functional-gain-v2/g0
python -m pytest -q tests/test_functional_outcomes.py tests/test_intervention.py
```

Preparation entry points in `scripts/functional_gain_v2/` are `prepare_pilot.py`,
`prepare_sqlite_training.py`, `prepare_tabular.py`, `qualify.py`, and
`freeze_pilot.py`; each reads the objective lock. `functional-v2 pilot --help`
lists actual continuation arguments. The ongoing pilot uses private
`pilot-protocol-v1.json`, `pilot-tasks-v1`, `pilot-runs-v1`, and its matching
`session-home`. Preserve that home for future official forks. Do not restart
completed cells or consume quota-reset credits without user authorization.

Next: finish pilot and remaining final-task qualification, bind unified assets
and common candidates/payloads, then real paired collection, pure-functional
learning, freeze and all required comparisons. Do not mark G1–G6 complete from
these preparation checks.
