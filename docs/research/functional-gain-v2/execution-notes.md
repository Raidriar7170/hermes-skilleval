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

## 2026-09-19 collection completeness gate

The first two completed tasks now contain 24 verified functional-pass tails;
12 skill pairs remain zero-delta, with 18 total skill/generic tie-pass pairs.
The full collection remains FUNCTIONAL_SIGNAL_UNRESOLVED. Portable replay CLI
requires the identity-bearing aggregate records, not the identity-free task
fragment; the initial fragment invocation rejected identity, and aggregate
records-only replay subsequently verified all 24 without new executions.

Static checking passed all 13 functional modules. Inspection found that training
previously checked the completed-task set without enforcing every prospective
tail. Training now requires `--roster
configs/functional-gain-v2/realized-collection-roster-v1.json`, verifies exact
sample identities (including unknown outcomes), rejects omissions, duplicates
and replacements, and checks candidate order and checkpoint metadata hashes
against the prospective roster. Its hash is retained in model data binding.
The current partial 24-row collection was correctly rejected by this gate;
all 24 available state bindings match the prospective roster. Seven focused
pair/feature/wait tests and Ruff passed. No sampling order, runtime budget,
trajectory, functional label, model training or final evaluation changed.

The records-only summary now shares the exact roster check, allowing a strict
subset only for explicitly partial progress reports. It rejects unregistered or
duplicate samples and cannot mark collection complete from task names alone.
`summarize` now also requires the same `--roster` path as training. Actual private
`progress-report-v2.json` recorded 24/192 scored tails, 168 not yet released,
2/16 completed tasks, and retained PARTIAL_METHOD / KEEP_EXISTING_DEFAULT.
Eight focused pair/report tests, Ruff and scoped mypy passed. The original
collector session 82437 / PID 4821 remained live throughout these read-only
result checks and report changes; no trajectory was restarted.

## 2026-09-19 secondary cost ledger

Third task csvkit-fix-3f9d8b6 completed all 12 tails. Records-only replay verified
36 total released tails, all functional pass; 18 skill pairs remain zero-delta,
so the still-incomplete collection remains FUNCTIONAL_SIGNAL_UNRESOLVED.

Added `scripts/functional_gain_v2/cost_ledger.py` for final secondary cost tables.
It accepts repeated `--records CATEGORY=PATH` arguments (collection,
online_evaluation, mechanism_probes), optional `--training training.json`, and
`--output`. It counts a resolved execution directory once globally, rejects
conflicting reused executions, excludes inherited prefix time, reports token
subsets without double addition, and preserves unknown fields. Online decision
budget charges are separate components, not added to active runtime or claimed
as independently measured total compute; shared/amortized prediction charges
are explicitly qualified. Training wall time is reported only when recorded.
No billing dollars are inferred. Active/unreleased and unsupplied records are
excluded explicitly, so this is not yet the entire campaign's accounting.

The first real invocation exposed dictionary-valued controller overhead rather
than scalar overhead. Fixed it by preserving state/retrieval/checkpoint/decision
components and added the corresponding regression assertion. The corrected
CLI ran on all currently released pilot/native/paired bundles: 60 references,
56 unique executions, four reused references excluded. All 56 executions had
complete usage notifications. Focused cost regression, Ruff and scoped mypy
passed; no Agent, model or verifier calls were made by accounting.

## 2026-09-19 independent pre-final evidence review

A read-only independent Reviewer examined bf81b33 against the complete Goal for
same-state/family isolation, waiting counterfactuals and publication privacy.
Two P1 findings were confirmed before any final trajectory or model fit: the
matrix runner released hidden labels before mechanism tails; the reporter could
interpret a missing delay roster as no eligible opportunity and had not bound
panel predictions to their hashed lock and frozen policy/model identity.

Final phases now write only `matrix-executions.json`, `panel-executions.json`
and `delay-executions.json`. After those phases, use the same evaluate arguments
with `--phase release`: its all-category exact-roster preflight rejects missing,
extra or duplicate execution rows, wrong panel bindings and hidden labels in
execution bundles before invoking any hidden verifier. Only release writes the
scored `*-records.json` files and a release receipt. This is a stronger global
release boundary than the minimum per-task boundary. Saved executions remain
reusable after interruption, with no outcome-driven re-sampling.

Panel locks now bind the full policy freeze, including model identities. The
reporter verifies lock/row/model bindings, reconstructs the prospective delay
roster, and distinguishes a missing plan from a verified empty one. Completion
also requires the release receipt and matching execution bundle hashes.

The same Reviewer statically rechecked both fixes and found no new blocking
issue, explicitly withholding claims about future real execution/recovery.
61 focused tests passed, including missing-bundle/no-hidden-check and missing-
delay-plan regressions; Ruff and mypy on all 14 functional modules passed.
These control-flow fixtures are not experimental evidence. G2 collector
PID 4821 / session 82437 continued unchanged; final sampling, trained models,
formal closure, publication and final evidence review remain pending.

