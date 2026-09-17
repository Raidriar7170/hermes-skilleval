"""Merge exactly two blinded contexts for one new partition, never read predictions."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from hermes_skilleval.repo_routing.applicability_data import (
    read_json,
    write_json,
    merge_annotations,
)

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--registry", type=Path, required=True)
p.add_argument("--split", choices=["cal", "check"], required=True)
p.add_argument("--pass-a", type=Path, required=True)
p.add_argument("--pass-b", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise ValueError("preserve previous merged annotations")
with TemporaryDirectory(prefix="hermes-new-labels-") as tmp:
    path = Path(tmp) / "tasks.json"
    write_json(path, [t for t in read_json(a.tasks) if t["split"] == a.split])
    result = merge_annotations(path, a.registry, [a.pass_a, a.pass_b], a.output)
write_json(a.output.with_suffix(".provenance.json"), result)
print(result)
