from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "demo" / "v0.2.0-release-decision"
DECISION_JSON = PACKAGE / "release-decision.json"
DECISION_MD = PACKAGE / "release-decision.md"
INPUT_MANIFEST = PACKAGE / "input-manifest.json"

PHASE16_REGRESSION = ROOT / "docs" / "demo" / "phase16-blind-validation" / "regression-summary.json"
PHASE16_COMPARISON = ROOT / "docs" / "demo" / "phase16-blind-validation" / "comparison.md"
PHASE16_ROUTE_DIFFS = ROOT / "docs" / "demo" / "phase16-blind-validation" / "route-diffs.jsonl"
PHASE17_DECISION_JSON = (
    ROOT / "docs" / "demo" / "phase17-calibrated-release-selector" / "release-decision.json"
)
PHASE17_DECISION_MD = (
    ROOT / "docs" / "demo" / "phase17-calibrated-release-selector" / "release-decision.md"
)
PHASE18_MANIFEST_JSON = (
    ROOT / "docs" / "demo" / "phase18-ci-release-reproducibility" / "release-manifest.json"
)
PHASE18_MANIFEST_MD = (
    ROOT / "docs" / "demo" / "phase18-ci-release-reproducibility" / "release-manifest.md"
)
PHASE18_RELEASE_CHECK = (
    ROOT / "docs" / "demo" / "phase18-ci-release-reproducibility" / "release-check-summary.json"
)
LOCAL_ACTION_GATE = (
    ROOT / "docs" / "demo" / "external-repo-action-smoke-pack" / "output" / "gate-report.json"
)
LOCAL_ACTION_CI = (
    ROOT / "docs" / "demo" / "external-repo-action-smoke-pack" / "output" / "ci-summary.json"
)
HOSTED_ACTION_METADATA = ROOT / "docs" / "demo" / "hosted-consumer-action-smoke" / "run-metadata.json"
HOSTED_ACTION_GATE = (
    ROOT / "docs" / "demo" / "hosted-consumer-action-smoke" / "output" / "gate-report.json"
)
HOSTED_ACTION_CI = (
    ROOT / "docs" / "demo" / "hosted-consumer-action-smoke" / "output" / "ci-summary.json"
)

REQUIRED_SOURCE_PATHS = [
    "docs/demo/phase16-blind-validation/comparison.md",
    "docs/demo/phase16-blind-validation/regression-summary.json",
    "docs/demo/phase16-blind-validation/route-diffs.jsonl",
    "docs/demo/phase17-calibrated-release-selector/release-decision.json",
    "docs/demo/phase17-calibrated-release-selector/release-decision.md",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.json",
    "docs/demo/phase18-ci-release-reproducibility/release-manifest.md",
    "docs/demo/phase18-ci-release-reproducibility/release-check-summary.json",
    "docs/demo/external-repo-action-smoke-pack/output/gate-report.json",
    "docs/demo/external-repo-action-smoke-pack/output/gate-report.md",
    "docs/demo/external-repo-action-smoke-pack/output/ci-summary.json",
    "docs/demo/external-repo-action-smoke-pack/output/ci-summary.md",
    "docs/demo/hosted-consumer-action-smoke/run-metadata.json",
    "docs/demo/hosted-consumer-action-smoke/output/gate-report.json",
    "docs/demo/hosted-consumer-action-smoke/output/gate-report.md",
    "docs/demo/hosted-consumer-action-smoke/output/ci-summary.json",
    "docs/demo/hosted-consumer-action-smoke/output/ci-summary.md",
]

FORBIDDEN_STATUSES = {"RELEASED", "APPROVED", "PUBLISHED"}
FORBIDDEN_CLAIMS = [
    "v0.2.0 has been released",
    "v0.2.0 is released",
    "released v0.2.0",
    "v0.2.0 tag exists",
    "github release exists",
    "published to the github marketplace",
    "marketplace publication complete",
    "posts pr comments",
    "writes pr annotations",
    "hosted saas dashboard",
    "runtime mcp router for agents",
    "production-ready",
    "sota benchmark",
    "automatic merge approval enabled",
    "approves the release",
    "finetuned-embedding is approved as default",
    "uses: raidriar7170/hermes-skilleval@v0.2.0",
    "git tag v0.2.0",
    "gh release create",
]


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown_links(markdown: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)


def test_v0_2_0_release_decision_package_files_exist() -> None:
    for path in [DECISION_JSON, DECISION_MD, INPUT_MANIFEST]:
        assert path.is_file(), path


def test_release_decision_json_records_review_not_publication() -> None:
    decision = _json(DECISION_JSON)

    assert decision["artifact_type"] == "v0.2.0-release-decision"
    assert decision["schema_version"] == "v0.2.0-release-decision.v1"
    assert decision["release_version"] == "v0.2.0"
    assert decision["release_decision"] == "NEEDS_REVIEW"
    assert decision["release_decision"] not in FORBIDDEN_STATUSES
    assert decision["published"] is False
    assert decision["github_release_created"] is False
    assert decision["tag_created"] is False
    assert decision["marketplace_published"] is False
    assert decision["release_actions_require_human_confirmation"] is True

    assert decision["router_decision"] == "KEEP_BASELINE"
    assert decision["default_router"] == "baseline-minilm"
    assert decision["candidate_router"] == "finetuned-embedding"
    assert decision["finetuned_embedding_approved_for_default"] is False


