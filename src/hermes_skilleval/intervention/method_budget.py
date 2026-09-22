"""Durable stage accounting; downtime is not executor activity."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
import uuid

from .relation_store import atomic_json


def boot_identity():
    # A boot identity is needed before a cross-process monotonic clock is evidence.
    import subprocess

    linux_boot = Path("/proc/sys/kernel/random/boot_id")
    if linux_boot.exists():
        return linux_boot.read_text().strip()
    return subprocess.check_output(["sysctl", "-n", "kern.boottime"], text=True).strip()


class MethodBudget:
    def __init__(
        self, path, seconds, *, identity, clock=time.monotonic, host_clock=None
    ):
        self.path, self.clock = Path(path), clock
        self.host_clock = host_clock
        self.value = {"identity": identity, "limit": seconds, "stages": []}
        if self.path.exists():
            self.value = json.loads(self.path.read_text())
            if self.value["identity"] != identity or self.value["limit"] != seconds:
                raise ValueError("Budget identity changed")
        self.save()

    def save(self):
        atomic_json(self.path, self.value)

    @property
    def spent(self):
        if any(
            s["status"] == "ACTIVE" or s.get("seconds") is None
            for s in self.value["stages"]
        ):
            raise ValueError("Unreconciled stage cost")
        return sum(s["seconds"] for s in self.value["stages"])

    @property
    def remaining(self):
        return max(0, self.value["limit"] - self.spent)

    def recover(self, *, confirmed_stopped, upper_bound=None):
        if not confirmed_stopped:
            raise ValueError("Must confirm previous request stopped before recovery")
        for stage in self.value["stages"]:
            if stage["status"] != "ACTIVE":
                continue
            if self.host_clock is not None and stage["host_clock"] == self.host_clock:
                stage["seconds"] = max(0, self.clock() - stage["started_monotonic"])
                stage["cost_status"] = "CONSERVATIVE_CHARGE"
                stage["reason"] = (
                    "same-boot elapsed includes unknown crash-to-recovery downtime"
                )
            elif upper_bound is not None:
                stage["seconds"] = upper_bound
                stage["cost_status"] = "CONSERVATIVE_CHARGE"
            else:
                stage["seconds"] = None
                stage["cost_status"] = "UNKNOWN"
            stage["status"] = "INTERRUPTED"
            stage["completed_timestamp"] = time.time()
        self.save()

    @contextmanager
    def stage(self, name):
        remaining = self.remaining
        if remaining <= 0:
            raise TimeoutError("Method budget exhausted")
        row = {
            "id": uuid.uuid4().hex,
            "name": name,
            "pid": os.getpid(),
            "started_timestamp": time.time(),
            "started_monotonic": self.clock(),
            "host_clock": self.host_clock,
            "status": "ACTIVE",
            "remaining_at_start": remaining,
        }
        self.value["stages"].append(row)
        self.save()
        try:
            yield row
        except BaseException as exc:
            row["status"] = "ERROR"
            row["error"] = type(exc).__name__ + ": " + str(exc)
            raise
        else:
            row["status"] = "COMPLETED"
        finally:
            row["seconds"] = max(0, self.clock() - row["started_monotonic"])
            row["completed_timestamp"] = time.time()
            row["cost_status"] = "MEASURED"
            self.save()


def tail_budget(protocol, *, total, prefix, method_cost):
    if min(total, prefix, method_cost) < 0:
        raise ValueError("Negative cost")
    if protocol == "P":
        return max(0, total - prefix - method_cost)
    if protocol == "C":
        return max(0, total - prefix)
    raise ValueError("Unknown protocol")
