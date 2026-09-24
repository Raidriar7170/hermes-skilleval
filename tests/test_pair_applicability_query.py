from copy import deepcopy
from dataclasses import replace

from test_evidence_linked_composition import fixture
from hermes_skilleval.intervention.anytime_relation_selector import ExactSelector
from hermes_skilleval.intervention.pair_applicability import (
    build_features,
    literals,
    panel,
    requests,
)
from hermes_skilleval.intervention.relation_batch_planner import CostEnvelope
from hermes_skilleval.intervention.relation_store import RelationStore
from hermes_skilleval.intervention.relation_query_study import audit_status


def test_old_order_equivalence_and_soft_scores_do_not_change_bounds(tmp_path):
    ledger, pool, rows = fixture()
    store = RelationStore(tmp_path / "s.json", ledger, pool)
    selector = ExactSelector(pool, ledger, count_tokens=len, token_budget=300)
    _, result = selector.solve(store)
    fs = build_features(ledger, pool, None)
    assert requests(selector, store, result, fs, method="A0") == selector.requests(
        store, result
    )
    before = deepcopy(store.records)
    for f in fs:
        f["z"] = 0
    fs[-1]["z"] = 1
    assert requests(selector, store, result, fs, method="R")[0] == tuple(
        fs[-1]["pair_id"]
    )
    assert store.records == before
    assert all(store.bounds(p) == (0, 1) for p in store.pairs)
    store.ingest(store.pairs, {"relations": rows})
    before = deepcopy(store.records)
    requests(selector, store, result, fs, method="V")
    assert store.records == before


def test_typed_literals_and_no_basename_or_generic_symbol_bonus():
    assert literals('0 False None [] {} ""') == {"0", "False", "None", "[]", "{}", '""'}
    ledger, pool, _ = fixture()
    req = ledger["requirements"][0]
    ledger = {
        **ledger,
        "requirements": [
            {
                **req,
                "expected_text": "error type default foo.py",
                "condition_text": "",
                "subject": ["error", "type", "default", "foo.py"],
            }
        ],
    }
    nodes = [
        {"symbol": "pkg.error", "path": "a/foo.py"},
        {"symbol": "pkg.type", "path": "b/foo.py"},
    ]
    fs = build_features(ledger, pool, None, nodes)
    assert all(f["feature_values"]["symbol"] == 0 for f in fs)


def test_same_unit_different_requirement_and_id_invariance(tmp_path):
    ledger, pool, _ = fixture()
    req = ledger["requirements"][0]
    ledger = {
        **ledger,
        "requirements": [
            {
                **req,
                "expected_text": "pkg.Real.method None",
                "condition_text": "",
                "subject": ["pkg.Real.method"],
            },
            {
                **req,
                "requirement_id": "unrelated",
                "expected_text": "rain falls",
                "condition_text": "",
                "subject": [],
            },
        ],
        "weights": {req["requirement_id"]: 0.5, "unrelated": 0.5},
    }
    pool = replace(
        pool,
        obligations=(pool.obligations[0], replace(pool.obligations[0], id="unrelated")),
        candidates=tuple(
            replace(c, unit=replace(c.unit, applies_to=("pkg.Real.method",)))
            for c in pool.candidates
        ),
    )
    fs = build_features(
        ledger, pool, None, [{"symbol": "pkg.Real.method", "path": "pkg/real.py"}]
    )
    assert fs[0]["z"] > fs[len(pool.candidates)]["z"]
    renamed = deepcopy(ledger)
    renamed["requirements"][0]["requirement_id"] = "zzz"
    fs2 = build_features(
        renamed, pool, None, [{"symbol": "pkg.Real.method", "path": "pkg/real.py"}]
    )
    assert [f["z"] for f in fs] == [f["z"] for f in fs2]


def test_affordability_censoring_and_no_success_is_unknown():
    rows = [
        {
            "lifecycle": "reuse",
            "size": 2,
            "status": "COMPLETED",
            "valid_rows": 2,
            "request_seconds": 15,
            "setup_seconds": 2,
            "payload_chars": 100,
        },
        {
            "lifecycle": "reuse",
            "size": 2,
            "status": "ERROR",
            "valid_rows": 0,
            "request_seconds": 20,
            "setup_seconds": 0,
            "payload_chars": 100,
            "censored": True,
        },
    ]
    e = CostEnvelope(rows, "reuse")
    assert e.estimate(2, 100) == 20
    assert e.choose([1, 2], lambda b: 100, 2.7) == ([], None)
    assert e.choose([1, 2], lambda b: 100, 60)[0] == [1, 2]
    assert e.estimate(8, 100) == float("inf")
    assert e.estimate(1, 100) == e.estimate(2, 100)


