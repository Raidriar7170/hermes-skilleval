# Phase 18: CI Release Reproducibility Pack

Phase 18 turns the Phase 17 release selector into a CI-reproducible release
gate. It does not retrain the fine-tuned embedding router, change Phase 16
blind-validation results, or approve `finetuned-embedding` as the default.

## Scope

Committed artifacts live under
`docs/demo/phase18-ci-release-reproducibility/`:

- `release-manifest.json`
- `release-manifest.md`
- `release-check-summary.json`

The release-check command reruns the Phase 17 selector, reruns the public
release guard, and records hashes for the input and generated release artifacts.

## Result

The current Phase 18 manifest reports `PASS`. The release decision remains
`KEEP_BASELINE`, the selected default router remains `baseline-minilm`, and
`finetuned-embedding` remains not approved for default routing.

## Reproduce

```bash
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

GitHub Actions runs the same release reproducibility command after the
lightweight pytest suite.

## Boundaries

This remains a self-built Hermes-style skill-routing release gate. It is not a
standard third-party benchmark, does not establish a leading outside result,
and should not be described as production readiness evidence.
