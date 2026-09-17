import json
import pytest
from hermes_skilleval.repo_routing.calibration import (
    fit,
    predict,
    calibrate,
    binary_rows,
)
from hermes_skilleval.repo_routing.support import ordinal_relevance


def rows():
    return [
        dict(
            family=f,
            label=label,
            raw_support_score=z,
            visible=True,
            context={"state": "usable"},
        )
        for f in ("a", "b", "c", "d")
        for label, z in [
            ("SUPPORTED", 2.0),
            ("NOT_APPLICABLE", -2.0),
            ("UNKNOWN", 100.0),
        ]
    ]


def test_real_fit_reload_unknown_and_identity():
    model = fit(rows(), "version-a")
    assert model["known_rows"] == 8
    assert model["unknown_rows"] == 4
    assert model["trajectory"][-1]["loss"] < model["trajectory"][0]["loss"]
    reloaded = json.loads(json.dumps(model))
    assert predict(reloaded, 2.0, "version-a") == predict(model, 2.0, "version-a")
    assert predict(model, 2.0, "version-a") > 0.8
    with pytest.raises(ValueError, match="identity"):
        predict(model, 2.0, "version-b")
    with pytest.raises(ValueError, match="both known"):
        fit([rows()[0]], "x")


def test_family_weights_and_calibration_operating_point():
    data = (
        rows()
        + [
            dict(
                family="a",
                label="SUPPORTED",
                raw_support_score=2.0,
                visible=True,
                context={"state": "usable"},
            )
        ]
        * 20
    )
    weighted = binary_rows(data)
    assert sum(r["weight"] for r in weighted if r["family"] == "a") == pytest.approx(
        0.25
    )
    model = calibrate(rows(), "v")
    assert model["threshold"] is not None
    refused = calibrate([{**r, "visible": False} for r in rows()], "v")
    assert refused["status"] == "NO_VALID_OPERATING_POINT"


def test_rank_translation_is_not_support_calibration():
    candidates = [{"id": "a"}, {"id": "b"}]
    assert ordinal_relevance(candidates, [-3.0, -4.0]) == ordinal_relevance(
        candidates, [97.0, 96.0]
    )
    model = fit(rows(), "v")
    # Independent calibrated support uses its own z, not either rank value.
    assert predict(model, 2.0, "v") != predict(model, -2.0, "v")


def test_partial_inputs_cannot_create_an_operating_point():
    model = calibrate([{**r, "context": {"state": "partial"}} for r in rows()], "v")
    assert model["threshold"] is None
    assert model["status"] == "NO_VALID_OPERATING_POINT"
