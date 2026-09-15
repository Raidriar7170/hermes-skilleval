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
