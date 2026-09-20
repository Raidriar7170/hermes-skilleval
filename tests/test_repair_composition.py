"""Focused algorithm oracles; no synthetic run is a functional study result."""

from dataclasses import replace
import hashlib
from types import SimpleNamespace

import pytest

from hermes_skilleval.intervention.repair_knowledge import (
    RepairKnowledgeUnit,
    SourceSpan,
    build_units,
    render_units,
)
from hermes_skilleval.intervention.repair_composer import (
    Candidate,
    CandidatePool,
    Obligation,
    exhaustive_optimum,
    extract_obligations,
    objective,
    select_gap_cover,
    select_mmr,
)


def unit(name, text="condition: preserve values"):
    return RepairKnowledgeUnit(
        name,
        "a/b",
        "a" * 40,
        "invariant",
        ("public.symbol",),
        ("condition",),
        text,
        None,
        (SourceSpan("x.py", "a" * 40, 1, 1, text),),
        "documented_contract",
        "supported",
        (),
        text,
    )


def pool():
    units = [unit("a"), unit("b"), unit("c")]
    candidates = tuple(
        Candidate(u, 0.8, c, e, {})
        for u, c, e in zip(
            units, [(1.0, 0.0), (1.0, 0.0), (0.0, 1.0)], [1.0, None, 0.0]
        )
    )
    return CandidatePool(
        candidates,
        ((1.0, 1.0, 0.0), (1.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        (
            Obligation("g1", "first", "request:0:5", "unverified", ()),
            Obligation("g2", "second", "request:6:12", "unverified", ()),
        ),
        "query",
    )


def test_duplicate_and_complement_objective():
    p = pool()
    assert objective(p, [0, 1])["coverage"] == objective(p, [0])["coverage"]
    assert objective(p, [0, 2])["coverage"] > objective(p, [0])["coverage"]
    assert objective(p, [0, 1])["redundancy_penalty"] == 0.1
    assert objective(p, [0])["exposure_penalty"] == 0.05
    assert objective(p, [1])["exposure_penalty"] == 0
    assert p.candidates[1].exposure is None


def test_heuristic_against_exhaustive_and_atomic_budget():
    p = pool()
    h = select_gap_cover(p, count_tokens=len, token_budget=260)
    best = exhaustive_optimum(p, count_tokens=len, token_budget=260)
    assert h.scores["total"] == pytest.approx(best["objective"])
    assert h.tokens == len(render_units(h.units)) <= 260
    assert len(h.units) <= 4
    assert len({i for i in h.indices} & {0, 1}) == 1
    assert 2 in h.indices
    assert not select_gap_cover(p, count_tokens=len, token_budget=1).units


def test_ablations_change_only_named_term():
    p = pool()
    before = objective(p, [0, 2])
    gap = objective(p, [0, 2], no_gap=True)
    exposure = objective(p, [0, 2], no_exposure=True)
    for k in before:
        if k not in ("coverage", "total"):
            assert before[k] == gap[k]
        if k not in ("exposure_penalty", "total"):
            assert before[k] == exposure[k]
    assert gap["coverage"] == 0
    assert exposure["exposure_penalty"] == 0
    assert select_gap_cover(p, no_gap=True, count_tokens=len).method == "H-no-gap"
    assert (
        select_gap_cover(p, no_exposure=True, count_tokens=len).method
        == "H-no-exposure"
    )


def test_no_obligations_falls_back_to_mmr():
    p = replace(pool(), obligations=())
    h = select_gap_cover(p, count_tokens=len)
    assert h.indices == select_mmr(p, count_tokens=len).indices
    assert h.method == "H-fallback-M"


def test_obligations_are_exact_public_spans():
    s = SimpleNamespace(
        request="When empty, preserve the original value.\nMust report invalid inputs.",
        failure_text="AssertionError: input was accepted",
        public_test_failure_seen=True,
    )
    obs = extract_obligations(s)
    assert obs[0].status == "contradicted"
    for o in obs:
        field, start, end = o.source_ref.split(":")
        assert getattr(s, field)[int(start) : int(end)] == o.statement
    assert all(o.status != "locally_supported" for o in obs)


def test_source_builder_is_version_bound_and_does_not_invent_contract(tmp_path):
    text = 'def process(value):\n    if value is None:\n        raise ValueError("input value must not be empty or unspecified")\n'
    (tmp_path / "source.py").write_text(text)
    manifest = {
        "repository": "a/b",
        "revision": "a" * 40,
        "scope": "pre_repair_base",
        "files": {"source.py": hashlib.sha256(text.encode()).hexdigest()},
    }
    units = build_units(tmp_path, manifest, count_tokens=len)
    assert len(units) == 1
    assert units[0].claim_role == "existing_behavior"
    assert "if value is None:" in units[0].serialized_payload
    assert "correctness is NOT established" in units[0].serialized_payload
    with pytest.raises(ValueError, match="non-corpus"):
        build_units(tmp_path, {**manifest, "task_id": "answer"})
    with pytest.raises(ValueError, match="revision"):
        build_units(tmp_path, {**manifest, "scope": "future"})
    with pytest.raises(ValueError, match="changed"):
        build_units(tmp_path, {**manifest, "files": {"source.py": "0" * 64}})
    assert build_units(tmp_path, manifest, count_tokens=lambda _: 501) == []


def test_functional_report_ignores_cost_and_requires_two_mechanisms():
    from hermes_skilleval.intervention.repair_content_report import summarize

    arms = ["N", "G", "L", "M", "H", "H-no-gap", "H-no-exposure"]
    states = [{"task_id": str(i), "mechanism": "mechanism" + str(i)} for i in range(2)]
    cells = [
        {"task_id": s["task_id"], "arm": a, "repeat": r}
        for s in states
        for a in arms
        for r in (1, 2)
    ]
    rows = [
        {
            **c,
            "y_functional": int(c["arm"] == "M"),
            "file_policy_status": "FAIL",
            "seconds": 999,
        }
        for c in cells
    ]
    lock = {"states": states, "cells": cells}
    result = summarize(rows, lock)
    assert result["confirmation_decision"] == "TRIGGERED"  # H need not win M.
    assert result["mechanism_mean_H_minus_M"] == -1
    rows[-1]["y_functional"] = None
    assert summarize(rows, lock)["confirmation_decision"] == "UNRESOLVED"
    with pytest.raises(ValueError, match="duplicate"):
        summarize(rows + [rows[0]], lock)


def test_posthoc_rules_keep_rejection_and_preservation_separate():
    import runpy

    code = runpy.run_path("scripts/repair_knowledge_composition/legacy_posthoc.py")[
        "EXTRA"
    ]
    namespace = {"pytest": pytest}
    exec(code, namespace)
    values = ["schema", "text:000123", "index"]
    db = SimpleNamespace(conn=SimpleNamespace(iterdump=lambda: iter(values)))
    observe = namespace["_posthoc_observe"]

    def reject():
        raise ValueError("equivalent wording")

    error, preserved = observe(db, reject)
    assert isinstance(error, ValueError) and preserved
    error, preserved = observe(db, lambda: None)
    assert (
        error is None and preserved
    )  # Not rejected; preservation alone is insufficient.

    def corrupt_then_reject():
        values.pop()
        raise ValueError("equivalent wording")

    error, preserved = observe(db, corrupt_then_reject)
    assert isinstance(error, ValueError) and not preserved

    def wrong_error():
        raise RuntimeError("arbitrary failure")

    error, preserved = observe(db, wrong_error)
    assert not isinstance(error, ValueError)


def test_decoded_wrapped_requirements_are_complete_source_spans():
    import json
    import runpy

    request = runpy.run_path("scripts/repair_knowledge_composition/prepare_pro.py")[
        "public_request"
    ]
    text = request(
        {
            "problem_statement": json.dumps(
                "When running the application\nobserve failure"
            ),
            "requirements": json.dumps(
                "- The operation must preserve types\n  whenever the input contains values.\n\n- Reject invalid input."
            ),
            "interface": "",
        }
    )
    assert "\\n" not in text
    obs = extract_obligations(
        SimpleNamespace(request=text, failure_text=None, public_test_failure_seen=False)
    )
    assert (
        obs[0].statement
        == "- The operation must preserve types\n  whenever the input contains values."
    )
    for o in obs:
        _, start, end = o.source_ref.split(":")
        assert text[int(start) : int(end)] == o.statement


def test_missing_public_api_requires_exact_exception_and_collector():
    import xml.etree.ElementTree as ET
    from hermes_skilleval.intervention.repair_checks import declared_api_absence

    meta = {
        "required_api_absence": "ModuleNotFoundError: No module named 'public.required'",
        "required_api_collector": "test.required",
    }
    case = ET.fromstring(
        "<testcase name=\"test.required\"><error>E   ModuleNotFoundError: No module named 'public.required'</error></testcase>"
    )
    assert declared_api_absence(meta, [case], [case], 4)
    case.find(
        "error"
    ).text = "E   RuntimeError: ModuleNotFoundError: No module named 'public.required'"
    assert not declared_api_absence(meta, [case], [case], 4)
    case.find(
        "error"
    ).text = "E   ModuleNotFoundError: No module named 'public.required'"
    case.set("name", "unrelated")
    assert not declared_api_absence(meta, [case], [case], 4)
