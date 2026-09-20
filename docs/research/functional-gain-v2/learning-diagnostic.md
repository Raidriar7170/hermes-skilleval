# Functional gain v2: train/dev evidence

This is a completed train/dev diagnostic, not a final test result. The complete collection contains 192 registered tails, 191 known functional outcomes and one unknown. Of 96 skill/no-op contrasts, 92 tie, two damage and two remain unknown. No functional rescue was observed.

Both independently trained representations selected 80 epochs from the frozen 80/160 grid. Each uses 58 aggregated training rows from 12 tasks and 18 development rows from four tasks; raw repeats remain in the collection. Two unknown training contrasts are retained as missing labels, not imputed zero.

| Predictor | Dev task-macro MSE | Dev task-macro MAE |
|---|---:|---:|
| full | 0.01776960 | 0.08978190 |
| task-only | 0.00251759 | 0.02828612 |
| zero | 0.00000000 | 0.00000000 |
| prior | 0.04861111 | 0.06250000 |

Every observed development gain label is zero, so the zero baseline has zero error. Full is worse than task-only on these development errors; neither fitted model improves on zero. These diagnostics do not authorize removing any frozen final comparator or changing the margin.

Gain parameter L2 changes are 5.947113513946533 (full) and 3.632460355758667 (task-only). Training curves, family-held-out wait targets and independent reload matches are in the JSON receipts. Training took 21.498341083002742 seconds. No model weights are exported.

Runtime model summaries omit the local encoder path and retain the original metadata SHA-256; they are not replacements for the original runtime model files. Model identities in the independent reload receipt and final policy freeze refer to the original runtime assets.

Status: TRAINED_AND_RELOADED. Functional, state and waiting benefit claims remain unestablished pending the registered final matrix and mechanism experiments.
