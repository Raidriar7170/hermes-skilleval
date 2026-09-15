"""Fixed-candidate, fixed-K set policies over real SkillRouter snapshots."""

from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import time
from hermes_skilleval.skill_features import features, relation


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class SelectionConfig:
    alpha: float = 0.25
    beta: float = 1.0
    redundancy_penalty: float = 0.15
    minimum_gain: float = 0.05
    max_rank: int = 10
    features_enabled: bool = True

    def __post_init__(self):
        for field in ("alpha", "beta", "redundancy_penalty", "minimum_gain"):
            value = getattr(self, field)
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("invalid selection coefficient: " + field)
        if not isinstance(self.max_rank, int) or self.max_rank < 2:
            raise ValueError("max_rank must be >=2")
        if not isinstance(self.features_enabled, bool):
            raise ValueError("features_enabled must be boolean")


def select(
    *,
    prompt: str,
    snapshot: dict,
    registry: dict,
    policy: str = "topk",
    k: int = 2,
    config: SelectionConfig | None = None,
) -> dict:
    start = time.perf_counter()
    config = config or SelectionConfig()
    if (
        policy not in ("topk", "dedup", "complementary")
        or not isinstance(k, int)
        or k < 0
    ):
        raise ValueError("invalid policy/K")
    if not isinstance(prompt, str):
        raise TypeError("public prompt string required")
    if snapshot.get("actual_router") != "skillrouter-open" or not snapshot.get(
        "model_identity"
    ):
        raise ValueError("real SkillRouter snapshot required")
    if (
        snapshot.get("registry_id") != registry["registry_id"]
        or digest_registry(registry) != registry["registry_id"]
    ):
        raise ValueError("registry binding mismatch")
    if snapshot.get("input_prompt_hash") != hashlib.sha256(prompt.encode()).hexdigest():
        raise ValueError("public prompt binding mismatch")
    profile = snapshot["model_identity"]["profile"]
    if snapshot.get("bound_model_identity") != digest(snapshot["model_identity"]):
        raise ValueError("model identity binding mismatch")
    ids = snapshot["reranked_ids"]
    retrieval_ids = [r["id"] for r in snapshot["retrieval"]]
    rows = {s["id"]: s for s in registry["skills"]}
    if (
        len(rows) != len(registry["skills"])
        or len(ids) != len(set(ids))
        or set(ids) != set(retrieval_ids)
        or len(retrieval_ids) != len(set(retrieval_ids))
        or not set(ids) <= rows.keys()
    ):
        raise ValueError("invalid candidate IDs")
    if set(snapshot["scores"]) != set(ids) or any(
        not math.isfinite(snapshot["scores"][sid]) for sid in ids
    ):
        raise ValueError("invalid candidate scores")
    if any(not math.isfinite(row["score"]) for row in snapshot["retrieval"]):
        raise ValueError("invalid retrieval scores")
    if ids != sorted(ids, key=lambda sid: -snapshot["scores"][sid]):
        raise ValueError("reranker rank/score mismatch")
    snapshot_id = digest(
        {
            key: snapshot[key]
            for key in (
                "model_identity",
                "registry_id",
                "input_prompt_hash",
                "retrieval",
                "reranked_ids",
                "scores",
                "index_key",
                "reranker_inputs",
                "query_input",
            )
        }
    )
    feature_start = time.perf_counter()
    # Respect actual token truncation as well as configured character prefixes.
    visible = {r["skill_id"]: r for r in snapshot["reranker_inputs"]}
    if set(visible) != set(ids):
        raise ValueError("candidate input visibility missing")
    projected = []
    for sid in ids:
        row = dict(rows[sid])
        record = visible[sid]
        body = (row.get("body") or "")[: profile.get("reranker_body_max", 2000)]
        desc = (row.get("description") or "")[: profile.get("desc_max", 500)]
        end = max((b for a, b in record["visible_char_spans"]), default=0)
        body_start = record["formatted_chars"] - len(body)
        desc_start = body_start - 3 - len(desc)
        row["body"] = body[: max(0, end - body_start)]
        row["description"] = desc[: max(0, end - desc_start)]
        projected.append(row)
    feat = features(
        prompt,
        projected,
        body_max=profile.get("reranker_body_max", 2000),
        desc_max=profile.get("desc_max", 500),
        enabled=config.features_enabled and policy != "topk",
    )
    feat["input_scope"]["actual_reranker_token_visibility"] = True
    feature_seconds = time.perf_counter() - feature_start
    count = min(k, len(ids))
    chosen = ids[:count]
    fallback = None
    reasons = []
    skipped = []
    relations = {}

    def rel(a, b):
        key = a + "|" + b
        if key not in relations:
            relations[key] = relation(
                rows[a], rows[b], feat["supports"][a], feat["supports"][b]
            )
        return relations[key]

    if policy != "topk" and count > 1:
        chosen = ids[:1]
        while len(chosen) < count:
            remaining = [sid for sid in ids if sid not in chosen]
            original = remaining[0]
            independent = [
                sid
                for sid in remaining
                if all(rel(sid, s)["kind"] != "OPERATION_SUBSTITUTE" for s in chosen)
            ]
            # D only replaces a proved interchangeable item with independently supported relevance.
            dedup = original
            if any(rel(original, s)["kind"] == "OPERATION_SUBSTITUTE" for s in chosen):
                eligible = [
                    sid
                    for sid in independent
                    if ids.index(sid) < config.max_rank
                    and any(e["support"] > 0 for e in feat["supports"][sid])
                ]
                if eligible:
                    dedup = eligible[0]
                else:
                    fallback = "redundancy_unavoidable"
            candidate = dedup
            if policy == "complementary" and feat["requirements"]:
                covered = [
                    max(feat["supports"][sid][j]["support"] for sid in chosen)
                    for j in range(len(feat["requirements"]))
                ]
                ranked = []
                for sid in remaining:
                    evidence = feat["supports"][sid]
                    gain = sum(
                        max(0, e["support"] - covered[j])
                        for j, e in enumerate(evidence)
                    ) / len(covered)
                    overlap = sum(
                        min(e["support"], covered[j]) for j, e in enumerate(evidence)
                    ) / len(covered)
                    relevance = 1 - ids.index(sid) / max(1, len(ids) - 1)
                    objective = (
                        config.alpha * relevance
                        + config.beta * gain
                        - config.redundancy_penalty * overlap
                    )
                    ranked.append(
                        {
                            "id": sid,
                            "gain": gain,
                            "overlap": overlap,
                            "relevance": relevance,
                            "objective": objective,
                        }
                    )
                credible = [
                    r
                    for r in ranked
                    if r["gain"] >= config.minimum_gain
                    and ids.index(r["id"]) < config.max_rank
                ]
                default = next(r for r in ranked if r["id"] == dedup)
                if credible:
                    winner = sorted(
                        credible,
                        key=lambda r: (-r["objective"], ids.index(r["id"]), r["id"]),
                    )[0]
                    if winner["objective"] > default["objective"]:
                        candidate = winner["id"]
                    else:
                        fallback = fallback or "no_better_supported_increment"
                else:
                    fallback = fallback or "no_credible_increment"
                skipped.extend(r for r in ranked if r["id"] != candidate)
            elif policy == "complementary":
                fallback = "no_public_requirements"
            chosen.append(candidate)
            reasons.append(
                {
                    "id": candidate,
                    "baseline_next": original,
                    "decision": "replaced" if candidate != original else "retained",
                }
            )
    return {
        "selection_policy": policy,
        "policy_revision": "fixed-k-v2",
        "policy_config": asdict(config),
        "candidate_snapshot_id": snapshot_id,
        "selected_skill_ids": chosen,
        "skill_ids": chosen,
        "selected_count": len(chosen),
        "why_selected": [{"id": ids[0], "decision": "strong_top1_anchor"}] + reasons
        if chosen
        else [],
        "why_skipped": skipped,
        "fallback_reason": fallback,
        "features": feat,
        "relations": relations,
        "unknown_features": sum(
            e["status"] == "UNKNOWN"
            for rows_ in feat["supports"].values()
            for e in rows_
        ),
        "selection_time": time.perf_counter() - start,
        "feature_seconds": feature_seconds,
        "extra_model_usage": feat["extra_model_usage"],
        "public_environment_profile": "NO_CANDIDATE_SPECIFIC_FILTER",
        "registry_id": registry["registry_id"],
        "input_prompt_hash": snapshot["input_prompt_hash"],
    }


def digest_registry(registry):
    return hashlib.sha256(
        json.dumps(registry["skills"], sort_keys=True).encode()
    ).hexdigest()


def bind_snapshot(result: dict, prompt: str, registry_id: str) -> dict:
    return {
        **result,
        "registry_id": registry_id,
        "input_prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
        "bound_model_identity": digest(result["model_identity"]),
    }
