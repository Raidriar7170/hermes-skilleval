# CI failure migration

Baseline: `10f8aa65b75fdcaf988d4a2e953ed02628b3c400`. A detached diagnostic checkout reproduced **25 failed / 1190 passed**. No historical Agent run was repeated.

| Failure group / old protection | Root cause | Current assertion / fix | Preserved guarantee |
|---|---|---|---|
| release-check CLI, Phase18, release decision/final approval hashes, protected baseline | Default generation overwrote three tracked Phase18 files; later tests read the polluted files | CLI uses a fresh temporary directory; explicit historical output is rejected before any writes; CI uses RUNNER_TEMP; byte and Git-status regression | Frozen Phase17/18 values and input hashes still checked, including KEEP_BASELINE |
| Phase9/10/12 checkboxes; Phase14–18 README wording | Homepage redesign removed historical captions | Stage-specific docs, timeline links and original artifact tests retain stage facts | Original task counts, guards, regression counts, provenance and publication facts unchanged |
| Project surface / global 698 count / v0.2.0 homepage | Tests treated a historical total and English page layout as permanent current state | Both language homepages validate installation, supported repositories, functional commands, local links, architecture and actual CI navigation | Historical count documents remain; current homepage cannot display an unversioned static test badge |
| overclaim scan / release check | English-only whole-line exemption flagged Chinese denial; could hide a second affirmative clause | Deterministic clause classification: negative exempt, affirmative FAIL, ambiguous REVIEW_REQUIRED; mixed, wrapped and quoted regression cases | No README path bypass; affirmatives still block |

Current generator tests use temporary fixtures. Historical consistency tests still run in the full suite. Default `skilleval release-check` prints its newly generated report location; explicit `--phase17-output-dir` / `--release-output-dir` remain available outside protected evidence directories. It does not update the historical release record.

Focused C1 validation: 31 release/summary/scanner cases passed; 32 current-surface cases passed. First full after-run: 1230 passed, one new test expected an exception instead of CLI error code; the protected write was correctly rejected. Final counts and exact-HEAD CI belong in the final validation record and PR body.
