from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path


PASS = "PASS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
FAIL = "FAIL"
TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".yaml", ".yml", ".html", ".txt", ".py"}
CHECKPOINT_SUFFIXES = {".bin", ".ckpt", ".pt", ".pth", ".safetensors"}
SENSITIVE_RE = re.compile(
    r"("
    r"AKIA[A-Z0-9]{12,}|"
    r"BEGIN (?:OPENSSH|RSA|DSA|EC )?PRIVATE KEY|"
    r"PRIVATE KEY|"
    r"ssh-(?:ed25519|rsa)\s+|"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]|"
    r"bearer\s+|"
    r"\bsk-[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b|"
    r"/root(?:/|\b)"
    r")",
    re.IGNORECASE,
)
OVERCLAIM_RE = re.compile(
    r"\b(state-of-the-art|sota|production-ready|external benchmark)\b",
    re.IGNORECASE,
)
NEGATIVE_DISCLAIMER_RE = re.compile(
    r"(does not establish|not a standard|not an external|does not claim|"
    r"should not be described)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextMatch:
    path: Path
    line_number: int
    text: str


@dataclass(frozen=True)
class ReleaseCheckResult:
    name: str
    ok: bool
    message: str
    status: str | None = None
    details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status is None:
            object.__setattr__(self, "status", PASS if self.ok else FAIL)


def find_sensitive_matches(paths: list[Path]) -> list[TextMatch]:
    return _find_text_matches(paths, SENSITIVE_RE)


def find_overclaim_matches(paths: list[Path]) -> list[TextMatch]:
    return _find_text_matches(
        paths,
        OVERCLAIM_RE,
        ignore_line_re=NEGATIVE_DISCLAIMER_RE,
    )


def find_checkpoint_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root] if root.suffix.lower() in CHECKPOINT_SUFFIXES else []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in CHECKPOINT_SUFFIXES
    )


def verify_required_paths(paths: list[Path]) -> ReleaseCheckResult:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        return _result(
            "required_paths",
            REVIEW_REQUIRED,
            "missing required path(s): " + ", ".join(missing),
            missing,
        )
    return _result("required_paths", PASS, "all required paths exist")


def run_release_checks(
    public_roots: list[Path],
    required_paths: list[Path],
    ignored_paths: list[Path] | None = None,
) -> dict[str, object]:
    public_root_result = _verify_public_roots(public_roots)
    required_result = verify_required_paths(required_paths)
    existing_public_roots = [path for path in public_roots if path.exists()]
    ignored_paths = ignored_paths or []

    sensitive_matches = _find_text_matches(
        existing_public_roots,
        SENSITIVE_RE,
        ignored_paths=ignored_paths,
    )
    overclaim_matches = _find_text_matches(
        existing_public_roots,
        OVERCLAIM_RE,
        ignore_line_re=NEGATIVE_DISCLAIMER_RE,
        ignored_paths=ignored_paths,
    )
    checkpoint_files = _find_checkpoint_files(existing_public_roots, ignored_paths)

    checks = [
        public_root_result,
        required_result,
        _content_result(
            "sensitive_strings",
            sensitive_matches,
            "sensitive match(es)",
        ),
        _content_result(
            "overclaims",
            overclaim_matches,
            "overclaim wording match(es)",
        ),
        _checkpoint_result(checkpoint_files),
    ]
    status = _summary_status(checks)

    return {
        "status": status,
        "match_count": (
            len(sensitive_matches) + len(overclaim_matches) + len(checkpoint_files)
        ),
        "checks": [_result_record(check) for check in checks],
        "matches": {
            "sensitive": [_match_record(match, redact=True) for match in sensitive_matches],
            "overclaims": [_match_record(match) for match in overclaim_matches],
            "checkpoints": [str(path) for path in checkpoint_files],
        },
    }


