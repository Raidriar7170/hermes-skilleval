"""Pure functional feature tables. Retrieval is never repeated for an ablation."""

from collections import defaultdict
import hashlib

from .functional_pairs import paired_records
from .state import State


def feature_tables(records, encoder, *, split, no_state=False):
    source = [r for r in records if r["split"] == split]
    pairs = paired_records(source)
    grouped = defaultdict(list)
    missing = []
    for row in pairs:
        if row["action"] == "GENERIC_REMINDER":
            continue  # reminder is an external control, not a deployable skill
        if row["delta_functional"] is None:
            missing.append((row["state_id"], row["action"], row["repeat"]))
            continue
        grouped[row["task_id"], row["state_id"], row["action"]].append(row)
    rows, chains = [], {}
    for group in grouped.values():
        row = group[0]
        payloads = {p["id"]: p["payload"] for p in row["candidate_payloads"]}
        if row["action"] not in payloads:
            raise ValueError("observed skill absent from common candidates")
        rows.append(
            {
                "task_id": row["task_id"],
                "family": row["family"],
                "state_id": row["state_id"],
                "stage": row["stage"],
                "action": row["action"],
                "x": encoder.features(State(**row["state"]), no_state=no_state),
                "k": encoder.encode(payloads[row["action"]]),
                "delta": sum(r["delta_functional"] for r in group) / len(group),
                "paired_repeats": len(group),
                "raw_deltas": [r["delta_functional"] for r in group],
                "baseline_samples": [r["baseline_sample"] for r in group],
            }
        )
    for row in source:
        tid = row["task_id"]
        chain = chains.setdefault(tid, {})
        if row["state_id"] in chain:
            if chain[row["state_id"]]["binding_sha256"] != row["binding_sha256"]:
                raise ValueError("state binding changed across repeats")
            continue
        payloads = row["candidate_payloads"]
        if [p["id"] for p in payloads] != row["candidates"]:
            raise ValueError("candidate payload order differs from common list")
        for payload in payloads:
            if (
                hashlib.sha256(payload["payload"].encode()).hexdigest()
                != payload["payload_sha256"]
            ):
                raise ValueError("actual candidate payload changed")
        chain[row["state_id"]] = {
            "task_id": tid,
            "family": row["family"],
            "state_id": row["state_id"],
            "binding_sha256": row["binding_sha256"],
            "stage": row["stage"],
            "x": encoder.features(State(**row["state"]), no_state=no_state),
            "candidate_ids": list(row["candidates"]),
            "candidates": [encoder.encode(p["payload"]) for p in payloads],
            "terminal_confirmed": row["stage"] == "E2",
        }
    ordered = {
        tid: sorted(chain.values(), key=lambda s: s["stage"])
        for tid, chain in chains.items()
    }
    for tid, chain in ordered.items():
        statuses = {r["native_terminal_status"] for r in source if r["task_id"] == tid}
        if len(statuses) != 1:
            raise ValueError("native chain status disagreement")
        # An interrupted/missing future remains unknown; E2 is the last permitted
        # opportunity by design, and clean completion confirms no next event.
        chain[-1]["terminal_confirmed"] |= statuses == {"COMPLETED"}
    return rows, ordered, missing


def task_weighted_prior(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["action"], row["stage"], row["task_id"]].append(row["delta"])
    by_action_stage = defaultdict(list)
    for (action, stage, _task), values in grouped.items():
        by_action_stage[action, stage].append(sum(values) / len(values))
    return {a + "@" + s: sum(v) / len(v) for (a, s), v in by_action_stage.items()}


def prior_predict(prior, action, stage):
    # Fixed before dev comparison: unseen skill/stage combinations imply zero.
    return prior.get(action + "@" + stage, 0.0)
