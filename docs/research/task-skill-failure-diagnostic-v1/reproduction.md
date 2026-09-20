# Execution and records-only reproduction

The active Goal is `docs/goals/Hermes_Task_Skill_Failure_Diagnostic_Codex_Goal.md`. This is a development diagnostic, not controller training or a held-out benchmark. PR50 baseline is `442e16ce4ab4b091321a26fc835fc27c92c2c00c`; its original records remain unchanged.

## Portable saved-record checks

From this checkout, with the package installed or `PYTHONPATH=src`:

```sh
python scripts/task_skill_failure_diagnostic/report.py replay \
  --output artifacts/task-skill-failure-diagnostic-v1
```

This verifies saved candidate/JUnit identities and recomputes raw functional labels, acceptance-validity overlays, native counts, paired contrasts and mechanism-equal aggregates. It makes **zero model calls and zero new checker executions**. It is not a rerun of source fixes, same-prefix Agent forks, or a second-environment behavioral replication. A portable replay cannot restore private official session history.

`acceptance-limitations.md` explains why raw checker failures and scientifically interpretable failures differ. Unknown outcomes retain their planned denominators. File policy and cost never override the functional outcome.

## Source preparation and qualification

`source-pool.json` is ordered and records excluded source exposure; `plan.json` binds admitted bases, references, requests, tests, docs, skills, payloads and runtime. Public commit identity is confirmed in `source-confirmation.json`. Preparation scripts build private source copies rather than committing complete repositories.

The final compact `task-contracts/<task-id>` export includes the exact public request, task metadata and frozen checker text. `test_behavior.py.txt` is a byte-preserving evidence object, not a repository test; restoring it as `trusted/test_behavior.py` reproduces that checker without formatting or repairing its documented overconstraints. It is excluded from fresh selector input along with all other hidden acceptance materials.

The actual preparer is `scripts/task_skill_failure_diagnostic/prepare.py`, with `--pool`, `--sqlite`, `--csvkit`, and `--output` paths. Qualification used the existing `scripts/functional_gain_v2/qualify.py` with `--tasks`, `--output`, and `--objective configs/functional-gain-v2/objective-lock.json`. Three preparation-stage qualification attempts are retained in `qualification.json`; only the affected source/acceptance preparation was repaired before sampling. They were local checks, not repair Agent samples. The current frozen plan is deliberately refused by `freeze.py`; do not overwrite it to manufacture a new baseline.

## Actual native execution

On the original host, private artifacts are rooted at `/Users/raidriar/dev/hermes-skilleval-worktrees/hermes-task-skill-failure-diagnostic-private`. The invocation uses the isolated existing Docker executor and mounted, prequalified tasks:

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.diagnostic probe \
  --plan configs/task-skill-failure-diagnostic-v1/plan.json \
  --tasks /Users/raidriar/dev/hermes-skilleval-worktrees/hermes-task-skill-failure-diagnostic-private/tasks-frozen \
  --output /Users/raidriar/dev/hermes-skilleval-worktrees/hermes-task-skill-failure-diagnostic-private/native-v1 \
  --skills configs/conditional-applicability-v1/skills \
  --payloads configs/adaptive-skill-intervention-v1/payloads
```

An output directory is a sample ledger, not a disposable cache. Existing executions are reused as records, never sampled again. A launched interrupted sample remains UNKNOWN; a subsequent invocation may only continue unstarted cells. Container/source preparation is distinct from model sampling. Credentials and full session histories stay private; temporary copied auth is removed in the coordinator's `finally` block.

Fixed runtime: Codex `0.154.0`, `gpt-5.6-sol`, medium, 600 active seconds per original task. Snapshot/restore/injection overhead consumes original remaining time; no fresh 600-second budget is granted to tails. All conditions see the same skills and read-only base-version docs. The executor filters private reasoning and raw provider streams.

## Selection and continuations

After the complete native roster, `audit_acceptance.py --native <native-v1> --plan <plan.json>` preserves the raw panel and produces an acceptance-audited panel. It reads saved checks only, changes no frozen test or original label, and makes no new model/checker call. K selection is blocked unless the audit binds the current native records.

If a supported native-failure panel exists, `selection_input.py` exports only the selected completed-turn public prefix, current source, public docs, ten skills and actual payloads. The answer-exposed coordinator is not the K selector. A fresh analysis context receives only that saved directory; no reference, hidden checks, terminal feedback, future source or arm result. Scratch file contents are omitted from the selector input, explicitly, while the real tails restore full scratch. Actual exported input and returned choices must be retained.

`diagnostic freeze-selection` binds the exact existing payload, G, checkpoint identities and shuffled N/G/K × 2 roster before any tail. `diagnostic tails` restores the official parent/boundary and full source/scratch, runs every state's registered cells, then releases hidden checks. These are execution entrypoints, not claims that an untriggered stage ran. The result report supplies the actual triggered/not-triggered status and counts.

## Export and validation boundaries

`report.py export --private <private-root> --output <new-output>` creates compact patches, JUnit, raw functional records, difficulty counts, paired summaries and costs. It refuses to overwrite per-group exports. Study rows reuse the existing functional evaluator identity; old learning/matrix contrasts are not this study's claim. Source qualification, host orchestration and selector assistance are separate from research-Agent usage; unavailable dollar cost remains unknown.

Focused tests in `tests/test_task_skill_diagnostic.py` use synthetic inputs only to test selector, UNKNOWN, no-K, budget/continuation and comparison contracts. The installed-wheel check uses a private `pip --target` directory and records-only data; no global installation or extra experiment is implied. Repository CI and final integrity verification are engineering evidence, not measured skill utility.
