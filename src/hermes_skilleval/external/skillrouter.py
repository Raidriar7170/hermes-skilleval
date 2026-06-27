from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from hermes_skilleval.provenance import _reject_sensitive_values
from hermes_skilleval.release_manifest import sha256_file


ADAPTER_VERSION = "v0.3.pr1"
TASK_ID_FIELDS = ("id", "task_id")
SKILL_ID_FIELDS = ("id", "skill_id")
QUERY_FIELDS = ("query", "prompt", "instruction")
TASK_TYPE_FIELDS = ("task_type", "type")
DESCRIPTION_FIELDS = ("description", "desc")
BODY_FIELDS = ("body", "content", "skill_body")
SOURCE_FIELDS = ("source", "source_path", "path")
RELEVANCE_FIELDS = ("relevance", "score", "grade")


@dataclass(frozen=True)
class ExternalTask:
    benchmark_id: str
    task_id: str
    query: str
    task_type: str
    graded_relevance: dict[str, float]
    tier: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ExternalSkill:
    benchmark_id: str
    skill_id: str
    name: str
    description: str
    body: str
    source: str | None
    tier: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ExternalRelevance:
    task_id: str
    skill_id: str
    relevance: float
    tier: str
    metadata: dict[str, Any]


class SkillRouterAdapter:
    def __init__(
        self,
        *,
        data_root: Path | str,
        benchmark_id: str = "skillrouter",
        upstream_repo: str = "zhengyanzhao1997/SkillRouter",
        upstream_ref: str = "FILL_BEFORE_RUN",
        license_note: str = "FILL_BEFORE_RUN",
        acquired_at: str | None = None,
        tiers: tuple[str, ...] = ("easy", "hard"),
    ) -> None:
        self.data_root = Path(data_root)
        self.benchmark_id = benchmark_id
        self.upstream_repo = upstream_repo
        self.upstream_ref = upstream_ref
        self.license_note = license_note
        self.acquired_at = acquired_at
        self.tiers = tiers

    def load_tasks(self) -> list[ExternalTask]:
        relevance_by_task: dict[str, dict[str, float]] = {}
        for relevance in self._iter_relevance():
            relevance_by_task.setdefault(relevance.task_id, {})[
                relevance.skill_id
            ] = relevance.relevance
        tasks = []
        for record in self._iter_records(self._tasks_path(), role="tasks"):
            task_id = _required_string(record, TASK_ID_FIELDS, "task id")
            query = _required_string(record, QUERY_FIELDS, "query")
            task_type = _optional_string(record, TASK_TYPE_FIELDS) or "unknown"
            tier = str(record.get("tier", "unknown"))
            metadata = _metadata_without(
                record,
                (*TASK_ID_FIELDS, *QUERY_FIELDS, *TASK_TYPE_FIELDS),
            )
            tasks.append(
                ExternalTask(
                    benchmark_id=self.benchmark_id,
                    task_id=task_id,
                    query=query,
                    task_type=task_type,
                    graded_relevance=dict(relevance_by_task.get(task_id, {})),
                    tier=tier,
                    metadata=metadata,
                )
            )
        return tasks

    def iter_skills(self, tier: str) -> Iterable[ExternalSkill]:
        for path in self._skill_files(tier):
            for record in self._iter_records(path, role=f"skills:{tier}"):
                skill_id = _required_string(record, SKILL_ID_FIELDS, "skill id")
                name = str(record.get("name") or skill_id)
                description = _optional_string(record, DESCRIPTION_FIELDS) or ""
                body = _optional_string(record, BODY_FIELDS) or ""
                source = _optional_string(record, SOURCE_FIELDS)
                record_tier = str(record.get("tier", tier))
                metadata = _metadata_without(
                    record,
                    (
                        *SKILL_ID_FIELDS,
                        "name",
                        *DESCRIPTION_FIELDS,
                        *BODY_FIELDS,
                        *SOURCE_FIELDS,
                    ),
                )
                yield ExternalSkill(
                    benchmark_id=self.benchmark_id,
                    skill_id=skill_id,
                    name=name,
                    description=description,
                    body=body,
                    source=source,
                    tier=record_tier,
                    metadata=metadata,
                )

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        tasks: list[ExternalTask] = []
        relevance: list[ExternalRelevance] = []
        skill_ids_by_tier: dict[str, set[str]] = {}
        skill_counts: dict[str, int] = {}

        try:
            relevance = list(self._iter_relevance())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
        try:
            tasks = self.load_tasks()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

        seen_tasks: set[str] = set()
        for task in tasks:
            if task.task_id in seen_tasks:
                errors.append(f"duplicate task id: {task.task_id}")
            seen_tasks.add(task.task_id)
            if not task.query.strip():
                errors.append(f"empty query for task: {task.task_id}")
            if not task.graded_relevance:
                errors.append(f"missing relevance for task: {task.task_id}")

        task_ids = {task.task_id for task in tasks}
        for tier in self.tiers:
            ids: set[str] = set()
            count = 0
            try:
                for skill in self.iter_skills(tier):
                    count += 1
                    if skill.tier != tier:
                        errors.append(
                            f"tier mismatch for skill {skill.skill_id}: "
                            f"expected {tier}, got {skill.tier}"
                        )
                    if skill.skill_id in ids:
                        errors.append(f"duplicate skill id in tier {tier}: {skill.skill_id}")
                    ids.add(skill.skill_id)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
            skill_ids_by_tier[tier] = ids
            skill_counts[tier] = count

        for item in relevance:
            if item.task_id not in task_ids:
                errors.append(f"relevance references missing task: {item.task_id}")
            if item.skill_id not in skill_ids_by_tier.get(item.tier, set()):
                errors.append(
                    "relevant skill missing from tier "
                    f"{item.tier}: {item.task_id} -> {item.skill_id}"
                )
        if self.upstream_ref == "FILL_BEFORE_RUN":
            errors.append("upstream_ref must be set before external validation")
        if self.license_note == "FILL_BEFORE_RUN":
            errors.append("license_note must be set before external validation")

        return {
            "schema_version": "v0.3.external-validation.v1",
            "benchmark_id": self.benchmark_id,
            "status": "INVALID" if errors else "PASS",
            "errors": errors,
            "task_count": len(tasks),
            "skill_count_by_tier": skill_counts,
            "relevance_count": len(relevance),
        }

    def provenance(self, validation: dict[str, Any] | None = None) -> dict[str, Any]:
        validation_status = validation["status"] if validation else self.validate()["status"]
        manifest = {
            "schema_version": "v0.3.external-run-manifest.v1",
            "adapter": "skillrouter",
            "adapter_version": ADAPTER_VERSION,
            "benchmark_id": self.benchmark_id,
            "upstream_repo": self.upstream_repo,
            "upstream_ref": self.upstream_ref,
            "license_note": self.license_note,
            "acquired_at": self.acquired_at,
            "data_root_label": self.data_root.name,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "tiers": list(self.tiers),
            "files": self._file_records(),
            "mapping": {
                "task_id": list(TASK_ID_FIELDS),
                "skill_id": list(SKILL_ID_FIELDS),
                "query": list(QUERY_FIELDS),
                "task_type": list(TASK_TYPE_FIELDS),
                "relevance": list(RELEVANCE_FIELDS),
            },
            "validation_status": validation_status,
        }
        _reject_sensitive_values(manifest)
        return manifest

    def _tasks_path(self) -> Path:
        return _first_existing(
            self.data_root,
            ("tasks.jsonl", "tasks.json", "tasks.jsonl.gz"),
            "tasks",
        )

    def _relevance_path(self) -> Path:
        return _first_existing(
            self.data_root,
            ("relevance.jsonl", "relevance.json", "relevance.jsonl.gz"),
            "relevance",
        )

    def _skill_files(self, tier: str) -> list[Path]:
        root = self.data_root / "skills"
        candidates = [
            root / f"{tier}.jsonl",
            root / f"{tier}.json",
            root / f"{tier}.jsonl.gz",
            root / tier,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return [candidate]
            if candidate.is_dir():
                files = sorted(
                    path
                    for path in candidate.rglob("*")
                    if path.is_file()
                    and path.suffix in {".json", ".jsonl", ".gz"}
                    and (
                        path.name.endswith(".json")
                        or path.name.endswith(".jsonl")
                        or path.name.endswith(".jsonl.gz")
                    )
                )
                if files:
                    return files
        raise ValueError(f"missing skill shard for tier {tier} under skills")

    def _iter_relevance(self) -> Iterable[ExternalRelevance]:
        for record in self._iter_records(self._relevance_path(), role="relevance"):
            task_id = _required_string(record, ("task_id",), "relevance task_id")
            skill_id = _required_string(record, ("skill_id",), "relevance skill_id")
            relevance = _required_number(record, RELEVANCE_FIELDS, "relevance")
            tier = str(record.get("tier", "unknown"))
            yield ExternalRelevance(
                task_id=task_id,
                skill_id=skill_id,
                relevance=float(relevance),
                tier=tier,
                metadata=_metadata_without(
                    record,
                    ("task_id", "skill_id", *RELEVANCE_FIELDS, "tier"),
                ),
            )

    def _iter_records(self, path: Path, *, role: str) -> Iterable[dict[str, Any]]:
        path_label = self._path_label(path)
        try:
            if path.name.endswith(".jsonl.gz"):
                with gzip.open(path, "rt", encoding="utf-8") as file:
                    yield from _iter_jsonl_file(file, path_label, role=role)
            elif path.suffix == ".jsonl":
                with path.open("r", encoding="utf-8") as file:
                    yield from _iter_jsonl_file(file, path_label, role=role)
            elif path.suffix == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    for item in payload:
                        if not isinstance(item, dict):
                            raise ValueError(
                                f"{path_label} {role} records must be objects"
                            )
                        yield item
                elif isinstance(payload, dict):
                    records = payload.get("records") or payload.get(role.split(":")[0])
                    if not isinstance(records, list):
                        raise ValueError(f"{path_label} must contain a list of records")
                    for item in records:
                        if not isinstance(item, dict):
                            raise ValueError(
                                f"{path_label} {role} records must be objects"
                            )
                        yield item
                else:
                    raise ValueError(f"{path_label} must contain JSON object or array")
            else:
                raise ValueError(f"unsupported file type for {role}: {path_label}")
        except OSError as exc:
            raise ValueError(
                f"failed to read {role} file {path_label}: {exc}"
            ) from exc

    def _file_records(self) -> list[dict[str, Any]]:
        records = []
        for role, resolve_path in (
            ("tasks", self._tasks_path),
            ("relevance", self._relevance_path),
        ):
            try:
                records.append(self._file_record(resolve_path(), role))
            except (OSError, ValueError) as exc:
                records.append(_missing_file_record(role, exc))
        for tier in self.tiers:
            role = f"skills:{tier}"
            try:
                paths = self._skill_files(tier)
            except (OSError, ValueError) as exc:
                records.append(_missing_file_record(role, exc))
                continue
            for path in paths:
                records.append(self._file_record(path, role))
        return records

    def _file_record(self, path: Path, role: str) -> dict[str, Any]:
        record: dict[str, Any] = {
            "path": self._path_label(path),
            "role": role,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "record_count": None,
        }
        try:
            record["record_count"] = sum(1 for _ in self._iter_records(path, role=role))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            record["read_error"] = str(exc)
        return record

    def _path_label(self, path: Path) -> str:
        try:
            return path.relative_to(self.data_root).as_posix()
        except ValueError:
            return path.name


def write_external_validation(
    *,
    data_root: Path | str,
    output_dir: Path | str,
    benchmark: str = "skillrouter",
    upstream_ref: str = "FILL_BEFORE_RUN",
    license_note: str = "FILL_BEFORE_RUN",
    acquired_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if benchmark != "skillrouter":
        raise ValueError(f"unsupported external benchmark: {benchmark}")
    adapter = SkillRouterAdapter(
        data_root=data_root,
        benchmark_id=benchmark,
        upstream_ref=upstream_ref,
        license_note=license_note,
        acquired_at=acquired_at,
    )
    validation = adapter.validate()
    manifest = adapter.provenance(validation)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if validation["status"] != "PASS":
        raise ValueError("external validation failed")
    return manifest, validation


def _iter_jsonl_file(file: Any, path_label: str, *, role: str) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(file, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"malformed JSONL in {path_label}:{line_number}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise ValueError(
                f"{path_label}:{line_number} {role} record must be an object"
            )
        yield record


def _first_existing(root: Path, names: tuple[str, ...], role: str) -> Path:
    for name in names:
        path = root / name
        if path.exists():
            return path
    raise ValueError(f"missing {role} file under <data-root>")


def _required_string(record: dict[str, Any], fields: tuple[str, ...], label: str) -> str:
    value = _first_present(record, fields)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_string(record: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    value = _first_present(record, fields)
    return value if isinstance(value, str) else None


def _required_number(record: dict[str, Any], fields: tuple[str, ...], label: str) -> float:
    value = _first_present(record, fields)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def _first_present(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in record:
            return record[field]
    return None


def _metadata_without(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    excluded = set(fields)
    return {key: value for key, value in record.items() if key not in excluded}


def _missing_file_record(role: str, exc: Exception) -> dict[str, Any]:
    return {
        "path": None,
        "role": role,
        "size_bytes": 0,
        "sha256": None,
        "record_count": None,
        "read_error": str(exc),
    }
