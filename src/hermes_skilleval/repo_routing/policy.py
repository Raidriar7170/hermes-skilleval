"""One explicit routing entrypoint shared by maintenance replay and assist."""

import hashlib
import json
import time
from pathlib import Path

from .context import ContextBudget, digest, extract, shared_prompt
from .gate import decide, features
from .selector import Budget, select

POLICIES = ("native", "fixed", "strong", "repo-aware", "auto")


def read_config(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text())
    for key in ("encoder_path", "reranker_path", "adapter", "gate", "cache"):
        if value.get(key):
            p = Path(value[key])
            value[key] = str(p if p.is_absolute() else (path.parent / p).resolve())
    if value.get("schema") != "repo-routing-v1":
        raise ValueError("unsupported routing configuration")
    return value


def routing_version(config, registry):
    keys = (
        "encoder_revision",
        "reranker_revision",
        "adapter_sha256",
        "adapter_config_sha256",
        "max_length",
        "support_threshold",
        "budget",
        "selection_mode",
        "profile",
        "context_budget",
        "fixed_ids",
        "model_files",
    )
    source = {
        name: hashlib.sha256(
            Path(__file__).with_name(name + ".py").read_bytes()
        ).hexdigest()
        for name in ("context", "reranker", "selector", "support", "policy", "gate")
    }
    for relative in ("routers/skillrouter_open.py", "vendor/skillrouter_common.py"):
        source[relative] = hashlib.sha256(
            (Path(__file__).parent.parent / relative).read_bytes()
        ).hexdigest()
    return digest(
        {
            "config": {key: config.get(key) for key in keys},
            "registry_id": registry["registry_id"],
            "source": source,
        }
    )


