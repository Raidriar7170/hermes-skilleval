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


## 2026-09-19 continuation: full qualification and collection freeze

All 24 registered v2 tasks are now base-red/reference-green. Final qualification
is in `artifacts/functional-gain-v2/qualification/final.json`. The first XLSX
qualification attempt was retained: current agate-excel automatically repairs
A1:A1 dimensions even on the old csvkit base. The revised source-grounded fixture
retains A1:A1 and adds stale A1:B2 dimensions; it tests the public fix's general
recalculation contract, not an exact reproduction of the original issue file.
No Agent had sampled that final task before this qualification repair.

The fixed pilot completed all eight executions: functional pass 8, fail 0,
unknown 0. Public compact counts: `artifacts/functional-gain-v2/pilot-summary.json`.
This does not establish a ceiling across the remaining registered categories.

`collection-protocol-v1.json` now freezes all task identities and the 48 potential
train/dev state slots. Every fourth registered slot gets a second repeat (12
slots), independently of observed availability/results. Maximum paired tails:
240. Related sqlite issue 769 fixes are one cross-fitting family; source family
metadata and the old pilot freeze remain intact. No family crosses a split.

The collector first completes all 16 registered native chains, reusing exactly
pilot repeat 1 for the first four tasks, before branching. The native-only phase
is running in exec session 69002 (process originally 94494), with durable log
`../hermes-functional-gain-v2-private/collection-native-v1.log`. Check live state
before any continuation; never launch a second collector against the same home.
Private assets: `collection-protocol-v1.json`, `collection-tasks-v1` (qualified
source symlinks), `collection-v1`, `pilot-runs-v1/session-home`. Preserve that home
for official forks. Completed native executions are reused by the full collect
command; interrupted reserved attempts remain unknown rather than redrawn.

New modules implement common checkpoint/payload binding, pure-functional pairing,
actual-payload fixed-candidate feature tables, task-weighted skill/stage priors,
and nested family-held-out wait targets. These are implementation and contract
checks only: no v2 gain/wait model has been fit, no skill paired tail has run,
and no final Agent trajectory has run. The training/reload CLI and fixed 80/160-epoch selection contract are implemented
but have no real paired data yet; end-to-end training execution, full result
exports, runtime policies, final freeze/matrix/panels and delivery remain pending.


Focused verification for this slice: 45 contract tests passed, Ruff passed, and
OpenSpec strict validation passed. These checks are not real fitting/evaluation
results. At the last live check, 6/16 registered native first trajectories were
recorded, all functional pass; the seventh was active. Paired tails remain zero.
The earlier 8/8 pilot includes repeats and is not eight distinct tasks.

## 2026-09-19 continuation: final-policy and mechanism execution paths

Implemented v2 policy classes and an isolated `functional-v2 evaluate` command
with ordered phases `matrix`, `panels`, and `delays`. These have not been run on
final tasks. The matrix entry requires current full/task-only model identities,
their independent reload evidence, matching functional collection/objective and
assets, and a prospective policy/code/96-cell roster freeze. N0 repeat 1 is first
within each task so its public checkpoint and model decisions can be locked
before hidden checks; other cells have a fixed seed-shuffled order.

The stable score tie rule is common candidate order; margin remains zero.
Myopic loads the same full gain artifact and never calls its wait head. Missing
learned assets fail closed and are not converted to successful native choices.
The delay controller uses actual branch-local future opportunities under the
original remaining budget; absence of a later opportunity permits no injection.

Panel selection is first real E1, else E2, else E0. First four nonterminal panels
in registered task order define the delay roster regardless of scores/outcomes.
Panel locks retain both immediate gain-only choices (representation contrast)
and full stopping-policy decisions. A WAIT decision is explicitly not identified
by the immediate no-op action panel; never equate it with no further intervention.
A separately measured common prediction overhead is charged equally to panel
and delay tails, along with each tail's own initialization and execution costs.

Resume repair: aggregates are rebuilt even when all per-task records were
already saved before an interruption. Completed samples are not redrawn.
Training now rejects any row whose train/dev split or mechanism family disagrees
with the frozen protocol. Delayed branches retain known functional outcomes
when they legitimately encounter no future intervention opportunity.

Validation: 52 focused contract tests passed, Ruff passed, and the evaluate CLI
help was checked. Synthetic test fixtures only validate code behavior and are
not experimental trajectories or fitting evidence. Real matrix/panel/delay
execution, complete exports and claim verification remain pending. Native
collection process 94494 / exec session 69002 remained live at the last check;
8/16 registered first native trajectories had completed, all functional pass.


Native probe update: the ninth registered task `sqlite-utils-fix-60811e7`
completed normally with `VERIFIED`, target=0, protected regression=1,
functional=0, file-policy=PASS. This is an observed functional failure, not a
policy-only difference. The next task passed, bringing the recorded first
trajectories to 10/16 (9 functional pass, 1 fail, 0 unknown). Preserve this
candidate and all previous successful trajectories; no failure-only sampling.
No skill rescue or damage has yet been observed because paired tails have not
started. Full remaining registered native continuation stays active.

