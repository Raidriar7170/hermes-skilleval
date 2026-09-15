# Evidence and limitations

## Qualification and claim boundary

Every confirmation family has a public request, explicit acceptance scope,
base/reference revision, controller-owned trusted tests, matched test IDs and
four qualification cells. The published qualification summaries omit raw
commands and local paths; `original_sha256` links each summary to its private
original. JUnit and trusted test bytes are preserved. Original public issue
bodies retain their line endings and repair hints. Git whitespace and Ruff
exemptions apply only to those byte-preserved evidence surfaces; project source
checks remain active.

| Family | Target / related regression cases | Scope limitation |
|---|---:|---|
| csvkit #1219 | 2 / 2 | csvstack field-size behavior; csvpy is mentioned but not verified |
| csvkit #1247 | 5 / 2 | timedelta serialization/helper and selected csvstat JSON cases |
| csvkit #1270 | 2 / 2 | numeric inference under explicit date formats; selected preservation cases |
| sqlite-utils #131 | 2 / 4 | insert/upsert text override on new tables; other types and existing tables not certified |
| sqlite-utils #781 + #783 | 14 / 50 | one combined rowid/ignored-insert identity family, not two samples |
| sqlite-utils #828 | 1 / 51 | one default FTS API attack regression; not complete CLI/FTS4 security proof |

#828's original public PR describes the concrete `Database.quote()` repair.
Preserving this hint equally for all arms follows the protocol, but this is
maintenance replay with a public solution hint, not blind vulnerability solving.
No candidate test count is treated as the number of independent tasks. A pass
means the specified target and regression slice passed, not complete requirement
coverage, whole-upstream-suite success or upstream acceptance.

## Frozen comparison

F was chosen for natural Python CLI/API debugging fit before confirmation, and
is unchanged for all requests in each repository. N exposes all five packages;
F/S expose exactly two in the same registry order. All are optional guidance,
with identical public requests, model, effort, executor environment and 600-second
budget. The S constructor, cache/index, retrieval and reranking remain measured
separately from Agent execution. Serialized S calls avoid simultaneous host
retrieval models; two candidate containers may overlap, as may controller checks.
Wall times are observations under this schedule, not isolated latency benchmarks.

All started attempts, including timeouts or failed patches, remain in the
public denominator. There is one attempt per arm/family: no best-of selection,
no confidence or equivalence claim, no causal attribution to skill selection
from a single divergent patch. Development and confirmation are reported apart.
Raw input/cached/output/reasoning token values are reported where present;
cached input is a subset of input and reasoning is a subset of output. No dollar
price was verified, so monetary cost is null, not zero.

## Preparation and repair history

Preparation failures preceded confirmation Agent execution and are not Agent
results. Retained private attempts include: unsafe extraction unavailable in
system Python 3.9; oversized csvkit example data; using a modern utility `.main`
pattern against older `.run` APIs; old editable-build behavior attempting an
unavailable dependency download; NumPy/pandas-dependent upstream test skips.
Python 3.12, declared export exclusions, historical `.run` calls, offline PEP 517
builds and a fully specified clean image resolved these. Mandatory skipped tests
were not deleted or accepted as passes. Six final qualified tasks and the
protocol were committed before confirmation starts.

Development csvkit #1345 originally passed six target and seven regression
cases in each of N/F/S. Subsequent verifier hardening bound original checks to
run/patch identity and exposed that the old development profile omitted allowed
documentation paths. A separate development audit task restores that permitted
scope and requalifies it, then rechecks the identical saved patches. Original
runs, the intermediate failed audit and final audit all remain private. This
is post-development verification repair, not a new Agent invocation, and never
enters the frozen confirmation denominator.

## Public derivative trust

Original run/check/task/patch bindings are checked before export. Offline
records validates public file digests, task/arm/attempt/run identity, the patch
and JUnit binding, exact test IDs and agreement with the original conclusion.
Empty/skipped/errored mandatory tests cannot certify success. Missing evidence
stays unknown. Whole check-directory replacement and conclusion mismatch have
regression coverage. These are consistency checks, not signatures against an
adversary who fabricates all controller records.

Only structured completed command observations referencing a `SKILL.md` path
are exported. A path mention or mounted package alone does not prove reading;
a shell read operation is observable, but full comprehension and causal utility
are not. Raw conversations, full shell commands, home paths, credentials,
private history and model weights are not published.

## Discovered fixture-path policy defect

The frozen csvkit profile omitted `examples/`, although that repository uses it
for test data. The Agent request did not disclose the write-root restriction.
The first observed case, #1247 F, added a four-line CSV fixture and was rejected
before trusted functional tests. The main raw outcome remains mechanically
rejected; public recomputation reports functional unknown and `policy_rejected`.
This defect limits functional-rate and F/S difference interpretations.

The [post-hoc rule](../../configs/repo-portability/post-hoc-fixture-audit.json)
applies uniformly to all N/F/S confirmation attempts. It admits only added,
ordinary, non-executable data fixtures under `examples/`, with bounded size and
suffixes. Eligible entire original patches are rebuilt against the same base,
image and trusted checks in separate audit outputs. No Agent rerun, patch edit,
primary-row replacement or denominator change is permitted. Results answer only
whether removing this fixture path gate changes the specified functional checks.
