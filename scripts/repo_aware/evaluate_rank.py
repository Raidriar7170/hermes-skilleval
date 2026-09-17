"""Frozen same-backbone/candidate development ablations on labelled support only."""

import argparse
import json
import time
from pathlib import Path

from hermes_skilleval.repo_routing.context import extract
from hermes_skilleval.repo_routing.support import score_candidates
from hermes_skilleval.repo_routing.reranker import Reranker, representation
from hermes_skilleval.repo_routing.selector import Budget, select
from hermes_skilleval.routers.skillrouter_open import OpenProfile, SkillRouterOpen
from hermes_skilleval.vendor import skillrouter_common as ref

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, required=True)
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--registry", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
c = json.loads(a.config.read_text())
registry = json.loads(a.registry.read_text())
# Offline developer annotations from public request/skill text; unrelated candidates UNKNOWN.
labels = {
    "csvkit-empty-stack": ["import-data-regression", "cli-api-regression"],
    "csvkit-sql-length-defaults": [
        "schema-change-regression",
        "import-data-regression",
    ],
}
router = SkillRouterOpen(
    Path(c["encoder_path"]),
    Path(c["reranker_path"]),
    encoder_revision=c["encoder_revision"],
    reranker_revision=c["reranker_revision"],
    profile=OpenProfile(**c["profile"]),
)
router.index(registry["skills"])
cases = []
for task_id, positive in labels.items():
    root = a.tasks / task_id
    meta = json.loads((root / "task.json").read_text())
    if meta["split"] != "rank-dev":
        raise ValueError("rank-dev only")
    request = (root / "public.md").read_text()
    context = extract(
        root / "base",
        request,
        {"network": "disabled", "python": "observed isolated Python executor"},
    )
    vectors = router.encode([ref.format_query(request, router.profile.query_chars)])
    sims = (vectors @ router.vectors.T)[0].tolist()
    indices = sorted(
        range(len(sims)), key=lambda i: (-sims[i], registry["skills"][i]["id"])
    )[: router.profile.retrieval_top_k]
    cases.append(
        (task_id, request, context, [registry["skills"][i] for i in indices], positive)
    )
router.model = None
results = []
for trained in (False, True):
    model = Reranker(
        c["reranker_path"],
        device=c["profile"]["device"],
        max_length=c["max_length"],
        adapter=c["adapter"] if trained else None,
    )
    for task_id, request, context, candidates, positive in cases:
        for use_context in (False, True):
            start = time.monotonic()
            scores = []
            records = []
            for skill in candidates:
                v, r = model.scores(
                    [representation(request, context, skill, use_context=use_context)]
                )
                scores.append(float(v.detach().cpu()[0]))
                records.extend(r)
            ranked = [
                s["id"]
                for s, v in sorted(
                    zip(candidates, scores), key=lambda v: (-v[1], v[0]["id"])
                )
            ]
            clauses, items = score_candidates(
                request,
                context,
                candidates,
                scores,
                model,
                {"network": "disabled"},
                c.get("support_threshold", 0.8),
            )
            weights = [1.0 / len(clauses)] * len(clauses)
            variants = {
                "top2": ranked[:2],
                "dedup_top2": ranked[:2],
                "complementary_top2": select(items, weights, Budget(), exact_k=2)[
                    "skill_ids"
                ],
                "budget": select(items, weights, Budget())["skill_ids"],
            }
            results.append(
                {
                    "task_id": task_id,
                    "trained": trained,
                    "context": use_context,
                    "ranked": ranked,
                    "positive": positive,
                    "unknown_ids": [
                        s["id"] for s in candidates if s["id"] not in positive
                    ],
                    "label_source": "model_judged_text",
                    "recall_at_2": len(set(ranked[:2]) & set(positive)) / len(positive),
                    "mrr": 1
                    / min(ranked.index(s) + 1 for s in positive if s in ranked),
                    "scores": dict(zip([s["id"] for s in candidates], scores)),
                    "variants": variants,
                    "inputs": records,
                    "seconds": time.monotonic() - start,
                }
            )
    del model
    import gc

    gc.collect()
with a.output.open("x") as stream:
    json.dump(
        {
            "evidence_level": "PILOT",
            "families": 2,
            "rows": results,
            "dedup_note": "No byte-identical packages; simple dedup equals Top2.",
            "utility": "NOT_MEASURED",
        },
        stream,
        indent=2,
    )
print(
    json.dumps(
        [
            {
                "trained": r["trained"],
                "context": r["context"],
                "recall_at_2": r["recall_at_2"],
            }
            for r in results
        ]
    )
)
