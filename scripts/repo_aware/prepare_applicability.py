"""Reproducible public-source preparation; frozen studies are never overwritten."""

import json
import hashlib
import subprocess
import shutil
import tarfile
import io
from pathlib import Path
from hermes_skilleval.repo_routing.context import extract_fragments, FragmentBudget
import argparse

parser = argparse.ArgumentParser(
    description="Prepare public issue inputs and complete skill packages without labels or model calls. Run from the Hermes source root."
)
parser.add_argument(
    "--sources-root",
    type=Path,
    required=True,
    help="Directory with sqlite-utils, csvkit and csv-diff Git clones",
)
parser.add_argument(
    "--issues-root",
    type=Path,
    required=True,
    help="Directory holding the frozen GitHub issue page JSON files",
)
parser.add_argument(
    "--scratch",
    type=Path,
    required=True,
    help="New private snapshots and annotation packet directory",
)
parser.add_argument(
    "--output-root",
    type=Path,
    required=True,
    help="New output directory; never overwrites the frozen study",
)
args = parser.parse_args()
args.output_root.mkdir(parents=True, exist_ok=False)
private = args.scratch
private.mkdir(parents=True, exist_ok=True)
cfg = args.output_root / "configs/conditional-applicability-v1"
cfg.mkdir(parents=True)
art = args.output_root / "artifacts/conditional-applicability-v1"
art.mkdir(parents=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def dump(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


repos = {
    name: args.sources_root / name for name in ["sqlite-utils", "csvkit", "csv-diff"]
}
revs = {
    r: git(p, "rev-list", "-1", "--before=2020-01-01", "--all").decode().strip()
    for r, p in repos.items()
}
orig = json.loads(Path("configs/repo-portability/skills-v1/registry.json").read_text())
skills = []
for s in orig["skills"][:2]:
    s = dict(s)
    dest = cfg / "skills" / s["id"]
    dest.parent.mkdir(exist_ok=True)
    if not dest.exists():
        shutil.copytree(Path("configs/repo-portability/skills-v1") / s["id"], dest)
    s["path"] = str(dest / "SKILL.md")
    s["package_path"] = "skills/" + s["id"]
    s["origin"] = "external_public_package"
    skills.append(s)


def section(text, anchor):
    start = text.index(".. _" + anchor + ":")
    end = text.find("\n.. _", start + 5)
    return text[start : end if end >= 0 else None].strip()


specs = [
    (
        "sqlite-ingest",
        "sqlite-utils",
        "docs/cli.rst",
        ["cli_inserting_data", "cli_insert_replace", "cli_upsert"],
        "Use for inserting JSON, CSV or TSV records into SQLite, including primary-key replacement and upsert. Confirm input format and whether mutation is requested; these commands write a database. Compare stored rows to the input; do not use ingestion as a read-only inspection step.",
    ),
    (
        "sqlite-schema",
        "sqlite-utils",
        "docs/python-api.rst",
        [
            "python_api_add_column",
            "python_api_add_foreign_key",
            "python_api_index_foreign_keys",
        ],
        "Use for SQLite column, foreign-key or index changes. Inspect the existing schema before mutation, apply only the requested operation in a disposable reproduction, then check schema and preserved rows. These APIs require a writable SQLite database; they do not describe CSV formatting.",
    ),
    (
        "sqlite-fulltext",
        "sqlite-utils",
        "docs/python-api.rst",
        ["python_api_fts"],
        "Use for configuring or maintaining SQLite full-text indexes. Check available FTS version, indexed columns and trigger policy. Verify search against indexed records. Index creation and population mutate the database; do not assume it is a generic SQL or CSV text-search procedure.",
    ),
    (
        "csv-dialect",
        "csvkit",
        "docs/scripts/csvformat.rst",
        None,
        "Use for CSV delimiter, quoting, escaping and line-ending conversion with csvformat. Separate input dialect flags from output dialect flags, run a minimal fixture, and compare parsed field contents before and after. This is serialization conversion; it does not implement arbitrary sorting, joins or database schema changes.",
    ),
    (
        "tabular-conversion",
        "csvkit",
        "docs/scripts/in2csv.rst",
        None,
        "Use for in2csv conversion of the documented input formats to CSV. Select the actual input format and applicable flags. Check headers, types and missing values in a small fixture. Format-specific flags are not interchangeable; follow the source limitations below.",
    ),
    (
        "csv-relational-join",
        "csvkit",
        "docs/scripts/csvjoin.rst",
        None,
        "Use for joining CSV tables with csvjoin. Identify join keys and requested inner/outer direction, check unmatched rows and multiplicity, and respect the memory requirement. Joining rows by keys is distinct from stacking records or computing a change report.",
    ),
    (
        "sql-query-export",
        "csvkit",
        "docs/scripts/sql2csv.rst",
        None,
        "Use for executing a SQL query and exporting its results to CSV with sql2csv. Confirm the connection and input-query encoding, query source precedence and header policy. For read-only requests use a read-only query and do not run the example import steps. Backend availability must be established; a connection-string example is not authorization for remote access.",
    ),
    (
        "keyed-csv-diff",
        "csv-diff",
        "README.md",
        None,
        "Use for comparing two CSV snapshots by a unique key with csv-diff. Establish the key and compare added, removed and changed records; inspect column changes separately. This documented version accepts CSV snapshots and emits text or JSON; it does not document JSON input, arbitrary separators or CSV diff output. Do not assume these newer features exist.",
    ),
]
for sid, repo, file, anchors, guide in specs:
    raw = git(repos[repo], "show", revs[repo] + ":" + file).decode()
    excerpt = "\n\n".join(section(raw, a) for a in anchors) if anchors else raw
    body = f"# {sid}\n\nAuthor-adapted operational skill, based only on the versioned pre-2020 public documentation below. Not an independently authored external package.\n\n{guide}\n\n## Versioned reference\n\n{excerpt}\n"
    dest = cfg / "skills" / sid
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SKILL.md").write_text(
        "---\nname: "
        + sid
        + "\ndescription: "
        + guide.split(". ")[0]
        + ".\n---\n\n"
        + body
    )
    owner = "wireservice" if repo == "csvkit" else "simonw"
    licfile = "docs/license.rst" if repo == "csvkit" else "LICENSE"
    license_bytes = git(repos[repo], "show", revs[repo] + ":" + licfile)
    (dest / "LICENSE").write_bytes(license_bytes)
    if repo == "csvkit":
        (dest / "COPYING").write_bytes(
            git(repos[repo], "show", revs[repo] + ":COPYING")
        )
    s = dict(
        id=sid,
        name=sid,
        description=guide.split(". ")[0] + ".",
        body=body,
        path=str(dest / "SKILL.md"),
        package_path="skills/" + sid,
        origin="author_adapted",
        source=f"https://github.com/{owner}/{repo}/blob/{revs[repo]}/{file}",
        source_revision=revs[repo],
        source_file_sha256=sha(raw.encode()),
        source_excerpts_sha256=sha(excerpt.encode()),
        license="MIT" if repo == "csvkit" else "Apache-2.0",
        requires_network=False,
        dependencies=[repo],
        execution_scope="Local disposable reproduction with installed project dependencies only; no external writes",
        version_scope="Use checked-out documentation to verify the pre-2020 operation remains available",
    )
    skills.append(s)
for s in skills:
    dest = cfg / s["package_path"]
    files = {
        str(p.relative_to(dest)): sha(p.read_bytes())
        for p in sorted(dest.rglob("*"))
        if p.is_file()
    }
    s["package_files"] = files
    s["package_sha256"] = sha(json.dumps(files, sort_keys=True).encode())
    s["package_revision"] = s.get("source_revision", s["source"])
    s["complete_package"] = True
registry = {
    "schema": "task-conditioned-registry-v1",
    "registry_id": sha(json.dumps(skills, sort_keys=True).encode()),
    "skills": skills,
    "frozen_before_labels": True,
}
dump(cfg / "registry.json", registry)
# Explicit factual mechanism assignment, before label/model results.
sets = [
    (
        "sqlite-utils",
        "sqlite-utils-issues-3.json",
        [
            (202, "fts-import", "model-dev"),
            (207, "column-statistics", "check"),
            (211, "trigger-introspection", "cal"),
            (223, "csv-delimiter", "fit"),
            (228, "headerless-import", "model-dev"),
            (234, "batch-schema-expansion", "fit"),
            (236, "database-attachment", "cal"),
            (238, "foreign-key-identifier", "fit"),
            (246, "fts-query-escaping", "fit"),
            (250, "utf8-bom", "fit"),
            (260, "descending-index", "fit"),
            (274, "sql-dump", "check"),
        ],
    ),
    (
        "csvkit",
        "csvkit-issues-12.json",
        [
            (1106, "nested-json-columns", "model-dev"),
            (1114, "database-driver-options", "fit"),
            (1125, "sort-preserve-types", "fit"),
            (1134, "spreadsheet-null-values", "fit"),
            (1141, "heterogeneous-stack", "fit"),
            (1148, "multiline-display", "cal"),
            (1159, "inference-preserve-fields", "fit"),
            (1177, "grep-header-semantics", "check"),
        ],
    ),
    (
        "csv-diff",
        "csv-diff-issues.json",
        [
            (12, "json-diff-input", "fit"),
            (18, "empty-snapshot", "model-dev"),
            (31, "duplicate-diff-key", "cal"),
            (39, "diff-csv-output", "check"),
        ],
    ),
]
tasks = []
for repo, file, items in sets:
    issues = {x["number"]: x for x in json.loads((args.issues_root / file).read_text())}
    for num, group, split in items:
        x = issues[num]
        tid = f"{repo}-issue-{num}"
        request = x["title"] + "\n\n" + (x["body"] or "")
        # Retain full public request including public proposed approaches; no comments or future fixes.
        rev = (
            git(repos[repo], "rev-list", "-1", "--before=" + x["created_at"], "--all")
            .decode()
            .strip()
        )
        base = private / "snapshots" / tid
        base.mkdir(parents=True, exist_ok=True)
        if not any(base.iterdir()):
            payload = git(repos[repo], "archive", rev)
            with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
                tar.extractall(base, filter="data")
        context = extract_fragments(
            base,
            request,
            {
                "network": "disabled",
                "execution": "offline_text_study; repository dependencies unverified",
            },
            FragmentBudget(max_snippets=3, output_bytes=6000),
        )
        context.pop("cost", None)
        tasks.append(
            dict(
                task_id=tid,
                parent_task_id=tid,
                requirement_id="whole-request",
                composite_requirement=True,
                repair_group_id=group,
                split=split,
                repository=x["repository_url"].split("/repos/")[1],
                source_revision=rev,
                request_ref=x["html_url"],
                request=request,
                request_sha256=sha(request.encode()),
                public_context_ref="contexts.json#" + tid,
                context=context,
                source_created_at=x["created_at"],
                source_updated_at=x["updated_at"],
                origin_kind="natural_public_issue",
                derived_from=None,
                previously_observed=False,
                runtime_qualified=False,
            )
        )
dump(art / "tasks.json", tasks)
dump(
    cfg / "splits.json",
    {t["task_id"]: {"group": t["repair_group_id"], "split": t["split"]} for t in tasks},
)
dump(
    art / "contexts.json",
    {t["task_id"]: {"ref": f"tasks.json#/{i}/context"} for i, t in enumerate(tasks)},
)
dump(
    art / "dataset-manifest.json",
    dict(
        schema="conditional-applicability-v1",
        tasks=24,
        repair_groups=24,
        requirements=24,
        skills=len(skills),
        pairs=24 * len(skills),
        registry_id=registry["registry_id"],
        task_sha256=sha((art / "tasks.json").read_bytes()),
        sampling="Purposive workflow diversity among enumerated public issue pages; all frozen registry skills per task; inclusion probability in GitHub population unknown; not user traffic.",
        source_pages=[x[1] for x in sets],
        human_reviewed=False,
        legacy_five="Original 20 tasks/100 rows retained unchanged in r-repair-v1; not new check",
        runtime_preselection=["sqlite-utils-issue-207", "csv-diff-issue-39"],
        runtime_qualification="NOT_YET_QUALIFIED; base/reference required before any execution",
    ),
)
# Blinded packet excludes split/group, all labels, model predictions and reference patches.
dump(
    private / "annotation-packet.json",
    {
        "schema": "conditional-applicability-v1",
        "tasks": [
            {
                k: t[k]
                for k in [
                    "task_id",
                    "request",
                    "repository",
                    "source_revision",
                    "context",
                ]
            }
            for t in tasks
        ],
        "skills": [
            {
                k: s[k]
                for k in [
                    "id",
                    "name",
                    "description",
                    "body",
                    "source",
                    "package_sha256",
                ]
            }
            for s in skills
        ],
    },
)
print(
    "Prepared",
    len(tasks),
    "tasks",
    len(skills),
    "skills",
    len(tasks) * len(skills),
    "pairs",
)
