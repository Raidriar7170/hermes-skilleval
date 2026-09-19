"""Fold exclusion contract; fake heads here do not count as learned evidence."""

import pytest

from hermes_skilleval.intervention import functional_wait


def test_sibling_mechanisms_are_excluded_from_all_target_models(monkeypatch):
    torch = pytest.importorskip("torch")
    family = {"a1": "a", "a2": "a", "b": "b", "c": "c"}
    rows = [{"task_id": tid, "family": f} for tid, f in family.items()]
    calls = []

    def gain(data, **kwargs):
        calls.append({r["task_id"] for r in data})
        return lambda x, k: torch.tensor([0.4]), {}

    monkeypatch.setattr(functional_wait, "fit_gain", gain)
    monkeypatch.setattr(
        functional_wait,
        "fit_wait",
        lambda data, **kw: (lambda x: torch.tensor([[0.2]]), {}),
    )
    chains = {
        tid: [
            {
                "task_id": tid,
                "family": f,
                "state_id": tid + ":" + stage,
                "stage": stage,
                "terminal_confirmed": stage == "E2",
                "x": torch.tensor([1.0]),
                "candidates": [torch.tensor([2.0])],
            }
            for stage in ("E0", "E1", "E2")
        ]
        for tid, f in family.items()
    }
    targets, provenance = functional_wait.cross_fitted_targets(rows, chains, epochs=1)
    held = next(p for p in provenance if p["excluded_family"] == "a")
    assert set(held["target_tasks"]) == {"a1", "a2"}
    assert set(held["gain_training_tasks"]) == {"b", "c"}
    assert set(held["wait_training_tasks"]) == {"b", "c"}
    for fold in held["inner_folds"]:
        assert not {"a1", "a2", fold["target_task"]} & set(fold["gain_training_tasks"])
    assert all(({"a1", "a2"} <= s) or not ({"a1", "a2"} & s) for s in calls)
    assert all(r["target"] == 0 for r in targets if r["stage"] == "E2")
    # Interrupted E1 has no observed future; never relabel it as terminal zero.
    chains["b"] = chains["b"][:2]
    targets, provenance = functional_wait.cross_fitted_targets(rows, chains, epochs=1)
    assert not any(r["state_id"] == "b:E1" for r in targets)
    assert any(
        x["state_id"] == "b:E1" for p in provenance for x in p["unknown_wait_targets"]
    )
