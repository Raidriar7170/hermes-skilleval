"""Small measured-facts adapter. No ML imports or authority from caller booleans."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import selectors
import os
import signal
import subprocess
import tempfile
import time
import uuid

from .context import digest

SCOPE = "isolated-source-maintenance"
SCHEMA = "environment-readiness-v1"
REQUIRED = {
    "interpreter",
    "source_import",
    "dependencies",
    "entrypoint",
    "feature",
    "isolation",
}


def reduce_conditions(requirements, observations):
    by = {o["probe_id"]: o for o in observations}
    if len(by) != len(observations):
        raise ValueError("duplicate probe observation")
    states = [
        by.get(r["id"], {}).get("state", "UNKNOWN")
        for r in requirements
        if r["required"]
    ]
    if not states or any(
        s not in {"SATISFIED", "UNSATISFIED", "UNKNOWN"} for s in states
    ):
        return "UNKNOWN"
    return (
        "UNSATISFIED"
        if "UNSATISFIED" in states
        else "UNKNOWN"
        if "UNKNOWN" in states
        else "SATISFIED"
    )


def source_files(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid source root")
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("source symlink forbidden")
        if p.is_file():
            files[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    if not files:
        raise ValueError("empty source")
    return files


def bounded_run(argv, timeout):
    started = time.monotonic()
    limit = 256_000
    data = bytearray()
    error = None
    code = None
    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() - started > timeout:
                    error = "TimeoutExpired"
                    break
                for key, _ in selector.select(0.1):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        data.extend(chunk)
                        if len(data) > limit:
                            error = "OutputLimitExceeded"
                            break
                if error:
                    break
        if error:
            os.killpg(process.pid, signal.SIGKILL)
        try:
            code = process.wait(
                timeout=max(0.01, timeout - (time.monotonic() - started))
            )
        except subprocess.TimeoutExpired:
            error = "TimeoutExpired"
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        process.stdout.close()
        if error:
            code = None
    except OSError as exc:
        error = type(exc).__name__
    return {
        "exit_status": code,
        "output": bytes(data[:limit]).decode(errors="replace"),
        "error": error,
        "elapsed_seconds": time.monotonic() - started,
    }


def probe_path(profile=None):
    variant = (profile or {}).get("probe_variant")
    if variant not in {None, "explicit-capability-v1"}:
        raise ValueError("unknown probe variant")
    return Path(__file__).with_name(
        "environment_probe_explicit.py" if variant else "environment_probe.py"
    )


def probe_identity(profile=None):
    return hashlib.sha256(probe_path(profile).read_bytes()).hexdigest()


def isolated_probe(image):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("immutable image identity required")
    name = "hermes-env-probe-" + uuid.uuid4().hex
    argv = [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "65534:65534",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--pids-limit",
        "128",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
        "-w",
        "/tmp",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "--entrypoint",
        "python",
        image,
        "/opt/environment_probe.py",
    ]
    try:
        run = bounded_run(argv, 90)
    finally:
        bounded_run(["docker", "rm", "-f", name], 20)
    observations = []
    if run["exit_status"] == 0:
        try:
            observations = json.loads(run["output"])["observations"]
        except (ValueError, KeyError, TypeError):
            run["error"] = "invalid probe output"
    if not observations:
        observations = [
            {
                "probe_id": key,
                "parameters": {},
                "exit_status": run["exit_status"],
                "state": "UNKNOWN",
                "details": {"reason": run["error"] or run["output"][:1000]},
                "elapsed_seconds": run["elapsed_seconds"],
            }
            for key in sorted(REQUIRED)
        ]
    return observations, {**run, "output": run["output"][:2000], "argv": argv}


def prepare(task, snapshot, profile, private_dir, *, offline=False, wheelhouse=None):
    plan = next(p for p in profile["tasks"] if p["task_id"] == task["task_id"])
    for key in ("source_revision", "repository"):
        if plan[key] != task[key]:
            raise ValueError("profile task mismatch")
    files = source_files(snapshot)
    if digest(files) != plan["snapshot_identity"]:
        raise ValueError("full source snapshot differs from frozen revision")
    if (
        profile.get("scope") != SCOPE
        or profile.get("base_image")
        != "python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
    ):
        raise ValueError("unsupported environment scope or base image")
    for name, meta in task["context"]["source_hashes"].items():
        if meta.get("full_file_sha256") and files.get(name) != meta["full_file_sha256"]:
            raise ValueError("original source mismatch")
    private_dir = Path(private_dir)
    private_dir.mkdir(parents=True, exist_ok=False)
    shutil.copytree(snapshot, private_dir / "source")
    shutil.copyfile(
        probe_path(profile),
        private_dir / "environment_probe.py",
    )
    (private_dir / "probe-plan.json").write_text(
        json.dumps({**plan, "source_files": files})
    )
    base = bounded_run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", profile["base_image"]], 20
    )
    if base["exit_status"] != 0 and not offline:
        bounded_run(["docker", "pull", profile["base_image"]], 300)
        base = bounded_run(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                profile["base_image"],
            ],
            20,
        )
    base_id = base["output"].strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", base_id):
        raise ValueError("base image unavailable: " + str(base["error"]))
    prefix = f"FROM {profile['base_image']}\nCOPY source /opt/source\nCOPY probe-plan.json /opt/probe-plan.json\nCOPY environment_probe.py /opt/environment_probe.py\n"
    tag = (
        "hermes-env-"
        + task["task_id"]
        + ":"
        + digest([files, profile, probe_identity(profile)])[:12]
    )
    download = None
    if wheelhouse is None:
        # Public dependency acquisition is a separate container build. Export
        # only wheel files; never reuse its interpreter as verified execution.
        wheel_code = "import importlib.metadata as m,json,subprocess,sys;from pathlib import Path;p=json.loads(Path('/opt/probe-plan.json').read_text());deps=[d.metadata['Name']+'=='+d.version for d in m.distributions() if d.metadata['Name'].lower().replace('_','-')!=p['distribution']];subprocess.check_call([sys.executable,'-m','pip','wheel','--wheel-dir','/opt/wheels',*deps])"
        (private_dir / "Dockerfile").write_text(
            prefix
            + 'RUN python -m pip install --no-cache-dir "setuptools<81" wheel pytest-runner && python -m pip install --no-cache-dir --no-build-isolation -e /opt/source\nRUN '
            + json.dumps(["python", "-c", wheel_code])
            + "\n"
        )
        download = bounded_run(
            [
                "docker",
                "build",
                "--network",
                "default",
                "-t",
                tag + "-download",
                str(private_dir),
            ],
            600,
        )
        (private_dir / "download.json").write_text(json.dumps(download, indent=2))
        if download["exit_status"] == 0:
            container = "hermes-wheel-export-" + uuid.uuid4().hex
            try:
                created = bounded_run(
                    [
                        "docker",
                        "create",
                        "--name",
                        container,
                        "--network",
                        "none",
                        tag + "-download",
                    ],
                    20,
                )
                if created["exit_status"] != 0:
                    raise ValueError("wheel export container unavailable")
                copied = bounded_run(
                    [
                        "docker",
                        "cp",
                        container + ":/opt/wheels",
                        str(private_dir / "wheelhouse"),
                    ],
                    30,
                )
                if copied["exit_status"] != 0:
                    raise ValueError("wheel export failed")
            finally:
                bounded_run(["docker", "rm", "-f", container], 20)
    else:
        shutil.copytree(wheelhouse, private_dir / "wheelhouse")
    wheels = (
        source_files(private_dir / "wheelhouse")
        if (private_dir / "wheelhouse").is_dir()
        else {}
    )
    (private_dir / "Dockerfile").write_text(
        prefix
        + 'COPY wheelhouse /opt/wheels\nRUN python -m pip install --no-index --find-links /opt/wheels "setuptools<81" wheel pytest-runner && python -m pip install --no-index --find-links /opt/wheels --use-pep517 --no-build-isolation -e /opt/source\n'
    )
    build = (
        bounded_run(
            [
                "docker",
                "build",
                "--provenance=false",
                "--sbom=false",
                "--network",
                "none",
                "-t",
                tag,
                str(private_dir),
            ],
            180,
        )
        if wheels
        else download
    )
    (private_dir / "build.json").write_text(json.dumps(build, indent=2))
    image = None
    if build and build["exit_status"] == 0:
        image = bounded_run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", tag], 20
        )["output"].strip()
    observations, run = isolated_probe(image) if image else ([], None)
    record = {
        "schema": SCHEMA,
        "task_id": task["task_id"],
        "repository": task["repository"],
        "source_revision": task["source_revision"],
        "snapshot_identity": digest(files),
        "original_snapshot_identity": task["context"]["snapshot_id"],
        "scope": SCOPE,
        "profile_version": profile["version"],
        "profile_identity": digest(profile),
        "probe_identity": probe_identity(profile),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "runner_identity": image,
        "base_image_identity": base_id,
        "wheelhouse_identity": digest(wheels),
        "dependency_download": {**download, "output": download["output"][-3000:]}
        if download
        else None,
        "requirements": profile["requirements"],
        "observations": observations,
        "preparation": {**build, "output": build["output"][-4000:]},
        "probe_run": run,
        "execution_authority": "NONE",
    }
    record["required_conditions_state"] = reduce_conditions(
        record["requirements"], observations
    )
    return record


def verify_record(record, task, snapshot, profile, *, refresh=True, wheelhouse=None):
    """Records read alone are archival. Live readiness requires an actual re-probe."""
    for key, expected in {
        "schema": SCHEMA,
        "task_id": task["task_id"],
        "repository": task["repository"],
        "source_revision": task["source_revision"],
        "scope": SCOPE,
        "profile_identity": digest(profile),
        "probe_identity": probe_identity(profile),
        "execution_authority": "NONE",
    }.items():
        if record.get(key) != expected:
            raise ValueError("environment binding mismatch: " + key)
    if (
        record.get("requirements") != profile["requirements"]
        or {r["id"] for r in profile["requirements"] if r["required"]} != REQUIRED
    ):
        raise ValueError("environment requirements mismatch")
    if not snapshot or digest(source_files(snapshot)) != record["snapshot_identity"]:
        raise ValueError("environment snapshot mismatch")
    if not refresh:
        return {
            "state": "UNKNOWN",
            "reason": "archival record; live environment not checked",
        }
    if not record.get("runner_identity"):
        return {
            "state": "UNKNOWN",
            "reason": "preparation did not produce an image",
            "observations": record["observations"],
        }
    if wheelhouse is None:
        return {
            "state": "UNKNOWN",
            "reason": "local preparation wheel assets required for offline reconstruction",
        }
    if digest(source_files(wheelhouse)) != record.get("wheelhouse_identity"):
        raise ValueError("environment dependency assets changed")
    # Reconstruct the controller recipe offline, trusting Docker's local build
    # cache and pinned public base, never executing the record-selected image.
    try:
        with tempfile.TemporaryDirectory(prefix="hermes-verified-") as temp:
            actual = prepare(
                task,
                snapshot,
                profile,
                Path(temp) / "build",
                offline=True,
                wheelhouse=wheelhouse,
            )
    except ValueError as exc:
        if str(exc).startswith("base image unavailable:"):
            return {
                "state": "UNKNOWN",
                "reason": "pinned base image unavailable locally; prepare the exact base again",
            }
        raise
    if not actual["runner_identity"]:
        return {
            "state": "UNKNOWN",
            "reason": "offline recipe cache unavailable; prepare environment again",
        }
    if actual["runner_identity"] != record["runner_identity"]:
        raise ValueError("environment image differs from reconstructed recipe")
    old = {o["probe_id"]: o for o in record["observations"]}
    new = {o["probe_id"]: o for o in actual["observations"]}
    old_inventory = (
        old.get("dependencies", {}).get("details", {}).get("inventory_sha256")
    )
    if old_inventory and old_inventory != new.get("dependencies", {}).get(
        "details", {}
    ).get("inventory_sha256"):
        raise ValueError("environment dependencies changed")
    return {
        "state": actual["required_conditions_state"],
        "observations": actual["observations"],
        "refresh": actual["probe_run"],
        "binding": digest(
            [
                record["snapshot_identity"],
                actual["runner_identity"],
                digest(profile),
                probe_identity(profile),
            ]
        ),
    }