def test_panel_is_unique_deterministic_and_stratified():
    fs = [
        {
            "pair_id": [str(i % 4), str(i)],
            "z": i / 100,
            "symbols_and_paths": [],
            "feature_values": {"lexical": i / 100},
        }
        for i in range(100)
    ]
    a = panel(fs)
    assert a == panel(fs)
    assert len({tuple(r["pair"]) for r in a}) == 48
    assert [
        sum(r["stratum"] == s for r in a)
        for s in ["relevant", "near_distractor", "distribution_control"]
    ] == [16] * 3


def test_audit_retains_unknown_and_requires_same_role():
    q = {
        "state": "VALID_POSITIVE",
        "relation": "IMPLEMENTATION_CONTEXT",
        "applicable": True,
        "condition_atoms": ["x is None"],
        "source_condition_atoms": [],
        "requirement_quote": "x is None",
        "unit_quote": "source",
    }
    assert audit_status(q, q) == "SUPPORTED_POSITIVE"
    assert audit_status(q, {**q, "relation": "PRECONDITION"}) == "DISPUTED"
    assert audit_status(q, {"state": "NOT_ANALYZED"}) == "REVIEW_UNKNOWN"
    assert audit_status(q, None) == "REVIEW_NOT_SAMPLED"


def test_partial_rows_keep_arrival_time_separate_from_cleanup():
    import json
    from hermes_skilleval.intervention.relation_batch_planner import partial_messages

    def event(time, row):
        return {
            "method": "item/completed",
            "_observed_monotonic": time,
            "params": {
                "item": {
                    "type": "agentMessage",
                    "text": json.dumps({"summary": json.dumps({"relations": [row]})}),
                }
            },
        }

    valid, late = partial_messages([event(9, {"a": 1}), event(11, {"a": 2})], 10)
    assert valid == {"relations": [{"a": 1}]}
    assert late == {"relations": [{"a": 2}]}


def test_conflicting_condition_anchors_do_not_count_as_supported():
    q = {
        "state": "VALID_POSITIVE",
        "relation": "PRECONDITION",
        "applicable": True,
        "condition_atoms": ["x is None"],
        "source_condition_atoms": [],
        "requirement_quote": "x is None",
    }
    j = {**q, "condition_atoms": ["x is False"], "requirement_quote": "x is False"}
    assert audit_status(q, j) == "REVIEW_UNKNOWN"


def test_actual_input_drift_is_rejected(tmp_path):
    import json
    import pytest
    from hermes_skilleval.intervention.relation_query_study import sha, verify_inputs

    d = tmp_path / "inputs" / "s"
    d.mkdir(parents=True)
    f = d / "features.json"
    f.write_text("{}")
    (tmp_path / "inputs.json").write_text(
        json.dumps({"states": [{"name": "s", "files": {"features.json": sha(f)}}]})
    )
    verify_inputs(tmp_path)
    f.write_text('{"z":1}')
    with pytest.raises(ValueError, match="drift"):
        verify_inputs(tmp_path)


def test_initial_optimistic_coverage_is_constant_for_nonempty_packages(tmp_path):
    from hermes_skilleval.intervention.linked_composition import objective

    ledger, pool, _ = fixture()
    solver = ExactSelector(pool, ledger, count_tokens=len, token_budget=300)
    upper = [[1.0 for _ in pool.obligations] for _ in pool.candidates]
    assert {
        objective(pool, ids, ledger["weights"], upper)["coverage"]
        for ids in solver.feasible
        if ids
    } == {sum(ledger["weights"].values())}


def test_reused_process_always_starts_empty_thread(monkeypatch, tmp_path):
    import json
    import time
    from hermes_skilleval.intervention.relation_batch_planner import RelationTransport

    ledger, pool, rows = fixture()

    class Fake:
        def __init__(self):
            self.events = []
            self.i = 0
            self.active = False

        def start(self):
            self.i += 1
            self.thread_id = str(self.i)
            return {"thread": {"id": self.thread_id, "turns": []}}

        def turn(self, *args):
            return {
                "items": [
                    {
                        "type": "agentMessage",
                        "text": json.dumps(
                            {"summary": json.dumps({"relations": rows[:1]})}
                        ),
                    }
                ]
            }

        def cancel(self):
            return "NO_KNOWN_ACTIVE_TURN"

        def close(self):
            pass

    opened = []

    def fake_open(self, *args):
        self.session = Fake()
        opened.append(self.session)
        return {}

    monkeypatch.setattr(RelationTransport, "open", fake_open)
    tx = RelationTransport(tmp_path / "tx", deadline=time.monotonic() + 60)
    for i in range(2):
        _, cost = tx.call(
            ledger,
            pool,
            [(rows[0]["requirement_id"], rows[0]["unit_id"])],
            tmp_path / f"call-{i}",
        )
        assert cost["fresh_thread"] and not cost["late"]
    tx.close()
    assert len(opened) == 1 and tx.thread_ids == ["1", "2"]


