"""Source-bound semantic proposals: validated provenance, not logical proof."""

from __future__ import annotations

import hashlib
import json

WEIGHTS = {
    "CONTRACT_SUPPORT": 1.0,
    "VERIFICATION_PATTERN": 0.7,
    "PRECONDITION": 0.6,
    "CONTRADICTION_CONTEXT": 0.6,
    "IMPLEMENTATION_CONTEXT": 0.3,
    "TOPICAL_ONLY": 0.0,
    "UNRESOLVED": 0.0,
}
PROMPT = """Classify source relationships only. Do not solve the repair or propose code.
Use only the supplied public requirement and exact legal base source. Existing
behavior is not a normative contract. Shared words alone are TOPICAL_ONLY.
For each pair return requirement_id, unit_id, relation (CONTRACT_SUPPORT,
VERIFICATION_PATTERN, PRECONDITION, CONTRADICTION_CONTEXT,
IMPLEMENTATION_CONTEXT, TOPICAL_ONLY, UNRESOLVED), requirement_quote,
unit_quote, applicable (true/false/null), condition_basis, rationale.
Quotes must be nonempty exact substrings. Positive relations require specific
behavior/symbol/condition correspondence, not generic error/default/type terms.
CONTRACT_SUPPORT requires documented_contract; VERIFICATION_PATTERN requires
public_test_example. PRECONDITION must cite the actual condition and its
applicability. If uncertain return UNRESOLVED with applicable null. Do not
invent missing references or claim correctness of existing code.
Return only a JSON object with key relations, a list containing every pair.
"""


def proposal_batches(ledger, pool, *, batch_size=12):
    pairs = []
    for r in ledger["requirements"]:
        for c in pool.candidates:
            pairs.append(
                {
                    "requirement_id": r["requirement_id"],
                    "requirement": r["expected_text"],
                    "unit_id": c.unit.unit_id,
                    "role": c.unit.claim_role,
                    "symbol": list(c.unit.applies_to),
                    "preconditions": list(c.unit.preconditions),
                    "source": c.unit.statement,
                }
            )
    return [
        {"prompt": PROMPT, "pairs": pairs[i : i + batch_size]}
        for i in range(0, len(pairs), batch_size)
    ]


