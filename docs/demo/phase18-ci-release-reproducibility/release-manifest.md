# Phase 18 Release Reproducibility Manifest

- Status: `PASS`
- Release decision: `KEEP_BASELINE`
- Selected router: `baseline-minilm`
- Candidate router: `finetuned-embedding`
- Approved for default: `False`
- Release check status: `PASS`

## Reproducible Artifacts

| Path | Size Bytes | SHA-256 |
|---|---:|---|
| `docs/demo/phase16-blind-validation/regression-summary.json` | 1947 | `c6063a141814d1f986c79f6b06c0a4fc81f4871583a36db27443ca974b55c8f6` |
| `docs/demo/phase16-blind-validation/route-diffs.jsonl` | 16435 | `d787dd8b1a51964ef0370e4f59897011757b16b8e28cf146e799e44d84719333` |
| `docs/demo/phase17-calibrated-release-selector/release-decision.json` | 9679 | `47c951630cae73c96f7ceae98c16ce7e15c263bac0b85abf4b9264bfcf24abdd` |
| `docs/demo/phase17-calibrated-release-selector/release-decision.md` | 1908 | `90a76119c7c9ace581283d7366b7cf7a633585df70bc0aa39f092c6ec766dbf3` |
| `docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl` | 6026 | `164afe009addfb044f496bb0632f5e0fd1b3723719139d603dfaad5b60f45a2d` |
| `docs/demo/phase18-ci-release-reproducibility/release-check-summary.json` | 903 | `bad33f51a9b613740ad5d47c1a954165e34c5d98726a2ba11293e5c166084acf` |

## Reasons

- release decision, public release check, and artifact hashes are reproducible