def test_metrics_count_unique_yield_but_all_attempt_positions(tmp_path):
    from hermes_skilleval.intervention.relation_query_study import metrics

    ledger, pool, rows = fixture()
    s = RelationStore(tmp_path / "s", ledger, pool)
    s.ingest(s.pairs[:1], {"relations": [{**rows[0], "relation": "TOPICAL_ONLY"}]})
    p = s.pairs[0]
    m = metrics(ledger, s, [p, p], {p: s.records[p]})
    assert m["request_positions"] == 2 and m["unique_requested"] == 1
    assert m["audit_counts"]["CORROBORATED_ZERO"] == 1


def test_failed_solver_retains_last_paid_batch_and_valid_row_count(
    monkeypatch, tmp_path
):
    from hermes_skilleval.intervention import relation_query_study as study
    from hermes_skilleval.intervention.relation_store import atomic_json

    ledger, pool, rows = fixture()
    fs = build_features(ledger, pool, None)
    monkeypatch.setattr(study, "state", lambda *a: (ledger, pool, fs, []))
    atomic_json(
        tmp_path / "cost-model.json",
        {
            "lifecycle": "reuse",
            "observations": [
                {
                    "lifecycle": "reuse",
                    "size": 2,
                    "status": "COMPLETED",
                    "valid_rows": 2,
                    "request_seconds": 1,
                    "setup_seconds": 0,
                    "payload_chars": 100000,
                }
            ],
        },
    )

    class Solver(ExactSelector):
        def __init__(self, pool, ledger, **kwargs):
            super().__init__(pool, ledger, count_tokens=len, token_budget=300)
            self.calls = 0

        def solve(self, *args, **kwargs):
            self.calls += 1
            if self.calls > 1:
                raise TimeoutError("synthetic solver deadline")
            return super().solve(*args, **kwargs)

    class Transport:
        def __init__(self, *args, **kwargs):
            self.session = None

        def call(self, ledger, pool, batch, *args, **kwargs):
            valid = {
                **rows[0],
                "requirement_id": batch[0][0],
                "unit_id": batch[0][1],
                "relation": "TOPICAL_ONLY",
            }
            return {"relations": [valid, valid, {"malformed": True}]}, {
                "status": "COMPLETED",
                "seconds": 1,
                "request_seconds": 1,
                "setup_seconds": 0,
                "size": len(batch),
                "payload_chars": 100000,
                "lifecycle": "reuse",
                "late": False,
            }

        def close(self):
            pass

    monkeypatch.setattr(study, "ExactSelector", Solver)
    monkeypatch.setattr(study, "RelationTransport", Transport)
    final = study.run_policy(tmp_path, "s", "A0", tmp_path / "run")
    assert final["stop_reason"] == "SOLVER_DEADLINE"
    event = study.read(tmp_path / "run/trajectory.json")[0]
    assert event["cost"]["raw_rows"] == 3
    assert event["cost"]["valid_rows"] == 1
    assert event["update_status"] == "SOLVER_DEADLINE_LOCKED_PREVIOUS_PACK"
    assert len(event["requested"]) == 2


def test_reference_empty_connection_error_stops_without_busy_loop(
    monkeypatch, tmp_path
):
    from hermes_skilleval.intervention import relation_query_study as study

    ledger, pool, _ = fixture()
    pair = [
        ledger["requirements"][0]["requirement_id"],
        pool.candidates[0].unit.unit_id,
    ]
    monkeypatch.setattr(study, "DEV", ["s"])
    monkeypatch.setattr(study, "verify_inputs", lambda *a: None)
    monkeypatch.setattr(study, "state", lambda *a: (ledger, pool, [], [{"pair": pair}]))
    calls = []

    class Transport:
        def __init__(self, root, **kwargs):
            self.root = root
            root.mkdir(parents=True)

        def call(self, *args, **kwargs):
            calls.append(1)
            return {"relations": []}, {
                "status": "ERROR",
                "error": "RuntimeError: unavailable",
            }

        def close(self):
            study.atomic_json(self.root / "sequence.json", {"seconds": 1})

    monkeypatch.setattr(study, "RelationTransport", Transport)
    study.reference(tmp_path, "development")
    assert len(calls) == 2  # one bounded attempt per Q/J role, not an empty-dict spin
    study.reference(tmp_path, "development")
    assert (
        len(calls) == 4
    )  # PARTIAL can continue, preserving original pending and costs


