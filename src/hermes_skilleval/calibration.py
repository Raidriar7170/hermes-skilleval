from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_skilleval.metrics import (
    abstention_rate,
    accepted_count,
    accepted_recall_at_k,
    coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    negative_accepted_rate,
    negative_hit_rate,
    precision_at_k,
    recall_at_k,
    selection_rate_at_k,
)


@dataclass(frozen=True)
class CrossEncoderCalibration:
    score_threshold: float
    margin_threshold: float
    fit_split: str
    max_negative_hit_rate: float
    max_selection_rate_at_5: float
    fitted_task_count: int
    metrics: dict[str, float]

    def with_thresholds(
        self,
        *,
        score_threshold: float,
        margin_threshold: float,
    ) -> CrossEncoderCalibration:
        return CrossEncoderCalibration(
            score_threshold=score_threshold,
            margin_threshold=margin_threshold,
            fit_split=self.fit_split,
            max_negative_hit_rate=self.max_negative_hit_rate,
            max_selection_rate_at_5=self.max_selection_rate_at_5,
            fitted_task_count=self.fitted_task_count,
            metrics=dict(self.metrics),
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "score_threshold": self.score_threshold,
            "margin_threshold": self.margin_threshold,
            "fit_split": self.fit_split,
            "max_negative_hit_rate": self.max_negative_hit_rate,
            "max_selection_rate_at_5": self.max_selection_rate_at_5,
            "fitted_task_count": self.fitted_task_count,
            "metrics": self.metrics,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> CrossEncoderCalibration:
        metrics = data.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError("calibration metrics must be an object")
        return cls(
            score_threshold=_finite_float(data, "score_threshold"),
            margin_threshold=_finite_float(data, "margin_threshold"),
            fit_split=_string_field(data, "fit_split"),
            max_negative_hit_rate=_finite_float(data, "max_negative_hit_rate"),
            max_selection_rate_at_5=_optional_finite_float(
                data,
                "max_selection_rate_at_5",
                default=1.0,
            ),
            fitted_task_count=_positive_int(data, "fitted_task_count"),
            metrics={
                str(key): float(value)
                for key, value in metrics.items()
                if isinstance(value, int | float) and not isinstance(value, bool)
            },
        )


def fit_cross_encoder_calibration(
    records: list[dict[str, Any]],
    *,
    fit_split: str = "dev",
    max_negative_hit_rate: float = 0.05,
    max_selection_rate_at_5: float = 1.0,
    top_k: int = 5,
) -> CrossEncoderCalibration:
    if fit_split not in {"dev", "test"}:
        raise ValueError("fit_split must be 'dev' or 'test'")
    if max_negative_hit_rate < 0.0 or max_negative_hit_rate > 1.0:
        raise ValueError("max_negative_hit_rate must be between 0.0 and 1.0")
    if max_selection_rate_at_5 < 0.0 or max_selection_rate_at_5 > 1.0:
        raise ValueError("max_selection_rate_at_5 must be between 0.0 and 1.0")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    fit_records = [record for record in records if record.get("split", "dev") == fit_split]
    if not fit_records:
        raise ValueError(f"no {fit_split!r} records available for calibration")

    candidates = _candidate_thresholds(fit_records)
    best_metrics: dict[str, float] | None = None
    best_score_threshold = 0.0
    best_margin_threshold = 0.0
    for score_threshold in candidates["score"]:
        for margin_threshold in candidates["margin"]:
            metrics = _mean_metrics(
                [
                    _metrics_for_selected(
                        _calibrated_selection(
                            record,
                            score_threshold=score_threshold,
                            margin_threshold=margin_threshold,
                            top_k=top_k,
                        ),
                        record,
                        top_k=top_k,
                    )
                    for record in fit_records
                ]
            )
            if metrics["negative_hit_rate"] > max_negative_hit_rate:
                continue
            if metrics["selection_rate_at_5"] > max_selection_rate_at_5:
                continue
            if best_metrics is None or _ranking_key(metrics) > _ranking_key(best_metrics):
                best_metrics = metrics
                best_score_threshold = score_threshold
                best_margin_threshold = margin_threshold

    if best_metrics is None:
        raise ValueError(
            "could not satisfy max_negative_hit_rate with available calibration records"
        )

    return CrossEncoderCalibration(
        score_threshold=best_score_threshold,
        margin_threshold=best_margin_threshold,
        fit_split=fit_split,
        max_negative_hit_rate=max_negative_hit_rate,
        max_selection_rate_at_5=max_selection_rate_at_5,
        fitted_task_count=len(fit_records),
        metrics=best_metrics,
    )


def apply_cross_encoder_calibration(
    record: dict[str, Any],
    calibration: CrossEncoderCalibration,
    *,
    top_k: int = 5,
    router: str = "cross-encoder-calibrated",
) -> dict[str, Any]:
    selected = _calibrated_selection(
        record,
        score_threshold=calibration.score_threshold,
        margin_threshold=calibration.margin_threshold,
        top_k=top_k,
    )
    metrics = _metrics_for_selected(selected, record, top_k=top_k)
    updated = dict(record)
    updated["router"] = router
    updated["selected_skill_ids"] = selected
    updated.update(_record_metric_fields(metrics))
    return updated


def read_cross_encoder_calibration(path: Path | str) -> CrossEncoderCalibration:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"calibration file must contain an object: {path}")
    return CrossEncoderCalibration.from_json_dict(data)


