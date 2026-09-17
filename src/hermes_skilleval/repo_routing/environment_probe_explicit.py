"""Controlled container payload. Never executes request or skill shell text."""

import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


def main():
    plan = json.loads(Path("/opt/probe-plan.json").read_text())
    observations = []

    def observe(name, fn):
        started = time.monotonic()
        try:
            ok, details = fn()
            state, code = ("SATISFIED" if ok else "UNSATISFIED"), 0
        except subprocess.TimeoutExpired as exc:
            state, code, details = (
                "UNKNOWN",
                None,
                {"error": "probe timeout", "timeout_seconds": exc.timeout},
            )
        except Exception as exc:
            state, code, details = (
                "UNSATISFIED",
                1,
                {"error": type(exc).__name__ + ": " + str(exc)[:1000]},
            )
        observations.append(
            {
                "probe_id": name,
                "parameters": {"profile_task": plan["task_id"]},
                "exit_status": code,
                "state": state,
                "details": details,
                "elapsed_seconds": time.monotonic() - started,
            }
        )

    observe(
        "interpreter",
        lambda: (
            sys.version_info[:2] == (3, 12) and platform.system() == "Linux",
            {
                "python": platform.python_version(),
                "platform": platform.system(),
                "machine": platform.machine(),
            },
        ),
    )

    def source():
        module = importlib.import_module(plan["module"])
        origin = Path(module.__file__).resolve()
        version = importlib.metadata.version(plan["distribution"])
        mismatches = [
            name
            for name, sha in plan["source_files"].items()
            if hashlib.sha256((Path("/opt/source") / name).read_bytes()).hexdigest()
            != sha
        ]
        return origin.is_relative_to("/opt/source") and version == plan[
            "version"
        ] and not mismatches, {
            "module_origin": str(origin),
            "distribution_version": version,
            "mismatches": mismatches[:10],
            "checked_files": len(plan["source_files"]),
        }

    observe("source_import", source)

    def dependencies():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        inventory = sorted(
            (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
        )
        encoded = json.dumps(inventory, sort_keys=True).encode()
        return result.returncode == 0, {
            "exit_status": result.returncode,
            "output": (result.stdout + result.stderr)[:2000],
            "inventory": inventory,
            "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
        }

    observe("dependencies", dependencies)

    def entrypoint():
        result = subprocess.run(
            [plan["cli"], "--help"], capture_output=True, text=True, timeout=20
        )
        return result.returncode == 0, {
            "argv": [plan["cli"], "--help"],
            "exit_status": result.returncode,
            "output": (result.stdout + result.stderr)[:1500],
        }

    observe("entrypoint", entrypoint)

    def feature():
        allowed = {"sqlite_utils": {"sqlite-basic", "sqlite-trigger"},
                   "csvkit": {"csvlook-basic"}, "csv_diff": {"keyed-diff-basic"}}
        if plan.get("capability") not in allowed.get(plan["module"], set()):
            raise ValueError("unsupported explicit module/capability")
        if plan["module"] == "sqlite_utils":
            import sqlite3

            db = sqlite3.connect(":memory:")
            if plan["capability"] == "sqlite-trigger":
                db.executescript(
                    "create table t (id integer); create trigger tr after insert on t begin select 1; end;"
                )
                ok = db.execute(
                    "select name from sqlite_master where type='trigger'"
                ).fetchall() == [("tr",)]
            else:
                db.execute("attach database ':memory:' as extra")
                ok = "extra" in [r[1] for r in db.execute("pragma database_list")]
            return ok, {
                "sqlite_version": sqlite3.sqlite_version,
                "capability": "trigger introspection"
                if plan["capability"] == "sqlite-trigger"
                else "ATTACH in-memory database",
            }
        if plan["module"] == "csvkit":
            from csvkit.utilities.csvlook import CSVLook
            import io

            Path("/tmp/input.csv").write_text("a,b\n1,2\n")
            obj = CSVLook(args=["/tmp/input.csv"], output_file=io.StringIO())
            obj.run()
            return True, {"capability": "CSVLook minimal CSV rendering"}
        from csv_diff import load_csv, compare
        import io

        a = load_csv(io.StringIO("id,value\n1,a\n"), key="id")
        return not compare(a, a)["changed"], {
            "capability": "unique-key load_csv/compare identical input"
        }

    observe("feature", feature)

    def isolation():
        import socket
        import errno

        interfaces = sorted(name for _, name in socket.if_nameindex())
        sock = socket.socket()
        sock.settimeout(1)
        no_route = False
        try:
            sock.connect(("192.0.2.1", 9))
        except OSError as exc:
            no_route = exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EPERM}
        finally:
            sock.close()
        Path("/tmp/probe-write").write_text("temporary")
        readonly = False
        try:
            Path("/opt/source/.probe-write").write_text("forbidden")
        except OSError:
            readonly = True
        return no_route and readonly and os.getuid() != 0 and not Path(
            "/var/run/docker.sock"
        ).exists(), {
            "network_interfaces": interfaces,
            "external_route_unavailable": no_route,
            "source_write_denied": readonly,
            "temporary_write": True,
            "uid": os.getuid(),
            "docker_socket_present": Path("/var/run/docker.sock").exists(),
        }

    observe("isolation", isolation)
    print(json.dumps({"observations": observations}))


if __name__ == "__main__":
    main()
