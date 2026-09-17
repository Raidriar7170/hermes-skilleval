"""Independent oracle controls, executed before candidate revalidation."""

import csv
import shutil
import sqlite3

from .acceptance_review import (
    MULTI,
    ORIGINAL,
    TASKS,
    behavior,
    invoke,
    judge_csv,
    make_xlsx,
    sha,
    write,
)


def semantic_controls(root):
    root.mkdir(parents=True, exist_ok=False)
    results = {}
    variants = {
        "correct_alternate_names": MULTI,
        "empty_matching_prefix": [[]],
        "wrong_cell": [[["name", "value"], ["wrong", "red"]], MULTI[1]],
        "missing_row": [[MULTI[0][0], MULTI[0][1]], MULTI[1]],
        "missing_column": [[["name"], ["alpha"], ["alpha"]], MULTI[1]],
        "missing_sheet": [MULTI[0]],
        "duplicate_first": [MULTI[0], MULTI[0]],
        "no_output": [],
        "nonzero": MULTI,
        "symlink": MULTI,
    }
    for name, matrices in variants.items():
        out = root / name
        out.mkdir()
        for i, m in enumerate(matrices):
            with (
                out
                / (
                    f"allowed_other_{i}.csv"
                    if name == "correct_alternate_names"
                    else f"stdin_{i}.csv"
                )
            ).open("w", newline="") as f:
                csv.writer(f).writerows(m)
        if name == "symlink":
            (out / "stdin_0.csv").unlink()
            (out / "stdin_0.csv").symlink_to(
                root / "correct_alternate_names" / "allowed_other_0.csv"
            )
        import io

        stdout = io.StringIO()
        csv.writer(stdout).writerows(MULTI[0])
        verdict = judge_csv(
            1 if name == "nonzero" else 0, stdout.getvalue(), out, MULTI
        )
        expected = "PASS" if name == "correct_alternate_names" else "FAIL"
        if verdict["status"] != expected:
            raise ValueError("CSV control failed: " + name)
        results[name] = dict(expected=expected, observed=verdict["status"])
    return results


def validate(tasks, config, output, image):
    output.mkdir(parents=True, exist_ok=False)
    results = {
        "csv_controls": semantic_controls(output / "synthetic-csv"),
        "entry_controls": {},
        "real_controls": {},
    }
    # Actual independent Python packages, not mocked runpy responses.
    for mode in ("package_only", "submodule_only", "help_only", "console_broken"):
        source = output / mode / "source"
        pkg = source / "sqlite_utils"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        cli = "import sys,json\ndef cli():\n print('Usage: control' if '--help' in sys.argv else json.dumps([{'table':'acceptance_items'}]))\n"
        if mode == "help_only":
            cli = "def cli():\n print('Usage: control')\n"
        if mode == "console_broken":
            cli = "def cli():\n raise RuntimeError('console regression')\n"
        if mode == "submodule_only":
            cli += "\nif __name__=='__main__': cli()\n"
        (pkg / "cli.py").write_text(cli)
        if mode in ("package_only", "help_only"):
            (pkg / "__main__.py").write_text("from .cli import cli\ncli()\n")
        r = behavior(source, TASKS[1], image, config, output / mode / "behavior")
        expected = {
            "package_only": {
                "package_help": "PASS",
                "package_function": "PASS",
                "submodule_help": "FAIL",
                "submodule_function": "FAIL",
                "console_help": "PASS",
                "console_function": "PASS",
            },
            "submodule_only": {
                "package_help": "FAIL",
                "package_function": "FAIL",
                "submodule_help": "PASS",
                "submodule_function": "PASS",
                "console_help": "PASS",
                "console_function": "PASS",
            },
            "help_only": {
                "package_help": "PASS",
                "package_function": "FAIL",
                "submodule_help": "FAIL",
                "submodule_function": "FAIL",
                "console_help": "PASS",
                "console_function": "FAIL",
            },
            "console_broken": dict.fromkeys(
                [
                    "package_help",
                    "package_function",
                    "submodule_help",
                    "submodule_function",
                    "console_help",
                    "console_function",
                ],
                "FAIL",
            ),
        }[mode]
        observed = {k: v["status"] for k, v in r.items()}
        if observed != expected:
            raise ValueError("dispatch control failed: " + mode + str(observed))
        results["entry_controls"][mode] = {
            "expected": expected,
            "observed": observed,
            "evidence": r,
        }
    # A real timed-out process must remain UNKNOWN, not zero-exit success.
    source = output / "timeout" / "source"
    pkg = source / "sqlite_utils"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text("import time\ntime.sleep(10)\n")
    process, _ = invoke(
        source,
        image,
        "package",
        ["--help"],
        output / "timeout" / "execution",
        timeout=1,
    )
    if process["returncode"] is not None:
        raise ValueError("timeout control failed")
    results["timeout_control"] = process
    for tid in TASKS:
        results["real_controls"][tid] = {}
        for variant in ("base", "reference"):
            r = behavior(
                tasks / tid / variant,
                tid,
                image,
                config,
                output / "real" / tid / variant,
            )
            results["real_controls"][tid][variant] = r
    write(output / "validation.json", results)
    return results


def fixtures(tasks, config):
    config.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tasks / TASKS[0] / "trusted/dummy.xlsx", config / "dummy.xlsx")
    make_xlsx(config / "multisheet.xlsx")
    with sqlite3.connect(config / "known.db") as db:
        db.execute("create table acceptance_items (name text)")
        db.execute("insert into acceptance_items values ('alpha')")
    write(
        config / "fixtures.json",
        dict(
            generator="stdlib OOXML deterministic ZIP v1",
            original_expected=ORIGINAL,
            multisheet_expected=MULTI,
            original_source="fixed trusted/dummy.xlsx; Sheet1 A1:C2, sharedStrings a/b/c and numeric 1/2/3",
            normalization="CSV parse only; no strip, reorder, coercion or deduplication. Files matched by complete matrix multiset.",
            files={
                p.name: sha(p)
                for p in (
                    config / "dummy.xlsx",
                    config / "multisheet.xlsx",
                    config / "known.db",
                )
            },
        ),
    )
