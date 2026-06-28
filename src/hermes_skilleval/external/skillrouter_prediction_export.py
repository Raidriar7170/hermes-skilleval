from __future__ import annotations

import gzip
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Protocol

from hermes_skilleval.external.skillrouter import ExternalSkill, SkillRouterAdapter
from hermes_skilleval.external.skillrouter_matrix import build_field_view
from hermes_skilleval.provenance import _reject_sensitive_values
from hermes_skilleval.release_manifest import sha256_file
from hermes_skilleval.routers.embedding import _cosine


EXPORT_SCHEMA = "v0.3.skillrouter-prediction-export-manifest.v1"
PREDICTION_SCHEMA = "skillrouter.scorer.predictions.v1"
MIN_TOP_K = 50
QUERY_FIELDS = ("instruction_text", "query", "prompt", "instruction")
TASK_ID_FIELDS = ("id", "task_id")
SUPPORTED_TIERS = {"easy", "hard"}
SUPPORTED_FIELD_VIEWS = {"name_only", "metadata", "full_body"}
SUPPORTED_ROUTERS = {"baseline-minilm", "finetuned-embedding"}
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
IMMUTABLE_REVISION_RE = re.compile(r"^[0-9a-fA-F]{40}([0-9a-fA-F]{24})?$")
DIRTY_PATH_PREFIXES = ("src/", "tests/", "scripts/", "docs/", "openspec/")
DIRTY_PATH_NAMES = {"README.md", "pyproject.toml"}


class BatchEmbeddingModel(Protocol):
    cache_key: str

    def encode_batch(self, texts: Iterable[str]) -> list[list[float]]:
        raise NotImplementedError


@dataclass(frozen=True)
class FrozenRouterConfig:
    router_id: str
    field_view: str
    tier: str
    model_name: str
    model_revision: str | None = None
    config_id: str | None = None
    checkpoint_path: str | None = None
    checkpoint_sha256: str | None = None


@dataclass(frozen=True)
class _TaskRecord:
    task_id: str
    query: str


class _SentenceTransformerBatchModel:
    def __init__(self, *, model_name: str, revision: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "sentence-transformers is required to export baseline-minilm predictions"
            ) from exc

        kwargs = {"revision": revision} if revision else {}
        self.model = SentenceTransformer(model_name, **kwargs)
        self.cache_key = f"sentence-transformers:{model_name}@{revision or 'unversioned'}"

    def encode_batch(self, texts: Iterable[str]) -> list[list[float]]:
        embeddings = self.model.encode(list(texts), normalize_embeddings=True)
        result = []
        for vector in embeddings:
            if hasattr(vector, "tolist"):
                vector = vector.tolist()
            result.append([float(item) for item in vector])
        return result


