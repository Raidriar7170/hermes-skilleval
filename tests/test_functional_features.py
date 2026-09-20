"""Synthetic contract fixtures are not runtime or training evidence."""

import hashlib

from hermes_skilleval.intervention.functional_features import (
    feature_tables,
    task_weighted_prior,
    prior_predict,
)
from hermes_skilleval.intervention.state import observe


class RecordingEncoder:
    def features(self, state, *, no_state=False):
        return (
            state.request,
            state.stage,
            state.remaining_seconds,
            None if no_state else state.failure_text,
        )

    def encode(self, text):
        return text


def test_actual_payload_and_candidate_order_shared_by_representations():
    state = observe(
        request="repair",
        repo_facts="repo",
        stage="E1",
        turn_index=2,
        remaining=300,
        total=600,
        events=[],
    ).to_dict()
    state["failure_text"] = "visible failure"
    payloads = [
        {"id": "b", "payload": "bounded b"},
        {"id": "a", "payload": "bounded a"},
    ]
    for payload in payloads:
        payload["payload_sha256"] = hashlib.sha256(
            payload["payload"].encode()
        ).hexdigest()
    common = {
        "task_id": "t",
        "state_id": "t:E1",
        "repeat": 1,
        "split": "train",
        "family": "f",
        "stage": "E1",
        "state": state,
        "binding_sha256": "same",
        "candidates": ["b", "a"],
        "candidate_payloads": payloads,
        "native_terminal_status": "EXECUTOR_ERROR",
    }
    records = [
        {**common, "action": a, "y_functional": y}
        for a, y in [("NO_INTERVENTION", 0), ("b", 1), ("a", 0)]
    ]
    full, full_chains, _ = feature_tables(records, RecordingEncoder(), split="train")
    static, static_chains, _ = feature_tables(
        records, RecordingEncoder(), split="train", no_state=True
    )
    assert (
        [r["k"] for r in full] == [r["k"] for r in static] == ["bounded b", "bounded a"]
    )
    assert full[0]["x"] != static[0]["x"]
    assert (
        full_chains["t"][0]["candidate_ids"]
        == static_chains["t"][0]["candidate_ids"]
        == ["b", "a"]
    )
    assert not full_chains["t"][-1]["terminal_confirmed"]
    assert [r["delta"] for r in full] == [1, 0]


def test_prior_does_not_overweight_tasks_with_more_observations():
    rows = [
        {"task_id": t, "action": "a", "stage": "E1", "delta": y}
        for t, y in [("one", 1), ("one", 1), ("two", -1)]
    ]
    prior = task_weighted_prior(rows)
    assert prior_predict(prior, "a", "E1") == 0
    assert prior_predict(prior, "unseen", "E0") == 0
