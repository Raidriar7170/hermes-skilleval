"""Post-check descriptive slices; never changes frozen predictions or policy."""

import argparse
import json
from pathlib import Path

from hermes_skilleval.repo_routing.applicability_data import (
    file_hash,
    group_weights,
    read_rows,
    targets,
)
from hermes_skilleval.repo_routing.applicability_eval import axis_metrics, ranking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((args.root / "check-scores.lock.json").read_text())
    scores_path = args.root / "check-scores.json"
    if file_hash(scores_path) != lock["predictions_sha256"]:
        raise ValueError("prediction lock mismatch")
    scores = json.loads(scores_path.read_text())
    rows = read_rows(args.root / "check-labels.jsonl")
    stream = {r["row_id"]: r for r in scores["rows"]}
    if set(stream) != {r["row_id"] for r in rows}:
        raise ValueError("label alignment mismatch")
    names = (
        "A",
        "A_calibrated",
        "cheap_text",
        "cheap_text_calibrated",
        "skill_only",
        "skill_prior",
        "global_prior",
        "frozen",
    )
    slices = {}
    for dimension in ("skill_id", "repository", "task_id"):
        slices[dimension] = {}
        for value in sorted({r[dimension] for r in rows}):
            subset = [r for r in rows if r[dimension] == value]
            slices[dimension][value] = {
                name: {
                    k: v
                    for k, v in axis_metrics(
                        subset,
                        [[stream[r["row_id"]]["scores"][name], 0] for r in subset],
                    ).items()
                    if k != "reliability"
                }
                for name in names
            }
    ranks = {}
    for name in ("A", "J", "cheap_text", "B2"):
        pp = [stream[r["row_id"]]["scores"][name] for r in rows]
        ranks[name] = ranking(rows, [[v, 1] for v in pp], rank_scores=pp)
    # Evaluate the actual fixed arm without creating a post-hoc alternative.
    fixed = {}
    row_index = {r["task_id"]: r for r in rows}
    for selection in scores["selections"]:
        fixed[row_index[selection["task_id"]]["repository"]] = selection["F2"]
    fixed["default"] = []
    ranks["F2"] = ranking(rows, [[0, 0] for _ in rows], fixed=fixed)
    known = [r for r in rows if targets(r)[0] is not None]
    weights = dict(zip((r["row_id"] for r in known), group_weights(known)))
    result = {
        "purpose": "post-check descriptive appendix; no method selection or refitting",
        "predictions_sha256": file_hash(scores_path),
        "labels_sha256": file_hash(args.root / "check-labels.jsonl"),
        "model_calls": 0,
        "limitations": [
            "same-model weak labels; subgroup comparisons not preregistered",
            "no multiple-comparison claim; not repair utility",
            "within-skill AUC undefined when labels contain only one class",
            "ranking is advisory; all check inputs lack live support eligibility",
        ],
        "slices": slices,
        "task_specific_ranking": ranks,
        "known_masked_probability_weights": weights,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
