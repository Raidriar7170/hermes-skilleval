from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
DASHBOARD_SCREENSHOT = ROOT / "docs" / "assets" / "dashboard-screenshot.png"
MIGRATION_PROTOCOL = ROOT / "docs" / "skill-library-migration-protocol.md"
EXPERIMENT_TIMELINE = ROOT / "docs" / "experiment-timeline.md"
USAGE = ROOT / "docs" / "usage.md"
EVIDENCE_MAP = ROOT / "docs" / "evidence-map.md"
FAILURE_GALLERY = ROOT / "docs" / "failure-gallery.md"
NODE24_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-github-actions-node24-validation.html"
)
REUSABLE_ACTION_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-reusable-github-action-rc.html"
)
PUBLIC_EVIDENCE_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-public-evidence-surface-refresh.html"
)
DIAGNOSTIC_DEMO = ROOT / "docs" / "demo" / "diagnostic-onboarding"
EXTERNAL_VALIDATION_PACK = ROOT / "docs" / "demo" / "external-skill-library-validation"
RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.1.0.md"
PUBLIC_EVIDENCE_CHANGE = "public-evidence-surface-refresh"


def _openspec_change_artifact(relative_path: str) -> Path:
    active = ROOT / "openspec" / "changes" / PUBLIC_EVIDENCE_CHANGE / relative_path
    if active.exists():
        return active

    archive_root = ROOT / "openspec" / "changes" / "archive"
    archived = sorted(archive_root.glob(f"*-{PUBLIC_EVIDENCE_CHANGE}/{relative_path}"))
    if archived:
        return archived[-1]

    return active


CURRENT_HUMAN_BRIEFS = [
    ROOT / "docs" / "human-briefs" / "2026-06-02-diagnostic-skill-library-onboarding.html",
    ROOT / "docs" / "human-briefs" / "2026-06-02-diagnostic-demo-evidence-pack.html",
    ROOT / "docs" / "human-briefs" / "2026-06-02-diagnostic-ci-gate.html",
    ROOT / "docs" / "human-briefs" / "2026-06-03-diagnostic-artifact-drift-ci-workflow.html",
    ROOT / "docs" / "human-briefs" / "2026-06-03-pr-facing-ci-summary.html",
    ROOT / "docs" / "human-briefs" / "2026-06-03-external-skill-library-validation-pack.html",
    ROOT / "docs" / "human-briefs" / "2026-06-03-docs-evidence-map.html",
    ROOT / "docs" / "human-briefs" / "2026-06-04-failure-gallery.html",
    NODE24_HUMAN_BRIEF,
    REUSABLE_ACTION_HUMAN_BRIEF,
    PUBLIC_EVIDENCE_HUMAN_BRIEF,
]
CURRENT_OPENSPEC_CHANGE_ARTIFACTS = [
    _openspec_change_artifact("proposal.md"),
    _openspec_change_artifact("design.md"),
    _openspec_change_artifact("tasks.md"),
    _openspec_change_artifact("specs/docs-evidence-map/spec.md"),
]


def test_ci_workflow_runs_lightweight_pytest_validation():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "pytest -q" in workflow


def test_ci_workflow_runs_diagnostic_ci_gate_from_committed_demo_artifacts():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "skilleval diagnostic-ci-gate" in workflow
    for artifact in [
        "docs/demo/diagnostic-onboarding/scan.json",
        "docs/demo/diagnostic-onboarding/lint.json",
        "docs/demo/diagnostic-onboarding/inspect.json",
        "docs/demo/diagnostic-onboarding/route-browser-smoke.json",
        "docs/demo/diagnostic-onboarding/route-debug-red-green.json",
    ]:
        assert artifact in workflow

    assert "$RUNNER_TEMP/diagnostic-ci-gate-report.json" in workflow
    assert "$RUNNER_TEMP/diagnostic-ci-gate-report.md" in workflow
    assert "--max-lint-findings 5" in workflow
    assert "--max-conflict-clusters 4" in workflow
    assert "--max-route-risk-flags 15" in workflow
    assert "--min-route-candidates 3" in workflow
    assert "git diff --exit-code docs/demo/diagnostic-onboarding" not in workflow


