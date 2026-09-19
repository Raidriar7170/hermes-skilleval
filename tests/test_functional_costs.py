import pytest

from hermes_skilleval.intervention.functional_costs import cost_ledger


def test_reused_prefix_is_not_recharged_and_missing_usage_is_unknown():
    row = {
        "run": "/tmp/native",
        "execution": {
            "tail_seconds": 10,
            "prefix_seconds": 200,
            "controller_overhead_seconds": {"state": 1, "decision": 2},
        },
    }
    tail = {"run": "/tmp/tail", "execution": {"tail_seconds": 3, "prefix_seconds": 200}}
    reads = []

    def usage(path):
        reads.append(path.name)
        return {
            "tokens": {"inputTokens": 100, "cachedInputTokens": 80}
            if path.name == "native"
            else None
        }

    ledger = cost_ledger(
        {"collection": [row, row], "mechanism_probes": [row, tail]}, usage_reader=usage
    )
    assert reads == ["native", "tail"]
    assert ledger["unique_executions"] == 2
    assert ledger["groups"]["collection"]["active_seconds"]["observed_sum"] == 10
    overhead = ledger["groups"]["collection"]["online_decision_budget_charges"][
        "controller_overhead_seconds"
    ]
    assert overhead["decision"] == {"observed_sum": 2, "known": 1, "unknown": 0}
    assert overhead["checkpoint"]["unknown"] == 1
    probe = ledger["groups"]["mechanism_probes"]
    assert probe["active_seconds"]["observed_sum"] == 3
    assert probe["tokens"]["inputTokens"] == {
        "observed_sum": 0,
        "known": 0,
        "unknown": 1,
    }
    assert probe["reused_execution_references_excluded"] == 1
    assert ledger["billing_usd"] is None
    with pytest.raises(ValueError, match="conflicting cost evidence"):
        cost_ledger(
            {"collection": [row, {**row, "execution": {"tail_seconds": 11}}]},
            usage_reader=usage,
        )
