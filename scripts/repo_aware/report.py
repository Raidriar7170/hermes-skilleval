"""Paired family bootstrap and compact report from independently recomputed records."""

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import statistics

from recompute_execution import recompute


def interval(values):
    if not values:
        return {"n": 0, "mean": None, "interval_95": None}
    rng = random.Random(7170)
    samples = sorted(
        statistics.mean(rng.choices(values, k=len(values))) for _ in range(2000)
    )
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "interval_95": [samples[49], samples[1949]],
        "degenerate": len(set(values)) == 1,
        "limitation": "Small family sample; a degenerate interval does not establish equality or generalization.",
    }


def analyze(index):
    result = recompute(index)
    raw = json.loads(index.read_text())
    lookup = {(r["family_id"], r["policy"]): r for r in result["families"]}
    pairs = {}
    for baseline in ("native", "fixed", "strong", "repo-aware"):
        values = {key: [] for key in ("quality", "elapsed_seconds", "total_tokens")}
        for family, policy in lookup:
            if policy != "auto" or (family, baseline) not in lookup:
                continue
            h, b = lookup[(family, policy)], lookup[(family, baseline)]
            for key in values:
                if h.get(key) is not None and b.get(key) is not None:
                    values[key].append(h[key] - b[key])
        pairs[baseline] = {k: interval(v) for k, v in values.items()}
    auto = [r for r in raw["cells"] if r["policy"] == "auto"]
    gate = {
        "actions": dict(Counter(r["action"] for r in auto)),
        "cheap_branches": sum(r["action"] in ("N", "F") for r in auto),
        "cheap_zero_heavy": sum(
            r["action"] in ("N", "F")
            and all(
                r["calls"].get(k) == 0
                for k in ("heavy_constructors", "encoder_queries", "reranker_forwards")
            )
            for r in auto
        ),
    }
    return {
        **result,
        "paired_bootstrap": pairs,
        "gate": gate,
        "noninferiority_margin": 0.05,
        "utility": "INCONCLUSIVE",
        "interpretation_required": "Read paired intervals, intervention records and unknowns; a complete plan alone proves no utility conclusion.",
        "evidence_level": "PILOT",
        "deployment_recommendation": "KEEP_NATIVE",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = analyze(a.index)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
