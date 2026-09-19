"""Real functional heads, fixed dev selection, no training on policy or costs."""

import hashlib
from pathlib import Path
import time

from .functional_collection import verify_row
from .functional_features import feature_tables, task_weighted_prior, prior_predict
from .functional_outcomes import load_objective
from .functional_pairs import paired_records, signal_summary
from .functional_wait import cross_fitted_targets
from .learning import asset_identity, model_identity
from .session import dump
from .study import read, assets
from .value import fit_gain, fit_wait, weights, save_models, load_models


def scores(predictions, rows):
    import torch

    p = torch.tensor(predictions)
    y = torch.tensor([r["delta"] for r in rows])
    w = weights(rows)
    return {
        "task_macro_mse": float((w * (p - y).square()).sum()),
        "task_macro_mae": float((w * (p - y).abs()).sum()),
        "sign_confusion": {
            str(actual) + ":" + str(predicted): sum(
                int(torch.sign(y[i])) == actual and int(torch.sign(p[i])) == predicted
                for i in range(len(rows))
            )
            for actual in (-1, 0, 1)
            for predicted in (-1, 0, 1)
        },
        "predictions": predictions,
    }


def model_scores(model, rows):
    import torch

    with torch.no_grad():
        p = model(
            torch.stack([r["x"] for r in rows]), torch.stack([r["k"] for r in rows])
        )
    return scores(p.tolist(), rows)


