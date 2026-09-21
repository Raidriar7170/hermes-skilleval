"""Compare frozen proposals/packs with a separately authored blinded unit review."""

import argparse
from collections import Counter
from pathlib import Path
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--root", type=Path, required=True)
p.add_argument("--review", type=Path, required=True)
p.add_argument("--mapping", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
review = read(a.review)
mapping = read(a.mapping)
output = []
for state in review["states"]:
    name = state["state"]
    units = {u["blind_id"]: u for u in state["units"]}
    aliases = state["requirement_aliases"]
    approved = {}
    for uid, u in units.items():
        for relation in [
            u,
            *([u["additional_relation"]] if "additional_relation" in u else []),
        ]:
            for alias in relation.get("requirements", []):
                approved.setdefault((aliases[alias], uid), set()).add(
                    relation["relation"]
                )
    relations = read(a.root / name / "relations.json")
    counts = Counter()
    pair_rows = []
    for row in relations:
        if row["weight"] <= 0:
            continue
        uid = mapping[name]["unit_mapping"][row["unit_id"]]
        labels = approved.get((row["requirement_id"], uid), set())
        verdict = (
            "SUPPORTED"
            if row["relation"] in labels
            else "OPPOSED"
            if units[uid]["relation"] == "TOPICAL_ONLY"
            else "UNKNOWN"
        )
        counts[verdict] += 1
        pair_rows.append(
            {
                "requirement_id": row["requirement_id"],
                "unit_id": row["unit_id"],
                "blind_id": uid,
                "proposed_relation": row["relation"],
                "independent_relations": sorted(labels),
                "verdict": verdict,
            }
        )
    packs = {}
    for method, pack in read(a.root / name / "packs.json").items():
        ids = [mapping[name]["unit_mapping"][u["unit_id"]] for u in pack["units"]]
        packs[method] = {
            "tokens": pack["tokens"],
            "units": ids,
            "topical_units": sum(units[u]["relation"] == "TOPICAL_ONLY" for u in ids),
            "unknown_units": sum(units[u]["relation"] == "UNKNOWN" for u in ids),
            "independently_supported_pairs": len(
                {key for key in approved if key[1] in ids}
            ),
            "requirements_with_some_supported_relationship": sorted(
                {r for r, u in approved if u in ids}
            ),
            "missing_prerequisites_or_partial_scope": [
                {"blind_id": u, "limitation": units[u]["missing_prerequisites"]}
                for u in ids
                if units[u].get("missing_prerequisites")
            ],
        }
    output.append(
        {
            "mechanism": name,
            "positive_proposal_counts": {
                k: counts[k] for k in ["SUPPORTED", "OPPOSED", "UNKNOWN"]
            },
            "positive_pairs": pair_rows,
            "packs": packs,
            "anchor_audit": state["anchor_audit"],
            "parsing_audit": state["parsing_audit"],
        }
    )
dump(
    a.output,
    {
        "review_type": review["review_type"],
        "human_reviewer_count": 0,
        "same_model_family_correlated_errors_possible": True,
        "scope": "finite source support, not functional correctness or complete repository recall",
        "unlisted_pairs": "UNKNOWN, retained in denominator",
        "relation_class_disagreement": "UNKNOWN unless reviewer explicitly calls entire unit topical",
        "states": output,
    },
)
print([{r["mechanism"]: r["positive_proposal_counts"]} for r in output])
