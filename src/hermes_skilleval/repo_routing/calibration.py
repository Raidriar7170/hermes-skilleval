"""Small family-weighted affine sigmoid for TEXT support, never task success.

Pure Python inference and fitting keep the ordinary runtime free of ML imports.
"""

import math

from .context import digest
from .gate import sigmoid


def input_eligible(row):
    """Shared qualification for calibration, checking and runtime acceptance."""
    return bool(
        row.get("visible")
        and not row.get("conflict")
        and row.get("context", {}).get("state") == "usable"
    )


def binary_rows(rows):
    known = []
    for row in rows:
        label = row["label"]
        if label == "UNKNOWN":
            continue
        if label not in {"SUPPORTED", "NOT_APPLICABLE", "CONTRADICTED"}:
            raise ValueError("explicit absolute support label required")
        z = row["raw_support_score"]
        if not math.isfinite(z):
            raise ValueError("finite support scores required")
        known.append({**row, "y": int(label == "SUPPORTED")})
    counts = {}
    for row in known:
        counts[row["family"]] = counts.get(row["family"], 0) + 1
    return [
        {**row, "weight": 1 / (len(counts) * counts[row["family"]])} for row in known
    ]


def fit(rows, identity, regularization=0.01):
    data = binary_rows(rows)
    if len({r["y"] for r in data}) != 2:
        raise ValueError("DATA_SIGNAL_INSUFFICIENT: both known classes required")
    mean = sum(r["weight"] * r["raw_support_score"] for r in data)
    scale = max(
        1e-8,
        math.sqrt(
            sum(r["weight"] * (r["raw_support_score"] - mean) ** 2 for r in data)
        ),
    )
    a, b = 0.0, 0.0

    # Convex ridge logistic objective, intercept unpenalized. Damped Newton.
    def loss(x, y):
        return (
            sum(
                r["weight"]
                * (
                    max(v := x * ((r["raw_support_score"] - mean) / scale) + y, 0)
                    - r["y"] * v
                    + math.log1p(math.exp(-abs(v)))
                )
                for r in data
            )
            + regularization * x * x / 2
        )

    trajectory = []
    for step in range(100):
        ga, gb, aa, ab, bb = regularization * a, 0.0, regularization, 0.0, 1e-10
        for r in data:
            x = (r["raw_support_score"] - mean) / scale
            p = sigmoid(a * x + b)
            w = r["weight"]
            ga += w * (p - r["y"]) * x
            gb += w * (p - r["y"])
            h = w * p * (1 - p)
            aa += h * x * x
            ab += h * x
            bb += h
        determinant = aa * bb - ab * ab
        da, db = (bb * ga - ab * gb) / determinant, (aa * gb - ab * ga) / determinant
        rate, before = 1.0, loss(a, b)
        while rate > 1e-8 and loss(a - rate * da, b - rate * db) > before:
            rate *= 0.5
        a, b = a - rate * da, b - rate * db
        trajectory.append(
            {"step": step, "loss": loss(a, b), "gradient_norm": math.hypot(ga, gb)}
        )
        if math.hypot(ga, gb) < 1e-9:
            break
    return {
        "schema": "text-support-sigmoid-v1",
        "a": a / scale,
        "b": b - a * mean / scale,
        "identity": identity,
        "data_sha256": digest(rows),
        "families": sorted({r["family"] for r in data}),
        "known_rows": len(data),
        "unknown_rows": len(rows) - len(data),
        "regularization": regularization,
        "trajectory": trajectory,
        "meaning": "model-judged textual applicability; not repair success probability",
    }


def predict(model, z, identity):
    if (
        model.get("schema") != "text-support-sigmoid-v1"
        or model["identity"] != identity
    ):
        raise ValueError("support calibration identity mismatch")
    if not all(math.isfinite(v) for v in (z, model["a"], model["b"])):
        raise ValueError("nonfinite support model")
    return sigmoid(model["a"] * z + model["b"])


def calibrate(rows, identity, *, precision_target=0.9, minimum_families=2):
    families = sorted({r["family"] for r in binary_rows(rows)})
    if len(families) < 3:
        raise ValueError(
            "DATA_SIGNAL_INSUFFICIENT: at least three calibration families required"
        )
    folds = []
    for family in families:
        fitted = fit([r for r in rows if r["family"] != family], identity)
        for row in rows:
            if row["family"] == family:
                folds.append(
                    {
                        **row,
                        "prediction": predict(
                            fitted, row["raw_support_score"], identity
                        ),
                    }
                )
    data = binary_rows(folds)
    positives = sum(r["weight"] * r["y"] for r in data)
    curve = []
    for threshold in sorted({r["prediction"] for r in data}):
        accepted = [
            r for r in data if r["prediction"] >= threshold and input_eligible(r)
        ]
        tp = sum(r["weight"] * r["y"] for r in accepted)
        total = sum(r["weight"] for r in accepted)
        curve.append(
            {
                "threshold": threshold,
                "precision": tp / total if total else None,
                "recall": tp / positives,
                "accepted": len(accepted),
                "positive_families": len({r["family"] for r in accepted if r["y"]}),
            }
        )
    feasible = [
        c
        for c in curve
        if c["precision"] is not None
        and c["precision"] >= precision_target
        and c["positive_families"] >= minimum_families
    ]
    chosen = (
        max(feasible, key=lambda c: (c["recall"], c["precision"], c["threshold"]))
        if feasible
        else None
    )
    model = fit(rows, identity)
    model.update(
        threshold=chosen["threshold"] if chosen else None,
        status="PROVISIONAL_DEV_CALIBRATION" if chosen else "NO_VALID_OPERATING_POINT",
        curve=curve,
        out_of_family_predictions=folds,
        precision_target=precision_target,
    )
    return model
