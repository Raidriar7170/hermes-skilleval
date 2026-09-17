"""Reconstruct historical public source references from an explicit Git baseline."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--repository", type=Path, required=True)
p.add_argument("--baseline", required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()


def git(*args):
    return subprocess.check_output(["git", "-C", str(a.repository), *args])


head = git("rev-parse", a.baseline + "^{commit}").decode().strip()
files = (
    git("ls-tree", "-r", "--name-only", head, "artifacts", "configs", "docs", "scripts")
    .decode()
    .splitlines()
)
records = []
for name in files:
    if Path(name).suffix not in {
        ".json",
        ".jsonl",
        ".md",
        ".py",
        ".yaml",
        ".yml",
        ".csv",
    }:
        continue
    data = git("show", head + ":" + name)
    text = data.decode(errors="replace")
    refs = sorted(
        set(
            re.findall(
                r"(?:https://github.com/)?(?:simonw/|wireservice/)?(?:sqlite-utils|csvkit|csv-diff)(?:/issues/|/pull/|-issue-)(\d+)",
                text,
            )
        )
    )
    urls = sorted(
        set(
            re.findall(
                r"https://github.com/(?:simonw/(?:sqlite-utils|csv-diff)|wireservice/csvkit)/(?:issues|pull)/\d+",
                text,
            )
        )
    )
    if refs or urls:
        records.append(
            dict(
                file=name,
                sha256=hashlib.sha256(data).hexdigest(),
                source_refs=urls,
                issue_numbers_unscoped=refs,
            )
        )
a.output.write_text(
    json.dumps(
        {"baseline": head, "files_scanned": len(files), "records": records}, indent=2
    )
    + "\n"
)
print(json.dumps({"source_files": len(records), "baseline": head}))
