from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train a SentenceTransformer skill router model."
    )
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output_dir = str(config["output_dir"])
    if not output_dir.startswith("/mnt/data/minghongsun/"):
        raise SystemExit("output_dir must be under /mnt/data/minghongsun/")

    try:
        from sentence_transformers import InputExample, SentenceTransformer, losses
        from torch.utils.data import DataLoader
    except (ImportError, ModuleNotFoundError) as exc:
        raise SystemExit(
            "sentence-transformers and torch are required on the training machine; "
            "install the repo with: python -m pip install -e '.[embedding]'"
        ) from exc

    random.seed(int(config["seed"]))
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

    train_examples = [
        InputExample(texts=[pair["query_text"], pair["skill_text"]])
        for pair in positive_pairs
    ]
    model = SentenceTransformer(config["base_model"])
    train_loader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=int(config["batch_size"]),
    )
    train_loss = losses.MultipleNegativesRankingLoss(model)
    model.fit(
        train_objectives=[(train_loader, train_loss)],
        epochs=int(config["epochs"]),
        warmup_steps=0,
        optimizer_params={"lr": float(config["learning_rate"])},
        show_progress_bar=True,
    )

    model_output = Path(output_dir)
    model_output.mkdir(parents=True, exist_ok=True)
    model.save(str(model_output))
    (model_output / "train-run-summary.json").write_text(
        json.dumps(
            {
                "phase": "Phase 14",
                "trained_pair_count": len(train_examples),
                "base_model": config["base_model"],
                "output_dir": output_dir,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
