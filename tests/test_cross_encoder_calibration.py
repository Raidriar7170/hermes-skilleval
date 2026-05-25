import json

from hermes_skilleval.calibration import (
    apply_cross_encoder_calibration,
    fit_cross_encoder_calibration,
)


def test_fit_cross_encoder_calibration_uses_dev_split_and_controls_negatives():
    records = [
        _record(
            "dev-clear-positive",
            split="dev",
            selected=["gold-clear", "other-clear"],
            scores={"gold-clear": 5.0, "other-clear": 1.0},
            gold=["gold-clear"],
            negative=["bad-clear"],
        ),
        _record(
            "dev-ambiguous-negative",
            split="dev",
            selected=["bad-ambiguous", "other-ambiguous"],
            scores={"bad-ambiguous": 4.5, "other-ambiguous": 4.3},
            gold=["missing-gold"],
            negative=["bad-ambiguous"],
        ),
        _record(
            "dev-margin-positive",
            split="dev",
            selected=["gold-margin", "other-margin"],
            scores={"gold-margin": 3.5, "other-margin": 0.5},
            gold=["gold-margin"],
            negative=["bad-margin"],
        ),
        _record(
            "test-negative-must-not-fit",
            split="test",
            selected=["bad-test", "other-test"],
            scores={"bad-test": 100.0, "other-test": 0.0},
            gold=["missing-test"],
            negative=["bad-test"],
        ),
    ]

    calibration = fit_cross_encoder_calibration(
        records,
        fit_split="dev",
        max_negative_hit_rate=0.0,
        top_k=5,
    )

    assert calibration.fitted_task_count == 3
    assert calibration.metrics["negative_hit_rate"] == 0.0
    assert calibration.metrics["recall_at_5"] == 2 / 3
    assert calibration.margin_threshold > 0.2


def test_apply_cross_encoder_calibration_filters_by_score_and_margin():
    calibration = fit_cross_encoder_calibration(
        [
            _record(
                "dev",
                split="dev",
                selected=["gold", "other"],
                scores={"gold": 5.0, "other": 1.0},
                gold=["gold"],
                negative=[],
            )
        ],
        fit_split="dev",
        max_negative_hit_rate=0.0,
        top_k=5,
    )
    calibration = calibration.with_thresholds(
        score_threshold=3.0,
        margin_threshold=1.0,
    )

    accepted = apply_cross_encoder_calibration(
        _record(
            "accepted",
            split="test",
            selected=["gold", "other"],
            scores={"gold": 5.0, "other": 2.0},
            gold=["gold"],
            negative=["bad"],
        ),
        calibration,
        top_k=5,
        router="cross-encoder-calibrated",
    )
    ambiguous = apply_cross_encoder_calibration(
        _record(
            "ambiguous",
            split="test",
            selected=["gold", "other"],
            scores={"gold": 5.0, "other": 4.5},
            gold=["gold"],
            negative=["bad"],
        ),
        calibration,
        top_k=5,
        router="cross-encoder-calibrated",
    )

    assert accepted["router"] == "cross-encoder-calibrated"
    assert accepted["selected_skill_ids"] == ["gold"]
    assert accepted["recall_at_5"] == 1.0
    assert accepted["selection_rate_at_5"] == 0.2
    assert ambiguous["selected_skill_ids"] == []
    assert ambiguous["abstention_rate"] == 1.0


def test_fit_cross_encoder_calibration_can_cap_selection_rate():
    records = [
        _record(
            "dev-many",
            split="dev",
            selected=["gold", "other-a", "other-b"],
            scores={"gold": 5.0, "other-a": 2.0, "other-b": 1.0},
            gold=["gold"],
            negative=[],
        ),
        _record(
            "dev-negative",
            split="dev",
            selected=["bad", "other"],
            scores={"bad": 4.0, "other": 3.9},
            gold=["missing"],
            negative=["bad"],
        ),
    ]

    calibration = fit_cross_encoder_calibration(
        records,
        fit_split="dev",
        max_negative_hit_rate=0.0,
        max_selection_rate_at_5=0.2,
        top_k=5,
    )

    assert calibration.metrics["selection_rate_at_5"] <= 0.2
    assert calibration.metrics["negative_hit_rate"] == 0.0


def test_cross_encoder_calibration_round_trips_json(tmp_path):
    calibration = fit_cross_encoder_calibration(
        [
            _record(
                "dev",
                split="dev",
                selected=["gold", "other"],
                scores={"gold": 4.0, "other": 1.0},
                gold=["gold"],
                negative=[],
            )
        ],
        fit_split="dev",
        max_negative_hit_rate=0.0,
        top_k=5,
    )
    path = tmp_path / "calibration.json"

    path.write_text(json.dumps(calibration.to_json_dict()), encoding="utf-8")
    loaded = type(calibration).from_json_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )

    assert loaded == calibration


def _record(task_id, *, split, selected, scores, gold, negative):
    return {
        "task_id": task_id,
        "category": "coding",
        "difficulty": "medium",
        "split": split,
        "robustness_tags": [],
        "router": "cross-encoder-rank-only",
        "selected_skill_ids": selected,
        "scores": scores,
        "gold_skills": gold,
        "negative_skills": negative,
        "latency_ms": 1.0,
    }
