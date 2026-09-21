from itertools import combinations
import pytest
from hermes_skilleval.intervention.evidence_linked_state import analyze
from hermes_skilleval.intervention.linked_composition import objective, select
from hermes_skilleval.intervention.linked_context_study import functional_label
from hermes_skilleval.intervention.repair_composer import (
    Candidate,
    CandidatePool,
    Obligation,
    render_pack,
)
from hermes_skilleval.intervention.repair_knowledge import (
    RepairKnowledgeUnit,
    SourceSpan,
)
from hermes_skilleval.intervention.source_relation import validate_relations


def fixture():
    ledger = analyze(
        "## Public requirements\n- Must preserve list entries unless empty.",
        [],
        checkpoint_event_count=0,
    )
    r = ledger["requirements"][0]
    units = []
    for i, role in enumerate(
        ["documented_contract", "existing_behavior", "public_test_example"]
    ):
        text = "Preserve list entries unless empty."
        units.append(
            RepairKnowledgeUnit(
                str(i),
                "r",
                "a" * 40,
                "paragraph",
                ("f",),
                ("unless empty",),
                text,
                None,
                (SourceSpan("a.py", "a" * 40, 1, 1, text),),
                role,
                "supported",
                (),
                f"{role}: unless empty; {text}",
            )
        )
    pool = CandidatePool(
        tuple(Candidate(u, 0.8, (0.6,), None, {}) for u in units),
        ((1.0, 0.2, 0.3), (0.2, 1.0, 0.4), (0.3, 0.4, 1.0)),
        (
            Obligation(
                r["requirement_id"], r["expected_text"], "request", r["status"], ()
            ),
        ),
        r["expected_text"],
    )
    proposals = [
        {
            "requirement_id": r["requirement_id"],
            "unit_id": u.unit_id,
            "relation": "CONTRACT_SUPPORT",
            "requirement_quote": "list entries",
            "unit_quote": "list entries",
            "applicable": True,
            "condition_basis": "unless empty",
            "rationale": "quoted same condition",
        }
        for u in units
    ]
    return ledger, pool, proposals


def test_existing_code_cannot_be_promoted_to_contract():
    ledger, pool, proposals = fixture()
    rows = validate_relations(ledger, pool, proposals)
    assert [r["weight"] for r in rows] == [1.0, 0.0, 0.0]
    proposals[0]["unit_quote"] = "not in source"
    invalid = validate_relations(ledger, pool, proposals)[0]
    assert invalid["weight"] == 0 and not invalid["provenance_valid"]


def test_topical_only_zero_and_missing_matrix_not_semantic():
    ledger, pool, proposals = fixture()
    for r in proposals:
        r["relation"] = "TOPICAL_ONLY"
    rows = validate_relations(ledger, pool, proposals)
    assert (
        select(pool, ledger, method="H-link", relations=rows, count_tokens=len).method
        == "NO_SUPPORTED_LOCAL_CONTEXT"
    )
    with pytest.raises(ValueError, match="Incomplete"):
        validate_relations(ledger, pool, proposals[:-1])


def test_shared_payload_budget_and_exact_objective_small_subsets():
    ledger, pool, proposals = fixture()
    rows = validate_relations(ledger, pool, proposals)
    before = repr(pool)
    for method in ["M-local", "H-sim", "H-link"]:
        pack = select(
            pool,
            ledger,
            method=method,
            relations=rows,
            token_budget=300,
            count_tokens=len,
        )
        assert len(render_pack(pack)) == pack.tokens <= 300
        assert all("unless empty" in u.serialized_payload for u in pack.units)
    assert repr(pool) == before
    coverage = tuple(c.coverage for c in pool.candidates)
    for n in range(4):
        for ids in combinations(range(3), n):
            actual = objective(pool, ids, ledger["weights"], coverage)["total"]
            expected = (
                (0.6 if ids else 0)
                + 0.08 * len(ids)
                - 0.10 * sum(pool.overlap[i][j] for i, j in combinations(ids, 2))
            )
            assert actual == pytest.approx(expected)


def test_new_failure_protocol_preserves_independent_failure():
    assert (
        functional_label(integrity="CONFIRMED", target="UNKNOWN", protected="FAIL")
        == "FAIL"
    )
    assert (
        functional_label(integrity="UNKNOWN", target="PASS", protected="FAIL")
        == "UNKNOWN"
    )
    assert (
        functional_label(integrity="CONFIRMED", target="PASS", protected="PASS")
        == "PASS"
    )


def test_compact_transport_never_invents_positive_or_missing_pairs():
    from hermes_skilleval.intervention.source_relation import expand_compact_relations

    ledger, pool, proposals = fixture()
    rid = ledger["requirements"][0]["requirement_id"]
    first = proposals[0]
    fields = [
        "requirement_id",
        "unit_id",
        "relation",
        "requirement_quote",
        "unit_quote",
        "applicable",
        "condition_basis",
        "rationale",
    ]
    payload = {
        "rows": [
            [first[k] for k in fields],
            [rid, "1", "TOPICAL_ONLY"],
            [rid, "2", "UNRESOLVED"],
        ]
    }
    rows = validate_relations(
        ledger, pool, expand_compact_relations(payload, ledger, pool)
    )
    assert [r["weight"] for r in rows] == [1, 0, 0]
    assert rows[1]["quote_origin"] == "complete_supplied_input_not_model_selected"
    with pytest.raises(ValueError, match="Malformed"):
        expand_compact_relations(
            {"rows": [[rid, "0", "CONTRACT_SUPPORT"]]}, ledger, pool
        )
    with pytest.raises(ValueError, match="Incomplete"):
        validate_relations(
            ledger,
            pool,
            expand_compact_relations({"rows": payload["rows"][:-1]}, ledger, pool),
        )