def test_ci_workflow_regenerates_diagnostic_demo_and_runs_artifact_drift_check():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "RUNNER_TEMP/diagnostic-onboarding" in workflow
    assert "skilleval scan" in workflow
    assert "skilleval lint" in workflow
    assert "skilleval inspect" in workflow
    assert "skilleval route" in workflow
    assert "skilleval diagnostic-dashboard" in workflow
    assert "skilleval diagnostic-ci-gate" in workflow
    assert "skilleval diagnostic-pr-review-surface" in workflow
    assert "skilleval diagnostic-artifact-drift-check" in workflow
    assert '"$RUNNER_TEMP/diagnostic-onboarding/ci-gate-report.json"' in workflow
    assert '"$RUNNER_TEMP/diagnostic-onboarding/ci-gate-report.md"' in workflow
    assert '"$RUNNER_TEMP/diagnostic-onboarding/pr-review-packet.json"' in workflow
    assert '"$RUNNER_TEMP/diagnostic-onboarding/pr-review-packet.md"' in workflow
    assert "--expected docs/demo/diagnostic-onboarding" in workflow
    assert '--actual "$RUNNER_TEMP/diagnostic-onboarding"' in workflow
    assert '--output "$RUNNER_TEMP/diagnostic-artifact-drift.json"' in workflow
    assert '--markdown-output "$RUNNER_TEMP/diagnostic-artifact-drift.md"' in workflow
    assert "git diff --exit-code docs/demo/diagnostic-onboarding" not in workflow


def test_ci_workflow_regenerates_external_validation_pack_in_runner_temp():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "id: external_pack" in workflow
    assert "RUNNER_TEMP/external-skill-library-validation" in workflow
    assert "docs/demo/external-skill-library-validation/source/markdown-skills" in workflow
    assert "docs/demo/external-skill-library-validation/source/mcp-tool-schema/tools.json" in workflow
    assert "route-release-note-review.json" in workflow
    assert "route-workflow-evidence.json" in workflow
    assert "route-browser-console.json" in workflow
    assert "route-artifact-drift.json" in workflow
    assert "--expected docs/demo/external-skill-library-validation" in workflow
    assert '--actual "$RUNNER_TEMP/external-skill-library-validation"' in workflow
    assert '--output "$RUNNER_TEMP/external-skill-library-validation-drift.json"' in workflow
    assert "--check external-pack=${{ steps.external_pack.outcome }}" in workflow
    assert "${{ runner.temp }}/external-skill-library-validation" in workflow
    assert "${{ runner.temp }}/external-skill-library-validation-drift.json" in workflow


def test_ci_workflow_writes_pr_facing_summary_and_enforces_decision():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "continue-on-error: true" in workflow
    assert "if: always()" in workflow
    assert "skilleval ci-summary" in workflow
    assert "--check pytest=${{ steps.pytest.outcome }}" in workflow
    assert "--check openspec-validate=${{ steps.openspec_validate.outcome }}" in workflow
    assert "--check release-check=${{ steps.release_check.outcome }}" in workflow
    assert "--check diagnostic-gate=${{ steps.diagnostic_gate.outcome }}" in workflow
    assert "--check diagnostic-drift=${{ steps.diagnostic_drift.outcome }}" in workflow
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}" in workflow
    assert "PUSH_BEFORE_SHA: ${{ github.event.before }}" in workflow
    assert 'git diff --name-only "$BASE_SHA" "$GITHUB_SHA"' in workflow
    assert "$GITHUB_STEP_SUMMARY" in workflow
    assert "ALLOW_MERGE" in workflow
    assert "BLOCK_MERGE" in workflow
    assert "github-token" not in workflow
    assert "pulls/comments" not in workflow
    assert "::error" not in workflow


def test_ci_workflow_preflights_github_actions_node24_runtime():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert 'FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"' in workflow
    assert workflow.index("env:") < workflow.index("jobs:")
    assert "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION" not in workflow
    for existing_check in [
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/upload-artifact@v4",
        "pytest -q",
        "openspec validate --all --strict",
        "skilleval release-check",
        "skilleval diagnostic-ci-gate",
        "skilleval diagnostic-artifact-drift-check",
        "id: external_pack",
        "skilleval ci-summary",
        "CI summary decision",
    ]:
        assert existing_check in workflow


def test_readme_surfaces_live_dashboard_and_screenshot_near_key_results():
    readme = README.read_text(encoding="utf-8")
    key_results = readme.index("## Key Results")
    architecture = readme.index("## Architecture")
    limitations = readme.index("## Limitations / Boundaries")
    live_dashboard = readme.index("### Live Dashboard")
    screenshot = readme.index("docs/assets/dashboard-screenshot.png")

    assert key_results < live_dashboard < architecture
    assert key_results < screenshot < architecture
    assert key_results < limitations < architecture
    assert "actions/workflows/validate.yml/badge.svg" in readme
    assert "run filtering" in readme
    assert "failure inspection" in readme
    assert "raw JSON audit" in readme
    assert "### Example Failure Caught by the Release Gate" in readme
    assert "blind-claude-mcp-routing" in readme
    assert "This is a self-built Hermes-style benchmark" in readme
    assert "docs/experiment-timeline.md" in readme


