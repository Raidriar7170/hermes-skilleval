"""Decision invariants; real delayed continuation still requires runtime evidence."""

from hermes_skilleval.intervention.functional_policy import FunctionalController


def test_positive_gain_can_be_deferred_only_by_higher_wait():
    full = FunctionalController("H-full-v2")
    myopic = FunctionalController("H-myopic-v2")
    gains = {"b": 0.2, "a": 0.1}
    action = full.decide("E1", ["b", "a"], gains, 0.3)
    assert action["action"] == "WAIT" and action["wait_sensitive"]
    assert myopic.decide("E1", ["b", "a"], gains, 0.3)["action"] == "INJECT"
    assert full.remaining_interventions == 1 and myopic.remaining_interventions == 0
    assert (
        full.decide("E2", ["b", "a"], gains, 0.9, has_future=False)["skill_id"] == "b"
    )


def test_zero_and_negative_gain_are_not_wait_evidence_and_ties_keep_opportunity():
    controller = FunctionalController("H-full-v2")
    for gains, wait in [({"b": 0.0}, 0.3), ({"b": -0.1}, 0.2), ({"b": 0.2}, 0.2)]:
        action = controller.decide("E1", ["b"], gains, wait)
        assert action["action"] == "WAIT"
        assert action["wait_sensitive"] == (gains["b"] > 0)
    assert controller.remaining_interventions == 1


def test_candidate_order_tie_and_single_use_fixed_delay():
    controller = FunctionalController("P1-v2")
    assert controller.decide("E1", ["z", "a"], {"z": 0.1, "a": 0.1})["skill_id"] == "z"
    assert controller.decide("E2", ["z"], {"z": 1})["action"] == "CONTINUE"
    delayed = FunctionalController("DEFER_SAME-v2", fixed_skill="original")
    assert delayed.decide("E2", ["other"], has_future=False)["skill_id"] == "original"
    assert delayed.remaining_interventions == 0


def test_missing_model_is_unavailable_not_a_learned_noop():
    assert (
        FunctionalController("H-task-fixedC-v2").decide("E1", ["a"])["action"]
        == "UNAVAILABLE"
    )