## 2026-09-19 G2 nine-task interim evidence

The first nine registered tasks released 116 of 192 realized planned tails.
Records-only replay independently recomputed 115 VERIFIED records and one
UNKNOWN_NO_ACCEPTANCE record, with zero new Agent/model/verifier executions.
The exact prospective roster check accepted this incomplete subset; 76 tails
were not yet released. This is an interim snapshot, not collection completion.

Functional outcomes were 100 passes, 15 failures and one unknown. All 15 known
tails for sqlite-utils-fix-60811e7 failed functionally. Its E1 repeat-1
NO_INTERVENTION attempt returned EXECUTOR_ERROR with serverOverloaded (selected
model at capacity); the original attempt remains, without replacement sampling
or a different executor model. Subsequent scheduled branches completed normally.
This execution failure is not a functional zero or a known paired tie.

Across 58 skill/no-op pairs, 56 were known zero deltas and two were unknown.
Including the generic-reminder contrasts, transitions were 75 tie-pass, nine
tie-fail and three unknown. Twelve policy-only transitions remain secondary.
The status remains FUNCTIONAL_SIGNAL_UNRESOLVED: collection is incomplete, and
variation in absolute functional outcomes does not establish an action effect.
No model fitting or final evaluation has started. The same live collector
continued with registered task ten, csvkit-fix-6a47526.

## 2026-09-19 G2 first nonzero skill contrast

After eleven tasks, records-only replay recomputed 140/192 registered tails:
139 VERIFIED and one UNKNOWN_NO_ACCEPTANCE, with no new Agent/model/verifier
executions. Functional outcomes were 119 passes, 20 failures and one unknown.
The exact prospective roster accepted this partial subset; 52 tails remained
unreleased. Of 70 skill/no-op pairs, 67 were known ties, one was functional
damage and two were unknown. Including generic-reminder contrasts, there were
89 tie-pass, 12 tie-fail, one damage and three unknown transitions.

The nonzero contrast is csvkit-fix-8119565, E1, repeat 1, csv-dialect: target=0,
protected regression=1, functional=0 versus same-state no-op functional=1,
delta=-1. Its integrity was VERIFIED and ordinary file policy PASS. This is a
real observed functional action difference, not policy-only variation, a rescue
or evidence of positive utility. The interim signal status is therefore
FUNCTIONAL_ACTION_DIFFERENCE_OBSERVED. A single noisy negative contrast does not
establish a general action effect or useful learned selection.

The registered collection continues unchanged with task twelve. Training still
requires the complete realized roster and independent record verification;
neither model fitting nor final sampling has started. The observed damage is
retained under the same weighting and model-selection protocol as all other
pairs, without outcome-driven resampling, filtering or protocol expansion.


## G2 complete and G3 started

The original paired collector exited 0 with exactly 192/192 registered tails
across all 16 train/dev tasks. Independent saved-record replay recomputed 191
VERIFIED outcomes and one UNKNOWN_NO_ACCEPTANCE, without new Agent, model or
verifier calls. Functional outcomes are 170 pass, 21 fail, one unknown. The 96
skill contrasts contain 94 known (92 ties, two damage) and two unknown pairs.
Both nonzero contrasts are training-side: csvkit-fix-8119565 E1 csv-dialect and
csv-diff-fix-33e0a59 E0 keyed-csv-diff, each delta -1. No rescue was observed.
All non-noop contrasts including reminders comprise 127 tie-pass, 12 tie-fail,
two damage and three unknown; 18 policy-only transitions remain secondary.

Exact complete-roster validation passed. Fresh SHA-256 verification matched all
51 frozen payload, skill and encoder files to the collection protocol. Phase
integrity against baseline 87fd45f85f793361da016af3650fd7eb328b1f4b passed as
SCOPED_VERIFICATION: 154 files scanned/hashed, 1,011,083 bytes read, zero cache
hits, 115.058 ms, no full fallback. This is not FINAL_CLOSURE.
Private receipts: collection-complete-preflight-v1.json and
g2-phase-verification-v1.json. The fixed train command started with the complete
records, original collection protocol, objective lock, learning-protocol-v1 and
realized-collection-roster-v1, output models-v1, log training-v1.log. Training and
independent reload are not yet claimed complete; final evaluation has not run.

The actual training process then exited 0 in 21.498 seconds. A separate CLI
reload process exited 0; both full and task-only gain/wait probes exactly match
the saved expectations. Full weights SHA-256 is
c70fa5b08c63dab9f1a062c54700ff5c5f17f8c5c32e646e62878ba748501fff;
task-only weights SHA-256 is
d289f7013250d4dc6d7f937e13e8920af2947142c7eb3f64175b4adad9131648.
Independent reload evidence is models-v1/independent-reload.json. The training
stage is TRAINED_AND_RELOADED; this makes no functional or mechanism gain claim.


