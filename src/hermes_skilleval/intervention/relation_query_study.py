"""Bounded source-only research. No repair, acceptance or training execution imports."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

from .anytime_relation_selector import ExactSelector
from .budgeted_relation_session import BATCH_PROMPT, batch_payload
from .linked_context_study import load_pool, read
from .pair_applicability import build_features, panel, requests, literals
from .relation_batch_planner import CostEnvelope, RelationTransport
from .relation_store import RelationStore, TERMINAL, atomic_json
from .repair_composer import CompleteEncoder
from .source_relation import identity
from .value import Encoder

STUDY = "relation-applicability-query-v1"
SEED = 20260923
DEV = ["empty-keyed-group-naming", "mapping-subtype-combination"]
CHECK = ["documentation-macro-boundaries", "variable-file-cache"]
QUERY_PROMPT = BATCH_PROMPT
AUDIT_PROMPT = (
    QUERY_PROMPT
    + "\nIndependently assess the supplied public originals. You have no prior proposal to approve. Distinguish normative support, verification, prerequisites and implementation context. Shared helper names do not prove reachability. Retain uncertainty. Do not solve the repair."
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(root, name):
    d = root / "inputs" / name
    return (
        read(d / "ledger.json"),
        load_pool(d / "pool.json"),
        read(d / "features.json"),
        read(d / "panel.json"),
    )


def prepare(args):
    root = args.output
    if (root / "inputs.json").exists():
        raise ValueError("Inputs already frozen")
    prior = read(args.repo / "configs/budgeted-relation-selection-v1/plan.json")
    for name, expected in prior["representation"]["files"].items():
        if sha(args.encoder / name) != expected:
            raise ValueError("Frozen encoder mismatch: " + name)
    encoder = CompleteEncoder(Encoder(args.encoder))
    manifest = []
    for name in DEV + CHECK:
        if name in DEV:
            origin = args.assets / "hermes-evidence-linked-private"
            ledgerpath = origin / "development-v5" / name / "ledger.json"
            poolpath = origin / "fulltext-index-repair-v1" / name / "pool.json"
            indexpath = poolpath.parent / "index.json"
        else:
            t = next(t for t in prior["tasks"] if t["mechanism"] == name)
            origin = args.assets / "hermes-budgeted-relation-private/study-v1"
            ledgerpath = origin / "selection" / t["instance_id"] / "ledger.json"
            poolpath = ledgerpath.parent / "pool.json"
            indexpath = origin / "public-knowledge" / t["base_commit"] / "index.json"
        ledger, pool, idx = read(ledgerpath), load_pool(poolpath), read(indexpath)
        revisions = {c.unit.source_revision for c in pool.candidates}
        if revisions != {idx["revision"]}:
            raise ValueError("Mixed source revision")
        start = time.monotonic()
        features = build_features(ledger, pool, encoder, idx["nodes"])
        target = root / "inputs" / name
        atomic_json(target / "ledger.json", ledger)
        atomic_json(target / "pool.json", asdict(pool))
        atomic_json(target / "features.json", features)
        atomic_json(target / "panel.json", panel(features))
        meta = {
            "name": name,
            "phase": "development" if name in DEV else "check",
            "base_revision": idx["revision"],
            "source_ledger_sha256": sha(ledgerpath),
            "source_pool_sha256": sha(poolpath),
            "source_index_sha256": sha(indexpath),
            "pairs": len(features),
            "candidates": len(pool.candidates),
            "requirements": len(ledger["requirements"]),
            "feature_seconds": time.monotonic() - start,
            "files": {p.name: sha(p) for p in target.iterdir()},
        }
        manifest.append(meta)
        print(name, meta["pairs"], "pairs", flush=True)
    atomic_json(
        root / "inputs.json",
        {
            "study": STUDY,
            "seed": SEED,
            "states": manifest,
            "panel_frozen_before_labels": True,
            "encoder": prior["representation"],
            "max_online_review_pairs": 256,
            "reference_role_seconds": 600,
            "online_seconds": 60,
            "online_repeats": 2,
            "feature_cost_policy": "Common precomputed public features and original MMR available to every method; measured preparation reported separately. Each online run pays its own selector and transport setup within 60s.",
        },
    )
    # Deterministic eight development pairs: four per state, varied source lengths.
    rehearsal = []
    for name in DEV:
        _, _, fs, _ = state(root, name)
        ordered = sorted(fs, key=lambda f: (len(f["unit_text"]), f["pair_id"]))
        for fraction in (0.0, 0.33, 0.66, 1.0):
            rehearsal.append(
                {
                    "state": name,
                    "pair": ordered[round(fraction * (len(ordered) - 1))]["pair_id"],
                }
            )
    atomic_json(root / "transport-material.json", rehearsal)


def transport_material(root):
    # Namespace IDs so both states share exactly the same eight-pair payload.
    from dataclasses import replace
    from .repair_composer import CandidatePool, Obligation

    reqs, candidates, pairs = [], [], []
    for row in read(root / "transport-material.json"):
        ledger, pool, _, _ = state(root, row["state"])
        rid, uid = row["pair"]
        prefix = row["state"] + ":"
        req = next(r for r in ledger["requirements"] if r["requirement_id"] == rid)
        if prefix + rid not in {r["requirement_id"] for r in reqs}:
            reqs.append({**req, "requirement_id": prefix + rid})
        c = next(c for c in pool.candidates if c.unit.unit_id == uid)
        if prefix + uid not in {c.unit.unit_id for c in candidates}:
            candidates.append(replace(c, unit=replace(c.unit, unit_id=prefix + uid)))
        pairs.append((prefix + rid, prefix + uid))
    ledger = {
        "requirements": reqs,
        "weights": {r["requirement_id"]: 1 / len(reqs) for r in reqs},
    }
    pool = CandidatePool(
        tuple(candidates),
        (),
        tuple(
            Obligation(
                r["requirement_id"], r["expected_text"], "public", "unverified", ()
            )
            for r in reqs
        ),
        "",
    )
    return ledger, pool, pairs


def benchmark(root):
    ledger, pool, pairs = transport_material(root)
    configs = [
        (life, size, rep)
        for rep in range(2)
        for life in ("cold", "reuse")
        for size in (2, 8)
    ]
    random.Random(SEED).shuffle(configs)
    atomic_json(root / "transport-order.json", configs)
    rows = []
    for number, (life, size, rep) in enumerate(configs):
        out = root / "transport" / f"{number:02}-{life}-{size}-r{rep}"
        tx = RelationTransport(out, lifecycle=life)
        try:
            for i in range(0, 8, size):
                selected = pairs[i : i + size]
                value, cost = tx.call(
                    ledger, pool, selected, out / f"batch-{i:02}", seconds=90
                )
                store = RelationStore(out / f"validation-{i}.json", ledger, pool)
                store.ingest(selected, value)
                cost["valid_rows"] = sum(
                    store.records[p]["state"]
                    in {"VALID_ZERO", "VALID_POSITIVE", "SEMANTIC_UNRESOLVED"}
                    for p in selected
                )
                cost["sequence"] = number
                cost["repeat"] = rep
                rows.append(cost)
                atomic_json(root / "transport-observations.json", rows)
                print(
                    "transport",
                    number,
                    i,
                    cost["status"],
                    round(cost["seconds"], 2),
                    cost["valid_rows"],
                    flush=True,
                )
        finally:
            tx.close()
    # Choose solely valid throughput/time, including complete sequence cleanup costs.
    scores = {}
    for life in ("cold", "reuse"):
        observations = [r for r in rows if r["lifecycle"] == life]
        elapsed = sum(
            read(p)["seconds"]
            for p in (root / "transport").glob(f"*-{life}-*/sequence.json")
        )
        scores[life] = sum(r["valid_rows"] for r in observations) / max(0.001, elapsed)
    chosen = max(scores, key=lambda k: (scores[k], k == "cold"))
    atomic_json(
        root / "cost-model.json",
        {
            "lifecycle": chosen,
            "observations": rows,
            "selection_valid_rows_per_second": scores,
            "estimator": "conservative_length_scaled_envelope",
            "margin": 1.25,
            "cleanup_reserve": 5,
        },
    )


def verify_inputs(root):
    for s in read(root / "inputs.json")["states"]:
        for name, expected in s["files"].items():
            if sha(root / "inputs" / s["name"] / name) != expected:
                raise ValueError("Frozen input drift")


def reference(root, phase):
    verify_inputs(root)
    if phase == "check":
        verify_freeze(root)
    for name in DEV if phase == "development" else CHECK:
        ledger, pool, _, panel_rows = state(root, name)
        for role in ("Q", "J"):
            out = root / "reference" / name / role
            if (out / "done.json").exists() and read(out / "done.json")[
                "status"
            ] == "COMPLETE":
                continue
            domain = {tuple(r["pair"]) for r in panel_rows}
            out.mkdir(parents=True, exist_ok=True)
            prompt = QUERY_PROMPT if role == "Q" else AUDIT_PROMPT
            store = RelationStore(out / "store.json", ledger, pool, prompt=prompt)
            elapsed = sum(
                read(p)["seconds"] for p in out.glob("sequence-*/sequence.json")
            )
            start = time.monotonic()
            tx = RelationTransport(
                out / f"sequence-{len(list(out.glob('sequence-*'))):03}",
                lifecycle="reuse",
                deadline=start + max(0, 600 - elapsed),
            )
            try:
                while time.monotonic() - start + elapsed < 595:
                    pending = sorted(set(store.pending()) & domain)
                    if not pending:
                        break
                    batch = pending[:8]
                    store.ingest(batch, {})
                    value, cost = tx.call(
                        ledger,
                        pool,
                        batch,
                        tx.root / f"batch-{len(list(tx.root.glob('batch-*'))):03}",
                        seconds=min(90, 595 - elapsed - (time.monotonic() - start)),
                        prompt=prompt,
                    )
                    store.ingest(batch, value)
                    if cost["status"] == "ERROR" and not value.get(
                        "relations", value.get("rows", [])
                    ):
                        break  # confirmed connection termination; resumable explicit pending-only call
                    print(
                        "reference",
                        name,
                        role,
                        len(domain - set(store.pending())),
                        "/",
                        len(domain),
                        flush=True,
                    )
            finally:
                tx.close()
            atomic_json(
                out / "done.json",
                {
                    "terminal": len(domain - set(store.pending())),
                    "domain": len(domain),
                    "seconds": elapsed + time.monotonic() - start,
                    "status": "COMPLETE"
                    if not domain & set(store.pending())
                    else "PARTIAL",
                },
            )


def freeze(root, repo, encoder_path):
    verify_inputs(root)
    if encoder_path is None:
        raise ValueError(
            "Freeze requires the original encoder path for fresh verification"
        )
    for name, expected in read(root / "inputs.json")["encoder"]["files"].items():
        if sha(encoder_path / name) != expected:
            raise ValueError("Frozen encoder drift")
    paths = [*sorted((repo / "src/hermes_skilleval/intervention").glob("*.py"))]
    atomic_json(
        root / "freeze.json",
        {
            "algorithm": {str(p.relative_to(repo)): sha(p) for p in paths},
            "inputs_sha256": sha(root / "inputs.json"),
            "cost_sha256": sha(root / "cost-model.json"),
            "q_prompt": identity(QUERY_PROMPT),
            "j_prompt": identity(AUDIT_PROMPT),
            "timestamp": time.time(),
            "encoder_freshly_verified": True,
            "execution_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True
            ).strip(),
        },
    )


def verify_freeze(root):
    verify_inputs(root)
    frozen = read(root / "freeze.json")
    repo = Path(__file__).resolve().parents[3]
    for name, expected in frozen["algorithm"].items():
        if sha(repo / name) != expected:
            raise ValueError("Algorithm changed after freeze: " + name)
    if (
        sha(root / "inputs.json") != frozen["inputs_sha256"]
        or sha(root / "cost-model.json") != frozen["cost_sha256"]
    ):
        raise ValueError("Study configuration changed after freeze")


def audit_status(q, j):
    if j is None:
        return "REVIEW_NOT_SAMPLED"
    if q.get("state") not in {"VALID_POSITIVE", "VALID_ZERO"} or j.get("state") not in {
        "VALID_POSITIVE",
        "VALID_ZERO",
    }:
        return "REVIEW_UNKNOWN"
    if q["state"] == j["state"] == "VALID_ZERO":
        return "CORROBORATED_ZERO"
    if (
        q["state"] == j["state"] == "VALID_POSITIVE"
        and q["relation"] == j["relation"]
        and q["applicable"] == j["applicable"]
    ):
        # Independently emitted exact condition anchors are compared by a fixed rule.
        for field, textfield in [
            ("condition_atoms", "requirement_quote"),
            ("source_condition_atoms", "unit_quote"),
        ]:
            a, b = [q.get(textfield, "")], [j.get(textfield, "")]
            if (
                not isinstance(a, list)
                or not isinstance(b, list)
                or (field == "condition_atoms" and (not a or not b))
            ):
                return "REVIEW_UNKNOWN"
            if not all(isinstance(x, str) and x for x in a + b):
                return "REVIEW_UNKNOWN"
            for row, atoms in ((q, a), (j, b)):
                original = (
                    row.get("requirement_quote", "")
                    if field == "condition_atoms"
                    else row.get("unit_quote", "")
                )
                if any(atom not in original for atom in atoms):
                    return "REVIEW_UNKNOWN"
            if set(a) != set(b):
                return "REVIEW_UNKNOWN"  # Different anchors may be compatible; cannot prove conflict.
        if literals(q.get("condition_basis", "")) != literals(
            j.get("condition_basis", "")
        ):
            return "REVIEW_UNKNOWN"
        return "SUPPORTED_POSITIVE"
    return "DISPUTED"


def records(path):
    return {tuple(r["pair"]): r["record"] for r in read(path)["records"]}


def metrics(ledger, store, requested, checks):
    unique = list(dict.fromkeys(requested))
    counts = Counter(audit_status(store.records[p], checks.get(p)) for p in unique)
    positive = [
        p
        for p in unique
        if audit_status(store.records[p], checks.get(p)) == "SUPPORTED_POSITIVE"
    ]
    rids = {p[0] for p in positive}
    return {
        "request_positions": len(requested),
        "unique_requested": len(set(requested)),
        "valid_rows": sum(
            store.records[p]["state"]
            in {"VALID_POSITIVE", "VALID_ZERO", "SEMANTIC_UNRESOLVED"}
            for p in unique
        ),
        "audit_counts": dict(counts),
        "supported_types": dict(
            Counter(store.records[p]["relation"] for p in positive)
        ),
        "supported_requirements": len(rids),
        "supported_weight": sum(ledger["weights"][r] for r in rids),
        "relation_counts": store.summary()["counts"],
        "requested_relation_counts": dict(
            Counter(store.records[p]["state"] for p in unique)
        ),
    }


def connection_streak(previous, count, status, error):
    kind = error.split(":", 1)[0] if status == "ERROR" else None
    if kind not in {"RuntimeError", "BrokenPipeError"}:
        return None, 0
    return kind, count + 1 if previous == kind else 1


def run_policy(root, name, method, out, *, sealed=None):
    ledger, pool, features, panel_rows = state(root, name)
    return run_public_policy(
        ledger,
        pool,
        features,
        read(root / "cost-model.json"),
        out,
        method=method,
        seconds=60,
        sealed=sealed,
        panel_rows=panel_rows,
        name=name,
    )


def run_public_policy(
    ledger,
    pool,
    features,
    model,
    out,
    *,
    method="R",
    seconds=60,
    sealed=None,
    panel_rows=(),
    name="public-state",
):
    """Run the inherited query/selection chain using only explicit public inputs.

    No prior study directory, reference table or source-audit result is loaded.
    Each output directory reserves an independent acquisition with an empty store.
    """
    if not 0 <= seconds <= 60:
        raise ValueError("Relation budget must be within zero to sixty seconds")
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + seconds if sealed is None else None
    store = RelationStore(out / "store.json", ledger, pool, prompt=QUERY_PROMPT)
    selector = ExactSelector(pool, ledger, deadline=deadline)
    pack, result = selector.solve(store, deadline=deadline)
    atomic_json(out / "mmr.json", selector.mmr.to_dict())
    envelope = CostEnvelope(list(model["observations"]), model["lifecycle"])
    domain = {tuple(r["pair"]) for r in panel_rows} if sealed else None

    def length(pairs):
        return len(
            json.dumps({**batch_payload(ledger, pool, pairs), "prompt": QUERY_PROMPT})
        )

    costs = {
        tuple(f["pair_id"]): envelope.estimate(2, length([f["pair_id"]]))
        for f in features
    }
    seen, history = [], []
    failures = Counter()
    connection_failures = 0
    connection_kind = None
    tx = (
        None
        if sealed
        else RelationTransport(
            out / "transport", lifecycle=model["lifecycle"], deadline=deadline - 5
        )
    )
    reason = "PAIR_CAP"
    first_positive = first_change = None
    try:
        while len(set(seen)) < (32 if sealed else 48):
            costs = {
                tuple(f["pair_id"]): envelope.estimate(2, length([f["pair_id"]]))
                for f in features
            }
            ranked = requests(
                selector,
                store,
                result,
                features,
                method=method,
                size=min(8, (32 if sealed else 48) - len(set(seen))),
                costs=costs,
                offset=len(seen),
                domain=domain,
                excluded=set(seen) if sealed else {p for p in seen if failures[p] >= 2},
            )
            if not ranked:
                reason = "DOMAIN_EXHAUSTED"
                break
            if sealed:
                batch = ranked[:1]
                # Only this requested Q row crosses the replay boundary.
                value = sealed(batch)
                cost = {"seconds": None}
            else:
                batch, estimate = envelope.choose(
                    ranked,
                    length,
                    deadline - time.monotonic(),
                    cold=tx.session is None,
                    pending_count=sum(failures[p] < 2 for p in store.pending()),
                )
                if not batch:
                    reason = "NO_AFFORDABLE_BATCH"
                    break
                store.ingest(batch, {})
                value, cost = tx.call(
                    ledger,
                    pool,
                    batch,
                    out / f"batch-{len(history):03}",
                    seconds=deadline - 5 - time.monotonic(),
                    prompt=QUERY_PROMPT,
                )
            seen.extend(batch)
            store.ingest(batch, value, late=bool(cost.get("late")))
            if not sealed:
                cost["raw_rows"] = len(value.get("relations", value.get("rows", [])))
                cost["valid_rows"] = sum(
                    store.records[p]["state"]
                    in {"VALID_POSITIVE", "VALID_ZERO", "SEMANTIC_UNRESOLVED"}
                    for p in batch
                )
                envelope.observations.append(cost)
                for p in batch:
                    failures[p] += 1
            event = {
                "requested": batch,
                "position": len(seen),
                "seconds": time.monotonic() - start if not sealed else None,
                "cost": cost,
                "pack": pack.to_dict(),
                "solver": result,
                "update_status": "PENDING_SOLVE",
            }
            history.append(event)
            atomic_json(out / "trajectory.json", history)
            if first_positive is None:
                positions = [
                    i
                    for i, p in enumerate(batch)
                    if store.records[p]["state"] == "VALID_POSITIVE"
                ]
                if positions:
                    first_positive = {
                        "position": len(seen) - len(batch) + positions[0] + 1,
                        "batch_completion_position": len(seen),
                        "seconds": time.monotonic() - start if not sealed else None,
                    }
            try:
                pack, result = selector.solve(store, deadline=deadline)
            except TimeoutError:
                reason = "SOLVER_DEADLINE"
                event["update_status"] = "SOLVER_DEADLINE_LOCKED_PREVIOUS_PACK"
                atomic_json(out / "trajectory.json", history)
                break
            elapsed = time.monotonic() - start
            if first_change is None and set(pack.indices) != set(selector.mmr.indices):
                first_change = {
                    "position": len(seen),
                    "seconds": elapsed if not sealed else None,
                }
            event.update(
                {
                    "seconds": elapsed if not sealed else None,
                    "pack": pack.to_dict(),
                    "solver": result,
                    "update_status": "UPDATED",
                }
            )
            atomic_json(out / "trajectory.json", history)
            if not sealed and time.monotonic() >= deadline:
                reason = "TIME_BUDGET"
                break
            if not sealed:
                error = cost.get("error", "")
                connection_kind, connection_failures = connection_streak(
                    connection_kind, connection_failures, cost["status"], error
                )
                if cost["status"] == "ERROR" and (
                    "Frozen helper model unavailable" in error
                    or "Forbidden helper tool use" in error
                ):
                    reason = "HELPER_UNAVAILABLE"
                    break
                if connection_failures >= 2:
                    reason = "CONNECTION_UNAVAILABLE_PENDING_PRESERVED"
                    break
                # Format failures remain pending; terminal semantic rows never retry.
    finally:
        if tx:
            tx.close()
    final = {
        "state": name,
        "method": method,
        "requested": seen,
        "pack": pack.to_dict(),
        "stop_reason": reason,
        "seconds": time.monotonic() - start if not sealed else None,
        "solver": result,
        "first_positive": first_positive,
        "first_non_mmr": first_change,
        "input_identity": store.digest,
        "new_repair_agent_calls": 0,
    }
    atomic_json(out / "final.json", final)
    return final


def replay(root):
    verify_freeze(root)
    root = root.resolve()
    for name in DEV + CHECK:
        q = records(root / "reference" / name / "Q/store.json")
        for method in ("S", "A0", "R", "V", "V-no-cost"):
            out = root / "replay" / name / method
            if (out / "final.json").exists():
                continue
            # OS-level denial: policy worker has no read access to sealed Q/J or audits.
            denied = [root / "reference", root / "online-review"]
            profile = "(version 1)(allow default)" + "".join(
                "(deny file-read* (subpath " + json.dumps(str(p)) + "))" for p in denied
            )
            command = [
                "/usr/bin/sandbox-exec",
                "-p",
                profile,
                sys.executable,
                "-m",
                "hermes_skilleval.intervention.relation_query_worker",
                str(root),
                name,
                method,
                str(out),
            ]
            proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
            )
            try:
                for line in proc.stdout:
                    batch = [tuple(p) for p in json.loads(line)["requested"]]
                    value = {
                        "relations": [q[p] for p in batch if q[p]["state"] in TERMINAL]
                    }
                    proc.stdin.write(json.dumps(value) + "\n")
                    proc.stdin.flush()
                if proc.wait() != 0:
                    raise RuntimeError("Sealed replay worker failed")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            print("replay", name, method, flush=True)


def acquire(root):
    verify_freeze(root)
    order = [
        (name, method, rep)
        for name in CHECK
        for method in ("A0", "R", "V")
        for rep in range(2)
    ]
    random.Random(SEED).shuffle(order)
    atomic_json(root / "online-order.json", order)
    for i, (name, method, rep) in enumerate(order):
        out = root / "online" / f"{i:02}-{name}-{method}-r{rep}"
        if out.exists():
            if (out / "final.json").exists():
                continue
            raise ValueError(
                "Interrupted online attempt remains reserved; do not overwrite"
            )
        protected = [root.resolve() / "reference", root.resolve() / "online-review"]
        profile = "(version 1)(allow default)" + "".join(
            "(deny file-read* (subpath " + json.dumps(str(p)) + "))" for p in protected
        )
        subprocess.run(
            [
                "/usr/bin/sandbox-exec",
                "-p",
                profile,
                sys.executable,
                "-m",
                "hermes_skilleval.intervention.relation_query_worker",
                str(root.resolve()),
                name,
                method,
                str(out.resolve()),
                "online",
            ],
            check=True,
        )
        result = read(out / "final.json")
        print(
            "online",
            i,
            name,
            method,
            len(result["requested"]),
            result["stop_reason"],
            flush=True,
        )
    atomic_json(
        root / "online-locked.json",
        {
            "files": {
                str(p.relative_to(root)): sha(p)
                for p in (root / "online").rglob("*.json")
                if "server" not in p.parts and p.name not in {"input.json", "raw.json"}
            },
            "timestamp": time.time(),
        },
    )


def review(root):
    verify_freeze(root)
    for path, expected in read(root / "online-locked.json")["files"].items():
        if sha(root / path) != expected:
            raise ValueError("Online trajectory lock drift")
    for name in CHECK:
        finals = [
            read(p)
            for p in (root / "online").glob("*/final.json")
            if read(p)["state"] == name
        ]
        union = sorted({tuple(p) for f in finals for p in f["requested"]})
        if len(union) > 128:
            union = sorted(random.Random(SEED).sample(union, 128))
        ledger, pool, _, _ = state(root, name)
        # Remaining review quota covers final and initial MMR source pairs, still blind.
        pack_uids = {u["unit_id"] for f in finals for u in f["pack"]["units"]}
        for path in (root / "online").glob("*/final.json"):
            if read(path)["state"] == name:
                pack_uids.update(
                    u["unit_id"] for u in read(path.parent / "mmr.json")["units"]
                )
        extras = sorted(
            {
                (r["requirement_id"], u)
                for r in ledger["requirements"]
                for u in pack_uids
            }
            - set(union)
        )
        union += random.Random(SEED).sample(extras, min(len(extras), 128 - len(union)))
        out = root / "online-review" / name
        out.mkdir(parents=True, exist_ok=True)
        atomic_json(
            out / "sample.json",
            {
                "pairs": union,
                "cap": 128,
                "rule": "all requested pairs if <=128, otherwise uniform requested sample; remaining state quota uniformly samples MMR/final-package pairs",
            },
        )
        store = RelationStore(out / "store.json", ledger, pool, prompt=AUDIT_PROMPT)
        tx = RelationTransport(
            out / f"sequence-{len(list(out.glob('sequence-*'))):03}", lifecycle="reuse"
        )
        try:
            for i in range(0, len(union), 8):
                batch = [p for p in union[i : i + 8] if p in store.pending()]
                if not batch:
                    continue
                store.ingest(batch, {})
                value, cost = tx.call(
                    ledger,
                    pool,
                    batch,
                    tx.root / f"batch-{i:03}",
                    seconds=90,
                    prompt=AUDIT_PROMPT,
                )
                store.ingest(batch, value)
                print("review", name, i, cost["status"], flush=True)
        finally:
            tx.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=[
            "prepare-panel",
            "benchmark-transport",
            "build-reference",
            "freeze",
            "replay-queries",
            "run-acquisition",
            "review-sources",
            "summarize",
        ],
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--assets", type=Path)
    p.add_argument("--encoder", type=Path)
    p.add_argument("--phase", choices=["development", "check"], default="development")
    a = p.parse_args()
    if a.action == "prepare-panel":
        prepare(a)
    elif a.action == "benchmark-transport":
        benchmark(a.output)
    elif a.action == "build-reference":
        reference(a.output, a.phase)
    elif a.action == "freeze":
        freeze(a.output, a.repo, a.encoder)
    elif a.action == "replay-queries":
        replay(a.output)
    elif a.action == "run-acquisition":
        acquire(a.output)
    elif a.action == "review-sources":
        review(a.output)
    else:
        from .relation_query_report import summarize

        summarize(a.output, a.repo / "artifacts" / STUDY)


if __name__ == "__main__":
    main()
