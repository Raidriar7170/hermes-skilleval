"""Compact, public evidence export and records-only recomputation; no model calls."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from hermes_skilleval.intervention.functional_outcomes import outcomes
from hermes_skilleval.intervention.functional_costs import cost_ledger
from hermes_skilleval.intervention.repair_checks import declared_api_absence
from hermes_skilleval.intervention.repair_composer import (
    Candidate,
    CandidatePool,
    Obligation,
    objective,
)
from hermes_skilleval.intervention.repair_content_report import summarize
from hermes_skilleval.intervention.repair_knowledge import RepairKnowledgeUnit
from hermes_skilleval.intervention.session import dump, inventory


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def public_checks(checks):
    fields = {
        "valid",
        "passed",
        "returncode",
        "cases",
        "failures",
        "errors",
        "skipped",
        "skipped_ids",
        "preexisting_skips",
        "seconds",
        "selectors",
        "complete_expected_cases",
        "required_public_api_absent",
    }
    return {
        kind: {
            **{k: v for k, v in result.items() if k in fields},
            **(
                {"error": "CHECK_UNAVAILABLE_SEE_PRIVATE_RECORD"}
                if "error" in result
                else {}
            ),
        }
        for kind, result in checks.items()
    }


def prepare(private, output, plan):
    output.mkdir(parents=True, exist_ok=True)
    qualification = json.loads((private / "qualification-final.json").read_text())
    for row in qualification["rows"]:
        row["variants"] = {k: public_checks(v) for k, v in row["variants"].items()}
    dump(output / "qualification.json", qualification)
    copy(private / "preflight-v1/preflight.json", output / "preflight.json")
    copy(
        private / "pre-sampling-amendment.json", output / "pre-sampling-amendment.json"
    )
    for row in plan["tasks"]:
        base = row["base_commit"]
        task = private / "tasks" / row["instance_id"]
        for name in ["units.json", "source-manifest.json", "build.json"]:
            copy(
                private / "knowledge" / base / name, output / "knowledge" / base / name
            )
        dump(
            output / "tasks" / row["instance_id"] / "request.json",
            {
                "text": (task / "request.txt").read_text(),
                "sha256": sha(task / "request.txt"),
            },
        )
        meta = json.loads((task / "task.json").read_text())
        compact = {
            k: meta[k]
            for k in [
                "repo",
                "base_commit",
                "mechanism",
                "required_api_absence",
                "required_api_collector",
                "allowed_regression_skips",
                "regression_scope_limitation",
            ]
            if k in meta
        }
        compact["selectors"] = json.loads(
            (task / "evaluation/selectors.json").read_text()
        )
        compact["test_patch_sha256"] = sha(task / "evaluation/test.patch")
        dump(
            output / "tasks" / row["instance_id"] / "acceptance-contract.json", compact
        )
    legacy = json.loads((private / "legacy-posthoc-v1/results.json").read_text())
    rows = []
    for row in legacy["rows"]:
        tid = row["task_id"]
        repeat = row["repeat"]
        source = private / "legacy-posthoc-v1/checks" / tid / f"r{repeat}"
        target = output / "legacy-posthoc" / tid / f"r{repeat}"
        checks = {
            k: {field: v[field] for field in ["valid", "passed"] if field in v}
            for k, v in row["checks"].items()
        }
        for kind in ["target", "regression"]:
            copy(source / kind / "junit.xml", target / (kind + "-junit.xml"))
        old = (
            Path("artifacts/task-skill-failure-diagnostic-v1/native/native")
            / tid
            / f"native-r{repeat}-NO_INTERVENTION/candidate.patch"
        )
        assert sha(old) == sha(source / "capture/candidate.patch")
        rows.append(
            {
                "task_id": tid,
                "repeat": repeat,
                "status": "POSTHOC_ACCEPTANCE_ONLY",
                "original_patch": str(old),
                "patch_sha256": sha(old),
                "checks": checks,
            }
        )
        copy(
            private / "legacy-posthoc-v1/tasks" / tid / "trusted/test_behavior.py",
            output / "legacy-posthoc" / tid / "test_behavior.py.txt",
        )
    dump(output / "legacy-posthoc/results.json", {"rows": rows, "new_agent_calls": 0})


def export_phase(private, output, plan, phase):
    study = private / "study-v1"
    records = json.loads((study / (phase + "-results.json")).read_text())
    version = records.get("acceptance_version", "v1")
    rows = []
    for row in records["rows"]:
        tid, arm, repeat = row["task_id"], row["arm"], row["repeat"]
        cell = f"r{repeat}" if phase == "native" else f"{arm}-r{repeat}"
        root = study / phase / tid / cell
        acceptance = root / ("acceptance-v2" if version == "v2" else "acceptance")
        dest = output / phase / tid / cell
        public = {
            k: row[k]
            for k in [
                "task_id",
                "arm",
                "repeat",
                "phase",
                "y_functional",
                "y_target",
                "y_regression",
                "file_policy_status",
                "verifier_integrity_status",
            ]
        }
        execution = {
            k: v
            for k, v in row["execution"].items()
            if k
            in [
                "status",
                "model_input_observed",
                "injected",
                "payload_tokens",
                "initial_remaining",
                "total_seconds",
                "tail_seconds",
                "preparation_seconds",
                "policy_initialization_seconds",
                "controller_overhead_seconds",
                "prefix_seconds",
                "turns",
            ]
        }
        execution["thread_id"] = (
            "sha256:"
            + hashlib.sha256(row["execution"]["thread_id"].encode()).hexdigest()
            if row["execution"].get("thread_id")
            else None
        )
        public["execution"] = execution
        if (acceptance / "acceptance.json").exists():
            accepted = json.loads((acceptance / "acceptance.json").read_text())
            public["checks"] = public_checks(accepted["checks"])
            copy(acceptance / "capture/candidate.patch", dest / "candidate.patch")
            public["candidate_patch_sha256"] = sha(dest / "candidate.patch")
            public["complete_before_inventory_sha256"] = hashlib.sha256(
                json.dumps(accepted["capture"]["before"], sort_keys=True).encode()
            ).hexdigest()
            public["complete_after_inventory_sha256"] = hashlib.sha256(
                json.dumps(accepted["capture"]["after"], sort_keys=True).encode()
            ).hexdigest()
            public["changed_files"] = accepted["capture"]["changed_files"]
            for kind in ["target", "regression"]:
                for filename in ["junit.xml", "collected.json"]:
                    src = acceptance / "checks" / kind / filename
                    if src.exists():
                        copy(src, dest / (kind + "-" + filename))
            overlay_record = acceptance / "checks/test-overlay.json"
            if overlay_record.exists():
                copy(overlay_record, dest / "test-overlay.json")
        else:
            public["checks"] = {}
        public["evidence_path"] = str(dest.relative_to(output))
        rows.append(public)
    dump(
        output / (phase + "-results.json"),
        {
            "rows": rows,
            "planned": records["planned"],
            "plan_digest": records["plan_digest"],
            "acceptance_version": version,
            "acceptance_status": records.get("status", "ORIGINAL_ACCEPTANCE"),
            "original_results_sha256": records.get("original_results_sha256"),
        },
    )
    if phase != "native":
        lock = json.loads((study / (phase + "-lock.json")).read_text())
        for state in lock["states"]:
            state.pop("checkpoint")
        dump(output / (phase + "-lock.json"), lock)
        dump(output / (phase + "-summary.json"), summarize(rows, lock))


def replay(output, phase):
    records = json.loads((output / (phase + "-results.json")).read_text())
    for row in records["rows"]:
        path = output / row["evidence_path"]
        if row.get("candidate_patch_sha256"):
            assert sha(path / "candidate.patch") == row["candidate_patch_sha256"]
        meta = json.loads(
            (output / "tasks" / row["task_id"] / "acceptance-contract.json").read_text()
        )
        checks = {}
        for kind in ["target", "regression"]:
            j = path / (kind + "-junit.xml")
            if not j.exists():
                checks[kind] = {"valid": False, "passed": False}
                continue
            cases = list(ET.parse(j).getroot().iter("testcase"))
            errors = [c for c in cases if c.find("error") is not None]
            skipped = [c for c in cases if c.find("skipped") is not None]
            failed = [c for c in cases if c.find("failure") is not None]
            cp = path / (kind + "-collected.json")
            collected = json.loads(cp.read_text()) if cp.exists() else []
            ids = meta["selectors"][kind]
            skipids = sorted(
                c.get("classname", "") + "::" + c.get("name", "") for c in skipped
            )
            allowed = (
                sorted(meta.get("allowed_regression_skips", []))
                if kind == "regression"
                else []
            )
            rc = row["checks"][kind].get("returncode")
            valid = (
                rc in (0, 1)
                and sorted(collected) == sorted(ids)
                and len(cases) == len(ids)
                and not errors
                and skipids == allowed
                and len(cases) > len(skipped)
            )
            missing = kind == "target" and declared_api_absence(meta, errors, cases, rc)
            valid = bool(valid or missing)
            checks[kind] = {"valid": valid, "passed": valid and not failed and rc == 0}
            assert checks[kind]["valid"] == row["checks"][kind]["valid"]
            assert checks[kind]["passed"] == row["checks"][kind]["passed"]
        recomputed = outcomes(
            row["execution"], checks, integrity=row["verifier_integrity_status"]
        )
        assert recomputed["y_functional"] == row["y_functional"]
    if phase != "native":
        lock = json.loads((output / (phase + "-lock.json")).read_text())
        for state in lock["states"]:
            raw = state["pool"]
            pool = CandidatePool(
                tuple(
                    Candidate(
                        RepairKnowledgeUnit.from_dict(c["unit"]),
                        c["relevance"],
                        tuple(c["coverage"]),
                        c["exposure"],
                        c["retrieval"],
                    )
                    for c in raw["candidates"]
                ),
                tuple(tuple(r) for r in raw["overlap"]),
                tuple(Obligation(**o) for o in raw["obligations"]),
                raw["query"],
            )
            for method, entry in state["packs"].items():
                fallback = entry["pack"]["method"] == "H-fallback-M"
                scores = objective(
                    pool,
                    entry["pack"]["indices"],
                    no_gap=method == "H-no-gap" and not fallback,
                    no_exposure=method == "H-no-exposure" and not fallback,
                )
                assert all(
                    abs(scores[k] - entry["pack"]["scores"][k]) < 1e-10 for k in scores
                )
        summary = summarize(records["rows"], lock)
        assert summary == json.loads((output / (phase + "-summary.json")).read_text())
    result = {
        "phase": phase,
        "rows_verified": len(records["rows"]),
        "new_model_calls": 0,
        "new_behavioral_checks": 0,
        "status": "RECORDS_RECOMPUTED",
        "limitation": "Saved patch identities/JUnit/selector decisions, not a fresh Agent or second-host behavioral replication.",
    }
    dump(output / (phase + "-replay.json"), result)
    print(json.dumps(result))


def costs(private, output):
    """Count every reserved attempt, including prefixes and interrupted runs."""
    study = private / "study-v1"
    groups = {}
    for phase in ["native", "pilot", "confirmation-prefixes", "confirm"]:
        rows = []
        for run in sorted((study / phase).glob("*/*")):
            if not run.is_dir():
                continue
            path = run / "execution.json"
            execution = (
                json.loads(path.read_text())
                if path.exists()
                else {"status": "UNKNOWN_INTERRUPTED_ATTEMPT"}
            )
            rows.append({"run": str(run), "execution": execution})
        if rows:
            groups[phase] = rows
    report = cost_ledger(groups)
    report["scope"] = (
        "All reserved study execution directories, including incomplete attempts "
        "and confirmation prefixes; partial usage is observed-only, never billing."
    )
    report["research_reserved_attempts"] = {
        key: len(rows) for key, rows in groups.items()
    }
    report["offline_knowledge_build"] = {
        "model_calls": 0,
        "wall_seconds": None,
        "timing_status": "NOT_RECORDED",
    }
    report["online_selection_model_calls"] = 0
    report["training"] = {"status": "NOT_RUN", "model_calls": 0}
    report["agent_calls_semantics"] = (
        "The zero agent_calls/model_calls fields describe this export operation. "
        "research_reserved_attempts counts the real study attempts separately."
    )
    dump(output / "secondary-cost-ledger.json", report)


def source_support(private, output, plan):
    rows = []
    for task in plan["tasks"]:
        revision = task["base_commit"]
        base = private / "tasks" / task["instance_id"] / "base"
        assert (
            hashlib.sha256(
                json.dumps(inventory(base), sort_keys=True).encode()
            ).hexdigest()
            == task["files"]["base"]
        )
        assert (
            sha(output / "knowledge" / revision / "units.json")
            == task["knowledge_sha256"]
        )
        units = json.loads((output / "knowledge" / revision / "units.json").read_text())
        verified = []
        for raw in units:
            unit = RepairKnowledgeUnit.from_dict(raw)
            assert unit.source_revision == revision
            for span in unit.source_spans:
                path = (base / span.path_or_public_url).resolve()
                assert path.is_relative_to(base.resolve())
                assert span.revision == revision
                lines = path.read_text().splitlines(keepends=True)
                excerpt = "".join(lines[span.line_start - 1 : span.line_end])
                assert excerpt == span.exact_excerpt
            verified.append(unit.unit_id)
        rows.append({"revision": revision, "verified_units": verified})
    dump(
        output / "source-support.json",
        {
            "status": "VERIFIED_FOR_SCOPE",
            "method": "Fresh exact-span comparison against each frozen public base",
            "limitation": "Source attribution only; observed implementation is not a correctness invariant or an answer.",
            "rows": rows,
            "model_calls": 0,
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "command", choices=["prepare", "phase", "replay", "costs", "source-support"]
    )
    p.add_argument("--private", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--plan", type=Path)
    p.add_argument("--phase", default="pilot", choices=["native", "pilot", "confirm"])
    a = p.parse_args()
    if a.command == "replay":
        replay(a.output, a.phase)
    elif a.command == "costs":
        costs(a.private, a.output)
    else:
        plan = json.loads(a.plan.read_text())
        if a.command == "prepare":
            prepare(a.private, a.output, plan)
        elif a.command == "source-support":
            source_support(a.private, a.output, plan)
        else:
            export_phase(a.private, a.output, plan, a.phase)
