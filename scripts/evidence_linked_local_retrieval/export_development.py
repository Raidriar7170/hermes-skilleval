"""Compact public development exports, excluding full indexes and private sessions."""

import argparse
import hashlib
from pathlib import Path
from collections import Counter
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--root", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
summary = []
for directory in sorted(a.root.iterdir()):
    if not (directory / "prepared.json").exists():
        continue
    target = a.output / directory.name
    ledger = read(directory / "ledger.json")
    original_observations = ledger["observations"]
    ledger["observations"] = [
        {
            **{k: v for k, v in o.items() if k not in {"output"}},
            "output_sha256": hashlib.sha256(o["output"].encode()).hexdigest(),
            "output_excerpt": o["output"][:240]
            if o["kind"] in {"ENV_TOOL_FAILURE", "FUNCTIONAL_ASSERTION"}
            else None,
        }
        for o in original_observations
    ]
    dump(target / "ledger.json", ledger)
    index = read(directory / "index.json")
    coverage = {
        **index["coverage"],
        "exclusion_counts": dict(Counter(index["excluded"].values())),
        "parser_counts": dict(Counter(index["parsing"].values())),
        "index_sha256": hashlib.sha256(
            (directory / "index.json").read_bytes()
        ).hexdigest(),
    }
    dump(target / "index-coverage.json", coverage)
    pools = {}
    for variant in ["full", "old40", "no-expansion", "legacy-query"]:
        pools[variant] = read(directory / (variant + "-pool.json"))
        dump(target / (variant + "-pool.json"), pools[variant])
        dump(
            target / (variant + "-retrieval.json"),
            read(directory / (variant + "-retrieval.json")),
        )
    for name in ["packs.json", "relations.json", "relation-reuse.json"]:
        if (directory / name).exists():
            dump(target / name, read(directory / name))
    ids = {
        variant: {c["unit"]["unit_id"] for c in pool["candidates"]}
        for variant, pool in pools.items()
    }
    relations = (
        read(directory / "relations.json")
        if (directory / "relations.json").exists()
        else []
    )
    summary.append(
        {
            "mechanism": directory.name,
            "requirement_count": len(ledger["requirements"]),
            "environment_observation_count": sum(
                o["kind"] == "ENV_TOOL_FAILURE" for o in original_observations
            ),
            "environment_functional_weight": ledger["environment_functional_weight"],
            "observation_lifecycles": dict(
                Counter(o["lifecycle"] for o in original_observations)
            ),
            "coverage": coverage,
            "candidate_counts": {v: len(x) for v, x in ids.items()},
            "same_full_pool_unit_id_overlap": {
                v: len(ids["full"] & x) for v, x in ids.items()
            },
            "relation_proposals": len(relations),
            "positive_proposals": sum(r["weight"] > 0 for r in relations),
            "rejected_proposals": sum(
                r["validation_status"] == "REJECTED_ZERO_COVERAGE" for r in relations
            ),
            "semantic_truth": "independent review reported separately",
            "research_executions": 0,
        }
    )
dump(
    a.output / "summary.json",
    {
        "development_version": a.root.name,
        "states": summary,
        "legacy_results": "PRESERVED",
        "interpretation": "observed old development only; no new repair executions, no functional gain inferred",
    },
)
print(summary)
