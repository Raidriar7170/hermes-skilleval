"""Opt-in sparse source proposals; absence is never a negative semantic label."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile

from .source_relation import (
    PROMPT,
    WEIGHTS,
    expand_compact_relations,
    identity,
    validate_relations,
)

SCHEMA = "sparse-source-relations-v1"
RETRYABLE = {"NOT_ANALYZED", "TRANSPORT_MISSING", "FORMAT_INVALID"}
TERMINAL = {"VALID_POSITIVE", "VALID_ZERO", "SEMANTIC_UNRESOLVED", "REJECTED_PROPOSAL"}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def input_identity(ledger, pool, *, model, effort, prompt):
    return identity(
        {
            "schema": SCHEMA,
            "ledger": ledger,
            "units": [c.unit.to_dict() for c in pool.candidates],
            "model": model,
            "effort": effort,
            "prompt": prompt,
            "weights": WEIGHTS,
        }
    )


def validate_row(row, ledger, pool):
    """Reuse strict provenance checks on one pair, isolating malformed neighbors."""
    required = {
        "requirement_id",
        "unit_id",
        "relation",
        "requirement_quote",
        "unit_quote",
        "applicable",
        "condition_basis",
        "rationale",
    }
    if not isinstance(row, dict) or not required <= row.keys():
        raise ValueError("Missing row fields")
    if any(not isinstance(row[k], str) for k in required - {"applicable"}):
        raise ValueError("Non-string row field")
    if row["applicable"] is not None and type(row["applicable"]) is not bool:
        raise ValueError("Invalid applicability type")
    reqs = [
        r
        for r in ledger["requirements"]
        if r["requirement_id"] == row["requirement_id"]
    ]
    candidates = tuple(c for c in pool.candidates if c.unit.unit_id == row["unit_id"])
    if len(reqs) != 1 or len(candidates) != 1:
        raise ValueError("Unknown input ID")
    result = validate_relations(
        {**ledger, "requirements": reqs}, replace(pool, candidates=candidates), [row]
    )[0]
    if result["validation_status"] != "VALID_PROPOSAL":
        state = "REJECTED_PROPOSAL"
    elif result["relation"] == "UNRESOLVED" or (
        result["relation"] != "TOPICAL_ONLY" and result["applicable"] is None
    ):
        state = "SEMANTIC_UNRESOLVED"
    elif result["weight"] > 0:
        state = "VALID_POSITIVE"
    else:
        state = "VALID_ZERO"
    return {**result, "state": state}


class RelationStore:
    def __init__(
        self, path, ledger, pool, *, model="gpt-5.6-sol", effort="medium", prompt=PROMPT
    ):
        self.path, self.ledger, self.pool = Path(path), ledger, pool
        self.digest = input_identity(
            ledger, pool, model=model, effort=effort, prompt=prompt
        )
        self.pairs = [
            (r["requirement_id"], c.unit.unit_id)
            for r in ledger["requirements"]
            for c in pool.candidates
        ]
        if len(set(self.pairs)) != len(self.pairs):
            raise ValueError("Duplicate input IDs")
        self.records = {p: {"state": "NOT_ANALYZED"} for p in self.pairs}
        self.events = []
        if self.path.exists():
            saved = json.loads(self.path.read_text())
            if saved["input_identity"] != self.digest:
                raise ValueError("Changed relation input identity")
            if [tuple(r["pair"]) for r in saved["records"]] != self.pairs:
                raise ValueError("Changed stored relation domain")
            self.records = {tuple(r["pair"]): r["record"] for r in saved["records"]}
            self.events = saved["events"]
        self.save()

    def save(self):
        atomic_json(
            self.path,
            {
                "schema": SCHEMA,
                "input_identity": self.digest,
                "records": [{"pair": p, "record": self.records[p]} for p in self.pairs],
                "events": self.events,
            },
        )

    def pending(self):
        return [p for p in self.pairs if self.records[p]["state"] in RETRYABLE]

    def ingest(self, requested, value, *, late=False):
        requested = [tuple(p) for p in requested]
        if (
            len(set(requested)) != len(requested)
            or not set(requested) <= self.records.keys()
        ):
            raise ValueError("Invalid requested pairs")
        if late:
            self.events.append({"late": True, "requested": requested, "raw": value})
            self.save()
            return
        for pair in requested:
            if self.records[pair]["state"] in RETRYABLE:
                self.records[pair] = {"state": "TRANSPORT_MISSING"}
        rows = (
            value.get("relations", value.get("rows", []))
            if isinstance(value, dict)
            else []
        )
        if not isinstance(rows, list):
            rows = []
        for raw in rows:
            pair = None
            try:
                if isinstance(raw, dict):
                    pair = (raw.get("requirement_id"), raw.get("unit_id"))
                    row = raw
                else:
                    pair = tuple(raw[:2]) if isinstance(raw, list) else None
                    row = expand_compact_relations(
                        {"rows": [raw]}, self.ledger, self.pool
                    )[0]
                if (
                    not isinstance(pair, tuple)
                    or len(pair) != 2
                    or not all(isinstance(x, str) for x in pair)
                ):
                    pair = None
                    raise ValueError("Malformed pair IDs")
                if pair not in requested:
                    raise ValueError("Unrequested pair")
                result = validate_row(row, self.ledger, self.pool)
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                self.events.append({"raw": raw, "error": str(exc)})
                if pair in requested and self.records[pair]["state"] not in TERMINAL:
                    self.records[pair] = {"state": "FORMAT_INVALID", "raw": raw}
            else:
                if self.records[pair]["state"] in TERMINAL:
                    self.events.append(
                        {
                            "pair": pair,
                            "duplicate": result,
                            "conflict": result != self.records[pair],
                        }
                    )
                else:
                    self.records[pair] = result
            self.save()
        self.save()

    def bounds(self, pair):
        row = self.records[tuple(pair)]
        if row["state"] == "VALID_POSITIVE":
            return row["weight"], row["weight"]
        if row["state"] == "VALID_ZERO":
            return 0.0, 0.0
        return 0.0, 1.0

    def summary(self):
        return {
            "counts": dict(Counter(r["state"] for r in self.records.values())),
            "missing": [
                p
                for p in self.pairs
                if self.records[p]["state"] not in {"VALID_POSITIVE", "VALID_ZERO"}
            ],
            "pending": self.pending(),
            "total_pairs": len(self.pairs),
        }