def test_dashboard_screenshot_asset_exists():
    assert DASHBOARD_SCREENSHOT.is_file()
    assert DASHBOARD_SCREENSHOT.stat().st_size > 20_000


def test_skill_library_migration_protocol_is_actionable():
    protocol = MIGRATION_PROTOCOL.read_text(encoding="utf-8")

    required_phrases = (
        "Superpowers skills",
        "Codex skills",
        "Claude Code style skills",
        "browser-use-vision / gui-agent-benchmark",
        "10-20",
        "task success",
        "tool adaptation",
        "instruction fidelity",
        "failure recoverability",
        "evidence completeness",
        "summary JSON",
        "failure taxonomy",
        "dashboard comparison",
    )
    for phrase in required_phrases:
        assert phrase in protocol


def test_experiment_timeline_keeps_phase_history_outside_readme():
    readme = README.read_text(encoding="utf-8")
    timeline = EXPERIMENT_TIMELINE.read_text(encoding="utf-8")

    assert "| Phase 18 | CI-backed release reproducibility pack |" not in readme
    assert "| Phase 18 | CI-backed release reproducibility pack |" in timeline
    assert "| Phase 2 | Router comparison baseline |" in timeline


def test_readme_keeps_quick_start_short_and_links_full_usage():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")

    assert "For full CLI usage, see [`docs/usage.md`](docs/usage.md)." in readme
    assert "skilleval release-check" in readme
    assert "### 1. Index a Hermes-style Skill Library" not in readme
    assert "## 1. Index a Hermes-style Skill Library" in usage
    assert "## 17. Run Tests" in usage


def test_evidence_map_is_linked_from_public_entry_points():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")

    assert "[`docs/evidence-map.md`](docs/evidence-map.md)" in readme
    assert "[`docs/evidence-map.md`](evidence-map.md)" in usage
    assert "# Hermes SkillEval Evidence Map" in evidence_map
    assert "navigation layer, not a second source of truth" in evidence_map


def test_evidence_map_groups_current_proof_chain_and_local_links_exist():
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")

    for heading in [
        "## Project Positioning",
        "## Release-Gate Evidence",
        "## Diagnostic Onboarding Evidence",
        "## External-Style Validation Evidence",
        "## PR-Facing CI Evidence",
        "## Reusable Action RC Evidence",
        "## OpenSpec Specs",
        "## Human Briefs",
    ]:
        assert heading in evidence_map

    for required_path in [
        "../README.md",
        "release-handoff.md",
        "demo/phase16-blind-validation/comparison.md",
        "demo/phase17-calibrated-release-selector/release-decision.md",
        "demo/phase18-ci-release-reproducibility/release-manifest.md",
        "demo/diagnostic-onboarding/README.md",
        "demo/external-skill-library-validation/README.md",
        "../.github/workflows/validate.yml",
        "../action.yml",
        "../examples/github-action/README.md",
        "../examples/github-action/.github/workflows/skilleval.yml",
        "../openspec/specs/pr-facing-ci-summary/spec.md",
        "../openspec/specs/reusable-github-action-rc/spec.md",
        "human-briefs/2026-06-04-reusable-github-action-rc.html",
        "human-briefs/2026-06-04-autonomous-loop-reusable-github-action-rc.html",
        "human-briefs/2026-06-03-autonomous-loop-external-skill-library-validation-pack.html",
    ]:
        assert f"]({required_path})" in evidence_map

    for link in _markdown_links(evidence_map):
        if link.startswith(("http://", "https://", "#")):
            continue
        target = (EVIDENCE_MAP.parent / link.split("#", 1)[0]).resolve()
        assert target.exists(), f"broken evidence map link: {link}"


def test_evidence_map_docs_are_bounded_and_do_not_overclaim():
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    combined = "\n".join(
        [
            README.read_text(encoding="utf-8"),
            USAGE.read_text(encoding="utf-8"),
            evidence_map,
        ]
    )

    for phrase in [
        "not a Marketplace Action",
        "not a Marketplace Action release",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
        "not a v0.2.0 release",
    ]:
        assert phrase in evidence_map
        assert phrase in combined

    for risky_claim in [
        "released as a Marketplace Action",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "provides runtime MCP routing",
        "SOTA benchmark",
        "production-ready",
        "proves production readiness",
        "automatic merge approval enabled",
        "approves the release",
    ]:
        assert risky_claim not in combined


