# Stage 1 Audit Note

Stage 1 external SkillRouter evidence reached an interpretable gate status:
`REVIEW_REQUIRED` with `KEEP_BASELINE`.

The frozen plan recorded `plan.git.dirty=true` because evidence collection had
generated/untracked artifact paths in the working tree, including the local real
SkillRouter Eval Core input directory:

- `artifacts/v0.3/v0.3-stage1-external-20260628T105038Z/`
- generated Stage 1 artifact outputs under `artifacts/v0.3/`

The dirty state was not caused by `src/`, `configs/`, `tests/`, scorer,
matrix, evidence-gate, router-promotion, or live-agent code changes.

Do not rerun Stage 1 unless frozen hash verification fails.
