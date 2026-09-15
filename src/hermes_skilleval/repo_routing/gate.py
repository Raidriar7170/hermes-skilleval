"""Cheap action models serialized as JSON; no heavy-model or array dependency."""

import json
import math
from pathlib import Path

ACTIONS = ("N", "F", "R")
FEATURES = (
    "request_chars",
    "request_lines",
    "files",
    "symbols",
    "tests",
    "entrypoints",
    "truncated",
    "mentions_cli",
    "mentions_schema",
    "mentions_import",
)


def features(request, context):
    lower = request.lower()
    return [
        float(v)
        for v in (
            len(request),
            len(request.splitlines()),
            context["files_scanned"],
            len(context["matched_symbols"]),
            len(context["related_public_tests"]),
            len(context["entrypoints"]),
            bool(context["truncated"]),
            "cli" in lower or "command" in lower,
            "schema" in lower or "table" in lower,
            "import" in lower or "csv" in lower,
        )
    ]


def sigmoid(x):
    return 1 / (1 + math.exp(-max(-35, min(35, x))))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def normalize(x, model):
    if len(x) != len(FEATURES) or any(not math.isfinite(v) for v in x):
        raise ValueError("invalid cheap feature vector")
    return [1.0] + [(v - m) / s for v, m, s in zip(x, model["means"], model["scales"])]


def _fit(xs, ys, weights, *, logistic, steps=500):
    coef = [0.0] * len(xs[0])
    for _ in range(steps):
        grad = [0.0] * len(coef)
        for x, y, w in zip(xs, ys, weights):
            prediction = sigmoid(dot(x, coef)) if logistic else dot(x, coef)
            for j, v in enumerate(x):
                grad[j] += w * (prediction - y) * v
        for j in range(len(coef)):
            coef[j] -= 0.03 * (grad[j] / sum(weights) + (0.02 * coef[j] if j else 0))
    return coef


def fit(rows, r_version):
    if not rows or any(
        r["split"] != "gate-fit" or r["r_version"] != r_version for r in rows
    ):
        raise ValueError("frozen R gate-fit rows required")
    if any(
        r["action"] not in ACTIONS or r.get("source") != "real_execution" for r in rows
    ):
        raise ValueError("real action feedback required")
    grouped = {}
    for row in rows:
        x = row["features"]
        if len(x) != len(FEATURES) or any(not math.isfinite(v) for v in x):
            raise ValueError("invalid cheap features")
        family = row["repair_family"]
        if family in grouped and grouped[family] != x:
            raise ValueError(
                "same-family features differ; aggregate task observations explicitly"
            )
        grouped[family] = x
    means = [
        sum(x[j] for x in grouped.values()) / len(grouped) for j in range(len(FEATURES))
    ]
    scales = [
        max(
            1.0,
            (sum((x[j] - means[j]) ** 2 for x in grouped.values()) / len(grouped))
            ** 0.5,
        )
        for j in range(len(FEATURES))
    ]
    times = [r["seconds"] for r in rows if r.get("seconds") is not None]
    tokens = [r["tokens"] for r in rows if r.get("tokens") is not None]
    model = {
        "schema": "repo-gate-v1",
        "features": list(FEATURES),
        "r_version": r_version,
        "means": means,
        "scales": scales,
        "time_scale": max(1.0, sum(times) / len(times)) if times else 1.0,
        "token_scale": max(1.0, sum(tokens) / len(tokens)) if tokens else 1.0,
        "actions": {},
        "fit_families": sorted(grouped),
        "calibration_families": [],
        "fallback": "N",
        "lambda_time": 0.05,
        "lambda_tokens": 0.02,
        "calibrated": False,
    }
    for action in ACTIONS:
        subset = [r for r in rows if r["action"] == action]
        if {r["repair_family"] for r in subset} != set(grouped):
            raise ValueError("complete action feedback required (unknowns retained)")
        counts = {f: sum(r["repair_family"] == f for r in subset) for f in grouped}
        quality = [r for r in subset if r.get("quality") is not None]
        if any(r["quality"] not in (0, 1) for r in quality):
            raise ValueError("binary trusted quality or null required")
        labels = {r["quality"] for r in quality}
        if len(labels) < 2:
            # Smoothed constant supports degenerate data without invented labels.
            p = (
                sum(r["quality"] / counts[r["repair_family"]] for r in quality) + 1
            ) / (sum(1 / counts[r["repair_family"]] for r in quality) + 2)
            coef = [math.log(p / (1 - p))] + [0.0] * len(FEATURES)
        else:
            coef = _fit(
                [normalize(r["features"], model) for r in quality],
                [r["quality"] for r in quality],
                [1 / counts[r["repair_family"]] for r in quality],
                logistic=True,
            )
        entry = {
            "quality": coef,
            "quality_signal": "INSUFFICIENT" if len(labels) < 2 else "OBSERVED",
            "quality_n": len(quality),
            "temperature": 1.0,
        }
        for field, scale_key in [("seconds", "time_scale"), ("tokens", "token_scale")]:
            known = [r for r in subset if r.get(field) is not None]
            if any(not math.isfinite(r[field]) or r[field] < 0 for r in known):
                raise ValueError("invalid observed cost")
            entry[field] = (
                _fit(
                    [normalize(r["features"], model) for r in known],
                    [r[field] / model[scale_key] for r in known],
                    [1 / counts[r["repair_family"]] for r in known],
                    logistic=False,
                )
                if known
                else None
            )
        model["actions"][action] = entry
    model["gate_data_signal"] = (
        "INSUFFICIENT"
        if any(a["quality_signal"] == "INSUFFICIENT" for a in model["actions"].values())
        else "OBSERVED"
    )
    return model


