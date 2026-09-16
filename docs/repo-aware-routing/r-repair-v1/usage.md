# Run the explicit repair configuration

Native remains default. `N.json`, `B2.json`, `C2.json` are separate experimental
configurations. N+ uses `--policy native`; B2/C2 use `--policy repo-aware`.
C2 currently scores and falls back with `no_valid_operating_point`. It does not
certify supported selection. Old Gate + new R returns `r_version_mismatch`.

Run the following records-only check from the repository with the base package
installed (no Torch, Docker, model weights, credentials or new Agent call):

```sh
PYTHONPATH=src python scripts/repo_aware/check_repair.py
```

It verifies literal label quotes against public requests/skill bodies, family
separation, frozen scoring source/label identities, affine refitting and reload,
check metrics, and all six exported attempts using patch/package/JUnit bindings.
It does not re-execute models, Agent patches, or establish human label truth.
The full requests actually presented to labelers are preserved in
`artifacts/repo-aware-routing-r-repair-v1/public-requests.json`.

For independent JSON refit/reload from saved real scores, select **new** output
paths (the CLI refuses overwrites):

```sh
hermes-maintain support calibrate \
  --labels artifacts/repo-aware-routing-r-repair-v1/support-labels.json \
  --scores artifacts/repo-aware-routing-r-repair-v1/cal-scores.json \
  --protocol configs/repo-aware-routing-r-repair-v1/protocol.json \
  --output /tmp/repair-calibration-new.json
hermes-maintain support check \
  --labels artifacts/repo-aware-routing-r-repair-v1/support-labels.json \
  --scores artifacts/repo-aware-routing-r-repair-v1/check-scores.json \
  --model /tmp/repair-calibration-new.json \
  --output /tmp/repair-check-new.json
```

For real model scoring, follow the existing [asset/environment instructions](../usage.md).
Use the exact model revisions and rank-adapter hashes in the new configs;
weights remain private local assets, not part of this source distribution.
A retrained adapter is a different identity and cannot reuse these records.
New config asset paths resolve relative to their config directory; provision
`local-assets/SkillRouter-Embedding-0.6B`, `SkillRouter-Reranker-0.6B`, and
`rank-adapter` at repository root. The saved support calibrator loads with the
standard library. MPS/float32 is the measured device profile; changing it is a
new configuration, not an exact reproduction.

With `TASKS` set to the prepared, qualified task directory (public.md and base/),
the installed CLI's actual scoring command is:

```sh
hermes-maintain support score \
  --labels artifacts/repo-aware-routing-r-repair-v1/support-labels.json \
  --config configs/repo-aware-routing-r-repair-v1/C2.json \
  --tasks "$TASKS" \
  --registry configs/repo-portability/skills-v1/registry.json \
  --split support-check --output /tmp/repair-new-real-scores.json
```

This calls both the frozen rank adapter and independent support base, records
actual token sections and forward counts, and verifies local weight identities.
Use `support-fit` / `support-cal` only under a newly declared experiment; the
published check is frozen and must not be tuned against. The source diagnostic
entry is `python scripts/repo_aware/diagnose_support.py --help`.

Actual Agent execution uses the existing qualified replay protocol, not the
records checker. The published `execution-template.json` is the exact executed
C2 protocol shape with portable local paths; provision qualified tasks, checks,
canary and Docker first, resolve its paths from repository root, and assign fresh
run/output/workspace names. Its model/effort/timeout are inherited as in the smoke.

```sh
hermes-maintain canary --workspace-root /tmp/hermes-repair-canary \
  --private-root local-assets/runtime-private \
  --output local-assets/repair-canary.json --scratch
python scripts/repo_aware/evaluate.py \
  --protocol configs/repo-aware-routing-r-repair-v1/execution-template.json
```

The scratch canary and three real replay calls were executed outside the checkout
against an installed wheel with separately supplied model dependencies. The
public template intentionally requires local prerequisites; it cannot recreate
private qualified source trees or authentication. Reference/hidden checks must
remain in the trusted verifier, never the router or Agent workspace. Keep each
attempt and export with `export_execution.py`; do not turn this smoke into a new
support/utility experiment without a new frozen protocol.
