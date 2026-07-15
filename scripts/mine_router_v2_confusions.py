from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol

from hermes_skilleval.router_v2_training_pilot import (
    MODEL_ID,
    MODEL_REVISION,
    PR37_ADJUDICATION_SHA256,
    SKILL_INDEX_SHA256,
    SOURCE_CANDIDATES_SHA256,
    SOURCE_MANIFEST_SHA256,
    SOURCE_SNAPSHOT_ID,
    canonical_sha256,
    filter_prior_model_review,
    mine_confusions,
    validate_mining_bundle,
)


DEFAULT_SOURCE_MANIFEST = Path("data/router-v2-v4/source-manifest.json")
DEFAULT_SOURCE_CANDIDATES = Path("data/router-v2-v4/source-candidates.jsonl")
DEFAULT_SKILL_INDEX = Path("docs/demo/phase9-real-skill-library-migration/skills.json")
DEFAULT_ADJUDICATION = Path(
    "artifacts/router-v2-v4/model-only-pilot/"
    "router-v2-v4-codex-model-only-pilot-001/"
    "adjudication.model-opinions.jsonl"
)


class Encoder(Protocol):
    model_id: str
    model_revision: str
    device: str
    thread_count: int
    normalize_embeddings: bool

    def encode(self, texts: list[str]) -> list[list[float]]: ...


AdapterFactory = Callable[[], tuple[Encoder, Path]]


class _FrozenMiniLMAdapter:
    model_id = MODEL_ID
    model_revision = MODEL_REVISION
    device = "cpu"
    thread_count = 1
    normalize_embeddings = True

    def __init__(self, model: Any) -> None:
        self._model = model

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
        return [[float(value) for value in vector] for vector in vectors]