def write_skillrouter_prediction_artifacts(
    *,
    data_root: Path | str,
    output_dir: Path | str,
    run_id: str,
    configs: Iterable[FrozenRouterConfig],
    top_k: int = MIN_TOP_K,
    command: list[str] | None = None,
    embedding_model: BatchEmbeddingModel | None = None,
    embedding_backend: str | None = None,
    final_evidence: bool = False,
) -> dict[str, Any]:
    if top_k < MIN_TOP_K:
        raise ValueError(f"top_k must be at least {MIN_TOP_K}")

    frozen_configs = list(configs)
    _assert_unique_config_ids(frozen_configs)
    root = Path(data_root)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    tasks_path = _tasks_path(root)
    tasks = _load_task_records(tasks_path)
    task_ids = {task.task_id for task in tasks}
    code_state = _git_state()
    if final_evidence and code_state.get("dirty_paths"):
        raise ValueError(
            "production prediction export requires clean source/config/test paths: "
            + ", ".join(code_state["dirty_paths"])
        )
    backend = _embedding_backend_label(
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
    )

    manifest = {
        "schema_version": EXPORT_SCHEMA,
        "run_id": _non_empty(run_id, "run_id"),
        "generated_at": _now(),
        "code": code_state,
        "data_root": str(root),
        "task_input": _task_input_record(tasks_path, root, len(tasks)),
        "top_k": top_k,
        "command": list(command or []),
        "final_evidence": final_evidence,
        "relevance_labels_read": False,
        "scope_guards": {
            "no_training": True,
            "no_threshold_tuning": True,
            "no_hard_negative_mining": True,
            "no_new_router_variants": True,
            "no_scorer_matrix_gate_changes": True,
            "prediction_generation_reads_relevance_labels": False,
        },
        "artifacts": [],
    }

    for config in frozen_configs:
        normalized = _normalize_config(config)
        availability = _router_availability(
            normalized,
            embedding_backend=backend,
            injected_model=embedding_model is not None,
        )
        artifact_base = _artifact_record(
            normalized,
            output_root,
            top_k,
            embedding_backend=backend,
        )
        if availability["status"] != "PASS":
            manifest["artifacts"].append(artifact_base | availability)
            continue

        model = embedding_model or _load_model(normalized)
        skills = _load_tier_skills(root, normalized.tier)
        predictions = _rank_tasks(
            tasks=tasks,
            skills=skills,
            field_view=normalized.field_view,
            model=model,
            top_k=top_k,
        )
        output_path = _prediction_output_path(output_root, normalized.config_id)
        write_skillrouter_prediction_file(
            output_path=output_path,
            predictions=predictions,
            task_ids=task_ids,
            tier_skill_ids={skill.skill_id for skill in skills},
        )
        file_record = _prediction_file_record(output_path)
        manifest["artifacts"].append(
            artifact_base
            | {
                "status": "PASS",
                "output_path": str(output_path),
                "sha256": file_record["sha256"],
                "size_bytes": file_record["size_bytes"],
                "candidate_pool": _candidate_pool_record(root, normalized.tier),
                "model": _model_record(normalized, model),
            }
        )

    manifest_path = output_root / "manifest.json"
    _reject_sensitive_values(manifest)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_skillrouter_prediction_file(
    *,
    output_path: Path | str,
    predictions: dict[str, list[str]],
    task_ids: set[str],
    tier_skill_ids: set[str],
) -> None:
    normalized: dict[str, list[str]] = {}
    for task_id in sorted(predictions):
        if task_id not in task_ids:
            raise ValueError(f"unknown prediction task id: {task_id}")
        ranking = []
        seen: set[str] = set()
        for skill_id in predictions[task_id]:
            if skill_id not in tier_skill_ids:
                raise ValueError(f"unknown predicted skill id: {task_id} -> {skill_id}")
            if skill_id not in seen:
                seen.add(skill_id)
                ranking.append(skill_id)
        normalized[task_id] = ranking

    missing = sorted(task_ids - set(normalized))
    if missing:
        raise ValueError(f"missing predictions for task ids: {', '.join(missing)}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rank_tasks(
    *,
    tasks: list[_TaskRecord],
    skills: list[ExternalSkill],
    field_view: str,
    model: BatchEmbeddingModel,
    top_k: int,
) -> dict[str, list[str]]:
    if not skills:
        raise ValueError("candidate skill pool is empty")
    unique_skills = _unique_skills(skills)
    task_vectors = model.encode_batch(task.query for task in tasks)
    skill_texts = [build_field_view(skill, field_view)["text"] for skill in unique_skills]
    skill_vectors = model.encode_batch(skill_texts)
    predictions: dict[str, list[str]] = {}
    for task, task_vector in zip(tasks, task_vectors, strict=True):
        scored = [
            (skill.skill_id, _cosine(task_vector, skill_vector))
            for skill, skill_vector in zip(unique_skills, skill_vectors, strict=True)
        ]
        ranked = sorted(scored, key=lambda item: (-item[1], item[0]))
        predictions[task.task_id] = [skill_id for skill_id, _ in ranked[:top_k]]
    return predictions


def _tasks_path(data_root: Path) -> Path:
    return _first_existing(data_root / "tasks.jsonl", data_root / "tasks" / "tasks.jsonl")


def _load_task_records(path: Path) -> list[_TaskRecord]:
    tasks = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            task_id = _required_string(record, TASK_ID_FIELDS, f"{path}:{line_number} task id")
            query = _required_string(record, QUERY_FIELDS, f"{path}:{line_number} query")
            if task_id in seen:
                raise ValueError(f"duplicate task id: {task_id}")
            seen.add(task_id)
            tasks.append(_TaskRecord(task_id=task_id, query=query))
    if not tasks:
        raise ValueError(f"no tasks found in {path}")
    return tasks


