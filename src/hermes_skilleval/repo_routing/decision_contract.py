"""Goal-specific selection and ranking; saved-score arithmetic, never training."""

from __future__ import annotations

from .applicability_data import targets
from .applicability_eval import axis_metrics, ranking
from .gate import sigmoid

AXES = {
    "applicability": ["applicability"],
    "task_specific": ["applicability", "specificity_given_applicable"],
}
FORMULAS = {
    "applicability": "sigmoid_applicability",
    "task_specific": "raw_app_times_conditional_specificity",
}
METRICS = {
    "applicability": "group_macro_applicability_log_loss",
    "task_specific": "group_macro_joint_event_log_loss",
}


def event_rows(rows):
    result = []
    for row in rows:
        a, s = targets(row)
        y = 0 if a == 0 else s if a == 1 else None
        result.append(
            {
                **row,
                "applicability_label": "UNKNOWN"
                if y is None
                else "APPLICABLE"
                if y
                else "NOT_APPLICABLE",
                "specificity_label": "UNKNOWN" if y else None,
            }
        )
    return result


def aligned(rows, records):
    index = {r["row_id"]: r for r in records}
    if (
        len(index) != len(records)
        or len({r["row_id"] for r in rows}) != len(rows)
        or set(index) != {r["row_id"] for r in rows}
    ):
        raise ValueError("duplicate or mismatched row identities")
    return [index[r["row_id"]] for r in rows]


def priority(probabilities, target):
    if target not in AXES:
        raise ValueError("unknown decision target")
    return [p[0] if target == "applicability" else p[0] * p[1] for p in probabilities]


def metrics(
    rows, probabilities, target, *, fixed=None, accepted=None, rank_scores=None
):
    return {
        "applicability": axis_metrics(rows, probabilities),
        "joint_event": axis_metrics(
            event_rows(rows), [[p[0] * p[1], 0] for p in probabilities]
        ),
        "ranking": ranking(
            rows,
            probabilities,
            fixed=fixed,
            accepted=accepted,
            rank_scores=rank_scores
            if rank_scores is not None
            else priority(probabilities, target),
        ),
    }


def validate_contract(contract):
    target = contract["decision_target"]
    if target not in AXES or contract.get("schema") != "decision-alignment-v1":
        raise ValueError("unknown decision contract")
    if (
        contract.get("required_supervised_axes") != AXES[target]
        or contract.get("ranking_formula") != FORMULAS[target]
        or contract.get("selection_metric") != METRICS[target]
        or contract.get("k") != 2
    ):
        raise ValueError("objective/supervision/ranking mismatch")
    for axis in AXES[target]:
        if contract.get("supervised_denominators", {}).get(axis, 0) <= 0:
            raise ValueError("direct supervision required: " + axis)
    if contract.get("support_mode") not in {"advisory", "supported"}:
        raise ValueError("invalid support mode")
    for field in ("candidate_id", "input_identity", "adapter_sha256"):
        if not contract.get(field) or contract[field] in {
            "FROM_DEV_ONLY",
            "BOUND_AT_EXECUTION",
        }:
            raise ValueError("unbound decision identity")
    if contract.get("epoch") not in (1, 2, 3):
        raise ValueError("invalid epoch")
    if contract["support_mode"] == "supported" and not contract.get("calibration_ref"):
        raise ValueError("supported decision requires bound calibration")
    return contract


def select_for_goal(rows, candidates, target, input_identity, tolerance=1e-12):
    """Only model-dev rows accepted. No cal/check argument or implicit access."""
    if not rows or any(r["split"] != "model-dev" for r in rows):
        raise ValueError("model-dev only")
    if target not in AXES:
        raise ValueError("unknown target")
    events = event_rows(rows)
    if target == "task_specific" and {targets(r)[0] for r in events} - {None} != {
        0.0,
        1.0,
    }:
        raise ValueError("INSUFFICIENT_DEV_EVENT_CLASSES")
    trials = []
    for candidate in candidates:
        if any(
            candidate["supervised_denominators"].get(a, 0) <= 0 for a in AXES[target]
        ):
            continue
        records = aligned(rows, candidate["rows"])
        pp = [[sigmoid(z) for z in r["logits"]] for r in records]
        mm = metrics(rows, pp, target)
        axis = mm["applicability" if target == "applicability" else "joint_event"]
        if axis["log_loss"] is None:
            continue
        trials.append(
            {k: v for k, v in candidate.items() if k != "rows"}
            | {"metrics": mm, "loss": axis["log_loss"]}
        )
    if not trials:
        raise ValueError("NO_SUPERVISED_CANDIDATE")
    best = min(t["loss"] for t in trials)
    tied = [t for t in trials if t["loss"] <= best + tolerance]

    def tie(t):
        m = t["metrics"]
        secondary = (
            (m["applicability"]["brier"],)
            if target == "applicability"
            else (
                m["ranking"]["group_macro"]["known_inapplicable_at_2"],
                -m["ranking"]["group_macro"]["precision_at_2"],
            )
        )
        return (*secondary, t["candidate_id"], t["epoch"])

    chosen = min(tied, key=tie)
    contract = {
        k: chosen[k]
        for k in ("candidate_id", "epoch", "adapter_sha256", "supervised_denominators")
    }
    contract.update(
        schema="decision-alignment-v1",
        decision_target=target,
        required_supervised_axes=AXES[target],
        selection_metric=METRICS[target],
        ranking_formula=FORMULAS[target],
        k=2,
        support_mode="advisory",
        input_identity=input_identity,
        calibration_ref=None,
        analysis_scope="RETROSPECTIVE_DIAGNOSTIC",
    )
    validate_contract(contract)
    return {
        "contract": contract,
        "trials": sorted(trials, key=lambda t: (t["candidate_id"], t["epoch"])),
    }