def _load_real_adapter() -> tuple[_FrozenMiniLMAdapter, Path]:
    frozen_environment = {
        "TOKENIZERS_PARALLELISM": "false",
        "RAYON_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    os.environ.update(frozen_environment)
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer
    import torch

    snapshot = Path(
        snapshot_download(
            MODEL_ID,
            revision=MODEL_REVISION,
            local_files_only=True,
        )
    ).resolve(strict=True)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
        raise ValueError("frozen CPU thread configuration could not be enforced")
    model = SentenceTransformer(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_files_only=True,
        device="cpu",
    )
    return _FrozenMiniLMAdapter(model), snapshot


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_line(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _json_loads_exact(text: str, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON") from exc


def _load_json_bytes(payload: bytes, *, label: str) -> Any:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc
    return _json_loads_exact(text, label)


def _load_jsonl_bytes(
    payload: bytes, *, label: str
) -> tuple[list[dict[str, Any]], list[bytes]]:
    if not payload or not payload.endswith(b"\n"):
        raise ValueError(f"{label} must use one LF per row")
    rows: list[dict[str, Any]] = []
    lines = payload.splitlines(keepends=True)
    for index, line in enumerate(lines, start=1):
        if not line.endswith(b"\n"):
            raise ValueError(f"{label} line {index} is missing LF")
        try:
            text = line[:-1].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} line {index} is not UTF-8") from exc
        value = _json_loads_exact(text, f"{label} line {index}")
        if not isinstance(value, dict):
            raise ValueError(f"{label} line {index} must be an object")
        if line != _canonical_line(value):
            raise ValueError(f"{label} line {index} is not canonical JSONL")
        rows.append(value)
    return rows, lines


def _resolve_frozen_inputs(root: Path) -> dict[str, Path]:
    relative_paths = {
        "source_manifest": DEFAULT_SOURCE_MANIFEST,
        "source_candidates": DEFAULT_SOURCE_CANDIDATES,
        "skill_index": DEFAULT_SKILL_INDEX,
        "adjudication": DEFAULT_ADJUDICATION,
    }
    resolved: dict[str, Path] = {}
    for label, relative in relative_paths.items():
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"frozen {label} path must be repository-relative")
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError(f"frozen {label} path must stay inside repository root")
        if not target.is_file():
            raise ValueError(f"frozen {label} path must be a regular file")
        resolved[label] = target
    return resolved


def _skill_text(skill: dict[str, Any]) -> str:
    return " ".join(
        [
            skill["id"].replace("-", " "),
            skill["name"],
            skill["category"],
            skill["description"],
            " ".join(skill["trigger_terms"]),
            skill["body"],
        ]
    )


def _restore_frozen_source(
    manifest_payload: bytes, candidates_payload: bytes
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    if _sha256(manifest_payload) != SOURCE_MANIFEST_SHA256:
        raise ValueError("frozen source manifest SHA-256 mismatch")
    if _sha256(candidates_payload) != SOURCE_CANDIDATES_SHA256:
        raise ValueError("frozen source candidates SHA-256 mismatch")
    manifest = _load_json_bytes(manifest_payload, label="source manifest")
    if (
        not isinstance(manifest, dict)
        or manifest.get("snapshot_id") != SOURCE_SNAPSHOT_ID
    ):
        raise ValueError("frozen source snapshot id mismatch")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 192:
        raise ValueError("source manifest must contain exactly 192 records")
    rows, raw_lines = _load_jsonl_bytes(candidates_payload, label="source candidates")
    if len(rows) != 192:
        raise ValueError("source candidates must contain exactly 192 rows")

    positive_rows: list[dict[str, Any]] = []
    source_bindings: list[dict[str, str]] = []
    hard_negative_rows: list[dict[str, Any]] = []
    identity_fields = (
        "source_record_id",
        "source_role",
        "split",
        "positive_skill_id",
        "skill_id",
        "prompt_text_sha256",
    )
    for index, (record, row, raw_line) in enumerate(
        zip(records, rows, raw_lines, strict=True), start=1
    ):
        if not isinstance(record, dict):
            raise ValueError(f"source manifest record {index} must be an object")
        exact_hash = _sha256(raw_line)
        if record.get("source_record_exact_bytes_sha256") != exact_hash:
            raise ValueError(f"source record {index} exact-bytes SHA-256 mismatch")
        if any(record.get(field) != row.get(field) for field in identity_fields):
            raise ValueError(f"source record {index} identity mismatch")
        query = row.get("query_text")
        if not isinstance(query, str) or _sha256(query.encode("utf-8")) != record.get(
            "prompt_text_sha256"
        ):
            raise ValueError(f"source record {index} prompt SHA-256 mismatch")
        if row.get("split") == "train" and row.get("source_role") == "POSITIVE":
            restored = {**row, "source_record_exact_bytes_sha256": exact_hash}
            positive_rows.append(restored)
            source_bindings.append(
                {
                    "task_id": row["task_id"],
                    "source_record_id": row["source_record_id"],
                    "source_record_exact_bytes_sha256": exact_hash,
                    "prompt_sha256": row["prompt_text_sha256"],
                    "positive_skill_id": row["positive_skill_id"],
                    "split": "train",
                    "source_role": "POSITIVE",
                }
            )
        elif (
            row.get("split") == "train"
            and row.get("source_role") == "HARD_NEGATIVE_CANDIDATE"
        ):
            hard_negative_rows.append(row)
    if not (
        len(positive_rows) == len(source_bindings) == len(hard_negative_rows) == 64
    ):
        raise ValueError("frozen source must contain 64 train positives and negatives")
    return positive_rows, source_bindings, hard_negative_rows


def _load_frozen_skills(
    payload: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if _sha256(payload) != SKILL_INDEX_SHA256:
        raise ValueError("frozen skill index SHA-256 mismatch")
    parsed = _load_json_bytes(payload, label="skill index")
    if not isinstance(parsed, list) or len(parsed) != 16:
        raise ValueError("skill index must contain exactly 16 rows")
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, skill in enumerate(parsed, start=1):
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), str):
            raise ValueError(f"skill index row {index} is invalid")
        if skill["id"] in seen:
            raise ValueError(f"duplicate skill id: {skill['id']}")
        seen.add(skill["id"])
        skills.append(skill)
    skills.sort(key=lambda skill: skill["id"])
    bindings = [
        {
            "skill_id": skill["id"],
            "skill_record_sha256": canonical_sha256(skill),
            "skill_text_sha256": canonical_sha256(_skill_text(skill)),
        }
        for skill in skills
    ]
    return skills, bindings


def _model_file_manifest(snapshot: Path) -> list[dict[str, Any]]:
    root = snapshot.resolve(strict=True)
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        payload = path.read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "size": len(payload),
                "sha256": _sha256(payload),
            }
        )
    if not records:
        raise ValueError("model snapshot contains no files")
    if not any(
        PurePosixPath(row["path"]).name == "model.safetensors" for row in records
    ):
        raise ValueError("model snapshot must contain model.safetensors")
    return records