def write_cross_encoder_calibration(
    calibration: CrossEncoderCalibration,
    path: Path | str,
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(calibration.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _candidate_thresholds(records: list[dict[str, Any]]) -> dict[str, list[float]]:
    score_thresholds = {0.0}
    margin_thresholds = {0.0}
    for record in records:
        selected = _selected(record)
        if not selected:
            continue
        scores = _scores(record)
        for skill_id in selected:
            if skill_id in scores:
                score = scores[skill_id]
                score_thresholds.add(score)
                score_thresholds.add(math.nextafter(score, math.inf))
        margin = _top_margin(selected, scores)
        if math.isfinite(margin):
            margin_thresholds.add(margin)
            margin_thresholds.add(math.nextafter(margin, math.inf))
    return {
        "score": sorted(score_thresholds),
        "margin": sorted(margin_thresholds),
    }


def _calibrated_selection(
    record: dict[str, Any],
    *,
    score_threshold: float,
    margin_threshold: float,
    top_k: int,
) -> list[str]:
    selected = _selected(record)[:top_k]
    if not selected:
        return []
    scores = _scores(record)
    top_score = scores.get(selected[0], -1_000_000.0)
    if top_score < score_threshold:
        return []
    if _top_margin(selected, scores) < margin_threshold:
        return []
    return [
        skill_id
        for skill_id in selected
        if scores.get(skill_id, -1_000_000.0) >= score_threshold
    ][:top_k]


def _top_margin(selected: list[str], scores: dict[str, float]) -> float:
    if not selected:
        return -math.inf
    if len(selected) == 1:
        return math.inf
    return scores.get(selected[0], -1_000_000.0) - scores.get(
        selected[1],
        -1_000_000.0,
    )


def _metrics_for_selected(
    selected: list[str],
    record: dict[str, Any],
    *,
    top_k: int,
) -> dict[str, float]:
    gold = _string_list(record, "gold_skills")
    negative = _string_list(record, "negative_skills")
    return {
        "recall_at_1": recall_at_k(selected, gold, 1),
        "recall_at_3": recall_at_k(selected, gold, 3),
        "recall_at_5": recall_at_k(selected, gold, min(5, top_k)),
        "precision_at_5": precision_at_k(selected, gold, min(5, top_k)),
        "mrr": mean_reciprocal_rank(selected, gold),
        "ndcg_at_5": ndcg_at_k(selected, gold, min(5, top_k)),
        "negative_hit_rate": negative_hit_rate(selected, negative, min(5, top_k)),
        "accepted_count": float(accepted_count(selected)),
        "coverage": coverage(selected),
        "selection_rate_at_5": selection_rate_at_k(selected, min(5, top_k)),
        "abstention_rate": abstention_rate(selected),
        "accepted_recall_at_5": accepted_recall_at_k(selected, gold, min(5, top_k)),
        "negative_accepted_rate": negative_accepted_rate(selected, negative, min(5, top_k)),
    }


def _record_metric_fields(metrics: dict[str, float]) -> dict[str, float]:
    return {
        "recall_at_1": metrics["recall_at_1"],
        "recall_at_3": metrics["recall_at_3"],
        "recall_at_5": metrics["recall_at_5"],
        "precision_at_5": metrics["precision_at_5"],
        "mrr": metrics["mrr"],
        "ndcg_at_5": metrics["ndcg_at_5"],
        "negative_hit_rate": metrics["negative_hit_rate"],
        "accepted_count": metrics["accepted_count"],
        "coverage": metrics["coverage"],
        "selection_rate_at_5": metrics["selection_rate_at_5"],
        "abstention_rate": metrics["abstention_rate"],
        "accepted_recall_at_5": metrics["accepted_recall_at_5"],
        "negative_accepted_rate": metrics["negative_accepted_rate"],
    }


def _mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: sum(row[key] for row in rows) / len(rows)
        for key in rows[0]
    }


def _ranking_key(metrics: dict[str, float]) -> tuple[float, float, float, float, float]:
    return (
        metrics["recall_at_5"],
        metrics["mrr"],
        metrics["ndcg_at_5"],
        -metrics["negative_hit_rate"],
        -metrics["selection_rate_at_5"],
    )


def _selected(record: dict[str, Any]) -> list[str]:
    return _string_list(record, "selected_skill_ids")


def _scores(record: dict[str, Any]) -> dict[str, float]:
    raw_scores = record.get("scores")
    if not isinstance(raw_scores, dict):
        raise ValueError("record scores must be an object")
    scores: dict[str, float] = {}
    for key, value in raw_scores.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("record scores must map skill ids to numeric values")
        scores[str(key)] = float(value)
    return scores


def _string_list(record: dict[str, Any], field: str) -> list[str]:
    values = record.get(field)
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"record {field} must be a list of strings")
    return list(values)


def _finite_float(data: dict[str, object], field: str) -> float:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"calibration {field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"calibration {field} must be finite")
    return result


def _optional_finite_float(
    data: dict[str, object],
    field: str,
    *,
    default: float,
) -> float:
    if field not in data:
        return default
    return _finite_float(data, field)


def _positive_int(data: dict[str, object], field: str) -> int:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"calibration {field} must be a positive integer")
    return value


def _string_field(data: dict[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"calibration {field} must be a non-empty string")
    return value
