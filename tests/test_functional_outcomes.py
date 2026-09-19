from copy import deepcopy
import json
from pathlib import Path

import pytest

from hermes_skilleval.intervention.functional_outcomes import (
    load_objective,
    outcomes,
    paired_delta,
    transition,
    decompose,
)
from hermes_skilleval.intervention.study import qualify_quality

LOCK = Path(__file__).parents[1] / "configs/functional-gain-v2/objective-lock.json"


def sample(target=True, regression=True, policy=True):
    execution = dict(status="COMPLETED", thread_id="sample", injected=False)
    checks = {
        k: dict(valid=v is not None, passed=v)
        for k, v in [("target", target), ("regression", regression), ("policy", policy)]
    }
    return execution, checks


@pytest.mark.parametrize(
    "target,regression,policy,functional,qualified",
    [
        (True, True, True, 1, 1),
        (True, True, False, 1, 0),
        (False, True, True, 0, 0),
        (True, False, True, 0, 0),
        (None, True, True, None, None),
    ],
)
def test_truth_table(target, regression, policy, functional, qualified):
    e, c = sample(target, regression, policy)
    r = outcomes(e, c, integrity="VERIFIED")
    assert r["y_functional"] == functional
    assert r["qualified_delivery"] == qualified
    if policy is False:
        assert qualify_quality(e, c) is False


def test_policy_cost_invariance_and_real_rescue_damage():
    e, c = sample()
    base = outcomes(e, c, integrity="VERIFIED")
    c["policy"]["passed"] = False
    e.update(tail_seconds=599, payload_tokens=1200, input_tokens=1000000)
    changed = outcomes(e, c, integrity="VERIFIED")
    assert paired_delta(base, changed) == 0
    assert transition(base, changed) == "tie_pass"
    c["target"]["passed"] = False
    failure = outcomes(e, c, integrity="VERIFIED")
    assert transition(failure, base) == "functional_rescue"
    assert transition(base, failure) == "functional_damage"
    assert paired_delta(failure, base) == 1


def test_unknown_not_zero_and_integrity_not_policy():
    e, c = sample()
    good = outcomes(e, c, integrity="VERIFIED")
    for integrity in ["UNKNOWN", "JUDGE_TAMPERING", "ISOLATION_FAILURE"]:
        unknown = outcomes(e, c, integrity=integrity)
        assert unknown["y_functional"] is None
        assert paired_delta(good, unknown) is None
    e["status"] = "TIMEOUT"
    assert outcomes(e, c, integrity="VERIFIED")["y_functional"] == 1
    e.update(injected=True, model_input_observed=False)
    assert outcomes(e, c, integrity="VERIFIED")["y_functional"] is None


def test_objective_rejects_drift(tmp_path):
    lock = load_objective(LOCK)
    for key in [
        "cost_in_gain_or_wait_training",
        "policy_in_gain_or_wait_training",
        "representation_ablation_retrieves_again",
    ]:
        mutated = deepcopy(lock)
        mutated[key] = True
        p = tmp_path / "lock.json"
        p.write_text(json.dumps(mutated))
        with pytest.raises(ValueError, match="objective drift"):
            load_objective(p)


def test_g0_cannot_read_final_rows(tmp_path):
    p = tmp_path / "records.json"
    p.write_text(json.dumps({"rows": [{"split": "test"}]}))
    with pytest.raises(ValueError, match="train/dev"):
        decompose(p, LOCK, tmp_path / "out")
