import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURRENT_FULL_SUITE_COUNT = "698"
README = ROOT / "README.md"
RESUME = ROOT / "docs" / "resume.md"
INTERVIEW_OVERVIEW = ROOT / "docs" / "interview-project-overview.html"
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_INIT = ROOT / "src" / "hermes_skilleval" / "__init__.py"
ACTION = ROOT / "action.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
GITHUB_ACTION_GATE = ROOT / "src" / "hermes_skilleval" / "github_action_gate.py"
DASHBOARD_SCREENSHOT = ROOT / "docs" / "assets" / "dashboard-screenshot.png"
MIGRATION_PROTOCOL = ROOT / "docs" / "skill-library-migration-protocol.md"
EXPERIMENT_TIMELINE = ROOT / "docs" / "experiment-timeline.md"
USAGE = ROOT / "docs" / "usage.md"
EVIDENCE_MAP = ROOT / "docs" / "evidence-map.md"
DEMO_REPO_PLAN = ROOT / "docs" / "demo-repo-plan.md"
V0_2_1_RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.2.1.md"
GITHUB_ACTION_EXAMPLE = ROOT / "examples" / "github-action"
GITHUB_ACTION_EXAMPLE_WORKFLOW = (
    GITHUB_ACTION_EXAMPLE / ".github" / "workflows" / "skilleval.yml"
)
FAILURE_GALLERY = ROOT / "docs" / "failure-gallery.md"
NODE24_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-github-actions-node24-validation.html"
)
REUSABLE_ACTION_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-reusable-github-action-rc.html"
)
EXTERNAL_REPO_ACTION_SMOKE_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-external-repo-action-smoke-pack.html"
)
HOSTED_CONSUMER_ACTION_SMOKE_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-hosted-consumer-action-smoke.html"
)
V0_2_0_RELEASE_DECISION_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-v0-2-0-release-decision.html"
)
PUBLIC_EVIDENCE_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-public-evidence-surface-refresh.html"
)
POST_RELEASE_ONBOARDING_HUMAN_BRIEF = (
    ROOT
    / "docs"
    / "human-briefs"
    / "2026-06-05-post-release-onboarding-cleanup.html"
)
RELEASE_HANDOFF = ROOT / "docs" / "release-handoff.md"
V0_2_0_RELEASE_DECISION_PACK = ROOT / "docs" / "demo" / "v0.2.0-release-decision"
V0_2_0_FINAL_APPROVAL_PACK = ROOT / "docs" / "demo" / "v0.2.0-final-approval"
V0_2_0_RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.2.0.md"
V0_2_1_POST_RELEASE = ROOT / "docs" / "demo" / "v0.2.1-post-release"
DIAGNOSTIC_DEMO = ROOT / "docs" / "demo" / "diagnostic-onboarding"
EXTERNAL_VALIDATION_PACK = ROOT / "docs" / "demo" / "external-skill-library-validation"
EXTERNAL_REPO_ACTION_SMOKE_PACK = (
    ROOT / "docs" / "demo" / "external-repo-action-smoke-pack"
)
HOSTED_CONSUMER_ACTION_SMOKE_PACK = (
    ROOT / "docs" / "demo" / "hosted-consumer-action-smoke"
)
RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.1.0.md"
V0_2_0_FINAL_APPROVAL_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-v0-2-0-release-notes-and-final-approval.html"
)
PUBLIC_EVIDENCE_CHANGE = "public-evidence-surface-refresh"
EXTERNAL_REPO_ACTION_SMOKE_CHANGE = "external-repo-action-smoke-pack"
HOSTED_CONSUMER_ACTION_SMOKE_CHANGE = "hosted-consumer-action-smoke"


def _openspec_change_artifact(relative_path: str) -> Path:
    return _openspec_named_change_artifact(PUBLIC_EVIDENCE_CHANGE, relative_path)