def test_release_decision_json_matches_current_source_evidence() -> None:
    decision = _json(DECISION_JSON)
    phase16 = _json(PHASE16_REGRESSION)
    phase17 = _json(PHASE17_DECISION_JSON)
    phase18 = _json(PHASE18_MANIFEST_JSON)
    release_check = _json(PHASE18_RELEASE_CHECK)
    local_gate = _json(LOCAL_ACTION_GATE)
    local_ci = _json(LOCAL_ACTION_CI)
    hosted_metadata = _json(HOSTED_ACTION_METADATA)
    hosted_gate = _json(HOSTED_ACTION_GATE)
    hosted_ci = _json(HOSTED_ACTION_CI)

    evidence = decision["evidence_summary"]
    assert evidence["phase16"]["guard_status"] == phase16["guard_status"]
    assert evidence["phase16"]["guard_status"] == phase17["source_guard_status"]
    assert evidence["phase16"]["regression_count"] == phase16["regression_count"]
    assert evidence["phase16"]["regression_count"] == phase17["regression_count"]
    assert evidence["phase16"]["task_count"] == phase16["task_count"]
    assert evidence["phase16"]["baseline_router"] == phase16["baseline_router"]
    assert evidence["phase16"]["candidate_router"] == phase16["candidate_router"]

    assert evidence["phase17"]["decision"] == phase17["decision"] == "KEEP_BASELINE"
    assert evidence["phase17"]["selected_router"] == phase17["selected_router"]
    assert evidence["phase17"]["approved_for_default"] == phase17["approved_for_default"]

    assert evidence["phase18"]["status"] == phase18["status"] == "PASS"
    assert evidence["phase18"]["release_check_status"] == release_check["status"] == "PASS"
    assert evidence["phase18"]["manifest_release_decision"] == phase18["release_decision"][
        "decision"
    ]

    assert evidence["action_rc"]["local_external_consumer"]["decision"] == local_gate[
        "decision"
    ]
    assert evidence["action_rc"]["local_external_consumer"]["ci_decision"] == local_ci[
        "decision"
    ]
    assert evidence["action_rc"]["hosted_consumer"]["decision"] == hosted_gate["decision"]
    assert evidence["action_rc"]["hosted_consumer"]["ci_decision"] == hosted_ci["decision"]
    assert evidence["action_rc"]["hosted_consumer"]["run_url"] == hosted_metadata["run_url"]


def test_input_manifest_lists_current_source_artifacts_with_hashes() -> None:
    manifest = _json(INPUT_MANIFEST)

    assert manifest["artifact_type"] == "v0.2.0-release-decision-input-manifest"
    assert manifest["decision_package_dir"] == "docs/demo/v0.2.0-release-decision"
    assert manifest["package_files"] == [
        "release-decision.json",
        "release-decision.md",
        "input-manifest.json",
    ]

    sources = {artifact["path"]: artifact for artifact in manifest["source_artifacts"]}
    assert list(sources) == REQUIRED_SOURCE_PATHS
    for relative_path in REQUIRED_SOURCE_PATHS:
        source = ROOT / relative_path
        assert source.is_file(), relative_path
        assert sources[relative_path]["exists"] is True
        assert sources[relative_path]["sha256"] == _sha256(source)
        assert sources[relative_path]["size_bytes"] == source.stat().st_size


def test_release_decision_markdown_links_evidence_and_requires_human_approval() -> None:
    markdown = DECISION_MD.read_text(encoding="utf-8")

    for phrase in [
        "# v0.2.0 Release Decision",
        "Decision: `NEEDS_REVIEW`",
        "Published: `false`",
        "Router decision: `KEEP_BASELINE`",
        "Default router: `baseline-minilm`",
        "`finetuned-embedding` is not approved as default",
        "human release review",
        "not automatic publication",
        "explicit human confirmation",
    ]:
        assert phrase in markdown

    for required_link in [
        "../phase16-blind-validation/comparison.md",
        "../phase16-blind-validation/regression-summary.json",
        "../phase16-blind-validation/route-diffs.jsonl",
        "../phase17-calibrated-release-selector/release-decision.md",
        "../phase17-calibrated-release-selector/release-decision.json",
        "../phase18-ci-release-reproducibility/release-manifest.md",
        "../phase18-ci-release-reproducibility/release-manifest.json",
        "../phase18-ci-release-reproducibility/release-check-summary.json",
        "../external-repo-action-smoke-pack/output/gate-report.md",
        "../external-repo-action-smoke-pack/output/ci-summary.md",
        "../hosted-consumer-action-smoke/run-metadata.json",
        "../hosted-consumer-action-smoke/output/gate-report.md",
        "../hosted-consumer-action-smoke/output/ci-summary.md",
        "release-decision.json",
        "input-manifest.json",
    ]:
        assert f"]({required_link})" in markdown

    for link in _markdown_links(markdown):
        if link.startswith(("http://", "https://", "#")):
            continue
        assert (PACKAGE / link.split("#", 1)[0]).resolve().exists(), link


def test_release_decision_artifacts_do_not_make_forbidden_claims() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in [DECISION_JSON, DECISION_MD, INPUT_MANIFEST]
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
