# Verification and publication boundary

Baseline: `8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552` (inspected public main).
Frozen Agent executable source: `31ebf2456381df2cff80725f9b9bc187d41021d2`.
Delivery source is the HEAD containing this document; executed snapshots are
checked against the frozen source, not silently relabelled as latest source.

- **Read scope:** this checkout's tracked configuration, source, tests and
  documents; task-specific private upstream/task/qualification/run evidence,
  existing local model assets and GitHub PR/CI state. No other private material
  is included in the export.
- **Write scope:** `src/hermes_skilleval`, named maintenance tests,
  `scripts/repo_workflow`, imported container/environment wrappers,
  `configs/repo-portability`, the imported seccomp profile,
  `artifacts/repo-portability`, `docs/repo-portability`, the designated Goal,
  `openspec/changes/hermes-two-repo-fixed-baseline`, `pyproject.toml`,
  `.gitattributes`, `.gitignore`, `README.md`, `README_EN.md`.
- **Frozen asset scope:** committed confirmation specs/public requests,
  qualification/trusted tests, registry/skill packages, F/protocol, exact local
  model file identities, original run/capture/check files and executed snapshots.
  Post-hoc audit output is separate from the original confirmation record.
- **Final repository scope:** the complete tracked delta from the explicit
  baseline, including tracked generated evidence, additions, deletions and modes.
  Untracked caches/builds/private logs and model weights are not public artifacts.

The final integrity check reads fresh SHA-256 content for all changed tracked
objects and declared frozen/public evidence, plus a separate fresh comparison
of local model assets to the published pre-run identities. Its private report
avoids a recursive self-hash. Hashes provide consistency, not functional success
or protection against wholesale controller fabrication. Focused behavioral
checks and review provide different evidence; their actual results are in
[validation.json](../../artifacts/repo-portability/validation.json).

Public history scanning examines every new reachable commit, not only HEAD.
It is supplemented by allowlisted export and read-only evidence/privacy review;
pattern scanning alone does not establish that all possible private data is absent.
The original local prerequisite branch/history is not merged into this branch.
No upstream write, merge, release, training, global configuration change or
new algorithm campaign is part of this closeout.
