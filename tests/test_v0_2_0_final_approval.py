from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.2.0.md"
FINAL_APPROVAL = ROOT / "docs" / "demo" / "v0.2.0-final-approval"
FINAL_APPROVAL_JSON = FINAL_APPROVAL / "final-approval.json"
FINAL_APPROVAL_MD = FINAL_APPROVAL / "final-approval.md"
INPUT_MANIFEST = FINAL_APPROVAL / "input-manifest.json"

RELEASE_DECISION_JSON = (
    ROOT / "docs" / "demo" / "v0.2.0-release-decision" / "release-decision.json"
)
RELEASE_DECISION_MD = (
    ROOT / "docs" / "demo" / "v0.2.0-release-decision" / "release-decision.md"
)
PHASE17_DECISION = (
    ROOT / "docs" / "demo" / "phase17-calibrated-release-selector" / "release-decision.json"
)
PHASE18_RELEASE_CHECK = (
    ROOT / "docs" / "demo" / "phase18-ci-release-reproducibility" / "release-check-summary.json"
)
LOCAL_ACTION_GATE = (
    ROOT / "docs" / "demo" / "external-repo-action-smoke-pack" / "output" / "gate-report.json"
)
HOSTED_ACTION_METADATA = ROOT / "docs" / "demo" / "hosted-consumer-action-smoke" / "run-metadata.json"
HOSTED_ACTION_GATE = (
    ROOT / "docs" / "demo" / "hosted-consumer-action-smoke" / "output" / "gate-report.json"
)

REQUIRED_INPUT_PATHS = [
    "docs/release-notes/v0.2.0.md",
    "docs/demo/v0.2.0-release-decision/release-decision.json",
    "docs/demo/v0.2.0-release-decision/release-decision.md",
    "docs/demo/v0.2.0-release-decision/input-manifest.json",
    "docs/demo/phase16-blind-validation/comparison.md",
    "docs/demo/phase17-calibrated-release-selector/release-decision.json",
    "docs/demo/phase17-calibrated-release-selector/release-decision.md",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.json",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.md",
    "docs/demo/phase18-ci-release-reproducibility/release-check-summary.json",
    "docs/demo/external-repo-action-smoke-pack/output/gate-report.json",
    "docs/demo/external-repo-action-smoke-pack/output/ci-summary.json",
    "docs/demo/hosted-consumer-action-smoke/run-metadata.json",
    "docs/demo/hosted-consumer-action-smoke/output/gate-report.json",
    "docs/demo/hosted-consumer-action-smoke/output/ci-summary.json",
]

FORBIDDEN_CLAIMS = [
    "v0.2.0 has been released",
    "v0.2.0 is released",
    "released v0.2.0",
    "tag v0.2.0 exists",
    "github release exists",
    "published to the github marketplace",
    "marketplace publication complete",
    "posts pr comments",
    "writes pr annotations",
    "hosted saas dashboard",
    "runtime mcp router for agents",
    "sota benchmark status",
    "production-ready",
    "proves production readiness",
    "approves the release",
    "automatic merge approval enabled",
    "finetuned-embedding is approved as default",
    "uses: raidriar7170/hermes-skilleval@v0.2.0",
    "gh release create",
]


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown_links(markdown: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)


def test_v0_2_0_final_approval_files_exist() -> None:
    for path in [RELEASE_NOTES, FINAL_APPROVAL_JSON, FINAL_APPROVAL_MD, INPUT_MANIFEST]:
        assert path.is_file(), path


def test_release_notes_are_final_bounded_and_evidence_linked() -> None:
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    for phrase in [
        "# v0.2.0",
        "published GitHub Release package",
        "not a Marketplace Action release",
        "implemented capabilities",
        "pre-publish `NEEDS_REVIEW`",
        "KEEP_BASELINE",
        "baseline-minilm",
        "`finetuned-embedding` is not approved as default",
        "reusable GitHub Action support",
        "local external-consumer action smoke",
        "hosted consumer action smoke",
        "pre-publish reviewer-facing checklist",
        "post-release evidence",
    ]:
        assert phrase in notes

    assert "Reusable GitHub Action RC" not in notes
    assert "not a v0.2.0 release" not in notes

    for required_link in [
        "../demo/v0.2.0-release-decision/release-decision.md",
        "../demo/phase16-blind-validation/comparison.md",
        "../demo/phase17-calibrated-release-selector/release-decision.md",
        "../demo/phase18-ci-release-reproducibility/release-manifest.md",
        "../demo/external-repo-action-smoke-pack/output/gate-report.md",
        "../demo/hosted-consumer-action-smoke/run-metadata.json",
        "../demo/v0.2.0-final-approval/final-approval.md",
    ]:
        assert f"]({required_link})" in notes

    for link in _markdown_links(notes):
        if link.startswith(("http://", "https://", "#")):
            continue
        assert (RELEASE_NOTES.parent / link.split("#", 1)[0]).resolve().exists(), link


