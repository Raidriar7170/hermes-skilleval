"""Versioned development repair; reuse unchanged semantic pairs, never resample them."""

import argparse
from dataclasses import asdict
from pathlib import Path
import time

from hermes_skilleval.intervention.evidence_linked_state import analyze
from hermes_skilleval.intervention.linked_context_study import read, load_pool
from hermes_skilleval.intervention.local_source_index import build_index, include_legacy
from hermes_skilleval.intervention.local_retrieval import retrieve
from hermes_skilleval.intervention.linked_composition import select
from hermes_skilleval.intervention.repair_composer import CompleteEncoder
from hermes_skilleval.intervention.repair_knowledge import RepairKnowledgeUnit
from hermes_skilleval.intervention.source_relation import (
    propose_observation_links,
    compact_propose,
)
from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.value import Encoder

p = argparse.ArgumentParser()
p.add_argument("--private", type=Path, required=True)
p.add_argument("--legacy", type=Path, required=True)
p.add_argument("--encoder", type=Path, required=True)
p.add_argument("--phase", choices=["prepare", "relations", "compose"], required=True)
p.add_argument("--iteration", default="development-v3")
p.add_argument("--reuse-observation-from", default="development-v2")
p.add_argument("--reuse-relations-from")
a = p.parse_args()
lock = read(a.legacy / "study-v1/pilot-lock.json")
plan = read("configs/repair-knowledge-composition-v1/plan.json")
encoder = CompleteEncoder(Encoder(a.encoder)) if a.phase == "prepare" else None
for state in lock["states"]:
    name = state["mechanism"]
    out = a.private / a.iteration / name
    row = next(r for r in plan["tasks"] if r["instance_id"] == state["task_id"])
    if a.phase == "prepare":
        if (out / "prepared.json").exists():
            continue
        cp = read(Path(state["checkpoint"]) / "checkpoint.json")
        ledger = analyze(
            cp["state"]["request"],
            cp["visible_events"],
            checkpoint_event_count=len(cp["visible_events"]),
            initial_source_version=row["base_commit"],
        )
        prior_links = (
            a.private
            / a.reuse_observation_from
            / name
            / "observation-links"
            / "result.json"
        )
        if prior_links.exists():
            links = read(prior_links)["observation_links"]
            dump(
                out / "observation-link-reuse.json",
                {
                    "source": str(prior_links),
                    "reason": "same request and exact observed outputs; current lifecycle/status recomputed conservatively",
                },
            )
        else:
            links = propose_observation_links(ledger, out / "observation-links")
        ledger = analyze(
            cp["state"]["request"],
            cp["visible_events"],
            checkpoint_event_count=len(cp["visible_events"]),
            initial_source_version=row["base_commit"],
            links=links,
        )
        dump(out / "ledger.json", ledger)
        start = time.monotonic()
        index = build_index(
            a.legacy / "tasks" / row["instance_id"] / "base",
            repository=row["repo"],
            revision=row["base_commit"],
        )
        old = [
            RepairKnowledgeUnit.from_dict(u)
            for u in read(a.legacy / "knowledge" / row["base_commit"] / "units.json")
        ]
        include_legacy(index, a.legacy / "tasks" / row["instance_id"] / "base", old)
        dump(out / "index.json", index)
        visible = "\n".join(o["output"] for o in ledger["observations"])
        observed = tuple(
            p
            for o in ledger["observations"]
            if o["kind"] in {"SOURCE_READ", "CANDIDATE_CHANGE"}
            for p in o["paths"]
        )
        for variant, kwargs in [
            ("full", {}),
            ("no-expansion", {"expand": False}),
            ("old40", {"allowed_node_ids": set(index["legacy_subset_node_ids"])}),
        ]:
            pool, diag = retrieve(
                index,
                ledger,
                encoder=encoder,
                visible_text=visible,
                read_symbols=observed,
                **kwargs,
            )
            dump(out / (variant + "-pool.json"), asdict(pool))
            dump(out / (variant + "-retrieval.json"), diag)
        dump(
            out / "prepared.json",
            {
                "seconds": time.monotonic() - start,
                "research_executions": 0,
                "coverage": index["coverage"],
            },
        )
        print("prepared", name, flush=True)
    elif a.phase == "relations":
        pool = load_pool(out / "full-pool.json")
        ledger = read(out / "ledger.json")
        oldpool = (
            load_pool(a.private / a.reuse_relations_from / name / "full-pool.json")
            if a.reuse_relations_from
            else load_pool(a.private / (name + "-pool.json"))
        )

        # Require exact whole-unit equality, not merely an ID or a matching quote.
        def semantic_input(unit):
            return {
                "role": unit.claim_role,
                "symbols": unit.applies_to,
                "conditions": unit.preconditions,
                "text": unit.statement,
            }

        oldunits = {c.unit.unit_id: semantic_input(c.unit) for c in oldpool.candidates}
        unchanged = {
            c.unit.unit_id
            for c in pool.candidates
            if oldunits.get(c.unit.unit_id) == semantic_input(c.unit)
        }
        prior = (
            a.private
            / (
                "semantic-dev-v1"
                if name == "empty-keyed-group-naming"
                else "semantic-dev-compact-v1"
            )
            / name
            / "relations.json"
        )
        if a.reuse_relations_from:
            prior = a.private / a.reuse_relations_from / name / "relations.json"
        if not prior.exists():
            raise ValueError("Prior semantic attempt still incomplete: " + name)
        reusable = [r for r in read(prior) if r["unit_id"] in unchanged]
        relations = compact_propose(ledger, pool, out / "semantic", reusable=reusable)
        dump(out / "relations.json", relations)
        dump(
            out / "relation-reuse.json",
            {
                "reused_pairs": sum(r["unit_id"] in unchanged for r in relations),
                "total_pairs": len(relations),
                "policy": "unchanged exact units and request identities reused; only new inputs proposed",
            },
        )
        print("relations", name, len(relations), flush=True)
    else:
        pool = load_pool(out / "full-pool.json")
        ledger = read(out / "ledger.json")
        relations = read(out / "relations.json")
        packs = {
            m: select(pool, ledger, method=m, relations=relations).to_dict()
            for m in ["M-local", "H-sim", "H-link"]
        }
        dump(out / "packs.json", packs)
        print("composed", name, {m: p["tokens"] for m, p in packs.items()}, flush=True)
