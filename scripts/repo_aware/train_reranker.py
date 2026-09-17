"""Real local LoRA training, or independent process reload verification."""

import argparse
import json

from hermes_skilleval.repo_routing.reranker import reload_probe, train

p = argparse.ArgumentParser(description=__doc__)
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--config")
g.add_argument("--reload")
a = p.parse_args()
print(json.dumps(train(a.config) if a.config else reload_probe(a.reload), indent=2))
