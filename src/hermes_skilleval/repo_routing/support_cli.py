"""Real support scoring and family-separated development calibration/checks."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from hermes_skilleval.repo_routing.context import (
    extract_fragments,
    FragmentBudget,
)
from hermes_skilleval.repo_routing.policy import read_config
from hermes_skilleval.repo_routing.support import (
    score_support,
    support_identity,
    contradictions,
)
from hermes_skilleval.repo_routing.calibration import (
    fit,
    calibrate,
    predict,
    binary_rows,
    input_eligible,
)


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def metrics(rows):
    data = binary_rows(rows)

    def summarize(items):
        accepted = [r for r in items if r.get("accepted")]
        positive = [r for r in items if r["label"] == "SUPPORTED"]
        tp = sum(r["label"] == "SUPPORTED" for r in accepted)
        return dict(
            rows=len(items),
            positives=len(positive),
            accepted=len(accepted),
            true_positive=tp,
            false_positive=sum(
                r["label"] in {"NOT_APPLICABLE", "CONTRADICTED"} for r in accepted
            ),
            unknown=sum(r["label"] == "UNKNOWN" for r in items),
            accepted_unknown=sum(r["label"] == "UNKNOWN" for r in accepted),
            precision=tp / sum(r["label"] != "UNKNOWN" for r in accepted)
            if any(r["label"] != "UNKNOWN" for r in accepted)
            else None,
            recall=tp / len(positive) if positive else None,
        )

    result = summarize(rows)
    result["families"] = {
        f: summarize([r for r in rows if r["family"] == f])
        for f in sorted({r["family"] for r in rows})
    }
    result["skills"] = {
        s: summarize([r for r in rows if r["skill_id"] == s])
        for s in sorted({r["skill_id"] for r in rows})
    }
    if data and all("prediction" in r for r in data):
        import math

        result["family_weighted_brier"] = sum(
            r["weight"] * (r["prediction"] - r["y"]) ** 2 for r in data
        )
        result["family_weighted_log_loss"] = -sum(
            r["weight"]
            * (
                r["y"] * math.log(max(1e-12, r["prediction"]))
                + (1 - r["y"]) * math.log(max(1e-12, 1 - r["prediction"]))
            )
            for r in data
        )
        prevalence = sum(r["weight"] * r["y"] for r in data)
        result["constant_prevalence_brier"] = prevalence * (1 - prevalence)
        result["bins"] = [
            dict(
                lower=i / 5,
                count=len(b),
                mean_prediction=sum(r["prediction"] for r in b) / len(b) if b else None,
                positive_fraction=sum(r["y"] for r in b) / len(b) if b else None,
            )
            for i in range(5)
            for b in [
                [
                    r
                    for r in data
                    if i / 5 <= r["prediction"] <= (i + 1) / 5
                    and (i == 4 or r["prediction"] < (i + 1) / 5)
                ]
            ]
        ]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["score", "fit-diagnostic", "calibrate", "check"])
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--config", type=Path)
    p.add_argument("--tasks", type=Path)
    p.add_argument("--registry", type=Path)
    p.add_argument("--split", choices=["support-fit", "support-cal", "support-check"])
    p.add_argument("--scores", type=Path)
    p.add_argument("--model", type=Path)
    p.add_argument("--protocol", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    labels = json.loads(a.labels.read_text())
    label_hash = hashlib.sha256(a.labels.read_bytes()).hexdigest()
    if a.command == "score":
        from hermes_skilleval.repo_routing.reranker import (
            Reranker,
            structured_representation,
        )

        config = read_config(a.config)
        skills = {s["id"]: s for s in json.loads(a.registry.read_text())["skills"]}
        for name, expected in config.get("model_files", {}).get("reranker", {}).items():
            with (Path(config["reranker_path"]) / name).open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("frozen base model file changed")
        for name, key in (
            ("adapter_model.safetensors", "adapter_sha256"),
            ("adapter_config.json", "adapter_config_sha256"),
        ):
            if (
                hashlib.sha256(
                    (Path(config["adapter"]) / name).read_bytes()
                ).hexdigest()
                != config[key]
            ):
                raise ValueError("frozen adapter changed")
        identity = support_identity(config)
        selected = [r for r in labels["rows"] if r["split"] == a.split]
        ranker = Reranker(
            config["reranker_path"],
            device=config["profile"]["device"],
            max_length=config.get("max_length", 1024),
            adapter=config["adapter"],
        )
        support_ranker = ranker
        if config.get("support_model", "rank-adapter") == "base":
            support_ranker = Reranker(
                config["reranker_path"],
                device=config["profile"]["device"],
                max_length=config.get("support_max_length", 8192),
            )
        elif config.get("support_model", "rank-adapter") != "rank-adapter":
            raise ValueError("unknown support model")
        rows = []
        support_forwards = 0
        started = time.monotonic()
        for task_id in sorted({r["task_id"] for r in selected}):
            task = a.tasks / task_id
            request = (task / "public.md").read_text()
            context = extract_fragments(
                task / "base",
                request,
                {"network": "disabled"},
                FragmentBudget(**config.get("fragment_budget", {})),
            )
            for label in [r for r in selected if r["task_id"] == task_id]:
                skill = skills[label["skill_id"]]
                before_support_calls = support_ranker.forward_calls
                result = score_support(
                    request,
                    context,
                    skill,
                    support_ranker,
                    max_length=config.get("support_max_length", 8192),
                )
                support_forwards += support_ranker.forward_calls - before_support_calls
                visible = "\n".join(
                    s["visible_text"]
                    for s in result["input"]["sections"]
                    if s["section"] in ("metadata", "evidence")
                )
                quote_visible = all(
                    q in visible for q in label.get("support_quotes", [])
                )
                ranks, rank_inputs = ranker.scores(
                    [structured_representation(request, context, skill, support=False)]
                )
                rows.append(
                    {
                        **label,
                        **result,
                        "quote_visible": quote_visible,
                        "visible": result["visible"] and quote_visible,
                        "conflict": bool(
                            contradictions(request, skill, {"network": "disabled"})
                        ),
                        "rank_score": float(ranks.detach().cpu()[0]),
                        "rank_input": rank_inputs[0],
                        "context": context,
                    }
                )
            print(
                json.dumps(
                    {
                        "task": task_id,
                        "rows": len(rows),
                        "elapsed": time.monotonic() - started,
                    }
                ),
                flush=True,
            )
        write_new(
            a.output,
            dict(
                schema="repair-support-scores-v1",
                identity=identity,
                labels_sha256=label_hash,
                split=a.split,
                rows=rows,
                wall_seconds=time.monotonic() - started,
                forwards=ranker.forward_calls
                + (support_ranker.forward_calls if support_ranker is not ranker else 0),
                rank_forwards=ranker.forward_calls
                - (support_forwards if support_ranker is ranker else 0),
                support_forwards=support_forwards,
                loaded_source_sha256={
                    n: hashlib.sha256(
                        Path(__file__).with_name(n + ".py").read_bytes()
                    ).hexdigest()
                    for n in ("context", "reranker", "support", "support_cli")
                },
            ),
        )
        return
    scores = json.loads(a.scores.read_text())
    if scores["labels_sha256"] != label_hash:
        raise ValueError("labels changed after scores")
    rows = scores["rows"]
    identity = scores["identity"]
    if a.command == "fit-diagnostic":
        if scores["split"] != "support-fit":
            raise ValueError("fit-only diagnostic")
        predictions = []
        for family in sorted({r["family"] for r in rows}):
            model = fit([r for r in rows if r["family"] != family], identity)
            predictions.extend(
                {**r, "prediction": predict(model, r["raw_support_score"], identity)}
                for r in rows
                if r["family"] == family
            )
        known = binary_rows(predictions)
        positives = [r for r in known if r["y"]]
        negatives = [r for r in known if not r["y"]]
        auc = sum(
            (p["raw_support_score"] > n["raw_support_score"])
            + 0.5 * (p["raw_support_score"] == n["raw_support_score"])
            for p in positives
            for n in negatives
        ) / (len(positives) * len(negatives))
        write_new(
            a.output,
            dict(
                identity=identity,
                raw_auc=auc,
                metrics=metrics(predictions),
                note="Fit-only development diagnostic. AUC is row-pair descriptive, not independent-task sample size.",
            ),
        )
    elif a.command == "calibrate":
        if scores["split"] != "support-cal":
            raise ValueError("calibration-only fit")
        protocol = json.loads(a.protocol.read_text())
        start = time.monotonic()
        model = calibrate(
            rows,
            identity,
            precision_target=protocol["precision_target"],
            minimum_families=protocol["minimum_accepted_positive_families"],
        )
        model["wall_seconds"] = time.monotonic() - start
        model["labels_sha256"] = label_hash
        write_new(a.output, model)
        reloaded = json.loads(a.output.read_text())
        assert all(
            predict(model, r["raw_support_score"], identity)
            == predict(reloaded, r["raw_support_score"], identity)
            for r in rows
        )
        print(
            json.dumps(
                {
                    "status": model["status"],
                    "threshold": model["threshold"],
                    "reload": "EXACT_MATCH",
                }
            )
        )
    else:
        if scores["split"] != "support-check":
            raise ValueError("check-only reporting")
        model = json.loads(a.model.read_text())
        predicted = []
        for row in rows:
            value = predict(model, row["raw_support_score"], identity)
            accepted = (
                model["threshold"] is not None
                and value >= model["threshold"]
                and input_eligible(row)
            )
            predicted.append({**row, "prediction": value, "accepted": accepted})
        write_new(
            a.output,
            dict(
                identity=identity,
                threshold=model["threshold"],
                metrics=metrics(predicted),
                rows=predicted,
                scope="previously observed development check; model judged text, not repair success",
            ),
        )


if __name__ == "__main__":
    main()