def route(root, request, environment, registry, policy, config, *, repository=None):
    started = time.monotonic()
    if policy not in POLICIES:
        raise ValueError("unsupported policy")
    context = extract(
        Path(root),
        request,
        environment,
        ContextBudget(**config.get("context_budget", {})),
    )
    counts = {"heavy_constructors": 0, "encoder_queries": 0, "reranker_forwards": 0}
    decision = {
        "action": {
            "native": "N",
            "fixed": "F",
            "strong": "S",
            "repo-aware": "R",
            "auto": "N",
        }[policy],
        "fallback_reason": None,
    }
    r_version = routing_version(config, registry)
    if (
        config.get("r_version")
        and config["r_version"] != r_version
        and policy == "repo-aware"
    ):
        raise ValueError("frozen R implementation/configuration changed")
    if policy == "auto":
        if not config.get("gate") or not Path(config["gate"]).is_file():
            decision = {"action": "N", "fallback_reason": "gate_missing"}
        else:
            model = json.loads(Path(config["gate"]).read_text())
            resources = all(
                config.get(k) and Path(config[k]).is_dir()
                for k in ("encoder_path", "reranker_path", "adapter")
            )
            decision = decide(
                features(request, context),
                model,
                r_version,
                resources=resources,
                supported=context["supported"],
            )
    action = decision["action"]
    ids = [s["id"] for s in registry["skills"]]
    result = {
        "schema": "repo-routing-result-v1",
        "requested_policy": policy,
        "action": action,
        "decision": decision,
        "context": context,
        "features": features(request, context),
        "r_version": r_version,
        "registry_id": registry["registry_id"],
        "calls": counts,
        "timing": {},
        "agent_public_request": shared_prompt(request, context),
    }
    if action == "F":
        fixed = config.get("fixed_ids", ["cli-api-regression", "systematic-debugging"])
        if len(fixed) != 2 or len(set(fixed)) != 2 or not set(fixed) <= set(ids):
            raise ValueError("invalid frozen fixed set")
        ids = sorted(fixed)
    if action in ("S", "R"):
        from hermes_skilleval.routers.skillrouter_open import (
            OpenProfile,
            SkillRouterOpen,
        )
        from hermes_skilleval.vendor import skillrouter_common as ref

        profile = OpenProfile(**config.get("profile", {}))
        mark = time.monotonic()
        router = SkillRouterOpen(
            Path(config["encoder_path"]),
            Path(config["reranker_path"]),
            encoder_revision=config["encoder_revision"],
            reranker_revision=config["reranker_revision"],
            profile=profile,
        )
        counts["heavy_constructors"] += 1
        router.index(
            registry["skills"],
            Path(config["cache"]) if config.get("cache") else None,
            registry_id=registry["registry_id"],
        )
        result["timing"]["constructor_index_seconds"] = time.monotonic() - mark
        result["model_identity"] = router.identity
        if config.get("model_files") and any(
            router.identity[k]["files"] != config["model_files"][k]
            for k in ("encoder", "reranker")
        ):
            raise ValueError("frozen base model identity changed")
        mark = time.monotonic()
        vector = router.encode([ref.format_query(request, profile.query_chars)])
        counts["encoder_queries"] += 1
        sims = (vector @ router.vectors.T)[0].tolist()
        indices = sorted(
            range(len(sims)), key=lambda i: (-sims[i], registry["skills"][i]["id"])
        )[: profile.retrieval_top_k]
        candidates = [registry["skills"][i] for i in indices]
        result["retrieval"] = [
            {"id": registry["skills"][i]["id"], "score": sims[i]} for i in indices
        ]
        result["timing"]["retrieval_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        if action == "S":
            scores, inputs = router.rerank(request, candidates)
            counts["reranker_forwards"] += (
                len(candidates) + profile.batch_size - 1
            ) // profile.batch_size
            ids = [
                s["id"]
                for s, v in sorted(
                    zip(candidates, scores), key=lambda pair: (-pair[1], pair[0]["id"])
                )[:2]
            ]
            result["scores"] = {s["id"]: v for s, v in zip(candidates, scores)}
            result["inputs"] = inputs
        else:
            from .reranker import Reranker, representation

            if (
                not config.get("adapter")
                or not (Path(config["adapter"]) / "adapter_model.safetensors").is_file()
            ):
                raise ValueError("repo-aware requires trained adapter")
            actual = hashlib.sha256(
                (Path(config["adapter"]) / "adapter_model.safetensors").read_bytes()
            ).hexdigest()
            if (
                config.get("adapter_config_sha256")
                and hashlib.sha256(
                    (Path(config["adapter"]) / "adapter_config.json").read_bytes()
                ).hexdigest()
                != config["adapter_config_sha256"]
            ):
                raise ValueError("adapter configuration identity mismatch")
            if actual != config.get("adapter_sha256"):
                raise ValueError("adapter identity mismatch")
            # Release encoder before loading trained causal model.
            router.model = None
            import gc

            gc.collect()
            ranker = Reranker(
                config["reranker_path"],
                device=profile.device,
                max_length=config.get("max_length", 1024),
                adapter=config["adapter"],
            )
            counts["heavy_constructors"] += 1
            scores, inputs = [], []
            for skill in candidates:
                values, record = ranker.scores(
                    [representation(request, context, skill)]
                )
                scores.append(float(values.detach().cpu()[0]))
                inputs.extend(record)
            from .support import score_candidates

            clauses, items = score_candidates(
                request,
                context,
                candidates,
                scores,
                ranker,
                environment,
                config.get("support_threshold", 0.8),
            )
            selection = select(
                items,
                [1.0 / len(clauses)] * len(clauses),
                Budget(**config.get("budget", {})),
            )
            result["requirements"] = clauses
            if config.get("selection_mode", "budget") == "top2":
                compatible = {item["id"] for item in items if item["compatible"]}
                selection["skill_ids"] = [
                    skill["id"]
                    for skill, score in sorted(
                        zip(candidates, scores),
                        key=lambda pair: (-pair[1], pair[0]["id"]),
                    )
                    if skill["id"] in compatible
                ][:2]
                selection["mode"] = "top2_ablation"
                selection["objective"] = None
                selection["potential_load_tokens"] = sum(
                    item["tokens"]
                    for item in items
                    if item["id"] in selection["skill_ids"]
                )
            elif config.get("selection_mode", "budget") != "budget":
                raise ValueError("unknown selection mode")
            ids = selection["skill_ids"]
            if not ids:
                result["decision"]["fallback_reason"] = selection["fallback_reason"]
                result["action"] = "N"
                ids = [s["id"] for s in registry["skills"]]
            result.update(
                selection=selection,
                candidates=items,
                scores={s["id"]: v for s, v in zip(candidates, scores)},
                inputs=inputs,
                adapter_sha256=actual,
            )
            counts["reranker_forwards"] += ranker.forward_calls
        result["timing"]["reranker_selection_seconds"] = time.monotonic() - mark
    result["skill_ids"] = ids
    result["timing"]["route_wall_seconds"] = time.monotonic() - started
    result["context_digest"] = digest({k: v for k, v in context.items() if k != "cost"})
    return result