def _load_tier_skills(data_root: Path, tier: str) -> list[ExternalSkill]:
    return list(SkillRouterAdapter(data_root=data_root, tiers=(tier,)).iter_skills(tier))


def _normalize_config(config: FrozenRouterConfig) -> FrozenRouterConfig:
    router_id = _non_empty(config.router_id, "router_id")
    field_view = _non_empty(config.field_view, "field_view")
    tier = _non_empty(config.tier, "tier")
    if field_view not in SUPPORTED_FIELD_VIEWS:
        raise ValueError(f"unsupported field_view: {field_view}")
    if tier not in SUPPORTED_TIERS:
        raise ValueError(f"unsupported candidate tier: {tier}")
    config_id = config.config_id or f"{router_id}__{field_view}__{tier}"
    _safe_config_id(config_id)
    return FrozenRouterConfig(
        router_id=router_id,
        config_id=config_id,
        field_view=field_view,
        tier=tier,
        model_name=_non_empty(config.model_name, "model_name"),
        model_revision=config.model_revision,
        checkpoint_path=config.checkpoint_path,
        checkpoint_sha256=config.checkpoint_sha256,
    )


def _router_availability(
    config: FrozenRouterConfig,
    *,
    embedding_backend: str,
    injected_model: bool,
) -> dict[str, Any]:
    if config.router_id not in SUPPORTED_ROUTERS:
        return {
            "status": "UNAVAILABLE",
            "reason": f"unsupported frozen router_id: {config.router_id}",
        }
    if embedding_backend == "hashing" and config.router_id in {
        "baseline-minilm",
        "finetuned-embedding",
    }:
        return {
            "status": "UNAVAILABLE",
            "reason": (
                "hashing backend cannot produce final baseline-minilm or "
                "finetuned-embedding prediction artifacts"
            ),
        }
    if config.router_id == "baseline-minilm":
        if not config.model_revision:
            return {
                "status": "UNAVAILABLE",
                "reason": "baseline-minilm requires a provenance-pinned model revision",
            }
        if not injected_model and not _is_immutable_revision(config.model_revision):
            return {
                "status": "UNAVAILABLE",
                "reason": "baseline-minilm model revision must be an immutable commit SHA",
            }
        return {"status": "PASS"}
    if config.router_id == "finetuned-embedding":
        if not config.checkpoint_path:
            return {
                "status": "UNAVAILABLE",
                "reason": "finetuned-embedding checkpoint_path is not configured",
            }
        checkpoint = Path(config.checkpoint_path)
        if not checkpoint.exists():
            return {
                "status": "UNAVAILABLE",
                "reason": f"finetuned-embedding checkpoint_path does not exist: {checkpoint}",
            }
        actual = _path_sha256(checkpoint)
        if config.checkpoint_sha256 and config.checkpoint_sha256 != actual:
            return {
                "status": "UNAVAILABLE",
                "reason": "finetuned-embedding checkpoint sha256 mismatch",
                "model": _checkpoint_hash_record(config, actual),
            }
        return {"status": "PASS"}
    raise AssertionError("unreachable")


def _load_model(config: FrozenRouterConfig) -> BatchEmbeddingModel:
    model_name = config.checkpoint_path if config.checkpoint_path else config.model_name
    return _SentenceTransformerBatchModel(
        model_name=_non_empty(model_name, "model_name"),
        revision=config.model_revision,
    )


def _model_record(config: FrozenRouterConfig, model: BatchEmbeddingModel) -> dict[str, Any]:
    record: dict[str, Any] = {
        "model_name": config.model_name,
        "model_revision": config.model_revision,
        "embedding_cache_key": getattr(model, "cache_key", None),
    }
    if config.checkpoint_path:
        checkpoint = Path(config.checkpoint_path)
        record["checkpoint_path"] = str(checkpoint)
        record.update(_checkpoint_hash_record(config, _path_sha256(checkpoint)))
    return record


def _artifact_record(
    config: FrozenRouterConfig,
    output_root: Path,
    top_k: int,
    *,
    embedding_backend: str,
) -> dict[str, Any]:
    return {
        "router_id": config.router_id,
        "config_id": config.config_id,
        "router_family": "embedding",
        "embedding_backend": embedding_backend,
        "field_view": config.field_view,
        "text_builder": {
            "name": "skillrouter-field-view",
            "field_view": config.field_view,
            "builder_version": "v0.3.pr3.field-view.v1",
        },
        "candidate_tier": config.tier,
        "top_k": top_k,
        "intended_output_path": str(_prediction_output_path(output_root, config.config_id)),
    }

