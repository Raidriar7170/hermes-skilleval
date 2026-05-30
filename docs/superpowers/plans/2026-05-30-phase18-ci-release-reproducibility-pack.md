# Phase 18 CI Release Reproducibility Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CI-backed release reproducibility pack that reruns the Phase 17 selector, reruns the public release gate, and records deterministic manifest artifacts for reviewer and GitHub Actions verification.

**Architecture:** Keep Phase 16 blind validation and Phase 17 release selection unchanged. Add a focused manifest module plus a `skilleval release-check` CLI command that orchestrates existing selector and release-check code, writes Phase 18 manifest artifacts, and gives CI a single deterministic command to run. Public docs should continue to say the default router stays `baseline-minilm` because Phase 17 returned `KEEP_BASELINE`.

**Tech Stack:** Python 3.11, argparse, JSON/JSONL/Markdown artifacts, pytest, GitHub Actions.

---

## Current Context

Phase 17 is merged into `main` at commit `c350145`.

Fresh post-merge verification before writing this plan:

```bash
python -m pytest -q
# 296 passed

PYTHONPATH=src python -m hermes_skilleval.cli verify-release \
  --public-root README.md \
  --public-root docs/phase16.md \
  --public-root docs/phase17.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root docs/demo/phase17-calibrated-release-selector \
  --required-path docs/demo/phase17-calibrated-release-selector/release-decision.json \
  --required-path docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl \
  --required-path docs/phase17.md \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase17-calibrated-release-selector/release-check-summary.json
# Release check PASS

git diff --check
# no output
```

Phase 17 current release decision:

```json
{
  "decision": "KEEP_BASELINE",
  "selected_router": "baseline-minilm",
  "candidate_router": "finetuned-embedding",
  "approved_for_default": false,
  "regression_count": 2,
  "task_count": 16
}
```

Phase 18 must not retrain, re-label, or default-enable `finetuned-embedding`.

---

## File Structure

Create:

- `src/hermes_skilleval/release_manifest.py`
  - Pure helpers for deterministic Phase 18 release manifest records.
  - Computes SHA-256 digests for source and generated artifacts.
  - Renders `release-manifest.json` and `release-manifest.md`.

- `tests/test_release_manifest.py`
  - Unit tests for digesting, manifest validation, status derivation, and Markdown rendering.

- `tests/test_phase18_artifacts.py`
  - Artifact guard tests for committed Phase 18 output files and docs.

- `docs/phase18.md`
  - Short phase note explaining CI-backed reproducibility and boundaries.

- `docs/demo/phase18-ci-release-reproducibility/`
  - `release-manifest.json`
  - `release-manifest.md`
  - `release-check-summary.json`

- `docs/human-briefs/2026-05-30-phase18-ci-release-reproducibility-pack.html`
  - Concise Chinese human brief generated from Phase 16/17/18 evidence.

Modify:

- `src/hermes_skilleval/cli.py`
  - Add `release-check` parser and `_run_release_check`.
  - Reuse `write_release_decision` and `write_release_check_summary`.

- `tests/test_cli_smoke.py`
  - Add CLI smoke coverage for `release-check`.

- `.github/workflows/validate.yml`
  - Add deterministic release reproducibility gate after pytest.

- `README.md`
  - Add Quick Start command for Phase 18.
  - Add roadmap row.
  - Update test count to the final full-suite count after Phase 18 tests are added.

- `docs/release-handoff.md`
  - Add Phase 18 evidence row and CI gate entry point.

- Existing artifact count tests as needed:
  - `tests/test_phase14_artifacts.py`
  - `tests/test_phase15_artifacts.py`
  - `tests/test_phase16_artifacts.py`
  - `tests/test_phase17_artifacts.py`

---

## Release-Check Command Contract

The new command should be deterministic and safe to run locally or in CI:

