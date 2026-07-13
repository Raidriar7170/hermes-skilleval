from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from hermes_skilleval.model_manifest import build_model_manifest
from hermes_skilleval.remote_paths import (
    A100_USER_ROOT,
    resolve_path_root,
    validate_path_within_root,
)
from hermes_skilleval.router_query import router_query_text
from hermes_skilleval.training_input import (
    TrainingInputError,
    _verify_training_handoff,
    load_training_input,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train a SentenceTransformer skill router model."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    selected_root = (
        args.output_root
        if args.output_root is not None
        else config.get("output_root", A100_USER_ROOT)
    )
    try:
        output_root = resolve_path_root(selected_root, field="output_root")
        output_dir = validate_path_within_root(
            config["output_dir"],
            root=output_root,
            field="output_dir",
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    _positive_int(config["epochs"], "epochs")
    _positive_int(config["batch_size"], "batch_size")
    _positive_float(config["learning_rate"], "learning_rate")
    _positive_float(
        config.get("hard_negative_margin", 1.5),
        "hard_negative_margin",
    )
    if "training_pairs" in config:
        raise SystemExit(
            "legacy training_pairs is forbidden; training_input_manifest is required"
        )
    training_input_manifest = config.get("training_input_manifest")
    if not isinstance(training_input_manifest, (str, Path)):
        raise SystemExit("training_input_manifest is required and must be a path")
    try:
        handoff = load_training_input(training_input_manifest)
    except TrainingInputError as exc:
        raise SystemExit(str(exc)) from exc
    return _run_validated_training(
        config=config,
        handoff=handoff,
        output_root=output_root,
        output_dir=output_dir,
    )


def _run_validated_training(
    *,
    config: dict[str, Any],
    handoff: Any,
    output_root: str,
    output_dir: str,
) -> int:
    _verify_training_handoff(handoff)
    positive_examples = [
        example
        for example in handoff.examples
        if example.supervision_label == "POSITIVE"
    ]
    hard_negative_examples = [
        example
        for example in handoff.examples
        if example.supervision_label == "HARD_NEGATIVE"
    ]
    if not positive_examples:
        raise SystemExit("no accepted POSITIVE examples found")

    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.sentence_transformer import losses
    except (ImportError, ModuleNotFoundError) as exc:
        raise SystemExit(
            "sentence-transformers and torch are required on the training machine; "
            "install the repo with: python -m pip install -e '.[embedding]'"
        ) from exc

    model_output = Path(output_dir)
    random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))
    epochs = _positive_int(config["epochs"], "epochs")
    batch_size = _positive_int(config["batch_size"], "batch_size")
    learning_rate = _positive_float(config["learning_rate"], "learning_rate")
    hard_negative_margin = _positive_float(
        config.get("hard_negative_margin", 1.5),
        "hard_negative_margin",
    )

    model = SentenceTransformer(config["base_model"])
    if torch.cuda.is_available():
        model = model.to("cuda")
    train_loss = losses.MultipleNegativesRankingLoss(model)
    hard_negative_loss = (
        losses.ContrastiveLoss(model, margin=hard_negative_margin)
        if hard_negative_examples
        else None
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    model.train()
    observed_losses: list[float] = []
    optimizer_step_count = 0
    hard_negative_optimizer_step_count = 0
    for _ in range(epochs):
        random.shuffle(positive_examples)
        for start in range(0, len(positive_examples), batch_size):
            batch = positive_examples[start : start + batch_size]
            features = [
                _batch_to_device(
                    model.tokenize(
                        [router_query_text(example.query_text) for example in batch]
                    ),
                    model.device,
                ),
                _batch_to_device(
                    model.tokenize([example.skill_text for example in batch]),
                    model.device,
                ),
            ]
            labels = torch.empty(len(batch), device=model.device)
            optimizer.zero_grad()
            loss = train_loss(features, labels)
            loss.backward()
            optimizer.step()
            optimizer_step_count += 1
            observed_losses.append(float(loss.detach().cpu()))
        if hard_negative_loss is None:
            continue
        random.shuffle(hard_negative_examples)
        for start in range(0, len(hard_negative_examples), batch_size):
            batch = hard_negative_examples[start : start + batch_size]
            features = [
                _batch_to_device(
                    model.tokenize(
                        [router_query_text(example.query_text) for example in batch]
                    ),
                    model.device,
                ),
                _batch_to_device(
                    model.tokenize([example.skill_text for example in batch]),
                    model.device,
                ),
            ]
            labels = torch.zeros(len(batch), device=model.device)
            optimizer.zero_grad()
            loss = hard_negative_loss(features, labels)
            loss.backward()
            optimizer.step()
            optimizer_step_count += 1
            hard_negative_optimizer_step_count += 1
            observed_losses.append(float(loss.detach().cpu()))

    model_output.mkdir(parents=True, exist_ok=True)
    try:
        model.save(str(model_output), create_model_card=False)
    except TypeError as exc:
        if "create_model_card" not in str(exc):
            raise
        model.save(str(model_output))
    model_manifest = build_model_manifest(
        model_dir=model_output,
        model_dir_label=output_dir,
        output_root=output_root,
    )
    model_manifest.pop("phase", None)
    model_manifest.update(
        {
            "schema_version": "router-training-data-v2-model-manifest-v3",
            "artifact_version": 3,
            "policy_id": "router-training-data-v2-training-admission-v3",
            "artifact_type": "router-training-data-v2-model-manifest",
        }
    )
    (model_output / "model-manifest.json").write_text(
        json.dumps(model_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (model_output / "train-run-summary.json").write_text(
        json.dumps(
            {
                "schema_version": "router-training-data-v2-train-run-summary-v3",
                "artifact_version": 3,
                "policy_id": "router-training-data-v2-training-admission-v3",
                "artifact_type": "router-training-data-v2-train-run-summary",
                "base_model": config["base_model"],
                "device": str(model.device),
                "epoch_count": epochs,
                "final_loss": observed_losses[-1] if observed_losses else None,
                "hard_negative_margin": hard_negative_margin,
                "hard_negative_optimizer_step_count": (
                    hard_negative_optimizer_step_count
                ),
                "training_input_package_id": handoff.package_id,
                "optimizer_step_count": optimizer_step_count,
                "output_root": output_root,
                "output_dir": output_dir,
                "trained_hard_negative_pair_count": len(hard_negative_examples),
                "trained_pair_count": len(positive_examples),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _batch_to_device(batch: dict[str, Any], device) -> dict[str, Any]:
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in batch.items()
    }


def _positive_int(value: Any, field: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise SystemExit(f"{field} must be positive")
    return parsed


def _positive_float(value: Any, field: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise SystemExit(f"{field} must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
