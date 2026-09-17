"""Independent dual-instruction support LoRA; shared structured causal scorer."""

from __future__ import annotations
from dataclasses import dataclass
import math
from pathlib import Path

from .applicability_data import (
    file_hash,
    group_weights,
    read_json,
    read_rows,
    targets,
    write_json,
)
from .reranker import Reranker, structured_representation

INSTRUCTIONS = {
    "applicability": "judgment = applicability. Does the skill provide a concrete applicable procedure, implementation step or verification check for the public request under the known conditions? A general debugging or verification workflow CAN be applicable. It need not solve the entire task. Answer yes for a supported applicable step; no if its scope or necessary preconditions do not match, conflict, or evidence is insufficient. Preserve all negations and limitations.",
    "specificity_given_applicable": "judgment = specificity_given_applicable. Assuming an applicable step exists, does the cited skill content give help specifically targeting an explicit interface, input format, operation or constraint in this request? Answer yes for task-specific help. Answer no for concrete but broadly applicable debugging, testing or verification workflow, or insufficient specificity evidence. Do not infer specificity solely from a skill name.",
}


@dataclass(frozen=True)
class PublicInput:
    request: str
    context: str
    skill_name: str
    skill_description: str
    skill_body: str

    def __post_init__(self):
        if (
            not all(isinstance(v, str) for v in self.__dict__.values())
            or not self.request
            or not self.skill_body
        ):
            raise ValueError("nonempty public text input required")


def representation(public: PublicInput, judgment: str, *, use_context=True):
    if type(public) is not PublicInput or judgment not in INSTRUCTIONS:
        raise ValueError(
            "PublicInput and known program-owned judgment required; label rows forbidden"
        )
    result = structured_representation(
        public.request,
        {
            "summary": public.context
            if use_context
            else "Public context omitted for inference ablation."
        },
        {
            "name": public.skill_name,
            "description": public.skill_description,
            "body": public.skill_body,
        },
    )
    result["instruction"] = INSTRUCTIONS[judgment]
    return result


def public_input(task, skill):
    """Explicit allowlist boundary from study controller to scorer."""
    return PublicInput(
        task["request"],
        task["context"]["summary"],
        skill["name"],
        skill["description"],
        skill["body"],
    )


def masked_loss(logits, labels, weights):
    import torch
    import torch.nn.functional as F

    if logits.ndim != 1 or len(labels) != len(logits) or len(weights) != len(logits):
        raise ValueError("aligned one-dimensional samples required")
    if any(not math.isfinite(w) or w < 0 for w in weights):
        raise ValueError("finite nonnegative weights required")
    mask = torch.tensor(
        [y is not None for y in labels], device=logits.device, dtype=logits.dtype
    )
    yy = torch.tensor(
        [y if y is not None else 0 for y in labels],
        device=logits.device,
        dtype=logits.dtype,
    )
    ww = torch.tensor(weights, device=logits.device, dtype=logits.dtype) * mask
    den = ww.sum()
    return (
        (F.binary_cross_entropy_with_logits(logits, yy, reduction="none") * ww).sum()
        / den
        if den.item() > 0
        else logits.sum() * 0
    ), float(den.detach().cpu())


def score(ranker, public, *, use_context=True):
    values, records = ranker.scores(
        [representation(public, j, use_context=use_context) for j in INSTRUCTIONS]
    )
    return {
        "logits": values.detach().cpu().tolist(),
        "visible": all(not r["truncated"] for r in records),
        "inputs": [
            {
                "input_sha256": r["input_sha256"],
                "actual_tokens": r["actual_tokens"],
                "truncated": r["truncated"],
                "sections": [
                    {
                        k: s[k]
                        for k in (
                            "section",
                            "tokens_before",
                            "tokens_used",
                            "truncated",
                        )
                    }
                    for s in r["sections"]
                ],
            }
            for r in records
        ],
    }