```bash
skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Default input paths:

```text
docs/demo/phase16-blind-validation/regression-summary.json
docs/demo/phase16-blind-validation/route-diffs.jsonl
docs/demo/phase17-calibrated-release-selector
docs/demo/phase18-ci-release-reproducibility
```

Default public roots:

```text
README.md
docs/phase16.md
docs/phase17.md
docs/phase18.md
docs/release-handoff.md
docs/demo/phase16-blind-validation
docs/demo/phase17-calibrated-release-selector
docs/demo/phase18-ci-release-reproducibility
```

Default required paths:

```text
docs/demo/phase16-blind-validation/regression-summary.json
docs/demo/phase16-blind-validation/route-diffs.jsonl
docs/demo/phase17-calibrated-release-selector/release-decision.json
docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl
docs/demo/phase18-ci-release-reproducibility/release-manifest.json
docs/demo/phase18-ci-release-reproducibility/release-manifest.md
docs/phase17.md
docs/phase18.md
docs/release-handoff.md
```

Expected current result:

```text
Release reproducibility PASS: docs/demo/phase18-ci-release-reproducibility/release-manifest.json
```

The command should return exit code `2` through the existing CLI error path if the release check summary status is not `PASS`, if the Phase 17 decision is malformed, or if artifact paths are missing.

---

## Task 1: Manifest Unit Tests

**Files:**

- Create: `tests/test_release_manifest.py`
- Create later: `src/hermes_skilleval/release_manifest.py`

- [ ] **Step 1: Write digest and manifest tests**

Create `tests/test_release_manifest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from hermes_skilleval.release_manifest import (
    build_release_manifest,
    sha256_file,
    write_release_manifest,
)


def _decision() -> dict[str, object]:
    return {
        "phase": "Phase 17",
        "artifact_type": "phase17-calibrated-release-selector",
        "decision": "KEEP_BASELINE",
        "selected_router": "baseline-minilm",
        "baseline_router": "baseline-minilm",
        "candidate_router": "finetuned-embedding",
        "approved_for_default": False,
        "regression_count": 2,
        "task_count": 16,
        "metric_deltas": {
            "recall_at_5": 0.0,
            "mrr": -0.03125,
            "ndcg_at_5": -0.023067,
            "negative_hit_rate": 0.0625,
            "negative_accepted_rate": 0.0625,
        },
    }


def _release_summary() -> dict[str, object]:
    return {
        "status": "PASS",
        "match_count": 0,
        "checks": [
            {
                "name": "required_paths",
                "status": "PASS",
                "ok": True,
                "message": "all required paths exist",
                "details": [],
            }
        ],
        "matches": {"sensitive": [], "overclaims": [], "checkpoints": []},
    }


def test_sha256_file_is_deterministic(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text('{"status": "PASS"}\n', encoding="utf-8")

    assert sha256_file(artifact) == sha256_file(artifact)
    assert len(sha256_file(artifact)) == 64


def test_build_release_manifest_records_decision_and_artifact_hashes(
    tmp_path: Path,
) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    task_decisions_path = tmp_path / "task-decisions.jsonl"
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")
    task_decisions_path.write_text('{"task_id": "a"}\n', encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path, task_decisions_path],
        command_records=[
            {
                "name": "select-release-router",
                "argv": ["skilleval", "select-release-router"],
                "outputs": [str(decision_path)],
            }
        ],
    )

    assert manifest["phase"] == "Phase 18"
    assert manifest["artifact_type"] == "phase18-ci-release-reproducibility-pack"
    assert manifest["status"] == "PASS"
    assert manifest["release_decision"]["decision"] == "KEEP_BASELINE"
    assert manifest["release_decision"]["selected_router"] == "baseline-minilm"
    assert manifest["release_check"]["status"] == "PASS"
    assert [artifact["path"] for artifact in manifest["artifacts"]] == [
        str(decision_path),
        str(release_summary_path),
        str(task_decisions_path),
    ]
    assert all(artifact["sha256"] for artifact in manifest["artifacts"])


def test_build_release_manifest_requires_phase17_decision(tmp_path: Path) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    decision = {**_decision(), "artifact_type": "wrong"}
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")

    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path],
        command_records=[],
    )

    assert manifest["status"] == "REVIEW_REQUIRED"
    assert "decision artifact_type is not phase17-calibrated-release-selector" in manifest["reasons"]


def test_write_release_manifest_writes_json_and_markdown(tmp_path: Path) -> None:
    decision_path = tmp_path / "release-decision.json"
    release_summary_path = tmp_path / "release-check-summary.json"
    output_dir = tmp_path / "phase18"
    decision_path.write_text(json.dumps(_decision()), encoding="utf-8")
    release_summary_path.write_text(json.dumps(_release_summary()), encoding="utf-8")

    manifest = write_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_summary_path,
        artifact_paths=[decision_path, release_summary_path],
        command_records=[],
        output_dir=output_dir,
    )

    assert manifest["status"] == "PASS"
    manifest_json = json.loads((output_dir / "release-manifest.json").read_text())
    manifest_md = (output_dir / "release-manifest.md").read_text(encoding="utf-8")
    assert manifest_json["release_decision"]["decision"] == "KEEP_BASELINE"
    assert "# Phase 18 Release Reproducibility Manifest" in manifest_md
    assert "`baseline-minilm`" in manifest_md