def validate_relations(ledger, pool, proposals):
    reqs = {r["requirement_id"]: r for r in ledger["requirements"]}
    units = {c.unit.unit_id: c.unit for c in pool.candidates}
    found = {}
    for row in proposals:
        key = (row["requirement_id"], row["unit_id"])
        if key in found:
            raise ValueError("Duplicate relationship proposal")
        if key[0] not in reqs or key[1] not in units:
            raise ValueError("Unknown relation input")
        r, u = reqs[key[0]], units[key[1]]
        rq, uq = row["requirement_quote"], row["unit_quote"]
        provenance_valid = bool(
            rq and rq in r["expected_text"] and uq and uq in u.statement
        )
        relation = row["relation"]
        if relation not in WEIGHTS:
            raise ValueError("Unknown relation class")
        if row["applicable"] not in (True, False, None):
            raise ValueError("Invalid applicability")
        role_valid = not (
            (relation == "CONTRACT_SUPPORT" and u.claim_role != "documented_contract")
            or (
                relation == "VERIFICATION_PATTERN"
                and u.claim_role != "public_test_example"
            )
        )
        basis_valid = bool(row.get("condition_basis") and row.get("rationale"))
        weight = (
            WEIGHTS[relation]
            if role_valid
            and provenance_valid
            and basis_valid
            and row["applicable"] is True
            else 0.0
        )
        found[key] = {
            **row,
            "weight": weight,
            "role_valid": role_valid,
            "provenance_valid": provenance_valid,
            "basis_valid": basis_valid,
            "validation_status": "VALID_PROPOSAL"
            if provenance_valid
            and role_valid
            and (not WEIGHTS[relation] or basis_valid)
            else "REJECTED_ZERO_COVERAGE",
            "semantic_truth": "MODEL_PROPOSAL_REQUIRES_INDEPENDENT_CHECK",
            "requirement_span": r["verbatim_span"],
            "unit_spans": [
                {
                    "path": s.path_or_public_url,
                    "revision": s.revision,
                    "start": s.line_start,
                    "end": s.line_end,
                }
                for s in u.source_spans
            ],
        }
    expected = {(r, u) for r in reqs for u in units}
    if set(found) != expected:
        raise ValueError("Incomplete relation matrix; missing pairs stay explicit")
    return [found[(r, u)] for r in reqs for u in units]


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def propose_with_session(
    ledger,
    pool,
    output,
    *,
    model="gpt-5.6-sol",
    image="hermes-repair-knowledge-executor:v1",
    batch_size=24,
):
    """One stored model attempt per batch. No repository mounts or repair tools.

    Format/service failures remain recorded and raise; semantic results are
    never resampled or filtered by whether they favor a selector.
    """
    from pathlib import Path
    import time
    from .diagnostic import home_auth
    from .session import Session, dump

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    empty = output / "empty"
    empty.mkdir(exist_ok=True)
    for reserved in (".git", ".codex", ".agents"):
        (empty / reserved).mkdir(exist_ok=True)
    skills = output / "empty-skills"
    skills.mkdir(exist_ok=True)
    batches = proposal_batches(ledger, pool, batch_size=batch_size)
    all_rows = []
    for i, batch in enumerate(batches):
        run = output / f"batch-{i:04}"
        digest = identity(batch)
        original = run
        retry = 0
        while (run / "error.json").exists() and not (run / "result.json").exists():
            error = json.loads((run / "error.json").read_text())["error"]
            if "thread/start" in error and "bwrap:" in error:
                retry += 1
                run = output / f"batch-{i:04}-thread-start-repair-v{retry}"
            else:
                break
        if run.exists():
            recorded = json.loads((run / "input.json").read_text())
            if recorded["digest"] != digest:
                raise ValueError("Existing semantic attempt input differs")
            if not (run / "result.json").exists():
                raise ValueError(
                    "Interrupted semantic attempt requires explicit versioned engineering repair"
                )
            all_rows.extend(json.loads((run / "result.json").read_text())["relations"])
            continue
        run.mkdir()
        for reserved in (".git", ".codex", ".agents"):
            (run / "scratch" / reserved).mkdir(parents=True, exist_ok=True)
        dump(
            run / "input.json",
            {
                "digest": digest,
                "model": model,
                "effort": "medium",
                "batch": batch,
                "purpose": "semantic_relation_proposal",
                "research_repair_executions": 0,
                "prior_engineering_attempt": str(original) if original != run else None,
            },
        )
        home, auth = home_auth(run)
        started = time.monotonic()
        try:
            with Session(
                empty,
                run / "scratch",
                home,
                skills,
                run / "server",
                model=model,
                image=image,
            ) as session:
                available = session.rpc("model/list", {"includeHidden": True}).get(
                    "data", []
                )
                if not any((r.get("model") or r.get("id")) == model for r in available):
                    raise ValueError("Required semantic model unavailable")
                session.start()
                message = (
                    batch["prompt"]
                    + "\nNo tool use. Put the requested JSON object as a JSON string in summary; segment_status TASK_COMPLETE.\n"
                    + json.dumps(batch["pairs"], ensure_ascii=False)
                )
                turn = session.turn(message, 300)
                tool_events = [
                    e
                    for e in session.events
                    if e.get("method") == "item/completed"
                    and e.get("params", {}).get("item", {}).get("type")
                    in {"commandExecution", "fileChange", "mcpToolCall", "webSearch"}
                ]
                if tool_events:
                    raise ValueError("Semantic analysis used forbidden tools")
                messages = [
                    x["text"]
                    for x in turn.get("items", [])
                    if x.get("type") == "agentMessage"
                ]
                if not messages:
                    raise ValueError("Missing semantic output")
                outer = json.loads(messages[-1])
                value = json.loads(outer["summary"])
                dump(run / "result.json", value)
                dump(
                    run / "cost.json",
                    {
                        "seconds": time.monotonic() - started,
                        "model_calls": 1,
                        "research_repair_executions": 0,
                    },
                )
                all_rows.extend(value["relations"])
        except Exception as exc:
            dump(
                run / "error.json",
                {"error": str(exc), "seconds": time.monotonic() - started},
            )
            raise
        finally:
            auth.unlink(missing_ok=True)
    result = validate_relations(ledger, pool, all_rows)
    dump(output / "relations.json", result)
    return result


def expand_compact_relations(value, ledger, pool):
    """Lossless transport expansion; never infer a positive relation."""
    if "relations" in value:
        return value["relations"]
    reqs = {r["requirement_id"]: r for r in ledger["requirements"]}
    units = {c.unit.unit_id: c.unit for c in pool.candidates}
    rows = []
    for entry in value["rows"]:
        rid, uid, relation = entry[:3]
        if len(entry) == 3 and relation in {"TOPICAL_ONLY", "UNRESOLVED"}:
            rows.append(
                {
                    "requirement_id": rid,
                    "unit_id": uid,
                    "relation": relation,
                    "requirement_quote": reqs[rid]["expected_text"],
                    "unit_quote": units[uid].statement,
                    "applicable": None,
                    "condition_basis": "No positive applicability asserted",
                    "rationale": "Model classified zero relationship; source spans supplied mechanically",
                    "quote_origin": "complete_supplied_input_not_model_selected",
                }
            )
        elif len(entry) == 8:
            rows.append(
                dict(
                    zip(
                        (
                            "requirement_id",
                            "unit_id",
                            "relation",
                            "requirement_quote",
                            "unit_quote",
                            "applicable",
                            "condition_basis",
                            "rationale",
                        ),
                        entry,
                    )
                )
            )
        else:
            raise ValueError("Malformed compact semantic row")
    return rows