## G4 frozen; G5 matrix started

Fresh verify_freeze passed for all 24 registered task base/trusted/reference
assets, task profiles/requests, encoder, payloads, skills, registry and executor
image before final execution. The final freeze binds both independently reloaded
models, training receipt, runtime code, all 96 matrix cells, panel selection,
two panel repeats and prospective delay selection. Saved privately at
evaluation-v1/policy-freeze.json. Existing account usage allowed continuation
with 36% of the current weekly window remaining; no resource purchase/reset.

The real matrix command started with the same collection-protocol-v1,
collection-tasks-v1, models-v1, frozen skills/payloads/encoder and 600-second
budget, output evaluation-v1 and log evaluation-matrix-v1.log. It executes all
six methods on all eight fresh final tasks with two repeats. Matrix, panels
and delays must all finish before the separate release phase runs any hidden
acceptance. No final functional outcomes or mechanism gains are claimed here.

## Independent review of completed G2/G3/G4 exports

The existing read-only reviewer inspected HEAD
a8eb96f094ef8864d2115490bd3c2b72e2effb05 and reported no consequential
findings within the completed collection, training and freeze export scope.
Independent records-only replay reproduced 192 rows: 191 VERIFIED and one
UNKNOWN_NO_ACCEPTANCE; 96 skill contrasts were 92 ties, two damage and two
unknown, with no rescue. All 191 public patches matched their original captured
bytes. Labels, payloads and state bindings matched completed private collection
records; thread identities were hashed as intended.

Public training/reload receipts matched their private originals, and both
weight/metadata identities matched training, reload and final freeze. Saved
cross-fitting family exclusions held. Development errors and documentation
correctly report neither learned model outperforming the zero baseline.
The public collection contained 1261 files (approximately 4.29 MB); the review
found no authentication material, private sessions, raw thread IDs, full source
copies or model weights, with no hits from its limited credential/local-path
pattern scan.

This review did not run new models or acceptance checks, independently reload
weights again, or read evaluation-v1 or final hidden outcomes. It relies on the
saved independent-reload receipt and identity bindings for reload evidence.
It is not final study closure and does not establish functional, representation
or waiting benefits. Final evaluation and final evidence review remain pending.

## G5 interrupted process recovery

After 63 completed matrix executions, the observation call was interrupted.
On continuation, the original process handle was missing, no functional matrix
process existed, and Docker reported no running containers. The next reserved
sample, csvkit-fix-7bba1bd / H-task-fixedC-v2 / repeat 2, retained intermediate
files but no execution.json. This establishes stopped execution, not merely an
observation timeout; the precise process termination cause is not established.

The stale task-local authentication copy was removed after these checks, and
the unchanged matrix command resumed against the same output and policy freeze.
Existing completed samples were reused. The existing run_once recovery path
retained the reserved sample as UNKNOWN_INTERRUPTED_ATTEMPT, with no replacement
sampling, and advanced to P1-v2 repeat 2. The original log and partial attempt
remain intact; recovery-after-interruption-v1.json and
evaluation-matrix-resume-v1.log record the recovery privately. All 96 planned
cells remain in the denominator. No hidden final acceptance was released.

## G5 matrix recorded; common-state panels started

The resumed matrix process exited 0. Exact multiset comparison against the
frozen roster verified all 96 planned task/method/repeat cells without missing
or duplicate entries: 95 COMPLETED executions and one
UNKNOWN_INTERRUPTED_ATTEMPT. These are execution statuses, not functional
acceptance results. The saved policy freeze is unchanged, all eight prospective
panel states are available, and the registered forward-delay roster contains
16 tails. The matrix session authentication copy was removed normally; no
release.json exists.

The panels phase started with the same protocol, task assets, output directory,
models, skills, payloads and encoder as the matrix. Its log is
evaluation-panels-v1.log. This phase runs the frozen common-state action table;
delays and the separate hidden-acceptance release remain pending.

## G5 panels recorded; forward delays started

The panel process exited 0 with 64 recorded tails across eight locked states.
Exact multiset comparison against each saved action roster found no missing or
duplicate task/action/repeat entries; all 64 execution statuses are COMPLETED.
These statuses do not assert functional acceptance. The task-local auth copy
was removed normally and no release.json exists.

The delays phase started using the unchanged protocol, assets, models and
evaluation-v1 output, with log evaluation-delays-v1.log. It executes the 16
registered DEFER_SAME/WAIT_THEN_FULL continuations from their common starting
states. Final hidden acceptance and all final benefit claims remain withheld.

## G5 forward continuations complete; unified acceptance started

