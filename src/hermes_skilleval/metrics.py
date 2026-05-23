from __future__ import annotations

import math


def recall_at_k(selected: list[str], gold: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    selected_set = set(selected[:k])
    return len(selected_set & gold_set) / len(gold_set)


def precision_at_k(selected: list[str], gold: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    gold_set = set(gold)
    selected_slice = selected[:k]
    if not selected_slice:
        return 0.0
    return len(set(selected_slice) & gold_set) / k


def mean_reciprocal_rank(selected: list[str], gold: list[str]) -> float:
    gold_set = set(gold)
    for index, skill_id in enumerate(selected, start=1):
        if skill_id in gold_set:
            return 1.0 / index
    return 0.0


def ndcg_at_k(selected: list[str], gold: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    gold_set = set(gold)
    if not gold_set:
        return 0.0
    dcg = 0.0
    credited_gold: set[str] = set()
    for index, skill_id in enumerate(selected[:k], start=1):
        if skill_id in gold_set and skill_id not in credited_gold:
            credited_gold.add(skill_id)
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(gold_set), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def negative_hit_rate(selected: list[str], negative: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    negative_set = set(negative)
    if not negative_set:
        return 0.0
    return 1.0 if set(selected[:k]) & negative_set else 0.0


def accepted_count(selected: list[str]) -> int:
    return len(selected)


def coverage(selected: list[str]) -> float:
    return 1.0 if selected else 0.0


def selection_rate_at_k(selected: list[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return min(len(selected), k) / k


def abstention_rate(selected: list[str]) -> float:
    return 0.0 if selected else 1.0


def accepted_recall_at_k(selected: list[str], gold: list[str], k: int) -> float:
    return recall_at_k(selected, gold, k)


def negative_accepted_rate(selected: list[str], negative: list[str], k: int) -> float:
    return negative_hit_rate(selected, negative, k)
