"""Frozen experiment adapter. Prediction never opens annotations or reference repairs."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .applicability_data import (
    file_hash,
    read_json,
    read_rows,
    write_json,
    targets,
    validate_splits,
    records_equal,
    group_weights,
)
from .context import digest
from .pointwise_support import public_input
from .gate import sigmoid


def now():
    return datetime.now(timezone.utc).isoformat()


def checked(path, sha):
    if file_hash(path) != sha:
        raise ValueError("frozen binding mismatch: " + str(path))


def validate_roster(tasks, historical):
    validate_splits(tasks)
    old_ids = {t["task_id"] for t in historical}
    old_groups = {t["repair_group_id"] for t in historical}
    old_sources = {t.get("request_ref") for t in historical}
    seen = set()
    for t in tasks:
        if t["split"] not in {"cal", "check"}:
            raise ValueError("new study only permits cal/check")
        if (
            t["task_id"] in old_ids
            or t["repair_group_id"] in old_groups
            or t["request_ref"] in old_sources
        ):
            raise ValueError("historical overlap")
        # Same underlying source/repair cannot become independent by changing IDs.
        key = (t["repository"], t.get("source_issue", t["request_ref"]))
        if key in seen:
            raise ValueError("duplicate source mechanism")
        seen.add(key)
        if t.get("previously_observed") is not False:
            raise ValueError("previous exposure must be explicit")


def load(args):
    protocol = read_json(args.protocol)
    required = {
        protocol["baselines"],
        protocol["historical_tasks"],
        protocol["environment_profile"],
        "src/hermes_skilleval/repo_routing/independent_validation.py",
        "src/hermes_skilleval/repo_routing/calibration_preflight.py",
        "src/hermes_skilleval/repo_routing/environment_probe_explicit.py",
    }
    if not required <= set(protocol["source_bindings"]):
        raise ValueError("incomplete method bindings")
    for path, sha in protocol["source_bindings"].items():
        checked(args.project_root / path, sha)
    checked(args.tasks, protocol["tasks_sha256"])
    checked(args.registry, protocol["registry_sha256"])
    tasks = sorted(read_json(args.tasks), key=lambda t: t["task_id"])
    historical = read_json(args.project_root / protocol["historical_tasks"])
    validate_roster(tasks, historical)
    skills = sorted(read_json(args.registry)["skills"], key=lambda s: s["id"])
    if len(skills) != 10 or len({s["id"] for s in skills}) != 10:
        raise ValueError("frozen complete ten-skill catalog required")
    return protocol, tasks, skills


def pairs(tasks, skills):
    return [
        {
            "row_id": t["task_id"] + "::" + s["id"],
            "task_id": t["task_id"],
            "skill_id": s["id"],
            "repair_group_id": t["repair_group_id"],
            "parent_task_id": t["parent_task_id"],
            "requirement_id": t["requirement_id"],
            "repository": t["repository"],
            "split": t["split"],
        }
        for t in tasks
        for s in skills
    ]


def calibrations(rows, stream, rule):
    from .applicability_eval import fit_calibration, precision_curve, choose_threshold

    if any(r["split"] != "cal" for r in rows):
        raise ValueError("cal-only mapping")
    result = {}
    for name in ("A", "cheap_text"):
        zz = [[stream[r["row_id"]]["logits"][name]] for r in rows]
        eligible = [stream[r["row_id"]]["input_eligible"] for r in rows]
        ii = [
            i for i, r in enumerate(rows) if eligible[i] and targets(r)[0] is not None
        ]
        mapping = fit_calibration(
            [rows[i] for i in ii], [zz[i] for i in ii], 0, rule["calibration"]
        )
        pp = [[sigmoid(mapping["a"] * z[0] + mapping["b"]), 0] for z in zz]
        curve = precision_curve(rows, pp, eligible)
        chosen = (
            choose_threshold(curve, rule["operating_point"])
            if mapping["status"] == "FITTED"
            else None
        )
        result[name] = {
            "mapping": mapping,
            "threshold": chosen["threshold"] if chosen else None,
            "operating_point": chosen,
            "precision_curve": curve,
        }
    return result


def select(rows, streams, fixed, threshold):
    """Same original rank for B2/C2. Partial sets are never exposed as K=2."""
    result = []
    for tid in sorted({r["task_id"] for r in rows}):
        rr = [r for r in rows if r["task_id"] == tid]
        rank = sorted(
            rr, key=lambda r: (-streams[r["row_id"]]["scores"]["B2"], r["skill_id"])
        )
        available = [r for r in rank if not streams[r["row_id"]]["public_conflict"]]

        def ids(xs):
            return [r["skill_id"] for r in xs]

        b = ids(available[:2])
        c = ids([r for r in available if streams[r["row_id"]]["policy_accepts"]][:2])
        t = ids(
            sorted(
                available,
                key=lambda r: (
                    -streams[r["row_id"]]["scores"]["cheap_text"],
                    r["skill_id"],
                ),
            )[:2]
        )
        f = [
            s
            for s in fixed.get(rr[0]["repository"], fixed["default"])
            if s in ids(available)
        ]
        result.append(
            {
                "task_id": tid,
                "B2": b if len(b) == 2 else [],
                "C2": c if len(c) == 2 else [],
                "T2": t if len(t) == 2 else [],
                "F2": f if len(f) == 2 else [],
                "C2_fallback": len(c) < 2,
                "C2_reason": "NO_OPERATING_POINT"
                if threshold is None
                else "INSUFFICIENT_SUPPORTED_SET"
                if len(c) < 2
                else None,
                "execution_authority": "NONE",
                "C2_partial_admitted": c,
            }
        )
    return result


def label_rows(path, expected):
    rr = read_rows(path)
    idx = {r["row_id"]: r for r in rr}
    if len(idx) != len(rr) or set(idx) != {r["row_id"] for r in expected}:
        raise ValueError("complete exact split labels required")
    out = []
    for r in expected:
        label = idx[r["row_id"]]
        if any(
            label[k] != r[k]
            for k in ("task_id", "skill_id", "split", "repair_group_id")
        ):
            raise ValueError("label provenance mismatch")
        targets(label)
        for key in ("parent_task_id", "requirement_id", "repository"):
            if label[key] != r[key]:
                raise ValueError("label grouping mismatch")
        out.append({**label, **r})
    return out


def score_stage(args, protocol, tasks, skills):
    from .decision_cli import tokenize, measured_environments
    from .pointwise_support import scorer_identity, representation
    from .reranker import Reranker, structured_representation
    from .calibration_preflight import structural
    from .applicability_eval import predict_text
    from types import SimpleNamespace

    tasks = [t for t in tasks if t["split"] == args.split]
    configs = read_json(args.model_configs)
    if args.split == "check":
        checked(args.lock, args.lock_sha256)
        lock = read_json(args.lock)
        if lock["protocol_sha256"] != file_hash(args.protocol):
            raise ValueError("policy lock mismatch")
    else:
        lock = None
    checked(
        args.environment_profile,
        protocol["source_bindings"][protocol["environment_profile"]],
    )
    environment = measured_environments(
        SimpleNamespace(
            environment_facts=args.environment_facts,
            environment_profile=args.environment_profile,
            snapshots=args.snapshots,
            environment_assets=args.environment_assets,
        ),
        tasks,
    )
    tokens = tokenize(tasks, skills, configs["A"], axes=("applicability",))
    all_tokens = {
        name: tokenize(
            tasks,
            skills,
            configs[name],
            axes=(
                ("applicability", "specificity_given_applicable")
                if name == "J"
                else ("applicability",)
            ),
        )
        for name in ("J", "frozen")
    }
    all_tokens["A"] = tokens
    # Critical token loss blocks this formal score call before constructing models.
    # Legacy B2 retains its original 1024-token truncation semantics, separately disclosed.
    if any(not v["visible"] for m in all_tokens.values() for v in m.values()):
        raise ValueError(
            "critical input token loss; retain roster and report score coverage failure"
        )
    qualification = structural(
        tasks, skills, tokens=tokens, environment_states=environment
    )
    qi = {r["row_id"]: r for r in qualification}
    public = {
        t["task_id"] + "::" + s["id"]: public_input(t, s) for t in tasks for s in skills
    }
    rows = pairs(tasks, skills)
    records = {
        r["row_id"]: {
            **r,
            "public_input_identity": digest(public[r["row_id"]].__dict__),
            "input_eligible": qi[r["row_id"]]["eligible"],
            "reasons": qi[r["row_id"]]["reasons"],
            "public_conflict": "explicit_conflict" in qi[r["row_id"]]["reasons"],
            "logits": {},
            "scores": {},
            "token_inputs": {},
        }
        for r in rows
    }
    costs = {}
    identities = {}
    for name in ("A", "J", "frozen", "B2"):
        config = configs[name]
        identity = scorer_identity(config, rank_only=name == "B2")
        if identity != protocol["models"][name]["scorer_identity"]:
            raise ValueError("scorer identity mismatch")
        identities[name] = identity
        started = time.monotonic()
        model = Reranker(
            config["base"],
            device=config["device"],
            max_length=config["max_length"],
            adapter=config.get("adapter"),
        )
        load_seconds = time.monotonic() - started
        started = time.monotonic()
        for t in tasks:
            for s in skills:
                rid = t["task_id"] + "::" + s["id"]
                inp = public[rid]
                reps = (
                    [
                        structured_representation(
                            t["request"], t["context"], s, support=False
                        )
                    ]
                    if name == "B2"
                    else [
                        representation(inp, a)
                        for a in (
                            ("applicability", "specificity_given_applicable")
                            if name == "J"
                            else ("applicability",)
                        )
                    ]
                )
                zz, observed = model.scores(reps)
                z = zz.detach().cpu().tolist()
                actual = [
                    {k: o[k] for k in ("input_sha256", "actual_tokens", "truncated")}
                    for o in observed
                ]
                if name != "B2" and actual != all_tokens[name][rid]["axes"]:
                    raise ValueError("prepared/forward token mismatch")
                records[rid]["logits"][name] = z if name == "J" else z[0]
                records[rid]["scores"][name] = (
                    sigmoid(z[0]) * sigmoid(z[1])
                    if name == "J"
                    else z[0]
                    if name == "B2"
                    else sigmoid(z[0])
                )
                records[rid]["token_inputs"][name] = actual
        costs[name] = {
            "model_load_seconds": load_seconds,
            "forward_seconds": time.monotonic() - started,
            "forward_calls": model.forward_calls,
        }
        del model
        import gc

        gc.collect()
    baseline = read_json(args.project_root / protocol["baselines"])
    for rid, r in records.items():
        for name, m in baseline["models"].items():
            pp = predict_text(m, public[rid])
            r["scores"][name] = pp[0] if isinstance(pp, list) else pp
        for name, pp in [
            ("global_prior", baseline["prior"]["global"]),
            (
                "skill_prior",
                baseline["prior"]["skills"].get(
                    r["skill_id"], baseline["prior"]["global"]
                ),
            ),
        ]:
            r["scores"][name] = pp[0] if isinstance(pp, list) else pp
        p = r["scores"]["cheap_text"]
        r["logits"]["cheap_text"] = math.log(max(p, 1e-12) / max(1 - p, 1e-12))
        r["policy_accepts"] = False
        if lock:
            for name, c in lock["calibrations"].items():
                prob = sigmoid(
                    c["mapping"]["a"] * r["logits"][name] + c["mapping"]["b"]
                )
                r["scores"][name + "_calibrated"] = prob
                if name == "A":
                    r["policy_accepts"] = (
                        r["input_eligible"]
                        and c["threshold"] is not None
                        and prob >= c["threshold"]
                    )
        r["execution_authority"] = "NONE"
    result = {
        "schema": "independent-predictions-v1",
        "split": args.split,
        "protocol_sha256": file_hash(args.protocol),
        "created_at": now(),
        "method_identities": identities,
        "environment": environment,
        "cost": costs,
        "rows": list(records.values()),
        "lock_sha256": file_hash(args.lock) if lock else None,
        "labels_read": False,
    }
    if lock:
        result["selections"] = select(
            rows, records, baseline["fixed"], lock["calibrations"]["A"]["threshold"]
        )
    write_json(args.output, result)
    write_json(
        args.output.with_suffix(".lock.json"),
        {
            "predictions_sha256": file_hash(args.output),
            "protocol_sha256": file_hash(args.protocol),
            "created_at": now(),
        },
    )
    return {
        "rows": len(records),
        "eligible": sum(r["input_eligible"] for r in records.values()),
        "cost": costs,
    }


def evaluate(predictions, labels, protocol):
    from .applicability_eval import axis_metrics, bootstrap_brier, ranking

    stream = {r["row_id"]: r for r in predictions["rows"]}
    rr = sorted(labels, key=lambda r: r["row_id"])
    metrics = {}
    if len(stream) != len(predictions["rows"]) or set(stream) != {
        r["row_id"] for r in rr
    }:
        raise ValueError("check score row mismatch")
    for name in sorted(next(iter(stream.values()))["scores"]):
        if name == "B2":
            continue
        pp = [stream[r["row_id"]]["scores"][name] for r in rr]
        if name == "J":
            joint = []
            for r in rr:
                a, s = targets(r)
                j = 0 if a == 0 else s if a == 1 else None
                joint.append(
                    {
                        **r,
                        "applicability_label": "UNKNOWN"
                        if j is None
                        else "APPLICABLE"
                        if j
                        else "NOT_APPLICABLE",
                        "specificity_label": "GENERAL_WORKFLOW" if j else None,
                    }
                )
            metrics[name] = {
                "joint": axis_metrics(joint, [[v, 0] for v in pp]),
                "task_specific_ranking": ranking(
                    rr, [[v, 1] for v in pp], rank_scores=pp
                ),
            }
        else:
            metrics[name] = axis_metrics(rr, [[v, 0] for v in pp])
    accepted = [r for r in rr if stream[r["row_id"]]["policy_accepts"]]

    def counts(xs):
        c = Counter(targets(r)[0] for r in xs)
        known = c[0.0] + c[1.0]
        return {
            "positive": c[1.0],
            "negative": c[0.0],
            "unknown": c[None],
            "known": known,
            "precision": c[1.0] / known if known else None,
            "groups": len({r["repair_group_id"] for r in xs}),
            "rows": len(xs),
        }

    def weighted(xs):
        known = [r for r in xs if targets(r)[0] is not None]
        weights = group_weights(known) if known else []
        return (
            sum(w * targets(r)[0] for r, w in zip(known, weights)) / sum(weights)
            if weights
            else None
        )

    ca = counts(accepted)
    total = counts(rr)
    ca["mechanism_weighted_precision"] = weighted(accepted)
    known = [r for r in rr if targets(r)[0] is not None]
    ww = group_weights(known) if known else []
    ca["mechanism_weighted_known_coverage"] = (
        sum(w for r, w in zip(known, ww) if stream[r["row_id"]]["policy_accepts"])
        / sum(ww)
        if ww
        else None
    )
    ca["known_coverage"] = ca["known"] / total["known"] if total["known"] else None
    ca["positive_recall"] = (
        ca["positive"] / total["positive"] if total["positive"] else None
    )
    selections = {}
    idx = {r["row_id"]: r for r in rr}
    for arm in ("B2", "C2", "T2", "F2"):
        selected = [
            idx[t["task_id"] + "::" + s]
            for t in predictions["selections"]
            for s in t[arm]
        ]
        selections[arm] = {
            **counts(selected),
            "mechanism_weighted_precision": weighted(selected),
            "full_k_tasks": sum(len(t[arm]) == 2 for t in predictions["selections"]),
            "fallback_tasks": sum(len(t[arm]) < 2 for t in predictions["selections"]),
        }
    comparisons = {
        arm: {
            "same": sum(set(t[arm]) == set(t["C2"]) for t in predictions["selections"]),
            "different": [
                t["task_id"]
                for t in predictions["selections"]
                if set(t[arm]) != set(t["C2"])
            ],
        }
        for arm in ("B2", "F2", "T2")
    }
    for name in metrics:
        if name == "J":
            continue
        aucs = []
        for group in sorted({r["repair_group_id"] for r in rr}):
            gr = [r for r in rr if r["repair_group_id"] == group]
            value = axis_metrics(
                gr, [[stream[r["row_id"]]["scores"][name], 0] for r in gr]
            )["auc"]
            if value is not None:
                aucs.append(value)
        metrics[name]["group_macro_auc"] = sum(aucs) / len(aucs) if aucs else None
        metrics[name]["auc_defined_groups"] = len(aucs)
    ap = [stream[r["row_id"]]["scores"]["A_calibrated"] for r in rr]
    tp = [stream[r["row_id"]]["scores"]["cheap_text_calibrated"] for r in rr]
    boot = bootstrap_brier(
        rr,
        [[v, 0] for v in ap],
        repeat=protocol["bootstrap"]["repetitions"],
        seed=protocol["bootstrap"]["seed"],
        reference=[[v, 0] for v in tp],
    )
    selection_boot = bootstrap_selections(
        rr, stream, predictions["selections"], protocol["bootstrap"]
    )
    return {
        "schema": "independent-results-v1",
        "label_meaning": "relative to same-model dual-context weak labels; no human truth",
        "tasks": len({r["task_id"] for r in rr}),
        "mechanisms": len({r["repair_group_id"] for r in rr}),
        "rows": len(rr),
        "prediction_coverage": len(stream),
        "eligible_rows": sum(x["input_eligible"] for x in stream.values()),
        "label_counts": total,
        "metrics": metrics,
        "acceptance": ca,
        "selections": selections,
        "set_comparisons": comparisons,
        "mechanism_bootstrap_selection": selection_boot,
        "paired_mechanism_bootstrap_brier_A_minus_text": boot,
        "deployment_recommendation": "KEEP_NATIVE",
    }


def bootstrap_selections(rows, stream, selections, rule):
    import random

    groups = sorted({r["repair_group_id"] for r in rows})
    by = {g: [r for r in rows if r["repair_group_id"] == g] for g in groups}
    si = {t["task_id"]: t for t in selections}
    rng = random.Random(rule["seed"])
    series = {
        n: []
        for n in (
            "pool_precision",
            "pool_coverage",
            "C2_precision",
            "C2_minus_B2_precision",
        )
    }
    empty = Counter()
    for _ in range(rule["repetitions"]):
        sample = []
        for i, g in enumerate(rng.choices(groups, k=len(groups))):
            sample += [
                {
                    **r,
                    "repair_group_id": str(i),
                    "parent_task_id": str(i) + r["parent_task_id"],
                }
                for r in by[g]
            ]
        known = [r for r in sample if targets(r)[0] is not None]
        w = group_weights(known) if known else []

        def precision(xs):
            xs = [r for r in xs if targets(r)[0] is not None]
            ww = group_weights(xs) if xs else []
            return (
                sum(v * targets(r)[0] for r, v in zip(xs, ww)) / sum(ww) if ww else None
            )

        pool = [r for r in sample if stream[r["row_id"]]["policy_accepts"]]
        cp = precision([r for r in sample if r["skill_id"] in si[r["task_id"]]["C2"]])
        bp = precision([r for r in sample if r["skill_id"] in si[r["task_id"]]["B2"]])
        vals = {
            "pool_precision": precision(pool),
            "pool_coverage": sum(
                v for r, v in zip(known, w) if stream[r["row_id"]]["policy_accepts"]
            )
            / sum(w)
            if w
            else None,
            "C2_precision": cp,
            "C2_minus_B2_precision": cp - bp
            if cp is not None and bp is not None
            else None,
        }
        for n, v in vals.items():
            if v is None:
                empty[n] += 1
            else:
                series[n].append(v)
    return {
        n: {
            "lower": sorted(v)[int(len(v) * 0.025)] if v else None,
            "upper": sorted(v)[min(len(v) - 1, int(len(v) * 0.975))] if v else None,
            "undefined_resamples": empty[n],
            "repetitions": rule["repetitions"],
            "unit": "repair mechanism",
            "warning": "zero-width empirical interval is not a population guarantee",
        }
        for n, v in series.items()
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--stage",
        choices=["preflight", "score", "calibrate", "lock", "check", "records"],
        required=True,
    )
    for name in ("tasks", "registry", "protocol", "project-root", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    for name in (
        "historical",
        "model-configs",
        "snapshots",
        "environment-facts",
        "environment-profile",
        "environment-assets",
        "scores",
        "cal-labels",
        "check-labels",
        "lock",
        "results",
    ):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--split", choices=["cal", "check"])
    p.add_argument("--lock-sha256")
    p.add_argument("--scores-sha256")
    args = p.parse_args(argv)
    if args.stage in {"score", "preflight"} and (args.cal_labels or args.check_labels):
        p.error("prediction stages cannot accept labels")
    if args.stage in {"calibrate", "lock"} and args.check_labels:
        p.error("calibration cannot accept check labels")
    protocol, tasks, skills = load(args)
    if args.stage == "preflight":
        result = {
            "roster": "VERIFIED",
            "tasks": len(tasks),
            "pairs": len(tasks) * len(skills),
            "model_calls": 0,
        }
    elif args.stage == "score":
        result = score_stage(args, protocol, tasks, skills)
    elif args.stage in {"calibrate", "lock"}:
        scores = read_json(args.scores)
        if scores["split"] != "cal" or scores["protocol_sha256"] != file_hash(
            args.protocol
        ):
            raise ValueError("cal score binding")
        expected = pairs([t for t in tasks if t["split"] == "cal"], skills)
        if len(scores["rows"]) != len(expected) or {
            r["row_id"] for r in scores["rows"]
        } != {r["row_id"] for r in expected}:
            raise ValueError("cal score row mismatch")
        labels = label_rows(args.cal_labels, expected)
        result = {
            "schema": "independent-policy-lock-v1",
            "protocol_sha256": file_hash(args.protocol),
            "created_at": now(),
            "cal_scores_sha256": file_hash(args.scores),
            "cal_labels_sha256": file_hash(args.cal_labels),
            "calibrations": calibrations(
                labels, {r["row_id"]: r for r in scores["rows"]}, protocol
            ),
            "execution_authority": "NONE",
            "meaning": "cal-only policy awaiting independent check",
        }
    else:
        checked(args.scores, args.scores_sha256)
        scores = read_json(args.scores)
        checked(args.lock, args.lock_sha256)
        if (
            scores["split"] != "check"
            or scores["protocol_sha256"] != file_hash(args.protocol)
            or scores["lock_sha256"] != file_hash(args.lock)
        ):
            raise ValueError("check prediction lock mismatch")
        labels = label_rows(
            args.check_labels,
            pairs([t for t in tasks if t["split"] == "check"], skills),
        )
        result = evaluate(scores, labels, protocol)
        if args.stage == "records":
            if not records_equal(result, read_json(args.results)):
                raise ValueError("records mismatch")
            result = {"records": "MATCHED", "rows": len(labels), "model_calls": 0}
    if args.stage != "score":
        write_json(args.output, result)
    print(
        json.dumps(
            result
            if args.stage in {"preflight", "score", "records"}
            else {"stage": args.stage, "output": str(args.output)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
