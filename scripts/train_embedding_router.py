from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train a SentenceTransformer skill router model."
    )
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output_dir = str(config["output_dir"])
    model_output = _validated_output_dir(output_dir)

    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.sentence_transformer import losses
    except (ImportError, ModuleNotFoundError) as exc:
        raise SystemExit(
            "sentence-transformers and torch are required on the training machine; "
            "install the repo with: python -m pip install -e '.[embedding]'"
        ) from exc

    random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))
    epochs = _positive_int(config["epochs"], "epochs")
    batch_size = _positive_int(config["batch_size"], "batch_size")
    learning_rate = _positive_float(config["learning_rate"], "learning_rate")
    pairs = [
        json.loads(line)
        for line in Path(config["training_pairs"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    positive_pairs = [
        pair
        for pair in pairs
        if int(pair["label"]) == 1 and str(pair["split"]) in {"train", "dev"}
    ]
    if not positive_pairs:
        raise SystemExit("no positive train/dev pairs found")

    model = SentenceTransformer(config["base_model"])
    if torch.cuda.is_available():
        model = model.to("cuda")
    train_loss = losses.MultipleNegativesRankingLoss(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    model.train()
    observed_losses: list[float] = []
    optimizer_step_count = 0
    for _ in range(epochs):
        random.shuffle(positive_pairs)
        for start in range(0, len(positive_pairs), batch_size):
            batch = positive_pairs[start : start + batch_size]
            features = [
                _batch_to_device(
                    model.tokenize([pair["query_text"] for pair in batch]),
                    model.device,
                ),
                _batch_to_device(
                    model.tokenize([pair["skill_text"] for pair in batch]),
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

    model_output.mkdir(parents=True, exist_ok=True)
    model.save(str(model_output))
    (model_output / "train-run-summary.json").write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "trained_pair_count": len(positive_pairs),
                "base_model": config["base_model"],
                "device": str(model.device),
                "epoch_count": epochs,
                "final_loss": observed_losses[-1] if observed_losses else None,
                "optimizer_step_count": optimizer_step_count,
                "output_dir": output_dir,
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


def _validated_output_dir(output_dir: str) -> Path:
    allowed_root = Path("/mnt/data/minghongsun").resolve(strict=False)
    resolved_output = Path(output_dir).resolve(strict=False)
    try:
        resolved_output.relative_to(allowed_root)
    except ValueError as exc:
        raise SystemExit("output_dir must be under /mnt/data/minghongsun/") from exc
    return resolved_output


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
