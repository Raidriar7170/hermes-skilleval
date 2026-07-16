from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from hermes_skilleval.router_v2_blind_v2_evaluation import canonical_sha256
from hermes_skilleval.router_v2_blind_v2_evaluation_runner import (
    DATASET_FREEZE_RELATIVE,
    EVALUATION_OUTPUT_FILENAMES,
    FINAL_NAMESPACE_RELATIVE,
    PILOT_MANIFEST_RELATIVE,
    build_attempt_started_document,
    build_attempt_terminal_document,
    build_authoritative_lineage_bindings,
    build_dataset_freeze_documents,
    build_evaluation_documents,
    build_model_load_smoke_receipt,
    evaluate_routes,
    human_pack_root_from_environment,
    load_preregistered_human_validation_inputs,
    read_frozen_dataset_documents,
    run_model_load_smoke,
    run_single_attempt,
    validate_commit_a_repository,
    validate_commit_b_repository,
    validate_frozen_dataset_documents,
    validate_human_pack,
    validate_model_load_smoke_receipt,
    validate_preregistration_authority,
    write_authoring_templates,
    write_dataset_freeze,
    write_model_load_smoke_receipt,
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_stdout(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _smoke(args: argparse.Namespace) -> int:
    repository = args.repository_root.resolve(strict=True)
    preregistration = args.preregistration.resolve(strict=True)
    validate_preregistration_authority(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=args.pilot_manifest,
        verify_model_files=False,
    )
    inputs = load_preregistered_human_validation_inputs(
        preregistration, repository_root=repository
    )
    state = validate_commit_a_repository(repository, inputs["preregistration"])
    smoke = run_model_load_smoke(
        args.pilot_manifest,
        preregistration_path=preregistration,
        repository_root=repository,
    )
    receipt = build_model_load_smoke_receipt(
        smoke,
        commit_a=state["commit_a"],
        preregistration_sha256=inputs["preregistration"]["preregistration_sha256"],
    )
    receipt_path = write_model_load_smoke_receipt(receipt)
    _write_stdout({**smoke, "receipt_path": str(receipt_path)})
    return 0


def _pack_status(args: argparse.Namespace) -> int:
    repository = args.repository_root.resolve(strict=True)
    preregistration = args.preregistration.resolve(strict=True)
    pilot_manifest = (repository / PILOT_MANIFEST_RELATIVE).resolve(strict=True)
    validate_preregistration_authority(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest,
        verify_model_files=False,
    )
    inputs = load_preregistered_human_validation_inputs(
        preregistration, repository_root=repository
    )
    state = validate_commit_a_repository(repository, inputs["preregistration"])
    validate_model_load_smoke_receipt(
        commit_a=state["commit_a"],
        preregistration_sha256=inputs["preregistration"]["preregistration_sha256"],
    )
    root = human_pack_root_from_environment(repository)
    if root is None:
        paths = write_authoring_templates()
        _write_stdout(
            {
                "status": "BLIND_V2_WAITING_FOR_HUMAN_DATA",
                "template_paths": [str(path) for path in paths],
                "authored_tasks_missing": 64,
                "reviewed_tasks_missing": 64,
                "negative_labeled_tasks_missing": 48,
            }
        )
        return 3
    _write_stdout({"status": "HUMAN_PACK_PRESENT", "root": str(root)})
    return 0


def _validated_pack(
    args: argparse.Namespace,
    inputs: dict[str, Any],
    *,
    first_read_timestamp: str,
) -> tuple[Path, dict[str, Any]]:
    pack_root = human_pack_root_from_environment(args.repository_root)
    if pack_root is None:
        raise ValueError("complete HERMES_BLIND_V2_ROOT human pack is required")
    validation = validate_human_pack(
        pack_root,
        repository_root=args.repository_root,
        canonical_skills=inputs["canonical_skills"],
        train_prompts=inputs["train_prompts"],
        pilot_prompts=inputs["pilot_prompts"],
        train_family_ids=inputs["train_family_ids"],
        pilot_family_ids=inputs["pilot_family_ids"],
        phase16_prompts=inputs["phase16_prompts"],
        first_read_timestamp=first_read_timestamp,
    )
    return pack_root, validation


def _freeze(args: argparse.Namespace) -> int:
    repository = args.repository_root.resolve(strict=True)
    preregistration = args.preregistration.resolve(strict=True)
    pilot_manifest = (repository / PILOT_MANIFEST_RELATIVE).resolve(strict=True)
    validate_preregistration_authority(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest,
        verify_model_files=False,
    )
    inputs = load_preregistered_human_validation_inputs(
        preregistration, repository_root=repository
    )
    state = validate_commit_a_repository(repository, inputs["preregistration"])
    validate_model_load_smoke_receipt(
        commit_a=state["commit_a"],
        preregistration_sha256=inputs["preregistration"]["preregistration_sha256"],
    )
    _, validation = _validated_pack(
        args, inputs, first_read_timestamp=datetime.now(UTC).isoformat()
    )
    documents = build_dataset_freeze_documents(validation, commit_a=state["commit_a"])
    output_dir = repository / DATASET_FREEZE_RELATIVE
    write_dataset_freeze(documents, output_dir)
    _write_stdout(
        {
            "status": "BLIND_V2_DATASET_FROZEN",
            "commit_a": state["commit_a"],
            "output_dir": str(output_dir),
            "task_count": validation["task_count"],
            "negative_labeled_task_count": validation["negative_labeled_task_count"],
        }
    )
    return 0


def _model_bindings(pilot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "arm": row["arm"],
            "seed": row["seed"],
            "model_path": row["model_path"],
        }
        for row in pilot["training_artifacts"]
        if row.get("arm") in {"A", "C"}
    ]
    if len(rows) != 6:
        raise ValueError("pilot manifest does not contain the complete A/C model grid")
    return rows


def _evaluate(args: argparse.Namespace) -> int:
    repository = args.repository_root.resolve(strict=True)
    preregistration = args.preregistration.resolve(strict=True)
    pilot_manifest_path = (repository / PILOT_MANIFEST_RELATIVE).resolve(strict=True)
    validate_preregistration_authority(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=False,
    )
    inputs = load_preregistered_human_validation_inputs(
        preregistration, repository_root=repository
    )
    frozen_documents = read_frozen_dataset_documents(repository)
    blind_manifest = json.loads(
        frozen_documents["blind-v2-manifest.json"].decode("utf-8")
    )
    state = validate_commit_b_repository(
        repository, commit_a=str(blind_manifest["commit_a"])
    )
    validate_model_load_smoke_receipt(
        commit_a=state["commit_a"],
        preregistration_sha256=inputs["preregistration"]["preregistration_sha256"],
    )
    _, validation = _validated_pack(
        args,
        inputs,
        first_read_timestamp=str(blind_manifest["blind_v2_data_first_read_timestamp"]),
    )
    tasks = validate_frozen_dataset_documents(validation, frozen_documents)
    authority = validate_preregistration_authority(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        verify_model_files=True,
    )
    pilot = _json(pilot_manifest_path)
    bindings = _model_bindings(pilot)
    protected = [Path(pilot["training_execution_root"])]
    lineage_bindings = build_authoritative_lineage_bindings(
        preregistration,
        repository_root=repository,
        pilot_manifest_path=pilot_manifest_path,
        frozen_documents=frozen_documents,
    )
    blind_manifest_file_sha256 = _sha256_bytes(
        frozen_documents["blind-v2-manifest.json"]
    )
    attempt_token_sha256 = canonical_sha256(
        {
            "schema_version": "router-v2-blind-v2-attempt-token-v1",
            "commit_a": state["commit_a"],
            "commit_b": state["commit_b"],
            "preregistration_sha256": authority["preregistration_sha256"],
            "blind_v2_manifest_file_sha256": blind_manifest_file_sha256,
            "output_namespace": str(FINAL_NAMESPACE_RELATIVE),
        }
    )
    started_payload = {
        "commit_a": state["commit_a"],
        "commit_b": state["commit_b"],
        "evaluator_commit": state["commit_a"],
        "attempt_token_sha256": attempt_token_sha256,
        "preregistration_sha256": authority["preregistration_sha256"],
        "blind_v2_manifest_file_sha256": blind_manifest_file_sha256,
    }
    attempt_artifacts = {
        "attempt-1.started.json": _canonical_bytes(
            build_attempt_started_document(started_payload)
        ),
        "attempt-1.terminal.json": _canonical_bytes(
            build_attempt_terminal_document(len(EVALUATION_OUTPUT_FILENAMES))
        ),
    }
    input_artifacts = {
        "preregistration.json": preregistration.read_bytes(),
        "blind-v2-manifest.json": frozen_documents["blind-v2-manifest.json"],
        "review-summary.json": frozen_documents["blind-v2-review-summary.json"],
    }

    def evaluate() -> dict[str, bytes]:
        routes = evaluate_routes(tasks, inputs["canonical_skills"], bindings)
        return build_evaluation_documents(
            routes,
            commit_a=state["commit_a"],
            commit_b=state["commit_b"],
            evaluator_commit=state["commit_a"],
            attempt_token_sha256=attempt_token_sha256,
            frozen_bindings=lineage_bindings,
            input_artifacts=input_artifacts,
            attempt_artifacts=attempt_artifacts,
        )

    terminal = run_single_attempt(
        repository / FINAL_NAMESPACE_RELATIVE,
        repository_root=repository,
        started_payload=started_payload,
        evaluate=evaluate,
        protected_roots=protected,
    )
    _write_stdout(terminal)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen Router V2 final blind-v2 protocol."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    smoke = commands.add_parser("smoke", help="Run the fixed A/C model-load check.")
    smoke.add_argument("--pilot-manifest", type=Path, required=True)
    smoke.add_argument("--preregistration", type=Path, required=True)
    smoke.add_argument("--repository-root", type=Path, required=True)
    smoke.set_defaults(handler=_smoke)

    status = commands.add_parser(
        "pack-status", help="Check for the external human pack after Commit A."
    )
    status.add_argument("--repository-root", type=Path, required=True)
    status.add_argument("--preregistration", type=Path, required=True)
    status.set_defaults(handler=_pack_status)

    freeze = commands.add_parser("freeze", help="Validate and freeze reviewed data.")
    freeze.add_argument("--repository-root", type=Path, required=True)
    freeze.add_argument("--preregistration", type=Path, required=True)
    freeze.set_defaults(handler=_freeze)

    evaluate = commands.add_parser("evaluate", help="Consume the only final attempt.")
    evaluate.add_argument("--repository-root", type=Path, required=True)
    evaluate.add_argument("--preregistration", type=Path, required=True)
    evaluate.set_defaults(handler=_evaluate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
