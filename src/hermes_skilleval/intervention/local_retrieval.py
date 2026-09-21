"""Global lexical seeds, real one-hop neighbors, complete views and common pool."""

from __future__ import annotations

from collections import Counter, defaultdict
import math

from .repair_composer import (
    Candidate,
    CandidatePool,
    Obligation,
    lexical,
    words,
)
from .local_source_index import materialize


class LexicalIndex:
    def __init__(self, nodes):
        self.nodes = nodes
        self.postings = defaultdict(dict)
        self.lengths = []
        for i, n in enumerate(nodes):
            counts = Counter(words(n["symbol"] + " " + n["path"] + " " + n["text"]))
            self.lengths.append(sum(counts.values()))
            for word, tf in counts.items():
                self.postings[word][i] = tf
        self.average = sum(self.lengths) / max(1, len(nodes)) or 1

    def search(self, query):
        scores = defaultdict(float)
        for word in set(words(query)):
            posting = self.postings.get(word, {})
            idf = math.log(
                1 + (len(self.nodes) - len(posting) + 0.5) / (len(posting) + 0.5)
            )
            for i, tf in posting.items():
                scores[i] += (
                    idf
                    * tf
                    * 2.2
                    / (tf + 1.2 * (0.25 + 0.75 * self.lengths[i] / self.average))
                )
        maximum = max(scores.values(), default=0) or 1
        return {i: v / maximum for i, v in scores.items()}


