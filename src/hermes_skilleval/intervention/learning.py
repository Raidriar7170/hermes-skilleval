"""Actual supervised fitting and independently reloadable policy artifacts."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

from .session import dump
from .study import read, assets, paired_rows
from .value import (
    fit_gain,
    fit_wait,
    weights,
    cross_fitted_wait_targets,
    save_models,
    load_models,
)


def aggregate_pairs(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["task_id"], row["state_id"], row["action"]].append(row)
    result = []
    for group in grouped.values():
        result.append(
            {
                **group[0],
                "delta": sum(r["delta"] for r in group) / len(group),
                "delta_quality": sum(r["delta_quality"] for r in group) / len(group),
                "paired_repeats": len(group),
                "baseline_runs": [r["baseline_run"] for r in group],
            }
        )
    return result


def errors(model, rows):
    import torch

    if not rows:
        raise ValueError("no usable development paired labels")
    with torch.no_grad():
        prediction = model(
            torch.stack([r["x"] for r in rows]), torch.stack([r["k"] for r in rows])
        )
    y = torch.tensor([r["delta"] for r in rows])
    w = weights(rows)
    return {
        "task_macro_mse": float(((prediction - y) ** 2 * w).sum()),
        "sign_accuracy": float((((prediction > 0) == (y > 0)).float() * w).sum()),
        "predictions": prediction.tolist(),
    }


def cheap_baselines(train, dev):
    import torch

    w = weights(dev)
    y = torch.tensor([r["delta"] for r in dev])
    prior = defaultdict(list)
    for r in train:
        prior[r["action"], r["stage"]].append(r["delta"])
    prediction = torch.tensor(
        [
            sum(prior[r["action"], r["stage"]]) / len(prior[r["action"], r["stage"]])
            if prior[r["action"], r["stage"]]
            else 0.0
            for r in dev
        ]
    )
    return {
        "zero_gain_mse": float((w * y * y).sum()),
        "skill_stage_prior_mse": float((w * (prediction - y) ** 2).sum()),
        "skill_stage_prior": {
            a + "@" + s: sum(v) / len(v) for (a, s), v in prior.items() if v
        },
    }


def train(records_path, output, payload_dir, encoder_path, epochs=(80, 160)):
    import torch

    torch.set_num_threads(2)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    records = read(records_path)["rows"]
    encoder, retriever, _, _ = assets(payload_dir, encoder_path)
    report = {
        "selection": "minimum task-macro dev MSE of paired net-utility delta; fixed epochs grid",
        "training_only_real_tail_labels": True,
        "methods": {},
    }
    for name, no_state in [("full", False), ("no-state", True)]:
        raw, chains, missing = paired_rows(
            records, encoder, retriever, split="train", no_state=no_state
        )
        dev_raw, _, dev_missing = paired_rows(
            records, encoder, retriever, split="dev", no_state=no_state
        )
        rows = aggregate_pairs(raw)
        dev = aggregate_pairs(dev_raw)
        if len({r["task_id"] for r in rows}) < 3:
            raise ValueError(
                "DATA_SIGNAL_INSUFFICIENT: fewer than three qualified train mechanisms"
            )
        candidates = []
        for count in epochs:
            gain, log = fit_gain(rows, epochs=count)
            scores = errors(gain, dev)
            candidates.append((scores["task_macro_mse"], count, gain, log, scores))
        _, count, gain, log, scores = min(candidates, key=lambda v: (v[0], v[1]))
        targets, provenance = cross_fitted_wait_targets(rows, chains, epochs=count)
        wait, wait_log = fit_wait(targets, epochs=count)
        probe_state = dev[0]["x"][None]
        probe_skill = dev[0]["k"][None]
        with torch.no_grad():
            expected = {
                "gain": float(gain(probe_state, probe_skill)[0]),
                "wait": float(wait(probe_state)[0, 0]),
            }
        meta = {
            "state_dim": rows[0]["x"].numel(),
            "skill_dim": rows[0]["k"].numel(),
            "no_state": no_state,
            "epochs": count,
            "seed": 7170,
            "encoder_path": str(Path(encoder_path).resolve()),
            "probe": {
                "state": probe_state.tolist(),
                "skill": probe_skill.tolist(),
                "expected": expected,
            },
            "train_tasks": sorted(chains),
            "cost_weights": {"time": 0.05, "context": 0.02},
        }
        save_models(output / name, gain, wait, meta)
        report["methods"][name] = {
            "selected_epochs": count,
            "gain_training": log,
            "wait_training": wait_log,
            "dev_candidates": [
                {"epochs": c[1], "task_macro_mse": c[0]} for c in candidates
            ],
            "dev_scores": scores,
            "cheap_baselines": cheap_baselines(rows, dev),
            "cross_fit": provenance,
            "wait_target_values": [r["target"] for r in targets],
            "train_rows": len(rows),
            "raw_paired_repeats": len(raw),
            "dev_rows": len(dev),
            "missing_train": missing,
            "missing_dev": dev_missing,
            "delta_quality_counts": {
                key: sum(
                    (
                        r["delta_quality"] > 0
                        if key == "rescue"
                        else r["delta_quality"] < 0
                        if key == "damage"
                        else r["delta_quality"] == 0
                    )
                    for r in raw
                )
                for key in ("rescue", "damage", "tie")
            },
        }
        dump(output / "training.json", report)
        print(
            json.dumps(
                {
                    "trained": name,
                    "train_tasks": len(chains),
                    "paired_rows": len(rows),
                    "epochs": count,
                    "gain_parameter_change": log["parameter_l2_change"],
                    "wait_parameter_change": wait_log["parameter_l2_change"],
                }
            ),
            flush=True,
        )
    return report


def reload_probe(output):
    """Run via a NEW process; this is not an in-memory save/load assertion."""
    import torch

    results = {}
    for name in ["full", "no-state"]:
        gain, wait, meta = load_models(Path(output) / name)
        x = torch.tensor(meta["probe"]["state"])
        k = torch.tensor(meta["probe"]["skill"])
        with torch.no_grad():
            actual = {"gain": float(gain(x, k)[0]), "wait": float(wait(x)[0, 0])}
        expected = meta["probe"]["expected"]
        if any(abs(actual[key] - expected[key]) > 1e-6 for key in actual):
            raise ValueError("reload mismatch")
        results[name] = {"actual": actual, "expected": expected, "match": True}
    dump(Path(output) / "independent-reload.json", results)
    return results


class Predictor:
    def __init__(self, models, method, encoder, retriever):
        self.gain, self.wait, self.metadata = load_models(
            Path(models) / ("no-state" if method == "H-no-state" else "full")
        )
        self.encoder, self.retriever = encoder, retriever
        self.gain_calls = 0
        self.wait_calls = 0
        self.use_wait = method != "H-myopic"

    def __call__(self, state, candidates):
        import torch

        x = self.encoder.features(state, no_state=self.metadata["no_state"])[None]
        self.gain_calls += 1
        if self.use_wait and state.stage != "E2":
            self.wait_calls += 1
        with torch.no_grad():
            gains = {
                k: float(
                    self.gain(
                        x, self.encoder.encode(self.retriever.full_bodies[k])[None]
                    )[0]
                )
                for k in candidates
            }
            wait = (
                float(self.wait(x)[0, 0])
                if self.use_wait and state.stage != "E2"
                else 0.0
            )
        return gains, wait
