"""Thin runtime-utility entrypoints on the existing parser, router, and runner."""

from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path

from hermes_skilleval.models import BenchmarkTask, Skill
from hermes_skilleval.routers.embedding import (
    EmbeddingRouter,
    SentenceTransformerEmbeddingModel,
    _skill_text,
)
from hermes_skilleval.skill_package import package_manifest
from hermes_skilleval.skill_parser import parse_skill_file


def validate_registry_projection(pool: list[dict], registry: dict) -> str:
    """Bind the actual indexed projection to the complete-package registry."""
    if hashlib.sha256(json.dumps(registry['skills'], sort_keys=True).encode()).hexdigest() != registry['registry_id']:
        raise ValueError('registry digest mismatch')
    keys = [k for k in Skill.__dataclass_fields__ if k != 'path'] + ['package_sha256']
    project = lambda rows: [{k: row[k] for k in keys} for row in rows]
    if project(pool) != project(registry['skills']):
        raise ValueError('indexed pool differs from registry')
    return registry['registry_id']


def load_registry(path: Path, assets: Path) -> tuple[dict, list[Skill]]:
    registry = json.loads(path.read_text())
    if (
        hashlib.sha256(
            json.dumps(registry["skills"], sort_keys=True).encode()
        ).hexdigest()
        != registry["registry_id"]
    ):
        raise ValueError("registry digest mismatch")
    skills = []
    for row in registry["skills"]:
        root = assets / row["package_path"]
        if not root.resolve().is_relative_to(assets.resolve()):
            raise ValueError("skill package escapes asset root")
        if package_manifest(root)["sha256"] != row["package_sha256"]:
            raise ValueError("SKILL_PACKAGE_UNAVAILABLE: " + row["id"])
        parsed = parse_skill_file(root / "SKILL.md", root.parent)
        if any(
            getattr(parsed, k) != row[k] for k in ("id", "name", "description", "body")
        ):
            raise ValueError("registry text differs from complete skill package")
        fields = {k: row[k] for k in Skill.__dataclass_fields__}
        fields["path"] = str(root / "SKILL.md")
        skills.append(Skill(**fields))
    return registry, skills


