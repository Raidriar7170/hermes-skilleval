from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from hermes_skilleval.router_v2_pilot_runtime import (
    TRUTH_FIELDS,
    _atomic_output_publish,
    _clean_git_commit,
    build_frozen_config,
    build_skill_unique_plan,
    canonical_json_line,
    canonical_sha256,
    dependency_versions,
    load_and_seal_internal_package,
    resolve_authorized_output_root,
    validate_frozen_config,
    validate_sealed_handoff,
    validate_skill_unique_plan,
)


RUN_PACK_RELATIVE_PATH = Path("run-pack/router-v2-v4-training-run-pack-001")
RUN_PACK_ID = "router-v2-v4-training-run-pack-001"
SEEDS = (7170, 7171, 7172)
ARMS = ("A", "B", "C")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_payload(value: dict[str, Any]) -> bytes:
    return canonical_json_line(value).encode("utf-8")


def _parse_canonical(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict) or payload != _canonical_payload(value):
        raise ValueError(f"{label} must be canonical JSON")
    return value


def _payload_names() -> set[str]:
    return {
        "sealed-handoff.json",
        *(f"sampler-plan-seed-{seed}.json" for seed in SEEDS),
        *(f"config-arm-{arm}-seed-{seed}.json" for arm in ARMS for seed in SEEDS),
    }


def _build_manifest(
    payloads: dict[str, bytes],
    handoff: dict[str, Any],
    plans: dict[int, dict[str, Any]],
    *,
    training_code_git_commit: str,
    frozen_dependencies: dict[str, str],
) -> dict[str, Any]:
    manifest = {
        "schema_version": "router-v2-pilot-run-pack-manifest-v1",
        "run_pack_id": RUN_PACK_ID,
        "execution_relative_path": RUN_PACK_RELATIVE_PATH.as_posix(),
        "payload_files": [
            {
                "path": path,
                "sha256": sha256_bytes(payloads[path]),
                "size": len(payloads[path]),
            }
            for path in sorted(payloads)
        ],
        "row_fingerprints": [row["fingerprint"] for row in handoff["examples"]],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "positive_count": handoff["positive_count"],
        "hard_negative_count": handoff["hard_negative_count"],
        "arms": list(ARMS),
        "seeds": list(SEEDS),
        "sampler_version": "skill-unique-v1",
        "sampler_plan_sha256_by_seed": {
            str(seed): plans[seed]["plan_sha256"] for seed in SEEDS
        },
        "training_code_git_commit": training_code_git_commit,
        "dependency_versions": dict(sorted(frozen_dependencies.items())),
        "data_manifest_sha256": handoff["data_manifest_sha256"],
        "accepted_pairs_sha256": handoff["accepted_pairs_sha256"],
        "mining_rows_sha256": handoff["mining_rows_sha256"],
        "mining_manifest_sha256": handoff["mining_manifest_sha256"],
        "package_code_git_commit": handoff["package_code_git_commit"],
        "base_model_id": handoff["base_model_id"],
        "base_model_revision": handoff["base_model_revision"],
        "base_model_file_manifest_sha256": handoff["base_model_file_manifest_sha256"],
        **TRUTH_FIELDS,
    }
    return {**manifest, "manifest_sha256": canonical_sha256(manifest)}


def build_run_pack_documents(
    repository_root: Path | str,
    *,
    training_code_git_commit: str,
    dependency_versions: dict[str, str],
) -> dict[str, bytes]:
    if HEX40.fullmatch(training_code_git_commit) is None:
        raise ValueError("training code Git commit must be lowercase 40-hex")
    handoff = load_and_seal_internal_package(repository_root)
    plans = {
        seed: build_skill_unique_plan(handoff, seed=seed, epochs=3) for seed in SEEDS
    }
    documents = {"sealed-handoff.json": _canonical_payload(handoff)}
    for seed, plan in plans.items():
        documents[f"sampler-plan-seed-{seed}.json"] = _canonical_payload(plan)
        for arm in ARMS:
            config = build_frozen_config(
                handoff=handoff,
                plan=plan,
                arm=arm,
                seed=seed,
                training_code_git_commit=training_code_git_commit,
                dependency_versions=dependency_versions,
                output_dir=f"arm-{arm}/seed-{seed}",
            )
            documents[f"config-arm-{arm}-seed-{seed}.json"] = _canonical_payload(config)
    manifest = _build_manifest(
        documents,
        handoff,
        plans,
        training_code_git_commit=training_code_git_commit,
        frozen_dependencies=dependency_versions,
    )
    documents["run-pack-manifest.json"] = _canonical_payload(manifest)
    validate_run_pack_documents(documents)
    return documents


