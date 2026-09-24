"""Public pair content priorities. Scores never enter the relation store or bounds."""

from __future__ import annotations

from collections import defaultdict
import random
import re

from .repair_composer import _bm25

GENERIC = {
    "error",
    "type",
    "default",
    "value",
    "key",
    "True",
    "False",
    "None",
    "str",
    "int",
    "list",
    "dict",
    "object",
}


def literals(text):
    # Preserve types and spelling: 0, False, None, [], {}, and '' remain distinct.
    pattern = r"\b(?:None|True|False)\b|(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])|\[\s*\]|\{\s*\}|\"[^\"\n]*\"|'[^'\n]*'|==|!=|<=|>=|(?<![<>=])[<>](?![=])"
    return set(re.findall(pattern, text))


def complete_requirement(row):
    text = row["expected_text"]
    condition = row.get("condition_text", "")
    return text if condition in text else text + "\n" + condition


def build_features(ledger, pool, encoder, nodes=()):
    """Resolve qualified names or unambiguous public short names; never basename match."""
    symbols = {n["symbol"] for n in nodes}
    paths = {n["path"] for n in nodes}
    short = defaultdict(set)
    for symbol in symbols:
        short[symbol.rsplit(".", 1)[-1]].add(symbol)
    documents = [c.unit.statement for c in pool.candidates]
    vectors = [encoder.encode(t) for t in documents] if encoder else None
    result = []
    for r in ledger["requirements"]:
        text = complete_requirement(r)
        bm = _bm25(text, documents)
        names = set(r.get("subject", [])) | set(re.findall(r"[A-Za-z_][\w./]*", text))
        resolved = (names & symbols) | {
            next(iter(short[n]))
            for n in names
            if n not in GENERIC and len(short[n]) == 1
        }
        resolved_paths = {p for p in paths if p in text and "/" in p}
        q = encoder.encode(text) if encoder else None
        rc = literals(text)
        for i, c in enumerate(pool.candidates):
            unit = c.unit
            matched = (set(unit.applies_to) & resolved) | (
                {s.path_or_public_url for s in unit.source_spans} & resolved_paths
            )
            uc = literals(unit.statement)
            common = rc & uc
            values = {
                "semantic": max(0.0, min(1.0, float(q @ vectors[i])))
                if encoder
                else 0.0,
                "lexical": bm[i],
                "symbol": float(bool(matched)),
                "condition": len(common) / max(1, len(rc | uc)),
            }
            result.append(
                {
                    "pair_id": [r["requirement_id"], unit.unit_id],
                    "requirement_text": text,
                    "unit_text": unit.statement,
                    "source_role": unit.claim_role,
                    "symbols_and_paths": sorted(matched),
                    "resolved_requirement_symbols": sorted(resolved | resolved_paths),
                    "condition_literals": {
                        "requirement": sorted(rc),
                        "unit": sorted(uc),
                        "shared": sorted(common),
                    },
                    "feature_values": values,
                    "feature_missing": ([] if encoder else ["semantic"])
                    + (
                        []
                        if resolved or resolved_paths
                        else ["resolved_requirement_symbol"]
                    ),
                    "z": 0.5 * values["semantic"]
                    + 0.2 * values["lexical"]
                    + 0.2 * values["symbol"]
                    + 0.1 * values["condition"],
                }
            )
    return result


def requests(
    selector,
    store,
    result,
    features,
    *,
    method,
    size=8,
    costs=None,
    offset=0,
    domain=None,
    excluded=(),
):
    if method not in {"S", "A0", "R", "V", "V-no-cost"}:
        raise ValueError("Unknown query method")
    pending = [
        p
        for p in store.pending()
        if (domain is None or p in domain) and p not in excluded
    ]
    if method == "S":
        return sorted(pending)[:size]
    costs = costs or {}
    scores = {tuple(f["pair_id"]): f["z"] for f in features}
    selected = [
        set(selector.mmr.indices),
        set(result["lower_indices"]),
        set(result["upper_indices"]),
    ]
    index = {c.unit.unit_id: i for i, c in enumerate(selector.pool.candidates)}
    weights = selector.ledger["weights"]
    counts = {
        r: sum(
            store.records[p]["state"] != "NOT_ANALYZED"
            for p in store.pairs
            if p[0] == r
        )
        for r in weights
    }

    def priority(p):
        z = scores[p]
        if method == "R":
            return weights[p[0]] * z
        low, high = store.bounds(p)
        cost = 1.0 if method == "V-no-cost" else max(1e-9, costs.get(p, 1.0))
        base = (
            weights[p[0]]
            * (high - low)
            * (1 + sum(index[p[1]] in s for s in selected))
            / cost
        )
        return base if method == "A0" else base * (0.05 + 0.95 * z)

    batch = []
    while pending and len(batch) < size:
        eligible = pending
        if (offset + len(batch) + 1) % 3 == 0:
            rid = min(
                {p[0] for p in pending}, key=lambda r: (counts[r], -weights[r], r)
            )
            eligible = [p for p in pending if p[0] == rid]
        chosen = min(eligible, key=lambda p: (-priority(p), p))
        batch.append(chosen)
        pending.remove(chosen)
        counts[chosen[0]] += 1
    return batch


def panel(features, *, seed=20260923, cap=48):
    """Three fixed strata; shortages filled uniformly from remaining full domain."""
    rng = random.Random(seed)
    by_req = defaultdict(list)
    for f in features:
        by_req[f["pair_id"][0]].append(f)
    related = []
    ordered = {
        r: sorted(fs, key=lambda f: (-f["z"], f["pair_id"])) for r, fs in by_req.items()
    }
    for i in range(max(map(len, ordered.values()), default=0)):
        for r in sorted(ordered):
            if i < len(ordered[r]):
                related.append(ordered[r][i])
    chosen = []
    used = set()
    for label, options in [
        ("relevant", related),
        (
            "near_distractor",
            sorted(
                (
                    f
                    for f in features
                    if not f["symbols_and_paths"] and f["feature_values"]["lexical"] > 0
                ),
                key=lambda f: (-f["feature_values"]["lexical"], f["pair_id"]),
            ),
        ),
        (
            "distribution_control",
            rng.sample(sorted(features, key=lambda f: f["pair_id"]), len(features)),
        ),
    ]:
        rows = [f for f in options if tuple(f["pair_id"]) not in used][
            : min(16, cap - len(chosen))
        ]
        if len(rows) < min(16, cap - len(chosen)):
            available = [
                f for f in features if tuple(f["pair_id"]) not in used and f not in rows
            ]
            rows += rng.sample(
                available, min(len(available), min(16, cap - len(chosen)) - len(rows))
            )
        for f in rows:
            chosen.append({"pair": f["pair_id"], "stratum": label})
            used.add(tuple(f["pair_id"]))
    return chosen