def compact_proposal_input(ledger, pool):
    """Factor repeated source text out of the matrix; relation semantics unchanged."""
    return {
        "requirements": [
            {"id": r["requirement_id"], "text": r["expected_text"]}
            for r in ledger["requirements"]
        ],
        "units": [
            {
                "id": c.unit.unit_id,
                "role": c.unit.claim_role,
                "symbols": c.unit.applies_to,
                "conditions": c.unit.preconditions,
                "text": c.unit.statement,
            }
            for c in pool.candidates
        ],
        "prompt": PROMPT
        + """\nThe source lists are shared across pairs. Return ALL requirement-unit pairs.
Use concise exact quotes (a few words suffices) and concise, specific rationales.
No candidate scores or method identities are supplied. Do not infer a repair.
For compact transport, override the object-row format above: return {"rows": [...]}.
Every pair must still have one explicit row. A TOPICAL_ONLY or UNRESOLVED row is
[requirement_id, unit_id, relation]. A positive-relation row is
[requirement_id, unit_id, relation, requirement_quote, unit_quote, applicable,
condition_basis, rationale]. Quotes and reasons may be concise, never invented.
The short negative form asserts no applicability and receives zero coverage;
its provenance spans come from the complete supplied inputs, not a model quote.
""",
    }


def compact_propose(ledger, pool, output, *, reusable=()):
    """Single frozen proposal context per state, with all source text shared."""
    from pathlib import Path
    import time
    from .diagnostic import home_auth
    from .session import Session, dump

    output = Path(output)
    payload = compact_proposal_input(ledger, pool)
    wanted = {
        (r["requirement_id"], c.unit.unit_id)
        for r in ledger["requirements"]
        for c in pool.candidates
    }
    reused = [r for r in reusable if (r["requirement_id"], r["unit_id"]) in wanted]
    if len({(r["requirement_id"], r["unit_id"]) for r in reused}) != len(reused):
        raise ValueError("Duplicate reusable relation")
    pending = wanted - {(r["requirement_id"], r["unit_id"]) for r in reused}
    if reused:
        payload["requested_pairs"] = sorted(pending)
        payload["prompt"] += (
            "\nReturn ONLY requested_pairs; other pairs already have immutable proposals."
        )
    if not pending:
        return validate_relations(ledger, pool, reused)
    payload_id = identity(payload)
    if output.exists():
        saved = json.loads((output / "input.json").read_text())
        if saved["digest"] != payload_id:
            raise ValueError("Changed semantic input at reserved attempt")
        if not (output / "result.json").exists():
            raise ValueError(
                "Interrupted semantic attempt retained; versioned repair required"
            )
        value = json.loads((output / "result.json").read_text())
        return validate_relations(
            ledger, pool, [*reused, *expand_compact_relations(value, ledger, pool)]
        )
    output.mkdir(parents=True)
    dump(
        output / "input.json",
        {
            "digest": payload_id,
            "model": "gpt-5.6-sol",
            "effort": "medium",
            "payload": payload,
        },
    )
    empty = output / "empty"
    empty.mkdir()
    for reserved in (".git", ".codex", ".agents"):
        (empty / reserved).mkdir(exist_ok=True)
        (output / "scratch" / reserved).mkdir(parents=True, exist_ok=True)
    home, auth = home_auth(output)
    started = time.monotonic()
    try:
        with Session(
            empty,
            output / "scratch",
            home,
            empty,
            output / "server",
            model="gpt-5.6-sol",
            image="hermes-repair-knowledge-executor:v1",
        ) as session:
            advertised = session.rpc("model/list", {"includeHidden": True}).get(
                "data", []
            )
            if not any(
                (r.get("model") or r.get("id")) == "gpt-5.6-sol" for r in advertised
            ):
                raise ValueError("Frozen semantic model unavailable")
            session.start()
            turn = session.turn(
                "No tools. Analyze only this supplied material. Return JSON in the summary string and TASK_COMPLETE.\n"
                + json.dumps(payload),
                450,
            )
            forbidden = [
                e
                for e in session.events
                if e.get("method") == "item/completed"
                and e.get("params", {}).get("item", {}).get("type")
                in {"commandExecution", "fileChange", "mcpToolCall", "webSearch"}
            ]
            if forbidden:
                raise ValueError("Semantic tool use is not allowed")
            messages = [
                x["text"]
                for x in turn.get("items", [])
                if x.get("type") == "agentMessage"
            ]
            value = json.loads(json.loads(messages[-1])["summary"])
            dump(output / "result.json", value)
            dump(
                output / "cost.json",
                {
                    "seconds": time.monotonic() - started,
                    "model_calls": 1,
                    "research_repair_executions": 0,
                },
            )
        validated = validate_relations(
            ledger, pool, [*reused, *expand_compact_relations(value, ledger, pool)]
        )
        dump(output / "relations.json", validated)
        return validated
    except Exception as exc:
        dump(
            output / "error.json",
            {"error": str(exc), "seconds": time.monotonic() - started},
        )
        raise
    finally:
        auth.unlink(missing_ok=True)


