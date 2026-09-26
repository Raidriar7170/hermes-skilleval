"""Metadata-only optional navigation using existing frozen complete MiniLM encoding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time


def query_text(task):
    return f"Repository: {task['repo']}\nLanguage: {task.get('language', 'Python')}\nProblem statement:\n{task['problem_statement']}"


def select_metadata(query, vectors, entries):
    def dot(a, b):
        return max(0.0, sum(x * y for x, y in zip(a, b, strict=True)))

    relevance = [dot(query, v) for v in vectors]
    selected, scores = [], []
    while len(selected) < min(3, len(entries)):

        def score(i):
            return 0.7 * relevance[i] - 0.3 * max(
                (dot(vectors[i], vectors[j]) for j in selected), default=0.0
            )

        candidates = [i for i in range(len(entries)) if i not in selected]
        best = min(candidates, key=lambda i: (-score(i), entries[i]["name"]))
        if score(best) <= 0:
            break
        scores.append(score(best))
        selected.append(best)
    return selected, scores


def render(entries):
    lines = ["Optional entries in the available experience catalog:"]
    for e in entries:
        lines.extend(
            [
                f"- Name: {e['name']}",
                f"  Description: {e['description']}",
                f"  Path: {e['path']}",
            ]
        )
    lines.append(
        "These entries are optional. Inspect and judge applicability yourself; you may ignore them or search any other entry in the full catalog."
    )
    return "\n".join(lines)


def encoder(path):
    from hermes_skilleval.intervention.value import Encoder
    from hermes_skilleval.intervention.repair_composer import CompleteEncoder

    return CompleteEncoder(Encoder(path))


def build_index(entries, model_path, output):
    started = time.monotonic()
    enc = encoder(model_path)
    texts = [e["name"] + "\n" + e["description"] for e in entries]
    vectors = [enc.encode(t).tolist() for t in texts]
    value = {
        "entries": entries,
        "vectors": vectors,
        "metadata_texts": texts,
        "encoding_records": enc.encoding_records,
        "offline_seconds": time.monotonic() - started,
    }
    Path(output).write_text(json.dumps(value, indent=2) + "\n")
    return value


def navigate(descriptor, task):
    # A new process and encoder per cell: no cross-cell query cache.
    started = time.monotonic()
    raw = Path(descriptor["index_path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != descriptor["index_sha256"]:
        raise ValueError("frozen metadata index changed")
    index = json.loads(raw)
    enc = encoder(descriptor["encoder_path"])
    query = query_text(task)
    vector = enc.encode(query).tolist()
    chosen, scores = select_metadata(vector, index["vectors"], index["entries"])
    entries = [index["entries"][i] for i in chosen]
    return {
        "method": "ASSIST_METADATA_MMR",
        "entries": entries,
        "block": render(entries),
        "scores_evidence_only": scores,
        "query_encoding": enc.encoding_records[query],
        "seconds": time.monotonic() - started,
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
    }