def _write_validated_outputs(
    output_dir: Path,
    mined: list[dict[str, Any]],
    manifest: dict[str, Any],
    prior_report: dict[str, Any],
) -> None:
    mining_payload = b"".join(_canonical_line(row) for row in mined)
    if _sha256(mining_payload) != manifest["mining_jsonl_sha256"]:
        raise ValueError("mining JSONL SHA-256 does not match manifest")
    payloads = {
        "mining.jsonl": mining_payload,
        "mining-manifest.json": _canonical_line(manifest),
        "prior-review-filter.json": _canonical_line(prior_report),
    }
    _load_jsonl_bytes(payloads["mining.jsonl"], label="mining output")
    _load_json_bytes(payloads["mining-manifest.json"], label="mining manifest output")
    _load_json_bytes(payloads["prior-review-filter.json"], label="prior-review output")

    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("output directory must not exist")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-", dir=str(output_dir.parent)
        )
    )
    try:
        for name, payload in payloads.items():
            (staging / name).write_bytes(payload)
        if output_dir.exists() or output_dir.is_symlink():
            raise ValueError("output directory must not exist")
        staging.rename(output_dir)
    finally:
        if staging.exists() or staging.is_symlink():
            shutil.rmtree(staging)


def run_mining(
    *,
    repository_root: Path | str,
    output_dir: Path | str,
    # Private test seam only; public CLI always uses the real frozen adapter.
    adapter_factory: AdapterFactory = _load_real_adapter,
) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root must be a directory")
    target = Path(output_dir).resolve(strict=False)
    if target.exists() or target.is_symlink():
        raise ValueError("output directory must not exist")

    inputs = _resolve_frozen_inputs(root)
    manifest_path = inputs["source_manifest"]
    candidates_path = inputs["source_candidates"]
    skills_path = inputs["skill_index"]
    review_path = inputs["adjudication"]
    source_rows, source_bindings, hard_negative_rows = _restore_frozen_source(
        manifest_path.read_bytes(), candidates_path.read_bytes()
    )
    skills, skill_bindings = _load_frozen_skills(skills_path.read_bytes())
    review_payload = review_path.read_bytes()
    if _sha256(review_payload) != PR37_ADJUDICATION_SHA256:
        raise ValueError("PR #37 adjudication file SHA-256 mismatch")
    adjudication_rows, _ = _load_jsonl_bytes(
        review_payload, label="PR #37 adjudication"
    )

    encoder, snapshot = adapter_factory()
    model_manifest = _model_file_manifest(snapshot)
    mined, mining_manifest = mine_confusions(
        source_rows=source_rows,
        skills=skills,
        encoder=encoder,
        model_file_manifest=model_manifest,
        source_snapshot_id=SOURCE_SNAPSHOT_ID,
        source_candidates_sha256=SOURCE_CANDIDATES_SHA256,
        source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        skill_index_sha256=SKILL_INDEX_SHA256,
        expected_source_bindings=source_bindings,
        expected_skill_bindings=skill_bindings,
    )
    validation = validate_mining_bundle(
        mined,
        mining_manifest,
        expected_source_bindings=source_bindings,
        expected_skill_bindings=skill_bindings,
    )
    prior_report = filter_prior_model_review(
        mining_rows=mined,
        source_rows=hard_negative_rows,
        adjudication_rows=adjudication_rows,
    )
    if prior_report["supported_count"] != 35 or prior_report["disputed_count"] != 29:
        raise ValueError("PR #37 prior-review counts drifted")

    _write_validated_outputs(target, mined, mining_manifest, prior_report)
    return {
        **validation,
        "output_dir": str(target),
        "mined_count": len(mined),
        "prior_retained_count": prior_report["retained_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine frozen Router V2 baseline confusions on CPU."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_mining(
        repository_root=args.repository_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