def write_release_check_summary(
    public_roots: list[Path],
    required_paths: list[Path],
    output_path: Path,
) -> dict[str, object]:
    summary = run_release_checks(
        public_roots=public_roots,
        required_paths=required_paths,
        ignored_paths=[output_path],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _find_text_matches(
    paths: list[Path],
    pattern: re.Pattern[str],
    *,
    ignore_line_re: re.Pattern[str] | None = None,
    ignored_paths: list[Path] | None = None,
) -> list[TextMatch]:
    matches: list[TextMatch] = []
    for path in _iter_text_files(paths, ignored_paths=ignored_paths or []):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1,
        ):
            if ignore_line_re is not None and ignore_line_re.search(line):
                continue
            if pattern.search(line):
                matches.append(TextMatch(path=path, line_number=line_number, text=line))
    return matches


def _iter_text_files(
    paths: Iterable[Path],
    *,
    ignored_paths: Iterable[Path] = (),
) -> Iterator[Path]:
    seen: set[Path] = set()
    ignored = {path.resolve() for path in ignored_paths}
    for root in paths:
        if not root.exists():
            continue
        candidates: Iterable[Path]
        if root.is_file():
            candidates = [root]
        else:
            candidates = root.rglob("*")

        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if _is_docs_superpowers_path(path):
                continue
            key = path.resolve()
            if key in ignored:
                continue
            if key in seen:
                continue
            seen.add(key)
            yield path


def _find_checkpoint_files(
    roots: Iterable[Path],
    ignored_paths: Iterable[Path] = (),
) -> list[Path]:
    checkpoints: dict[Path, Path] = {}
    ignored = {path.resolve() for path in ignored_paths}
    for root in roots:
        for path in find_checkpoint_files(root):
            if path.resolve() in ignored:
                continue
            checkpoints[path.resolve()] = path
    return sorted(checkpoints.values())


def _verify_public_roots(public_roots: list[Path]) -> ReleaseCheckResult:
    if not public_roots:
        return _result("public_roots", REVIEW_REQUIRED, "no public roots configured")
    missing = [str(path) for path in public_roots if not path.exists()]
    if missing:
        return _result(
            "public_roots",
            REVIEW_REQUIRED,
            "missing public root(s): " + ", ".join(missing),
            missing,
        )
    return _result("public_roots", PASS, "all public roots exist")


def _content_result(
    name: str,
    matches: list[TextMatch],
    label: str,
) -> ReleaseCheckResult:
    if not matches:
        return _result(name, PASS, f"no {label}")
    details = tuple(
        f"{match.path}:{match.line_number}" for match in matches
    )
    return _result(
        name,
        FAIL,
        f"{len(matches)} {label} found",
        details,
    )


def _checkpoint_result(paths: list[Path]) -> ReleaseCheckResult:
    if not paths:
        return _result("checkpoints", PASS, "no checkpoint files found")
    details = tuple(str(path) for path in paths)
    return _result(
        "checkpoints",
        FAIL,
        f"{len(paths)} checkpoint file(s) found",
        details,
    )


def _summary_status(checks: list[ReleaseCheckResult]) -> str:
    statuses = {check.status for check in checks}
    if FAIL in statuses:
        return FAIL
    if REVIEW_REQUIRED in statuses:
        return REVIEW_REQUIRED
    return PASS


def _result(
    name: str,
    status: str,
    message: str,
    details: Iterable[str] = (),
) -> ReleaseCheckResult:
    return ReleaseCheckResult(
        name=name,
        ok=status == PASS,
        message=message,
        status=status,
        details=tuple(details),
    )


def _result_record(result: ReleaseCheckResult) -> dict[str, object]:
    return {
        "name": result.name,
        "status": result.status,
        "ok": result.ok,
        "message": result.message,
        "details": list(result.details),
    }


def _match_record(match: TextMatch, *, redact: bool = False) -> dict[str, object]:
    return {
        "path": str(match.path),
        "line_number": match.line_number,
        "text": "[redacted]" if redact else match.text,
    }


def _is_docs_superpowers_path(path: Path) -> bool:
    parts = path.parts
    return any(
        part == "docs" and index + 1 < len(parts) and parts[index + 1] == "superpowers"
        for index, part in enumerate(parts)
    )