## 2026-09-19 continuation: functional report and portable evidence

Added functional-only main and mechanism tables. Planned matrix cells remain in
the denominator; a task with a missing paired repeat is not summarized from only
its surviving repeat. Intervals first average repeats per task, then tasks per
public mechanism family (fixed seed 7170, 10000 percentile-bootstrap draws;
small-n unstable). Positive point estimates alone are INCONCLUSIVE; the report
uses OBSERVED_WITH_LIMITATIONS only for a complete contrast with a positive lower
interval endpoint and at least two independent families. Zero/negative means
remain NOT_ESTABLISHED. Policy and costs cannot change this computation.

Mechanism tables retain prelocked full/task-only/prior immediate choices,
skill-versus-reminder outcomes, both real delay modes, and the prespecified
positive-current-gain/wait-sensitive subset. An empty sensitive subset keeps the
wait-head claim NOT_IDENTIFIABLE even if a forced delayed branch happens to win.

Implemented `functional-v2 replay` (private or portable evidence) and `export`.
A real export validation on all eight retained native pilot samples completed in
private `export-pilot-validation-v1`; all eight portable records recomputed.
This made zero new Agent/model/verifier calls. Only original patches, compact
JUnit/collected-test/check outputs, hashed thread/fork identities, action metadata
and usage counters were exported; no session transcript, full source or weights.
The currently recorded first 12 native trajectories also passed private
records-only recomputation, preserving the true target failure on 60811e7.

Focused tests now pass 55 checks; Ruff passed. Current resource observation from
the Codex account tool: ordinary usage allowed, weekly used 53% (47% remaining),
no credit purchase or reset use. This is available-capacity evidence, not a
billing statement or guarantee of the whole campaign's future capacity.

Native continuation finished: 16/16 registered train/dev first trajectories,
15 functional pass, 1 functional fail, 0 unknown. Zero-model replay verified all
16 saved records. The native-only process ended normally and removed its auth
copy. G1 is complete; G2 uses the same recorded prefixes and session home.

G2 paired collector is now live: exec session 82437, process originally 4821;
log `../hermes-functional-gain-v2-private/collection-paired-v1.log`. It reused
all 16 native executions before starting the first real sqlite-fulltext E0 tail.
Do not restart a live collector or remove its session-home auth copy. Derived
from the frozen rules: 39 natural checkpoints of 48 possible slots, 192 planned
actual tails of the maximum 240, with nine naturally absent slots. The realized
roster is public configuration; it does not select on paired functional results.
All 16 native original patch/check records were exported to
`artifacts/functional-gain-v2/native` and passed portable records-only replay.

The records-only `functional-v2 summarize` CLI now combines objective identity,
verified saved labels, functional main/mechanism tables, training/reload identity
and explicit pending statuses. An actual invocation during ongoing G2 reported
functional gain training/final evaluation/representation as NOT_RUN, overall
PARTIAL_METHOD/PARTIAL, and KEEP_EXISTING_DEFAULT. It does not assert final
repository closure, legacy preservation or publication without separate evidence.
The first real paired skill tail completed with actual guidance input observed,
658 payload tokens, original remaining budget 599.9063987500267 seconds, and
205.268419791013 active seconds. Hidden functional checks are still held until
all scheduled tails of that task finish; normal execution is not yet success.

## 2026-09-19 continuation: sample identity and intervention receipts

A focused integrity review found two concrete gaps: common-panel reporting had
not rejected equal-sized sets containing an unregistered action, and paired
verification had not independently compared each saved row with its reservation,
actual initial source inventory and newly observed guidance text. Added those
checks, plus delayed-stage/single-use/fixed-skill receipt checks. Existing sampled
executions remain untouched; later replay/training applies the stronger checks
symmetrically. No hidden functional checks or Agent calls were used to validate
these receipts. All seven completed real tails available at the check passed.

The final matrix will persist actual gain/wait head call counters and gain
artifact identity beside each execution. Reused executions without a saved call
receipt are explicitly unknown, never reported as zero fresh calls. Private and
portable verification reject a myopic receipt containing wait-head calls.

57 focused tests passed, including changed-source/wrong-guidance and wrong-panel-
action counterexamples. These changes do not modify sample selection, objective,
model configuration, budgets, repetitions or any already produced trajectory.

## 2026-09-19 first complete paired task

The first registered task, sqlite-utils-fix-f66ddcb, finished all 16 planned
E0/E1/E2 tails and external checks. The stronger receipt/candidate/JUnit replay
verified all 16 without a new Agent, model inference or verifier execution.
Every tail had y_functional=1: eight skill-versus-no-op pairs and four generic-
reminder-versus-no-op pairs were all tie_pass. One pair had only a file-policy
transition; it remains zero functional delta and is not a ranking preference.
This is one completed task, not a full-pool constant-signal finding. The collector
has moved to the next registered task without changing selection or repeats.
