from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
POST_RELEASE = ROOT / "docs" / "demo" / "v0.2.0-post-release"
POST_RELEASE_JSON = POST_RELEASE / "post-release.json"
POST_RELEASE_MD = POST_RELEASE / "post-release.md"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _markdown_links(markdown: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)


def test_v0_2_0_post_release_files_exist() -> None:
    assert POST_RELEASE_JSON.is_file()
    assert POST_RELEASE_MD.is_file()


def test_readme_surfaces_v0_2_0_post_release_evidence() -> None:
    readme = README.read_text(encoding="utf-8")

    for phrase in [
        "docs/demo/v0.2.0-post-release/post-release.md",
        "post-release facts after human GO",
        "Published `true`",
        "GitHub Release created `true`",
        "Marketplace published `false`",
        "Published: `true`; tag and GitHub Release created",
    ]:
        assert phrase in readme


def test_v0_2_0_post_release_json_records_github_release_facts() -> None:
    evidence = _json(POST_RELEASE_JSON)

    assert evidence["artifact_type"] == "v0.2.0-post-release-evidence"
    assert evidence["schema_version"] == "v0.2.0-post-release.v1"
    assert evidence["release_version"] == "v0.2.0"
    assert evidence["published"] is True
    assert evidence["tag_created"] is True
    assert evidence["github_release_created"] is True
    assert evidence["marketplace_published"] is False
    assert evidence["tag_name"] == "v0.2.0"
    assert evidence["target_commitish"] == "main"
    assert evidence["target_commit_sha"] == "13af31ee4fd2e9eed4a40f643284120bc5afab9e"
    assert evidence["release_url"] == (
        "https://github.com/Raidriar7170/hermes-skilleval/releases/tag/v0.2.0"
    )
    assert evidence["published_at"] == "2026-06-04T14:06:56Z"
    assert evidence["is_draft"] is False
    assert evidence["is_prerelease"] is False

    notes = evidence["release_notes_source"]
    assert isinstance(notes, dict)
    assert notes["path"] == "docs/release-notes/v0.2.0.md"
    assert notes["sha256"] == "bb16523a16b22b79a925d5d55c7f55935cf2b2229023c30d557e3732b3ad128e"
    assert notes["size_bytes"] == 2934


def test_v0_2_0_post_release_markdown_links_and_boundaries_are_bounded() -> None:
    markdown = POST_RELEASE_MD.read_text(encoding="utf-8")
    combined = markdown + "\n" + POST_RELEASE_JSON.read_text(encoding="utf-8")

    for phrase in [
        "Published: `true`",
        "GitHub Release created: `true`",
        "Marketplace published: `false`",
        "not Marketplace publication",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not benchmark status",
        "not production readiness",
        "not automatic merge approval",
        "`finetuned-embedding` is not\napproved as default",
    ]:
        assert phrase in combined

    for forbidden in [
        "published to the GitHub Marketplace",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS product",
        "runtime MCP router for agents",
        "SOTA benchmark status",
        "production-ready",
        "automatic merge approval enabled",
        "finetuned-embedding is approved as default",
    ]:
        assert forbidden not in combined

    for link in _markdown_links(markdown):
        if link.startswith(("http://", "https://", "#")):
            continue
        assert (POST_RELEASE / link.split("#", 1)[0]).resolve().exists(), link