def recommend(
    *,
    prompt: str,
    registry_path: Path,
    assets: Path,
    model_path: Path | None = None,
    top_k: int = 2,
    cache_path: Path | None = None,
    backend: str = "sentence-transformers",
    open_config: dict | None = None,
    selection_policy: str = "topk",
    selection_config: dict | None = None,
) -> dict:
    from hermes_skilleval.skill_selection import SelectionConfig, bind_snapshot, select
    policy_config = SelectionConfig(**(selection_config or {}))
    if selection_policy not in ("topk", "dedup", "complementary"):
        raise ValueError("invalid selection policy")
    if backend != "skillrouter-open" and (selection_policy != "topk" or selection_config):
        raise ValueError("set selection requires SkillRouterOpen")
    started = time.perf_counter()
    registry, skills = load_registry(registry_path, assets)
    if backend == "skillrouter-open":
        from dataclasses import asdict
        from hermes_skilleval.routers.skillrouter_open import OpenProfile, SkillRouterOpen

        config = dict(open_config or {})
        profile = OpenProfile(**config.pop("profile", {}))
        constructor_start = time.perf_counter()
        router = SkillRouterOpen(profile=profile, **config)
        constructor_seconds = time.perf_counter() - constructor_start
        router.index([asdict(s) for s in skills], cache_path, registry_id=registry["registry_id"])
        result = router.recommend(prompt, top_k)
        result["timing"]["constructor_seconds"] = constructor_seconds
        result["timing"]["initialization_id"] = router.index_key
        result = bind_snapshot(result, prompt, registry["registry_id"])
        selection = select(prompt=prompt, snapshot=result, registry=registry, policy=selection_policy, k=top_k, config=policy_config)
        result["selection"] = selection
        result["skill_ids"] = selection["skill_ids"]
        return result
    if backend != "sentence-transformers" or model_path is None:
        raise ValueError("known backend and real model configuration required")
    model = SentenceTransformerEmbeddingModel(
        str(model_path), device="cpu", local_files_only=True
    )
    router = EmbeddingRouter(model=model, cache_path=cache_path)
    router._skill_vectors(skills)  # Build outside the measured per-request route.
    index_seconds = time.perf_counter() - started
    task = BenchmarkTask(
        "request", "unspecified", "unspecified", prompt, [], [], "external"
    )
    result = router.route(task, skills, top_k)
    token_lengths = {
        s.id: len(model.model.tokenizer.encode(_skill_text(s), truncation=False))
        for s in skills
    }
    return {
        "actual_router": "sentence-transformers",
        "model_identity": model.cache_key,
        "model_path": str(model_path),
        "registry_id": registry["registry_id"],
        "decision": "CANDIDATES",
        "skill_ids": result.selected_skill_ids,
        "candidate_budget": top_k,
        "fallback": False,
        "scores": result.scores,
        "route_ms": result.latency_ms,
        "index_and_load_seconds": index_seconds,
        "max_seq_length": model.max_seq_length,
        "truncated_skills": {
            k: v
            for k, v in token_lengths.items()
            if model.max_seq_length is not None and v > model.max_seq_length
        },
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--model", type=Path)
    p.add_argument("--backend", choices=["sentence-transformers", "skillrouter-open"], default="sentence-transformers")
    p.add_argument("--open-config", type=Path)
    p.add_argument("--prompt", required=True)
    p.add_argument("--top-k", type=int, default=2)
    p.add_argument("--cache", type=Path)
    p.add_argument("--selection-policy", choices=["topk", "dedup", "complementary"], default="topk")
    p.add_argument("--selection-config", type=Path)
    args = p.parse_args()
    print(
        json.dumps(
            recommend(
                prompt=args.prompt,
                registry_path=args.registry,
                assets=args.assets,
                model_path=args.model,
                top_k=args.top_k,
                cache_path=args.cache,
                backend=args.backend,
                selection_policy=args.selection_policy,
                selection_config=json.loads(args.selection_config.read_text()) if args.selection_config else None,
                open_config=json.loads(args.open_config.read_text()) if args.open_config else None,
            ),
            indent=2,
        )
    )


def manufacturing_completeness(source: Path, output: Path) -> dict:
    """Check every requested record, without inventing semantic gold labels."""
    import csv

    logs = {
        r["record_id"]: r
        for r in csv.DictReader((source / "test_center_logs.csv").open())
    }
    books = {}
    for file in source.glob("codebook_*.csv"):
        for row in csv.DictReader(file.open()):
            books[(row["product_id"], row["code"])] = row["standard_label"]
    data = json.loads(output.read_text())
    records = data.get("records", []) if isinstance(data, dict) else []
    if len(records) != len(logs) or {r.get("record_id") for r in records} != set(logs):
        raise ValueError("all original records must appear exactly once")
    for record in records:
        original = logs[record["record_id"]]
        for key in ("product_id", "station", "engineer_id", "raw_reason_text"):
            if record.get(key) != original[key]:
                raise ValueError("record metadata differs from original input")
        segments = record.get("normalized")
        if not isinstance(segments, list) or not segments:
            raise ValueError("every record must contain a nonempty normalized list")
        for index, segment in enumerate(segments, 1):
            if segment.get("segment_id") != f"{record['record_id']}-S{index}":
                raise ValueError("segment ID mismatch")
            span = segment.get("span_text")
            if (
                not isinstance(span, str)
                or not span
                or span not in original["raw_reason_text"]
            ):
                raise ValueError("segment must refer to original input text")
            code = segment.get("pred_code")
            if code == "UNKNOWN":
                if segment.get("pred_label") != "":
                    raise ValueError("unknown label must be empty")
            elif (original["product_id"], code) not in books or segment.get(
                "pred_label"
            ) != books[(original["product_id"], code)]:
                raise ValueError("code or label is outside product codebook")
    return {
        "records_checked": len(records),
        "semantic_accuracy": "NOT_INDEPENDENTLY_LABELED",
    }


if __name__ == "__main__":
    main()
