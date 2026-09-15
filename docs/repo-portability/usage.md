# Two-repository maintenance replay

This optional CLI supports the published csvkit and sqlite-utils profiles. It
produces a patch in an isolated copy, then independently rebuilds it and runs
controller-owned target/regression tests. It does not modify or push the
upstream checkout. This is a historical replay interface; general current-task
`assist` remains **NOT_IMPLEMENTED** in this delivery. No reference-free issue is
certified as resolved. Assist smoke and external-user adoption were not run.

## Install and offline inspection

Python 3.12 is recommended (safe archive extraction requires an updated Python).
From this repository, build a wheel, then install into a fresh environment:

```sh
python -m pip wheel . --no-deps -w dist
python -m venv .maintenance-env
.maintenance-env/bin/pip install dist/hermes_skilleval-0.3.0-py3-none-any.whl
.maintenance-env/bin/hermes-maintain doctor
.maintenance-env/bin/hermes-maintain records \
  --index artifacts/repo-portability/records/index.json --output /tmp/hermes-records
```

Use a fresh output directory: existing evidence is never overwritten. Records
needs Python and PyYAML only; it does not call an Agent, download weights, or
require Docker. `doctor` reports asset/dependency presence, not successful strong
inference. Native/F require no Torch or Transformers.

## Reproduce a qualified task

Set `ROOT` to this checkout and use fresh private directories. These commands
require Docker already running, Git, the installed CLI on PATH, and network only
for building dependencies/cloning public sources. The resulting candidate build
and trusted checks have no network. This build pins top-level dependencies;
transitive dependencies are recorded in the published environment inventory.

```sh
ROOT="$PWD"
mkdir -p /tmp/hermes-replay
cd /tmp/hermes-replay
git clone https://github.com/wireservice/csvkit.git upstream-csvkit
git clone https://github.com/simonw/sqlite-utils.git upstream-sqlite-utils
docker build -f "$ROOT/configs/repo-portability/CleanExecutor.Dockerfile" \
  -t hermes-two-repo-clean:v3 "$ROOT"
hermes-maintain prepare --spec "$ROOT/configs/repo-portability/confirmation-v1/csvkit-1219.json" \
  --upstream upstream-csvkit --output task-csvkit
hermes-maintain prepare --spec "$ROOT/configs/repo-portability/confirmation-v1/sqlite-utils-828.json" \
  --upstream upstream-sqlite-utils --output task-sqlite
hermes-maintain qualify --task-root task-csvkit --output qualified-csvkit \
  --oracle cli-api-regression systematic-debugging
hermes-maintain qualify --task-root task-sqlite --output qualified-sqlite \
  --oracle cli-api-regression systematic-debugging
hermes-maintain canary --image hermes-two-repo-clean:v3 \
  --workspace-root /tmp/hermes-replay-work --private-root private --output canary.json
```

Qualification requires base target red, reference target green, related
regressions green on both, identical collected test IDs, and no skipped/error
mandatory tests. Rebuilding another image produces a new local identity and
requires local qualification/canary; it is not the published experiment.

## Real Agent replay

Uses the existing local Codex login, model `gpt-5.6-sol`, medium effort, a 600 s
Agent timeout, and a fresh isolated workspace. It has inference cost. Credentials
are privately staged for the transport then removed; they are not mounted into
the candidate's accessible filesystem. The canary is a bounded check, not proof
of arbitrary malicious-Python containment. Only the explicit trusted regression
slice is verified, not the upstream's complete test suite.

```sh
hermes-maintain run --task-root task-csvkit --qualification qualified-csvkit/qualified.json \
  --public-request task-csvkit/public.md --canary canary.json \
  --registry "$ROOT/configs/repo-portability/skills-v1/registry.json" \
  --skill-assets "$ROOT/configs/repo-portability/skills-v1" \
  --fixed-config "$ROOT/configs/repo-portability/fixed-v1.json" \
  --arm F --run-id csvkit-F-local --timeout 600 \
  --workspace-root /tmp/hermes-replay-work --private-root private --output csvkit-F-local
```

For sqlite-utils, replace task/qualification/public-request with `task-sqlite`,
`qualified-sqlite/qualified.json`, `task-sqlite/public.md`, and use a new run ID
and output. These use the same runner and verifier with repository profiles.
For N, use `--arm N` and omit `--fixed-config`.

For S, install the optional `embedding` extra into the controller environment,
place the real encoder/reranker assets at paths in a copy of
[open-profile.example.json](../../configs/repo-portability/open-profile.example.json),
and use `--arm S --profile profile.json --cache router-cache.json`. Relative model
paths resolve against the profile file. Exact revisions, device, dtype, lengths,
templates and index identity are recorded. The example CPU profile is portable;
the published online S runs used MPS/float32. The cache is identity-checked;
constructor/index/retrieval/reranking times are separate. No hash router can
substitute for missing weights while retaining the S label.

## Verify a saved patch without an Agent

```sh
hermes-maintain verify --task-root task-csvkit \
  --qualification qualified-csvkit/qualified.json \
  --patch csvkit-F-local/saved-capture/candidate.patch --output verify-csvkit
```

Replay `run.json` is private raw evidence. Public export is an allowlisted
derivative: patch, JUnit, bound record, timing, usage and structured skill-read
observations. Public digests detect inconsistency; they are not signatures or
independent proof against a controller that fabricates its entire evidence set.

## Delivery checks and known policy limit

`scripts/repo_workflow/check_install.sh /absolute/fresh/directory` executes the
wheel/offline smoke separately. Existing pytest CI includes the public records
consistency test; no new Actions workflow or broader GitHub scope is required.

The frozen csvkit profile does not allow `examples/` modifications. This limit
was not disclosed to the campaign Agent and caused ordinary fixture additions
to be rejected. Consult the [evidence boundary](evidence-boundary.md) before
interpreting those outcomes. The published frozen profiles are retained for
review, not silently relaxed into a revised primary experiment.

The final delivery CLI discloses `writable_roots` directly to the Agent,
including the restriction on fixtures. The frozen confirmation used the earlier
wheel without that disclosure. Reproducing that original presentation requires
source commit `31ebf2456381df2cff80725f9b9bc187d41021d2`; the modern entrypoint is
not silently claimed to have generated the historical records.

The records output's `summary.json` also contains `cost_summary`: sums of known
input/cached/output/reasoning tokens and timings, with coverage counts. Cached
input and reasoning output remain subsets; unknown values and dollar cost are
not replaced by zero. Validated route files provide the online S timing detail.