def test_synced_openspec_specs_have_explicit_purpose_text():
    spec_root = ROOT / "openspec" / "specs"

    for spec in sorted(spec_root.glob("*/spec.md")):
        text = spec.read_text(encoding="utf-8")
        assert "\n## Purpose\n" in text
        assert "TBD - created by archiving" not in text, spec
        assert "Update Purpose after archive" not in text, spec

    docs_evidence_spec = (spec_root / "docs-evidence-map" / "spec.md").read_text(
        encoding="utf-8"
    )
    assert "Reusable Action RC Evidence" in docs_evidence_spec
    assert "reusable GitHub Action RC" in docs_evidence_spec


def test_failure_gallery_is_linked_from_public_entry_points():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    gallery = FAILURE_GALLERY.read_text(encoding="utf-8")

    assert "[`docs/failure-gallery.md`](docs/failure-gallery.md)" in readme
    assert "[`docs/failure-gallery.md`](failure-gallery.md)" in usage
    assert "[`docs/failure-gallery.md`](failure-gallery.md)" in evidence_map
    assert "# Hermes SkillEval Failure Gallery" in gallery
    assert "navigation layer over committed failure evidence" in gallery
    assert "canonical evidence remains in the linked artifacts" in gallery


def test_failure_gallery_groups_current_failure_evidence_and_local_links_exist():
    gallery = FAILURE_GALLERY.read_text(encoding="utf-8")

    for heading in [
        "## Release-Gate Regression Examples",
        "## Diagnostic Routing-Clarity Examples",
        "## External-Style Validation Examples",
        "## CI Boundary Examples",
        "## How To Use This Gallery",
    ]:
        assert heading in gallery

    for required_path in [
        "demo/phase16-blind-validation/comparison.md",
        "demo/phase16-blind-validation/route-diffs.jsonl",
        "demo/phase17-calibrated-release-selector/release-decision.md",
        "demo/phase18-ci-release-reproducibility/release-manifest.md",
        "demo/diagnostic-onboarding/lint.json",
        "demo/diagnostic-onboarding/inspect.json",
        "demo/diagnostic-onboarding/route-browser-smoke.json",
        "demo/diagnostic-onboarding/pr-review-packet.md",
        "demo/external-skill-library-validation/README.md",
        "../.github/workflows/validate.yml",
        "../openspec/specs/pr-facing-ci-summary/spec.md",
    ]:
        assert f"]({required_path})" in gallery

    for phrase in [
        "REVIEW_REQUIRED",
        "KEEP_BASELINE",
        "new_negative_skill_selected",
        "missing_negative_boundaries",
        "review-worthy conflict risk clusters",
        "ALLOW_MERGE",
        "BLOCK_MERGE",
    ]:
        assert phrase in gallery

    for link in _markdown_links(gallery):
        if link.startswith(("http://", "https://", "#")):
            continue
        target = (FAILURE_GALLERY.parent / link.split("#", 1)[0]).resolve()
        assert target.exists(), f"broken failure gallery link: {link}"


def test_failure_gallery_docs_are_bounded_and_do_not_overclaim():
    gallery = FAILURE_GALLERY.read_text(encoding="utf-8")
    combined = "\n".join(
        [
            README.read_text(encoding="utf-8"),
            USAGE.read_text(encoding="utf-8"),
            EVIDENCE_MAP.read_text(encoding="utf-8"),
            gallery,
        ]
    )

    for phrase in [
        "not a Marketplace Action",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not benchmark status",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
    ]:
        assert phrase in gallery
        assert phrase in combined

    for risky_claim in [
        "released as a Marketplace Action",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "provides runtime MCP routing",
        "SOTA benchmark",
        "production-ready",
        "proves production readiness",
        "automatic merge approval enabled",
        "approves the release",
    ]:
        assert risky_claim not in combined


def test_diagnostic_ci_gate_surface_is_artifact_based_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    report = (DIAGNOSTIC_DEMO / "ci-gate-report.md").read_text(encoding="utf-8")
    combined = "\n".join([readme, usage, report])

    assert "artifact-based CI validation" in combined
    assert "skilleval diagnostic-ci-gate" in combined
    for phrase in [
        "not a Marketplace Action",
        "not a PR annotation system",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
    ]:
        assert phrase in combined

    risky_claims = [
        "released as a Marketplace Action",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark",
    ]
    for phrase in risky_claims:
        assert phrase not in combined