def _embedding_backend_label(
    *,
    embedding_backend: str | None,
    embedding_model: BatchEmbeddingModel | None,
) -> str:
    if embedding_backend:
        return embedding_backend
    if embedding_model is not None:
        return "test-injected"
    return "sentence-transformers"


def _task_input_record(path: Path, root: Path, task_count: int) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "task_count": task_count,
    }


def _candidate_pool_record(data_root: Path, tier: str) -> dict[str, Any]:
    files = [_file_record(path, data_root) for path in _skill_files(data_root, tier)]
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "tier": tier,
        "sha256": digest,
        "size_bytes": sum(record["size_bytes"] for record in files),
        "files": files,
    }


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _prediction_file_record(path: Path) -> dict[str, Any]:
    return {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def _skill_files(data_root: Path, tier: str) -> list[Path]:
    tier_dir = _first_existing(data_root / tier, data_root / "skills" / tier)
    files = sorted([*tier_dir.glob("*.jsonl"), *tier_dir.glob("*.jsonl.gz")])
    if not files:
        raise ValueError(f"missing skill shard files for tier: {tier}")
    return files


def _unique_skills(skills: Iterable[ExternalSkill]) -> list[ExternalSkill]:
    by_id: dict[str, ExternalSkill] = {}
    for skill in skills:
        by_id.setdefault(skill.skill_id, skill)
    return [by_id[skill_id] for skill_id in sorted(by_id)]


def _path_sha256(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    records = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        records.append(
            {
                "path": child.relative_to(path).as_posix(),
                "sha256": sha256_file(child),
                "size_bytes": child.stat().st_size,
            }
        )
    return hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _checkpoint_hash_record(
    config: FrozenRouterConfig,
    actual_sha256: str,
) -> dict[str, Any]:
    return {
        "provided_checkpoint_sha256": config.checkpoint_sha256,
        "actual_checkpoint_sha256": actual_sha256,
        "checkpoint_hash_verified": (
            config.checkpoint_sha256 is not None
            and config.checkpoint_sha256 == actual_sha256
        ),
    }


def _prediction_output_path(output_root: Path, config_id: str | None) -> Path:
    safe_id = _safe_config_id(_non_empty(config_id, "config_id"))
    return output_root / f"{safe_id}.predictions.json"


def _safe_config_id(config_id: str) -> str:
    if not SAFE_FILENAME_RE.match(config_id):
        raise ValueError(f"config_id contains unsafe characters: {config_id}")
    return config_id


def _assert_unique_config_ids(configs: list[FrozenRouterConfig]) -> None:
    seen: set[str] = set()
    for config in configs:
        config_id = config.config_id or f"{config.router_id}__{config.field_view}__{config.tier}"
        if config_id in seen:
            raise ValueError(f"duplicate config_id: {config_id}")
        seen.add(config_id)


def _first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise ValueError(f"missing required path; checked: {', '.join(str(path) for path in paths)}")


def _required_string(record: dict[str, Any], fields: tuple[str, ...], label: str) -> str:
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError(f"missing {label}")


def _non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        tag = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--",
                "src",
                "tests",
                "scripts",
                "docs",
                "openspec",
                "pyproject.toml",
                "README.md",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        dirty_paths = _dirty_code_paths(status.stdout.splitlines())
        return {
            "commit": commit,
            "tag": tag.stdout.strip() or None,
            "dirty": bool(dirty_paths),
            "dirty_paths": dirty_paths,
        }
    except (OSError, subprocess.CalledProcessError):
        return {
            "commit": "UNAVAILABLE",
            "tag": None,
            "dirty": "UNAVAILABLE",
            "dirty_paths": [],
        }


def _dirty_code_paths(status_lines: Iterable[str]) -> list[str]:
    paths: list[str] = []
    for line in status_lines:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        path = path.strip('"')
        if path.startswith(DIRTY_PATH_PREFIXES) or path in DIRTY_PATH_NAMES:
            paths.append(path)
    return paths


def _is_immutable_revision(revision: str | None) -> bool:
    return isinstance(revision, str) and IMMUTABLE_REVISION_RE.fullmatch(revision) is not None


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
