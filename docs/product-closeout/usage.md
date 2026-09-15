# Current-task assist

`hermes-maintain assist` supports the existing **sqlite-utils** and **csvkit** Python layouts. Default **N** mounts the declared skill library; explicit **F** mounts the fixed package list. These paths do not import Torch/Transformers or download retrieval weights. They still call a real authorized Codex model. Historical replay and optional S recommendation remain separate commands.

## Install and prepare

Use Python 3.11+ and install a wheel in a new environment:

```sh
python -m venv /tmp/hermes-assist-env
/tmp/hermes-assist-env/bin/pip install /absolute/path/hermes_skilleval-0.3.0-py3-none-any.whl
/tmp/hermes-assist-env/bin/hermes-maintain doctor
```

Build the wheel from this branch with `python -m build --wheel`. Keep the checkout as a source of **explicit user-provided** configs/skill assets. The installed runner and seccomp resource come from the wheel, not checkout scripts.

Real execution requires Docker Desktop/Engine, an existing authorized Codex login (`CODEX_HOME/auth.json`, or the default user location), and a prepared offline executor image. The existing [Dockerfile](../../configs/repo-portability/CleanExecutor.Dockerfile) gives the pinned runtime/dependency ingredients. Build into a new local tag, inspect its image ID, and set `profile.image` in your repository configuration to that ID. Example configs contain the image identity actually used for these smokes; that local image ID is not a downloadable registry reference. No remote GPU is needed.

Copy a supported public/local repository into your own development directory. For the supplied smoke checks use the upstream revision in each `upstream.json`; the `existing` check file must byte-match that input repository's `tests/` file. Do not point an example at an unrelated version and assume its fixtures are valid.

## Smallest command

From the checkout containing the explicit example assets (replace `/absolute/path/sqlite-utils` with your source repository):

```sh
/tmp/hermes-assist-env/bin/hermes-maintain assist \
  --repo /absolute/path/sqlite-utils \
  --request configs/product-assist/sqlite-utils/request.md \
  --repository-config configs/product-assist/sqlite-utils/repository.json \
  --checks configs/product-assist/sqlite-utils/checks.json \
  --registry configs/repo-portability/skills-v1/registry.json \
  --skill-assets configs/repo-portability/skills-v1 \
  --output /tmp/new-hermes-assist-run \
  --plan-only
```

Remove `--plan-only` to execute with exactly those inputs. Preflight does not call the model or create the run directory, so the same new output path can then be used. It lists selected input files, excluded/untracked files, actual policy, selected packages, checks, model/effort, timeouts, image/client identity and missing resources. Runtime probes use short-lived offline containers.

For csvkit use its `request.md`, `repository.json` and `checks.json`, and add:

```sh
--arm F --fixed-config configs/repo-portability/fixed-v1.json
```

Model and effort are explicit `--model` / `--effort` options; the smokes used `gpt-5.6-sol` / `medium`. `--timeout` bounds the Agent process. Invalid fields, unsupported layouts, missing package roots, invalid skill configuration, excluded required inputs and unsafe output paths fail before model execution. A failed execution uses a new output directory on retry; it never overwrites its predecessor.

## Input and file policy

The baseline is the **current tracked file contents**, including staged/unstaged changes and deletions. `.git` history is not copied. `include_untracked` explicitly names extra nonignored input files; `exclude_input` explicitly acknowledges excluded tracked files. Unexpected sensitive files, symlinks, special files and oversized input files are rejected. Review preflight exclusions for task completeness. Source branch/index/status and selected bytes are checked again after snapshotting and execution; an unrelated concurrent source edit is reported, never automatically reverted.

`operations-v1` uses case-sensitive POSIX relative paths, component boundaries and add/modify/delete permissions. Longest matching rule wins; unmatched paths are denied. Normal source/test changes and csvkit `examples/` data additions are declared separately. Example fixture rules accept bounded UTF-8 CSV/TSV/JSON/TXT, reject executable modes and obvious script content, and do **not** claim arbitrary data is safe to execute. Files remain isolated. Credentials, check/configuration entrypoints and dependency locks stay protected. Renames need delete plus add permission.

The same policy generates the prompt and validates captured changes. Old profiles without `file_policy` keep the legacy writable-root behavior. New policy does not rewrite csvkit #1247's two historical UNKNOWN results.

## Checks and result meaning

Checks use `assist-checks-v1`. Each specifies an ID, source kind (`existing` or `requirement`), mapped requirement IDs, a controller-owned `trusted_dir`, argv, cwd, environment and timeout. The supported argv is exactly `["python", "-m", "pytest", "test_NAME.py", "-k", "SELECTOR"]`; cwd must be `/tmp`, environment `{}`, and timeout is enforced **per isolated build/CLI/collection/test step**. Other commands/settings are rejected, not silently ignored. Relative trusted paths resolve against the checks JSON. `pytest.ini` fixes discovery; trusted checks are copied outside the Agent workspace and mounted read-only for verification.

Existing checks must match the input snapshot file; additional controller checks are authored before execution from explicit requirements. Agent-authored tests remain development evidence. Baseline and reconstructed candidate run the same frozen checks through the existing isolated candidate loader: top-level candidate pytest/config hooks are outside discovery and package origins must point to `/input`. Empty collection, skip/error, timeout or import mismatch cannot certify a requirement. Baseline failures and newly introduced failures are listed separately.

Read `report.md`, `result.json`, `capture/candidate.patch`, and the paired `baseline-checks/` / `candidate-checks/` outputs. `CHECKED_PASS` means only the mapped cases passed; uncovered requirements remain `NOT_VERIFIED`, and overall `resolved` is always null. Exit 0 means the Agent completed and the declared candidate checks passed; it never means all user requirements are proven. Exit 2 denotes configuration/resource/execution/check failure or partial execution. No-op patches are possible and are reported without inventing changes.

Apply a reviewed patch manually to a separate copy of the same baseline:

```sh
git -C /absolute/path/your-review-copy apply --check /tmp/new-hermes-assist-run/capture/candidate.patch
git -C /absolute/path/your-review-copy apply /tmp/new-hermes-assist-run/capture/candidate.patch
```

There is no automatic apply, commit, upstream push or PR creation. Policy rejection retains the captured patch and reasons. Unsupported capture types retain the private stopped workspace and error; they never enter functional verification. Raw run directories are private and can contain source and model event text: the public evidence pack intentionally exports only selected safe fields, patches and check outputs.

## Evidence limits

The two developer-defined smokes test the software entrypoint, not a new N/F study. Their tasks differ, and no success-rate or token-saving comparison is valid. Codex bundled/client-managed capabilities remain `SYSTEM_MANAGED_UNKNOWN`; mounting the declared packages does not prove which guidance caused a repair. Usage comes only from observed completion events; missing usage and dollar costs stay unknown. Timings are monotonic intervals; request wall time is not the sum of nested intervals.

See [smoke results](smoke-results.md), [CI migration](ci-migration.md), and the [review index](review-index.md). Historical replay's gold/qualification requirements remain intact in the [earlier usage](../repo-portability/usage.md).