def _openspec_named_change_artifact(change: str, relative_path: str) -> Path:
    active = ROOT / "openspec" / "changes" / change / relative_path
    if active.exists():
        return active

    archive_root = ROOT / "openspec" / "changes" / "archive"
    archived = sorted(archive_root.glob(f"*-{change}/{relative_path}"))
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
    V0_2_0_RELEASE_DECISION_HUMAN_BRIEF,
    V0_2_0_FINAL_APPROVAL_HUMAN_BRIEF,
    PUBLIC_EVIDENCE_HUMAN_BRIEF,
    POST_RELEASE_ONBOARDING_HUMAN_BRIEF,
]
PUBLIC_EVIDENCE_CHANGE_ARTIFACTS = [
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


def test_post_release_metadata_and_action_onboarding_are_current():
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    package_init = PACKAGE_INIT.read_text(encoding="utf-8")
    action = ACTION.read_text(encoding="utf-8")
    current_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            README,
            USAGE,
            EVIDENCE_MAP,
            RELEASE_HANDOFF,
            V0_2_0_RELEASE_NOTES,
            V0_2_1_RELEASE_NOTES,
            GITHUB_ACTION_EXAMPLE / "README.md",
            GITHUB_ACTION_EXAMPLE_WORKFLOW,
            GITHUB_ACTION_GATE,
        ]
    )

    assert pyproject["project"]["version"] == "0.3.0"
    assert '__version__ = "0.3.0"' in package_init
    assert "Hermes SkillEval Reusable GitHub Action" in action
    assert "Hermes SkillEval Reusable Action RC" not in action
    assert "Raidriar7170/hermes-skilleval@v0.3.0" in current_docs
    assert "Raidriar7170/hermes-skilleval@main" not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            README,
            USAGE,
            GITHUB_ACTION_EXAMPLE / "README.md",
            GITHUB_ACTION_EXAMPLE_WORKFLOW,
        ]
    )
    assert "Reusable GitHub Action RC" not in current_docs
    assert "not a v0.2.0 release" not in current_docs
    assert "0.1.0" not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in [README, USAGE, V0_2_0_RELEASE_NOTES]
    )


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


def test_readme_presents_post_release_developer_tool_front_door():
    readme = README.read_text(encoding="utf-8")
    tagline = (
        "Evaluate, route, and regression-test agent skills before they break "
        "your coding agent."
    )
    first_screen = readme[: readme.index("## Architecture")]
    architecture = readme.index("## Architecture")
    limitations = readme.index("## Limitations / Boundaries")
    dashboard_preview = readme.index("## Dashboard preview")
    screenshot = readme.index("docs/assets/dashboard-screenshot.png")

    assert tagline in first_screen
    assert (
        "**Language / 语言:** [中文总览](#总览) · "
        "[English README](#what-it-does) · "
        "[中文完整说明](https://raidriar7170.github.io/hermes-skilleval/docs/interview-project-overview.html)"
    ) in first_screen
    assert (
        "Hermes SkillEval helps maintainers of Claude Code, Codex, Cursor-style "
        "skill libraries, and MCP tool schemas detect wrong-skill activations, "
        "near-miss conflicts, and routing regressions in CI"
    ) in first_screen
    assert "## 总览" in first_screen
    assert "面向 AI 编程 Agent 技能库的离线评测和 CI 回归门禁项目" in first_screen
    assert "系统能不能稳定选中正确技能" in first_screen
    assert "避免误触看起来相关但实际错误的技能" in first_screen
    assert "带 gold / negative 标签的任务集" in first_screen
    assert "多类路由策略" in first_screen
    assert "错误的 negative skill" in first_screen
    assert "继续保留 `baseline-minilm`" in first_screen
    assert "`v0.3.0` 已发布，当前测试面为 `698` 个 pytest cases" in first_screen
    assert "`REVIEW_REQUIRED / KEEP_BASELINE`" in first_screen
    assert "`live_agent.overlap_status`" in first_screen
    assert "这不是 benchmark PASS、性能提升结论或 router promotion" in first_screen
    assert (
        "[中文完整说明](https://raidriar7170.github.io/hermes-skilleval/docs/interview-project-overview.html)"
        in first_screen
    )
    assert "(docs/interview-project-overview.html)" not in first_screen
    assert "[`docs/resume.md`](docs/resume.md)" not in first_screen
    assert "For Interviewers" not in first_screen
    assert "面试官关心" not in first_screen
    assert "If you only have three minutes" not in first_screen
    for heading in [
        "## 总览",
        "## What it does",
        "## Why skill routing is hard",
        "## Quick Start",
        "## v0.3.0 release status",
        "## Use as GitHub Action",
        "## Example failure caught",
        "## Dashboard preview",
        "## Evidence links",
        "## Limitations / Boundaries",
    ]:
        assert heading in first_screen
    assert dashboard_preview < architecture
    assert dashboard_preview < screenshot < architecture
    assert limitations < architecture
    assert "actions/workflows/validate.yml/badge.svg" in readme
    assert "badge/release-v0.3.0" in readme
    assert "badge/tests-698%20passed" in readme
    assert "badge/action-reusable%20repo%20Action" in readme
    assert "badge/A100-validated" not in first_screen
    assert "run filtering" in readme
    assert "failure inspection" in readme
    assert "raw JSON audit" in readme
    assert "## Example failure caught" in readme
    assert "blind-claude-mcp-routing" in readme
    assert (
        "This is a reusable repository Action, not a Marketplace-published "
        "Action, not a GitHub API PR comment bot, not a SaaS dashboard, and "
        "not a runtime MCP router."
    ) in readme
    assert "`baseline-minilm` remains the default router" in readme
    assert "`finetuned-embedding` is not approved as default" in readme
    assert "docs/experiment-timeline.md" in readme

    combined = "\n".join(
        [
            readme,
            RESUME.read_text(encoding="utf-8"),
            INTERVIEW_OVERVIEW.read_text(encoding="utf-8"),
        ]
    )

    assert f"{CURRENT_FULL_SUITE_COUNT} pytest cases" in combined
    assert f"{CURRENT_FULL_SUITE_COUNT} passing tests" in combined
    assert "314 tests" not in combined
    assert "314-test" not in combined
    assert "413 passed" not in combined
    assert "418 passed" not in combined


