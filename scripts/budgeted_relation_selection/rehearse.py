"""One bounded development helper attempt; never invokes a repair agent."""

import argparse
from pathlib import Path

from hermes_skilleval.intervention.budgeted_relation_session import (
    BATCH_PROMPT,
    call_batch,
)
from hermes_skilleval.intervention.linked_context_study import load_pool, read
from hermes_skilleval.intervention.relation_store import RelationStore, atomic_json
from hermes_skilleval.intervention.repair_composer import select_mmr

p = argparse.ArgumentParser()
p.add_argument("--ledger", type=Path, required=True)
p.add_argument("--pool", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--resume", action="store_true")
a = p.parse_args()
ledger, pool = read(a.ledger), load_pool(a.pool)
a.output.mkdir(parents=True, exist_ok=True)
store = RelationStore(a.output / "store.json", ledger, pool, prompt=BATCH_PROMPT)
atomic_json(a.output / "mmr.json", select_mmr(pool).to_dict())
requested = store.pending()[:2]
prior = sorted(a.output.glob("batch-*"))
if prior and not a.resume:
    raise ValueError("Use --resume for pending-only continuation")
run = a.output / f"batch-{len(prior) + 1:04}"
if run.exists():
    raise ValueError("Rehearsal attempt already reserved; inspect saved output")
store.ingest(requested, {})
try:
    value = call_batch(ledger, pool, requested, run, seconds=20)
    store.ingest(requested, value)
finally:
    reloaded = RelationStore(store.path, ledger, pool, prompt=BATCH_PROMPT)
    atomic_json(
        a.output / "recovery-check.json",
        {
            "same_records_after_reload": reloaded.records == store.records,
            "requested": requested,
            "summary": reloaded.summary(),
            "research_repair_executions": 0,
        },
    )
print(store.summary()["counts"])
