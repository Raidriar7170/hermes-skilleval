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
from hermes_skilleval.task_loader import load_tasks


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/demo/router-training-data-v2-qualification-pack"
TASKS = ROOT / "benchmarks/migration-tasks"
SKILLS = ROOT / "docs/demo/phase9-real-skill-library-migration/skills.json"
HISTORICAL_V1_BRIEF = (
    ROOT
    / "docs/human-briefs/2026-07-11-build-router-training-data-v2-qualification-pack.html"
)
HUMAN_BRIEF = HISTORICAL_V1_BRIEF
PROPOSAL_BRIEF = (
    ROOT
    / "docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only.html"
)
APPLY_BRIEF = (
    ROOT
    / "docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only-apply.html"
)
CURRENT_V3_BRIEF = (
    ROOT / "docs/human-briefs/2026-07-12-harden-router-v2-pretraining-contracts.html"
)
PROPOSAL_BRIEF_SHA256 = (
    "8aad6d45b991e0cc0c4581d233207b042ee35bb4527ed84f9193644661803778"
)
ACTIVE_CHANGE_PATH = "openspec/changes/harden-router-v2-pretraining-contracts"
HISTORICAL_V2_CHANGE_PATH = (
    "openspec/changes/make-router-training-data-v2-primary-prompt-only"
)
LEGACY_ACTIVE_CHANGE_PATH = (
    "openspec/changes/build-router-training-data-v2-qualification-pack"
)
V1_BASELINE_PACK_SHA256 = {
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
CURRENT_V2_PACK_SHA256 = {
    "candidate-pairs.jsonl": (
        "e70006f3124f496a7e0005a081db06527391167bd380574b08c7991bcf2c6475"
    ),
    "qualification-report.json": (
        "d36afe875f2ada4e38ac3b707ced5bbb27c89262aad403793b7ee68058dd2395"
    ),
    "manifest.json": (
        "883e7d8a35622b89a243a373304bd5e9e570275649bd22d01e9a8799c674daaf"
    ),
}
CURRENT_V3_PACK_SHA256 = {
    "candidate-pairs.jsonl": (
        "fff59d8ddc199a4579dcf831fa806fa0b2ef761465a7bde7acd77dc967f41b45"
    ),
    "qualification-report.json": (
        "edb1b1111e24c8866bda6edca776129d4952ef38d23c017c753586dd6ef77e3b"
    ),
    "manifest.json": (
        "da97accd98e3af5113a962423ff79a8235f4388b4e2fd2d0ff7aeb3931f6c449"
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
EXPECTED_QUERY_CONTRACT = {
    "alternate_query_fields": [],
    "forbidden_primary_query_inputs": [
        "task_id",
        "category",
        "difficulty",
        "robustness_tags",
        "split",
        "family",
    ],
    "formatter": "router_query_text(prompt: str)",
    "hash_algorithm": "sha256",
    "hash_field": "prompt_text_sha256",
    "normalization": "loader_normalized",
    "primary_query_field": "query_text",
    "query_text_policy": "prompt_only",
    "source_field": "task.prompt",
}
ROW_FIELDS = {
    "accepted_for_training",
    "artifact_version",
    "candidate_type",
    "disposition",
    "label",
    "pair_id",
    "policy_id",
    "prompt_text_sha256",
    "query_text",
    "query_text_policy",
    "schema_version",
    "skill_id",
    "skill_text",
    "source",
    "source_split",
    "task_id",
}
EXPECTED_DIVERSITY_DIAGNOSTICS = {
    "family_independent_count": None,
    "family_metadata_status": "UNAVAILABLE",
    "per_skill_unique_train_positive_prompt_count": {
        "accessibility-tree-inspection": 0,
        "apply-patch-discipline": 1,
        "browser-smoke-testing": 1,
        "evidence-backed-final": 1,
        "form-interaction-flow": 1,
        "mcp-tool-routing": 0,
        "plan-mode": 1,
        "slash-command-workflow": 1,
        "subagent-worker-protocol": 1,
        "systematic-debugging": 1,
        "task-tool-delegation": 0,
        "test-driven-development": 1,
        "using-git-worktrees": 0,
        "verification-before-completion": 1,
        "visual-regression-review": 1,
        "workspace-git-hygiene": 0,
    },
    "train_policy_unique_prompt_count": 8,
    "unique_prompt_count": 12,
    "unique_task_family_count": None,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path = PACK / "candidate-pairs.jsonl") -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _independent_diversity_diagnostics(
    rows: list[dict[str, object]],
) -> dict[str, object]:
    skill_ids = {str(row["skill_id"]) for row in rows}
    train_policy_rows = [
        row
        for row in rows
        if row["source_split"] == "dev"
        and row["candidate_type"] in {"positive", "same_category_negative_candidate"}
    ]
    return {
        "family_independent_count": None,
        "family_metadata_status": "UNAVAILABLE",
        "per_skill_unique_train_positive_prompt_count": {
            skill_id: len(
                {
                    str(row["query_text"])
                    for row in rows
                    if row["source_split"] == "dev"
                    and row["candidate_type"] == "positive"
                    and row["skill_id"] == skill_id
                }
            )
            for skill_id in sorted(skill_ids)
        },
        "train_policy_unique_prompt_count": len(
            {str(row["query_text"]) for row in train_policy_rows}
        ),
        "unique_prompt_count": len({str(row["query_text"]) for row in rows}),
        "unique_task_family_count": None,
    }


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

    assert report["qualification_status"] == "REVIEW_REQUIRED"
    assert report["router_decision"] == "KEEP_BASELINE"
    assert report["can_start_training"] is False
    assert report["artifact_version"] == 3
    assert report["blocker_codes"] == BLOCKER_CODES
    assert report["counts"] == EXPECTED_COUNTS
    assert manifest["counts"] == EXPECTED_COUNTS
    independently_recomputed = _independent_diversity_diagnostics(rows)
    assert independently_recomputed == EXPECTED_DIVERSITY_DIAGNOSTICS
    assert report["diversity_diagnostics"] == independently_recomputed
    assert manifest["diversity_diagnostics"] == independently_recomputed
    assert all("family" not in row for row in rows)
    assert not (PACK / "training-pairs.jsonl").exists()
    assert not (PACK / "training-pairs-v2.jsonl").exists()


def test_committed_candidate_queries_equal_loaded_prompts_and_hashes():
    task_by_id = {task.id: task for task in load_tasks(TASKS)}

    for row in _rows():
        query_text = row["query_text"]
        assert isinstance(query_text, str)
        expected_prompt = task_by_id[str(row["task_id"])].prompt
        assert query_text.encode("utf-8") == expected_prompt.encode("utf-8")
        assert (
            hashlib.sha256(query_text.encode("utf-8")).hexdigest()
            == row["prompt_text_sha256"]
        )


def test_committed_candidate_rows_use_exact_v3_prompt_only_contract():
    rows = _rows()

    assert all(set(row) == ROW_FIELDS for row in rows)
    assert {row["schema_version"] for row in rows} == {
        "router-training-data-v2-candidate-v3"
    }
    assert {row["artifact_version"] for row in rows} == {3}
    assert {row["policy_id"] for row in rows} == {
        "router-training-data-v2-qualification-v3"
    }
    assert {row["query_text_policy"] for row in rows} == {"prompt_only"}
    assert all(
        {key for key in row if key.endswith("query_text")} == {"query_text"}
        for row in rows
    )


def test_committed_report_and_manifest_use_exact_v3_query_contract():
    report = json.loads(
        (PACK / "qualification-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))

    assert {
        "manifest_artifact_version": manifest.get("artifact_version"),
        "manifest_policy_id": manifest.get("policy_id"),
        "manifest_query_contract": manifest.get("query_contract"),
        "manifest_schema_version": manifest.get("schema_version"),
        "report_policy_id": report.get("policy_id"),
        "report_query_contract": report.get("query_contract"),
        "report_schema_version": report.get("schema_version"),
    } == {
        "manifest_artifact_version": 3,
        "manifest_policy_id": "router-training-data-v2-qualification-v3",
        "manifest_query_contract": EXPECTED_QUERY_CONTRACT,
        "manifest_schema_version": "router-training-data-v2-manifest-v3",
        "report_policy_id": "router-training-data-v2-qualification-v3",
        "report_query_contract": EXPECTED_QUERY_CONTRACT,
        "report_schema_version": ("router-training-data-v2-qualification-report-v3"),
    }
    assert report["query_contract"] == manifest["query_contract"]


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
    assert not (regenerated / "training-pairs-v2.jsonl").exists()
    assert not (regenerated / "accepted-pairs-v3.jsonl").exists()
    assert not (regenerated / "training-input-manifest-v3.json").exists()


def test_committed_v3_machine_artifact_hashes_replace_v2_snapshot():
    actual = {name: _sha256(PACK / name) for name in CURRENT_V3_PACK_SHA256}

    assert actual == CURRENT_V3_PACK_SHA256
    assert all(
        actual[name] != v2_hash for name, v2_hash in CURRENT_V2_PACK_SHA256.items()
    )


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


def test_proposal_brief_remains_unchanged_and_proposal_only():
    assert _sha256(PROPOSAL_BRIEF) == PROPOSAL_BRIEF_SHA256
    html = PROPOSAL_BRIEF.read_text(encoding="utf-8")
    parser = _HTMLLinksAndText()
    parser.feed(html)
    visible_text = _visible_html_text(html)

    assert "PROPOSED" in visible_text
    assert "APPLY_NOT_STARTED" in visible_text
    assert "APPLY_COMPLETE_LOCAL" not in visible_text
    assert "USER_REVIEW_REQUIRED" not in visible_text
    assert parser.hrefs
    for href in parser.hrefs:
        target = _local_link_target(PROPOSAL_BRIEF, href)
        if target is not None:
            assert target.exists(), (
                f"missing proposal brief link target: {href} -> {target}"
            )


def test_readme_is_current_prompt_only_v3_truth_surface():
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())

    for truth in (
        ACTIVE_CHANGE_PATH,
        "current deterministic prompt-only v3 diagnostic qualification snapshot",
        "router_query_text(prompt: str)",
        'query_text_policy="prompt_only"',
        "query_text == loader-normalized task.prompt",
        "router-training-data-v2-candidate-v3",
        "router-training-data-v2-qualification-v3",
        "router-training-data-v2-qualification-report-v3",
        "router-training-data-v2-manifest-v3",
        "artifact_version=3",
        "Matrix candidates: 192",
        "Positives: 16",
        "Same-category negative candidates requiring review: 32",
        "Cross-category easy negatives: 144",
        "Reserved source-test rows: 64",
        "Train-policy candidates: 32",
        "Accepted training pairs: 0",
        "Train-positive target-skill coverage: 11/16",
        "Reviewed reject/no-skill examples: 0",
        "Unique prompts: 12",
        "Train-policy unique prompts: 8",
        "Unique task family count: `null`",
        "Family-independent count: `null`",
        "Family metadata status: `UNAVAILABLE`",
        "Candidate rows are diagnostic candidates, not qualified training data",
        "Only formally reviewed positives and human-reviewed hard negatives can pass",
        "ACCEPTED_POSITIVE",
        "ACCEPTED_HARD_NEGATIVE",
        "The current canonical pack is rejected by the v3 trainer gate",
        "review/navigation aid, not a second source of truth",
        *BLOCKER_CODES,
        *CURRENT_V3_PACK_SHA256.values(),
    ):
        assert truth in normalized_readme
    expected_per_skill = EXPECTED_DIVERSITY_DIAGNOSTICS[
        "per_skill_unique_train_positive_prompt_count"
    ]
    assert isinstance(expected_per_skill, dict)
    for skill_id, count in expected_per_skill.items():
        assert f"`{skill_id}`: `{count}`" in readme
    for historical_hash in (
        *V1_BASELINE_PACK_SHA256.values(),
        *CURRENT_V2_PACK_SHA256.values(),
    ):
        assert historical_hash not in readme
    for stale_or_false_claim in (
        "current deterministic prompt-only v2",
        "router-training-data-v2-candidate-v2",
        "This is accepted training data",
        "remote CI passed",
    ):
        assert stale_or_false_claim not in normalized_readme


def test_historical_v1_brief_is_visibly_historical_and_links_current_v2():
    html = HISTORICAL_V1_BRIEF.read_text(encoding="utf-8")
    parser = _HTMLLinksAndText()
    parser.feed(html)
    visible_text = _visible_html_text(html)

    for historical_truth in (
        "HISTORICAL_V1_SNAPSHOT",
        "v1 contract",
        "v1 hashes",
        "v1 validation counts",
        "current v2 apply brief",
        *V1_BASELINE_PACK_SHA256.values(),
    ):
        assert historical_truth in visible_text
    assert any(href.endswith(APPLY_BRIEF.name) for href in parser.hrefs)
    for artifact_name in CURRENT_V2_PACK_SHA256:
        assert any(href.endswith(artifact_name) for href in parser.hrefs)


def test_apply_brief_is_historical_v2_snapshot_with_repaired_lifecycle_and_links():
    assert APPLY_BRIEF.exists()
    html = APPLY_BRIEF.read_text(encoding="utf-8")
    parser = _HTMLLinksAndText()
    parser.feed(html)
    visible_text = _visible_html_text(html)

    for truth in (
        "HISTORICAL_V2_SNAPSHOT",
        "historical v2 evidence",
        "APPLY_COMPLETE_LOCAL",
        "USER_REVIEW_REQUIRED",
        "prompt_only",
        "query_text == loader-normalized task.prompt",
        "router-training-data-v2-candidate-v2",
        "router-training-data-v2-qualification-v2",
        "router-training-data-v2-qualification-report-v2",
        "router-training-data-v2-manifest-v2",
        "artifact_version=2",
        "Matrix candidates 192",
        "Positives 16",
        "Same-category negative candidates 32",
        "Cross-category easy negatives 144",
        "Reserved source-test rows 64",
        "Train-policy candidates 32",
        "Accepted training pairs 0",
        "Train-positive target-skill coverage 11/16",
        "Reviewed reject/no-skill examples 0",
        "REVIEW_REQUIRED",
        "KEEP_BASELINE",
        "can_start_training=false",
        "NO_TRAINING",
        "NO_A100_GPU_JOB",
        "NO_CHECKPOINT",
        "NO_BLIND_RERUN",
        "NO_PERFORMANCE_CLAIM",
        "NO_PUSH",
        "NO_PR",
        "NO_MERGE",
        "NO_ARCHIVE",
        "NO_RELEASE",
        "不是第二事实源",
        "active/unarchived",
        "f996690700a79ab4c065ed8523340d2fd387f6b9",
        "committed locally",
        "unpushed",
        "unmerged",
        "unarchived",
        "remote CI unavailable",
        "current v3 brief",
        "current canonical v3 artifacts",
        "validation-only reproducibility replay",
        "replayed the frozen release selector",
        "committed/frozen Phase 16 aggregate artifacts",
        "fresh temporary Phase 17/18 outputs",
        "did not read blind prompts or rerun blind evaluation",
        "did not use new data or tuning to make a new router choice",
        "did not promote or adopt a candidate router and did not change the router decision",
        "reproduced result remained KEEP_BASELINE",
        "Focused builder / artifact / CLI 64 passed",
        "Blind / protected preflight 16 passed, 28 deselected",
        "Full pytest 762 passed",
        "Scoped Ruff PASS",
        "Strict OpenSpec 29 passed, 0 failed",
        "Release reproducibility PASS / KEEP_BASELINE",
        "782f7d3e756e3bf19dc33a930095b8a83f76ccd847644842444ba57e8fc1a390",
        *BLOCKER_CODES,
        *CURRENT_V2_PACK_SHA256.values(),
    ):
        assert truth in visible_text
    assert any(href.endswith(CURRENT_V3_BRIEF.name) for href in parser.hrefs)
    for artifact_name in CURRENT_V3_PACK_SHA256:
        assert any(href.endswith(artifact_name) for href in parser.hrefs)
    assert parser.hrefs
    for href in parser.hrefs:
        target = _local_link_target(APPLY_BRIEF, href)
        if target is not None:
            assert target.exists(), (
                f"missing apply brief link target: {href} -> {target}"
            )
    for stale_or_false_claim in (
        "HEAD e822d9c489ca39180b556000dc3e361552d6c75e is the proposal commit",
        "current apply diff is uncommitted",
        "NO_COMMIT applies to the current apply diff",
        "Current v3 artifact hashes",
    ):
        assert stale_or_false_claim not in visible_text


def test_current_v3_brief_has_truth_boundaries_authoritative_links_and_next_step():
    assert CURRENT_V3_BRIEF.exists()
    html = CURRENT_V3_BRIEF.read_text(encoding="utf-8")
    parser = _HTMLLinksAndText()
    parser.feed(html)
    visible_text = _visible_html_text(html)

    for truth in (
        "Router Training Data V2 v3",
        "router_query_text(prompt: str)",
        "router-training-data-v2-candidate-v3",
        "router-training-data-v2-qualification-v3",
        "router-training-data-v2-qualification-report-v3",
        "router-training-data-v2-manifest-v3",
        "router-training-data-v2-training-input-manifest-v3",
        "router-training-data-v2-training-admission-v3",
        "192 diagnostic rows",
        "16 positives",
        "32 unreviewed same-category negatives",
        "144 easy negatives",
        "64 reserved rows",
        "32 train-policy candidates",
        "0 accepted pairs",
        "11/16 skill coverage",
        "0 reject examples",
        "unique_prompt_count=12",
        "train_policy_unique_prompt_count=8",
        "unique_task_family_count=null",
        "family_independent_count=null",
        "family_metadata_status=UNAVAILABLE",
        "REVIEW_REQUIRED",
        "KEEP_BASELINE",
        "can_start_training=false",
        "LOCAL_WORKING_DIFF",
        "f996690700a79ab4c065ed8523340d2fd387f6b9",
        "UNCOMMITTED",
        "UNPUSHED",
        "NO_PR",
        "NO_MERGE",
        "ACTIVE_UNARCHIVED",
        "REMOTE_CI_UNAVAILABLE",
        "NO_TRAINING",
        "NO_A100_GPU_JOB",
        "NO_MODEL",
        "NO_CHECKPOINT",
        "NO_BLIND_V2",
        "NO_PERFORMANCE_CLAIM",
        "NO_TAG",
        "NO_RELEASE",
        "NO_DEPLOY",
        "PHASE14_18_AND_BLIND_UNCHANGED",
        "source_hash / acceptance_hash",
        "只证明内容与接受决策的完整性，不证明 source authenticity",
        "independent source snapshot",
        "human review",
        "independent calibration",
        "reviewed-data → one small training matrix → frozen family-disjoint blind-v2",
        "insufficient data or no stable blind gain",
        "冻结 Hermes，并将后续时间转向 Voice2Task",
        "shared formatter + v3 artifacts + sealed fail-closed trainer 是实现进展",
        "test/brief counts 只是证据，不是进展",
        "review/navigation aid，不是第二事实源",
        "940 passed, 1 failed",
        "文档更新前基线，不是最终 full-suite 结论",
        *BLOCKER_CODES,
        *CURRENT_V3_PACK_SHA256.values(),
    ):
        assert truth in visible_text

    expected_per_skill = EXPECTED_DIVERSITY_DIAGNOSTICS[
        "per_skill_unique_train_positive_prompt_count"
    ]
    assert isinstance(expected_per_skill, dict)
    for skill_id, count in expected_per_skill.items():
        assert f"{skill_id} {count}" in visible_text

    required_link_suffixes = (
        "proposal.md",
        "design.md",
        "specs/router-query-contract/spec.md",
        "specs/router-training-data-v2-qualification-pack/spec.md",
        "specs/router-training-input-gate/spec.md",
        "tasks.md",
        "src/hermes_skilleval/router_query.py",
        "src/hermes_skilleval/router_training_data_v2.py",
        "src/hermes_skilleval/training_input.py",
        "scripts/train_embedding_router.py",
        "tests/test_router_query_contract.py",
        "tests/test_router_training_data_v2_artifacts.py",
        "tests/test_training_input.py",
        "candidate-pairs.jsonl",
        "qualification-report.json",
        "manifest.json",
    )
    for suffix in required_link_suffixes:
        assert any(href.endswith(suffix) for href in parser.hrefs), suffix
    for href in parser.hrefs:
        target = _local_link_target(CURRENT_V3_BRIEF, href)
        if target is not None:
            assert target.exists(), (
                f"missing current v3 brief link target: {href} -> {target}"
            )

    for overclaim in (
        "FINAL_FULL_SUITE_PASS",
        "remote CI passed",
        "training completed",
        "blind-v2 completed",
        "benchmark improved",
        "Phase 19",
    ):
        assert overclaim not in visible_text


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


def test_lifecycle_truth_separates_active_apply_from_historical_v1_change():
    branch = "ops/archive-build-router-training-data-v2-qualification-pack"
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())
    visible_brief = _visible_html_text(HUMAN_BRIEF.read_text(encoding="utf-8"))

    assert ACTIVE_CHANGE_PATH in readme
    assert "LOCAL_WORKING_DIFF" in normalized_readme
    assert "base HEAD `f996690700a79ab4c065ed8523340d2fd387f6b9`" in normalized_readme
    assert "uncommitted, unpushed, has no PR, is unmerged" in normalized_readme
    assert "active and unarchived" in normalized_readme
    assert "remote CI is unavailable" in normalized_readme
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