The delayed phase exited 0. Exact multiset comparison against the frozen
`delay-roster.json` confirmed all 16 task/action/repeat records, each with
execution status COMPLETED. The task-local auth file was removed, and no
`release.json` existed before unified acceptance began. All three raw categories
are now present: matrix 96 (95 COMPLETED and one retained interrupted UNKNOWN),
panels 64, delays 16. These are execution counts, not functional pass counts.

The unchanged `evaluate --phase release` entry point is now checking the saved
complete candidates only after its all-category roster/freeze preflight. It
starts no new Agent samples and does not replace the interrupted matrix cell.

Fresh local compatibility checks on the unchanged implementation passed:
`PYTHONPATH=src /opt/anaconda3/bin/python -m pytest -q`: 1507 passed in 46.28s;
`OPENSPEC_TELEMETRY=0 openspec validate --all --strict`: 39 passed, zero failed.
A new isolated Python 3.12 venv installed the package normally; both the legacy
entry point help and the v2 module help worked, with the latter invoked from
`/tmp` to avoid relying on the source checkout. These checks do not establish
functional gain, final repository closure, or same-HEAD GitHub CI.

## G5 unified results and G6 records-only exports

`evaluate --phase release` exited 0 after all raw categories were complete.
The release receipt binds 96 matrix, 64 panel and 16 delay rows to their original
execution-bundle SHA-256 values and the unchanged policy freeze. Matrix outcomes
are 95 functional passes plus the retained interrupted task-only UNKNOWN; panel
and delay outcomes are 64/64 and 16/16. No Agent sample was added or replaced.

The records-only `summarize` command used collection-protocol-v1, the locked
objective, collection-v1, realized-collection-roster-v1, evaluation-v1 and
models-v1, writing private final-report-v1.json. It recomputed saved evidence and
verified release/freeze bindings. Public final-report.json preserves all values,
replacing only private path keys and recording the original report hash. The
strict terminal remains PARTIAL / PARTIAL_METHOD because one final cell has no
functional verdict. All three benefit claims are NOT_ESTABLISHED.

The existing `functional_cli export` ran for matrix-records, panel-records and
delay-records with groups matrix, panels and delays, respectively. Each export
performed private and portable records-only replay, with zero Agent/model calls
and zero new verifier executions. The resulting 96/64/16 rows, original patches
and compact checker outputs are public. Panel decision summaries retain original
lock identities and predictions; they explicitly omit raw checkpoint/source
state and do not pretend their redacted digest equals the original lock digest.

The cost ledger used, in order, pilot-runs-v1/records, collection-v1/native-records,
collection-v1/records, then matrix/panel/delay records, plus models-v1/training.
Four pilot/native references reused execution directories; 392 references reduce
to 388 unique attempts. Saved usage for the interrupted directory is observed
partial execution cost, not a completed-run estimate. No billing USD is inferred.

The result homepage and Chinese retrospective report the functional primary
outcome first, then fixed-candidate representation, waiting, cheap controls,
limitations and secondary policy/cost. Six of eight immediate-action choices
differ by representation; two of four delayed states are wait-sensitive. All
corresponding observed functional contrasts are zero. No threshold, candidate,
weight or sample count changed after outcome release.

## G6 independent final evidence review

The existing read-only reviewer independently recomputed public/private 96/64/16
replays and the main/mechanism tables; original patch identities, frozen rosters,
release bindings and interruption preservation matched. All cost-ledger values
were independently reproduced from saved usage: 392 references, four reuse
exclusions, 388 unique attempts. The reviewer confirmed six representation
disagreements, two genuine wait-sensitive states, actual forward E1-to-E2 tails,
fixed DEFER_SAME content, and adaptive WAIT_THEN_FULL behavior. All measured
functional contrasts remained zero. No consequential finding required repair.
Public privacy checks found no credential/local-machine-path matches, private
transcripts or weights. This was records-only evidence review, with no new Agent,
training, model or verifier execution; it does not certify unperformed GitHub CI.

An additional secondary setup receipt preserves both original and resumed matrix
coordinator loads (8.893562625 seconds total). Shared initialization without a
standalone receipt in other phases remains UNKNOWN, not zero; it is not silently
added to already charged per-state work.

## Draft PR and first CI correction

Draft PR #50 was created stacked on still-open/draft #49. First push encountered
an unavailable pre-existing local Git proxy; a command-local empty proxy override
succeeded without changing global configuration. First GitHub run 35491754811
at bd7a711 passed pytest, OpenSpec, release and diagnostic gates, but the final
summary correctly blocked on a new Ruff format finding in functional_pairs.py.
The correction wraps one existing ValueError string across lines. AST comparison
against the executed source is identical; no labels, frozen runtime policy,
weights, candidates or experimental outcomes change. The failed CI is retained,
and the next commit is checked afresh.
