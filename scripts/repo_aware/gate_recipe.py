"""Full-feedback signal boundary for the small, pre-confirmation gate recipe."""

from collections import defaultdict

from hermes_skilleval.repo_routing.gate import fit, calibrate


def train(fit_rows, calibration_rows, r_version):
    model = calibrate(calibration_rows, fit(fit_rows, r_version))
    grouped = defaultdict(lambda: defaultdict(list))
    for row in fit_rows:
        if row.get("quality") is not None:
            grouped[row["repair_family"]][row["action"]].append(row["quality"])
    contrasts = 0
    for actions in grouped.values():
        if set(actions) == {"N", "F", "R"}:
            means = [sum(values) / len(values) for values in actions.values()]
            contrasts += len(set(means)) > 1
    model["quality_action_contrast_families"] = contrasts
    model["signal_boundary"] = (
        "Zero observed within-family quality contrasts cannot establish when R is needed. Cost variation alone does not override this conservative fallback."
    )
    if contrasts == 0:
        model["gate_data_signal"] = "INSUFFICIENT"
        model["signal_reason"] = "no_observed_action_quality_contrast"
    return model
