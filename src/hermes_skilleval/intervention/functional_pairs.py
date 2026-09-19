"""Same-state functional contrasts and explicit incomplete paired denominators."""

from collections import Counter

from .functional_outcomes import paired_delta, transition


def verify_collection_roster(rows, roster, protocol_sha256, *, require_complete=True):
    """Require every prospectively registered tail, including unknown outcomes."""
    if roster["source_protocol_sha256"] != protocol_sha256:
        raise ValueError("realized roster protocol mismatch")
    fields = ("task_id", "state_id", "repeat", "action")
    expected = [tuple(row[k] for k in fields) for row in roster["samples"]]
    actual = [tuple(row[k] for k in fields) for row in rows]
    if (
        len(expected) != roster["realized_planned_tails"]
        or len(set(expected)) != len(expected)
        or len(set(actual)) != len(actual)
        or not set(actual) <= set(expected)
        or (require_complete and set(actual) != set(expected))
    ):
        raise ValueError("collection sample roster mismatch; retain planned denominator")
    return {
        "realized_planned_tails": len(expected),
        "recorded_tails": len(actual),
        "missing_tails": len(set(expected) - set(actual)),
        "complete": set(actual) == set(expected),
    }


def paired_records(rows):
    by_key = {}
    for row in rows:
        key = (row["task_id"], row["state_id"], row["repeat"], row["action"])
        if key in by_key:
            raise ValueError("duplicate paired sample")
        by_key[key] = row
    pairs = []
    for key, row in by_key.items():
        if row["action"] == "NO_INTERVENTION":
            continue
        base = by_key.get((*key[:3], "NO_INTERVENTION"))
        reminder = by_key.get((*key[:3], "GENERIC_REMINDER"))
        for peer in (base, reminder):
            if peer is None:
                continue
            for field in (
                "binding_sha256",
                "candidates",
                "candidate_payloads",
                "state",
            ):
                if row[field] != peer[field]:
                    raise ValueError("paired common state mismatch: " + field)
        pairs.append(
            {
                **row,
                "baseline_sample": None
                if base is None
                else list((*key[:3], "NO_INTERVENTION")),
                "delta_functional": paired_delta(base, row) if base else None,
                "transition": transition(base, row) if base else "unknown",
                "delta_vs_reminder": paired_delta(reminder, row) if reminder else None,
                "policy_only_transition": bool(
                    base
                    and row["y_functional"] is not None
                    and row["y_functional"] == base["y_functional"]
                    and {row.get("file_policy_status"), base.get("file_policy_status")}
                    == {"PASS", "FAIL"}
                ),
            }
        )
    return pairs


def signal_summary(pairs, *, collection_complete):
    skills = [r for r in pairs if r["action"] != "GENERIC_REMINDER"]
    known = [r for r in skills if r["delta_functional"] is not None]
    nonzero = sum(r["delta_functional"] != 0 for r in known)
    status = (
        "FUNCTIONAL_ACTION_DIFFERENCE_OBSERVED"
        if nonzero
        else "FUNCTIONAL_SIGNAL_NOT_IDENTIFIABLE"
        if collection_complete and skills and len(known) == len(skills)
        else "FUNCTIONAL_SIGNAL_UNRESOLVED"
    )
    return {
        "status": status,
        "collection_complete": collection_complete,
        "skill_pair_denominator": len(skills),
        "known_skill_pairs": len(known),
        "unknown_skill_pairs": len(skills) - len(known),
        "nonzero_skill_pairs": nonzero,
        "transitions": dict(Counter(r["transition"] for r in pairs)),
        "policy_only_transitions": sum(r["policy_only_transition"] for r in pairs),
        "positive_utility_claim": False,
    }
