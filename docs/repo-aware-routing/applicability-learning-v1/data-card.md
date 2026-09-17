# Task-conditioned applicability data

Status: READY for this bounded offline pilot; counts are finalized in data-summary.json and results.md. This is model-judged weak supervision, `human_reviewed=false`, not human truth or causal patch utility.

The new catalog combines two existing complete general-workflow packages with eight author-adapted operational skills. The adapted skills use pinned documentation from before 2020: SQLite ingestion, schema changes, full-text indexing; csvkit dialect conversion, tabular conversion, joins and SQL export; and keyed csv-diff comparison. Dependencies, licenses, source revisions and complete package file hashes are in `configs/conditional-applicability-v1/registry.json`. Their content predates the selected issue creation dates; this does not imply the generic external workflow packages were authored before 2020. csvkit's license include is accompanied by its MIT COPYING file; SQLite and csv-diff references retain Apache-2.0 licenses.

24 selected public issues represent 24 declared mechanisms: 12 sqlite-utils, eight csvkit, four csv-diff. Each keeps its full request as one composite requirement, avoiding unsupported per-clause coverage claims. All ten skills are labeled for every task (240 rows); there are no constructed main-set negatives or fit hard-mining samples. Sampling is purposive from recorded GitHub issue pages, based on interface/input/operation diversity; population inclusion probabilities are unknown, and this is not a sample of real user traffic. A package with no positives remains in the complete catalog. No label balance was forced.

Source commits are selected before issue creation, while request bodies are the retrieved public versions and may include later edits or public proposed approaches. No claim of historically original issue text is made. Necessary public approaches are not hidden. Snapshots/context derivation never consult reference patches or hidden tests. Existing bounded context extraction preserves partial/unavailable states and source windows; local runtime dependency qualification is separate.

The split was assigned from mechanisms before annotation or model scoring: fit 12 mechanisms, model-dev four, cal four, check four. A parent request stays in one split. New check groups are not reused original final tasks. The old `legacy-five` directory remains the unchanged 20 tasks / 100 rows in `r-repair-v1`, explicitly previously observed diagnostics. It is not a second new confirmation set.

Two independent same-model contexts saw only the task text, public context and full skill bodies. They did not receive split/group assignments, predictions or reference patches. Both original passes are preserved within the compact merged annotation records. Literal quote checks establish provenance, not semantic truth. Axis-specific disagreement becomes UNKNOWN; there is no outcome-driven arbitration. The parent session record confirms configured model `gpt-6-astra`, medium effort, inherited without overrides by both contexts. Exact backend snapshot and per-call billing are not exposed, so those fields remain unavailable. Invocation IDs/prompt and tool provenance are documented in the work log and annotation provenance artifact.

Applicability is APPLICABLE / NOT_APPLICABLE / CONFLICT / UNKNOWN. Conditional specificity, only for applicable rows, is TASK_SPECIFIC / GENERAL_WORKFLOW / UNKNOWN. A generic workflow remains an applicability positive. Natural absence of conflicts means conflict classification is unassessed, not perfect. Roles may be multi-valued. Request/skill quotation annotations never enter model inputs.

Training follows the Goal's normalized masked objective with pre-mask equal group/task/requirement weights. Main evaluation separately averages the known rows within each requirement, task and mechanism; therefore missing labels do not change one mechanism's mass relative to another. Probability metrics exclude UNKNOWN; selection reports UNKNOWN separately and keeps tasks with no specific positive. Group bootstrap is exploratory with only four check mechanisms.

## Development identifiability (16 mechanisms, 160 pairs)

| Skill | Applicable | Not applicable | Unknown | Specific / general | Positive-negative group pairs |
|---|---:|---:|---:|---:|---:|
| csv-dialect | 2 | 12 | 2 | 2 / 0 | 24 |
| csv-relational-join | 0 | 16 | 0 | 0 / 0 | 0 |
| keyed-csv-diff | 2 | 12 | 2 | 2 / 0 | 24 |
| sql-query-export | 0 | 16 | 0 | 0 / 0 | 0 |
| sqlite-fulltext | 4 | 12 | 0 | 4 / 0 | 48 |
| sqlite-ingest | 5 | 11 | 0 | 5 / 0 | 55 |
| sqlite-schema | 3 | 12 | 1 | 3 / 0 | 36 |
| systematic-debugging | 16 | 0 | 0 | 0 / 16 | 0 |
| tabular-conversion | 7 | 8 | 1 | 7 / 0 | 56 |
| verification-before-completion | 16 | 0 | 0 | 0 / 16 | 0 |

14/16 development tasks have multiple applicable skills and at least one task-specific skill. Six catalog skills vary across positive and negative natural mechanism groups. The 243 positive-negative group pairs count overlapping Cartesian combinations, not independent repairs. Two general-workflow skills are applicable throughout this development set, revealing a strong skill-prior shortcut; two operational skills have no development positives.

The frozen fit-vocabulary lexical model has model-dev applicability log-loss 0.1805 versus 0.3278 for the skill-only negative control. This is a development estimate, not the independent check result and not evidence that the new neural model learned repository reasoning. The adapted content was sourced before selected issues; requests and project/format words can still make shallow lexical matching effective. Labeling contexts share one configured model and prompt, so agreement does not rule out shared bias.

Mechanism groups are authored from public request obligations and source context, not certified from reference-patch families. Shared repositories, libraries and input formats can leave dependence across declared groups. The four-group bootstrap respects the declared units but cannot establish population independence or compensate for purposive sampling. Runtime base/reference qualification has not been inherited merely from these offline source snapshots.

Final labels: 76 APPLICABLE (28 TASK_SPECIFIC, 48 GENERAL_WORKFLOW), 154 NOT_APPLICABLE, 10 UNKNOWN, zero CONFLICT. Applicability judgments agree on 230/240 rows; specificity agrees on all 76 rows where both contexts make the applicable judgment. Agreement does not certify semantic correctness. Check contains 11/37 known applicability positives and three UNKNOWN; its three specific positives occur in two tasks.