```

- [ ] **Step 2: Run the tests and verify they fail for the expected reason**

Run:

```bash
python -m pytest tests/test_release_manifest.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'hermes_skilleval.release_manifest'`.

---

## Task 2: Implement Release Manifest Module

**Files:**

- Create: `src/hermes_skilleval/release_manifest.py`
- Test: `tests/test_release_manifest.py`

- [ ] **Step 1: Add the manifest implementation**

Create `src/hermes_skilleval/release_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PASS = "PASS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
PHASE18_ARTIFACT_TYPE = "phase18-ci-release-reproducibility-pack"
PHASE17_ARTIFACT_TYPE = "phase17-calibrated-release-selector"


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(
    *,
    decision_path: Path | str,
    release_check_summary_path: Path | str,
    artifact_paths: list[Path | str],
    command_records: list[dict[str, Any]],
) -> dict[str, Any]:
    decision_file = Path(decision_path)
    release_summary_file = Path(release_check_summary_path)
    decision = _read_json(decision_file)
    release_summary = _read_json(release_summary_file)
    reasons = _manifest_reasons(decision, release_summary, artifact_paths)
    status = PASS if not reasons else REVIEW_REQUIRED

    return {
        "phase": "Phase 18",
        "artifact_type": PHASE18_ARTIFACT_TYPE,
        "status": status,
        "source_phase": decision.get("phase"),
        "release_decision": {
            "decision": decision.get("decision"),
            "selected_router": decision.get("selected_router"),
            "baseline_router": decision.get("baseline_router"),
            "candidate_router": decision.get("candidate_router"),
            "approved_for_default": decision.get("approved_for_default"),
            "regression_count": decision.get("regression_count"),
            "task_count": decision.get("task_count"),
            "metric_deltas": decision.get("metric_deltas", {}),
        },
        "release_check": {
            "status": release_summary.get("status"),
            "match_count": release_summary.get("match_count"),
            "check_count": len(release_summary.get("checks", []))
            if isinstance(release_summary.get("checks"), list)
            else 0,
        },
        "commands": command_records,
        "artifacts": [_artifact_record(path) for path in artifact_paths],
        "reasons": reasons or ["release decision, public release check, and artifact hashes are reproducible"],
    }


def write_release_manifest(
    *,
    decision_path: Path | str,
    release_check_summary_path: Path | str,
    artifact_paths: list[Path | str],
    command_records: list[dict[str, Any]],
    output_dir: Path | str,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest = build_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_check_summary_path,
        artifact_paths=artifact_paths,
        command_records=command_records,
    )
    (output / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "release-manifest.md").write_text(
        _render_manifest_markdown(manifest),
        encoding="utf-8",
    )
    return manifest


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing_path": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"_malformed": f"{path} must contain a JSON object"}
    return data


def _manifest_reasons(
    decision: dict[str, Any],
    release_summary: dict[str, Any],
    artifact_paths: list[Path | str],
) -> list[str]:
    reasons: list[str] = []
    if decision.get("_missing_path"):
        reasons.append(f"missing release decision: {decision['_missing_path']}")
    if release_summary.get("_missing_path"):
        reasons.append(f"missing release check summary: {release_summary['_missing_path']}")
    if decision.get("artifact_type") != PHASE17_ARTIFACT_TYPE:
        reasons.append("decision artifact_type is not phase17-calibrated-release-selector")
    if decision.get("decision") not in {"APPROVE_CANDIDATE", "KEEP_BASELINE", "REVIEW_REQUIRED"}:
        reasons.append("decision must be APPROVE_CANDIDATE, KEEP_BASELINE, or REVIEW_REQUIRED")
    if not isinstance(decision.get("selected_router"), str) or not decision.get("selected_router"):
        reasons.append("selected_router must be a non-empty string")
    if release_summary.get("status") != PASS:
        reasons.append("release check status is not PASS")
    for path in artifact_paths:
        if not Path(path).is_file():
            reasons.append(f"missing artifact: {path}")
    return reasons