def test_final_approval_json_matches_source_evidence_and_stays_unpublished() -> None:
    approval = _json(FINAL_APPROVAL_JSON)
    decision = _json(RELEASE_DECISION_JSON)
    phase17 = _json(PHASE17_DECISION)
    phase18 = _json(PHASE18_RELEASE_CHECK)
    local_gate = _json(LOCAL_ACTION_GATE)
    hosted_metadata = _json(HOSTED_ACTION_METADATA)
    hosted_gate = _json(HOSTED_ACTION_GATE)

    assert approval["artifact_type"] == "v0.2.0-final-approval-checklist"
    assert approval["schema_version"] == "v0.2.0-final-approval.v1"
    assert approval["release_version"] == "v0.2.0"
    assert approval["overall_decision"] == "NEEDS_REVIEW"
    assert approval["published"] is False
    assert approval["tag_created"] is False
    assert approval["github_release_created"] is False
    assert approval["marketplace_published"] is False
    assert approval["release_actions_require_human_confirmation"] is True

    assert approval["release_decision"] == decision["release_decision"] == "NEEDS_REVIEW"
    assert approval["router_decision"] == phase17["decision"] == "KEEP_BASELINE"
    assert approval["default_router"] == phase17["selected_router"] == "baseline-minilm"
    assert approval["finetuned_embedding_approved_for_default"] is False
    assert approval["release_check_status"] == phase18["status"] == "PASS"
    assert approval["local_action_smoke_decision"] == local_gate["decision"] == "ALLOW_MERGE"
    assert approval["hosted_action_smoke_decision"] == hosted_gate["decision"] == "ALLOW_MERGE"
    assert approval["hosted_action_run_url"] == hosted_metadata["run_url"]

    check_names = {check["name"] for check in approval["review_checks"]}
    assert check_names == {
        "release-notes-draft",
        "release-decision-package",
        "router-release-gate",
        "local-action-smoke",
        "hosted-action-smoke",
        "focused-tests",
        "full-pytest",
        "openspec-strict",
        "release-check",
        "v0.2.0-tag-absent",
        "v0.2.0-github-release-absent",
        "overclaim-and-secret-scan",
    }
    assert all(check["status"] in {"PASS", "READY_FOR_REVIEW"} for check in approval["review_checks"])


def test_final_approval_markdown_has_go_no_go_and_confirmation_sections() -> None:
    markdown = FINAL_APPROVAL_MD.read_text(encoding="utf-8")

    for phrase in [
        "# v0.2.0 Final Approval Checklist",
        "Overall decision: `NEEDS_REVIEW`",
        "Published: `false`",
        "## GO Conditions",
        "## NO-GO Until",
        "## Requires Human Confirmation",
        "create tag `v0.2.0`",
        "create a GitHub Release",
        "Marketplace publication",
        "not automatic publication",
        "not release approval",
        "not a v0.2.0 release",
    ]:
        assert phrase in markdown

    for required_link in [
        "../../release-notes/v0.2.0.md",
        "../v0.2.0-release-decision/release-decision.md",
        "../phase16-blind-validation/comparison.md",
        "../phase17-calibrated-release-selector/release-decision.md",
        "../phase18-ci-release-reproducibility/release-manifest.md",
        "../external-repo-action-smoke-pack/output/gate-report.md",
        "../hosted-consumer-action-smoke/run-metadata.json",
        "final-approval.json",
        "input-manifest.json",
    ]:
        assert f"]({required_link})" in markdown

    for link in _markdown_links(markdown):
        if link.startswith(("http://", "https://", "#")):
            continue
        assert (FINAL_APPROVAL / link.split("#", 1)[0]).resolve().exists(), link


def test_final_approval_manifest_lists_current_sources_with_hashes() -> None:
    manifest = _json(INPUT_MANIFEST)

    assert manifest["artifact_type"] == "v0.2.0-final-approval-input-manifest"
    assert manifest["approval_package_dir"] == "docs/demo/v0.2.0-final-approval"
    assert manifest["package_files"] == [
        "final-approval.json",
        "final-approval.md",
        "input-manifest.json",
    ]

    sources = {source["path"]: source for source in manifest["source_artifacts"]}
    assert list(sources) == REQUIRED_INPUT_PATHS
    for relative_path in REQUIRED_INPUT_PATHS:
        source = ROOT / relative_path
        assert source.is_file(), relative_path
        assert sources[relative_path]["exists"] is True
        if relative_path == "docs/release-notes/v0.2.0.md":
            # The final-approval manifest is historical pre-publish evidence;
            # post-release note edits must not force rewriting that package.
            assert sources[relative_path]["sha256"]
            assert sources[relative_path]["size_bytes"] > 0
            continue
        assert sources[relative_path]["sha256"] == _sha256(source)
        assert sources[relative_path]["size_bytes"] == source.stat().st_size


def test_final_approval_artifacts_do_not_make_forbidden_claims() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [RELEASE_NOTES, FINAL_APPROVAL_JSON, FINAL_APPROVAL_MD, INPUT_MANIFEST]
    ).lower()

    for phrase in [
        "not a Marketplace Action release",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not benchmark status",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
        "not a v0.2.0 release",
    ]:
        assert phrase.lower() in combined

    for claim in FORBIDDEN_CLAIMS:
        assert claim not in combined