def train(
    records_path,
    protocol_path,
    objective_path,
    learning_path,
    output,
    payloads,
    encoder_path,
):
    started = time.monotonic()
    objective = load_objective(objective_path)
    protocol, plan, bundle = map(read, (protocol_path, learning_path, records_path))
    if (
        plan["epochs"] != [80, 160]
        or plan["seed"] != 7170
        or plan["cost_or_policy_label_inputs"] is not False
    ):
        raise ValueError("learning contract changed")
    identity = {
        "protocol_sha256": hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        "objective_sha256": objective["sha256"],
    }
    if (
        bundle["identity"] != identity
        or protocol["objective_sha256"] != objective["sha256"]
    ):
        raise ValueError("training collection identity mismatch")
    expected = {r["task_id"] for r in protocol["tasks"] if r["split"] != "test"}
    if set(bundle["completed_tasks"]) != expected:
        raise ValueError("collection incomplete; retain planned denominator")
    task_info = {r["task_id"]: r for r in protocol["tasks"] if r["split"] != "test"}
    records = []
    for row in bundle["rows"]:
        if row["task_id"] not in expected or row["split"] == "test":
            raise ValueError("unregistered or final record in training input")
        info = task_info[row["task_id"]]
        if row["split"] != info["split"] or row["family"] != info["family"]:
            raise ValueError("row split or cross-fit family differs from protocol")
        actual = verify_row(row)
        if any(
            actual[k] != row[k]
            for k in (
                "y_target",
                "y_regression",
                "y_functional",
                "verifier_integrity_status",
            )
        ):
            raise ValueError("training source outcome changed")
        records.append(actual)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    binding = {
        **identity,
        "records_sha256": hashlib.sha256(Path(records_path).read_bytes()).hexdigest(),
        "learning_protocol_sha256": hashlib.sha256(
            Path(learning_path).read_bytes()
        ).hexdigest(),
        **asset_identity(payloads, encoder_path),
    }
    all_pairs = paired_records(records)
    train_signal = signal_summary(
        [r for r in all_pairs if r["split"] == "train"], collection_complete=True
    )
    report = {
        "data_binding": binding,
        "train_signal": train_signal,
        "methods": {},
        "selection": plan["selection"],
        "research_target": "FUNCTIONAL_REPAIR_GAIN",
    }
    encoder, _, _, _ = assets(payloads, encoder_path)
    for name, no_state in (("full", False), ("task-only", True)):
        rows, chains, missing = feature_tables(
            records, encoder, split="train", no_state=no_state
        )
        dev, _, dev_missing = feature_tables(
            records, encoder, split="dev", no_state=no_state
        )
        if not rows or not dev:
            report.update(
                status="PARTIAL_METHOD", reason="KNOWN_FUNCTIONAL_PAIRS_INSUFFICIENT"
            )
            dump(output / "training.json", report)
            return report
        prior = task_weighted_prior(rows)
        diagnostics = {
            "zero": scores([0.0] * len(dev), dev),
            "prior": scores(
                [prior_predict(prior, r["action"], r["stage"]) for r in dev], dev
            ),
            "skill_stage_prior": prior,
        }
        if train_signal["nonzero_skill_pairs"] == 0:
            report.update(
                status="PARTIAL_METHOD",
                reason="NO_NONZERO_TRAIN_FUNCTIONAL_GAIN",
                cheap_baselines=diagnostics,
            )
            dump(output / "training.json", report)
            return report
        if len({r["family"] for r in rows}) < 3:
            report.update(
                status="PARTIAL_METHOD",
                reason="INDEPENDENT_FAMILIES_INSUFFICIENT",
                cheap_baselines=diagnostics,
            )
            dump(output / "training.json", report)
            return report
        candidates = []
        for epochs in plan["epochs"]:
            model, log = fit_gain(rows, epochs=epochs, seed=plan["seed"])
            score = model_scores(model, dev)
            candidates.append((score["task_macro_mse"], epochs, model, log, score))
        _, epochs, gain, log, score = min(candidates, key=lambda c: (c[0], c[1]))
        targets, provenance = cross_fitted_targets(rows, chains, epochs=epochs)
        if not targets:
            raise ValueError("no independently cross-fitted functional wait targets")
        wait, wait_log = fit_wait(targets, epochs=epochs, seed=plan["seed"])
        import torch

        x, k = dev[0]["x"][None], dev[0]["k"][None]
        with torch.no_grad():
            probe = {"gain": float(gain(x, k)[0]), "wait": float(wait(x)[0, 0])}
        meta = {
            "research_target": "FUNCTIONAL_REPAIR_GAIN",
            "data_binding": binding,
            "state_dim": x.shape[1],
            "skill_dim": k.shape[1],
            "no_state": no_state,
            "epochs": epochs,
            "seed": plan["seed"],
            "encoder_path": str(Path(encoder_path).resolve()),
            "probe": {"state": x.tolist(), "skill": k.tolist(), "expected": probe},
            "train_tasks": sorted({r["task_id"] for r in rows}),
            "train_families": sorted({r["family"] for r in rows}),
            "cost_in_labels": False,
            "policy_in_labels": False,
            "candidate_rule": "COMMON_FIXED_C_ACTUAL_PAYLOAD",
        }
        save_models(output / name, gain, wait, meta)
        report["methods"][name] = {
            "gain_training": log,
            "wait_training": wait_log,
            "dev_candidates": [
                {"epochs": c[1], "task_macro_mse": c[0]} for c in candidates
            ],
            "selected_epochs": epochs,
            "dev_scores": score,
            "cheap_baselines": diagnostics,
            "cross_fit": provenance,
            "wait_targets": [
                {"state_id": r["state_id"], "target": r["target"]} for r in targets
            ],
            "train_rows": len(rows),
            "dev_rows": len(dev),
            "missing_train": missing,
            "missing_dev": dev_missing,
            "model_identity": model_identity(output / name),
        }
        dump(output / "training.json", report)
    report.update(
        status="FITTED_PENDING_INDEPENDENT_RELOAD",
        wall_seconds=time.monotonic() - started,
    )
    dump(output / "training.json", report)
    return report


def reload_probe(output):
    """Invoke from a separate process, independently constructing both models."""
    import torch

    result = {}
    for name in ("full", "task-only"):
        gain, wait, meta = load_models(Path(output) / name)
        x, k = (
            torch.tensor(meta["probe"]["state"]),
            torch.tensor(meta["probe"]["skill"]),
        )
        with torch.no_grad():
            actual = {"gain": float(gain(x, k)[0]), "wait": float(wait(x)[0, 0])}
        if any(abs(actual[k] - meta["probe"]["expected"][k]) > 1e-6 for k in actual):
            raise ValueError("independent functional model reload mismatch")
        result[name] = {
            "actual": actual,
            "expected": meta["probe"]["expected"],
            "match": True,
            "model_identity": model_identity(Path(output) / name),
        }
    dump(Path(output) / "independent-reload.json", result)
    return result
