from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "diagnostic.v1"
VOLATILE_FIELDS = ("generated_at",)
VOLATILE_PATH_KEYS = (
    "inspect",
    "inspect_path",
    "index_path",
    "lint",
    "file_path",
    "path",
    "routes",
    "scan",
    "source_path",
)
DASHBOARD_PAYLOAD_MARKER = "window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__ = "
DEFAULT_DEMO_ARTIFACTS = (
    "scan.json",
    "lint.json",
    "inspect.json",
    "route-browser-smoke.json",
    "route-debug-red-green.json",
    "dashboard.html",
    "ci-gate-report.json",
    "pr-review-packet.json",
)


def compare_diagnostic_artifacts(
    *,
    expected_path: Path | str,
    actual_path: Path | str,
    output_path: Path | str | None = None,
    markdown_output_path: Path | str | None = None,
) -> dict[str, Any]:
    expected = Path(expected_path)
    actual = Path(actual_path)
    pairs = _artifact_pairs(expected, actual)
    compared = [
        _compare_pair(name, expected_item, actual_item)
        for name, expected_item, actual_item in pairs
    ]
    drift_count = sum(1 for item in compared if item["status"] == "FAIL")
    report = {
        "artifact_type": "diagnostic_artifact_drift",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "decision": "FAIL" if drift_count else "PASS",
        "scope": "local semantic drift check for diagnostic demo artifacts",
        "policy": {
            "ignored_fields": [*VOLATILE_FIELDS, "local_artifact_paths"],
            "mode": "directory" if expected.is_dir() or actual.is_dir() else "file_pair",
        },
        "inputs": {
            "expected": _display_path(expected),
            "actual": _display_path(actual),
        },
        "summary": {
            "compared_count": len(compared),
            "drift_count": drift_count,
        },
        "compared_artifacts": compared,
    }
    if output_path is not None:
        _write_json(output_path, report)
    if markdown_output_path is not None:
        _write_markdown(markdown_output_path, report)
    return report


def _artifact_pairs(expected: Path, actual: Path) -> list[tuple[str, Path, Path]]:
    if expected.is_dir() or actual.is_dir():
        if not expected.is_dir() or not actual.is_dir():
            raise ValueError("expected and actual must both be directories or both be files")
        pairs = []
        for artifact in DEFAULT_DEMO_ARTIFACTS:
            expected_item = expected / artifact
            actual_item = actual / artifact
            _require_file(expected_item)
            _require_file(actual_item)
            pairs.append((artifact, expected_item, actual_item))
        return pairs

    _require_file(expected)
    _require_file(actual)
    return [(expected.name, expected, actual)]


def _compare_pair(name: str, expected_path: Path, actual_path: Path) -> dict[str, Any]:
    expected_payload = _read_supported_artifact(expected_path)
    actual_payload = _read_supported_artifact(actual_path)
    expected_normalized = _normalize(expected_payload.value)
    actual_normalized = _normalize(actual_payload.value)
    differences = _diff_paths(expected_normalized, actual_normalized)
    return {
        "artifact": name,
        "artifact_type": expected_payload.artifact_type,
        "status": "FAIL" if differences else "PASS",
        "ignored_fields": [*VOLATILE_FIELDS, "local_artifact_paths"],
        "differences": differences,
    }


class _ArtifactPayload:
    def __init__(self, *, value: Any, artifact_type: str) -> None:
        self.value = value
        self.artifact_type = artifact_type


def _read_supported_artifact(path: Path) -> _ArtifactPayload:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"unsupported diagnostic artifact: {path} has invalid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError(f"unsupported diagnostic artifact: {path} is not an object")
        return _ArtifactPayload(
            value=payload,
            artifact_type=str(payload.get("artifact_type") or "json"),
        )
    if suffix == ".html":
        payload = _dashboard_payload(path)
        artifact_type = str(payload.get("artifact_type") or "diagnostic_dashboard")
        return _ArtifactPayload(value=payload, artifact_type=artifact_type)
    raise ValueError(f"unsupported diagnostic artifact: {path}")


def _dashboard_payload(path: Path) -> dict[str, Any]:
    html = path.read_text(encoding="utf-8")
    marker_index = html.find(DASHBOARD_PAYLOAD_MARKER)
    if marker_index < 0:
        raise ValueError(f"unsupported diagnostic artifact: {path} missing dashboard payload")
    payload_text = html[marker_index + len(DASHBOARD_PAYLOAD_MARKER) :].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(payload_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"unsupported diagnostic artifact: {path} has invalid dashboard payload") from error
    if not isinstance(payload, dict):
        raise ValueError(f"unsupported diagnostic artifact: {path} dashboard payload is not an object")
    return payload


def _normalize(value: Any, key: str | None = None) -> Any:
    if isinstance(value, str) and key is not None and _is_path_key(key):
        return _path_basename(value)
    if isinstance(value, dict):
        return {
            key: _normalize(item, key=key)
            for key, item in sorted(value.items())
            if key not in VOLATILE_FIELDS
        }
    if isinstance(value, list):
        return [_normalize(item, key=key) for item in value]
    return value


def _is_path_key(key: str) -> bool:
    return key in VOLATILE_PATH_KEYS


def _path_basename(value: str) -> str:
    if not value:
        return value
    if value.startswith("<external>/"):
        return value.removeprefix("<external>/")
    return Path(value).name


def _display_path(path: Path) -> str:
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return f"<external>/{path.name}"


def _diff_paths(expected: Any, actual: Any, path: str = "") -> list[str]:
    if type(expected) is not type(actual):
        return [path or "/"]
    if isinstance(expected, dict):
        differences: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            child_path = f"{path}/{_json_pointer_token(key)}"
            if key not in expected or key not in actual:
                differences.append(child_path)
                continue
            differences.extend(_diff_paths(expected[key], actual[key], child_path))
        return differences
    if isinstance(expected, list):
        differences = []
        if len(expected) != len(actual):
            differences.append(path or "/")
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            differences.extend(_diff_paths(expected_item, actual_item, f"{path}/{index}"))
        return differences
    if expected != actual:
        return [path or "/"]
    return []


def _json_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"missing diagnostic artifact: {path}")


def _write_json(path: Path | str, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path | str, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Diagnostic Artifact Drift Check",
        "",
        f"- Decision: `{report['decision']}`",
        "- Scope: local semantic drift check for diagnostic demo artifacts",
        "- Ignored volatile fields: `generated_at`, `local_artifact_paths`",
        "",
        "## Summary",
        "",
        f"- compared_count: {report['summary']['compared_count']}",
        f"- drift_count: {report['summary']['drift_count']}",
        "",
        "## Compared Artifacts",
        "",
    ]
    for item in report["compared_artifacts"]:
        lines.append(f"- `{item['artifact']}`: `{item['status']}`")
        for difference in item["differences"]:
            lines.append(f"  - drift: `{difference}`")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
