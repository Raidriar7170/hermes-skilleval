"""Export actual legacy per-requirement scores and token-visible inputs (no Agent)."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from hermes_skilleval.repo_routing.policy import read_config, route
from hermes_skilleval.repo_routing.reranker import Reranker


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("tasks", "config", "registry", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--task", action="append", required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    config = read_config(a.config)
    registry = json.loads(a.registry.read_text())
    original = Reranker.scores
    observations = []

    def capture(self, texts, **kwargs):
        values, records = original(self, texts, **kwargs)
        tensors, _ = self.inputs(texts)
        for text, value, record, ids in zip(
            texts,
            values.detach().cpu().tolist(),
            records,
            tensors["input_ids"].tolist(),
        ):
            observations.append(
                dict(
                    representation=text,
                    raw_score=value,
                    input=record,
                    visible_text=self.tokenizer.decode(ids),
                    token_ids=ids,
                )
            )
        return values, records

    Reranker.scores = capture
    try:
        for task_id in a.task:
            observations.clear()
            task = a.tasks / task_id
            target = a.output / (task_id + ".json")
            if target.exists():
                raise ValueError("refuse to overwrite an observed diagnostic")
            request = (task / "public.md").read_text()
            started = time.time()
            result = route(
                task / "base",
                request,
                {"network": "disabled"},
                registry,
                "repo-aware",
                config,
            )
            result["diagnostic"] = dict(
                started_at=started,
                finished_at=time.time(),
                previously_observed=True,
                task_id=task_id,
                calls=list(observations),
                legacy_threshold=config.get("support_threshold", 0.8),
                instruction_visibility="inspect decoded actual token input; representation prefix is not evidence of visibility",
            )
            result["diagnostic"]["source_identities"] = {
                name: hashlib.sha256(
                    Path("src/hermes_skilleval/repo_routing", name + ".py").read_bytes()
                ).hexdigest()
                for name in ("context", "reranker", "support", "policy", "selector")
            }
            target.write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps(
                    dict(
                        task=task_id,
                        action=result["action"],
                        calls=len(observations),
                        missing=result["context"]["missing"],
                    )
                ),
                flush=True,
            )
    finally:
        Reranker.scores = original


if __name__ == "__main__":
    main()