def test_dashboard_screenshot_asset_exists():
    assert DASHBOARD_SCREENSHOT.is_file()
    assert DASHBOARD_SCREENSHOT.stat().st_size > 20_000


def test_readme_architecture_and_structure_diagrams_render_as_mermaid():
    readme = README.read_text(encoding="utf-8")
    architecture = readme[
        readme.index("## Architecture / 系统架构") : readme.index(
            "## Project Structure / 项目结构"
        )
    ]
    project_structure = readme[
        readme.index("## Project Structure / 项目结构") : readme.index(
            "## Experiment Timeline / 实验演进"
        )
    ]

    assert "```mermaid\nflowchart TD" in architecture
    assert "```mermaid\nflowchart TD" in project_structure
    assert "Input corpus" in architecture
    assert "Router families" in architecture
    assert "Verification layer" in architecture
    assert "Skill metadata improvement loop" in architecture
    assert "Core runtime" in project_structure
    assert "src/hermes_skilleval" in project_structure
    assert "Reviewer evidence" in project_structure
    assert "Release evidence" in project_structure
    assert "```text" not in architecture
    assert "```text" not in project_structure
    assert "generate_benchmark_skills.py" not in project_structure
    assert "cross_encoder.py" not in project_structure


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
    assert "skilleval github-action-gate" in readme
    assert "Raidriar7170/hermes-skilleval@v0.3.0" in readme
    assert (
        "[`GitHub Release`](https://github.com/Raidriar7170/hermes-skilleval/"
        "releases/tag/v0.3.0)"
    ) in readme
    assert "[`release notes`](docs/release-notes/v0.3.0.md)" in readme
    assert (
        "[`closeout`](artifacts/v0.3/skillsbench-pilot/"
        "v0.3-stage2-real-codex-evidence-gate-closeout-20260708T080414Z/"
        "stage2-real-codex-evidence-gate-closeout.json)"
    ) in readme
    assert "No performance claim" in readme
    assert "router promotion" in readme
    assert "### 1. Index a Hermes-style Skill Library" not in readme
    assert "## Fresh-clone local demo" in usage
    assert "## GitHub Action trial" in usage
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
        "## Reusable GitHub Action Evidence",
        "## Local External Consumer Smoke Pack",
        "## Hosted Consumer Action Smoke Evidence",
        "## Release Evidence",
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
        "demo/external-repo-action-smoke-pack/README.md",
        "demo/external-repo-action-smoke-pack/output/gate-report.md",
        "demo/external-repo-action-smoke-pack/output/ci-summary.md",
        "demo/hosted-consumer-action-smoke/README.md",
        "demo/hosted-consumer-action-smoke/run-metadata.json",
        "demo/hosted-consumer-action-smoke/output/gate-report.md",
        "demo/hosted-consumer-action-smoke/output/ci-summary.md",
        "demo/v0.2.0-release-decision/release-decision.md",
        "demo/v0.2.0-release-decision/release-decision.json",
        "demo/v0.2.0-release-decision/input-manifest.json",
        "release-notes/v0.2.0.md",
        "demo/v0.2.0-final-approval/final-approval.md",
        "demo/v0.2.0-final-approval/final-approval.json",
        "demo/v0.2.0-final-approval/input-manifest.json",
        "demo/v0.2.0-post-release/post-release.md",
        "demo/v0.2.0-post-release/post-release.json",
        "release-notes/v0.2.1.md",
        "demo/v0.2.1-post-release/post-release.md",
        "demo/v0.2.1-post-release/post-release.json",
        "demo-repo-plan.md",
        "../openspec/specs/pr-facing-ci-summary/spec.md",
        "../openspec/specs/reusable-github-action-rc/spec.md",
        "../openspec/specs/v0-2-0-release-decision/spec.md",
        "../openspec/specs/v0-2-0-release-notes-and-final-approval/spec.md",
        "human-briefs/2026-06-04-reusable-github-action-rc.html",
        "human-briefs/2026-06-04-external-repo-action-smoke-pack.html",
        "human-briefs/2026-06-04-hosted-consumer-action-smoke.html",
        "human-briefs/2026-06-04-v0-2-0-release-decision.html",
        "human-briefs/2026-06-04-v0-2-0-release-notes-and-final-approval.html",
        "human-briefs/2026-06-05-post-release-onboarding-cleanup.html",
        "human-briefs/2026-06-04-autonomous-loop-v0-2-0-release-decision.html",
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
        "This is a reusable repository Action, not a Marketplace-published Action, not a GitHub API PR comment bot, not a SaaS dashboard, and not a runtime MCP router.",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
    ]:
        assert phrase in combined

    for phrase in [
        "not a v0.2.0 release",
        "Reusable GitHub Action RC Evidence",
        "release-candidate evidence",
    ]:
        assert phrase not in combined

    assert "historical pre-publish review artifacts" in evidence_map
    assert "post-release artifacts as the current publication record" in evidence_map

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
    assert "reusable GitHub Action evidence" in docs_evidence_spec
    assert "published `v0.2.0` state" in docs_evidence_spec

    external_smoke_docs_delta = _openspec_named_change_artifact(
        EXTERNAL_REPO_ACTION_SMOKE_CHANGE,
        "specs/docs-evidence-map/spec.md",
    ).read_text(encoding="utf-8")
    assert "external consumer smoke pack" in external_smoke_docs_delta

    hosted_smoke_docs_delta = _openspec_named_change_artifact(
        HOSTED_CONSUMER_ACTION_SMOKE_CHANGE,
        "specs/docs-evidence-map/spec.md",
    ).read_text(encoding="utf-8")
    assert "hosted consumer action smoke evidence" in hosted_smoke_docs_delta


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