def test_os_replay_worker_cannot_read_qj_and_keeps_outside_unknown(tmp_path):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import pytest
    from dataclasses import asdict
    from hermes_skilleval.intervention.relation_store import atomic_json

    if sys.platform != "darwin":
        pytest.skip("This study uses measured macOS sandbox-exec isolation")
    ledger, pool, rows = fixture()
    root = tmp_path / "study"
    d = root / "inputs" / "s"
    fs = build_features(ledger, pool, None)
    atomic_json(d / "ledger.json", ledger)
    atomic_json(d / "pool.json", asdict(pool))
    atomic_json(d / "features.json", fs)
    pair = fs[0]["pair_id"]
    atomic_json(d / "panel.json", [{"pair": pair, "stratum": "distribution_control"}])
    atomic_json(
        root / "cost-model.json",
        {
            "lifecycle": "reuse",
            "observations": [
                {
                    "lifecycle": "reuse",
                    "size": 2,
                    "status": "COMPLETED",
                    "valid_rows": 2,
                    "request_seconds": 1,
                    "setup_seconds": 0,
                    "payload_chars": 100000,
                }
            ],
        },
    )
    for role in ("Q", "J"):
        atomic_json(
            root / "reference" / "s" / role / "store.json", {"SECRET_UNREVEALED": True}
        )
    profile = (
        "(version 1)(allow default)(deny file-read* (subpath "
        + json.dumps(str(root / "reference"))
        + "))"
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    proc = subprocess.Popen(
        [
            "/usr/bin/sandbox-exec",
            "-p",
            profile,
            sys.executable,
            "-m",
            "hermes_skilleval.intervention.relation_query_worker",
            str(root),
            "s",
            "R",
            str(root / "out"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        line = proc.stdout.readline()
        assert json.loads(line)["requested"] == [pair]
        proc.stdin.write(json.dumps({"relations": [rows[0]]}) + "\n")
        proc.stdin.flush()
        stdout, stderr = proc.communicate(timeout=20)
        assert proc.returncode == 0, stderr
        data = json.loads((root / "out/store.json").read_text())
        assert sum(r["record"]["state"] == "NOT_ANALYZED" for r in data["records"]) == 2
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_connection_failure_streak_resets_on_success_or_different_type():
    from hermes_skilleval.intervention.relation_query_study import connection_streak

    kind, count = connection_streak(None, 0, "ERROR", "RuntimeError: exit")
    assert count == 1
    kind, count = connection_streak(kind, count, "COMPLETED", "")
    kind, count = connection_streak(kind, count, "ERROR", "RuntimeError: exit")
    assert count == 1
    kind, count = connection_streak(kind, count, "ERROR", "BrokenPipeError: pipe")
    assert count == 1
    kind, count = connection_streak(kind, count, "ERROR", "BrokenPipeError: pipe")
    assert count == 2


def test_singleton_only_when_one_pending_pair():
    e = CostEnvelope(
        [
            dict(
                lifecycle="reuse",
                size=2,
                status="COMPLETED",
                valid_rows=2,
                request_seconds=10,
                payload_chars=100,
            )
        ],
        "reuse",
    )
    # One item fits the length-scaled envelope; two do not. Affordability
    # must not silently permit an unmeasured singleton while two remain.
    assert e.choose([1, 2], lambda b: 100 * len(b), 20) == ([], None)
    assert e.choose([1], lambda b: 100 * len(b), 20)[0] == [1]


def test_pair_cap_truncation_does_not_authorize_singleton():
    e = CostEnvelope(
        [
            dict(
                lifecycle="reuse",
                size=2,
                status="COMPLETED",
                valid_rows=2,
                request_seconds=10,
                payload_chars=100,
            )
        ],
        "reuse",
    )
    # At 47/48 unique queries ranked can have one item while the domain has many.
    assert e.choose([1], lambda b: 100, 60, pending_count=97) == ([], None)
