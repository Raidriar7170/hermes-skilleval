"""Public-only source registration; no patch or hidden-test columns are read."""

import json
from pathlib import Path
import subprocess

SELECTED = {
    "0ea40e09": ("dev", "mapping-subtype-combination"),
    "29aea9ff": ("dev", "empty-keyed-group-naming"),
    "395e5e20": ("dev", "iterator-state-enum-compatibility"),
    "5f4e332e": ("dev", "ini-string-unquoting"),
    "3b823d90": ("confirmation", "variable-file-cache"),
    "3db08adb": ("confirmation", "filter-attribute-forwarding"),
    "415e08c2": ("confirmation", "locale-fallback"),
    "c616e54a": ("confirmation", "collection-import-resolution"),
    "d62496fe": ("confirmation", "human-size-parser-validation"),
    "fb144c44": ("confirmation", "documentation-macro-boundaries"),
    "1ee70fc2": ("reserve", "python-identifier-validation"),
    "cd473dfb": ("reserve", "invalid-host-field-errors"),
}

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--public", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("source pool already registered")
    rows = []
    for row in json.loads(a.public.read_text()):
        prefix = row["instance_id"].split("-")[1][:8]
        if row["repo"] != "ansible/ansible" or prefix not in SELECTED:
            continue
        role, mechanism = SELECTED[prefix]
        meta = json.loads(
            subprocess.check_output(
                ["gh", "api", f"repos/{row['repo']}/commits/{row['base_commit']}"]
            )
        )
        # Only expose date from the base commit API; do not inspect commit diffs.
        rows.append(
            {
                **row,
                "split": role,
                "mechanism": mechanism,
                "base_date": meta["commit"]["committer"]["date"],
            }
        )
    rows.sort(key=lambda r: (r["base_date"], r["issue_categories"], r["instance_id"]))
    for i, r in enumerate(rows):
        r["source_order"] = i + 1
    a.output.write_text(
        json.dumps(
            {
                "status": "PRE_SAMPLING_SOURCE_POOL",
                "source": "SWE-bench Pro",
                "dataset_revision": "7ab5114912baf22bb098818e604c02fe7ad2c11f",
                "evaluation_revision": "ca10a60a5fcae51e6948ffe1485d4153d421e6c5",
                "selection_basis": "Public requirement mechanism; local Python unit execution without remote targets. One repository. Dates/category/stable ID determine ordering. Reserve substitutes earliest invalid slot only for missing source/environment/invalid acceptance, never observed model results.",
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )
    print([(r["split"], r["mechanism"], r["base_date"]) for r in rows])
