# Two-repository maintenance — review index

**Study completed: six new confirmation families, 18 N/F/S attempts, plus three separately reported development attempts.** All 18 started; no outcome retries or timeouts.

- **Engineering: PARTIAL.** Two-repository replay, isolated wheel entrypoint and offline records are complete; current-task `assist` is **NOT_IMPLEMENTED**, with no assist smoke or adoption claim.
- **Study: COMPLETED_EXPLORATORY. Utility: INCONCLUSIVE.** sqlite-utils N/F/S each pass 2/3. csvkit N/F each pass 2 with 1 policy-rejected functional unknown; S passes 3/3. Uniform post-hoc checks pass both unknown patches, without replacing primary records.
- **Publication:** [Draft PR #47](https://github.com/Raidriar7170/hermes-skilleval/pull/47), branch `codex/hermes-two-repo-fixed-baseline`. No merge or release.
- **Validation:** clean wheel/offline paths and focused maintenance checks pass. The earlier CI code boundary passes integration gates/OpenSpec but remains **BLOCK_MERGE** on legacy pytest/release-check failures. Final HEAD CI is reported in the PR; [validation details](../../artifacts/repo-portability/validation.json) distinguish each checked source boundary.

Actual Agent source: `31ebf2456381df2cff80725f9b9bc187d41021d2`. Later delivery code discloses writable roots and hardens reporting; these improvements are not relabelled as the source of the frozen runs. Start with the [results and cost table](results.md) and [one-page Chinese retrospective](retrospective.md).

| Surface | Direct entry |
|---|---|
| Active Goal | [Execution contract](../goals/Hermes_Two_Repo_Fixed_Baseline_GitHub_Goal.md) |
| Install and commands | [Wheel, replay, verify, records, assist boundary](usage.md) |
| Fixed comparison | [Pre-run protocol](../../configs/repo-portability/confirmation-protocol.json) |
| Skills/F | [Fixed pairs](../../configs/repo-portability/fixed-v1.json), [registry](../../configs/repo-portability/skills-v1/registry.json) |
| New task qualification | [Six public qualification bundles](../../artifacts/repo-portability/qualification) |
| Development audit | [Qualification](../../artifacts/repo-portability/development-qualification) |
| Results and costs | [Readable tables](results.md), [all-start ledger](../../artifacts/repo-portability/execution-ledger.json), [separate post-hoc audit](../../artifacts/repo-portability/fixture-audit/index.json) |
| Public results | [Index](../../artifacts/repo-portability/records/index.json), [offline summary](../../artifacts/repo-portability/records/summary.json) |
| Claim boundaries | [Scope, preparation history, trust limitations](evidence-boundary.md) |
| Environment | [Clean image/versions](../../artifacts/repo-portability/environment.json), [model identity](../../artifacts/repo-portability/model-identity.json) |
| Verification boundary | [Read/write/frozen/final scope](verification-boundary.md), [checks and CI](../../artifacts/repo-portability/validation.json) |
| Retrospective | [One page](retrospective.md), [actual patch walkthrough](patch-walkthrough.md) |
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
