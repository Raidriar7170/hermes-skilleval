"""Six original candidates only; no regeneration and no research Agent calls."""

import argparse
import ast
import json
from pathlib import Path
import shutil
from hermes_skilleval.intervention.rollouts import accept
from hermes_skilleval.intervention.session import dump

EXTRA = """
def _posthoc_snapshot(db):
    return tuple(db.conn.iterdump())

def _posthoc_observe(db, operation):
    before = _posthoc_snapshot(db)
    error = None
    try:
        operation()
    except Exception as exc:
        error = exc
    return error, before == _posthoc_snapshot(db)

@pytest.mark.parametrize("observation", ["rejection", "preservation"])
def test_posthoc_strict_any_observations(fresh_db, observation):
    if not fresh_db.supports_strict:
        pytest.skip("SQLite version lacks strict tables")
    fresh_db.execute("create table items (data any) strict")
    fresh_db.execute("insert into items values (?)", ("000123",))
    fresh_db.execute("create table data_values (id integer primary key, data any)")
    error, preserved = _posthoc_observe(fresh_db, lambda: fresh_db["items"].extract("data", table="data_values"))
    if observation == "rejection":
        assert isinstance(error, InvalidColumns)
    else:
        assert preserved

@pytest.mark.parametrize("index_sql", ["create index idx on t(name) where id > 0", "create index idx on t(lower(name))"])
@pytest.mark.parametrize("observation", ["rejection", "preservation"])
def test_posthoc_index_observations(fresh_db, index_sql, observation):
    table = fresh_db["t"]
    table.insert({"id": 1, "name": "keep"}, pk="id")
    fresh_db.execute(index_sql)
    error, preserved = _posthoc_observe(fresh_db, lambda: table.transform(rename={"name": "full_name"}))
    if observation == "rejection":
        assert isinstance(error, TransformError)
    else:
        assert preserved

@pytest.mark.parametrize("operation", ["insert", "extract", "view"])
@pytest.mark.parametrize("observation", ["rejection", "preservation"])
def test_posthoc_cli_observations(db_path, operation, observation):
    db = Database(db_path)
    db["t"].insert({"id": 1, "name": "keep"}, pk="id")
    db.create_view("v", "select * from t")
    before = _posthoc_snapshot(db)
    args = ["insert", db_path, "t", "-", "--pk", "missing"] if operation == "insert" else ["extract", db_path, "v" if operation == "view" else "t", "name" if operation == "view" else "missing"]
    result = CliRunner().invoke(cli.cli, args, input='{"id":2}')
    preserved = before == _posthoc_snapshot(db)
    if observation == "rejection":
        assert result.exit_code != 0
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert result.output.startswith("Error:")
    else:
        assert preserved
"""


def revised(text, short):
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "startswith"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value).startswith("Error: Invalid")
            ):
                node.args[0] = ast.Constant("Error:")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "raises":
                node.keywords = [k for k in node.keywords if k.arg != "match"]
    extra = ast.parse(EXTRA)
    allowed = {
        "548a886": "test_posthoc_cli_observations",
        "fcfccea": "test_posthoc_strict_any_observations",
        "57192ef": "test_posthoc_index_observations",
    }[short]
    tree.body.extend(
        n
        for n in extra.body
        if isinstance(n, ast.FunctionDef)
        and (n.name.startswith("_posthoc") or n.name == allowed)
    )
    return ast.unparse(tree) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--old", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    rows = []
    for short in ["548a886", "fcfccea", "57192ef"]:
        tid = "sqlite-utils-diagnostic-" + short
        original = a.old / "tasks-frozen" / tid
        if not original.exists():
            rows.append({"task_id": tid, "status": "ASSETS_UNAVAILABLE"})
            continue
        task = a.output / "tasks" / tid
        if not task.exists():
            task.mkdir(parents=True)
            (task / "base").symlink_to(
                (original / "base").resolve(), target_is_directory=True
            )
            shutil.copyfile(original / "task.json", task / "task.json")
            shutil.copytree(original / "trusted", task / "trusted")
            f = task / "trusted/test_behavior.py"
            f.write_text(revised(f.read_text(), short))
        for repeat in (1, 2):
            run = a.old / "native-v1" / tid / f"r{repeat}"
            out = a.output / "checks" / tid / f"r{repeat}"
            if not (run / "source").exists():
                rows.append(
                    {"task_id": tid, "repeat": repeat, "status": "ASSETS_UNAVAILABLE"}
                )
                continue
            checks = (
                json.loads((out / "acceptance.json").read_text())["checks"]
                if (out / "acceptance.json").exists()
                else accept(task, run, out)
            )
            rows.append(
                {
                    "task_id": tid,
                    "repeat": repeat,
                    "status": "POSTHOC_ACCEPTANCE_ONLY",
                    "checks": checks,
                }
            )
            dump(
                a.output / "results.json",
                {
                    "rows": rows,
                    "new_agent_calls": 0,
                    "claim": "No skill rescue; original patches only",
                },
            )
            print(
                tid,
                repeat,
                {k: (v.get("valid"), v.get("passed")) for k, v in checks.items()},
                flush=True,
            )


if __name__ == "__main__":
    main()
