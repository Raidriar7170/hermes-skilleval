# Scope and evidence boundary

Baseline: `49a7dfeb9efc8dcce112c829d4d7136c5bd281a3` (clean, Draft PR48).
Read scope: this repository, the original advisory replay local task/run assets,
and the two public issues plus fixed-base documentation/source.
Write scope: new acceptance-semantics-v1 config/artifact/document directories,
new acceptance adapter and tests, maintenance CLI dispatch, active Goal,
and the existing OpenSpec change continuation; old documentation navigation only.
The existing .gitattributes evidence-whitespace policy is extended only to new
raw replayed JUnit and the pinned dependency source excerpt.
Frozen scope: all pre-existing artifacts/configs, original patches, JUnit,
fixed task bases/references/trusted fixtures and original private run records.
Final repository scope: complete tracked delta from the baseline; no unrelated
tracked changes allowed. Private execution copies and logs stay outside Git.

32 old records are inventoried; only the two affected tasks (16 candidates) are
re-executed. POSTHOC_REVALIDATION_OF_FROZEN_PATCHES; zero new repair Agent calls,
routing forwards, training and calibration. No support certification or new
independent gain claim. Independent review is required before closure because
this publishes execution evidence and handles candidate/judge isolation.

Raw replayed JUnit retains pytest failure-text whitespace; it is not normalized
to satisfy diff whitespace lint. The frozen dependency source excerpt likewise
retains its original trailing newline. Code and authored docs pass scoped diff
whitespace checks. No legacy evidence index or source binding was refreshed.
