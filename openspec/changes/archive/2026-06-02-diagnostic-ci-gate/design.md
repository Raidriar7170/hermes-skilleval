## Context

The repository now has a Diagnostic Onboarding Path with stable JSON artifacts:
scan, lint, inspect, route, and a static dashboard. `CONTEXT.md` defines CI gate
productization as the follow-up after the Diagnostic Artifact Contract, while
also warning that P1 should not become a hosted product or runtime router by
default. The current `.github/workflows/validate.yml` already runs pytest and the
Phase 18 release reproducibility gate.

## Goals / Non-Goals

**Goals:**

- Provide a deterministic `skilleval diagnostic-ci-gate` command that exits
  non-zero when diagnostic artifacts exceed explicit thresholds.
- Keep gate semantics explainable: fail on artifact contract problems, lint
  severity counts, conflict cluster counts, route risk flags, missing evidence,
  or zero routed candidates.
- Add a lightweight GitHub Actions job that demonstrates how to validate
  committed diagnostic demo artifacts through the gate.
- Preserve the existing Phase 16-18 release-check workflow and conservative
  `KEEP_BASELINE` story.

**Non-Goals:**

- Publishing a standalone Marketplace Action.
- Adding PR comment annotations, GitHub API calls, or merge automation.
- Treating conflict clusters as definitive duplicates.
- Requiring network access, model downloads, or hosted services.
- Changing benchmark router defaults or promoting a learned router.

## Decisions

- **Gate over existing artifacts, not raw source.** The command reads scan, lint,
  inspect, and route artifacts instead of reinterpreting skill source directly.
  This keeps CI aligned with the Diagnostic Artifact Contract and allows users to
  regenerate artifacts however they prefer.
- **Explicit thresholds only.** Defaults are conservative and explainable, while
  CLI flags let maintainers tune acceptable warning/risk levels. A threshold of
  zero blocks that issue category.
- **Demo workflow inside existing validate.yml.** A separate Marketplace Action
  would require release and versioning decisions. The first useful CI surface is
  a repo-local workflow step that reads committed demo artifacts and writes
  fresh reports to `$RUNNER_TEMP`.
- **Markdown + JSON report.** The gate writes machine-readable JSON and a compact
  Markdown summary so local and GitHub logs remain inspectable.

## Risks / Trade-offs

- **False positives from strict thresholds** -> Make thresholds explicit in the
  command and docs rather than implying universal policy.
- **Generated demo artifacts can create noisy diffs** -> The workflow does not
  regenerate the demo pack because current diagnostic artifacts contain
  `generated_at` timestamps. A later phase can add deterministic timestamps if
  regenerate-and-diff CI becomes necessary.
- **Users may confuse CI gate with production runtime routing** -> Docs and specs
  state that this is artifact validation, not an agent runtime router.
- **Large skill libraries may need richer policy** -> Keep v1 small and let later
  OpenSpec changes add baselines, PR annotations, or Marketplace Action packaging.