def train(config_path):
    import random
    import time
    import resource
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig, get_peft_model

    c = read_json(config_path)
    out = Path(c["output"])
    out.mkdir(parents=True, exist_ok=False)
    rows = [r for r in read_rows(c["labels"]) if r["split"] in {"fit", "model-dev"}]
    from .applicability_data import validate_splits

    validate_splits(read_json(c["tasks"]))
    if c.get("base_files"):
        for name, expected in c["base_files"].items():
            if file_hash(Path(c["base"]) / name) != expected:
                raise ValueError("training base/tokenizer content mismatch")
    tasks = {t["task_id"]: t for t in read_json(c["tasks"])}
    skills = {s["id"]: s for s in read_json(c["registry"])["skills"]}
    if any(
        r["split"] != tasks[r["task_id"]]["split"]
        or r["repair_group_id"] != tasks[r["task_id"]]["repair_group_id"]
        for r in rows
    ):
        raise ValueError("label split/group differs from frozen task source")
    fit = [r for r in rows if r["split"] == "fit"]
    dev = [r for r in rows if r["split"] == "model-dev"]
    if not fit or not dev:
        raise ValueError("fit and separate model-dev required")
    weights = group_weights(fit)
    den = [
        sum(w for r, w in zip(fit, weights) if targets(r)[a] is not None)
        for a in range(2)
    ]
    if not den[0]:
        raise ValueError("no applicability labels")
    torch.manual_seed(c["seed"])
    rng = random.Random(c["seed"])
    ranker = Reranker(c["base"], device=c["device"], max_length=c["max_length"])
    examples = []
    for r, w in zip(fit, weights):
        for axis, y in enumerate(targets(r)):
            if y is not None and (axis == 0 or c["lambda_spec"]):
                text = representation(
                    public_input(tasks[r["task_id"]], skills[r["skill_id"]]),
                    list(INSTRUCTIONS)[axis],
                )
                _, records = ranker.inputs([text])
                if records[0]["truncated"]:
                    raise ValueError(
                        "training evidence truncated; revise public-only budget before experiment"
                    )
                examples.append(
                    (
                        text,
                        y,
                        w / den[axis] * (1 if axis == 0 else c["lambda_spec"]),
                        axis,
                    )
                )
    ranker.model = get_peft_model(
        ranker.model,
        LoraConfig(
            r=c["rank"],
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    ranker.model.config.use_cache = False
    ranker.model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    params = {n: p for n, p in ranker.model.named_parameters() if p.requires_grad}
    initial = {n: p.detach().cpu().clone() for n, p in params.items()}
    opt = torch.optim.AdamW(params.values(), lr=c["lr"])
    trajectory = []
    epoch_records = []
    start = time.monotonic()
    peak = 0
    best = None
    devweights = group_weights(dev)
    for epoch in range(1, c["epochs"] + 1):
        order = list(range(len(examples)))
        rng.shuffle(order)
        opt.zero_grad()
        ranker.model.train()
        for step, i in enumerate(order):
            text, y, w, axis = examples[i]
            z, _ = ranker.scores([text], grad=True)
            # Unbiased mini-batch estimate of the explicitly normalized full objective.
            count = min(
                c["gradient_accumulation"],
                len(order)
                - (step // c["gradient_accumulation"]) * c["gradient_accumulation"],
            )
            loss = (
                F.binary_cross_entropy_with_logits(
                    z, torch.tensor([y], device=z.device)
                )
                * w
                * len(examples)
                / count
            )
            loss.backward()
            if (step + 1) % c["gradient_accumulation"] == 0 or step + 1 == len(order):
                norm = float(torch.nn.utils.clip_grad_norm_(params.values(), 1).cpu())
                if not math.isfinite(norm) or not math.isfinite(
                    float(loss.detach().cpu())
                ):
                    raise ValueError("nonfinite training")
                opt.step()
                opt.zero_grad()
                if c["device"] == "mps":
                    peak = max(peak, torch.mps.driver_allocated_memory())
                item = {
                    "epoch": epoch,
                    "sample": step + 1,
                    "gradient_norm": norm,
                    "last_scaled_loss": float(loss.detach().cpu()),
                    "elapsed_seconds": time.monotonic() - start,
                }
                trajectory.append(item)
                with (out / "trajectory.jsonl").open("a") as f:
                    import json

                    f.write(json.dumps(item) + "\n")
                print(item, flush=True)
        ranker.model.eval()
        pred = []
        losses = []
        for r in dev:
            pred.append(
                score(ranker, public_input(tasks[r["task_id"]], skills[r["skill_id"]]))
            )
        for axis in range(2):
            zs = torch.tensor([p["logits"][axis] for p in pred])
            losses.append(
                masked_loss(zs, [targets(r)[axis] for r in dev], devweights)[0].item()
            )
        checkpoint = out / f"epoch-{epoch}"
        ranker.model.save_pretrained(checkpoint, safe_serialization=True)
        record = {
            "epoch": epoch,
            "dev_log_loss": losses,
            "elapsed_seconds": time.monotonic() - start,
            "checkpoint_sha256": file_hash(checkpoint / "adapter_model.safetensors"),
        }
        epoch_records.append(record)
        write_json(
            out / f"dev-epoch-{epoch}.json",
            {
                "rows": [{"row_id": r["row_id"], **p} for r, p in zip(dev, pred)],
                "metrics": record,
            },
        )
        if best is None or losses[0] < best["dev_log_loss"][0]:
            best = record
        print(record, flush=True)
    changed = sum(
        not torch.equal(initial[n], p.detach().cpu()) for n, p in params.items()
    )
    if not changed or not any(t["gradient_norm"] > 0 for t in trajectory):
        raise ValueError("no actual parameter update")
    # Probe current (last epoch) state; model selection occurs separately using dev only.
    probe = public_input(tasks[fit[0]["task_id"]], skills[fit[0]["skill_id"]])
    probe_result = score(ranker, probe)
    result = {
        "schema": "pointwise-training-v1",
        "config": c,
        "fit_rows": len(fit),
        "dev_rows": len(dev),
        "masked_denominators": den,
        "examples_per_epoch": len(examples),
        "trainable_parameters": sum(p.numel() for p in params.values()),
        "changed_tensors": changed,
        "nonzero_gradient_steps": sum(t["gradient_norm"] > 0 for t in trajectory),
        "epochs": epoch_records,
        "best_epoch": best["epoch"],
        "wall_seconds": time.monotonic() - start,
        "peak_driver_allocated_bytes_observed": peak,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "probe": probe.__dict__,
        "probe_result": probe_result,
        "reload": "PENDING",
        "label_sha256": file_hash(c["labels"]),
        "registry_sha256": file_hash(c["registry"]),
    }
    write_json(out / "training-summary.json", result)
    return result


def reload_probe(summary_path, epoch=None):
    s = read_json(summary_path)
    c = s["config"]
    epoch = c["epochs"] if epoch is None else epoch
    adapter = Path(summary_path).parent / f"epoch-{epoch}"
    ranker = Reranker(
        c["base"], device=c["device"], max_length=c["max_length"], adapter=adapter
    )
    saved = read_json(Path(summary_path).parent / f"dev-epoch-{epoch}.json")["rows"][0]
    tasks = {t["task_id"]: t for t in read_json(c["tasks"])}
    skills = {t["id"]: t for t in read_json(c["registry"])["skills"]}
    row = next(r for r in read_rows(c["labels"]) if r["row_id"] == saved["row_id"])
    actual = score(ranker, public_input(tasks[row["task_id"]], skills[row["skill_id"]]))
    error = max(abs(a - b) for a, b in zip(actual["logits"], saved["logits"]))
    if error > 1e-5 or actual["inputs"] != saved["inputs"]:
        raise ValueError("fresh process selected-epoch reload mismatch")
    result = {
        "reload": "MATCHED",
        "epoch": epoch,
        "adapter_sha256": file_hash(adapter / "adapter_model.safetensors"),
        "max_abs_error": error,
        "actual": actual,
    }
    write_json(Path(summary_path).parent / f"reload-epoch-{epoch}.json", result)
    return result


def scorer_identity(config, *, use_context=True, rank_only=False):
    """Content identity independent of installation path, checked before each run."""
    from .context import digest
    from .reranker import SUPPORT_TEMPLATE

    expected = config["base_files"]
    for name, value in expected.items():
        if file_hash(Path(config["base"]) / name) != value:
            raise ValueError("base/tokenizer identity mismatch: " + name)
    adapter = None
    if config.get("adapter"):
        adapter = {
            name: file_hash(Path(config["adapter"]) / name)
            for name in ("adapter_model.safetensors", "adapter_config.json")
        }
        if adapter != config.get("adapter_files"):
            raise ValueError("adapter identity mismatch")
    sources = {
        name: file_hash(Path(__file__).with_name(name))
        for name in ("pointwise_support.py", "reranker.py", "support.py")
    }
    sources["outer_template"] = file_hash(
        Path(__file__).parent.parent / "vendor/skillrouter_common.py"
    )
    return digest(
        {
            "schema": "conditional-scorer-v1",
            "base_files": expected,
            "adapter_files": adapter,
            "device": config["device"],
            "dtype": "float32",
            "max_length": config["max_length"],
            "instructions": structured_representation(
                "", {"summary": ""}, {"name": ""}, support=False
            )["instruction"]
            if rank_only
            else INSTRUCTIONS,
            "rank_only": rank_only,
            "structured_template": SUPPORT_TEMPLATE,
            "use_context": use_context,
            "sources": sources,
        }
    )


def calibrated_decision(
    observed,
    calibration,
    identity,
    *,
    context_state,
    environment_known,
    conflicts=False,
):
    """Shared offline/runtime probability and conservative acceptance semantics."""
    from .applicability_eval import calibrated

    if calibration["scorer_identity"] != identity:
        raise ValueError("calibration/scorer identity mismatch")
    probabilities = calibrated([observed["logits"]], calibration["mapping"])[0]
    eligible = bool(
        observed["visible"]
        and context_state == "usable"
        and environment_known
        and not conflicts
    )
    threshold = calibration["threshold"]
    accepted = eligible and threshold is not None and probabilities[0] >= threshold
    reason = (
        "explicit_conflict"
        if conflicts
        else "unknown_environment"
        if not environment_known
        else "critical_input_not_visible"
        if not observed["visible"]
        else "context_" + context_state
        if context_state != "usable"
        else "no_valid_operating_point"
        if threshold is None
        else "supported"
        if accepted
        else "support_below_threshold"
    )
    return {
        "probabilities": probabilities,
        "specific_priority": probabilities[0] * probabilities[1],
        "eligible": eligible,
        "accepted": accepted,
        "reason": reason,
    }


def predict_public(
    public,
    config,
    calibration=None,
    *,
    context_state="unknown",
    environment_known=False,
    conflicts=False,
):
    if type(public) is not PublicInput:
        raise ValueError("PublicInput required")
    if not Path(config["base"]).is_dir() or (
        config.get("adapter") and not Path(config["adapter"]).is_dir()
    ):
        return {
            "status": "FALLBACK",
            "reason": "support_model_unavailable",
            "accepted": False,
        }
    identity = scorer_identity(config)
    ranker = Reranker(
        config["base"],
        device=config["device"],
        max_length=config["max_length"],
        adapter=config.get("adapter"),
    )
    observed = score(ranker, public)
    from .support import contradictions

    conflicts = conflicts or bool(
        contradictions(public.request, {"body": public.skill_body}, {})
    )
    if calibration is None:
        return {
            "status": "RAW_ADVISORY",
            "scorer_identity": identity,
            **observed,
            "accepted": False,
            "reason": "calibration_not_supplied",
        }
    return {
        "status": "SCORED",
        "scorer_identity": identity,
        **observed,
        **calibrated_decision(
            observed,
            calibration,
            identity,
            context_state=context_state,
            environment_known=environment_known,
            conflicts=conflicts,
        ),
    }
