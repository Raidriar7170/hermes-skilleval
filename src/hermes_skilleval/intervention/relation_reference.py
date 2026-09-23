"""Post-lock dense completion and hidden-table query-order diagnostics."""

from pathlib import Path
import tempfile

from .anytime_acquisition import acquire
from .anytime_relation_selector import ExactSelector
from .budgeted_relation_session import BATCH_PROMPT
from .linked_composition import objective
from .linked_context_study import read
from .relation_store import RelationStore, atomic_json
from .repair_knowledge import token_count


def complete_reference(
    ledger, pool, source, output, *, seconds=300, batch_size=2, helper=None
):
    source, output = Path(source), Path(output)
    if not (source / "selection.json").exists():
        raise ValueError("A selection must be locked before dense completion")
    seed = read(source / "relations.json")
    kwargs = {"helper": helper} if helper is not None else {}
    result = acquire(
        ledger,
        pool,
        output,
        seconds=seconds,
        pair_cap=len(ledger["requirements"]) * len(pool.candidates),
        strategy="D",
        batch_size=batch_size,
        seed_store=seed,
        **kwargs,
    )
    missing = sum(
        result["relations"]["counts"].get(s, 0)
        for s in ("NOT_ANALYZED", "TRANSPORT_MISSING", "FORMAT_INVALID")
    )
    result["reference_status"] = "PARTIAL" if missing else "COMPLETE_TRANSPORT"
    result["semantic_unknown"] = sum(
        result["relations"]["counts"].get(s, 0)
        for s in ("SEMANTIC_UNRESOLVED", "REJECTED_PROPOSAL")
    )
    result["reference_scope"] = "same_model_matrix_posthoc_completion_not_oracle"
    atomic_json(output / "reference.json", result)
    return result


def replay_table(
    ledger,
    pool,
    table_path,
    *,
    points=(8, 16, 32, 48),
    batch_size=2,
    count_tokens=token_count,
):
    """No external requests, repair execution or trusted acceptance; unknown stays unknown."""
    raw = read(table_path)
    with tempfile.TemporaryDirectory(prefix="hermes-relation-replay-") as tmp:
        root = Path(tmp)
        reference = RelationStore(
            root / "reference.json", ledger, pool, prompt=BATCH_PROMPT
        )
        if raw["input_identity"] != reference.digest:
            raise ValueError("Reference input differs")
        reference.records = {tuple(r["pair"]): r["record"] for r in raw["records"]}
        if set(reference.records) != set(reference.pairs):
            raise ValueError("Reference domain differs")
        solver = ExactSelector(pool, ledger, count_tokens=count_tokens)
        dense_pack, dense = solver.solve(reference)
        lower = [
            [reference.bounds((o.id, c.unit.unit_id))[0] for o in pool.obligations]
            for c in pool.candidates
        ]
        upper = [
            [reference.bounds((o.id, c.unit.unit_id))[1] for o in pool.obligations]
            for c in pool.candidates
        ]
        rows = []
        for strategy in ("A", "S"):
            store = RelationStore(
                root / (strategy + ".json"), ledger, pool, prompt=BATCH_PROMPT
            )
            seen = set()
            pack, state = solver.solve(store)
            for point in points:
                while len(seen) < min(point, len(store.pairs)):
                    requested = solver.requests(
                        store,
                        state,
                        size=min(batch_size, point - len(seen)),
                        strategy=strategy,
                        offset=len(seen),
                        excluded=seen,
                    )
                    if not requested:
                        break
                    # The scheduler sees only previously revealed rows, never the reference object.
                    for pair in requested:
                        store.records[pair] = dict(reference.records[pair])
                    seen.update(requested)
                    pack, state = solver.solve(store)
                rows.append(
                    {
                        "strategy": strategy,
                        "progress_point": point,
                        "requested": len(seen),
                        "package_ids": [u.unit_id for u in pack.units],
                        "state": state,
                        "relations": store.summary(),
                        "same_pack_as_reference": pack.units == dense_pack.units,
                        "reference_objective_lower": objective(
                            pool, pack.indices, ledger["weights"], lower
                        )["total"],
                        "reference_objective_upper": objective(
                            pool, pack.indices, ledger["weights"], upper
                        )["total"],
                    }
                )
        return {
            "mode": "OFFLINE_HIDDEN_TABLE_REPLAY",
            "batch_size": batch_size,
            "model_calls": 0,
            "repair_executions": 0,
            "latency_claim": "NONE",
            "reference": dense,
            "reference_coverage": reference.summary(),
            "rows": rows,
        }
