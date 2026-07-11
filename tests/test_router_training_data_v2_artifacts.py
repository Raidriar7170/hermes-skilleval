from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from hermes_skilleval.router_training_data_v2 import (
    BLOCKER_CODES,
    qualify_router_training_data_v2,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/demo/router-training-data-v2-qualification-pack"
TASKS = ROOT / "benchmarks/migration-tasks"
SKILLS = ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"
HUMAN_BRIEF = (
    ROOT
    / "docs/human-briefs/2026-07-11-build-router-training-data-v2-qualification-pack.html"
)
LEGACY_ACTIVE_CHANGE_PATH = (
    "openspec/changes/build-router-training-data-v2-qualification-pack"
)
EXPECTED_PACK_SHA256 = {
    "candidate-pairs.jsonl": (
        "fbfc626d0b5fa98f3eb505042a3bf002d697ec0ca9ea1328edec6fd637cb82c3"
    ),
    "qualification-report.json": (
        "7a5b61ec9245cb6ffbdb514899c637005652382cd6db4a19b7fafcff5c6d62d7"
    ),
    "manifest.json": (
        "b1f8fb98b9eac2f21bed137506eec63d678053d03205ce0248b843fc3e5a80ab"
    ),
}

EXPECTED_COUNTS = {
    "accepted_train_pair_count": 0,
    "cross_category_easy_negative_count": 144,
    "matrix_candidate_count": 192,
    "positive_count": 16,
    "reject_example_count": 0,
    "reserved_matrix_row_count": 64,
    "reserved_positive_or_same_category_count": 16,
    "same_category_negative_candidate_count": 32,
    "source_pair_count": 28,
    "target_skill_count": 16,
    "task_count": 12,
    "train_policy_candidate_count": 32,
    "train_positive_skill_coverage_count": 11,
}
ROW_FIELDS = {
    "accepted_for_training",
    "candidate_type",
    "disposition",
    "label",
    "pair_id",
    "prompt_text_sha256",
    "query_text",
    "schema_version",
    "skill_id",
    "skill_text",
    "source",
    "source_split",
    "task_id",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path = PACK / "candidate-pairs.jsonl") -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class _HTMLLinksAndText(HTMLParser):
    _NON_RENDERED_TAGS = {"noscript", "script", "style", "template"}
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.text: list[str] = []
        self._element_stack: list[tuple[str, bool]] = []
        self._in_body = False
        self._suppressed_depth = 0

    def _record_hrefs(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(
                value for name, value in attrs if name == "href" and value is not None
            )

    def _is_suppressed(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        attributes = {name.lower(): value for name, value in attrs}
        aria_hidden = (attributes.get("aria-hidden") or "").strip().lower()
        inline_style = attributes.get("style") or ""
        return (
            tag in self._NON_RENDERED_TAGS
            or "hidden" in attributes
            or aria_hidden == "true"
            or re.search(r"\bdisplay\s*:\s*none\b", inline_style, re.IGNORECASE)
            is not None
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_hrefs(tag, attrs)
        if tag == "body":
            self._in_body = True
        if tag not in self._VOID_TAGS:
            suppressed = self._is_suppressed(tag, attrs)
            self._element_stack.append((tag, suppressed))
            if suppressed:
                self._suppressed_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_hrefs(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == tag:
                closed_elements = self._element_stack[index:]
                del self._element_stack[index:]
                self._suppressed_depth -= sum(
                    suppressed for _, suppressed in closed_elements
                )
                break
        if tag == "body":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._in_body and self._suppressed_depth == 0:
            self.text.append(data)


def _local_link_target(source: Path, href: str) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None

    target = (source.parent / unquote(parsed.path)).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError as error:
        raise AssertionError(f"local link escapes repository: {href}") from error
    return target


def _markdown_hrefs(markdown: str) -> list[str]:
    hrefs = []
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", markdown):
        destination = match.group(1).strip()
        if destination.startswith("<"):
            hrefs.append(destination[1 : destination.index(">")])
        else:
            hrefs.append(destination.split(maxsplit=1)[0])
    return hrefs


def _visible_html_text(html: str) -> str:
    parser = _HTMLLinksAndText()
    parser.feed(html)
    return " ".join(" ".join(parser.text).split())


def test_html_truth_parser_excludes_non_rendered_text():
    html = """
    <html>
      <head><title>HEAD_ONLY_TOKEN</title></head>
      <body>
        <style>STYLE_ONLY_TOKEN</style>
        <script>SCRIPT_ONLY_TOKEN</script>
        <template>TEMPLATE_ONLY_TOKEN</template>
        <noscript>NOSCRIPT_ONLY_TOKEN</noscript>
        <p hidden>HIDDEN_ONLY_TOKEN</p>
        <p aria-hidden="true">ARIA_HIDDEN_ONLY_TOKEN</p>
        <p style="display: none">DISPLAY_NONE_ONLY_TOKEN</p>
        <p>BODY_VISIBLE_TOKEN</p>
      </body>
    </html>
    """

    visible_text = _visible_html_text(html)

    assert "BODY_VISIBLE_TOKEN" in visible_text
    for excluded_token in (
        "HEAD_ONLY_TOKEN",
        "STYLE_ONLY_TOKEN",
        "SCRIPT_ONLY_TOKEN",
        "TEMPLATE_ONLY_TOKEN",
        "NOSCRIPT_ONLY_TOKEN",
        "HIDDEN_ONLY_TOKEN",
        "ARIA_HIDDEN_ONLY_TOKEN",
        "DISPLAY_NONE_ONLY_TOKEN",
    ):
        assert excluded_token not in visible_text


def test_committed_pack_parses_and_preserves_exact_blocked_contract():
    rows = _rows()
    report = json.loads(
        (PACK / "qualification-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))

    assert len(rows) == 192
    assert all(set(row) == ROW_FIELDS for row in rows)
    assert {row["schema_version"] for row in rows} == {
        "router-training-data-v2-candidate-v1"
    }
    assert [row["pair_id"] for row in rows] == sorted(row["pair_id"] for row in rows)
    assert len({row["pair_id"] for row in rows}) == 192
    assert Counter(row["candidate_type"] for row in rows) == {
        "positive": 16,
        "same_category_negative_candidate": 32,
        "cross_category_easy_negative": 144,
    }
    assert sum(row["disposition"] == "RESERVED_SOURCE_TEST" for row in rows) == 64
    assert all(row["accepted_for_training"] is False for row in rows)
    assert all(
        row["disposition"] == "RESERVED_SOURCE_TEST"
        for row in rows
        if row["source_split"] == "test"
    )

    assert report["schema_version"] == (
        "router-training-data-v2-qualification-report-v1"
    )
    assert report["policy_id"] == "router-training-data-v2-qualification-v1"
    assert report["qualification_status"] == "REVIEW_REQUIRED"
    assert report["router_decision"] == "KEEP_BASELINE"
    assert report["can_start_training"] is False
    assert report["blocker_codes"] == BLOCKER_CODES
    assert report["counts"] == EXPECTED_COUNTS
    assert manifest["schema_version"] == "router-training-data-v2-manifest-v1"
    assert manifest["policy_id"] == "router-training-data-v2-qualification-v1"
    assert manifest["counts"] == EXPECTED_COUNTS
    assert not (PACK / "training-pairs.jsonl").exists()


def test_manifest_binds_every_repository_relative_input_and_output_hash():
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    input_records = manifest["inputs"]["files"]

    assert len(input_records) == 25
    assert [record["path"] for record in input_records] == sorted(
        record["path"] for record in input_records
    )
    assert all(not Path(record["path"]).is_absolute() for record in input_records)
    for record in input_records:
        assert _sha256(ROOT / record["path"]) == record["sha256"]

    assert manifest["inputs"]["task_root"] == "benchmarks/migration-tasks"
    assert manifest["inputs"]["skills_index"] == {
        "path": "docs/demo/phase9-real-skill-library-migration/skills.json",
        "sha256": _sha256(SKILLS),
    }
    assert [record["path"] for record in manifest["outputs"]] == [
        "candidate-pairs.jsonl",
        "qualification-report.json",
    ]
    for record in manifest["outputs"]:
        output = PACK / record["path"]
        assert len(output.read_bytes()) == record["bytes"]
        assert _sha256(output) == record["sha256"]

    machine_text = "\n".join(
        (PACK / name).read_text(encoding="utf-8")
        for name in (
            "candidate-pairs.jsonl",
            "qualification-report.json",
            "manifest.json",
        )
    )
    assert str(ROOT) not in machine_text
    assert "blind-migration-tasks" not in machine_text


def test_committed_pack_regenerates_byte_identically_into_fresh_target(tmp_path: Path):
    regenerated = tmp_path / "fresh-pack"
    qualify_router_training_data_v2(
        tasks_path=TASKS,
        skills_index_path=SKILLS,
        output_dir=regenerated,
        repository_root=ROOT,
    )

    for name in (
        "candidate-pairs.jsonl",
        "qualification-report.json",
        "manifest.json",
    ):
        assert (regenerated / name).read_bytes() == (PACK / name).read_bytes()
    assert not (regenerated / "training-pairs.jsonl").exists()


def test_committed_machine_artifact_hashes_are_frozen():
    assert {
        name: _sha256(PACK / name) for name in EXPECTED_PACK_SHA256
    } == EXPECTED_PACK_SHA256


def test_qualification_readme_local_links_resolve_within_repository():
    readme_path = PACK / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    hrefs = _markdown_hrefs(readme)

    assert hrefs
    for href in hrefs:
        target = _local_link_target(readme_path, href)
        if target is not None:
            assert target.exists(), f"missing README link target: {href} -> {target}"
    assert LEGACY_ACTIVE_CHANGE_PATH not in readme


def test_human_brief_local_links_resolve_within_repository():
    brief = HUMAN_BRIEF.read_text(encoding="utf-8")
    parser = _HTMLLinksAndText()
    parser.feed(brief)

    assert parser.hrefs
    for href in parser.hrefs:
        target = _local_link_target(HUMAN_BRIEF, href)
        if target is not None:
            assert target.exists(), (
                f"missing Human Brief link target: {href} -> {target}"
            )
    assert LEGACY_ACTIVE_CHANGE_PATH not in brief


def test_human_brief_has_coherent_post_archive_lifecycle_truth():
    visible_text = _visible_html_text(HUMAN_BRIEF.read_text(encoding="utf-8"))

    for required_status in (
        "BRANCH_PUSHED",
        "OPENSPEC_ARCHIVED",
        "NO_PR",
        "NO_MAIN_MERGE",
        "NO_TRAINING",
        "NO_A100_GPU_JOB",
        "NO_CHECKPOINT",
        "NO_BLIND_RERUN",
        "NO_RELEASE",
        "NO_TAG",
        "NO_DEPLOY",
        "KEEP_BASELINE",
    ):
        assert required_status in visible_text

    for stale_pattern in (
        r"仍未\s*push",
        r"没有[^。；\n]{0,40}\bpush\b",
        r"(?:仍未|尚未|未)\s*(?:完成\s*)?(?:OpenSpec\s*)?archive",
        r"没有[^。；\n]{0,40}OpenSpec\s+archive",
        r"本地\s+publication\s+gate",
    ):
        assert re.search(stale_pattern, visible_text, flags=re.IGNORECASE) is None


def test_lifecycle_truth_is_scoped_to_current_archive_branch_and_change():
    branch = "ops/archive-build-router-training-data-v2-qualification-pack"
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())
    visible_brief = _visible_html_text(HUMAN_BRIEF.read_text(encoding="utf-8"))

    assert f"archive branch `{branch}` has been pushed" in normalized_readme
    assert "No PR has been opened for this branch" in normalized_readme
    assert "this branch has not been merged to `main`" in normalized_readme
    assert (
        "This archive/truth-surface change created no new tag, release, or deploy"
        in normalized_readme
    )
    assert branch in visible_brief
    assert "该 branch 尚未创建 GitHub PR" in visible_brief
    assert "该 branch 尚未 merge main" in visible_brief
    assert (
        "本次 archive/truth-surface change 未创建新的 tag、release 或 deploy"
        in visible_brief
    )

    for unscoped_claim in (
        "No GitHub PR exists",
        "No tag, release, or deploy exists",
    ):
        assert unscoped_claim not in readme


def test_readme_and_human_brief_lock_complete_canonical_qualification_truth():
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    visible_brief = _visible_html_text(HUMAN_BRIEF.read_text(encoding="utf-8"))

    for readme_truth in (
        "closed 12-task by 16-skill diagnostic matrix",
        "Matrix candidates: 192",
        "Positives: 16",
        "Same-category negative candidates requiring review: 32",
        "Cross-category easy negatives: 144",
        "Reserved source-test rows: 64",
        "Train-policy candidates: 32",
        "Accepted training pairs: 0",
        "Train-positive target-skill coverage: 11/16",
        "Reviewed reject/no-skill examples: 0",
        "`REVIEW_REQUIRED` / `KEEP_BASELINE`",
        "`can_start_training=false`",
    ):
        assert readme_truth in readme

    for brief_truth in (
        "候选矩阵 192 12 个非盲 migration tasks × 16 个 canonical skills。",
        "Positive 16 来自 gold skill 标注。",
        "同类别 negative candidates 32 只是待审候选，尚不能称为已接受 hard negatives。",
        "跨类别 easy negatives 144 明确排除在合格 pair 门槛之外。",
        "Reserved source-test rows 64 已用 held-out source，不回流到训练候选。",
        "Train-policy candidates 32 11 个 dev positives + 21 个 dev 同类别待审 negatives。",
        "Accepted train pairs 0 没有人工 acceptance 证据。",
        "Train positive skill coverage 11/16 仍未覆盖全部目标 skills。",
        "Reviewed reject examples 0 没有真实、人工审核的 no-skill query。",
        "Qualification REVIEW_REQUIRED",
        "Router decision KEEP_BASELINE",
        "can_start_training=false",
    ):
        assert brief_truth in visible_brief


def test_human_brief_verification_and_review_process_match_latest_evidence():
    visible_brief = _visible_html_text(HUMAN_BRIEF.read_text(encoding="utf-8"))

    for evidence in (
        "Focused artifact / truth suite PASS 12 passed",
        "Full pytest PASS 747 passed",
        "Scoped Ruff PASS tests/test_router_training_data_v2_artifacts.py",
        "Strict OpenSpec PASS 28 passed, 0 failed",
        "Release reproducibility PASS",
        "Pass with fixes",
        "3 项 Must Fix 已在本地处理",
        "Re-plan Needed=No",
        "final re-review 在本文更新后执行",
        "最终结果以本地任务报告为准",
    ):
        assert evidence in visible_brief

    for stale_evidence_pattern in (
        r"(?<!\d)8 passed",
        r"84 passed",
        r"739 passed",
        r"743 passed",
        r"Must Fix=None",
        r"Final Verdict=Pass",
    ):
        assert re.search(stale_evidence_pattern, visible_brief) is None


def test_readme_regeneration_and_truth_boundaries_match_artifacts():
    readme = (PACK / "README.md").read_text(encoding="utf-8")

    for truth in (
        "`REVIEW_REQUIRED`",
        "`KEEP_BASELINE`",
        "`can_start_training=false`",
        "Accepted training pairs: 0",
        "Train-positive target-skill coverage: 11/16",
        *[f"`{code}`" for code in BLOCKER_CODES],
    ):
        assert truth in readme
    for boundary in (
        "did not train",
        "blind prompt",
        "A100/GPU",
        "checkpoint",
        "benchmark improvement",
        "merge",
        "release",
        "archive",
    ):
        assert boundary in readme

    assert 'TMP_ROOT="$(mktemp -d' in readme
    assert 'OUT="$TMP_ROOT/pack"' in readme
    assert "qualify-router-training-data-v2" in readme
    assert 'cmp "docs/demo/router-training-data-v2-qualification-pack/$name"' in readme
    assert "candidate-pairs.jsonl qualification-report.json manifest.json" in readme
    assert '--output-dir "$OUT"' in readme
    assert (
        "--output-dir docs/demo/router-training-data-v2-qualification-pack"
        not in readme
    )
    assert "training-pairs.jsonl" in readme

    assert _sha256(PACK / "candidate-pairs.jsonl") in readme
    assert _sha256(PACK / "qualification-report.json") in readme
    assert _sha256(PACK / "manifest.json") in readme