def score_axes(ranker, public, contract):
    """Actual A inference uses one instruction; J uses the same raw product as dev."""
    validate_contract(contract)
    from .pointwise_support import representation

    axes = AXES[contract["decision_target"]]
    values, records = ranker.scores([representation(public, axis) for axis in axes])
    logits = values.detach().cpu().tolist()
    pp = [sigmoid(z) for z in logits]
    return {
        "logits": logits,
        "priority_score": pp[0] if len(pp) == 1 else pp[0] * pp[1],
        "formula_id": contract["ranking_formula"],
        "output_axes": axes,
        "inputs": records,
        "accepted": False,
    }


def guarded_score(
    public, config, contract, facts, token_records, *, calibration=None, factory=None
):
    """Validate before weight hashing/construction; all acceptance uses shared predicate."""
    validate_contract(contract)
    from .calibration_preflight import eligibility
    from .context import digest
    from .pointwise_support import PublicInput, scorer_identity

    if type(public) is not PublicInput:
        raise ValueError("public allowlist required")
    if (
        config.get("adapter_files", {}).get("adapter_model.safetensors")
        != contract["adapter_sha256"]
    ):
        raise ValueError("candidate/checkpoint mismatch")
    current_input = digest(public.__dict__)
    if token_records.get("public_input_identity") != current_input:
        raise ValueError("token/input identity mismatch")
    qualified = eligibility(
        context_state=facts["context_state"],
        token_visible=token_records.get("visible"),
        environment_known=facts.get("environment_known"),
        conflicts=facts.get("conflicts", False),
        structural_reasons=facts.get("structural_reasons", ()),
    )
    if token_records.get("visible") is not True or facts["context_state"] in {
        "unknown",
        "unavailable",
    }:
        return {
            "status": "BLOCKED",
            "accepted": False,
            **qualified,
            "model_constructions": 0,
        }
    if contract["support_mode"] == "supported":
        if not qualified["eligible"]:
            return {
                "status": "BLOCKED",
                "accepted": False,
                **qualified,
                "model_constructions": 0,
            }
        if calibration is None or calibration.get("threshold") is None:
            raise ValueError("supported mode requires a validated threshold")
        if (
            current_input not in calibration.get("public_input_identities", [])
            or calibration.get("contract_identity") != contract_identity(contract)
            or calibration.get("axis") != "applicability"
        ):
            raise ValueError("calibration/input/contract mismatch")
    if (
        calibration is not None
        and calibration.get("schema") == "aligned-calibration-v2"
    ):
        if (
            not facts.get("environment_binding")
            or calibration.get("environment_bindings", {}).get(current_input)
            != facts["environment_binding"]
        ):
            raise ValueError("calibration/environment binding mismatch")
    identity = scorer_identity(config)
    if calibration is not None and calibration.get("scorer_identity") != identity:
        raise ValueError("calibration/scorer mismatch")
    if factory is None:
        from .reranker import Reranker

        factory = Reranker
    ranker = factory(
        config["base"],
        device=config["device"],
        max_length=config["max_length"],
        adapter=config.get("adapter"),
    )
    result = score_axes(ranker, public, contract)
    result.update(
        status="ADVISORY",
        scorer_identity=identity,
        actual_adapter_sha256=config["adapter_files"]["adapter_model.safetensors"],
        input_identity=current_input,
        decision_target=contract["decision_target"],
        support_eligibility=qualified,
        execution_eligibility="NOT_ASSESSED",
        model_constructions=1,
    )
    if contract["support_mode"] == "supported":
        mapping = calibration["mapping"]
        probability = sigmoid(mapping["a"] * result["logits"][0] + mapping["b"])
        result.update(
            status="SUPPORTED_SCORE",
            support_probability=probability,
            accepted=qualified["eligible"] and probability >= calibration["threshold"],
        )
    return result


def contract_identity(contract):
    """Support mode/reference do not change the frozen model or ranking decision."""
    from .context import digest

    return digest(
        {
            k: v
            for k, v in contract.items()
            if k not in {"support_mode", "calibration_ref"}
        }
    )
