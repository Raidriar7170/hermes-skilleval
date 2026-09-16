"""Requirement clauses and explicit contradictions, with literal evidence spans."""

import re


def requirements(request, limit=6):
    clauses = [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", request) if s.strip()]
    if len(clauses) > limit:
        # Group adjacent requirements without deleting constraints or negation.
        size = (len(clauses) + limit - 1) // limit
        clauses = [
            " ".join(clauses[i : i + size]) for i in range(0, len(clauses), size)
        ]
    return clauses or [request]


def contradictions(requirement, skill, environment):
    text = skill.get("body", "")
    evidence = []
    if (
        environment.get("network") == "disabled"
        and skill.get("requires_network") is True
    ):
        evidence.append(
            {
                "reason": "network_required_but_disabled",
                "source": "requires_network",
                "text": True,
            }
        )
    pairs = [
        (
            r"\b(?:preserve|retain|keep)\s+(?:all\s+)?duplicate",
            r"\b(?:remove|drop|eliminate)\s+duplicates|\bdeduplicate\b",
            "preserve_vs_remove_duplicates",
        ),
        (
            r"\b(?:without|do not|must not|never)\s+(?:changing|change|modify|modifying)\s+(?:stored\s+)?(?:rows|data|database)",
            r"\b(?:overwrite|replace)\s+(?:the\s+)?(?:source|input|database)\b",
            "readonly_vs_overwrite",
        ),
    ]
    for request_pattern, skill_pattern, reason in pairs:
        if re.search(request_pattern, requirement, re.I):
            for match in re.finditer(skill_pattern, text, re.I):
                prefix = text[max(0, match.start() - 30) : match.start()].lower()
                if re.search(
                    r"(?:do not|does not|must not|is not|cannot|can not|don.t|doesn.t|never|avoid|without)\s*$",
                    prefix,
                ):
                    continue
                evidence.append(
                    {
                        "reason": reason,
                        "source": "body",
                        "span": [match.start(), match.end()],
                        "text": match.group(),
                    }
                )
    return evidence


def score_candidates(
    request, context, candidates, scores, ranker, environment, threshold=0.8
):
    from .gate import sigmoid
    from .reranker import representation

    clauses = requirements(request)
    items = []
    for skill, score in zip(candidates, scores):
        supports, evidence, conflicts = [], [], []
        for clause in clauses:
            conflict = contradictions(clause, skill, environment)
            conflicts.extend(conflict)
            values, _ = ranker.scores([representation(clause, context, skill)])
            support = sigmoid(float(values.detach().cpu()[0]))
            supported = not conflict and support >= threshold
            supports.append(support if supported else 0.0)
            evidence.append(
                {
                    "requirement": clause,
                    "state": "CONTRADICTED"
                    if conflict
                    else ("SUPPORTED_BY_TEXT" if supported else "UNKNOWN"),
                    "source": "model_judged_text",
                    "score": support,
                    "text": skill["body"][:4000],
                    "conflicts": conflict,
                }
            )
        items.append(
            {
                "id": skill["id"],
                "relevance": sigmoid(score),
                "support": supports,
                "support_state": "SUPPORTED_BY_TEXT" if any(supports) else "UNKNOWN",
                "support_source": "model_judged_text",
                "evidence": evidence,
                "compatible": not bool(conflicts),
                "tokens": len(ranker.tokenizer.encode(skill["body"])),
                "equivalent_family": skill["package_sha256"],
            }
        )
    return clauses, items


def ordinal_relevance(candidates, rank_scores):
    """Within-pool ordering proxy. A rank logit is never a support probability."""
    import math

    if len(candidates) != len(rank_scores) or not all(
        math.isfinite(v) for v in rank_scores
    ):
        raise ValueError("finite rank scores aligned with candidates required")
    order = sorted(
        range(len(candidates)), key=lambda i: (-rank_scores[i], candidates[i]["id"])
    )
    return {
        candidates[i]["id"]: 1 - rank / max(1, len(order) - 1)
        for rank, i in enumerate(order)
    }


def support_identity(config):
    from pathlib import Path
    import hashlib
    from .context import digest
    from .reranker import SUPPORT_TEMPLATE, SUPPORT_INSTRUCTION

    return digest(
        {
            "schema": "text-help-v2",
            "template": SUPPORT_TEMPLATE,
            "instruction": SUPPORT_INSTRUCTION,
            "base": config["reranker_revision"],
            "adapter": config["adapter_sha256"],
            "adapter_config": config.get("adapter_config_sha256"),
            "model_files": config.get("model_files", {}).get("reranker"),
            "max_length": config.get("support_max_length", 8192),
            "context": "repo-context-v2",
            "context_budget": config.get("fragment_budget", {}),
            "evidence": "full-body-v1",
            "requirement": "whole-public-request-v1",
            "sources": {
                n: hashlib.sha256(
                    Path(__file__).with_name(n + ".py").read_bytes()
                ).hexdigest()
                for n in ("context", "reranker", "support")
            },
        }
    )


def score_support(requirement, context, skill_evidence, ranker, *, max_length=8192):
    """Independent support instruction, raw yes/no logit and actual input evidence."""
    import time
    from .reranker import structured_representation

    before = ranker.max_length
    started = time.monotonic()
    try:
        ranker.max_length = max_length
        values, records = ranker.scores(
            [structured_representation(requirement, context, skill_evidence)]
        )
    finally:
        ranker.max_length = before
    record = records[0]
    return {
        "raw_support_score": float(values.detach().cpu()[0]),
        "input": record,
        "visible": record["request_complete"] and record["evidence_complete"],
        "wall_seconds": time.monotonic() - started,
        "source": "model_judged_text",
        "score_target": "specific applicable textual help, not issue sufficiency",
    }


def calibrated_candidates(
    request, context, candidates, rank_scores, ranker, environment, config, model
):
    from .calibration import predict

    relevance = ordinal_relevance(candidates, rank_scores)
    identity = support_identity(config)
    # Reject incompatible calibration before any expensive support forwards.
    predict(model, 0.0, identity)
    items = []
    for skill in candidates:
        observed = score_support(
            request,
            context,
            skill,
            ranker,
            max_length=config.get("support_max_length", 8192),
        )
        conflicts = contradictions(request, skill, environment)
        p = predict(model, observed["raw_support_score"], identity)
        threshold = model.get("threshold")
        accepted = (
            threshold is not None
            and observed["visible"]
            and not conflicts
            and context.get("state") == "usable"
            and p >= threshold
        )
        reason = (
            "explicit_conflict"
            if conflicts
            else "critical_input_not_visible"
            if not observed["visible"]
            else "context_" + context.get("state", "unknown")
            if context.get("state") != "usable"
            else "no_valid_operating_point"
            if threshold is None
            else "supported"
            if accepted
            else "support_below_threshold"
        )
        items.append(
            {
                "id": skill["id"],
                "relevance": relevance[skill["id"]],
                "rank_score": rank_scores[candidates.index(skill)],
                "support": [p if accepted else 0.0],
                "support_state": "SUPPORTED_BY_TEXT" if accepted else "UNKNOWN",
                "support_source": "model_judged_text",
                "compatible": not conflicts,
                "tokens": len(ranker.tokenizer.encode(skill["body"])),
                "equivalent_family": skill["package_sha256"],
                "evidence": [
                    {
                        "requirement": request,
                        **observed,
                        "p_text": p,
                        "threshold": threshold,
                        "conflicts": conflicts,
                        "eligible": accepted,
                        "reason": reason,
                        "text": skill["body"],
                    }
                ],
            }
        )
    return [request], items
