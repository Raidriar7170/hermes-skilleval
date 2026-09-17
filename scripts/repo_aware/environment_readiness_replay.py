"""Fresh-process cal-only arithmetic reload; no model or old check selection."""

import argparse
import json
import math
from pathlib import Path
import time

from hermes_skilleval.repo_routing.applicability_data import (
    read_json,
    read_rows,
    group_weights,
    targets,
    write_json,
)
from hermes_skilleval.repo_routing.applicability_eval import (
    axis_metrics,
    fit_calibration,
)

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--evidence", type=Path, required=True)
p.add_argument("--labels", type=Path, required=True)
p.add_argument("--rule", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
started = time.monotonic()
scores = read_json(a.evidence / "a-cal-preflight-scores.json")
cal = read_json(a.evidence / "a-calibration-preflight-calibration.json")
preflight = read_json(a.evidence / "a-calibration-preflight.json")
rule = read_json(a.rule)
rows = [r for r in read_rows(a.labels) if r["split"] == "cal"]
by = {r["row_id"]: r for r in scores["rows"]}
facts = {r["row_id"]: r for r in preflight["rows"]}
assert set(by) == set(facts) == {r["row_id"] for r in rows}
assert scores["input_identity"] == cal["input_identity"] == preflight["input_identity"]
assert (
    scores["environment_binding"]
    == cal["environment_binding"]
    == preflight["environment_binding"]
)
assert all(
    by[r["row_id"]]["public_input_identity"]
    == facts[r["row_id"]]["public_input_identity"]
    for r in rows
)
logits = [by[r["row_id"]]["logits"] for r in rows]
assert all(len(z) == 1 for z in logits)
refit = fit_calibration(rows, logits, 0, rule["calibration"])
assert all(abs(refit[k] - cal["mapping"][k]) < 1e-10 for k in ("a", "b", "loss"))
raw = [[1 / (1 + math.exp(-z[0]))] for z in logits]
pp = [
    [1 / (1 + math.exp(-(cal["mapping"]["a"] * z[0] + cal["mapping"]["b"])))]
    for z in logits
]
known = [r for r in rows if targets(r)[0] is not None]
weights = dict(zip((r["row_id"] for r in known), group_weights(known)))
curve = []
for threshold in [1.0000001] + sorted({v[0] for v in pp}, reverse=True):
    accepted = [
        r
        for r, v in zip(rows, pp)
        if facts[r["row_id"]]["eligible"] and v[0] >= threshold
    ]
    ka = [r for r in accepted if targets(r)[0] is not None]
    mass = sum(weights[r["row_id"]] for r in ka)
    tp = sum(weights[r["row_id"]] for r in ka if targets(r)[0] == 1)
    curve.append(
        {
            "threshold": threshold,
            "accepted": len(accepted),
            "known_accepted": len(ka),
            "unknown_accepted": len(accepted) - len(ka),
            "groups": len({r["repair_group_id"] for r in ka}),
            "precision": tp / mass if mass else None,
            "coverage": mass / sum(weights.values()),
            "known_false_accepts": sum(targets(r)[0] == 0 for r in ka),
        }
    )
for actual, saved in zip(curve, cal["precision_curve"]):
    for k, v in actual.items():
        assert saved[k] == v or (isinstance(v, float) and abs(saved[k] - v) < 1e-12), (
            k,
            v,
            saved[k],
        )
op = rule["operating_point"]
qualified = [
    r
    for r in curve
    if r["precision"] is not None
    and r["precision"] >= op["target_precision"]
    and r["groups"] >= op["min_accepted_groups"]
    and r["known_accepted"] >= op["min_accepted_rows"]
    and r["coverage"] >= op["min_known_coverage"]
    and r["unknown_accepted"] <= op["max_unknown_acceptance"]
]
chosen = (
    max(qualified, key=lambda r: (r["coverage"], r["threshold"])) if qualified else None
)
assert (chosen["threshold"] if chosen else None) == cal["threshold"]
result = {
    "schema": "environment-cal-reload-v1",
    "status": "MATCHED",
    "scope": "same cal inputs only; retrospective software verification",
    "rows": len(rows),
    "known": len(known),
    "unknown": len(rows) - len(known),
    "groups": len({r["repair_group_id"] for r in rows}),
    "raw_applicability": axis_metrics(rows, raw),
    "calibrated_applicability": axis_metrics(rows, pp),
    "operating_point": chosen,
    "curve_rows_checked": len(curve),
    "refit": refit,
    "forward_calls": 0,
    "model_constructions": 0,
    "calibration_fits": 1,
    "elapsed_seconds": time.monotonic() - started,
}
write_json(a.output, result)
print(json.dumps({"status": result["status"], "operating_point": chosen}))