def validate_run_pack_documents(documents: dict[str, bytes]) -> dict[str, Any]:
    expected_names = {*_payload_names(), "run-pack-manifest.json"}
    if set(documents) != expected_names or any(
        not isinstance(payload, bytes) for payload in documents.values()
    ):
        raise ValueError("run pack uses an invalid exact file set")
    handoff = _parse_canonical(documents["sealed-handoff.json"], "sealed handoff")
    validate_sealed_handoff(handoff)
    plans: dict[int, dict[str, Any]] = {}
    configs: list[dict[str, Any]] = []
    for seed in SEEDS:
        plan = _parse_canonical(
            documents[f"sampler-plan-seed-{seed}.json"], f"sampler plan {seed}"
        )
        validate_skill_unique_plan(plan, handoff)
        if type(plan["seed"]) is not int or plan["seed"] != seed:
            raise ValueError("sampler plan seed mismatch")
        plans[seed] = plan
        for arm in ARMS:
            config = _parse_canonical(
                documents[f"config-arm-{arm}-seed-{seed}.json"],
                f"config {arm}/{seed}",
            )
            validate_frozen_config(config, handoff, plan)
            if (
                config["arm"] != arm
                or type(config["seed"]) is not int
                or config["seed"] != seed
            ):
                raise ValueError("config arm/seed filename mismatch")
            configs.append(config)
    commits = {config["training_code_git_commit"] for config in configs}
    dependencies = {
        canonical_json_line(config["dependency_versions"]) for config in configs
    }
    if len(commits) != 1 or len(dependencies) != 1:
        raise ValueError("run pack config lineage is inconsistent")
    commit = next(iter(commits))
    frozen_dependencies = configs[0]["dependency_versions"]
    payloads = {
        path: payload
        for path, payload in documents.items()
        if path != "run-pack-manifest.json"
    }
    expected_manifest = _build_manifest(
        payloads,
        handoff,
        plans,
        training_code_git_commit=commit,
        frozen_dependencies=frozen_dependencies,
    )
    expected_manifest_payload = _canonical_payload(expected_manifest)
    if documents["run-pack-manifest.json"] != expected_manifest_payload:
        raise ValueError("run pack manifest does not match canonical documents")
    return _parse_canonical(expected_manifest_payload, "run pack manifest")


def validate_run_pack_directory(output: Path | str) -> dict[str, Any]:
    root = Path(output).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run pack output must be a directory")
    files = list(root.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError("run pack output contains a non-regular file")
    return validate_run_pack_documents({path.name: path.read_bytes() for path in files})


def build_run_pack(
    repository_root: Path | str, *, execution_root: Path | str
) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    resolved_execution_root = resolve_authorized_output_root(execution_root)
    if resolved_execution_root.is_relative_to(root):
        raise ValueError("execution root must be outside repository root")
    commit = _clean_git_commit(root)
    documents = build_run_pack_documents(
        root,
        training_code_git_commit=commit,
        dependency_versions=dependency_versions(),
    )

    completed_manifest: dict[str, Any] | None = None

    def write_and_validate(staging: Path) -> None:
        nonlocal completed_manifest
        for path, payload in documents.items():
            (staging / path).write_bytes(payload)
        completed_manifest = validate_run_pack_directory(staging)

    _atomic_output_publish(
        resolved_execution_root,
        RUN_PACK_RELATIVE_PATH.as_posix(),
        write_and_validate,
    )
    if completed_manifest is None:
        raise RuntimeError("run pack staging was not validated")
    return completed_manifest
