# Assist smoke results

These are developer-defined software smokes on two supported public repositories, **not an N/F comparison**. Requests and controller checks were written before execution. Neither reference patches nor qualification were supplied. No historical model experiment was rerun.

| Case | Arm / requested model | Existing checks | Additional regression | Request checks, baseline → candidate | Patch / source |
|---|---|---|---|---|---|
| sqlite-utils: reject invalid chunk size before consuming input | N / gpt-5.6-sol, medium | 4 → 4 passed | 3 → 3 passed | 7 failed → 7 passed | 2 files; source unchanged; reconstruction matches |
| csvkit: null GeoJSON properties | F / gpt-5.6-sol, medium | 2 → 2 passed | 2 → 2 passed | 2 failed → 2 passed | 4 files including examples JSON; source unchanged; reconstruction matches |

- sqlite-utils: [request/config/checks](../../configs/product-assist/sqlite-utils), [actual patch](../../artifacts/product-closeout/sqlite-smoke-02/candidate.patch), [result and paired cases](../../artifacts/product-closeout/sqlite-smoke-02/result.json), [candidate origins and check execution](../../artifacts/product-closeout/sqlite-smoke-02/checks.json), [isolation](../../artifacts/product-closeout/sqlite-smoke-02/isolation.json).
- csvkit: [request/config/checks](../../configs/product-assist/csvkit), [actual patch](../../artifacts/product-closeout/csvkit-smoke-02/candidate.patch), [result and paired cases](../../artifacts/product-closeout/csvkit-smoke-02/result.json), [candidate origins and check execution](../../artifacts/product-closeout/csvkit-smoke-02/checks.json), [isolation](../../artifacts/product-closeout/csvkit-smoke-02/isolation.json).

The sqlite-utils candidate changes its own test file; controller verification still runs the original four frozen existing cases, so new candidate tests cannot replace the acceptance criterion. The csvkit patch really adds `examples/assist_null_properties.json` and passes the declared data/add policy. Its structured fixture requirement remains NOT_VERIFIED because no executable requirement check was mapped to that item; patch inspection establishes file presence only. Broader compatibility is NOT_VERIFIED in both cases; overall resolved remains null.

## Failure history and costs

[All attempt summaries](../../artifacts/product-closeout/attempts.json) retain two pre-model failures: sqlite attempt 01 was blocked by parent skill-directory detection; csvkit attempt 01 rejected class test IDs despite two actual passing tests. The source stayed unchanged and model usage was unknown/absent in those attempts. Workspace isolation and the shared pytest/JUnit mapping were corrected before the two real starts. Initial tag-based image inspection also failed; execution used the verified existing immutable image ID. No model result was discarded or retried for a better score.

Both real runs used Codex CLI 0.154.0 and the image ID recorded in each result. N mounted the five declared packages; F mounted the two fixed packages. Client-managed bundled capabilities remain SYSTEM_MANAGED_UNKNOWN, so mounted packages are not a causal attribution claim.

Observed completion-event usage is stored alongside each result in `usage-events.json`. sqlite-utils reported input 274303 (cached subset 243072), output 5170 (reasoning subset 1785); csvkit reported input 333780 (cached subset 300416), output 4227 (reasoning subset 746). Dollar costs remain unknown. Monotonic stage and request wall times are in each result; nested durations are not summed into a second cost claim. Different tasks and scopes make these unsuitable for N/F efficiency comparison.

## Installation and source identity

[Wheel acceptance](../../artifacts/product-closeout/wheel-acceptance.json) records outside-checkout installation with no PYTHONPATH and no Torch/Transformers/sentence-transformers/pytest in the controller environment. It checks CLI help, doctor, N/F recommendation, records-only, real resource preflight, and an actual Docker build/CLI/trusted class check through the installed verifier.

The raw run directories retain executed-source snapshots. Their exported hashes identify the runtime used for each smoke; later delivery includes the class-ID correction, verifier-helper binding, canary timeout cleanup and formatting. Existing scalar/function cases remain compatible; the first positive sqlite run was not repeated merely to obtain a newer source stamp. Final delivery and final CI source identities are recorded separately in the PR body.

Historical research remains UNCHANGED_INCONCLUSIVE, including both csvkit #1247 UNKNOWN records. No release, merge, router promotion or upstream adoption is implied.