def predict(x, model):
    x = normalize(x, model)
    return {
        a: {
            "quality_estimate": sigmoid(dot(x, m["quality"]) / m["temperature"]),
            "time_scaled": max(0, dot(x, m["seconds"]))
            if m["seconds"] is not None
            else None,
            "tokens_scaled": max(0, dot(x, m["tokens"]))
            if m["tokens"] is not None
            else None,
        }
        for a, m in model["actions"].items()
    }


def calibrate(rows, model):
    if not rows or any(
        r["split"] != "gate-calibration"
        or r["r_version"] != model["r_version"]
        or r.get("source") != "real_execution"
        for r in rows
    ):
        raise ValueError("independent real calibration rows required")
    families = {r["repair_family"] for r in rows}
    if families & set(model["fit_families"]):
        raise ValueError("fit/calibration family leakage")
    for a in ACTIONS:
        if {r["repair_family"] for r in rows if r["action"] == a} != families:
            raise ValueError("incomplete calibration actions")
    metrics = {}
    for a in ACTIONS:
        valid = [r for r in rows if r["action"] == a and r.get("quality") is not None]
        # Do not fit high-variance temperature to a tiny one-class calibration set.
        predictions = [
            predict(r["features"], model)[a]["quality_estimate"] for r in valid
        ]
        metrics[a] = {
            "n": len(valid),
            "brier": sum((p - r["quality"]) ** 2 for p, r in zip(predictions, valid))
            / len(valid)
            if valid
            else None,
            "calibration": "INSUFFICIENT"
            if len(families) < 6
            else "CHECKED_UNCALIBRATED",
        }
    model["calibration_families"] = sorted(families)
    model["calibration_metrics"] = metrics
    model["calibrated"] = all(v["n"] > 0 for v in metrics.values())
    model["probability_claim"] = False
    return model


def decide(x, model, r_version, *, resources=True, supported=True):
    if model.get("schema") != "repo-gate-v1" or model.get("features") != list(FEATURES):
        raise ValueError("unsupported gate feature schema")
    reason = None
    if r_version != model["r_version"]:
        reason = "r_version_mismatch"
    elif not resources:
        reason = "heavy_assets_missing"
    elif not supported:
        reason = "unsupported_context"
    elif not model["calibrated"]:
        reason = "calibration_not_completed"
    elif model["gate_data_signal"] == "INSUFFICIENT":
        reason = "gate_data_signal_insufficient"
    predictions = predict(x, model)
    if any(
        v["time_scaled"] is None or v["tokens_scaled"] is None
        for v in predictions.values()
    ):
        reason = reason or "missing_cost_feedback"
    chosen = model["fallback"]
    if not reason:
        utilities = {
            a: v["quality_estimate"]
            - model["lambda_time"] * v["time_scaled"]
            - model["lambda_tokens"] * v["tokens_scaled"]
            for a, v in predictions.items()
        }
        chosen = max(ACTIONS, key=lambda a: utilities[a])
    return {
        "action": chosen,
        "fallback_reason": reason,
        "predictions": predictions,
        "r_version": r_version,
    }


def main():
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fit", type=Path, required=True)
    p.add_argument("--calibration", type=Path, required=True)
    p.add_argument("--r-version", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    def read(path):
        return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

    model = calibrate(read(a.calibration), fit(read(a.fit), a.r_version))
    with a.output.open("x") as stream:
        json.dump(model, stream, indent=2)


if __name__ == "__main__":
    main()
