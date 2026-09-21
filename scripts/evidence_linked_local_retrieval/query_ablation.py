"""Fixed full-index comparison of legacy summary queries and complete public ledger."""

import argparse
from dataclasses import asdict
from pathlib import Path
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.local_retrieval import retrieve
from hermes_skilleval.intervention.repair_composer import CompleteEncoder
from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.value import Encoder

p = argparse.ArgumentParser()
p.add_argument("--private", type=Path, required=True)
p.add_argument("--iteration", default="development-v4")
p.add_argument("--encoder", type=Path, required=True)
a = p.parse_args()
encoder = CompleteEncoder(Encoder(a.encoder))
legacy = read(
    "artifacts/evidence-linked-local-retrieval-v1/legacy-development-baseline.json"
)["states"]
for directory in sorted((a.private / a.iteration).iterdir()):
    if not (directory / "prepared.json").exists():
        continue
    if (directory / "legacy-query-pool.json").exists():
        continue
    prior = next(s for s in legacy if s["mechanism"] == directory.name)[
        "old_obligations"
    ]
    current = read(directory / "ledger.json")
    ledger = {
        "requirements": [
            {
                "requirement_id": o["id"],
                "expected_text": o["statement"],
                "verbatim_span": {
                    "field": "legacy_summary_diagnostic",
                    "start": 0,
                    "end": len(o["statement"]),
                },
                "status": o["status"],
                "subject": o["related_symbols"],
            }
            for o in prior
        ],
        "observations": [],
    }
    visible = "\n".join(o["output"] for o in current["observations"])
    observed = tuple(
        p
        for o in current["observations"]
        if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
        for p in o["paths"]
    )
    pool, diagnostic = retrieve(
        read(directory / "index.json"),
        ledger,
        encoder=encoder,
        visible_text=visible,
        read_symbols=observed,
    )
    dump(directory / "legacy-query-pool.json", asdict(pool))
    dump(
        directory / "legacy-query-retrieval.json",
        {
            "interpretation": "offline query-only diagnostic on same repaired full index and retriever; not historical execution replay",
            **diagnostic,
        },
    )
    print(directory.name, len(pool.candidates), flush=True)
