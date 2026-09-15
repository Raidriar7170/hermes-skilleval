"""Check new Git commits for common private-path/credential patterns; print no matches."""

import argparse
import json
import re
import subprocess


def scan(baseline, head):
    def git(*args):
        return subprocess.check_output(["git", *args])

    commits = git("rev-list", "--reverse", baseline + ".." + head).decode().splitlines()
    patterns = {
        "personal_home": rb"/Users/(?!person/|secret/)[A-Za-z0-9_-]+/",
        "github_token": rb"gh[pousr]_[A-Za-z0-9]{20,}",
        "openai_key": rb"sk-proj-[A-Za-z0-9_-]{20,}",
        "private_key": rb"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    }
    findings = []
    blobs = 0
    total_bytes = 0
    for commit in commits:
        paths = (
            git(
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "--diff-filter=ACMR",
                commit,
            )
            .decode()
            .splitlines()
        )
        for path in paths:
            data = git("show", commit + ":" + path)
            blobs += 1
            total_bytes += len(data)
            for kind, pattern in patterns.items():
                if re.search(pattern, data):
                    findings.append({"commit": commit, "path": path, "kind": kind})
    return {
        "baseline": baseline,
        "head": head,
        "commits": commits,
        "blobs_scanned": blobs,
        "bytes_read": total_bytes,
        "findings": findings,
        "scope": "Common-pattern scan of every added/modified blob in every new reachable commit; no raw matched values printed. Not proof against all sensitive content.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True)
    p.add_argument("--head", default="HEAD")
    args = p.parse_args()
    result = scan(args.baseline, args.head)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["findings"]))
