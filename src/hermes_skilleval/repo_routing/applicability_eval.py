"""Group-weighted dual-axis baselines and records-only metrics (no model imports)."""

from __future__ import annotations
from collections import Counter, defaultdict
import math
import random
import re

from .applicability_data import group_weights, targets
from .gate import sigmoid


def axis_metrics(rows, predictions, axis=0):
    if len(rows) != len(predictions):
        raise ValueError("aligned predictions required")
    known = [(r, p) for r, p in zip(rows, predictions) if targets(r)[axis] is not None]
    unknown = sum(
        targets(r)[axis] is None
        and (axis == 0 or r["applicability_label"] == "APPLICABLE")
        for r in rows
    )
    outside_axis = len(rows) - len(known) - unknown
    weights = group_weights([r for r, _ in known]) if known else []
    data = [(targets(r)[axis], p[axis], w) for (r, p), w in zip(known, weights)]
    if not data:
        return {
            "known": 0,
            "unknown": unknown,
            "outside_conditional_axis": outside_axis,
            "brier": None,
            "log_loss": None,
            "auc": None,
            "auprc": None,
        }
    den = sum(w for _, _, w in data)
    data = [(y, p, w / den) for y, p, w in data]
    if any(not math.isfinite(p) or not 0 <= p <= 1 for _, p, _ in data):
        raise ValueError("invalid probabilities")
    pos = sum(y * w for y, _, w in data)
    neg = 1 - pos
    auc = (
        sum(
            wa * wb * (float(pa > pb) + 0.5 * float(pa == pb))
            for ya, pa, wa in data
            if ya
            for yb, pb, wb in data
            if not yb
        )
        / (pos * neg)
        if pos > 1e-12 and neg > 1e-12
        else None
    )
    ap = None
    if pos > 1e-12 and neg > 1e-12:
        ap = 0.0
        tp = 0.0
        total = 0.0
        for threshold in sorted({p for _, p, _ in data}, reverse=True):
            batch = [(y, w) for y, p, w in data if p == threshold]
            delta = sum(y * w for y, w in batch)
            tp += delta
            total += sum(w for _, w in batch)
            ap += delta / pos * tp / total
    bins = []
    for i in range(5):
        selected = [(y, p, w) for y, p, w in data if min(4, int(p * 5)) == i]
        mass = sum(w for _, _, w in selected)
        bins.append(
            {
                "range": [i / 5, (i + 1) / 5],
                "count": len(selected),
                "weight": mass,
                "mean_probability": sum(p * w for _, p, w in selected) / mass
                if mass
                else None,
                "positive_rate": sum(y * w for y, _, w in selected) / mass
                if mass
                else None,
            }
        )
    return {
        "known": len(data),
        "unknown": unknown,
        "outside_conditional_axis": outside_axis,
        "positive": sum(y for y, _, _ in data),
        "negative": sum(1 - y for y, _, _ in data),
        "weighted_prevalence": pos,
        "brier": sum(w * (p - y) ** 2 for y, p, w in data),
        "log_loss": -sum(
            w * (y * math.log(max(1e-12, p)) + (1 - y) * math.log(max(1e-12, 1 - p)))
            for y, p, w in data
        ),
        "auc": auc,
        "auprc": ap,
        "reliability": bins,
    }


def priors(fit, smoothing=1):
    if any(r["split"] != "fit" for r in fit):
        raise ValueError("fit-only prior required")
    weights = group_weights(fit)
    globals = []
    skills = {}
    # Weights sum to one; effective count is independent mechanism count, not pairs.
    effective = len({r["repair_group_id"] for r in fit})
    for axis in range(2):
        data = [
            (targets(r)[axis], w * effective)
            for r, w in zip(fit, weights)
            if targets(r)[axis] is not None
        ]
        globals.append(
            (sum(y * w for y, w in data) + smoothing * 0.5)
            / (sum(w for _, w in data) + smoothing)
        )
    for sid in sorted({r["skill_id"] for r in fit}):
        rr = [r for r in fit if r["skill_id"] == sid]
        ww = group_weights(rr)
        ss = []
        for axis in range(2):
            data = [
                (targets(r)[axis], w * effective)
                for r, w in zip(rr, ww)
                if targets(r)[axis] is not None
            ]
            ss.append(
                (sum(y * w for y, w in data) + smoothing * globals[axis])
                / (sum(w for _, w in data) + smoothing)
            )
        skills[sid] = ss
    return {
        "global": globals,
        "skills": skills,
        "smoothing": smoothing,
        "fit_groups": effective,
    }


def words(text):
    return set(re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower()))


def features(public, skill_only=False):
    skill = words(
        public.skill_name + " " + public.skill_description + " " + public.skill_body
    )
    result = {"s:" + w: 1.0 for w in skill}
    if not skill_only:
        task = words(public.request)
        context = words(public.context)
        result.update({"t:" + w: 1.0 for w in task})
        result.update({"overlap:" + w: 1.0 for w in skill & task})
        result.update({"context_overlap:" + w: 1.0 for w in skill & context})
        result["overlap_fraction"] = len(task & skill) / max(1, len(task))
    return result


