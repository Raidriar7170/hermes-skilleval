"""Reload new cal mapping and reconstruct locked check decisions without model calls."""

import argparse
import math
import json
from pathlib import Path
from hermes_skilleval.repo_routing.applicability_data import (
    read_json,
    read_rows,
    write_json,
    records_equal,
    targets,
    group_weights,
    file_hash,
)
from hermes_skilleval.repo_routing.independent_validation import calibrations, select
from hermes_skilleval.repo_routing.gate import sigmoid

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--root", type=Path, required=True)
p.add_argument("--protocol", type=Path, required=True)
p.add_argument("--baseline", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
rule = read_json(a.protocol)
lock = read_json(a.root / "policy-lock.json")
scores = read_json(a.root / "cal-scores.json")
labels = sorted(read_rows(a.root / "cal-labels.jsonl"), key=lambda r: r["row_id"])
assert lock["cal_scores_sha256"] == file_hash(a.root / "cal-scores.json")
assert lock["cal_labels_sha256"] == file_hash(a.root / "cal-labels.jsonl")
assert lock["protocol_sha256"] == file_hash(a.protocol)
stream = {r["row_id"]: r for r in scores["rows"]}
new = calibrations(labels, stream, rule)
assert records_equal(json.loads(json.dumps(new)), lock["calibrations"])
# Independently implement weighted threshold-curve arithmetic and selection.
curve_checks = {}
known = [r for r in labels if targets(r)[0] is not None]
weights = dict(zip((r["row_id"] for r in known), group_weights(known)))
for name, cal in lock["calibrations"].items():
    pp = {
        r["row_id"]: sigmoid(
            cal["mapping"]["a"] * stream[r["row_id"]]["logits"][name]
            + cal["mapping"]["b"]
        )
        for r in labels
    }
    qualified = []
    for saved in cal["precision_curve"]:
        accepted = [
            r
            for r in labels
            if stream[r["row_id"]]["input_eligible"]
            and pp[r["row_id"]] >= saved["threshold"]
        ]
        ka = [r for r in accepted if targets(r)[0] is not None]
        mass = sum(weights[r["row_id"]] for r in ka)
        tp = sum(weights[r["row_id"]] for r in ka if targets(r)[0] == 1)
        vals = {
            "accepted": len(accepted),
            "known_accepted": len(ka),
            "unknown_accepted": len(accepted) - len(ka),
            "groups": len({r["repair_group_id"] for r in ka}),
            "precision": tp / mass if mass else None,
            "coverage": mass / sum(weights.values()) if weights else 0,
            "known_false_accepts": sum(targets(r)[0] == 0 for r in ka),
        }
        for k, v in vals.items():
            assert (
                v == saved[k]
                or isinstance(v, float)
                and math.isclose(v, saved[k], abs_tol=1e-10)
            ), (name, k, v, saved[k])
        op = rule["operating_point"]
        if (
            vals["precision"] is not None
            and vals["precision"] >= op["target_precision"]
            and vals["groups"] >= op["min_accepted_groups"]
            and vals["known_accepted"] >= op["min_accepted_rows"]
            and vals["coverage"] >= op["min_known_coverage"]
            and vals["unknown_accepted"] <= op["max_unknown_acceptance"]
        ):
            qualified.append(saved)
    selected = (
        max(qualified, key=lambda x: (x["coverage"], x["threshold"]))
        if qualified and cal["mapping"]["status"] == "FITTED"
        else None
    )
    assert (selected["threshold"] if selected else None) == cal["threshold"]
    curve_checks[name] = len(cal["precision_curve"])
result = {
    "status": "MATCHED",
    "model_calls": 0,
    "cal_rows": len(labels),
    "curve_checks": curve_checks,
    "scope": "new-cal software reload; not a second independent study",
}
check = a.root / "check-scores.json"
if check.exists():
    pred = read_json(check)
    assert read_json(check.with_suffix(".lock.json"))[
        "predictions_sha256"
    ] == file_hash(check)
    assert pred["lock_sha256"] == file_hash(a.root / "policy-lock.json")
    expected = {r["row_id"]: dict(r) for r in pred["rows"]}
    for r in expected.values():
        for name, c in lock["calibrations"].items():
            prob = sigmoid(c["mapping"]["a"] * r["logits"][name] + c["mapping"]["b"])
            assert abs(prob - r["scores"][name + "_calibrated"]) < 1e-10
            if name == "A":
                assert r["policy_accepts"] == bool(
                    r["input_eligible"]
                    and c["threshold"] is not None
                    and prob >= c["threshold"]
                )
    assert (
        select(
            pred["rows"],
            expected,
            read_json(a.baseline)["fixed"],
            lock["calibrations"]["A"]["threshold"],
        )
        == pred["selections"]
    )
    result["check_decisions_reconstructed"] = len(pred["rows"])
write_json(a.output, result)
print(json.dumps(result))
