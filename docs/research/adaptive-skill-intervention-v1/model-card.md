# ASI v1 model card

Status: real CPU fitting and independent process reload completed. Final policy utility remains pending the frozen 96-trajectory comparison. The existing deployment default is unchanged.

The frozen MiniLM encoder feeds small gain and waiting heads. The gain supervision is measured terminal utility relative to the matching no-intervention tail. Training uses 12 mechanisms and 80 aggregated state/action rows, derived from 91 valid paired repeats. Four development mechanisms supply 30 aggregated rows for the predeclared 80/160-epoch selection. Neither final-test outcomes nor hidden checker information enter policy state or model selection.

| Model | Selected epochs | Gain parameter L2 change | Wait parameter L2 change | Development task-macro MSE |
| --- | ---: | ---: | ---: | ---: |
| Full | 80 | 7.181362 | 4.217676 | 0.230540 |
| No-state | 80 | 4.250988 | 1.198854 | 0.216440 |
| State-only diagnostic | 160, fixed | 8.972044 | Not fitted | 0.285536 |

The zero-gain baseline scores 0.216876 MSE and the training skill/stage prior scores 0.204755. Thus the complete gain model does not beat these cheap development baselines. Loss reduction and nonzero parameter updates establish actual fitting, not incremental task utility. The state-only diagnostic is not an additional final-test arm.

Full-model training loss decreases from 0.014627 to 0.010850; its waiting loss decreases from 0.019409 to 0.000073. The 26 waiting targets use task-excluded downstream predictions, rather than the realized best future action. Missing downstream evidence and unknown native termination are excluded from targets; terminal E2 has zero continuation opportunity. Full and no-state heads retain separate training and provenance records.

Fresh-process probes match saved expected outputs for full, no-state and state-only models, with identities bound to the training records, protocol, encoder and payloads. The full probe returns gain -0.282985 and waiting value 0.187719. This verifies reload; actual waiting-model participation and decisions must be reported from the final runtime records.

Measured offline fitting costs 30.899 seconds wall time and 30.447 seconds process CPU time. This includes encoder loading/features, fixed development selection, nested cross-fitting, final heads and the state-only diagnostic. It excludes Agent collection and independent reload. Per-trajectory policy loading is charged to the final trajectory budget; shared encoder/catalog initialization is reported separately.

The sample is small, correlated, drawn from known repositories, and mostly consists of quality ties. A versioned checker repair affects four training mechanisms. No held-out-project, contamination-free, deployment, or demonstrated-gain claim follows from this model card. Final export will include training curves, reload receipts and model identities; weights and private Agent histories remain outside Git.
