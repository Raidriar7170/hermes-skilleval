# Fit-only decision before calibration

Labels were frozen before scoring: 75 SUPPORTED, 13 NOT_APPLICABLE, 12 UNKNOWN,
9 inter-model disagreements. Their unit is the complete public request as one
composite requirement; they judge concrete help to a specified step, not issue
sufficiency. Two independent model contexts are not human truth.

The original rank adapter's support-specific input gave raw AUC 0.384 and
family-held-out affine calibration Brier 0.138 versus constant 0.122. The fixed
public base gave raw AUC 0.326 and held-out Brier 0.130; neither is a positive
validation result. Negative slope is permitted by the predeclared affine model;
raw scores have no prior probability or orientation guarantee.

The base-only support channel is retained as the lower-loss of these two fixed
objects, independently of the frozen rank adapter used for ordering. No other
backbone search is conducted. First base attempt loaded the prior editable
source and is excluded as INVALID_BASE_COMPARISON; the real base-v2 attempt and
original rank-adapter attempt are both retained. Source-tree commands now set
PYTHONPATH explicitly; installed-wheel commands run separately.

Only five known negative fit rows in three repair groups are available. This
is not adequate evidence to introduce a separately trained support adapter:
no pointwise training is claimed. We will fit the specified low-dimensional
calibrator on the independent support-cal families and retain its predeclared
precision/coverage acceptance rule. If no qualified operating point exists,
report NO_VALID_OPERATING_POINT, never relax the rule to activate C2.

Independent code review found incomplete critical-window/token qualification,
calibration/runtime eligibility divergence, missing outer-template identity and
base support forward undercount. These were repaired before opening calibration
scores. A fresh final fit scoring checkpoint uses the repaired input/identity;
prior scored attempts remain developmental history, not interchangeable inputs.

## Frozen calibration outcome

The repaired fixed-base scorer was sealed before support-cal scoring. Calibration
returned `NO_VALID_OPERATING_POINT`: maximum family-weighted precision among
thresholds covering two or more positive families was 0.8875, below the frozen
0.90 target. Thresholds attaining 1.0 accepted positives from only one family.
The affine fit was saved and independently JSON-reloaded with exactly matching
predictions, but its operating threshold remains null. This is a fitted model
with insufficient selection evidence, not a calibrated support success.

The four-family N+/B2/C2 comparison cannot establish the support contribution
under this failure. Preserve all twelve planned slots. Execute only the first
preselected task's three conditions as installation/fallback smoke; mark the
remaining nine `NOT_EXECUTED_NO_VALID_SUPPORT_OPERATING_POINT`. This is a
prerequisite stop, not removal of unfavorable outcomes or a smaller completed
main study. No extra task or arm-specific repetition is added. All executed
smoke attempts remain visible; utility is INCONCLUSIVE.
