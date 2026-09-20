"""Build by repository/base only. This process never opens task/answer records."""

import argparse
import hashlib
import json
from pathlib import Path
from hermes_skilleval.intervention.repair_knowledge import build_units


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--repository", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("knowledge output already exists")
    # Repository-level scope fixed before any trial: internal Python maintenance
    # contracts, not thousands of independent remote-system module interfaces.
    roots = [
        "lib/ansible/config",
        "lib/ansible/executor",
        "lib/ansible/parsing",
        "lib/ansible/playbook",
        "lib/ansible/template",
        "lib/ansible/utils",
        "lib/ansible/vars",
        "lib/ansible/plugins/filter",
        "lib/ansible/plugins/inventory",
    ]
    files = {}
    for root in roots:
        for path in sorted((a.base / root).rglob("*.py")):
            if path.is_symlink():
                continue
            files[str(path.relative_to(a.base))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    manifest = {
        "repository": a.repository,
        "revision": a.revision,
        "scope": "pre_repair_base",
        "files": files,
        "license": "GPL-3.0-or-later; Ansible source excerpts retain upstream license",
    }
    units = build_units(a.base, manifest)
    a.output.mkdir(parents=True)
    (a.output / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    (a.output / "units.json").write_text(
        json.dumps([u.to_dict() for u in units], indent=2) + "\n"
    )
    (a.output / "knowledge.txt").write_text(
        "\n\n".join(u.serialized_payload for u in units) + "\n"
    )
    (a.output / "build.json").write_text(
        json.dumps(
            {
                "builder": "deterministic AST/docstring extractor v1",
                "model_calls": 0,
                "inputs": {
                    "repository": a.repository,
                    "revision": a.revision,
                    "scope": roots,
                },
                "units": len(units),
                "not_covered": "Unselected module fragments, external APIs, absent documented invariants; no task-specific completion.",
            },
            indent=2,
        )
        + "\n"
    )
    print(a.revision, len(units))


if __name__ == "__main__":
    main()
