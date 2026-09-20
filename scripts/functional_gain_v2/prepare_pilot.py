"""Prepare first four preregistered mechanisms; no Agent or outcome selection."""

import argparse
import ast
import io
import json
from pathlib import Path
import subprocess
import tarfile

from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.repository_profile import SQLITE_UTILS, CSVKIT, RepositoryProfile
from hermes_skilleval.intervention.session import IMAGE

REQUESTS = {
    "f66ddcb": """Fix table.transform() inside an existing transaction when foreign keys are enabled: transforming a table referenced by destructive ON DELETE actions (CASCADE, SET NULL, SET DEFAULT) must refuse with TransactionError before changing schema or losing referencing rows. The error should identify the offending table/action. Include self-referential foreign keys. Preserve normal transforms for non-destructive inbound keys, child-only outbound keys, and foreign_keys disabled. Preserve existing data and rowids for ordinary transforms.""",
    "8572d1e": """Fix repeated extract() into a shared lookup table: NULL-containing lookup values currently produce duplicate/orphan rows even when the same value combination already exists. Repeated extraction must reuse the existing lookup record and both source tables must reference it. Preserve non-NULL deduplication and ordinary extraction behavior, including missing values.""",
    "3f9d8b6": """Fix csvjoin --right when the join columns have different positions or different names in the two input files. The --columns list is in input-file order. Preserve all right-side rows, attach matching left data by the specified keys, leave unmatched left values empty, and do not match unrelated columns. Keep ordinary inner/left joins working. The existing CLI options and default column output order remain compatible.""",
    "9574395": """Fix csv-diff when CSV column names contain a dot. Both compare() results and CLI --json should report changed values under the original column name, without splitting that name into a path or crashing. Cover multiple dotted names and unchanged dotted fields; preserve ordinary key matching, added/removed records and columns.""",
}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def extract_functions(repo, ref, file, names):
    text = git(repo, "show", ref + ":" + file).decode()
    lines = text.splitlines(keepends=True)
    result = []
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            result.append("".join(lines[start - 1 : node.end_lineno]))
    if len(result) != len(names):
        raise ValueError("missing source test")
    return "\n\n".join(result)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pool", type=Path, required=True)
    p.add_argument("--objective", type=Path, required=True)
    p.add_argument("--upstreams", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    load_objective(a.objective)
    a.output.mkdir(parents=True, exist_ok=False)
    rows = json.loads(a.pool.read_text())["rows"][:4]
    for row in rows:
        repo = a.upstreams / row["repository"].split("/")[-1]
        ref = row["fix_commit"]
        short = ref[:7]
        root = a.output / row["task_id"]
        root.mkdir()
        for name, commit in [("base", row["base_commit"]), ("reference", ref)]:
            dest = root / name
            dest.mkdir()
            with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", commit))) as tar:
                tar.extractall(dest, filter="data")
        trusted = root / "trusted"
        trusted.mkdir()
        (trusted / "pytest.ini").write_text("[pytest]\n")
        if row["repository"].endswith("sqlite-utils"):
            profile = SQLITE_UTILS.to_dict()
            code = "import pytest\nfrom sqlite_utils import Database\nfrom sqlite_utils.db import TransactionError\n\n@pytest.fixture\ndef fresh_db():\n    db=Database(memory=True)\n    yield db\n    db.close()\n\n"
            if short == "f66ddcb":
                names = [
                    "test_transform_in_transaction_" + s
                    for s in [
                        "refuses_destructive_on_delete",
                        "refuses_self_referential_cascade",
                        "allowed_with_no_action_foreign_key",
                        "allowed_for_child_table",
                        "allowed_with_foreign_keys_off",
                    ]
                ]
                code += extract_functions(repo, ref, "tests/test_transform.py", names)
                code += '\n\ndef test_regression(fresh_db):\n    fresh_db["items"].insert_all([{"name":"a"},{"name":"b"}])\n    before=list(fresh_db.query("select rowid,name from items"))\n    fresh_db["items"].transform(rename={"name":"label"})\n    assert list(fresh_db.query("select rowid,label as name from items"))==before\n'
                target = "test_transform_in_transaction"
            else:
                names = [
                    "test_extract_repeated_into_shared_lookup_with_nulls",
                    "test_extract_repeated_into_shared_lookup_no_nulls",
                    "test_extract_null_values_existing_lookup_table_with_null_row",
                ]
                code += extract_functions(repo, ref, "tests/test_extract.py", names)
                code += '\n\ndef test_regression(fresh_db):\n    fresh_db["items"].insert_all([{"id":1,"kind":"a"},{"id":2,"kind":"b"}],pk="id")\n    fresh_db["items"].extract(["kind"],table="kinds")\n    assert fresh_db["items"].count==2\n    assert {r["kind"] for r in fresh_db["kinds"].rows}=={"a","b"}\n'
                target = "test_extract"
        elif row["repository"].endswith("csvkit"):
            profile = CSVKIT.to_dict()
            code = """import csv
import io
import pytest
from csvkit.utilities.csvjoin import CSVJoin

def joined(tmp_path,columns,mode):
    left=tmp_path/'left.csv';right=tmp_path/'right.csv'
    left.write_text('left_id,left_value,decoy\\na,A,z\\nc,C,a\\n')
    right.write_text('right_value,decoy,right_id\\nR1,c,a\\nR2,a,b\\n')
    out=io.StringIO()
    CSVJoin(['--no-inference','-y','0','-c',columns,mode,str(left),str(right)],output_file=out).run()
    return list(csv.DictReader(io.StringIO(out.getvalue())))

@pytest.mark.parametrize('columns',['1,3','left_id,right_id'])
def test_target(tmp_path,columns):
    rows=joined(tmp_path,columns,'--right')
    assert len(rows)==2
    by={r['right_id']:r for r in rows}
    assert by['a']['left_value']=='A'
    assert by['b']['left_value']==''
    assert by['a']['right_value']=='R1' and by['b']['right_value']=='R2'

def test_regression(tmp_path):
    rows=joined(tmp_path,'left_id,right_id','--left')
    assert len(rows)==2
    by={r['left_id']:r for r in rows}
    assert by['a']['right_value']=='R1' and by['c']['right_value']==''
"""
            target = "test_target"
        else:
            profile = RepositoryProfile(
                "simonw/csv-diff",
                {"csv_diff": "."},
                "csv_diff.cli",
                "cli",
                "csv-diff",
                IMAGE,
                ("csv_diff", "tests"),
            ).to_dict()
            code = """import io
import json
import pytest
from click.testing import CliRunner
from csv_diff import compare,load_csv
from csv_diff.cli import cli

@pytest.mark.parametrize('field',['foo.bar','a.b.c'])
def test_target(tmp_path,field):
    before='id,'+field+',same.dot\\n1,old,keep\\n'
    after='id,'+field+',same.dot\\n1,new,keep\\n'
    expected={'added':[],'removed':[],'changed':[{'key':'1','changes':{field:['old','new']}}],'columns_added':[],'columns_removed':[]}
    assert compare(load_csv(io.StringIO(before),key='id'),load_csv(io.StringIO(after),key='id'))==expected
    a=tmp_path/'a.csv';b=tmp_path/'b.csv';a.write_text(before);b.write_text(after)
    result=CliRunner().invoke(cli,[str(a),str(b),'--key','id','--json'])
    assert result.exit_code==0,result.output
    assert json.loads(result.output)==expected

def test_regression():
    a=load_csv(io.StringIO('id,name\\n1,a\\n2,b\\n'),key='id')
    b=load_csv(io.StringIO('id,name\\n1,a\\n3,c\\n'),key='id')
    diff=compare(a,b)
    assert diff['changed']==[]
    assert diff['added']==[{'id':'3','name':'c'}]
    assert diff['removed']==[{'id':'2','name':'b'}]
"""
            target = "test_target"
        profile["image"] = IMAGE
        profile["file_policy"] = {
            "version": "operations-v1",
            "rules": [
                {
                    "path": r,
                    "operations": ["add", "modify", "delete"],
                    "max_bytes": 1000000,
                }
                for r in profile["writable_roots"]
            ],
        }
        (trusted / "test_behavior.py").write_text(code)
        (root / "request.txt").write_text(REQUESTS[short] + "\n")
        meta = {
            **row,
            "profile": profile,
            "trusted_test_file": "test_behavior.py",
            "target_selector": target,
            "regression_selector": "test_regression",
            "reference_commit": ref,
            "request_ref": row["source"],
        }
        (root / "task.json").write_text(json.dumps(meta, indent=2) + "\n")
        row["request"] = REQUESTS[short]
        row["coverage"] = {
            "source": row["source"],
            "target_selector": target,
            "protected_regression": "test_regression",
            "known_omissions": "Not the complete upstream suite; source-grounded scoped behavior only",
        }
    (a.output / "candidate-roster.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"prepared": len(rows), "agent_calls": 0}))


if __name__ == "__main__":
    main()