def test_pr_facing_ci_summary_surface_is_local_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    brief = (
        ROOT / "docs" / "human-briefs" / "2026-06-03-pr-facing-ci-summary.html"
    ).read_text(encoding="utf-8")
    combined = "\n".join([readme, usage, workflow, brief])

    assert "PR-facing CI Summary" in combined
    assert "skilleval ci-summary" in combined
    assert "local/GitHub Actions summary" in combined
    assert "not a GitHub API comment bot" in combined
    assert "not a PR annotation system" in combined
    assert "not a Marketplace Action" in combined
    assert "not SaaS" in combined
    assert "not a runtime MCP router" in combined
    assert "not release approval" in combined

    risky_claims = [
        "released as a Marketplace Action",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark",
        "approves the release",
    ]
    for phrase in risky_claims:
        assert phrase not in combined


def test_external_validation_pack_docs_are_local_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    pack_readme = (EXTERNAL_VALIDATION_PACK / "README.md").read_text(encoding="utf-8")
    combined = "\n".join([readme, usage, pack_readme])

    assert "External Skill Library Validation Pack" in combined
    assert "docs/demo/external-skill-library-validation" in combined
    assert "source/markdown-skills" in combined
    assert "source/mcp-tool-schema/tools.json" in combined
    assert "skilleval diagnostic-artifact-drift-check" in combined
    assert "--check external-pack=success" in combined
    for phrase in [
        "not a Marketplace Action",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not benchmark status",
        "not production readiness",
        "not release approval",
    ]:
        assert phrase in combined

    risky_claims = [
        "released as a Marketplace Action",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark status",
        "production-ready",
        "approves the release",
    ]
    for phrase in risky_claims:
        assert phrase not in combined


def test_node24_ci_preflight_docs_are_local_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    brief = NODE24_HUMAN_BRIEF.read_text(encoding="utf-8")
    combined = "\n".join([readme, usage, workflow, brief])

    assert "GitHub Actions Node 24 preflight" in combined
    assert "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" in combined
    assert "github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners" in combined
    assert "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION" not in combined
    for phrase in [
        "not a Marketplace Action",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not benchmark status",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
        "not a permanent compatibility guarantee",
    ]:
        assert phrase in combined

    risky_claims = [
        "released as a Marketplace Action",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark status",
        "production-ready",
        "approves the release",
        "guarantees future GitHub Actions compatibility",
    ]
    for phrase in risky_claims:
        assert phrase not in combined


def test_current_public_surfaces_use_latest_full_suite_count():
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    evidence_map_briefs = [
        EVIDENCE_MAP.parent / link
        for link in _markdown_links(evidence_map)
        if link.startswith("human-briefs/")
    ]
    surfaces = [
        README,
        USAGE,
        *CURRENT_HUMAN_BRIEFS,
        *evidence_map_briefs,
        *CURRENT_OPENSPEC_CHANGE_ARTIFACTS,
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)

    assert "392 passed" in combined
    assert "392 pytest cases" in README.read_text(encoding="utf-8")
    for stale_count in [
        "391 pytest cases",
        "386 pytest cases",
        "384 pytest cases",
        "381 pytest cases",
        "378 pytest cases",
        "372 pytest cases",
        "365 pytest cases",
        "365 unit and smoke tests",
        "365 passing tests",
        "391 passed",
        "391 passing tests",
        "386 passed",
        "384 passed",
        "381 passed",
        "378 passed",
        "372 passed",
        "366 passed",
        "365 passed",
        "361 passed",
        "314 passed",
        "334 passed",
        "338 passed",
        "344 passed",
        "346 passed",
        "| Test cases | 391 |",
        "| Test cases | 361 |",
        "| Test cases | 365 |",
        "| Test cases | 314 |",
        "| Test cases | 346 |",
        "| Test cases | 366 |",
        "| Test cases | 372 |",
        "| Test cases | 378 |",
        "| Test cases | 381 |",
        "| Test cases | 386 |",
        "| Test cases | 384 |",
    ]:
        assert stale_count not in combined


def test_release_notes_are_reviewer_ready_and_conservative():
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    assert "# v0.1.0 - CI-backed Skill Routing Evaluation Harness" in notes
    assert "KEEP_BASELINE" in notes
    assert "baseline-minilm" in notes
    assert "SOTA" not in notes


def _markdown_links(markdown: str) -> list[str]:
    import re

    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
