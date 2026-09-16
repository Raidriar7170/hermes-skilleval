"""Bounded conditional-applicability study and records-only recomputation."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from hermes_skilleval.repo_routing.applicability_data import (
    file_hash,
    identifiability,
    merge_annotations,
    read_json,
    read_rows,
    targets,
    validate_splits,
    write_json,
    write_rows,
)
from hermes_skilleval.repo_routing.applicability_eval import (
    axis_metrics,
    bootstrap_brier,
    calibrated,
    choose_threshold,
    fit_calibration,
    fit_text,
    predict_text,
    precision_curve,
    priors,
    ranking,
)
from hermes_skilleval.repo_routing.pointwise_support import (
    PublicInput,
    public_input,
    reload_probe,
    score,
    train,
    scorer_identity,
    calibrated_decision,
    predict_public,
)
from hermes_skilleval.repo_routing.gate import sigmoid

DEFAULT = "artifacts/conditional-applicability-v1"
REGISTRY = "configs/conditional-applicability-v1/registry.json"
PROTOCOL = "configs/conditional-applicability-v1/protocol.json"


def load(root):
    tasks = read_json(root / "tasks.json")
    validate_splits(tasks)
    rows = read_rows(root / "labels.jsonl")
    skills = read_json(REGISTRY)["skills"]
    ti = {t["task_id"]: t for t in tasks}
    si = {s["id"]: s for s in skills}
    return rows, ti, si


def baseline(root, output):
    rows, tasks, skills = load(root)
    fit = [r for r in rows if r["split"] == "fit"]
    dev = [r for r in rows if r["split"] == "model-dev"]

    def inputs(rr):
        return [public_input(tasks[r["task_id"]], skills[r["skill_id"]]) for r in rr]

    trials = []
    for smoothing in read_json(PROTOCOL)["baselines"]["prior_smoothing_candidates"]:
        model = priors(fit, smoothing)
        pred = [model["skills"].get(r["skill_id"], model["global"]) for r in dev]
        trials.append((axis_metrics(dev, pred)["log_loss"], model))
    prior = min(trials, key=lambda x: x[0])[1]
    models = {}
    development = {}
    for name, only in [("cheap_text", False), ("skill_only", True)]:
        trials = []
        for C in read_json(PROTOCOL)["baselines"]["lexical_C_candidates"]:
            model = fit_text(fit, inputs(fit), C=C, skill_only=only)
            pred = [predict_text(model, p) for p in inputs(dev)]
            loss = axis_metrics(dev, pred)["log_loss"]
            trials.append((loss, model))
        loss, models[name] = min(trials, key=lambda x: x[0])
        development[name] = {
            "selection_loss": loss,
            "trials": [{"C": m["C"], "loss": value} for value, m in trials],
        }
    fixed = {}
    for repo in ["default"] + sorted({r["repository"] for r in rows}):
        subset = [r for r in dev if repo == "default" or r["repository"] == repo]
        if not subset:
            subset = [r for r in fit if repo == "default" or r["repository"] == repo]
        scores = {
            sid: sum(targets(r)[1] == 1 for r in subset if r["skill_id"] == sid)
            for sid in skills
        }
        fixed[repo] = sorted(scores, key=lambda sid: (-scores[sid], sid))[:2]
    write_json(
        output,
        {
            "prior": prior,
            "models": models,
            "fixed": fixed,
            "development": development,
            "fit_labels_sha256": file_hash(root / "labels.jsonl"),
            "protocol_sha256": file_hash(PROTOCOL),
            "registry_sha256": file_hash(REGISTRY),
        },
    )
    predictions = []
    for r in rows:
        inp = public_input(tasks[r["task_id"]], skills[r["skill_id"]])
        predictions.append(
            {
                "row_id": r["row_id"],
                "global_prior": prior["global"],
                "skill_prior": prior["skills"].get(r["skill_id"], prior["global"]),
                **{n: predict_text(m, inp) for n, m in models.items()},
            }
        )
    write_rows(root / "baseline-predictions.jsonl", predictions)
    return {
        "development": development,
        "identifiability": identifiability(rows),
        "fixed": fixed,
    }


def model_score(root, config, split, output, no_context=False, rank_only=False):
    from hermes_skilleval.repo_routing.reranker import Reranker

    if rank_only and (no_context or split != "check"):
        raise ValueError("original rank comparison requires check and public context")
    frozen = verify_freeze(root) if split in {"cal", "check"} else None
    rows, tasks, skills = load(root)
    c = read_json(config)
    rr = [r for r in rows if r["split"] == split]
    if split in {"cal", "check"} and not (root / "model-freeze.json").exists():
        raise ValueError("freeze scorer selection before cal/check")
    identity = scorer_identity(c, use_context=not no_context, rank_only=rank_only)
    if frozen is not None:
        allowed = {a["scorer_identity"] for a in frozen["comparison_arms"].values()}
        if rank_only and split == "check":
            allowed = {frozen["original_rank"]["scorer_identity"]}
        if identity not in allowed or (
            split == "cal" and identity != frozen["scorer_identity"]
        ):
            raise ValueError("scorer/context is not a frozen comparison arm")
    ranker = Reranker(
        c["base"],
        device=c["device"],
        max_length=c["max_length"],
        adapter=c.get("adapter"),
    )
    result = []
    start = time.monotonic()
    from hermes_skilleval.repo_routing.support import contradictions

    for r in rr:
        conflict = bool(
            contradictions(
                tasks[r["task_id"]]["request"],
                skills[r["skill_id"]],
                tasks[r["task_id"]]["context"].get("environment", {}),
            )
        )
        if rank_only:
            from hermes_skilleval.repo_routing.reranker import structured_representation

            values, inputs = ranker.scores(
                [
                    structured_representation(
                        tasks[r["task_id"]]["request"],
                        tasks[r["task_id"]]["context"],
                        skills[r["skill_id"]],
                        support=False,
                    )
                ]
            )
            record = {
                "logits": values.detach().cpu().tolist(),
                "inputs": [
                    {
                        k: v
                        for k, v in item.items()
                        if k in {"input_sha256", "actual_tokens", "truncated"}
                    }
                    for item in inputs
                ],
            }
        else:
            record = score(
                ranker,
                public_input(tasks[r["task_id"]], skills[r["skill_id"]]),
                use_context=not no_context,
            )
        result.append(
            {
                "row_id": r["row_id"],
                **record,
                "context_state": tasks[r["task_id"]]["context"]["state"],
                "conflict": conflict,
                "elapsed_seconds": time.monotonic() - start,
            }
        )
        print(r["row_id"], record["logits"], flush=True)
    write_json(
        output,
        {
            "schema": "pointwise-scores-v1",
            "split": split,
            "config_sha256": file_hash(config),
            "scorer_identity": identity,
            "tasks_sha256": file_hash(root / "tasks.json"),
            "labels_sha256": file_hash(root / "labels.jsonl"),
            "adapter_sha256": file_hash(
                Path(c["adapter"]) / "adapter_model.safetensors"
            )
            if c.get("adapter")
            else None,
            "registry_sha256": file_hash(REGISTRY),
            "use_context": not no_context,
            "forward_calls": ranker.forward_calls,
            "wall_seconds": time.monotonic() - start,
            "rows": result,
        },
    )
    return {"rows": len(result), "wall_seconds": time.monotonic() - start}


def verify_freeze(root):
    frozen = read_json(root / "model-freeze.json")
    for path, expected in frozen["source_bindings"].items():
        if file_hash(path) != expected:
            raise ValueError("frozen source binding mismatch: " + path)
    return frozen


def verify_scores(root, scores, *, selected=False, arm=None):
    frozen = verify_freeze(root)
    if (
        scores["registry_sha256"] != file_hash(REGISTRY)
        or scores["tasks_sha256"] != file_hash(root / "tasks.json")
        or scores["labels_sha256"] != file_hash(root / "labels.jsonl")
    ):
        raise ValueError("score source mismatch")
    if selected and (
        scores["scorer_identity"] != frozen["scorer_identity"]
        or scores["adapter_sha256"] != frozen["selected"]["adapter_sha256"]
        or not scores["use_context"]
    ):
        raise ValueError("score does not match frozen selected model")
    if arm is not None:
        expected = frozen["comparison_arms"][arm]
        if any(
            scores[key] != expected[key]
            for key in ("scorer_identity", "adapter_sha256", "use_context")
        ):
            raise ValueError("comparison arm identity mismatch: " + arm)
    return frozen


def freeze(root, summaries, output, rank_config):
    rows, _, _ = load(root)
    dev = [r for r in rows if r["split"] == "model-dev"]
    trials = []
    local = {}
    for path in summaries:
        summary = read_json(path)
        candidate = Path(path).parent.name
        local[candidate] = path
        exported = {k: v for k, v in summary.items() if k not in {"config", "probe"}}
        exported["config"] = {
            k: v
            for k, v in summary["config"].items()
            if k not in {"base", "labels", "tasks", "registry", "output"}
        }
        exported["candidate_id"] = candidate
        exported["training_weighting"] = (
            "Goal masked sum(w*m*BCE)/sum(w*m); main dev metric independently averages known labels within groups"
        )
        for epoch in summary["epochs"]:
            number = epoch["epoch"]
            reload = read_json(Path(path).parent / f"reload-epoch-{number}.json")
            if (
                reload["reload"] != "MATCHED"
                or reload["adapter_sha256"] != epoch["checkpoint_sha256"]
            ):
                raise ValueError(
                    "each candidate checkpoint needs bound fresh-process reload"
                )
            saved = read_json(Path(path).parent / f"dev-epoch-{number}.json")
            index = {r["row_id"]: r for r in saved["rows"]}
            if set(index) != {r["row_id"] for r in dev}:
                raise ValueError("complete dev predictions required")
            pred = [[sigmoid(v) for v in index[r["row_id"]]["logits"]] for r in dev]
            losses = [axis_metrics(dev, pred, a)["log_loss"] for a in range(2)]
            write_json(root / f"{candidate}-dev-{number}.json", saved)
            write_json(root / f"{candidate}-reload-{number}.json", reload)
            trials.append(
                {
                    "candidate_id": candidate,
                    "epoch": number,
                    "lambda_spec": summary["config"]["lambda_spec"],
                    "dev_loss": losses,
                    "adapter_sha256": epoch["checkpoint_sha256"],
                }
            )
        exported["initial_masked_metric_best_epoch"] = exported.pop("best_epoch")
        exported["reload"] = "ALL_EPOCHS_MATCHED"
        exported["trajectory"] = read_rows(Path(path).parent / "trajectory.jsonl")
        write_json(root / (candidate + ".json"), exported)
    selected = min(
        trials,
        key=lambda t: (
            t["dev_loss"][0],
            t["dev_loss"][1] if t["lambda_spec"] else float("inf"),
        ),
    )

    def candidate_config(trial):
        path = local[trial["candidate_id"]]
        config = read_json(path)["config"]
        config["base_files"] = read_json(root / "base-identity.json")["files"]
        config["adapter"] = str(Path(path).parent / f"epoch-{trial['epoch']}")
        config["adapter_files"] = {
            name: file_hash(Path(config["adapter"]) / name)
            for name in ("adapter_model.safetensors", "adapter_config.json")
        }
        return config

    config = candidate_config(selected)
    identity = scorer_identity(config)
    original = read_json(rank_config)
    original_identity = scorer_identity(original, rank_only=True)
    rule = read_json(PROTOCOL)["original_rank"]
    if (
        original["max_length"] != rule["max_length"]
        or original["adapter_files"] != rule["adapter_files"]
    ):
        raise ValueError("original rank must retain frozen weights and input budget")
    best_noaux = min(
        (t for t in trials if t["lambda_spec"] == 0), key=lambda t: t["dev_loss"][0]
    )
    best_joint = min(
        (t for t in trials if t["lambda_spec"] == 1), key=lambda t: t["dev_loss"][0]
    )
    base_config = {
        k: v for k, v in config.items() if k not in {"adapter", "adapter_files"}
    }
    arm_configs = {
        "learned_raw": config,
        "frozen_raw": base_config,
        "no_aux_raw": candidate_config(best_noaux),
        "joint_raw": candidate_config(best_joint),
        "learned_no_context_raw": config,
    }
    arms = {}
    private_root = Path(local[selected["candidate_id"]]).parent.parent
    for name, arm_config in arm_configs.items():
        use_context = name != "learned_no_context_raw"
        arms[name] = {
            "scorer_identity": scorer_identity(arm_config, use_context=use_context),
            "use_context": use_context,
            "adapter_sha256": arm_config.get("adapter_files", {}).get(
                "adapter_model.safetensors"
            ),
        }
        write_json(private_root / (name + "-config.json"), arm_config)
    bindings = [
        root / "tasks.json",
        root / "labels.jsonl",
        root / "baseline-models.json",
        root / "baseline-predictions.jsonl",
        root / "dataset-manifest.json",
        Path(REGISTRY),
        Path(PROTOCOL),
    ]
    bindings += [
        p
        for p in Path("configs/conditional-applicability-v1/skills").rglob("*")
        if p.is_file()
    ]
    bindings += [
        Path(__file__),
        Path(__file__).with_name("pointwise_support.py"),
        Path(__file__).with_name("applicability_eval.py"),
        Path(__file__).with_name("applicability_data.py"),
        Path(__file__).with_name("reranker.py"),
        Path(__file__).with_name("support.py"),
        Path(__file__).parent.parent / "vendor/skillrouter_common.py",
    ]
    bindings = [Path(str(p).replace(str(Path.cwd()) + "/", "")) for p in bindings]
    write_json(
        output,
        {
            "schema": "pointwise-model-freeze-v1",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "selected": selected,
            "trials": trials,
            "scorer_identity": identity,
            "comparison_arms": arms,
            "original_rank": {
                "scorer_identity": original_identity,
                "adapter_sha256": original["adapter_files"][
                    "adapter_model.safetensors"
                ],
                "max_length": original["max_length"],
            },
            "source_bindings": {str(p): file_hash(p) for p in bindings},
            "decision_source": "group-macro model-dev only; no cal/check scores inspected",
        },
    )
    write_json(private_root / "selected-score-config.json", config)
    return selected


def calibrate(root, scores_path, output):
    rows, _, _ = load(root)
    rr = [r for r in rows if r["split"] == "cal"]
    scores = read_json(scores_path)
    verify_scores(root, scores, selected=True)
    if scores["split"] != "cal":
        raise ValueError("cal-only mapping")
    idx = {r["row_id"]: r for r in scores["rows"]}
    if set(idx) != {r["row_id"] for r in rr}:
        raise ValueError("score/label alignment")
    logits = [idx[r["row_id"]]["logits"] for r in rr]
    rule = read_json(PROTOCOL)
    mapping = [fit_calibration(rr, logits, a, rule["calibration"]) for a in range(2)]
    pred = calibrated(logits, mapping)
    eligible = [
        idx[r["row_id"]]["visible"]
        and idx[r["row_id"]]["context_state"] == "usable"
        and not idx[r["row_id"]].get("conflict", False)
        for r in rr
    ]
    curve = precision_curve(rr, pred, eligible)
    eligible_groups = len({r["repair_group_id"] for r, ok in zip(rr, eligible) if ok})
    chosen = (
        choose_threshold(curve, rule["operating_point"])
        if mapping[0]["status"] == "FITTED"
        else None
    )
    result = {
        "scorer_identity": scores["scorer_identity"],
        "mapping": mapping,
        "threshold": chosen["threshold"] if chosen else None,
        "operating_point": chosen,
        "status": "PROVISIONAL" if chosen else "NOT_ESTABLISHED",
        "curve": curve,
        "text_only_curve_diagnostic": precision_curve(
            rr, pred, [idx[r["row_id"]]["visible"] for r in rr]
        ),
        "eligible_groups": eligible_groups,
        "reason": "INSUFFICIENT_ELIGIBLE_GROUPS"
        if eligible_groups < rule["operating_point"]["min_accepted_groups"]
        else "QUALIFIED"
        if chosen
        else "NO_QUALIFYING_THRESHOLD",
        "scores_sha256": file_hash(scores_path),
        "scores_ref": str(scores_path),
        "scorer_config_sha256": scores["config_sha256"],
        "adapter_sha256": scores["adapter_sha256"],
        "model_freeze_sha256": file_hash(root / "model-freeze.json"),
        "registry_sha256": file_hash(REGISTRY),
    }
    write_json(output, result)
    return {
        "status": result["status"],
        "mapping": mapping,
        "threshold": result["threshold"],
    }


def evaluate(root, score_files, calibration_path):
    rows, _, _ = load(root)
    rr = [r for r in rows if r["split"] == "check"]
    base = {r["row_id"]: r for r in read_rows(root / "baseline-predictions.jsonl")}
    baseline_model = read_json(root / "baseline-models.json")
    frozen = verify_freeze(root)
    if set(score_files) != set(frozen["comparison_arms"]) | {"original_rank"}:
        raise ValueError("complete frozen comparison arm set required")
    streams = {
        n: [base[r["row_id"]][n] for r in rr]
        for n in ("global_prior", "skill_prior", "cheap_text", "skill_only")
    }
    model_records = {}
    for name, path in score_files.items():
        d = read_json(path)
        if name == "original_rank":
            verify_scores(root, d)
            if (
                any(
                    d[k] != frozen["original_rank"][k]
                    for k in ("scorer_identity", "adapter_sha256")
                )
                or d["split"] != "check"
            ):
                raise ValueError("original rank identity mismatch")
            continue
        verify_scores(root, d, selected=name == "learned_raw", arm=name)
        if d["split"] != "check":
            raise ValueError("check scores required")
        idx = {r["row_id"]: r for r in d["rows"]}
        if set(idx) != {r["row_id"] for r in rr}:
            raise ValueError("complete check scores required")
        model_records[name] = [idx[r["row_id"]] for r in rr]
        streams[name] = [[sigmoid(v) for v in idx[r["row_id"]]["logits"]] for r in rr]
    cal = read_json(calibration_path)
    frozen = verify_freeze(root)
    if cal["scorer_identity"] != frozen["scorer_identity"] or cal[
        "model_freeze_sha256"
    ] != file_hash(root / "model-freeze.json"):
        raise ValueError("calibration identity mismatch")
    if cal["scores_sha256"] != file_hash(cal["scores_ref"]):
        raise ValueError("calibration input binding mismatch")
    learned = model_records["learned_raw"]
    streams["learned_calibrated"] = calibrated(
        [p["logits"] for p in learned], cal["mapping"]
    )
    decisions = [
        calibrated_decision(
            p,
            cal,
            frozen["scorer_identity"],
            context_state=p["context_state"],
            environment_known=True,
            conflicts=p.get("conflict", False),
        )
        for p in learned
    ]
    eligible = [d["eligible"] for d in decisions]
    accepted = [d["accepted"] for d in decisions]
    metrics = {}
    for name, pred in streams.items():
        per_skill = {}
        for sid in sorted({r["skill_id"] for r in rr}):
            indices = [i for i, r in enumerate(rr) if r["skill_id"] == sid]
            per_skill[sid] = axis_metrics(
                [rr[i] for i in indices], [pred[i] for i in indices]
            )
        aucs = {s: v["auc"] for s, v in per_skill.items() if v["auc"] is not None}
        per_group = {}
        for group in sorted({r["repair_group_id"] for r in rr}):
            ii = [i for i, r in enumerate(rr) if r["repair_group_id"] == group]
            per_group[group] = {
                "applicability": axis_metrics(
                    [rr[i] for i in ii], [pred[i] for i in ii]
                ),
                "specificity_given_applicable": axis_metrics(
                    [rr[i] for i in ii], [pred[i] for i in ii], 1
                ),
            }
        group_auc = [
            v["applicability"]["auc"]
            for v in per_group.values()
            if v["applicability"]["auc"] is not None
        ]
        group_ap = [
            v["applicability"]["auprc"]
            for v in per_group.values()
            if v["applicability"]["auprc"] is not None
        ]
        metrics[name] = {
            "applicability": axis_metrics(rr, pred),
            "specificity_given_applicable": axis_metrics(rr, pred, 1),
            "top2": ranking(rr, pred),
            "per_skill": per_skill,
            "per_group": per_group,
            "group_macro_auc": sum(group_auc) / len(group_auc) if group_auc else None,
            "group_macro_auprc": sum(group_ap) / len(group_ap) if group_ap else None,
            "skill_macro_auc": sum(aucs.values()) / len(aucs) if aucs else None,
            "skill_auc_coverage": sorted(aucs),
            "brier_interval": bootstrap_brier(rr, pred),
        }
    metrics["fixed_workflow"] = {"top2": ranking(rr, [], fixed=baseline_model["fixed"])}
    curve = precision_curve(rr, streams["learned_calibrated"], eligible)
    supported = ranking(rr, streams["learned_calibrated"], accepted=accepted)
    rank_index = {
        r["row_id"]: r for r in read_json(score_files["original_rank"])["rows"]
    }
    if set(rank_index) != {r["row_id"] for r in rr}:
        raise ValueError("complete original rank predictions required")
    rank_values = [rank_index[r["row_id"]]["logits"][0] for r in rr]
    posthoc = axis_metrics(rr, streams["global_prior"])["weighted_prevalence"]
    result = {
        "schema": "conditional-applicability-results-v1",
        "metrics": metrics,
        "learned_raw_brier_differences": {
            name: bootstrap_brier(rr, streams["learned_raw"], reference=streams[name])
            for name in (
                "frozen_raw",
                "global_prior",
                "skill_prior",
                "cheap_text",
                "skill_only",
            )
        },
        "check_precision_coverage_curve": curve,
        "check_text_only_precision_coverage_curve": precision_curve(
            rr, streams["learned_calibrated"], [p["visible"] for p in learned]
        ),
        "supported_top2": supported,
        "original_rank_top2": ranking(rr, [], rank_scores=rank_values),
        "original_rank_supported_top2": ranking(
            rr, [], rank_scores=rank_values, accepted=accepted
        ),
        "original_rank_truncated_rows": sum(
            any(i["truncated"] for i in r["inputs"]) for r in rank_index.values()
        ),
        "operating_threshold": cal["threshold"],
        "unknown_accepted": sum(
            a and targets(r)[0] is None for r, a in zip(rr, accepted)
        ),
        "frozen_global_prior_brier": metrics["global_prior"]["applicability"]["brier"],
        "frozen_skill_prior_brier": metrics["skill_prior"]["applicability"]["brier"],
        "posthoc_check_prevalence_reference": posthoc * (1 - posthoc),
        "runtime": "NOT_RUN" if not any(accepted) else "REQUIRES_QUALIFICATION",
        "runtime_reason": "NO_SUPPORTED_CHECK_SELECTION"
        if not any(accepted)
        else "CONDITIONAL_MECHANISM_VALIDATION_ONLY",
        "check_groups": len({r["repair_group_id"] for r in rr}),
        "check_rows": len(rr),
        "meaning": "weak-label text discrimination, not repair utility",
        "calibration_axis_status": [m["status"] for m in cal["mapping"]],
    }
    predictions = [
        {
            "row_id": r["row_id"],
            "predictions": {n: p[i] for n, p in streams.items()},
            "eligible": eligible[i],
            "accepted": accepted[i],
        }
        for i, r in enumerate(rr)
    ]
    return result, predictions


def verify_baseline_records(root):
    from hermes_skilleval.repo_routing.applicability_data import (
        validate_merged,
        records_equal,
    )
    from hermes_skilleval.repo_routing.applicability_eval import features

    rows, tasks, skills = load(root)
    validate_merged(rows, list(tasks.values()), read_json(REGISTRY))
    fit = [r for r in rows if r["split"] == "fit"]
    model = read_json(root / "baseline-models.json")
    if not records_equal(priors(fit, model["prior"]["smoothing"]), model["prior"]):
        raise ValueError("fit-only prior recomputation mismatch")
    for lexical in model["models"].values():
        vocabulary = set()
        for r in fit:
            vocabulary.update(
                features(
                    public_input(tasks[r["task_id"]], skills[r["skill_id"]]),
                    lexical["skill_only"],
                )
            )
        if vocabulary != set(lexical["vocabulary"]):
            raise ValueError("lexical vocabulary not fit-only")
    saved = {r["row_id"]: r for r in read_rows(root / "baseline-predictions.jsonl")}
    if set(saved) != {r["row_id"] for r in rows}:
        raise ValueError("baseline row mismatch")
    for r in rows:
        public = public_input(tasks[r["task_id"]], skills[r["skill_id"]])
        expected = {
            "row_id": r["row_id"],
            "global_prior": model["prior"]["global"],
            "skill_prior": model["prior"]["skills"].get(
                r["skill_id"], model["prior"]["global"]
            ),
            **{n: predict_text(m, public) for n, m in model["models"].items()},
        }
        if not records_equal(expected, saved[r["row_id"]]):
            raise ValueError("baseline prediction mismatch")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(DEFAULT))
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("validate-labels")
    a.add_argument("--pass-a", required=True)
    a.add_argument("--pass-b", required=True)
    a = sub.add_parser("baselines")
    a = sub.add_parser("train")
    a.add_argument("--config", required=True)
    a = sub.add_parser("reload")
    a.add_argument("--summary", required=True)
    a.add_argument("--epoch", type=int)
    a = sub.add_parser("score")
    a.add_argument("--config", required=True)
    a.add_argument(
        "--split", choices=["fit", "model-dev", "cal", "check"], required=True
    )
    a.add_argument("--output", required=True)
    a.add_argument("--no-context", action="store_true")
    a.add_argument("--rank-only", action="store_true")
    a = sub.add_parser("freeze")
    a.add_argument("--summaries", nargs="+", required=True)
    a.add_argument("--rank-config", required=True)
    a = sub.add_parser("calibrate")
    a.add_argument("--scores", required=True)
    a = sub.add_parser("check")
    a.add_argument(
        "--scores", required=True, help="JSON mapping model name to score path"
    )
    a = sub.add_parser("records")
    a = sub.add_parser("predict")
    a.add_argument("--config", required=True)
    a.add_argument("--input", required=True)
    a.add_argument("--calibration")
    a.add_argument(
        "--context-state",
        choices=["usable", "partial", "unavailable", "unknown"],
        default="unknown",
    )
    a.add_argument("--environment-known", action="store_true")
    args = p.parse_args()
    root = args.root
    if args.command == "validate-labels":
        result = merge_annotations(
            root / "tasks.json",
            REGISTRY,
            [args.pass_a, args.pass_b],
            root / "labels.jsonl",
        )
    elif args.command == "baselines":
        result = baseline(root, root / "baseline-models.json")
        write_json(root / "development-baselines.json", result)
    elif args.command == "train":
        result = train(args.config)
    elif args.command == "reload":
        result = reload_probe(args.summary, args.epoch)
    elif args.command == "score":
        result = model_score(
            root, args.config, args.split, args.output, args.no_context, args.rank_only
        )
    elif args.command == "freeze":
        result = freeze(
            root, args.summaries, root / "model-freeze.json", args.rank_config
        )
    elif args.command == "calibrate":
        result = calibrate(root, args.scores, root / "calibration.json")
    elif args.command == "check":
        files = read_json(args.scores)
        result, preds = evaluate(root, files, root / "calibration.json")
        write_json(root / "results.json", result)
        write_rows(root / "check-predictions.jsonl", preds)
        write_json(root / "check-score-index.json", files)
        paths = [
            p
            for p in root.rglob("*")
            if p.is_file() and p.name != "records-bindings.json"
        ]
        paths += [Path(REGISTRY), Path(PROTOCOL)]
        paths += [Path(path) for path in files.values()]
        paths.append(Path(read_json(root / "calibration.json")["scores_ref"]))
        paths += list(Path("configs/conditional-applicability-v1/skills").rglob("*"))
        write_json(
            root / "records-bindings.json",
            {str(p): file_hash(p) for p in paths if p.is_file()},
        )
    elif args.command == "records":
        verify_baseline_records(root)
        for path, expected in read_json(root / "records-bindings.json").items():
            if file_hash(path) != expected:
                raise ValueError("records source binding mismatch: " + path)
        files = read_json(root / "check-score-index.json")
        result, preds = evaluate(root, files, root / "calibration.json")
        from hermes_skilleval.repo_routing.applicability_data import records_equal

        if not records_equal(
            result, read_json(root / "results.json")
        ) or not records_equal(preds, read_rows(root / "check-predictions.jsonl")):
            raise ValueError("records mismatch")
        result = {"records": "MATCHED", "rows": len(preds), "model_calls": 0}
    elif args.command == "predict":
        result = predict_public(
            PublicInput(**read_json(args.input)),
            read_json(args.config),
            read_json(args.calibration) if args.calibration else None,
            context_state=args.context_state,
            environment_known=args.environment_known,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
