import json
from pathlib import Path


PHASE7B_ROOT = Path("docs/demo/phase7b-cross-encoder-calibration")


def test_phase7b_artifacts_preserve_heldout_metrics():
    expected_metrics = {
        "cross-encoder-calibrated-strict-test/results.jsonl": {
            "records": 30,
            "recall_at_5": 0.950,
            "negative_hit_rate": 0.033,
        },
        "cross-encoder-calibrated-balanced-test/results.jsonl": {
            "records": 30,
            "recall_at_5": 0.967,
            "negative_hit_rate": 0.100,
        },
        "cross-encoder-rank-only-test/results.jsonl": {
            "records": 30,
            "recall_at_5": 1.000,
            "negative_hit_rate": 0.333,
        },
        "gated-minilm-contrastive-test/results.jsonl": {
            "records": 30,
            "recall_at_5": 0.950,
            "negative_hit_rate": 0.100,
        },
    }

    for relative_path, expected in expected_metrics.items():
        records = _read_jsonl(PHASE7B_ROOT / relative_path)

        assert len(records) == expected["records"]
        assert _mean(records, "recall_at_5") == expected["recall_at_5"]
        assert _mean(records, "negative_hit_rate") == expected["negative_hit_rate"]

    strict = _read_json(PHASE7B_ROOT / "strict-calibration.json")
    balanced = _read_json(PHASE7B_ROOT / "balanced-calibration.json")
    assert strict["fit_split"] == "dev"
    assert strict["fitted_task_count"] == 50
    assert round(strict["score_threshold"], 6) == -3.992446
    assert balanced["fit_split"] == "dev"
    assert balanced["fitted_task_count"] == 50
    assert round(balanced["score_threshold"], 6) == -4.895247
    assert (PHASE7B_ROOT / "comparison.md").exists()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _mean(records: list[dict[str, object]], metric: str) -> float:
    values: list[float] = []
    for record in records:
        value = record[metric]
        assert isinstance(value, int | float)
        values.append(float(value))
    return round(sum(values) / len(values), 3)
