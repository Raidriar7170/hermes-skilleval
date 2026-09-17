"""Build model-judged textual preferences from public rank families only."""

import argparse
import hashlib
import json
from pathlib import Path

from hermes_skilleval.repo_routing.context import extract
from hermes_skilleval.repo_routing.reranker import representation

# Annotation declarations are offline labels, never a runtime task lookup.
# They rank textual support, not skill necessity or execution causality.
ANNOTATIONS = {
    "offset-without-limit": (
        "cli-api-regression",
        "import-data-regression",
        "API query boundaries are explicit; data ingestion is not requested.",
    ),
    "numeric-empty-transform": (
        "import-data-regression",
        "cli-api-regression",
        "Explicit empty string/null/type conversion support exceeds generic CLI checks.",
    ),
    "escaped-default": (
        "schema-change-regression",
        "import-data-regression",
        "Schema default introspection is explicit; ingestion is outside this request.",
    ),
    "keyword-default": (
        "schema-change-regression",
        "import-data-regression",
        "Schema default introspection needs SQL/Python type correspondence.",
    ),
    "ignore-last-pk": (
        "schema-change-regression",
        "cli-api-regression",
        "Stored primary key and cross-table state require data/schema verification.",
    ),
    "column-case": (
        "schema-change-regression",
        "cli-api-regression",
        "Schema column identity and stored keys are more specific than generic interface checks.",
    ),
    "duplicate-result-columns": (
        "cli-api-regression",
        "import-data-regression",
        "API return values and preserved output are explicit; import batching is not.",
    ),
    "list-last-pk": (
        "import-data-regression",
        "cli-api-regression",
        "Input shape, row contents and batching boundaries match the requested insert interface.",
    ),
}
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--registry", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
skills = {s["id"]: s for s in json.loads(a.registry.read_text())["skills"]}
rows = []
for family, (pos, neg, reason) in ANNOTATIONS.items():
    task = a.tasks / ("sqlite-utils-" + family)
    request = (task / "public.md").read_text()
    meta = json.loads((task / "task.json").read_text())
    if meta["split"] != "rank-train":
        raise ValueError("annotation family outside rank-train")
    context = extract(
        task / "base",
        request,
        {"network": "disabled", "python": "observed isolated Python executor"},
    )
    rows.append(
        {
            "task_key": meta["task_id"],
            "repair_family": family,
            "repository": meta["repository"],
            "split": "rank-train",
            "base_snapshot": context["snapshot_id"],
            "public_request_hash": hashlib.sha256(request.encode()).hexdigest(),
            "context_hash": context["cache_key"],
            "positive_or_preferred": pos,
            "negative_or_less_preferred": neg,
            "label_source": "model_judged_text",
            "weight": 0.5,
            "evidence_refs": [
                {"source": "public_request", "text": request},
                {"source": pos, "text": skills[pos]["body"]},
                {"source": neg, "text": skills[neg]["body"]},
            ],
            "rationale": reason,
            "execution_comparison_ids": [],
            "uncontrolled_factors": [
                "subjective textual preference; no causal utility label"
            ],
            "positive_text": representation(request, context, skills[pos]),
            "negative_text": representation(request, context, skills[neg]),
        }
    )
with a.output.open("x") as stream:
    for row in rows:
        stream.write(json.dumps(row) + "\n")
print(
    json.dumps(
        {
            "families": len(rows),
            "label_source": "model_judged_text",
            "execution_preference_signal": "INSUFFICIENT",
        }
    )
)
