"""Materialize the next registered SQLite training fixes from public source tests."""

import argparse
import ast
import io
import json
from pathlib import Path
import tarfile

from prepare_pilot import git, extract_functions
from hermes_skilleval.intervention.functional_outcomes import load_objective
from hermes_skilleval.repository_profile import SQLITE_UTILS
from hermes_skilleval.intervention.session import IMAGE

CONTRACTS = {
    "75ba588": (
        "tests/test_transform.py",
        [
            "test_transform_with_unique_constraint_implicit_index",
            "test_transform_preserves_composite_unique_constraint",
            "test_transform_preserves_column_unique_collation",
            "test_transform_drops_entire_composite_unique_constraint",
        ],
        "Make table.transform() preserve column and composite UNIQUE constraints, their conflict behavior and collation through column renames/type changes. Existing rows must survive. Case-insensitive constraints must still reject conflicting values; ON CONFLICT IGNORE must still ignore duplicates. Dropping a member of a composite constraint removes that whole constraint so remaining-column duplicates can be inserted. Preserve ordinary transforms.",
    ),
    "be27a96": (
        "tests/test_foreign_keys.py",
        [
            "test_foreign_key_captures_on_delete_and_on_update",
            "test_foreign_key_on_delete_defaults_to_no_action",
            "test_create_table_foreign_key_with_on_delete",
            "test_transform_preserves_on_delete_cascade",
            "test_transform_preserves_compound_foreign_key_on_delete",
        ],
        "Preserve ON DELETE and ON UPDATE foreign-key actions through introspection, table creation and transform(), including compound foreign keys. ForeignKey should expose on_delete/on_update, defaulting to NO ACTION, and accept them at construction. Transformed schemas must retain the original referential behavior and data. Preserve ordinary foreign keys.",
    ),
    "d9a0fd2": (
        "tests/test_query.py",
        ["test_query_preserves_error_from_transaction_destroying_trigger"],
        "Fix error handling in db.query() and atomic() when a RAISE(ROLLBACK) trigger or INSERT OR ROLLBACK destroys the transaction/savepoints. Preserve the original sqlite3.IntegrityError instead of masking it with a cleanup OperationalError. No partial write or phantom transaction should remain. Normal successful queries and transactions must still work.",
    ),
    "7d86118": (
        "tests/test_atomic.py",
        [
            "test_execute_failed_write_rolls_back_implicit_transaction",
            "test_execute_failed_write_preserves_explicit_transaction",
            "test_execute_failed_write_inside_atomic_preserves_block",
        ],
        "A failed db.execute() write outside an explicit transaction must not leave a phantom implicit transaction: subsequent writes should commit and survive close/reopen. Inside an explicit transaction or atomic() block, a caught write failure must preserve earlier caller work and keep that transaction usable. Preserve normal success and constraint errors.",
    ),
    "60811e7": (
        "tests/test_create.py",
        [
            "test_insert_ignore_reports_existing_row",
            "test_pk_rowid_alias_on_rowid_table",
            "test_insert_ignore_reports_existing_row_compound_pk",
            "test_insert_ignore_reports_existing_row_list_mode",
            "test_insert_ignore_hash_id_reports_pk",
            "test_insert_ignore_unresolvable_conflict_leaves_pk_unset",
        ],
        "Restore insert/upsert primary-key reporting for rowid tables: rowid, _rowid_ and oid must be accepted as pk aliases for upsert, insert replace and insert ignore. Ignored inserts should report the existing conflicting row via last_pk/last_rowid when resolvable, including compound primary keys and list-mode inserts. Unresolvable conflicts must not report misleading identities; preserve hash-id semantics, original values under ignore and ordinary inserts.",
    ),
}


class BehaviorOnly(ast.NodeTransformer):
    def visit_Assert(self, node):
        # Upstream schema string layout is not a behavioral obligation.
        if any(
            isinstance(x, ast.Attribute) and x.attr == "schema" for x in ast.walk(node)
        ):
            return None
        return node


def main():
    p = argparse.ArgumentParser()
    for key in ("pool", "objective", "upstreams", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    load_objective(a.objective)
    a.output.mkdir(parents=True, exist_ok=False)
    rows = [
        r
        for r in json.loads(a.pool.read_text())["rows"]
        if r["fix_commit"][:7] in CONTRACTS
    ]
    for row in rows:
        ref = row["fix_commit"]
        file, names, request = CONTRACTS[ref[:7]]
        repo = a.upstreams / "sqlite-utils"
        root = a.output / row["task_id"]
        root.mkdir()
        for scope, commit in [("base", row["base_commit"]), ("reference", ref)]:
            dest = root / scope
            dest.mkdir()
            with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", commit))) as tar:
                tar.extractall(dest, filter="data")
        code = extract_functions(repo, ref, file, names)
        code = ast.unparse(BehaviorOnly().visit(ast.parse(code)))
        code = (
            """import sqlite3
import pytest
from sqlite_utils import Database
from sqlite_utils.db import ForeignKey

@pytest.fixture
def fresh_db():
    db=Database(memory=True)
    yield db
    db.close()

"""
            + code
        )
        code += """

def test_regression(fresh_db):
    fresh_db['items'].insert_all([{'id':1,'value':'a'},{'id':2,'value':'b'}],pk='id')
    assert list(fresh_db['items'].rows)==[{'id':1,'value':'a'},{'id':2,'value':'b'}]
    with fresh_db.atomic():
        fresh_db.execute("update items set value='c' where id=2")
    assert fresh_db['items'].get(2)['value']=='c'
"""
        if ref.startswith("d9a0fd2"):
            code += """

def test_target_atomic_rollback(fresh_db):
    fresh_db.execute('create table t(id integer primary key)')
    fresh_db['t'].insert({'id':1})
    with pytest.raises(sqlite3.IntegrityError):
        with fresh_db.atomic():
            fresh_db.execute('insert or rollback into t values (1)')
    assert not fresh_db.conn.in_transaction
    assert list(fresh_db['t'].rows)==[{'id':1}]
"""
        trusted = root / "trusted"
        trusted.mkdir()
        (trusted / "pytest.ini").write_text("[pytest]\n")
        (trusted / "test_behavior.py").write_text(code + "\n")
        profile = SQLITE_UTILS.to_dict()
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
        meta = {
            **row,
            "profile": profile,
            "trusted_test_file": "test_behavior.py",
            "target_selector": "not test_regression",
            "regression_selector": "test_regression",
            "reference_commit": ref,
            "request_ref": row["source"],
        }
        (root / "task.json").write_text(json.dumps(meta, indent=2) + "\n")
        (root / "request.txt").write_text(request + "\n")
        row["request"] = request
        row["coverage"] = {
            "source_test_file": file,
            "source_test_functions": names,
            "adaptation": "Retain source behavioral assertions; omit literal schema formatting assertions; add normal write/transaction regression and source-supported atomic rollback control.",
            "known_omissions": "Full upstream suite not executed by hidden verifier.",
        }
    (a.output / "candidate-roster.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"prepared": len(rows), "agent_calls": 0}))


if __name__ == "__main__":
    main()
