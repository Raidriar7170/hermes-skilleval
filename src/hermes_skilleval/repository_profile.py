"""Small controller-owned repository profiles; no retrieval imports."""

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import re


@dataclass(frozen=True)
class RepositoryProfile:
    repository: str
    packages: dict[str, str]
    cli_module: str
    cli_callable: str
    cli_name: str
    image: str
    writable_roots: tuple[str, ...]

    def __post_init__(self):
        if not self.packages:
            raise ValueError("at least one candidate package is required")
        for name, root in self.packages.items():
            path = PurePosixPath(root)
            if not name.isidentifier() or path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe package root")
        if (
            not all(p.isidentifier() for p in self.cli_module.split("."))
            or not self.cli_callable.isidentifier()
        ):
            raise ValueError("invalid CLI import")
        if self.cli_module.split(".")[0] not in self.packages:
            raise ValueError("CLI must belong to candidate packages")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", self.cli_name):
            raise ValueError("invalid console name")

    def to_dict(self):
        return asdict(self)


SQLITE_UTILS = RepositoryProfile(
    "simonw/sqlite-utils",
    {"sqlite_utils": "."},
    "sqlite_utils.cli",
    "cli",
    "sqlite-utils",
    "hermes-repo-workflow:v2",
    ("sqlite_utils", "tests"),
)
CSVKIT = RepositoryProfile(
    "wireservice/csvkit",
    {"csvkit": "."},
    "csvkit.utilities.in2csv",
    "launch_new_instance",
    "in2csv",
    "hermes-two-repo:v1",
    ("csvkit", "tests"),
)


def profile_for(task):
    value = task.get("profile")
    if value:
        return RepositoryProfile(**value)
    if task.get("repository", "simonw/sqlite-utils") != "simonw/sqlite-utils":
        raise ValueError("repository requires explicit profile")
    return SQLITE_UTILS


def validate_changes(profile, changed_files):
    for name in changed_files:
        if not any(
            name == root or name.startswith(root.rstrip("/") + "/")
            for root in profile.writable_roots
        ):
            raise ValueError("illegal patch path: " + name)
