"""Resolve added parametrized tests from actual collection without using outcomes."""

import json
from pathlib import Path
import sys
from hermes_skilleval.intervention.relation_store import atomic_json

output = Path(sys.argv[1])
for task in sorted((output / "tasks").iterdir()):
    path = task / "evaluation/selectors.json"
    selectors = json.loads(path.read_text())
    collected_path = (
        output / "qualification" / task.name / "reference/target/collected.json"
    )
    if not collected_path.exists():
        continue
    collected = json.loads(collected_path.read_text())
    original = list(selectors["target"])
    expanded = []
    for selector in original:
        matches = [
            node
            for node in collected
            if node == selector or node.startswith(selector + "[")
        ]
        if not matches:
            raise ValueError("Required selector did not collect: " + selector)
        expanded.extend(matches)
    if len(expanded) != len(set(expanded)):
        raise ValueError("Duplicate selector")
    selectors["target"] = expanded
    atomic_json(path, selectors)
    atomic_json(
        output / "selector-resolution" / (task.name + ".json"),
        {
            "before": original,
            "after": expanded,
            "basis": "collection only; no pass/fail screening",
        },
    )
    print(task.name, len(original), len(expanded))
