"""Thin aligned-protocol front door; historical commands retain frozen modules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .applicability_data import read_json, read_rows, write_json, file_hash
from .context import digest, FragmentBudget
from .decision_contract import (
    select_for_goal,
    aligned,
    metrics,
    priority,
    validate_contract,
    contract_identity,
)
from .gate import sigmoid
from .calibration_preflight import (
    report,
    input_identity,
    extract_repaired,
    safe_snapshot_path,
)

DEFAULT = Path("artifacts/conditional-applicability-v1")
NEW = Path("artifacts/decision-alignment-v1")
REGISTRY = Path("configs/conditional-applicability-v1/registry.json")
RULE = Path("configs/conditional-applicability-v1/protocol.json")
COMMANDS = {
    "select-for-goal",
    "decision-replay",
    "preflight",
    "advise",
    "aligned-score",
    "aligned-calibrate",
    "aligned-train",
}


def study(root):
    tasks = read_json(root / "tasks.json")
    from .applicability_data import validate_splits

    validate_splits(tasks)
    skills = read_json(REGISTRY)["skills"]
    identity = input_identity(tasks, skills, template_identity())
    return tasks, skills, identity


def template_identity():
    return {
        name: file_hash(Path(__file__).with_name(name))
        for name in ("pointwise_support.py", "reranker.py")
    }


def selection(root):
    bindings = read_json(root / "records-bindings.json")
    for name, expected in bindings.items():
        if (
            "training-lambda-" in name
            and ("-dev-" in name or name.endswith(("lambda-0.json", "lambda-1.json")))
        ) or name.endswith(("tasks.json", "labels.jsonl", "model-freeze.json")):
            if file_hash(root / Path(name).name) != expected:
                raise ValueError("saved development source identity mismatch: " + name)
    tasks, skills, identity = study(root)
    rows = [r for r in read_rows(root / "labels.jsonl") if r["split"] == "model-dev"]
    candidates = []
    frozen = read_json(root / "model-freeze.json")
    for name, expected in frozen["source_bindings"].items():
        if name.startswith("src/") or name.startswith(
            "configs/conditional-applicability-v1/"
        ):
            if file_hash(Path(name)) != expected:
                raise ValueError(
                    "frozen input/template changed; old predictions cannot be rebound"
                )
    for trial in frozen["trials"]:
        summary = read_json(root / (trial["candidate_id"] + ".json"))
        denominators = summary["masked_denominators"]
        spec = summary["config"]["lambda_spec"]
        checkpoint = next(e for e in summary["epochs"] if e["epoch"] == trial["epoch"])
        if checkpoint["checkpoint_sha256"] != trial["adapter_sha256"]:
            raise ValueError("checkpoint metadata identity mismatch")
        scored = read_json(root / f"{trial['candidate_id']}-dev-{trial['epoch']}.json")
        if (
            scored["metrics"]["checkpoint_sha256"] != trial["adapter_sha256"]
            or scored["metrics"]["epoch"] != trial["epoch"]
        ):
            raise ValueError("prediction checkpoint/epoch mismatch")
        candidates.append(
            {
                **trial,
                "supervised_denominators": {
                    "applicability": denominators[0],
                    "specificity_given_applicable": denominators[1] if spec > 0 else 0,
                },
                "rows": scored["rows"],
            }
        )
    selected = {
        target: select_for_goal(rows, candidates, target, identity)
        for target in ("applicability", "task_specific")
    }
    # Explicit numerical reproduction, not a reinterpretation of historical freeze.
    legacy = min(
        candidates,
        key=lambda c: (
            metrics(
                rows,
                [[sigmoid(z) for z in r["logits"]] for r in aligned(rows, c["rows"])],
                "applicability",
            )["applicability"]["log_loss"],
            c["candidate_id"],
            c["epoch"],
        ),
    )
    if (legacy["candidate_id"], legacy["epoch"]) != (
        frozen["selected"]["candidate_id"],
        frozen["selected"]["epoch"],
    ):
        raise ValueError("historical selection not reproduced")
    return {
        "schema": "decision-selection-v1",
        "analysis_scope": "RETROSPECTIVE_DIAGNOSTIC",
        "selection_data": "model-dev only",
        "new_forward_calls": 0,
        "legacy_selected": {
            k: legacy[k] for k in ("candidate_id", "epoch", "adapter_sha256")
        },
        "targets": selected,
    }


def validate_selected(root, contract):
    validate_contract(contract)
    expected = selection(root)["targets"][contract["decision_target"]]["contract"]
    for key in (
        "candidate_id",
        "epoch",
        "adapter_sha256",
        "supervised_denominators",
        "input_identity",
        "ranking_formula",
        "selection_metric",
    ):
        if contract.get(key) != expected[key]:
            raise ValueError(
                "contract differs from development-selected candidate: " + key
            )
    return contract


def replay(root, selected):
    rows = [r for r in read_rows(root / "labels.jsonl") if r["split"] == "check"]
    freeze = read_json(root / "model-freeze.json")
    streams = {}
    for name, filename, target, model in [
        (
            "legacy_product",
            "learned_raw-check-scores.json",
            "task_specific",
            freeze["selected"],
        ),
        (
            "A_app_only",
            "learned_raw-check-scores.json",
            "applicability",
            selected["targets"]["applicability"]["contract"],
        ),
        (
            "J_joint_specific",
            "joint_raw-check-scores.json",
            "task_specific",
            selected["targets"]["task_specific"]["contract"],
        ),
    ]:
        data = read_json(root / filename)
        if data.get("adapter_sha256") != model["adapter_sha256"]:
            streams[name] = {
                "status": "MISSING_CHECK_SCORES",
                "candidate_id": model["candidate_id"],
                "epoch": model["epoch"],
            }
            continue
        pp = [[sigmoid(z) for z in r["logits"]] for r in aligned(rows, data["rows"])]
        streams[name] = stream(rows, pp, target, model)
    baseline = {r["row_id"]: r for r in read_rows(root / "baseline-predictions.jsonl")}
    for name in ("global_prior", "skill_prior", "cheap_text", "skill_only"):
        pp = [baseline[r["row_id"]][name] for r in rows]
        for target in ("applicability", "task_specific"):
            streams[name + "_" + target] = stream(
                rows,
                pp,
                target,
                {
                    "candidate_id": name,
                    "selection_scope": "old frozen fit/model-dev baseline; task-specific hyperparameters not optimized",
                },
            )
    model = read_json(root / "baseline-models.json")
    fixed = model["fixed"]
    pp = [baseline[r["row_id"]]["skill_prior"] for r in rows]
    streams["fixed"] = {
        "candidate_id": "old fixed",
        "probabilities": "NOT_APPLICABLE",
        "ranking": metrics(rows, pp, "task_specific", fixed=fixed)["ranking"],
    }
    rank = aligned(rows, read_json(root / "original-rank-check-scores.json")["rows"])
    rank_values = [r["logits"][0] if "logits" in r else r["score"] for r in rank]
    streams["original_rank"] = {
        "candidate_id": "original_rank",
        "input_max_length": 1024,
        "support_input_max_length": 8192,
        "probability_metrics": "NOT_APPLICABLE: ordinal rank score",
        "ranking": metrics(rows, pp, "applicability", rank_scores=rank_values)[
            "ranking"
        ],
        "orders": orders(rows, rank_values),
    }
    streams["rank_plus_support"] = {
        "candidate_id": "original_rank + historical support",
        "threshold": None,
        "ranking": metrics(
            rows,
            pp,
            "applicability",
            accepted=[False] * len(rows),
            rank_scores=rank_values,
        )["ranking"],
        "accepted_precision": None,
        "status": "NOT_ESTABLISHED",
    }
    return {
        "schema": "decision-replay-v1",
        "analysis_scope": "RETROSPECTIVE_DIAGNOSTIC",
        "new_forward_calls": 0,
        "operation": "saved-score arithmetic; no retokenization or model reload",
        "streams": streams,
        "runtime_effectiveness": "NOT_RUN",
    }


def orders(rows, values):
    return {
        task: [
            {"skill_id": rows[i]["skill_id"], "priority_score": values[i]}
            for i in sorted(
                [i for i, r in enumerate(rows) if r["task_id"] == task],
                key=lambda i: (-values[i], rows[i]["skill_id"]),
            )
        ]
        for task in sorted({r["task_id"] for r in rows})
    }


def stream(rows, pp, target, model):
    return {
        "status": "SAVED_SCORE_ARITHMETIC",
        "model": model,
        "decision_target": target,
        "metrics": metrics(rows, pp, target),
        "orders": orders(rows, priority(pp, target)),
        "supported": False,
    }


def tokenize(tasks, skills, config):
    """Optional local tokenizer only: do not hash/open model weights or build models."""
    from types import SimpleNamespace
    from transformers import AutoTokenizer
    from .pointwise_support import public_input, representation
    from .reranker import structured_tokens
    from hermes_skilleval.vendor.skillrouter_common import get_reranker_template_tokens

    base = Path(config["base"])
    for name in ("tokenizer.json", "tokenizer_config.json"):
        expected = config.get("base_files", {}).get(name)
        if expected is None or file_hash(base / name) != expected:
            raise ValueError("tokenizer identity mismatch")
    tokenizer = AutoTokenizer.from_pretrained(
        str(base), local_files_only=True, trust_remote_code=False, padding_side="left"
    )
    prefix, suffix = get_reranker_template_tokens(tokenizer)
    shell = SimpleNamespace(
        tokenizer=tokenizer,
        prefix=prefix,
        suffix=suffix,
        max_length=config["max_length"],
    )
    result = {}
    for task in tasks:
        for skill in skills:
            records = []
            for axis in ("applicability", "specificity_given_applicable"):
                _, r = structured_tokens(
                    shell, representation(public_input(task, skill), axis)
                )
                records.append(
                    {k: r[k] for k in ("input_sha256", "actual_tokens", "truncated")}
                )
            result[task["task_id"] + "::" + skill["id"]] = {
                "visible": all(not r["truncated"] for r in records),
                "axes": records,
            }
    return result


def run_preflight(args):
    if (
        args.operation == "train-structure"
        and getattr(args, "command", None) == "aligned-train"
    ):
        return training_preflight(args)
    tasks, skills, _ = study(args.root)
    split = (
        "fit"
        if args.operation == "train-structure"
        else "model-dev"
        if args.operation == "dev-score"
        else args.split
    )
    tasks = [t for t in tasks if t["split"] == split]
    repairs = []
    if args.snapshots:
        for task in tasks:
            c = task["context"]
            snapshot = safe_snapshot_path(args.snapshots, task["task_id"])
            for name, source in c.get("source_hashes", {}).items():
                if (
                    source.get("full_file_sha256")
                    and file_hash(safe_snapshot_path(snapshot, name))
                    != source["full_file_sha256"]
                ):
                    raise ValueError("snapshot source mismatch")
            task["context"] = extract_repaired(
                snapshot,
                task["request"],
                c["environment"],
                FragmentBudget(**c["budget"]),
            )
            repairs.append(
                {
                    "task_id": task["task_id"],
                    "original_state": c["state"],
                    "new_state": task["context"]["state"],
                    "original_missing": c["missing"],
                    "new_missing": task["context"]["missing"],
                    "corrections": task["context"]["prose_call_corrections"],
                    "source_files_verified": len(c.get("source_hashes", {})),
                    "original_snapshot_id": c["snapshot_id"],
                    "new_snapshot_id": task["context"]["snapshot_id"],
                    "old_scores_reused": False,
                }
            )
    identity = input_identity(tasks, skills, template_identity())
    token_records = (
        tokenize(tasks, skills, read_json(args.tokenizer_config))
        if args.tokenizer_config
        else None
    )
    # Cal labels are read only after a validated development-selected contract.
    labels = None
    if args.operation in {"calibrate", "cal-score"}:
        if split != "cal":
            raise ValueError("cal operation requires cal split")
        if not args.contract:
            raise ValueError("cal preflight requires frozen decision contract")
        validate_selected(args.root, read_json(args.contract))
        labels = [
            r for r in read_rows(args.root / "labels.jsonl") if r["split"] == "cal"
        ]
    result = report(
        tasks,
        skills,
        read_json(RULE),
        labels=labels,
        tokens=token_records,
        environment_known=read_json(args.environment_facts)
        if args.environment_facts
        else False,
        requested_operation=args.operation,
        identity=identity,
    )
    result["tokenization"] = (
        "LOCAL_TOKENIZER_ONLY" if token_records else "TOKENIZATION_UNCHECKED"
    )
    result["tokens"] = token_records
    result["context_repairs"] = repairs
    result["execution_environment"] = (
        "UNKNOWN: repository dependencies unverified; cannot infer from text-study network setting"
    )
    write_json(args.output, result)
    return result


def main():
    if not any(c in sys.argv[1:] for c in COMMANDS) and not (
        len(sys.argv) == 1 or sys.argv[1:] == ["--help"]
    ):
        from .applicability_cli import main as legacy

        return legacy()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DEFAULT)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("select-for-goal", "decision-replay"):
        a = sub.add_parser(name)
        a.add_argument("--output", type=Path, default=NEW)
    a = sub.add_parser("preflight")
    a.add_argument(
        "--operation",
        choices=[
            "structure",
            "calibrate",
            "cal-score",
            "dev-score",
            "advisory",
            "train-structure",
        ],
        default="structure",
    )
    a.add_argument(
        "--split", choices=["fit", "model-dev", "cal", "check"], default="cal"
    )
    a.add_argument("--contract", type=Path)
    a.add_argument("--snapshots", type=Path)
    a.add_argument("--tokenizer-config", type=Path)
    a.add_argument("--environment-facts", type=Path)
    a.add_argument("--output", type=Path, required=True)
    for name in ("aligned-score", "aligned-calibrate", "aligned-train"):
        a = sub.add_parser(name, help="Preflight guarded new-protocol operation")
        a.add_argument("--config", type=Path, required=True)
        a.add_argument("--contract", type=Path, required=name != "aligned-train")
        a.add_argument(
            "--split", choices=["fit", "model-dev", "cal", "check"], default="cal"
        )
        a.add_argument("--snapshots", type=Path)
        a.add_argument("--environment-facts", type=Path)
        a.add_argument("--scores", type=Path)
        a.add_argument("--output", type=Path, required=True)
    a = sub.add_parser("advise")
    a.add_argument("--config", type=Path, required=True)
    a.add_argument("--contract", type=Path, required=True)
    a.add_argument("--input", type=Path, required=True)
    a.add_argument("--calibration", type=Path)
    a.add_argument("--manifest", type=Path, required=True)
    a.add_argument("--environment-known", action="store_true")
    a.add_argument(
        "--context-state",
        choices=["usable", "partial", "unknown", "unavailable"],
        default="unknown",
    )
    a.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.command in {"select-for-goal", "decision-replay"}:
        selected = selection(args.root)
        write_json(args.output / "dev-selection.json", selected)
        contracts = {k: v["contract"] for k, v in selected["targets"].items()}
        write_json(args.output / "decision-contracts.json", contracts)
        for k, v in contracts.items():
            write_json(args.output / (k + "-contract.json"), v)
        if args.command == "decision-replay":
            write_json(args.output / "ranking-replay.json", replay(args.root, selected))
        print(
            json.dumps(
                {
                    "status": "RECOMPUTED",
                    "new_forward_calls": 0,
                    "output": str(args.output),
                }
            )
        )
    elif args.command == "advise":
        from .decision_contract import guarded_score
        from .pointwise_support import PublicInput

        contract = read_json(args.contract)
        validate_contract(contract)
        manifest = read_json(args.manifest)
        frozen_contract = manifest[contract["decision_target"]]
        validate_contract(frozen_contract)
        if contract_identity(contract) != contract_identity(frozen_contract):
            raise ValueError("online contract differs from frozen manifest")
        config = read_json(args.config)
        public = PublicInput(**read_json(args.input))
        task = {
            "task_id": "public",
            "request": public.request,
            "context": {"summary": public.context},
        }
        skill = {
            "id": "public",
            "name": public.skill_name,
            "description": public.skill_description,
            "body": public.skill_body,
        }
        token = tokenize([task], [skill], config)["public::public"]
        token["public_input_identity"] = digest(public.__dict__)
        result = guarded_score(
            public,
            config,
            contract,
            {
                "context_state": args.context_state,
                "environment_known": args.environment_known,
            },
            token,
            calibration=read_json(args.calibration) if args.calibration else None,
        )
        write_json(args.output, result)
        print(json.dumps({"status": result["status"], "accepted": result["accepted"]}))
        if result["status"] == "BLOCKED":
            raise SystemExit(2)
    else:
        if args.command.startswith("aligned-"):
            args.operation = (
                "train-structure"
                if args.command == "aligned-train"
                else "calibrate"
                if args.command == "aligned-calibrate"
                else "cal-score"
                if args.split == "cal"
                else "dev-score"
                if args.split == "model-dev"
                else "advisory"
            )
            args.tokenizer_config = args.config
            # Fast structural cal upper bound before even tokenizer construction.
            if args.operation in {"calibrate", "cal-score"}:
                saved = args.tokenizer_config
                args.tokenizer_config = None
                result = run_preflight(args)
                args.tokenizer_config = saved
                if (
                    result["calibration"]["context_known_group_upper_bound"]
                    < result["calibration"]["min_accepted_groups"]
                ):
                    print(
                        json.dumps(
                            {
                                "status": "BLOCKED",
                                "reason": "INSUFFICIENT_CONTEXT_GROUPS",
                                "model_constructions": 0,
                            }
                        )
                    )
                    raise SystemExit(2)
        result = run_preflight(args)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "status",
                        "requested_operation",
                        "scorer_calls",
                        "model_constructions",
                    )
                }
            )
        )
        if result["status"] == "BLOCKED":
            raise SystemExit(2)
        if args.command.startswith("aligned-"):
            execute_batch(args, result)


def execute_batch(args, preflight):
    """Called only after operation-specific preflight; writes a new identity stream."""
    config = read_json(args.config)
    if args.command == "aligned-train":
        # Structure-only gate is independent of cal/check; never invoked by this Goal.
        from .pointwise_support import train

        if file_hash(args.config) != preflight["config_sha256"] or any(
            file_hash(path) != expected
            for path, expected in preflight["training_sources"].items()
        ):
            raise ValueError("training inputs changed after preflight")
        return train(args.config)
    contract = read_json(args.contract)
    validate_contract(contract)
    if (
        config.get("adapter_files", {}).get("adapter_model.safetensors")
        != contract["adapter_sha256"]
    ):
        raise ValueError("candidate/checkpoint mismatch")
    if args.command == "aligned-calibrate":
        if not args.scores:
            raise ValueError("scores required after successful calibration preflight")
        scores = read_json(args.scores)
        if (
            scores.get("input_identity") != preflight["input_identity"]
            or scores.get("contract_identity") != contract_identity(contract)
            or scores.get("split") != "cal"
        ):
            raise ValueError("new input/contract/scores binding mismatch")
        from .applicability_eval import (
            fit_calibration,
            precision_curve,
            choose_threshold,
        )

        from .pointwise_support import scorer_identity

        if scores.get("actual_adapter_sha256") != contract[
            "adapter_sha256"
        ] or scores.get("scorer_identity") != scorer_identity(config):
            raise ValueError("calibration model identity mismatch")
        rr = [r for r in read_rows(args.root / "labels.jsonl") if r["split"] == "cal"]
        observed = aligned(rr, scores["rows"])
        mapping = fit_calibration(
            rr, [r["logits"] for r in observed], 0, read_json(RULE)["calibration"]
        )
        pp = [
            [sigmoid(mapping["a"] * r["logits"][0] + mapping["b"]), 0] for r in observed
        ]
        facts = {r["row_id"]: r for r in preflight["rows"]}
        if any(
            r.get("public_input_identity")
            != facts[r["row_id"]]["public_input_identity"]
            for r in observed
        ):
            raise ValueError("scored public inputs differ from preflight")
        eligible = [facts[r["row_id"]]["eligible"] for r in rr]
        chosen = choose_threshold(
            precision_curve(rr, pp, eligible), read_json(RULE)["operating_point"]
        )
        result = {
            "schema": "aligned-calibration-v1",
            "axis": "applicability",
            "public_input_identities": [
                r["public_input_identity"]
                for r in observed
                if facts[r["row_id"]]["eligible"]
            ],
            "mapping": mapping,
            "threshold": chosen["threshold"] if chosen else None,
            "operating_point": chosen,
            "input_identity": preflight["input_identity"],
            "contract_identity": contract_identity(contract),
            "scorer_identity": scores["scorer_identity"],
            "analysis_scope": "RETROSPECTIVE_DIAGNOSTIC",
            "status": "RETROSPECTIVE_ONLY" if chosen else "NOT_ESTABLISHED",
        }
        write_json(
            args.output.with_name(args.output.stem + "-calibration.json"), result
        )
        return result
    from .pointwise_support import scorer_identity, public_input
    from .reranker import Reranker
    from .decision_contract import score_axes

    tasks, skills, _ = study(args.root)
    tasks = [t for t in tasks if t["split"] == args.split]
    if args.snapshots:
        for t in tasks:
            c = t["context"]
            t["context"] = extract_repaired(
                safe_snapshot_path(args.snapshots, t["task_id"]),
                t["request"],
                c["environment"],
                FragmentBudget(**c["budget"]),
            )
    if (
        input_identity(tasks, skills, template_identity())
        != preflight["input_identity"]
    ):
        raise ValueError("input changed after preflight")
    identity = scorer_identity(config)
    ranker = Reranker(
        config["base"],
        device=config["device"],
        max_length=config["max_length"],
        adapter=config.get("adapter"),
    )
    records = []
    for task in tasks:
        for skill in skills:
            observed = score_axes(ranker, public_input(task, skill), contract)
            records.append(
                {
                    "row_id": task["task_id"] + "::" + skill["id"],
                    "public_input_identity": digest(public_input(task, skill).__dict__),
                    "logits": observed["logits"],
                    "formula_id": observed["formula_id"],
                    "output_axes": observed["output_axes"],
                    "priority_score": observed["priority_score"],
                }
            )
    result = {
        "schema": "aligned-scores-v1",
        "input_identity": preflight["input_identity"],
        "contract_identity": contract_identity(contract),
        "scorer_identity": identity,
        "actual_adapter_sha256": config["adapter_files"]["adapter_model.safetensors"],
        "split": args.split,
        "rows": records,
        "analysis_scope": "RETROSPECTIVE_DIAGNOSTIC",
    }
    write_json(args.output.with_name(args.output.stem + "-scores.json"), result)
    return result


def training_preflight(args):
    from .applicability_data import validate_splits, targets

    if args.snapshots:
        raise ValueError(
            "training must consume its exact configured tasks; snapshot substitution forbidden"
        )
    config = read_json(args.config)
    tasks = read_json(config["tasks"])
    validate_splits(tasks)
    skills = read_json(config["registry"])["skills"]
    rows = [
        r for r in read_rows(config["labels"]) if r["split"] in {"fit", "model-dev"}
    ]
    by = {t["task_id"]: t for t in tasks}
    if not rows or len({r["row_id"] for r in rows}) != len(rows):
        raise ValueError("invalid training label rows")
    skill_ids = {s["id"] for s in skills}
    for r in rows:
        if (
            r["skill_id"] not in skill_ids
            or r["row_id"] != r["task_id"] + "::" + r["skill_id"]
        ):
            raise ValueError("training skill/row identity mismatch")
        t = by[r["task_id"]]
        if r["split"] != t["split"] or r["repair_group_id"] != t["repair_group_id"]:
            raise ValueError("training label split/group mismatch")
        targets(r)
    fit = [r for r in rows if r["split"] == "fit"]
    if (
        not fit
        or not any(r["split"] == "model-dev" for r in rows)
        or not any(targets(r)[0] is not None for r in fit)
    ):
        raise ValueError("fit supervision and model-dev required")
    if config.get("lambda_spec", 0) > 0 and not any(
        targets(r)[1] is not None for r in fit
    ):
        raise ValueError("specificity supervision required")
    used = [t for t in tasks if t["split"] in {"fit", "model-dev"}]
    tokens = tokenize(used, skills, config)
    result = report(
        used,
        skills,
        read_json(RULE),
        tokens=tokens,
        requested_operation="train-structure",
        identity=input_identity(used, skills, template_identity()),
    )
    result["config_sha256"] = file_hash(args.config)
    result["training_sources"] = {
        config[k]: file_hash(config[k]) for k in ("tasks", "labels", "registry")
    }
    write_json(args.output, result)
    return result


if __name__ == "__main__":
    main()
