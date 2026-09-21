"""Old public checkpoint diagnostics only; never replays repairs or reads outcomes."""

from dataclasses import asdict
import argparse
from pathlib import Path
import time

from hermes_skilleval.intervention.evidence_linked_state import analyze
from hermes_skilleval.intervention.local_retrieval import retrieve
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.repair_composer import CompleteEncoder
from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.value import Encoder

p = argparse.ArgumentParser()
p.add_argument("--legacy-private", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--encoder", type=Path, required=True)
p.add_argument("--mechanism")
a = p.parse_args()
lock = read(a.legacy_private / "study-v1/pilot-lock.json")
plan = read(Path("configs/repair-knowledge-composition-v1/plan.json"))
encoder = CompleteEncoder(Encoder(a.encoder))
for s in lock["states"]:
    if a.mechanism and s["mechanism"] != a.mechanism:
        continue
    row = next(r for r in plan["tasks"] if r["instance_id"] == s["task_id"])
    cp = read(Path(s["checkpoint"]) / "checkpoint.json")
    ledger = analyze(
        cp["state"]["request"],
        cp["visible_events"],
        checkpoint_event_count=len(cp["visible_events"]),
    )
    dump(a.output / (s["mechanism"] + "-state.json"), ledger)
    index = read(a.output / "index" / (row["base_commit"] + ".json"))
    visible = "\n".join(o["output"] for o in ledger["observations"])
    symbols = tuple(
        p
        for o in ledger["observations"]
        if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
        for p in o["paths"]
    )
    start = time.monotonic()
    pool, diagnostic = retrieve(
        index, ledger, encoder=encoder, visible_text=visible, read_symbols=symbols
    )
    diagnostic["seconds"] = time.monotonic() - start
    dump(a.output / (s["mechanism"] + "-pool.json"), asdict(pool))
    dump(a.output / (s["mechanism"] + "-retrieval.json"), diagnostic)
    print(
        {
            "mechanism": s["mechanism"],
            "candidate_count": len(pool.candidates),
            "seconds": diagnostic["seconds"],
            "sources": [c.unit.applies_to for c in pool.candidates],
        },
        flush=True,
    )
