"""Lightweight public-input eligibility and cal-label necessary conditions.

No scorer, probabilities, reference patches, or heavy ML imports belong here.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from .applicability_data import group_weights, targets, validate_splits
from .context import digest


def eligibility(
    *,
    context_state,
    token_visible,
    environment_known,
    conflicts=False,
    structural_reasons=(),
):
    reasons = list(structural_reasons)
    if conflicts:
        reasons.append("explicit_conflict")
    if environment_known is not True:
        reasons.append("unknown_environment")
    if token_visible is not True:
        reasons.append(
            "TOKENIZATION_UNCHECKED"
            if token_visible is None
            else "critical_input_not_visible"
        )
    if context_state != "usable":
        reasons.append("context_" + context_state)
    return {"eligible": not reasons, "reasons": reasons}


def input_identity(tasks, registry, template_identity):
    return digest(
        {
            "tasks": [
                {
                    "request": t["request"],
                    "source_revision": t["source_revision"],
                    "context": t["context"],
                }
                for t in tasks
            ],
            "registry": registry,
            "template": template_identity,
        }
    )


def structural(tasks, skills, *, tokens=None, environment_known=False):
    """Public tasks only; token records must already bind to current input identity."""
    validate_splits(tasks)
    result = []
    for task in tasks:
        c = task["context"]
        errors = []
        if not task.get("source_revision") or not task.get("request"):
            errors.append("SOURCE_IDENTITY_MISSING")
        for fragment in c.get("matched_symbols", []):
            path = PurePosixPath(fragment["path"])
            if (
                path.is_absolute()
                or ".." in path.parts
                or set(path.parts) & {"reference", "trusted", ".git", ".codex"}
            ):
                errors.append("UNAUTHORIZED_PATH")
            source = c.get("source_hashes", {}).get(fragment["path"], {})
            if source.get("read_sha256") != fragment.get(
                "source_sha256"
            ) or not fragment.get("snippet"):
                errors.append("FRAGMENT_SOURCE_UNBOUND")
        missing = [m for m in c.get("missing", []) if m.get("critical")]
        known_environment = (
            environment_known.get(task["task_id"], False) is True
            if isinstance(environment_known, dict)
            else environment_known is True
        )
        for skill in skills:
            row_id = task["task_id"] + "::" + skill["id"]
            token = (tokens or {}).get(row_id)
            visible = token.get("visible") if token else None
            from .support import contradictions

            conflict = bool(contradictions(task["request"], skill, {}))
            decision = eligibility(
                context_state=c["state"],
                token_visible=visible,
                environment_known=known_environment,
                conflicts=conflict,
            )
            reasons = decision["reasons"] + errors
            if not skill.get("body") or not skill.get("name"):
                reasons.append("SKILL_CONTENT_MISSING")
            if missing:
                reasons.append("CRITICAL_CONTEXT_MISSING")
            from .pointwise_support import public_input

            result.append(
                {
                    "row_id": row_id,
                    "public_input_identity": digest(public_input(task, skill).__dict__),
                    "task_id": task["task_id"],
                    "repair_group_id": task["repair_group_id"],
                    "context_state": c["state"],
                    "critical_missing": missing,
                    "noncritical_missing": [
                        m for m in c.get("missing", []) if not m.get("critical")
                    ],
                    "context_eligible": c["state"] == "usable"
                    and not errors
                    and not missing,
                    "token_status": "TOKENIZATION_UNCHECKED"
                    if visible is None
                    else "COMPLETE"
                    if visible
                    else "TRUNCATED",
                    "token_visible": visible,
                    "environment_known": known_environment,
                    "environment": c.get("environment", {}),
                    "conflicts": conflict,
                    "eligible": not reasons,
                    "reasons": reasons,
                    "source_ref": task.get("public_context_ref"),
                    "source_revision": task["source_revision"],
                }
            )
    return result


def feasibility(public_rows, labels, rule, *, required_axes=(0,)):
    """Necessary bounds ignore score ordering; never validate an operating point."""
    by = {r["row_id"]: r for r in public_rows}
    if (
        len(by) != len(public_rows)
        or len({r["row_id"] for r in labels}) != len(labels)
        or set(by) != {r["row_id"] for r in labels}
    ):
        raise ValueError("cal label/structure identity mismatch")
    if any(
        r["split"] != "cal"
        or r["repair_group_id"] != by[r["row_id"]]["repair_group_id"]
        or r["task_id"] != by[r["row_id"]]["task_id"]
        for r in labels
    ):
        raise ValueError("cal-only matched labels required")
    known = [r for r in labels if targets(r)[0] is not None]
    eligible = [r for r in known if by[r["row_id"]]["eligible"]]
    context_known = [r for r in known if by[r["row_id"]]["context_eligible"]]
    weights = (
        dict(zip([r["row_id"] for r in known], group_weights(known))) if known else {}
    )
    groups = len({r["repair_group_id"] for r in eligible})
    context_groups = len({r["repair_group_id"] for r in context_known})
    mass = sum(weights[r["row_id"]] for r in eligible)
    op = rule["operating_point"]
    checks = {
        "accepted_known_groups": groups >= op["min_accepted_groups"],
        "accepted_known_rows": len(eligible) >= op["min_accepted_rows"],
        "known_coverage": mass >= op["min_known_coverage"],
    }
    axes = {}
    # Mapping follows old protocol: all known cal labels, independently of support eligibility.
    for axis in (0, 1):
        rr = [r for r in labels if targets(r)[axis] is not None]
        counts = {str(y): sum(targets(r)[axis] == y for r in rr) for y in (0, 1)}
        ng = len({r["repair_group_id"] for r in rr})
        ok = (
            ng >= rule["calibration"]["min_axis_groups"]
            and min(counts.values()) >= rule["calibration"]["min_each_class"]
        )
        axes[str(axis)] = {
            "known_rows": len(rr),
            "groups": ng,
            "classes": counts,
            "necessary_conditions_met": ok,
            "required": axis in required_axes,
            "scope": "all known cal labels; mapping is separate from eligible acceptance",
        }
        if axis in required_axes:
            checks["mapping_axis_" + str(axis)] = ok
    return {
        "status": "NECESSARY_CONDITIONS_MET" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "context_known_group_upper_bound": context_groups,
        "eligible_known_groups": groups,
        "eligible_known_rows": len(eligible),
        "max_known_coverage": mass,
        "min_accepted_groups": op["min_accepted_groups"],
        "axes": axes,
        "bound_scope": "necessary only; ignores score ordering; does not prove any precision or threshold",
        "supported_operating_point": "NOT_ESTABLISHED",
    }


def report(
    tasks,
    skills,
    rule,
    *,
    labels=None,
    tokens=None,
    environment_known=False,
    requested_operation="calibrate",
    identity=None,
):
    public = structural(
        tasks, skills, tokens=tokens, environment_known=environment_known
    )
    result = {
        "schema": "calibration-preflight-v1",
        "requested_operation": requested_operation,
        "input_identity": identity,
        "rows": public,
        "model_constructions": 0,
        "scorer_calls": 0,
        "forward_calls": 0,
        "status": "NECESSARY_CONDITIONS_MET"
        if all(r["eligible"] for r in public)
        else "BLOCKED",
    }
    if requested_operation in {"calibrate", "cal-score"}:
        if labels is None:
            raise ValueError("cal labels required only after model selection freeze")
        result["calibration"] = feasibility(public, labels, rule)
        result["status"] = result["calibration"]["status"]
    elif requested_operation in {"advisory", "dev-score", "train-structure"}:
        blocking = {
            "SOURCE_IDENTITY_MISSING",
            "UNAUTHORIZED_PATH",
            "FRAGMENT_SOURCE_UNBOUND",
            "SKILL_CONTENT_MISSING",
            "critical_input_not_visible",
            "TOKENIZATION_UNCHECKED",
        }
        result["status"] = (
            "BLOCKED"
            if any(
                blocking.intersection(r["reasons"])
                or r["context_state"] in {"unknown", "unavailable"}
                for r in public
            )
            else "NECESSARY_CONDITIONS_MET"
        )
    elif requested_operation not in {
        "advisory",
        "dev-score",
        "train-structure",
        "structure",
    }:
        raise ValueError("unknown requested operation")
    return result


def extract_repaired(root, request, environment, budget=None):
    """Remove only proven prose-parenthesis false calls; preserve original extractor.

    Code fences/backticks, adjacent calls, and ambiguous spaced calls remain strict.
    New context identity prevents pairing repaired eligibility with old logits.
    """
    import re
    from .context import extract_fragments

    context = extract_fragments(root, request, environment, budget)
    prose = re.sub(r"```[\s\S]*?```|`[^`\n]*`", "", request)
    false_calls = set(
        re.findall(
            r"\b([A-Za-z_]\w*)\s+\((?:the |maybe |an |a |e\.g\.|i\.e\.)[^)]*\)", prose
        )
    )
    removed = []
    kept = []
    for missing in context["missing"]:
        name = missing.get("symbol", "")
        # Every mention that looks like a call must be a recognized prose aside.
        remaining = (
            re.sub(
                r"\b"
                + re.escape(name)
                + r"\s+\((?:the |maybe |an |a |e\.g\.|i\.e\.)[^)]*\)",
                "",
                request,
            )
            if name
            else request
        )
        if (
            missing["reason"] == "explicit_call_unlocated"
            and name in false_calls
            and not re.search(r"\b" + re.escape(name) + r"\s*\(", remaining)
        ):
            removed.append(missing)
        else:
            kept.append(missing)
    context["missing"] = kept
    if removed:
        # Recompute only this predicate. Scan uncertainty and genuine criticality remain.
        blocking_scan = {
            "enumeration_budget",
            "scan_budget",
            "file_scan_budget",
            "hit_budget",
        }
        if (
            context["state"] == "partial"
            and context["matched_symbols"]
            and not any(m.get("critical") or m["reason"] in blocking_scan for m in kept)
        ):
            context["state"] = "usable"
            context["supported"] = True
            context["support_reason"] = "usable"
            context["summary"] = context["summary"].replace(
                "Context state: partial.", "Context state: usable.", 1
            )
    context["schema"] = "repo-context-prose-call-v1"
    context["legacy_cache_key"] = context["cache_key"]
    context["cache_key"] = digest(
        [context["schema"], context["legacy_cache_key"], context["summary"], kept]
    )
    context["prose_call_corrections"] = removed
    return context


def safe_snapshot_path(root, relative):
    """Reject traversal and every symlink before reading any snapshot bytes."""
    from pathlib import Path

    rel = PurePosixPath(relative)
    if (
        rel.is_absolute()
        or ".." in rel.parts
        or not rel.parts
        or set(rel.parts) & {"reference", "trusted", ".git", ".codex"}
    ):
        raise ValueError("UNAUTHORIZED_PATH")
    root = Path(root)
    if root.is_symlink():
        raise ValueError("UNAUTHORIZED_SYMLINK")
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("UNAUTHORIZED_SYMLINK")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("UNAUTHORIZED_PATH")
    return path
