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
    human_brief = Path(
        "docs/human-briefs/2026-05-30-phase18-ci-release-reproducibility-pack.html"
    ).read_text(encoding="utf-8")
    manifest_md = (ROOT / "release-manifest.md").read_text(encoding="utf-8")

    assert "Phase 18" in readme
    assert "release-check" in readme
    assert "docs/phase18.md" in readme
    assert "docs/demo/phase18-ci-release-reproducibility/release-manifest.json" in readme
    assert "Phase 18: CI Release Reproducibility Pack" in phase18
    assert "KEEP_BASELINE" in phase18
    assert "Phase 18" in handoff
    assert "release-manifest.json" in handoff
    assert "验证命令" in human_brief
    assert "Release reproducibility PASS" in human_brief
    assert "Phase 18 Release Reproducibility Manifest" in manifest_md
