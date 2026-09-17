"""Posthoc behavioral checks of frozen patches; never invokes repair or routing."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import os
import json
from pathlib import Path
import stat
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape

from .advisory_capture import inventory as source_inventory, reconstruct, RUNTIME
from .advisory_records import recompute as legacy_records
from .acceptance_probe import command

TASKS = ("csvkit-issue-1225", "sqlite-utils-issue-368")
SCOPE = "POSTHOC_REVALIDATION_OF_FROZEN_PATCHES"
VERSION = "acceptance-semantics-v1"
ORIGINAL = [[["a", "b", "c"], ["True", "2", "3"]]]
MULTI = [
    [["name", "value"], ["alpha", "red"], ["alpha", "red"]],
    [["label", "note"], ["beta", "blue,green"], ["gamma", 'quoted "text"']],
]


def safe_files(root):
    """Never follow candidate-controlled file or directory links on the host."""
    result = []
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            mode = path.lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(
                    "OUTPUT_BOUNDARY_VIOLATION: non-regular evidence " + name
                )
            if stat.S_ISREG(mode):
                result.append(path)
    return result


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("non-regular evidence file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            return hashlib.sha256(stream.read()).hexdigest()
    finally:
        os.close(fd)


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()


def write(p, v):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2) + "\n")


def inventory(legacy, tasks, runs):
    old = legacy_records(legacy)
    rows = read(legacy / "runs.json")
    qualification = {
        t["task_id"]: t for t in read(legacy / "qualification.json")["tasks"]
    }
    result = []
    for row in sorted(rows, key=lambda r: r["run_id"]):
        tid, rid = row["task_id"], row["run_id"]
        root = tasks / tid
        task = read(root / "task.json")
        q = qualification[tid]
        if sha(root / "task.json") != q["task_sha256"]:
            raise ValueError("task/base declaration mismatch")
        if source_inventory(root / "trusted") != q["trusted_manifest"]:
            raise ValueError("original trusted assets mismatch")
        rawpath = runs / rid / "raw-inventory.json"
        if sha(rawpath) != row["raw-inventory.json_sha256"]:
            raise ValueError("original source inventory mismatch")
        cap = read(runs / rid / "capture.json")
        raw = read(rawpath)
        after = {
            k: v for k, v in raw.items() if not any(x in RUNTIME for x in Path(k).parts)
        }
        if cap["after"] != after:
            raise ValueError("capture differs from bound original inventory")
        base = source_inventory(root / "base")
        # Identical exclusion to the original advisory reconstruction, not a new policy.
        if base != {
            k: v for k, v in cap["before"].items() if not k.startswith(".agents/")
        }:
            raise ValueError("base inventory mismatch")
        patch = legacy / "patches" / (rid + ".patch")
        if sha(patch) != cap["patch_sha256"] or sha(patch) != row["patch_sha256"]:
            raise ValueError("patch identity mismatch")
        prompt = (runs / rid / "prompt.txt").read_text()
        request = (root / "request.txt").read_text()
        if sha(root / "request.txt") != task[
            "public_request_sha256"
        ] or not prompt.startswith(request):
            raise ValueError("actual prompt/request mismatch")
        result.append(
            dict(
                run_id=rid,
                task_id=tid,
                arm=row["arm"],
                repeat=row["repeat"],
                alias=f"candidate-{len(result) + 1:02d}",
                affected=tid in TASKS,
                patch_path="patches/" + rid + ".patch",
                patch_sha256=sha(patch),
                base_commit=task["base_commit"],
                base_identity=digest(base),
                rebuilt_expected_identity=digest(
                    {k: v for k, v in after.items() if not k.startswith(".agents/")}
                ),
                trusted_identity=digest(q["trusted_manifest"]),
                original_source_manifest="AVAILABLE_VERIFIED",
                prompt_sha256=sha(runs / rid / "prompt.txt"),
                request_sha256=sha(root / "request.txt"),
                visible_to_original_agent="YES",
                legacy_target=row["checks"]["target"]["passed"],
                legacy_regression=row["checks"]["regression"]["passed"],
                legacy_result=row["result"],
            )
        )
    for tid in TASKS:
        cells = [(r["arm"], r["repeat"]) for r in result if r["task_id"] == tid]
        if len(cells) != 8 or set(cells) != {
            (a, n) for a in ("N", "F2", "T2", "J2") for n in (1, 2)
        }:
            raise ValueError("missing/duplicate cell")
    return dict(
        version=VERSION,
        analysis_scope=SCOPE,
        rows=result,
        legacy_counts=old["counts"],
        legacy_index_sha256=sha(legacy / "evidence-index.json"),
    )


def make_xlsx(path, matrices=MULTI):
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(matrices) + 1)
        )
        + "</Types>",
        "_rels/.rels": f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
        + "".join(
            f'<sheet name="Sheet{i}" sheetId="{i}" r:id="rId{i}"/>'
            for i in range(1, len(matrices) + 1)
        )
        + "</sheets></workbook>",
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(matrices) + 1)
        )
        + "</Relationships>",
    }
    for i, matrix in enumerate(matrices, 1):
        rows = "".join(
            f'<row r="{n}">'
            + "".join(
                f'<c r="{chr(65 + c)}{n}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
                for c, v in enumerate(row)
            )
            + "</row>"
            for n, row in enumerate(matrix, 1)
        )
        files[f"xl/worksheets/sheet{i}.xml"] = (
            f'<worksheet xmlns="{ns}"><sheetData>{rows}</sheetData></worksheet>'
        )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(files.items()):
            z.writestr(zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0)), content)


def matrix(text):
    return list(csv.reader(io.StringIO(text, newline=""), strict=True))


def judge_csv(rc, stdout, output, expected, *, export=True):
    try:
        files = {}
        for p in output.iterdir():
            if not stat.S_ISREG(p.lstat().st_mode) or p.suffix != ".csv":
                return {
                    "status": "FAIL",
                    "reason": "OUTPUT_BOUNDARY_VIOLATION",
                    "files": {},
                }
            files[p.name] = matrix(p.read_text())
        actual = Counter(json.dumps(v) for v in files.values())
        want = Counter(json.dumps(v) for v in expected)
        good = (
            rc == 0
            and matrix(stdout) == expected[0]
            and (actual == want if export else not files)
        )
        return {
            "status": "PASS" if good else "FAIL",
            "reason": None if good else "EXIT_OR_CONTENT_MISMATCH",
            "files": files,
            "stdout_matrix": matrix(stdout),
        }
    except (ValueError, UnicodeError, OSError, csv.Error) as exc:
        return {"status": "FAIL", "reason": "INVALID_CSV:" + str(exc), "files": {}}


def judge_entry(rc, stdout, kind):
    if rc is None:
        return {"status": "UNKNOWN", "reason": "TIMEOUT"}
    try:
        good = rc == 0 and (
            "Usage:" in stdout
            if kind == "help"
            else json.loads(stdout) == [{"table": "acceptance_items"}]
        )
    except (ValueError, TypeError):
        good = False
    return {
        "status": "PASS" if good else "FAIL",
        "reason": None if good else "ENTRY_BEHAVIOR_MISMATCH",
    }


def invoke(source, image, mode, args, work, *, fixture=None, stdin=False, timeout=30):
    from hermes_skilleval._maintenance.check import stopped

    work.mkdir(parents=True, exist_ok=False)
    output = work / "files"
    output.mkdir()
    name = "hermes-acceptance-" + uuid.uuid4().hex
    cmd = [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65534:65534",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--pids-limit",
        "64",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=32m,mode=1777",
        "-v",
        f"{source.resolve()}:/input:ro",
        "-v",
        f"{output.resolve()}:/work:rw",
        "-w",
        "/work",
    ]
    output.chmod(0o777)
    if fixture:
        cmd += ["-v", f"{fixture.resolve()}:/fixture:ro"]
    cmd += [image, *command(mode, args)]
    started = time.monotonic()
    rc = None
    out = b""
    err = b""
    try:
        p = subprocess.run(
            cmd,
            input=fixture.read_bytes() if stdin else b"",
            capture_output=True,
            timeout=timeout,
        )
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        out, err = exc.stdout or b"", exc.stderr or b""
    finally:
        stopped(name)
    safe_files(output)
    stdout = out.decode("utf-8", errors="replace")
    stderr = err.decode("utf-8", errors="replace")
    (work / "stdout.txt").write_text(stdout)
    (work / "stderr.txt").write_text(stderr)
    record = dict(
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
        seconds=time.monotonic() - started,
        entry=mode,
        argv=args,
        source_mount="/input",
        cleanup_confirmed=True,
    )
    write(work / "process.json", record)
    return record, output


def behavior(source, tid, image, config, output):
    result = {}
    if tid == TASKS[0]:
        for key, fixture, expected, export in [
            ("csv_original_fixture_content", "dummy.xlsx", ORIGINAL, True),
            ("csv_multisheet_content", "multisheet.xlsx", MULTI, True),
            ("csv_file_input_regression", "dummy.xlsx", ORIGINAL, False),
            ("csv_multisheet_file_regression", "multisheet.xlsx", MULTI, False),
        ]:
            args = (
                ["-f", "xlsx", "--write-sheets", "-"]
                if export
                else ["-f", "xlsx", "/fixture"]
            )
            p, files = invoke(
                source,
                image,
                "csv",
                args,
                output / key,
                fixture=config / fixture,
                stdin=export,
            )
            verdict = judge_csv(
                p["returncode"], p["stdout"], files, expected, export=export
            )
            if p["returncode"] is None:
                verdict = {"status": "UNKNOWN", "reason": "TIMEOUT"}
            result[key] = {**verdict, "process": p}
    else:
        for mode in ("package", "submodule", "console"):
            for kind in ("help", "function"):
                key = mode + "_" + kind
                args = ["--help"] if kind == "help" else ["tables", "/fixture"]
                p, _ = invoke(
                    source,
                    image,
                    mode,
                    args,
                    output / key,
                    fixture=config / "known.db" if kind == "function" else None,
                )
                result[key] = {
                    **judge_entry(p["returncode"], p["stdout"], kind),
                    "process": p,
                }
    return result


def junit(path, results):
    suite = ET.Element("testsuite", tests=str(len(results)))
    for name, r in results.items():
        c = ET.SubElement(suite, "testcase", classname=VERSION, name=name)
        if r["status"] != "PASS":
            ET.SubElement(
                c,
                "failure" if r["status"] == "FAIL" else "error",
                message=r["reason"] or r["status"],
            )
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def bound_files(root):
    return {
        p.relative_to(root).as_posix(): sha(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "freeze.json"
    }


def verify_freeze(config):
    lock = read(config / "freeze.json")
    if bound_files(config) != lock["files"]:
        raise ValueError("fixture/contract/check version mismatch")
    for name, value in lock["modules"].items():
        if sha(Path(__file__).with_name(name)) != value:
            raise ValueError("frozen adapter changed: " + name)
    return lock


def revalidate(a):
    from hermes_skilleval._maintenance.check import check, identity
    from hermes_skilleval.repository_profile import profile_for

    lock = verify_freeze(a.config)
    inv = inventory(a.legacy, a.tasks, a.runs)
    if inv != read(a.config / "inventory.json"):
        raise ValueError("inventory changed after freeze")
    if identity(lock["image"]) != lock["image"]:
        raise ValueError("image mismatch")
    selected = [r for r in inv["rows"] if r["affected"]]
    if a.first:
        selected = selected[:1]
    a.output.mkdir(parents=True, exist_ok=True)
    for row in selected:
        dest = a.output / row["alias"]
        if dest.exists():
            completed = read(dest / "result.json")
            if (
                completed["freeze_sha256"] != sha(a.config / "freeze.json")
                or completed["patch_sha256"] != row["patch_sha256"]
            ):
                raise ValueError("completed identity mismatch")
            for name, value in completed["evidence"].items():
                if sha(dest / name) != value:
                    raise ValueError("completed evidence changed")
            if (
                digest(source_inventory(dest / "rebuilt"))
                != row["rebuilt_expected_identity"]
            ):
                raise ValueError("completed rebuilt source changed")
            print(row["alias"], "PRESERVED_COMPLETED", flush=True)
            continue
        dest.mkdir()
        start = time.monotonic()
        root = a.tasks / row["task_id"]
        cap = read(a.runs / row["run_id"] / "capture.json")
        expected = {
            k: v for k, v in cap["after"].items() if not k.startswith(".agents/")
        }
        reconstruct(
            root / "base", a.legacy / row["patch_path"], dest / "rebuilt", expected
        )
        r = {
            **row,
            "analysis_scope": SCOPE,
            "version": VERSION,
            "freeze_sha256": sha(a.config / "freeze.json"),
            "rebuilt_source_identity": digest(source_inventory(dest / "rebuilt")),
            "new_repair_agent_calls": 0,
            "new_routing_model_forwards": 0,
            "training_and_calibration_runs": 0,
        }
        task = read(root / "task.json")
        replay = {}
        profile = profile_for(task)
        if profile.image != lock["image"]:
            raise ValueError("legacy profile image differs from frozen image")
        for kind in ("target", "regression"):
            c = check(
                dest / "rebuilt",
                root / "trusted",
                dest / ("legacy-" + kind),
                task[kind + "_selector"],
                test_file=task["trusted_test_file"],
                profile=profile,
                image=lock["image"],
            )
            replay[kind] = {
                k: c[k]
                for k in (
                    "valid",
                    "passed",
                    "cases",
                    "image_id",
                    "returncode",
                    "identity",
                )
            }
        r["legacy_replayed"] = replay
        r["legacy_reproduction"] = (
            "MATCHED"
            if all(
                replay[k]["valid"] and replay[k]["passed"] == row["legacy_" + k]
                for k in replay
            )
            else "LEGACY_REPRODUCTION_MISMATCH"
        )
        r["obligations"] = behavior(
            dest / "rebuilt", row["task_id"], lock["image"], a.config, dest / "behavior"
        )
        if (
            digest(source_inventory(dest / "rebuilt"))
            != row["rebuilt_expected_identity"]
        ):
            raise ValueError("candidate source changed during execution")
        r["seconds"] = time.monotonic() - start
        junit(dest / "behavior.xml", r["obligations"])
        r["evidence"] = {
            p.relative_to(dest).as_posix(): sha(p)
            for p in safe_files(dest)
            if p.is_file() and not p.is_relative_to(dest / "rebuilt")
        }
        write(dest / "result.json", r)
        print(
            row["alias"],
            r["legacy_reproduction"],
            {k: v["status"] for k, v in r["obligations"].items()},
            flush=True,
        )


def publish(executions, output):
    """Copy only scoped process observations; retain all candidate rows."""
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for dest in sorted(executions.glob("candidate-*")):
        r = read(dest / "result.json")
        for name, value in r["evidence"].items():
            if sha(dest / name) != value:
                raise ValueError("private evidence changed")
        public = output / dest.name
        if public.exists():
            raise ValueError("public result already exists")
        safe_files(dest / "behavior")
        shutil.copytree(dest / "behavior", public / "behavior", symlinks=True)
        shutil.copyfile(dest / "behavior.xml", public / "behavior.xml")
        for kind in ("target", "regression"):
            shutil.copyfile(
                dest / ("legacy-" + kind) / "junit.xml",
                public / ("legacy-" + kind + ".xml"),
            )
        r.pop("evidence")
        results.append(r)
    write(output / "runs.json", results)
    write(
        output / "evidence-index.json",
        {
            "files": {
                p.relative_to(output).as_posix(): sha(p)
                for p in sorted(output.rglob("*"))
                if p.is_file() and p.name != "evidence-index.json"
            }
        },
    )


def xml_cases(path):
    cases = []
    for c in ET.parse(path).iter("testcase"):
        cases.append(
            {
                "id": c.attrib["classname"] + "::" + c.attrib["name"],
                "outcome": "error"
                if c.find("error") is not None
                else "failed"
                if c.find("failure") is not None
                else "skipped"
                if c.find("skipped") is not None
                else "passed",
            }
        )
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("empty JUnit or duplicate test IDs")
    return cases


def validate_process(process, mode, argv):
    if (
        process["entry"] != mode
        or process["argv"] != argv
        or process["source_mount"] != "/input"
        or process["cleanup_confirmed"] is not True
    ):
        raise ValueError("entry/argv/source/cleanup mismatch")


def validate_legacy(process, image, package):
    identity = process["identity"]
    cli_source = (
        "/input/"
        + package
        + ("/utilities/in2csv.py" if package == "csvkit" else "/cli.py")
    )
    if (
        process["image_id"] != image
        or identity["source"] != {package: "/input/" + package}
        or identity["candidate_root_on_sys_path"]
        or identity["cli_source"] != cli_source
    ):
        raise ValueError("legacy runtime identity mismatch")
    if (
        process["returncode"] not in (0, 1)
        or (process["returncode"] == 0) != process["passed"]
    ):
        raise ValueError("legacy process returncode mismatch")


def records(legacy, config, output):
    lock = verify_freeze(config)
    old = legacy_records(legacy)
    inv = read(config / "inventory.json")
    if sha(legacy / "evidence-index.json") != inv["legacy_index_sha256"]:
        raise ValueError("legacy identity changed")
    index = read(output / "evidence-index.json")
    if "runs.json" not in index["files"]:
        raise ValueError("unbound run records")
    for name, value in index["files"].items():
        p = output / name
        if not p.resolve().is_relative_to(output.resolve()) or sha(p) != value:
            raise ValueError("revalidation evidence mismatch")
    results = read(output / "runs.json")
    expected = {r["run_id"]: r for r in inv["rows"] if r["affected"]}
    if len(results) != 16 or {r["run_id"] for r in results} != set(expected):
        raise ValueError("incomplete/duplicate revalidation matrix")
    transitions = {}
    for r in results:
        row = expected[r["run_id"]]
        if any(r[k] != v for k, v in row.items()) or r["freeze_sha256"] != sha(
            config / "freeze.json"
        ):
            raise ValueError("run identity mismatch")
        if r["rebuilt_source_identity"] != row["rebuilt_expected_identity"]:
            raise ValueError("rebuild identity mismatch")
        if (
            r["analysis_scope"] != SCOPE
            or r["version"] != VERSION
            or any(
                r[k] != 0
                for k in (
                    "new_repair_agent_calls",
                    "new_routing_model_forwards",
                    "training_and_calibration_runs",
                )
            )
        ):
            raise ValueError("execution scope/counter mismatch")
        root = output / r["alias"]
        safe_files(root)
        for kind in ("target", "regression"):
            path = root / ("legacy-" + kind + ".xml")
            if path.relative_to(output).as_posix() not in index["files"]:
                raise ValueError("unbound legacy JUnit")
            cases = xml_cases(path)
            if cases != r["legacy_replayed"][kind]["cases"]:
                raise ValueError("legacy JUnit mismatch")
            validate_legacy(
                r["legacy_replayed"][kind],
                lock["image"],
                "csvkit" if r["task_id"] == TASKS[0] else "sqlite_utils",
            )
            original = xml_cases(legacy / "checks" / r["run_id"] / (kind + ".xml"))
            if sorted(c["id"] for c in cases) != sorted(c["id"] for c in original):
                raise ValueError("legacy test identity mismatch")
            passed = all(c["outcome"] == "passed" for c in cases)
            valid = all(c["outcome"] not in ("error", "skipped") for c in cases)
            if (
                passed != r["legacy_replayed"][kind]["passed"]
                or valid != r["legacy_replayed"][kind]["valid"]
            ):
                raise ValueError("legacy interpretation mismatch")
        wanted_keys = (
            {
                "csv_original_fixture_content",
                "csv_multisheet_content",
                "csv_file_input_regression",
                "csv_multisheet_file_regression",
            }
            if r["task_id"] == TASKS[0]
            else {
                m + "_" + k
                for m in ("package", "submodule", "console")
                for k in ("help", "function")
            }
        )
        if set(r["obligations"]) != wanted_keys:
            raise ValueError("obligation coverage mismatch")
        for key, v in r["obligations"].items():
            work = root / "behavior" / key
            for path in work.rglob("*"):
                if (
                    path.is_file()
                    and path.relative_to(output).as_posix() not in index["files"]
                ):
                    raise ValueError("unbound raw observation")
            process = read(work / "process.json")
            if (
                process != v["process"]
                or process["stdout"] != (work / "stdout.txt").read_text()
                or process["stderr"] != (work / "stderr.txt").read_text()
            ):
                raise ValueError("process observation mismatch")
            expected_mode = "csv" if key.startswith("csv_") else key.split("_")[0]
            expected_argv = (
                (
                    ["-f", "xlsx", "--write-sheets", "-"]
                    if "content" in key
                    else ["-f", "xlsx", "/fixture"]
                )
                if expected_mode == "csv"
                else (["--help"] if key.endswith("_help") else ["tables", "/fixture"])
            )
            validate_process(process, expected_mode, expected_argv)
            if key.startswith("csv_"):
                expected_matrix = MULTI if "multisheet" in key else ORIGINAL
                verdict = judge_csv(
                    process["returncode"],
                    process["stdout"],
                    work / "files",
                    expected_matrix,
                    export="content" in key,
                )
                if process["returncode"] is None:
                    verdict = {"status": "UNKNOWN", "reason": "TIMEOUT"}
            else:
                verdict = judge_entry(
                    process["returncode"], process["stdout"], key.split("_")[1]
                )
            if any(v[k] != value for k, value in verdict.items()):
                raise ValueError("derived verdict differs")
            table = transitions.setdefault(r["task_id"], {}).setdefault(key, Counter())
            table[
                ("PASS" if row["legacy_target"] else "FAIL") + "->" + verdict["status"]
            ] += 1
        matched = all(
            r["legacy_replayed"][k]["valid"]
            and r["legacy_replayed"][k]["passed"] == row["legacy_" + k]
            for k in ("target", "regression")
        )
        if r["legacy_reproduction"] != (
            "MATCHED" if matched else "LEGACY_REPRODUCTION_MISMATCH"
        ):
            raise ValueError("legacy reproduction classification mismatch")
        if (root / "behavior.xml").relative_to(output).as_posix() not in index["files"]:
            raise ValueError("unbound behavior JUnit")
        cases = xml_cases(root / "behavior.xml")
        observed = {c["id"].split("::")[1]: c["outcome"] for c in cases}
        if observed != {
            k: {"PASS": "passed", "FAIL": "failed", "UNKNOWN": "error"}[v["status"]]
            for k, v in r["obligations"].items()
        }:
            raise ValueError("behavior JUnit mismatch")
    return dict(
        analysis_scope=SCOPE,
        legacy_counts=old["counts"],
        candidate_revalidation="COMPLETED_16_OF_16",
        transitions=transitions,
        legacy_results="PRESERVED",
        new_repair_agent_calls=0,
        new_routing_model_forwards=0,
        training_and_calibration_runs=0,
        utility_claim="NO_NEW_INDEPENDENT_GAIN_CLAIM",
        deployment_recommendation="KEEP_NATIVE",
        support_certification="NOT_CLAIMED",
        image=lock["image"],
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=[
            "inventory",
            "validate",
            "revalidate",
            "records",
            "summarize",
            "publish",
        ],
    )
    p.add_argument("--legacy", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--tasks", type=Path)
    p.add_argument("--runs", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--first",
        action="store_true",
        help="Installed smoke: stable first affected alias only",
    )
    a = p.parse_args(argv)
    if a.action == "inventory":
        write(a.output, inventory(a.legacy, a.tasks, a.runs))
    elif a.action == "revalidate":
        revalidate(a)
    elif a.action == "publish":
        publish(a.runs, a.output)
    elif a.action == "validate":
        if a.tasks:
            from .acceptance_controls import validate

            image = read(a.legacy / "environment.json")["image"]
            validate(a.tasks, a.config, a.output, image)
        else:
            verify_freeze(a.config)
            print("FROZEN_INPUTS_VERIFIED")
    else:
        print(json.dumps(records(a.legacy, a.config, a.output), indent=2))


if __name__ == "__main__":
    main()
