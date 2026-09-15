# One actual patch: csvkit #1219, fixed baseline F

The public report says `csvstack -z ...` raises a `field_size_limit` keyword
error. The base builds reader keyword arguments with that value, but the reader
path does not accept it as a constructor keyword.

The F candidate changes `csvkit/cli.py`: import the standard `csv` module,
apply the requested limit through `csv.field_size_limit(...)`, and omit it from
the reader keyword loop. It also adds its own csvstack and csvpy regression
cases. Those candidate-written tests are part of the patch, not the acceptance
oracle.

The controller saves the patch before verification, recreates a new base,
applies the saved patch, builds offline in a separate container, then executes
its independently held trusted tests. Two target cases cover ordinary and
over-default-limit fields with the requested option; two related cases preserve
ordinary stacking. All four pass on this candidate. The same trusted target
fails on base, while the reference fix passes. This rules out a no-op or an
already-installed repaired csvkit for this checked slice.

The controller has not independently certified csvpy's full behavior, all
csvkit commands, or all possible process-global field-limit interactions. The
candidate's extra tests do not enlarge the trusted acceptance claim. F's skill
exposure plus a correct patch in one attempt also does not prove the skill caused
the repair.

The final result index links the original candidate patch, sanitized JUnit,
structured skill-read observations and token/timing record by this run ID:
`confirm-csvkit-1219-F-001`.
