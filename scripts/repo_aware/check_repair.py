"""Recompute repair support and execution evidence without models or Docker."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from hermes_skilleval.repo_routing.calibration import calibrate, predict
from hermes_skilleval.repo_routing.support_cli import metrics
from recompute_execution import recompute


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root):
    labels = read(root / "support-labels.json")
    repository = root.resolve().parents[1]
    registry = read(repository / "configs/repo-portability/skills-v1/registry.json")
    skills = {s["id"]: s for s in registry["skills"]}
    groups = {}
    for row in labels["rows"]:
        task = read(root / "public-requests.json")[row["task_id"]]
        for judgment in row["judgments"]:
            assert (
                judgment["quote"] in skills[row["skill_id"]][judgment["source_field"]]
            )
            assert judgment["request_quote"] in task["text"]
        groups.setdefault(row["family"], set()).add(row["split"])
        assert row["source"] == "model_judged_text" and not row["human_reviewed"]
    assert all(len(splits) == 1 for splits in groups.values())
    assert len({(r["task_id"], r["skill_id"]) for r in labels["rows"]}) == 100
    cal = read(root / "cal-scores.json")
    checks = read(root / "check-scores.json")
    saved = read(root / "calibration.json")
    frozen = read(root / "calibration-freeze.json")
    scorer = read(root / "scorer-freeze.json")
    assert frozen["calibration_sha256"] == sha(root / "calibration.json")
    assert scorer["labels_sha256"] == sha(root / "support-labels.json")
    for name, expected in scorer["source_sha256"].items():
        assert (
            sha(repository / "src/hermes_skilleval/repo_routing" / (name + ".py"))
            == expected
        )
    assert (
        cal["identity"] == checks["identity"] == saved["identity"] == scorer["identity"]
    )
    for scores, split in [(cal, "support-cal"), (checks, "support-check")]:
        assert scores["split"] == split
        assert scores["labels_sha256"] == sha(root / "support-labels.json")
        expected = {
            (r["task_id"], r["skill_id"]): r
            for r in labels["rows"]
            if r["split"] == split
        }
        assert len(scores["rows"]) == len(expected)
        for row in scores["rows"]:
            original = expected[(row["task_id"], row["skill_id"])]
            assert all(row[k] == v for k, v in original.items())
            assert row["input"]["sections"]
    rebuilt = calibrate(
        cal["rows"], cal["identity"], precision_target=0.9, minimum_families=2
    )
    assert all(abs(saved[k] - rebuilt[k]) < 1e-10 for k in ("a", "b"))
    assert saved["threshold"] == rebuilt["threshold"] is None
    assert saved["status"] == rebuilt["status"] == "NO_VALID_OPERATING_POINT"
    rows = [
        {
            **r,
            "prediction": predict(saved, r["raw_support_score"], checks["identity"]),
            "accepted": False,
        }
        for r in checks["rows"]
    ]
    measured = metrics(rows)
    stored = read(root / "support-check.json")["metrics"]
    for key in ("accepted", "true_positive", "false_positive", "unknown", "recall"):
        assert measured[key] == stored[key]
    assert (
        abs(measured["family_weighted_brier"] - stored["family_weighted_brier"]) < 1e-10
    )
    execution = []
    for phase in ("execution-prelaunch", "execution-smoke"):
        for condition in ("N", "B2", "C2"):
            path = root / phase / condition / "index.json"
            result = recompute(path)
            assert result["planned_cells"] == 1
            execution.append(
                {"phase": phase, "condition": condition, **result["rows"][0]}
            )
    return {
        "schema": "repair-recomputed-v1",
        "implementation": "PARTIAL",
        "support_validation": "DATA_SIGNAL_INSUFFICIENT",
        "runtime_validation": "FALLBACK_ONLY",
        "utility": "INCONCLUSIVE",
        "label_counts": dict(Counter(r["label"] for r in labels["rows"])),
        "independent_groups": len(groups),
        "calibration_status": rebuilt["status"],
        "check_metrics": measured,
        "execution_attempts": execution,
        "main_planned_cells": 12,
        "installation_smoke_cells": 3,
        "main_unexecuted_cells": 9,
        "unexecuted_reason": "NO_VALID_SUPPORT_OPERATING_POINT",
        "limits": "Records-only arithmetic and binding checks; no re-execution, human truth, causal utility or supported C2 certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records", type=Path, default=Path("artifacts/repo-aware-routing-r-repair-v1")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(check(args.records), indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")