def test_v0_2_0_release_decision_surfaces_are_linked_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    handoff = RELEASE_HANDOFF.read_text(encoding="utf-8")
    brief = V0_2_0_RELEASE_DECISION_HUMAN_BRIEF.read_text(encoding="utf-8")
    decision_md = (V0_2_0_RELEASE_DECISION_PACK / "release-decision.md").read_text(
        encoding="utf-8"
    )
    current = "\n".join([readme, usage, evidence_map, handoff])
    historical = "\n".join([brief, decision_md])
    combined = "\n".join([current, historical])

    for path in [
        "docs/demo/v0.2.0-release-decision/release-decision.md",
        "docs/demo/v0.2.0-release-decision/release-decision.json",
        "docs/demo/v0.2.0-release-decision/input-manifest.json",
        "docs/human-briefs/2026-06-04-v0-2-0-release-decision.html",
    ]:
        assert path in combined

    for phrase in [
        "v0.2.0 release decision",
        "NEEDS_REVIEW",
        "Published: `false`",
        "KEEP_BASELINE",
        "baseline-minilm",
        "`finetuned-embedding` is not approved as default",
        "human release review",
        "not automatic publication",
        "explicit human confirmation",
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
        assert phrase in historical

    for phrase in [
        "historical pre-publish review evidence",
        "Published: `false`",
        "post-release evidence",
        "current publication record",
        "Raidriar7170/hermes-skilleval@v0.3.0",
    ]:
        assert phrase in current

    assert "not a v0.2.0 release" not in current

    for risky_claim in [
        "published to the GitHub Marketplace",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark status",
        "production-ready",
        "approves the release",
        "automatic merge approval enabled",
    ]:
        assert risky_claim not in combined


def test_v0_2_0_final_approval_surfaces_are_linked_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    handoff = RELEASE_HANDOFF.read_text(encoding="utf-8")
    release_notes = V0_2_0_RELEASE_NOTES.read_text(encoding="utf-8")
    final_md = (V0_2_0_FINAL_APPROVAL_PACK / "final-approval.md").read_text(
        encoding="utf-8"
    )
    brief = V0_2_0_FINAL_APPROVAL_HUMAN_BRIEF.read_text(encoding="utf-8")
    current = "\n".join([readme, usage, evidence_map, handoff, release_notes])
    historical = "\n".join([final_md, brief])
    combined = "\n".join([current, historical])

    for path in [
        "docs/release-notes/v0.2.0.md",
        "docs/demo/v0.2.0-final-approval/final-approval.md",
        "docs/demo/v0.2.0-final-approval/final-approval.json",
        "docs/demo/v0.2.0-final-approval/input-manifest.json",
        "docs/human-briefs/2026-06-04-v0-2-0-release-notes-and-final-approval.html",
    ]:
        assert path in combined

    for phrase in [
        "v0.2.0 release notes",
        "v0.2.0 final approval",
        "Overall decision: `NEEDS_REVIEW`",
        "Published: `false`",
        "GO Conditions",
        "NO-GO Until",
        "Requires Human Confirmation",
        "pre-publish human GO/NO-GO gate",
        "not automatic publication",
        "explicit human confirmation",
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
        assert phrase in historical

    for phrase in [
        "v0.2.0 release notes",
        "published GitHub Release package",
        "reusable GitHub Action support",
        "post-release evidence",
        "current publication record",
        "Raidriar7170/hermes-skilleval@v0.3.0",
    ]:
        assert phrase in current

    assert "not a v0.2.0 release" not in current

    for risky_claim in [
        "published to the GitHub Marketplace",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark status",
        "production-ready",
        "approves the release",
        "automatic merge approval enabled",
        "gh release create",
    ]:
        assert risky_claim not in combined


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


def test_external_repo_action_smoke_pack_docs_are_local_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    pack_readme = (EXTERNAL_REPO_ACTION_SMOKE_PACK / "README.md").read_text(
        encoding="utf-8"
    )
    brief = EXTERNAL_REPO_ACTION_SMOKE_HUMAN_BRIEF.read_text(encoding="utf-8")
    combined = "\n".join([readme, usage, evidence_map, pack_readme, brief])

    assert "External Repo Action Smoke Pack" in combined
    assert "docs/demo/external-repo-action-smoke-pack" in combined
    assert "local external-consumer smoke" in combined
    assert "skilleval-output" in combined
    assert "ALLOW_MERGE" in combined
    for phrase in [
        "not a Marketplace Action release",
        "not hosted GitHub Actions proof",
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
        assert phrase in combined

    risky_claims = [
        "published to the GitHub Marketplace",
        "proves hosted GitHub Actions",
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


def test_hosted_consumer_action_smoke_docs_are_hosted_and_bounded():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    pack_readme = (HOSTED_CONSUMER_ACTION_SMOKE_PACK / "README.md").read_text(
        encoding="utf-8"
    )
    brief = HOSTED_CONSUMER_ACTION_SMOKE_HUMAN_BRIEF.read_text(encoding="utf-8")
    metadata = (HOSTED_CONSUMER_ACTION_SMOKE_PACK / "run-metadata.json").read_text(
        encoding="utf-8"
    )
    combined = "\n".join([readme, usage, evidence_map, pack_readme, brief, metadata])

    assert "Hosted Consumer Action Smoke" in combined
    assert "docs/demo/hosted-consumer-action-smoke" in combined
    assert "GitHub-hosted consumer smoke run" in combined
    assert "Raidriar7170/hermes-skilleval-action-consumer-smoke" in combined
    assert "ALLOW_MERGE" in combined
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
        assert phrase in combined

    risky_claims = [
        "published to the GitHub Marketplace",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark status",
        "production-ready",
        "approves the release",
        "released as a Marketplace Action",
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
    surfaces = _current_count_surface_paths()
    combined = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)

    assert f"{CURRENT_FULL_SUITE_COUNT} passed" in combined
    assert f"{CURRENT_FULL_SUITE_COUNT} pytest cases" in README.read_text(
        encoding="utf-8"
    )
    for stale_count in [
        "392 pytest cases",
        "392 passed",
        "392 passing tests",
        "| Test cases | 392 |",
        "399 pytest cases",
        "399 passed",
        "399 passing tests",
        "| Test cases | 399 |",
        "406 pytest cases",
        "406 passed",
        "406 passing tests",
        "| Test cases | 406 |",
        "393 pytest cases",
        "393 passed",
        "393 passing tests",
        "| Test cases | 393 |",
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


def test_current_count_contexts_do_not_carry_unlabelled_stale_numbers():
    count_context_keywords = [
        "current public",
        "current reviewer surfaces",
        "latest public",
        "latest revalidation",
        "当前公开",
        "公开测试计数",
        "公开验证计数",
        "最新公开",
        "测试计数",
    ]
    boundary_phrases = _historical_count_boundary_phrases()
    offenders = []

    for path in _current_count_surface_paths():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            if not any(keyword in lowered for keyword in count_context_keywords):
                continue

            stale_numbers = sorted(
                {
                    match.group(0)
                    for match in re.finditer(r"\b\d{3}\b", line)
                    if match.group(0) != CURRENT_FULL_SUITE_COUNT
                }
            )
            if not stale_numbers:
                continue
            if any(phrase in lowered for phrase in boundary_phrases):
                continue

            rel_path = path.relative_to(ROOT)
            offenders.append(
                f"{rel_path}:{line_number}: {', '.join(stale_numbers)} :: {line.strip()}"
            )

    assert not offenders, (
        "Current count contexts must use the latest count or label stale numbers "
        "as historical/original/baseline evidence:\n" + "\n".join(offenders)
    )


def test_historical_human_briefs_label_non_current_pytest_counts():
    boundary_phrases = _historical_count_boundary_phrases()
    offenders = []

    for path in sorted((ROOT / "docs" / "human-briefs").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        non_current_counts = sorted(set(_non_current_pytest_counts(text)))
        if not non_current_counts:
            continue

        lowered = text.lower()
        if any(phrase in lowered for phrase in boundary_phrases):
            continue

        rel_path = path.relative_to(ROOT)
        offenders.append(f"{rel_path}: {', '.join(non_current_counts)}")

    assert not offenders, (
        "Historical Human Briefs with non-current pytest counts must label those "
        "counts as historical/original/baseline evidence:\n" + "\n".join(offenders)
    )


def test_release_notes_are_reviewer_ready_and_conservative():
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    assert "# v0.1.0 - CI-backed Skill Routing Evaluation Harness" in notes
    assert "KEEP_BASELINE" in notes
    assert "baseline-minilm" in notes
    assert "SOTA" not in notes


def _markdown_links(markdown: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)


def _current_count_surface_paths() -> list[Path]:
    evidence_map = EVIDENCE_MAP.read_text(encoding="utf-8")
    evidence_map_briefs = [
        EVIDENCE_MAP.parent / link
        for link in _markdown_links(evidence_map)
        if link.startswith("human-briefs/")
    ]
    return [
        README,
        USAGE,
        *CURRENT_HUMAN_BRIEFS,
        *evidence_map_briefs,
        *PUBLIC_EVIDENCE_CHANGE_ARTIFACTS,
        *_active_openspec_change_artifacts(),
    ]


def _active_openspec_change_artifacts() -> list[Path]:
    change_root = ROOT / "openspec" / "changes"
    artifacts = [
        *change_root.glob("*/*.md"),
        *change_root.glob("*/specs/**/*.md"),
    ]
    return sorted(
        path
        for path in artifacts
        if path.is_file() and "archive" not in path.relative_to(change_root).parts
    )


def _historical_count_boundary_phrases() -> list[str]:
    return [
        "historical count",
        "historical phase",
        "original run count",
        "original validation result",
        "implementation baseline",
        "baseline before implementation",
        "phase-time",
        "at the time",
        "本阶段",
        "当时",
    ]


def _non_current_pytest_counts(html: str) -> list[str]:
    pattern = re.compile(
        rf"\b(?!{CURRENT_FULL_SUITE_COUNT}\b)\d{{3}}\s+"
        r"(?:passed|passing tests|pytest cases|unit and smoke tests)\b"
    )
    return [match.group(0) for match in pattern.finditer(html)]
