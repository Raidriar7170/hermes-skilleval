# Installed use and recovery

The wheel contains the study adapter, not model weights, private traces or task sources. A base install needs only PyYAML. No new repair is started by `prepare` or `records`.

```sh
python -m pip wheel --no-deps . -w /tmp/hermes-advisory-wheel
python -m venv /tmp/hermes-advisory-installed
/tmp/hermes-advisory-installed/bin/pip install /tmp/hermes-advisory-wheel/*.whl
cd /tmp
/tmp/hermes-advisory-installed/bin/hermes-maintain advisory-study --help
/tmp/hermes-advisory-installed/bin/hermes-maintain advisory-study records \
  --output "$REPO/artifacts/advisory-utility-replay-v1"
```

`REPO` is the absolute checkout path. Public records recompute the full 32-cell denominator, verify bound file and patch hashes, parse trusted JUnit case outcomes, and reconstruct task-level comparisons and usage. They do not rerun models or containers. Private provenance remains local; public evidence alone cannot prove malicious candidate code could never tamper with pytest. Independent patch inspection supplies an additional bounded check.

For an authorized local reproduction, point `STUDY` at a fresh controller-owned directory outside all Agent workspaces, and `PREVIOUS` at the existing frozen independent-validation assets. Recover task assets with `scripts/repo_aware/advisory_prepare_assets.py --project "$REPO" --previous "$PREVIOUS" --output "$STUDY/tasks" --image "$IMAGE"`. This copies fixed existing sources and wraps prior behavior checks. It never replaces unavailable tasks.

```sh
hermes-maintain advisory-study prepare \
  --tasks "$STUDY/tasks" --output "$STUDY/qualification"
hermes-maintain advisory-study recommend \
  --project "$REPO" --tasks "$STUDY/tasks" \
  --registry "$REPO/configs/conditional-applicability-v1/registry.json" \
  --assets "$REPO/configs/conditional-applicability-v1" \
  --model-config "$PREVIOUS/model-configs.json" \
  --output "$STUDY/recommendations.json"
```

Recommendation requires the original available frozen weights and original scorer source identities. `prepare` requires Docker and the source-free pinned image, but no Torch/Transformers/PEFT. Before any formal call, bind fresh task qualification, recommendations, source modules and exact-image isolation canary in a study protocol. The committed protocol records this actual run; it must not be silently reused with new inputs.

The actual formal run used the installed wheel from `/tmp`, with all of the following explicit arguments:

```sh
hermes-maintain advisory-study run \
  --tasks "$STUDY/tasks-v2" --qualification "$STUDY/qualification-1" \
  --registry "$REPO/configs/conditional-applicability-v1/registry.json" \
  --assets "$REPO/configs/conditional-applicability-v1" \
  --protocol "$REPO/configs/advisory-utility-replay-v1/protocol.json" \
  --recommendations "$STUDY/recommendations.json" --canary "$STUDY/canary.json" \
  --private-root "$STUDY/execution-private" \
  --workspace-root /private/tmp/hermes-advisory-v1-formal --output "$STUDY/runs"
```

Run the same command to resume untouched cells after a clean terminal boundary. Completed results are bound and skipped; unresolved attempts stop for inspection. Never delete or rename a started sample to get another attempt. Recovery of interrupted validation must use the stopped original workspace/raw patch, without another Agent call. Prelaunch engineering failures retain their own logs and do not become extra independent samples.

All ten source packages retain their original byte contents. The runner's size/mode-aware package digest is derived from the verified old file-map digest; those two digest formats are recorded separately.