def fit_text(rows, inputs, *, C=1.0, skill_only=False):
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression

    if any(r["split"] != "fit" for r in rows):
        raise ValueError("fit-only vocabulary and regression")
    vec = DictVectorizer()
    X = vec.fit_transform([features(x, skill_only) for x in inputs])
    ww = group_weights(rows)
    axes = []
    for axis in range(2):
        indices = [i for i, r in enumerate(rows) if targets(r)[axis] is not None]
        ys = [targets(rows[i])[axis] for i in indices]
        if len(set(ys)) < 2:
            axes.append({"constant": sum(ys) / len(ys) if ys else 0.5})
            continue
        model = LogisticRegression(
            C=C, solver="liblinear", random_state=7170, max_iter=1000
        )
        scale = len({r["repair_group_id"] for r in rows})
        model.fit(X[indices], ys, sample_weight=[ww[i] * scale for i in indices])
        axes.append(
            {"coef": model.coef_[0].tolist(), "intercept": float(model.intercept_[0])}
        )
    return {
        "schema": "sparse-text-v1",
        "vocabulary": vec.vocabulary_,
        "axes": axes,
        "C": C,
        "skill_only": skill_only,
    }


def predict_text(model, public):
    f = features(public, model["skill_only"])
    vv = model["vocabulary"]
    result = []
    for axis in model["axes"]:
        result.append(
            axis["constant"]
            if "constant" in axis
            else sigmoid(
                axis["intercept"]
                + sum(axis["coef"][vv[k]] * v for k, v in f.items() if k in vv)
            )
        )
    return result


def ranking(rows, predictions, *, fixed=None, accepted=None, rank_scores=None):
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[r["parent_task_id"]].append(i)
    per = []
    for task, indices in by.items():
        if fixed is None:
            order = sorted(
                indices,
                key=lambda i: (
                    -rank_scores[i]
                    if rank_scores is not None
                    else -predictions[i][0] * predictions[i][1],
                    rows[i]["skill_id"],
                ),
            )
        else:
            ids = fixed.get(rows[indices[0]]["repository"], fixed["default"])
            order = [i for sid in ids for i in indices if rows[i]["skill_id"] == sid]
        eligible = [i for i in order if accepted is None or accepted[i]]
        top = eligible[:2]
        specific = [i for i in indices if targets(rows[i])[1] == 1]
        hits = sum(i in specific for i in top)
        per.append(
            {
                "task_id": task,
                "group": rows[indices[0]]["repair_group_id"],
                "selected": [rows[i]["skill_id"] for i in top],
                "filled_k2": len(top) == 2,
                "specific_positives": len(specific),
                "precision_at_2": hits / 2,
                "recall_at_2": hits / len(specific) if specific else None,
                "known_inapplicable_at_2": sum(targets(rows[i])[0] == 0 for i in top)
                / 2,
                "unknown_at_2": sum(targets(rows[i])[0] is None for i in top) / 2,
                "mean_positive_rank": sum(
                    order.index(i) + 1 for i in specific if i in order
                )
                / len(specific)
                if specific and all(i in order for i in specific)
                else None,
            }
        )
    groups = defaultdict(list)
    for r in per:
        groups[r["group"]].append(r)
    keys = [
        "precision_at_2",
        "recall_at_2",
        "known_inapplicable_at_2",
        "unknown_at_2",
        "mean_positive_rank",
    ]
    macro = {}
    for key in keys:
        means = [
            sum(r[key] for r in rr if r[key] is not None)
            / sum(r[key] is not None for r in rr)
            for rr in groups.values()
            if any(r[key] is not None for r in rr)
        ]
        macro[key] = sum(means) / len(means) if means else None
    return {
        "tasks": per,
        "group_macro": macro,
        "tasks_without_specific_positive": sum(
            not r["specific_positives"] for r in per
        ),
        "filled_k2": sum(r["filled_k2"] for r in per),
        "total_tasks": len(per),
    }


