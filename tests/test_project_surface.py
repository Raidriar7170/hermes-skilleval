from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
DASHBOARD_SCREENSHOT = ROOT / "docs" / "assets" / "dashboard-screenshot.png"
MIGRATION_PROTOCOL = ROOT / "docs" / "skill-library-migration-protocol.md"
EXPERIMENT_TIMELINE = ROOT / "docs" / "experiment-timeline.md"
USAGE = ROOT / "docs" / "usage.md"
DIAGNOSTIC_DEMO = ROOT / "docs" / "demo" / "diagnostic-onboarding"
RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.1.0.md"
CURRENT_HUMAN_BRIEFS = [
    ROOT / "docs" / "human-briefs" / "2026-06-02-diagnostic-skill-library-onboarding.html",
    ROOT / "docs" / "human-briefs" / "2026-06-02-diagnostic-demo-evidence-pack.html",
    ROOT / "docs" / "human-briefs" / "2026-06-02-diagnostic-ci-gate.html",
    ROOT / "docs" / "human-briefs" / "2026-06-03-diagnostic-artifact-drift-ci-workflow.html",
    ROOT / "docs" / "human-briefs" / "2026-06-03-pr-facing-ci-summary.html",
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


def test_current_public_surfaces_use_latest_full_suite_count():
    surfaces = [README, USAGE, *CURRENT_HUMAN_BRIEFS]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)

    assert "372 passed" in combined
    for stale_count in [
        "366 passed",
        "365 passed",
        "361 passed",
        "314 passed",
        "334 passed",
        "338 passed",
        "344 passed",
        "346 passed",
        "| Test cases | 361 |",
        "| Test cases | 365 |",
        "| Test cases | 314 |",
        "| Test cases | 346 |",
        "| Test cases | 366 |",
    ]:
        assert stale_count not in combined


def test_release_notes_are_reviewer_ready_and_conservative():
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    assert "# v0.1.0 - CI-backed Skill Routing Evaluation Harness" in notes
    assert "KEEP_BASELINE" in notes
    assert "baseline-minilm" in notes
    assert "SOTA" not in notes