def _artifact_record(path: Path | str) -> dict[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        return {
            "path": str(artifact),
            "exists": False,
            "size_bytes": 0,
            "sha256": None,
        }
    return {
        "path": str(artifact),
        "exists": True,
        "size_bytes": artifact.stat().st_size,
        "sha256": sha256_file(artifact),
    }


def _render_manifest_markdown(manifest: dict[str, Any]) -> str:
    release_decision = manifest["release_decision"]
    release_check = manifest["release_check"]
    artifact_rows = "\n".join(
        "| `{path}` | {size_bytes} | `{sha256}` |".format(**artifact)
        for artifact in manifest["artifacts"]
        if artifact["exists"]
    )
    if not artifact_rows:
        artifact_rows = "| None | 0 | None |"

    return "\n".join(
        [
            "# Phase 18 Release Reproducibility Manifest",
            "",
            f"- Status: `{manifest['status']}`",
            f"- Release decision: `{release_decision['decision']}`",
            f"- Selected router: `{release_decision['selected_router']}`",
            f"- Candidate router: `{release_decision['candidate_router']}`",
            f"- Approved for default: `{release_decision['approved_for_default']}`",
            f"- Release check status: `{release_check['status']}`",
            "",
            "## Reproducible Artifacts",
            "",
            "| Path | Size Bytes | SHA-256 |",
            "|---|---:|---|",
            artifact_rows,
            "",
            "## Reasons",
            "",
            *[f"- {reason}" for reason in manifest["reasons"]],
            "",
        ]
    )
```

- [ ] **Step 2: Run manifest unit tests**

Run:

```bash
python -m pytest tests/test_release_manifest.py -q
```

Expected: all tests in `tests/test_release_manifest.py` pass.

---

## Task 3: Add `skilleval release-check`

**Files:**

- Modify: `src/hermes_skilleval/cli.py`
- Modify: `tests/test_cli_smoke.py`
- Test: `tests/test_cli_smoke.py::test_cli_release_check_writes_reproducibility_pack`

- [ ] **Step 1: Add the failing CLI smoke test**

Append this test near the existing `verify-release` and `select-release-router` CLI smoke tests in `tests/test_cli_smoke.py`:

```python
def test_cli_release_check_writes_reproducibility_pack(tmp_path):
    phase17_output = tmp_path / "phase17"
    phase18_output = tmp_path / "phase18"

    result = main(
        [
            "release-check",
            "--regression-summary",
            "docs/demo/phase16-blind-validation/regression-summary.json",
            "--route-diffs",
            "docs/demo/phase16-blind-validation/route-diffs.jsonl",
            "--phase17-output-dir",
            str(phase17_output),
            "--release-output-dir",
            str(phase18_output),
            "--public-root",
            "README.md",
            "--public-root",
            "docs/phase16.md",
            "--public-root",
            "docs/phase17.md",
            "--public-root",
            str(phase17_output),
            "--required-path",
            str(phase17_output / "release-decision.json"),
            "--required-path",
            str(phase17_output / "task-decisions.jsonl"),
        ]
    )

    assert result == 0
    manifest = json.loads((phase18_output / "release-manifest.json").read_text())
    release_summary = json.loads(
        (phase18_output / "release-check-summary.json").read_text()
    )
    assert manifest["status"] == "PASS"
    assert manifest["release_decision"]["decision"] == "KEEP_BASELINE"
    assert manifest["release_decision"]["selected_router"] == "baseline-minilm"
    assert release_summary["status"] == "PASS"
    assert (phase18_output / "release-manifest.md").is_file()
```

- [ ] **Step 2: Run the smoke test and verify it fails because the command is missing**

Run:

```bash
python -m pytest tests/test_cli_smoke.py::test_cli_release_check_writes_reproducibility_pack -q
```

Expected: fail with argparse returning a non-zero status for unknown command `release-check`.

- [ ] **Step 3: Import manifest helper in `cli.py`**

Add near the other imports:

```python
from hermes_skilleval.release_manifest import write_release_manifest
```

- [ ] **Step 4: Add constants near parser constants in `cli.py`**

Add below `ROUTER_LABEL_RE`:

```python
DEFAULT_RELEASE_ROOTS = (
    "README.md",
    "docs/phase16.md",
    "docs/phase17.md",
    "docs/phase18.md",
    "docs/release-handoff.md",
    "docs/demo/phase16-blind-validation",
    "docs/demo/phase17-calibrated-release-selector",
    "docs/demo/phase18-ci-release-reproducibility",
)
DEFAULT_RELEASE_REQUIRED_PATHS = (
    "docs/demo/phase16-blind-validation/regression-summary.json",
    "docs/demo/phase16-blind-validation/route-diffs.jsonl",
    "docs/demo/phase17-calibrated-release-selector/release-decision.json",
    "docs/demo/phase17-calibrated-release-selector/task-decisions.jsonl",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.json",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.md",
    "docs/phase17.md",
    "docs/phase18.md",
    "docs/release-handoff.md",
)
```

- [ ] **Step 5: Add parser block in `_build_parser` after `select-release-router`**

```python
    release_check_parser = subparsers.add_parser(
        "release-check",
        help="rerun release selection and write a reproducibility manifest",
    )
    release_check_parser.add_argument(
        "--regression-summary",
        default="docs/demo/phase16-blind-validation/regression-summary.json",
    )
    release_check_parser.add_argument(
        "--route-diffs",
        default="docs/demo/phase16-blind-validation/route-diffs.jsonl",
    )
    release_check_parser.add_argument(
        "--phase17-output-dir",
        default="docs/demo/phase17-calibrated-release-selector",
    )
    release_check_parser.add_argument(
        "--release-output-dir",
        default="docs/demo/phase18-ci-release-reproducibility",
    )
    release_check_parser.add_argument("--public-root", action="append", default=None)
    release_check_parser.add_argument("--required-path", action="append", default=None)
    release_check_parser.set_defaults(handler=_run_release_check)
```

- [ ] **Step 6: Add `_run_release_check` near `_run_select_release_router`**

```python
def _run_release_check(args: argparse.Namespace) -> None:
    phase17_output = Path(args.phase17_output_dir)
    release_output = ensure_dir(args.release_output_dir)
    release_summary_path = release_output / "release-check-summary.json"

    decision = write_release_decision(
        regression_summary_path=Path(args.regression_summary),
        route_diffs_path=Path(args.route_diffs),
        output_dir=phase17_output,
    )

    manifest_json = release_output / "release-manifest.json"
    manifest_md = release_output / "release-manifest.md"
    _write_placeholder_release_manifest(
        decision_path=phase17_output / "release-decision.json",
        release_check_summary_path=release_summary_path,
        output_dir=release_output,
    )
    public_roots = [Path(path) for path in (args.public_root or DEFAULT_RELEASE_ROOTS)]
    required_paths = [
        Path(path)
        for path in (
            args.required_path
            or DEFAULT_RELEASE_REQUIRED_PATHS
        )
    ]
    summary = write_release_check_summary(
        public_roots=public_roots,
        required_paths=required_paths,
        output_path=release_summary_path,
    )

    verify_argv = ["skilleval", "verify-release"]
    for path in public_roots:
        verify_argv.extend(["--public-root", str(path)])
    for path in required_paths:
        verify_argv.extend(["--required-path", str(path)])
    verify_argv.extend(["--summary-output", str(release_summary_path)])

    command_records = [
        {
            "name": "select-release-router",
            "argv": [
                "skilleval",
                "select-release-router",
                "--regression-summary",
                args.regression_summary,
                "--route-diffs",
                args.route_diffs,
                "--output-dir",
                str(phase17_output),
            ],
            "outputs": [
                str(phase17_output / "release-decision.json"),
                str(phase17_output / "release-decision.md"),
                str(phase17_output / "task-decisions.jsonl"),
            ],
        },
        {
            "name": "verify-release",
            "argv": verify_argv,
            "outputs": [str(release_summary_path)],
        },
    ]
    artifact_paths = [
        Path(args.regression_summary),
        Path(args.route_diffs),
        phase17_output / "release-decision.json",
        phase17_output / "release-decision.md",
        phase17_output / "task-decisions.jsonl",
        release_summary_path,
    ]
    manifest = write_release_manifest(
        decision_path=phase17_output / "release-decision.json",
        release_check_summary_path=release_summary_path,
        artifact_paths=artifact_paths,
        command_records=command_records,
        output_dir=release_output,
    )

    if summary["status"] != "PASS":
        raise ValueError(f"release check status: {summary['status']}")
    if manifest["status"] != "PASS":
        raise ValueError(f"release manifest status: {manifest['status']}")

    print(f"Release reproducibility {manifest['status']}: {manifest_json}")
```

Also add this small helper below `_run_release_check`:

```python
def _write_placeholder_release_manifest(
    *,
    decision_path: Path,
    release_check_summary_path: Path,
    output_dir: Path,
) -> None:
    placeholder_summary = {
        "status": "PASS",
        "match_count": 0,
        "checks": [],
        "matches": {"sensitive": [], "overclaims": [], "checkpoints": []},
    }
    release_check_summary_path.parent.mkdir(parents=True, exist_ok=True)
    if not release_check_summary_path.exists():
        release_check_summary_path.write_text(
            json.dumps(placeholder_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    write_release_manifest(
        decision_path=decision_path,
        release_check_summary_path=release_check_summary_path,
        artifact_paths=[decision_path, release_check_summary_path],
        command_records=[],
        output_dir=output_dir,
    )
```

This placeholder lets the subsequent public-root scan require the manifest files. The final manifest is rewritten immediately after the real release check summary is written.

- [ ] **Step 7: Run focused CLI smoke test**

Run:

```bash
python -m pytest tests/test_cli_smoke.py::test_cli_release_check_writes_reproducibility_pack -q
```

Expected: pass.

---

## Task 4: Generate Phase 18 Artifacts and Docs

**Files:**

- Create: `docs/demo/phase18-ci-release-reproducibility/release-manifest.json`
- Create: `docs/demo/phase18-ci-release-reproducibility/release-manifest.md`
- Create: `docs/demo/phase18-ci-release-reproducibility/release-check-summary.json`
- Create: `docs/phase18.md`
- Create: `docs/human-briefs/2026-05-30-phase18-ci-release-reproducibility-pack.html`
- Modify: `README.md`
- Modify: `docs/release-handoff.md`

- [ ] **Step 1: Generate Phase 18 artifacts**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Expected:

```text
Release reproducibility PASS: docs/demo/phase18-ci-release-reproducibility/release-manifest.json
```

- [ ] **Step 2: Create `docs/phase18.md`**

Create:

```markdown
# Phase 18: CI Release Reproducibility Pack

Phase 18 turns the Phase 17 release selector into a CI-reproducible release
gate. It does not retrain the fine-tuned embedding router, change Phase 16
blind-validation results, or approve `finetuned-embedding` as the default.

## Scope

Committed artifacts live under
`docs/demo/phase18-ci-release-reproducibility/`:

- `release-manifest.json`
- `release-manifest.md`
- `release-check-summary.json`

The release-check command reruns the Phase 17 selector, reruns the public
release guard, and records hashes for the input and generated release artifacts.

## Result

The current Phase 18 manifest reports `PASS`. The release decision remains
`KEEP_BASELINE`, the selected default router remains `baseline-minilm`, and
`finetuned-embedding` remains not approved for default routing.

## Reproduce

```bash
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

GitHub Actions runs the same release reproducibility command after the
lightweight pytest suite.

## Boundaries

This remains a self-built Hermes-style skill-routing release gate. It is not a
standard external benchmark, does not establish SOTA, and should not be
described as production readiness evidence.
```

- [ ] **Step 3: Create Chinese human brief HTML**

Create `docs/human-briefs/2026-05-30-phase18-ci-release-reproducibility-pack.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phase 18 Release Reproducibility Brief</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #17202a; background: #f7f8fa; }
    main { max-width: 920px; margin: 0 auto; padding: 40px 20px 56px; }
    h1 { font-size: 30px; margin: 0 0 10px; }
    h2 { font-size: 18px; margin: 28px 0 10px; }
    p, li { line-height: 1.65; }
    .status { display: inline-block; padding: 4px 10px; border-radius: 6px; background: #e9f7ef; color: #196f3d; font-weight: 700; }
    .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    .item { background: white; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }
    code { background: #eef1f4; padding: 2px 5px; border-radius: 4px; }
  </style>
</head>
<body>
<main>
  <h1>Phase 18: CI Release Reproducibility Pack</h1>
  <p><span class="status">结论: 默认继续使用 baseline-minilm</span></p>
  <p>这一阶段把 Phase 17 的保守发布结论接进可复验的 release pack：本地和 CI 都能重新运行同一条命令，确认发布材料没有缺文件、泄露、checkpoint 或过度声明。</p>

  <h2>本阶段改变</h2>
  <div class="grid">
    <div class="item"><strong>一键复验</strong><br><code>skilleval release-check</code> 重新生成 Phase 17 决策和 Phase 18 manifest。</div>
    <div class="item"><strong>CI gate</strong><br>GitHub Actions 在 pytest 后运行 release reproducibility gate。</div>
    <div class="item"><strong>证据 manifest</strong><br>记录关键输入、输出、命令和 SHA-256，方便 reviewer 复查。</div>
  </div>

  <h2>关键文件</h2>
  <ul>
    <li><code>docs/demo/phase18-ci-release-reproducibility/release-manifest.json</code></li>
    <li><code>docs/demo/phase18-ci-release-reproducibility/release-manifest.md</code></li>
    <li><code>docs/demo/phase18-ci-release-reproducibility/release-check-summary.json</code></li>
    <li><code>.github/workflows/validate.yml</code></li>
  </ul>

  <h2>不要过度解读</h2>
  <p>Phase 18 证明的是发布证据链可复验，不证明这是标准外部 benchmark、SOTA，或生产就绪。当前 release decision 仍是 <code>KEEP_BASELINE</code>。</p>

  <h2>推荐下一步</h2>
  <p>Phase 19 可以做 external blind pack，把评测从自建 Hermes-style corpus 推向更强的外部泛化证据。</p>
</main>
</body>
</html>
```

- [ ] **Step 4: Update README**

Add a new Quick Start section after Phase 17:

```markdown
### 15. Reproduce the Release Pack in CI Shape

```bash
skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Phase 18 reruns the release selector and public release guard, then records a
deterministic manifest at
[`docs/demo/phase18-ci-release-reproducibility/release-manifest.json`](docs/demo/phase18-ci-release-reproducibility/release-manifest.json).
The current reproducible release reading remains `KEEP_BASELINE`.
```

Renumber the existing Static Dashboard section from `15` to `16`.

Add this roadmap row after Phase 17:

```markdown
- [x] CI-backed release reproducibility pack
      ([docs](docs/phase18.md), [manifest](docs/demo/phase18-ci-release-reproducibility/release-manifest.json))
```

Update stale test-count snippets to the actual final full-suite count after all Phase 18 tests are added.

- [ ] **Step 5: Update release handoff**

Add Phase 18 to the evidence chain:

```markdown
| Phase 18 | CI-backed release reproducibility pack | `docs/phase18.md` |
```

Add reviewer entry points:

```markdown
- Phase 18 release manifest: `docs/demo/phase18-ci-release-reproducibility/release-manifest.json`
- Phase 18 reproducibility check: `docs/demo/phase18-ci-release-reproducibility/release-check-summary.json`
```

Add current reading:

```markdown
Phase 18 makes the release reading CI-reproducible. The release-check command
reruns the selector and public artifact guard, writes a manifest with artifact
hashes, and keeps the default-router decision at `KEEP_BASELINE`.
```

---

## Task 5: CI Gate

**Files:**

- Modify: `.github/workflows/validate.yml`

- [ ] **Step 1: Update GitHub Actions workflow**

Modify `.github/workflows/validate.yml`:

```yaml
name: Validate

on:
  pull_request:
  push:
    branches:
      - main

jobs:
  lightweight-tests:
    name: Lightweight pytest and release gate
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install package with dev dependencies
        run: python -m pip install -e ".[dev]"

      - name: Run lightweight test suite
        run: pytest -q

      - name: Run release reproducibility gate
        run: |
          skilleval release-check \
            --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
            --release-output-dir docs/demo/phase18-ci-release-reproducibility
          git diff --exit-code \
            docs/demo/phase17-calibrated-release-selector \
            docs/demo/phase18-ci-release-reproducibility
```

The `git diff --exit-code` line makes stale committed release artifacts fail CI.

- [ ] **Step 2: Run local release command before committing artifacts**

Run:

```bash
python -m pytest -q
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Expected: pytest passes and release reproducibility returns `PASS`. The workflow-level `git diff --exit-code` check is validated after Phase 18 artifacts are committed or in GitHub Actions from a clean checkout.

---

## Task 6: Phase 18 Artifact Tests

**Files:**

- Create: `tests/test_phase18_artifacts.py`
- Modify: existing phase artifact tests only if they pin the old full-suite count.

- [ ] **Step 1: Add Phase 18 artifact tests**

Create `tests/test_phase18_artifacts.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("docs/demo/phase18-ci-release-reproducibility")


def test_phase18_artifact_pack_exists() -> None:
    required = [
        ROOT / "release-manifest.json",
        ROOT / "release-manifest.md",
        ROOT / "release-check-summary.json",
        Path("docs/phase18.md"),
        Path("docs/human-briefs/2026-05-30-phase18-ci-release-reproducibility-pack.html"),
    ]
    for path in required:
        assert path.is_file(), path


def test_phase18_manifest_keeps_phase17_release_reading() -> None:
    manifest = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))

    assert manifest["phase"] == "Phase 18"
    assert manifest["artifact_type"] == "phase18-ci-release-reproducibility-pack"
    assert manifest["status"] == "PASS"
    assert manifest["release_decision"]["decision"] == "KEEP_BASELINE"
    assert manifest["release_decision"]["selected_router"] == "baseline-minilm"
    assert manifest["release_decision"]["candidate_router"] == "finetuned-embedding"
    assert manifest["release_decision"]["approved_for_default"] is False
    assert manifest["release_check"]["status"] == "PASS"
    assert all(artifact["exists"] for artifact in manifest["artifacts"])


def test_phase18_docs_and_readme_reference_release_reproducibility() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    phase18 = Path("docs/phase18.md").read_text(encoding="utf-8")
    handoff = Path("docs/release-handoff.md").read_text(encoding="utf-8")
    manifest_md = (ROOT / "release-manifest.md").read_text(encoding="utf-8")

    assert "Phase 18" in readme
    assert "release-check" in readme
    assert "docs/phase18.md" in readme
    assert "docs/demo/phase18-ci-release-reproducibility/release-manifest.json" in readme
    assert "Phase 18: CI Release Reproducibility Pack" in phase18
    assert "KEEP_BASELINE" in phase18
    assert "Phase 18" in handoff
    assert "release-manifest.json" in handoff
    assert "Phase 18 Release Reproducibility Manifest" in manifest_md
```

- [ ] **Step 2: Run Phase 18 artifact tests**

Run:

```bash
python -m pytest tests/test_phase18_artifacts.py -q
```

Expected: pass after docs and artifacts are generated.

---

## Task 7: Final Verification and Commit

**Files:**

- All files changed by Phase 18.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_release_manifest.py tests/test_phase18_artifacts.py -q
python -m pytest tests/test_cli_smoke.py::test_cli_release_check_writes_reproducibility_pack -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass. Use the actual final pass count to update README and any test-count assertions.

- [ ] **Step 3: Run release reproducibility gate**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Expected:

```text
Release reproducibility PASS: docs/demo/phase18-ci-release-reproducibility/release-manifest.json
```

- [ ] **Step 4: Run public release guard directly**

Run:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli verify-release \
  --public-root README.md \
  --public-root docs/phase16.md \
  --public-root docs/phase17.md \
  --public-root docs/phase18.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root docs/demo/phase17-calibrated-release-selector \
  --public-root docs/demo/phase18-ci-release-reproducibility \
  --required-path docs/demo/phase18-ci-release-reproducibility/release-manifest.json \
  --required-path docs/demo/phase18-ci-release-reproducibility/release-manifest.md \
  --required-path docs/phase18.md \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase18-ci-release-reproducibility/release-check-summary.json
```

Expected:

```text
Release check PASS: docs/demo/phase18-ci-release-reproducibility/release-check-summary.json
```

- [ ] **Step 5: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Review diff**

Run:

```bash
git status -sb
git diff --stat
git diff -- .github/workflows/validate.yml src/hermes_skilleval/cli.py src/hermes_skilleval/release_manifest.py tests/test_release_manifest.py tests/test_cli_smoke.py tests/test_phase18_artifacts.py
```

Expected: only Phase 18 files and docs changed.

- [ ] **Step 7: Commit**

Run:

```bash
git add .github/workflows/validate.yml README.md docs src tests
git commit -m "feat: add phase18 release reproducibility pack"
```

Expected: commit succeeds.

---

## Out of Scope

- No router retraining.
- No new benchmark labels.
- No default switch to `finetuned-embedding`.
- No checkpoint or model-weight commits.
- No standard benchmark, external benchmark, SOTA, or production-readiness claims.

---

## Self-Review

- Spec coverage: The plan covers a pure manifest module, CLI orchestration, CI wiring, committed artifacts, docs, human brief, tests, and final verification.
- Placeholder scan: No placeholder markers remain.
- Type consistency: The plan consistently uses `release-check`, `release-manifest.json`, `release-manifest.md`, and `release-check-summary.json`.
- Scope check: Phase 18 is one coherent release reproducibility phase. External blind-pack expansion is deferred to Phase 19.