def precision_curve(rows, predictions, eligible):
    known_indices = [i for i, r in enumerate(rows) if targets(r)[0] is not None]
    weights = [0.0] * len(rows)
    for i, w in zip(known_indices, group_weights([rows[i] for i in known_indices])):
        weights[i] = w
    known = sum(w for r, w in zip(rows, weights) if targets(r)[0] is not None)
    positive = sum(w for r, w in zip(rows, weights) if targets(r)[0] == 1)
    curve = []
    for threshold in [1.0000001] + sorted({p[0] for p in predictions}, reverse=True):
        accepted = [
            i for i, p in enumerate(predictions) if eligible[i] and p[0] >= threshold
        ]
        known_accept = [i for i in accepted if targets(rows[i])[0] is not None]
        mass = sum(weights[i] for i in known_accept)
        tp = sum(weights[i] for i in known_accept if targets(rows[i])[0] == 1)
        interval = None
        if mass:
            groups = sorted({rows[i]["repair_group_id"] for i in known_indices})
            totals = []
            for group in groups:
                ii = [i for i in known_accept if rows[i]["repair_group_id"] == group]
                totals.append(
                    (
                        sum(weights[i] for i in ii if targets(rows[i])[0] == 1),
                        sum(weights[i] for i in ii),
                    )
                )
            rng = random.Random(7170)
            samples = []
            for _ in range(1000):
                draw = [rng.choice(totals) for _ in totals]
                denominator = sum(d for _, d in draw)
                if denominator:
                    samples.append(sum(n for n, _ in draw) / denominator)
            samples.sort()
            interval = {
                "lower": samples[int(len(samples) * 0.025)],
                "upper": samples[min(len(samples) - 1, int(len(samples) * 0.975))],
                "nonempty_resamples": len(samples),
                "resamples": 1000,
                "method": "mechanism bootstrap conditional on nonempty acceptance; exploratory, not a safety bound",
            }
        curve.append(
            {
                "threshold": threshold,
                "accepted": len(accepted),
                "known_accepted": len(known_accept),
                "unknown_accepted": len(accepted) - len(known_accept),
                "groups": len({rows[i]["repair_group_id"] for i in known_accept}),
                "precision": tp / mass if mass else None,
                "precision_interval": interval,
                "coverage": mass / known if known else None,
                "recall": tp / positive if positive else None,
                "known_false_accepts": sum(
                    targets(rows[i])[0] == 0 for i in known_accept
                ),
            }
        )
    return curve


def choose_threshold(curve, rule):
    qualified = [
        p
        for p in curve
        if p["precision"] is not None
        and p["precision"] >= rule["target_precision"]
        and p["groups"] >= rule["min_accepted_groups"]
        and p["known_accepted"] >= rule["min_accepted_rows"]
        and p["coverage"] >= rule["min_known_coverage"]
        and p["unknown_accepted"] <= rule["max_unknown_acceptance"]
    ]
    return (
        max(qualified, key=lambda p: (p["coverage"], p["threshold"]))
        if qualified
        else None
    )


def fit_calibration(rows, logits, axis, rule):
    import numpy as np
    from scipy.optimize import minimize

    ww = group_weights(rows)
    indices = [i for i, r in enumerate(rows) if targets(r)[axis] is not None]
    counts = Counter(targets(rows[i])[axis] for i in indices)
    if (
        len({rows[i]["repair_group_id"] for i in indices}) < rule["min_axis_groups"]
        or min(counts.get(0, 0), counts.get(1, 0)) < rule["min_each_class"]
    ):
        return {
            "status": "UNCALIBRATED_INSUFFICIENT_LABELS",
            "a": 1.0,
            "b": 0.0,
            "counts": dict(counts),
        }
    z = np.asarray([logits[i][axis] for i in indices])
    y = np.asarray([targets(rows[i])[axis] for i in indices])
    w = np.asarray([ww[i] for i in indices])
    w /= w.sum()

    def objective(ab):
        v = ab[0] * z + ab[1]
        return float(
            np.sum(w * (np.logaddexp(0, v) - y * v)) + 0.005 * (ab[0] - 1) ** 2
        )

    result = minimize(
        objective, [1.0, 0.0], method="L-BFGS-B", bounds=[(0, None), (None, None)]
    )
    if not result.success:
        raise ValueError("calibration did not converge: " + result.message)
    return {
        "status": "FITTED",
        "a": float(result.x[0]),
        "b": float(result.x[1]),
        "counts": dict(counts),
        "loss": float(result.fun),
    }


def calibrated(logits, mapping):
    return [
        [sigmoid(m["a"] * z + m["b"]) for z, m in zip(zz, mapping)] for zz in logits
    ]


def bootstrap_brier(rows, predictions, repeat=1000, seed=7170, reference=None):
    groups = sorted({r["repair_group_id"] for r in rows})
    rng = random.Random(seed)
    values = []
    # Mechanism means, preserving all within-group dependence.
    gm = []
    for group in groups:
        ii = [i for i, r in enumerate(rows) if r["repair_group_id"] == group]
        v = axis_metrics([rows[i] for i in ii], [predictions[i] for i in ii])["brier"]
        if v is not None:
            if reference is not None:
                v -= axis_metrics([rows[i] for i in ii], [reference[i] for i in ii])[
                    "brier"
                ]
            gm.append(v)
    if not gm:
        return None
    for _ in range(repeat):
        values.append(sum(rng.choice(gm) for _ in gm) / len(gm))
    values.sort()
    return {
        "lower": values[int(repeat * 0.025)],
        "upper": values[min(repeat - 1, int(repeat * 0.975))],
        "groups": len(gm),
        "point": sum(gm) / len(gm),
        "method": "paired mechanism percentile bootstrap; exploratory"
        if reference is not None
        else "mechanism percentile bootstrap; exploratory",
    }
