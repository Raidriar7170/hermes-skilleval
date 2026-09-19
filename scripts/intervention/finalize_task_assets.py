"""Reference-only implementations and repaired development semantic checks.

Runs before research outcomes. References and target checks remain outside Agent
mounts. These are qualification controls, never intervention training examples.
"""

import argparse
import json
from pathlib import Path
from hermes_skilleval.repo_routing.acceptance_review import make_xlsx, MULTI
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--tasks", type=Path, required=True)
a = p.parse_args()


def edit(tid, relative, old, new):
    p = a.tasks / tid / relative
    s = p.read_text()
    if old not in s:
        raise ValueError((tid, "reference anchor missing"))
    p.write_text(s.replace(old, new, 1))


for tid, option, body in [
    (
        "sqlite-utils-issue-202",
        "fts",
        "db[kwargs['table']].enable_fts(columns,fts_version='FTS5')",
    ),
    (
        "sqlite-utils-issue-352",
        "extract",
        "\n    for column in columns:\n        db[kwargs['table']].extract([column],table=column,fk_column=column,rename={column:'value'})",
    ),
]:
    file = a.tasks / tid / "reference/sqlite_utils/cli.py"
    flag = "['-f', '--fts']" if option == "fts" else "['--extract']"
    with file.open("a") as f:
        f.write(
            "\n\n# Independent qualification reference: compose existing public operations.\n_original_insert_callback = insert.callback\n"
        )
        f.write(f"insert.params.append(click.Option({flag},multiple=True))\n")
        f.write(
            f"def _reference_insert(*args, {option}=(), **kwargs):\n    result = _original_insert_callback(*args, **kwargs)\n    columns = {option}\n    if columns:\n        from sqlite_utils import Database\n        db = Database(kwargs['path'])\n"
        )
        if option == "fts":
            f.write("        " + body + "\n")
        else:
            f.write(
                "        for column in columns:\n            db[kwargs['table']].extract([column],table=column,fk_column=column,rename={column:'value'})\n"
            )
        f.write("    return result\ninsert.callback = _reference_insert\n")

edit(
    "sqlite-utils-issue-323",
    "reference/sqlite_utils/db.py",
    "                if drop:\n                    self.transform(drop=columns)\n        return self",
    "                if drop:\n                    self.transform(drop=columns)\n            self.db.conn.create_function(fn_name, 1, None)\n        return self",
)
edit(
    "sqlite-utils-issue-323",
    "reference/sqlite_utils/db.py",
    '            fn_name = getattr(fn, "__name__", "fn")\n            if fn_name == "<lambda>":\n                fn_name = f"lambda_{abs(hash(fn))}"',
    '            import uuid\n            fn_name = "convert_" + uuid.uuid4().hex',
)

edit(
    "csvkit-issue-1268",
    "reference/csvkit/utilities/csvjoin.py",
    "            self.input_files.append(self._open_input_file(path))",
    "            stream = self._open_input_file(path)\n            if not stream.seekable():\n                from io import StringIO\n                data = stream.read()\n                stream.close()\n                stream = StringIO(data)\n            self.input_files.append(stream)",
)
for tid in ["csv-diff-issue-18", "csv-diff-issue-23", "csv-diff-issue-15"]:
    file = a.tasks / tid / "reference/csv_diff/__init__.py"
    s = file.read_text()
    if tid.endswith("-18"):
        s = s.replace(
            "next(iter(previous.values()))", "next(iter(previous.values()), {})"
        ).replace("next(iter(current.values()))", "next(iter(current.values()), {})")
    if tid.endswith("-23"):
        s = s.replace(
            "    if key:\n        keyfn = lambda r: r[key]",
            "    if isinstance(key, (tuple, list)):\n        keyfn = lambda r: tuple(r[column] for column in key)\n    elif key:\n        keyfn = lambda r: r[key]",
            1,
        )
    if tid.endswith("-15"):
        s = s.replace(
            "    if key:\n        keyfn = lambda r: r[key]",
            '    if key == "__rowid__":\n        return dict(enumerate(rows))\n    if key:\n        keyfn = lambda r: r[key]',
            1,
        )
    file.write_text(s)

# Preserve historical verdicts elsewhere; these NEW dev checks implement the
# explicitly clarified package entrypoint and actual workbook content contracts.
p = a.tasks / "sqlite-utils-issue-368/trusted/test_behavior.py"
s = p.read_text()
s += """

def test_target_function(tmp_path):
    for entry in ([sys.executable, '-m', 'sqlite_utils'], ['sqlite-utils']):
        r=candidate_run(entry + [':memory:', 'select 17 as value'],capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        assert json.loads(r.stdout)==[{'value':17}]
"""
p.write_text(s)
p = a.tasks / "csvkit-issue-1225/trusted/test_behavior.py"
s = p.read_text()
aidx = s.index("def test_target(")
s = (
    s[:aidx]
    + """
def test_target(tmp_path, monkeypatch):
    import csv
    from pathlib import Path
from hermes_skilleval.repo_routing.acceptance_review import make_xlsx, MULTI
    monkeypatch.chdir(tmp_path)
    data=Path('/trusted/dummy.xlsx').read_bytes()
    r=candidate_run(['in2csv','-f','xlsx','--write-sheets','-'],input=data,capture_output=True)
    assert r.returncode==0,r.stderr
    files=list(tmp_path.glob('*.csv'))
    assert len(files)==1
    with files[0].open(newline='') as stream:
        assert list(csv.reader(stream))==[['a','b','c'],['True','2','3']]

def test_regression(tmp_path):
    import csv,io
    r=candidate_run(['in2csv','-f','xlsx','/trusted/dummy.xlsx'],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert list(csv.reader(io.StringIO(r.stdout)))==[['a','b','c'],['True','2','3']]
"""
)
p.write_text(s)

make_xlsx(a.tasks / "csvkit-issue-1225/trusted/multisheet.xlsx")
with p.open("a") as f:
    f.write(
        "\ndef test_target_multisheet(tmp_path, monkeypatch):\n    import csv,json\n    from pathlib import Path\n    monkeypatch.chdir(tmp_path)\n    r=candidate_run(['in2csv','-f','xlsx','--write-sheets','-'],input=Path('/trusted/multisheet.xlsx').read_bytes(),capture_output=True)\n    assert r.returncode==0,r.stderr\n    matrices=[]\n    for file in tmp_path.glob('*.csv'):\n        with file.open(newline='') as stream:\n            matrices.append(list(csv.reader(stream)))\n    assert sorted(map(json.dumps,matrices))==sorted(map(json.dumps,"
        + repr(MULTI)
        + "))\n"
    )

for root in a.tasks.iterdir():
    if not (root / "task.json").exists():
        continue
    m = json.loads((root / "task.json").read_text())
    m["profile"]["image"] = "hermes-asi-executor:v1"
    m["reference_scope"] = (
        "Qualification only; source and checks never exposed to Agent or policy"
    )
    dump(root / "task.json", m)
print("reference implementations and development semantic checks prepared")
