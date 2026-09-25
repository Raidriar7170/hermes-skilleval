import json
import subprocess
import time
import shlex
from pathlib import Path

P = Path(
    __import__("os").environ.get(
        "NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"
    )
)
result = []
for iid in ["asottile__pyupgrade-330", "encode__httpx-386"]:
    d = json.loads((P / "trusted-targets" / (iid + ".json")).read_text())
    out = P / "qualification" / iid
    out.mkdir(parents=True, exist_ok=True)
    (out / "test.patch").write_text(d["test_patch"])
    (out / "reference.patch").write_text(d["patch"])
    files = sorted(
        {x[6:] for x in d["test_patch"].splitlines() if x.startswith("+++ b/")}
    )
    for mode in ["base", "reference"]:
        commands = [
            "set -e",
            "source /opt/miniconda3/bin/activate testbed",
            "cd /testbed",
            'test "$(git rev-parse HEAD)" = ' + shlex.quote(d["base_commit"]),
            "git status --short",
        ]
        if mode == "reference":
            commands += ["git apply /evidence/reference.patch"]
        commands += [
            "git apply /evidence/test.patch",
            "python -c "
            + shlex.quote(
                "import "
                + ("pyupgrade" if "pyupgrade" in iid else "httpx")
                + "; print("
                + ("pyupgrade" if "pyupgrade" in iid else "httpx")
                + ".__file__)"
            ),
            d["install_config"]["test_cmd"]
            + " "
            + " ".join(map(shlex.quote, files))
            + " --junitxml=/evidence/"
            + mode
            + ".xml",
        ]
        command = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "-v",
            str(out) + ":/evidence",
            "--entrypoint",
            "/bin/bash",
            d["docker_image"],
            "-lc",
            "\n".join(commands),
        ]
        t = time.monotonic()
        r = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (out / (mode + ".log")).write_text(r.stdout + r.stderr)
        row = {
            "instance_id": iid,
            "mode": mode,
            "returncode": r.returncode,
            "seconds": time.monotonic() - t,
            "command": command,
            "stdout": r.stdout,
            "stderr": r.stderr,
        }
        result.append(row)
        (P / "qualification-results.json").write_text(json.dumps(result, indent=2))
        print(iid, mode, r.returncode, (r.stdout + r.stderr)[-1700:], flush=True)
