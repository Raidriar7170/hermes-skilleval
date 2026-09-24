"""OS-restricted replay worker; Q rows enter only through the requested-row pipe."""

import json
from pathlib import Path
import sys
from .relation_query_study import run_policy


def main():
    root, name, method, out = sys.argv[1:]
    # Assert enforcement against actual sealed files before executing policy.
    for role in ("Q", "J"):
        try:
            (Path(root) / "reference" / name / role / "store.json").read_bytes()
        except PermissionError:
            pass
        else:
            raise RuntimeError("Sealed label read denial not enforced")

    def reveal(batch):
        print(json.dumps({"requested": batch}), flush=True)
        return json.loads(sys.stdin.readline())

    run_policy(Path(root), name, method, Path(out), sealed=reveal)


if __name__ == "__main__":
    main()
