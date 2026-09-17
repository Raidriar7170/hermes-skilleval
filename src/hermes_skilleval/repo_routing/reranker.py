"""Shared causal yes/no scoring for training and inference; imports remain lazy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

TEMPLATE = "repo-four-section-v1"


def representation(request, context, skill, *, use_context=True):
    # Keep all request constraints. Token-level truncation is recorded separately.
    return (
        "<Instruct>: Judge whether the skill evidence supports the task requirements.\n"
        "[TASK]\n"
        + request
        + "\n[REPO_CONTEXT]\n"
        + (context["summary"] if use_context else "omitted")
        + "\n[SKILL_METADATA]\n"
        + skill["name"]
        + "\n"
        + skill.get("description", "")
        + "\n[SKILL_EVIDENCE]\n"
        + skill.get("body", "")[:4000]
    )


class Reranker:
    def __init__(
        self, base, *, device="cpu", max_length=1024, adapter=None, train=False
    ):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        from hermes_skilleval.vendor.skillrouter_common import (
            get_reranker_template_tokens,
        )

        self.device, self.max_length = device, max_length
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(base),
            local_files_only=True,
            trust_remote_code=False,
            padding_side="left",
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.prefix, self.suffix = get_reranker_template_tokens(self.tokenizer)
        if max_length <= len(self.prefix) + len(self.suffix) + 32:
            raise ValueError("insufficient token budget")
        self.model = AutoModelForCausalLM.from_pretrained(
            str(base),
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.float32,
            attn_implementation="sdpa",
        ).to(device)
        self.yes, self.no = [
            self.tokenizer.convert_tokens_to_ids(t) for t in ("yes", "no")
        ]
        if self.yes == self.no or self.yes is None or self.no is None:
            raise ValueError("invalid yes/no token identities")
        if adapter:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(
                self.model, str(adapter), is_trainable=train
            )
        self.model.eval()
        self.forward_calls = 0

    def inputs(self, texts):
        import torch

        batches, records = [], []
        for text in texts:
            if isinstance(text, dict):
                ids, record = structured_tokens(self, text)
                batches.append(ids)
                records.append(record)
                continue
            full = self.tokenizer.encode(text)
            markers = [
                "[TASK]",
                "[REPO_CONTEXT]",
                "[SKILL_METADATA]",
                "[SKILL_EVIDENCE]",
            ]
            if not all(marker in text for marker in markers):
                raise ValueError("four-section representation required")
            sections = []
            for index, marker in enumerate(markers):
                section = text.split(marker, 1)[1]
                if index + 1 < len(markers):
                    section = section.split(markers[index + 1], 1)[0]
                sections.append(marker + section)
            available = self.max_length - len(self.prefix) - len(self.suffix)
            caps = [int(available * fraction) for fraction in (0.30, 0.25, 0.10)]
            caps.append(available - sum(caps))
            body_ids, section_records = [], []
            for marker, section, cap in zip(markers, sections, caps):
                tokens = self.tokenizer.encode(section, add_special_tokens=False)
                # Keep tail constraints when a long request needs truncation.
                visible = (
                    tokens
                    if len(tokens) <= cap
                    else (
                        tokens[: cap // 2] + tokens[-(cap - cap // 2) :]
                        if marker == "[TASK]"
                        else tokens[:cap]
                    )
                )
                body_ids.extend(visible)
                section_records.append(
                    {
                        "section": marker,
                        "tokens_before": len(tokens),
                        "tokens_used": len(visible),
                        "truncated": len(tokens) > cap,
                    }
                )
            ids = self.prefix + body_ids + self.suffix
            batches.append(ids)
            records.append(
                {
                    "actual_tokens": len(ids),
                    "body_tokens_before": len(full),
                    "truncated": any(r["truncated"] for r in section_records),
                    "sections": section_records,
                    "input_sha256": hashlib.sha256(
                        json.dumps(ids).encode()
                    ).hexdigest(),
                }
            )
        length = max(map(len, batches))
        return {
            "input_ids": torch.tensor(
                [
                    [self.tokenizer.pad_token_id] * (length - len(b)) + b
                    for b in batches
                ],
                device=self.device,
            ),
            "attention_mask": torch.tensor(
                [[0] * (length - len(b)) + [1] * len(b) for b in batches],
                device=self.device,
            ),
        }, records

    def scores(self, texts, *, grad=False):
        import torch

        values, records = self.inputs(texts)
        self.forward_calls += 1
        with torch.set_grad_enabled(grad):
            # Qwen causal LM supports logits_to_keep: avoid allocating vocab logits at all positions.
            logits = self.model(**values, logits_to_keep=1).logits[:, -1, :]
            scores = (logits[:, self.yes] - logits[:, self.no]).float()
        if not torch.isfinite(scores).all():
            raise ValueError("nonfinite scores")
        return scores, records


def pairwise_loss(positive, negative, weight):
    import torch.nn.functional as F

    return -weight * F.logsigmoid(positive - negative).mean()


def train(config_path):
    import random
    import time

    import torch
    from peft import LoraConfig, get_peft_model

    config_path = Path(config_path)
    c = json.loads(config_path.read_text())
    output = Path(c["output"])
    output.mkdir(parents=True, exist_ok=False)
    rows = [
        json.loads(s) for s in Path(c["data"]).read_text().splitlines() if s.strip()
    ]
    if not rows or any(r["split"] != "rank-train" for r in rows):
        raise ValueError("nonempty rank-train-only data required")
    if any(
        r.get("label_source") not in {"model_judged_text", "observed_preference"}
        or not r.get("evidence_refs")
        or not 0 < r["weight"] <= 1
        for r in rows
    ):
        raise ValueError("explicit grounded preference labels required")
    torch.manual_seed(c.get("seed", 7170))
    random.seed(c.get("seed", 7170))
    ranker = Reranker(
        c["base"], device=c.get("device", "cpu"), max_length=c.get("max_length", 1024)
    )
    modules = sorted(
        {
            name.rsplit(".", 1)[-1]
            for name, _ in ranker.model.named_modules()
            if name.endswith(("q_proj", "v_proj"))
        }
    )
    if modules != ["q_proj", "v_proj"]:
        raise ValueError("expected observed Qwen projection modules unavailable")
    probe = [rows[0]["positive_text"], rows[0]["negative_text"]]
    before = ranker.scores(probe)[0].detach().cpu().tolist()
    ranker.model = get_peft_model(
        ranker.model,
        LoraConfig(
            r=c.get("rank", 8),
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=modules,
            task_type="CAUSAL_LM",
        ),
    )
    params = {n: p for n, p in ranker.model.named_parameters() if p.requires_grad}
    initial = {n: p.detach().cpu().clone() for n, p in params.items()}
    optimizer = torch.optim.AdamW(params.values(), lr=c.get("lr", 5e-5))
    trajectory = []
    start = time.monotonic()
    for epoch in range(c.get("epochs", 2)):
        order = list(range(len(rows)))
        random.shuffle(order)
        for index in order:
            row = rows[index]
            ranker.model.train()
            optimizer.zero_grad()
            values, _ = ranker.scores(
                [row["positive_text"], row["negative_text"]], grad=True
            )
            loss = pairwise_loss(values[0], values[1], row["weight"])
            loss.backward()
            norm = float(torch.nn.utils.clip_grad_norm_(params.values(), 1.0).cpu())
            if not torch.isfinite(loss) or not 0 < norm < float("inf"):
                raise ValueError("nonfinite loss or invalid gradient")
            optimizer.step()
            item = {
                "epoch": epoch,
                "row": index,
                "loss": float(loss.detach().cpu()),
                "gradient_norm": norm,
                "elapsed_seconds": time.monotonic() - start,
            }
            trajectory.append(item)
            with (output / "trajectory.jsonl").open("a") as stream:
                stream.write(json.dumps(item) + "\n")
            print(json.dumps(item), flush=True)
    ranker.model.eval()
    after, inputs = ranker.scores(probe)
    changed = sum(
        not torch.equal(initial[n], p.detach().cpu()) for n, p in params.items()
    )
    if not changed:
        raise ValueError("no trainable parameter changed")
    ranker.model.save_pretrained(output / "adapter", safe_serialization=True)
    evidence = {
        "template": TEMPLATE,
        "seed": c.get("seed", 7170),
        "families": len({r["repair_family"] for r in rows}),
        "pairs": len(rows),
        "steps": len(trajectory),
        "trainable_parameters": sum(p.numel() for p in params.values()),
        "changed_tensors": changed,
        "before": before,
        "after": after.detach().cpu().tolist(),
        "probe_texts": probe,
        "probe_inputs": inputs,
        "config": c,
        "reload": "PENDING",
        "utility": "NOT_MEASURED",
    }
    (output / "training.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def reload_probe(training_path):
    import math

    training_path = Path(training_path)
    evidence = json.loads(training_path.read_text())
    c = evidence["config"]
    ranker = Reranker(
        c["base"],
        device=c.get("device", "cpu"),
        max_length=c.get("max_length", 1024),
        adapter=training_path.parent / "adapter",
    )
    values, _ = ranker.scores(evidence["probe_texts"])
    actual = values.detach().cpu().tolist()
    if not all(
        math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
        for a, b in zip(actual, evidence["after"])
    ):
        raise ValueError("reload score mismatch")
    result = {
        "reload": "MATCHED",
        "scores": actual,
        "max_abs_error": max(abs(a - b) for a, b in zip(actual, evidence["after"])),
    }
    (training_path.parent / "reload.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result


SUPPORT_TEMPLATE = "text-help-structured-v2"
SUPPORT_INSTRUCTION = (
    "Judge textual applicability, not whether a skill alone solves the issue. "
    "Does the skill provide a concrete applicable procedure, implementation step, "
    "or verification check for this requirement under the known constraints? "
    "Generic encouragement is insufficient. Preserve negation, conditions and scope. "
    "Answer yes only when visible skill evidence supports a specific useful step "
    "and no necessary precondition conflicts; otherwise answer no."
)


def structured_representation(request, context, skill, *, support=True):
    return {
        "schema": SUPPORT_TEMPLATE,
        "instruction": SUPPORT_INSTRUCTION
        if support
        else "Rank relevance of this skill to the public task using the repository facts.",
        "task": request,
        "context": context["summary"],
        "metadata": skill["name"] + "\n" + skill.get("description", ""),
        "evidence": skill.get("body", ""),
    }


def structured_tokens(ranker, sections):
    """Program-owned sections; user marker text is never parsed as structure."""
    if sections.get("schema") != SUPPORT_TEMPLATE:
        raise ValueError("unsupported structured representation")
    names = ("instruction", "task", "context", "metadata", "evidence")
    tokenizer = ranker.tokenizer
    headers = [
        tokenizer.encode("\n[" + name.upper() + "]\n", add_special_tokens=False)
        for name in names
    ]
    tokens = [
        tokenizer.encode(sections[name], add_special_tokens=False) for name in names
    ]
    available = (
        ranker.max_length
        - len(ranker.prefix)
        - len(ranker.suffix)
        - sum(map(len, headers))
    )
    # Instruction and request must be intact for a supported decision. Allocate
    # the rest proportionally, then lend unused capacity in fixed order.
    caps = [
        len(tokens[0]),
        min(len(tokens[1]), max(0, min(available // 3, available - len(tokens[0])))),
        0,
        0,
        0,
    ]
    remainder = available - sum(caps)
    if remainder < 0:
        raise ValueError("instruction does not fit token budget")
    caps[2:5] = [int(remainder * 0.40), int(remainder * 0.10), 0]
    caps[4] = remainder - caps[2] - caps[3]
    caps = [min(cap, len(t)) for cap, t in zip(caps, tokens)]
    spare = available - sum(caps)
    for index in (1, 4, 2, 3):
        extra = min(spare, len(tokens[index]) - caps[index])
        caps[index] += extra
        spare -= extra
    body, records = [], []
    for name, header, ids, cap in zip(names, headers, tokens, caps):
        visible = ids[:cap]
        body.extend(header + visible)
        records.append(
            {
                "section": name,
                "tokens_before": len(ids),
                "tokens_used": cap,
                "truncated": cap < len(ids),
                "visible_text": tokenizer.decode(visible),
                "visible_token_ids": visible,
            }
        )
    ids = ranker.prefix + body + ranker.suffix
    return ids, {
        "schema": SUPPORT_TEMPLATE,
        "actual_tokens": len(ids),
        "body_tokens_before": sum(map(len, tokens)),
        "sections": records,
        "truncated": any(r["truncated"] for r in records),
        "request_complete": not records[1]["truncated"],
        "evidence_complete": not records[4]["truncated"],
        "input_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
    }