def retrieve(
    index,
    ledger,
    *,
    encoder,
    visible_text=None,
    read_symbols=(),
    expand=True,
    allowed_node_ids=None,
    seed_cap=8,
    rerank_cap=128,
    candidate_cap=24,
):
    """Only public ledger and exact-base index are accepted; no failure blob."""
    nodes = [
        n
        for n in index["nodes"]
        if allowed_node_ids is None or n["node_id"] in allowed_node_ids
    ]
    by_id = {n["node_id"]: i for i, n in enumerate(nodes)}
    lexical_index = LexicalIndex(nodes)
    requirements = ledger["requirements"]
    queries = []
    for r in requirements:
        query = r["expected_text"]
        # Environment evidence enters only with an explicit grounded link.
        relevant = [
            o["output"]
            for o in ledger["observations"]
            if o["lifecycle"] == "current"
            and any(
                link["requirement_id"] == r["requirement_id"]
                for link in o["requirement_links"]
            )
        ]
        queries.append(query + "\n" + "\n".join(relevant))
    per_requirement = []
    entries = defaultdict(list)
    for j, (r, q) in enumerate(zip(requirements, queries)):
        bm = lexical_index.search(q)
        symbols = r["subject"]

        def symbol_score(n):
            return float(
                any(s == n["symbol"] or n["symbol"].endswith("." + s) for s in symbols)
            )

        ranked = sorted(
            (
                i
                for i in bm
                if not (
                    nodes[i]["kind"] == "assignment"
                    and nodes[i]["parent"]
                    and nodes[i]["role"] != "documented_contract"
                )
            ),
            key=lambda i: (-symbol_score(nodes[i]), -bm[i], nodes[i]["node_id"]),
        )[:seed_cap]
        per_requirement.append(ranked)
        for i in ranked:
            entries[i].append(
                {
                    "requirement_id": r["requirement_id"],
                    "channel": "global_bm25_symbol",
                    "bm25": bm[i],
                    "symbol_match": symbol_score(nodes[i]),
                }
            )
    read_seeds = [
        i
        for i, n in enumerate(nodes)
        if n["symbol"] in read_symbols or n["path"] in read_symbols
    ]
    # Round-robin seeds first, so a verbose early requirement does not consume
    # the entire materialization budget before other conditions are considered.
    ordered = []
    for offset in range(seed_cap):
        for rows in per_requirement:
            if offset < len(rows) and rows[offset] not in ordered:
                ordered.append(rows[offset])
    for i in read_seeds:
        if i not in ordered:
            ordered.append(i)
        entries[i].append({"channel": "observed_symbol", "symbol": nodes[i]["symbol"]})
    seed_indices = list(ordered)
    edges = defaultdict(list)
    if expand:
        for e in index["edges"]:
            if e["source"] in by_id and e["target"] in by_id:
                edges[by_id[e["source"]]].append((by_id[e["target"]], e))
                edges[by_id[e["target"]]].append((by_id[e["source"]], e))
        for seed in seed_indices:
            for neighbor, e in sorted(
                edges[seed],
                key=lambda pair: (pair[1]["kind"], nodes[pair[0]]["node_id"]),
            )[:4]:
                entries[neighbor].append(
                    {"channel": "one_hop", "seed": nodes[seed]["node_id"], "edge": e}
                )
                if neighbor not in ordered:
                    ordered.append(neighbor)
    units = []
    kept = []
    unpackable = []
    for i in ordered:
        unit = materialize(index, nodes[i])
        if unit is None:
            unpackable.append(nodes[i]["node_id"])
            continue
        kept.append(i)
        units.append(unit)
        if len(units) == rerank_cap:
            break
    obligations = tuple(
        Obligation(
            r["requirement_id"],
            r["expected_text"],
            f"request:{r['verbatim_span']['start']}:{r['verbatim_span']['end']}",
            r["status"],
            tuple(r["subject"]),
        )
        for r in requirements
    )
    query = "\n".join(queries)
    if not units:
        return CandidatePool((), (), obligations, query), {
            "status": "NO_PACKABLE_LOCAL_CONTEXT",
            "unpackable": unpackable,
            "index_nodes": len(nodes),
        }
    vectors = [encoder.encode(u.statement) for u in units]
    qvectors = [encoder.encode(q) for q in queries]
    q = encoder.encode(query)
    bm = lexical_index.search(query)

    def cosine(a, b):
        return max(0.0, min(1.0, float(a @ b)))

    seen = (
        set(s.strip() for s in visible_text.splitlines())
        if visible_text is not None
        else None
    )
    rows = []
    for k, (i, u, v) in enumerate(zip(kept, units, vectors)):
        rel = (
            0.3 * bm.get(i, 0)
            + 0.6 * cosine(q, v)
            + 0.1 * lexical(query, " ".join(u.applies_to))
        )
        lines = [s.strip() for s in u.statement.splitlines() if s.strip()]
        exposure = (
            sum(s in seen for s in lines) / len(lines)
            if seen is not None and lines
            else None
        )
        coverage = tuple(
            0.7 * cosine(g, v) + 0.3 * lexical(r["expected_text"], u.statement)
            for r, g in zip(requirements, qvectors)
        )
        rows.append(
            Candidate(
                u,
                rel,
                coverage,
                exposure,
                {
                    "entries": entries[i],
                    "index_node": nodes[i]["node_id"],
                    "bm25": bm.get(i, 0),
                },
            )
        )
    selected = []
    # Give each public condition a first choice from its actual retrieval channel.
    for r in requirements:
        available = [
            i
            for i, c in enumerate(rows)
            if any(
                e.get("requirement_id") == r["requirement_id"]
                for e in c.retrieval["entries"]
            )
            and i not in selected
        ]
        if available:
            selected.append(
                min(available, key=lambda i: (-rows[i].relevance, rows[i].unit.unit_id))
            )
        if len(selected) == candidate_cap:
            break
    for i in sorted(
        range(len(rows)), key=lambda i: (-rows[i].relevance, rows[i].unit.unit_id)
    ):
        if len(selected) == candidate_cap:
            break
        if i not in selected:
            selected.append(i)
    overlap = tuple(
        tuple(
            0.7 * cosine(vectors[i], vectors[j])
            + 0.3 * lexical(units[i].statement, units[j].statement)
            for j in selected
        )
        for i in selected
    )
    covered = {
        e["requirement_id"]
        for i in selected
        for e in rows[i].retrieval["entries"]
        if "requirement_id" in e
    }
    report = {
        "status": "RETRIEVED",
        "index_nodes": len(nodes),
        "seed_nodes": len(seed_indices),
        "expanded_nodes": len(ordered) - len(seed_indices),
        "materialized_views": len(units),
        "unpackable": unpackable,
        "overflow_nodes": max(0, len(ordered) - len(units) - len(unpackable)),
        "uncovered_requirements": [
            r["requirement_id"]
            for r in requirements
            if r["requirement_id"] not in covered
        ],
        "expansion_enabled": expand,
    }
    return CandidatePool(
        tuple(rows[i] for i in selected), overlap, obligations, query
    ), report
