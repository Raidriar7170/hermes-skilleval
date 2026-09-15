# Two-repository maintenance — review index

**Delivery in progress.** Six confirmation families qualified and 18 N/F/S
attempts are scheduled/running under the committed protocol. No confirmation
utility conclusion is published yet. The records currently contain three
separately labelled csvkit development attempts.

| Surface | Direct entry |
|---|---|
| Active Goal | [Execution contract](../goals/Hermes_Two_Repo_Fixed_Baseline_GitHub_Goal.md) |
| Install and commands | [Wheel, replay, verify, records, assist boundary](usage.md) |
| Fixed comparison | [Pre-run protocol](../../configs/repo-portability/confirmation-protocol.json) |
| Skills/F | [Fixed pairs](../../configs/repo-portability/fixed-v1.json), [registry](../../configs/repo-portability/skills-v1/registry.json) |
| New task qualification | [Six public qualification bundles](../../artifacts/repo-portability/qualification) |
| Development audit | [Qualification](../../artifacts/repo-portability/development-qualification) |
| Public results | [Index](../../artifacts/repo-portability/records/index.json), [offline summary](../../artifacts/repo-portability/records/summary.json) |
| Claim boundaries | [Scope, preparation history, trust limitations](evidence-boundary.md) |
| Environment | [Clean image/versions](../../artifacts/repo-portability/environment.json), [model identity](../../artifacts/repo-portability/model-identity.json) |
| Imported prerequisites | [Allowlist and source commit](prerequisite-import.json) |
| Implementation | [CLI](../../src/hermes_skilleval/maintenance_cli.py), [shared runner](../../src/hermes_skilleval/_maintenance/execute.py), [trusted harness](../../src/hermes_skilleval/_maintenance/trusted_harness.py), [records](../../src/hermes_skilleval/maintenance_records.py) |

## Offline recomputation

After wheel installation, from the checkout:

```sh
hermes-maintain records --index artifacts/repo-portability/records/index.json --output /tmp/hermes-two-repo-records
```

Use a new output directory. This makes no model/network/Docker calls. Actual
replay requires the separately provisioned model/login/Docker resources in the
usage document. Neither a public PR nor a test pass establishes upstream adoption.