OBSERVATION_PROMPT = """Relate public requirements to checkpoint-visible observations only.
Do not solve or give repair steps. Return JSON with observation_links and unresolved.
A link has requirement_id, observation_id, requirement_quote (exact substring),
observation_quote (exact substring of output), relation (CONTRADICTS, LOCAL_SUPPORT,
CONTEXT), coverage_basis (specific public assertion/call/node/input/output mapping).
Only FUNCTIONAL_ASSERTION may CONTRADICT. Only PUBLIC_CHECK_PASS may LOCAL_SUPPORT.
Exit code alone or a file/module name does not identify tested conditions. Without
an actual identifiable coverage basis leave the requirement unresolved. Environment
errors are CONTEXT only, and only when the public requirement explicitly addresses
that environment behavior. Historical, superseded or unknown-lifecycle evidence
cannot certify current code. Preserve unrelated/conflicting evidence. No future,
reference or hidden acceptance information is available or may be inferred.
"""


def propose_observation_links(ledger, output):
    from pathlib import Path
    import time
    from .diagnostic import home_auth
    from .session import Session, dump

    output = Path(output)
    eligible = [
        o
        for o in ledger["observations"]
        if o["kind"]
        in {"FUNCTIONAL_ASSERTION", "PUBLIC_CHECK_PASS", "ENV_TOOL_FAILURE"}
    ]
    payload = {
        "prompt": OBSERVATION_PROMPT,
        "requirements": ledger["requirements"],
        "observations": eligible,
    }
    if output.exists():
        if read_json(output / "input.json")["digest"] != identity(payload):
            raise ValueError("Changed observation-link input")
        return read_json(output / "result.json")["observation_links"]
    output.mkdir(parents=True)
    dump(
        output / "input.json",
        {
            "digest": identity(payload),
            "payload": payload,
            "model": "gpt-5.6-sol",
            "effort": "medium",
        },
    )
    if not eligible:
        dump(
            output / "result.json",
            {
                "observation_links": [],
                "unresolved": "No public assertion/check observation at this prefix",
            },
        )
        dump(
            output / "cost.json",
            {"seconds": 0, "model_calls": 0, "research_repair_executions": 0},
        )
        return []
    empty = output / "empty"
    empty.mkdir()
    for reserved in (".git", ".codex", ".agents"):
        (empty / reserved).mkdir()
        (output / "scratch" / reserved).mkdir(parents=True, exist_ok=True)
    home, auth = home_auth(output)
    started = time.monotonic()
    try:
        with Session(
            empty,
            output / "scratch",
            home,
            empty,
            output / "server",
            model="gpt-5.6-sol",
            image="hermes-repair-knowledge-executor:v1",
        ) as session:
            session.start()
            turn = session.turn(
                "No tools. Return requested JSON inside summary; TASK_COMPLETE.\n"
                + json.dumps(payload),
                300,
            )
            if any(
                e.get("method") == "item/completed"
                and e.get("params", {}).get("item", {}).get("type")
                in {"commandExecution", "fileChange", "mcpToolCall", "webSearch"}
                for e in session.events
            ):
                raise ValueError("Observation linker used tools")
            messages = [
                x["text"]
                for x in turn.get("items", [])
                if x.get("type") == "agentMessage"
            ]
            value = json.loads(json.loads(messages[-1])["summary"])
            dump(output / "result.json", value)
            dump(
                output / "cost.json",
                {
                    "seconds": time.monotonic() - started,
                    "model_calls": 1,
                    "research_repair_executions": 0,
                },
            )
            return value["observation_links"]
    except Exception as exc:
        dump(
            output / "error.json",
            {"error": str(exc), "seconds": time.monotonic() - started},
        )
        raise
    finally:
        auth.unlink(missing_ok=True)


def read_json(path):
    return json.loads(path.read_text())
