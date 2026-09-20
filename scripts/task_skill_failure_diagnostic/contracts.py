"""Public behavioral obligations and independent acceptance preparation only.

Never mount this module or reference tests into an Agent or selection context.
"""

REQUESTS = {
    "548a886": "Handle invalid-column errors cleanly in sqlite-utils CLI insert/upsert --pk and extract. For a nonexistent primary-key column on an existing table, nonexistent extract column, or extract on a view, return a normal nonzero Click Error message instead of a raw Python exception. Do not alter existing rows on these errors. Keep successful insert and extract working.",
    "fcfccea": "Support SQLite ANY types consistently across Python and CLI strict-table operations. Expose sqlite_utils.ANY and recognize ANY/any type names for create/add-column/transform and CLI create-table/insert/upsert --type. Strict ANY must preserve integer, real, text including leading zeroes, blobs and NULL without coercion. Introspection, transform and extract must preserve the type and strictness. Extracting strict ANY into an existing non-strict lookup must reject before data loss. Explicitly converting to non-strict follows SQLite ordinary ANY numeric affinity. Preserve existing non-ANY operations.",
    "80437fd": "Fix csvkit column selection with --ignore-unknown-columns: unknown names containing a hyphen or colon should be skipped like other unknown names, rather than treated as invalid ranges. Real existing names containing these characters and valid numeric ranges must still resolve normally. Without the flag invalid ranges must raise ColumnIdentifierError with the offending identifier in the message (including excluded-column ranges). Keep ordinary column selection and exclusions compatible.",
    "19810a3": "Add csvkit --add-bom for UTF-8 CSV output for Excel compatibility. When requested, prefix output with a UTF-8 BOM while preserving all CSV content and non-ASCII text; default output must stay unchanged. The common option should work for ordinary CSV-output utilities, including in2csv. csvpy and sql2csv, which override these common options, must not advertise this option. Preserve quoting and the ordinary conversion path.",
    "2b52b5e": "Preserve AUTOINCREMENT and its sequence high-water mark through sqlite-utils table.transform(), including column renames. Deleted high IDs must not be reused after a transform, surviving rows must be retained, and ordinary non-AUTOINCREMENT table transforms should keep working. Validate actual subsequent insertion behavior, not only schema spelling.",
    "57192ef": "Preserve ordinary indexes when table.transform(rename=...) renames indexed columns. Preserve index name, uniqueness, column order, descending flags and collations, including swapped names and names shared by table/column/index. Do not cascade textual substitutions. Partial or expression indexes affected by a rename must raise TransformError before changing schema or data; dropping an indexed column without handling its index must continue to fail safely. Preserve ordinary transforms.",
    "29ca9d2": "Restore support for mixed foreign_keys lists in sqlite-utils table creation: accept ForeignKey objects, tuple forms and bare column-name strings in the same list, preserving table/column inference and actual constraints. Do not require all entries to have the same representation. Keep homogeneous forms working and reject invalid entries rather than silently dropping them.",
    "8e015d0": "Use PRIMARY KEY declaration order, not physical table column order, for sqlite-utils compound primary keys. Preserve that order in introspection, transform, and implicit compound foreign-key references, including create and add_foreign_key inference. Valid data must remain valid after transform; reversed foreign-key values must still fail, and ordinary single-column keys must keep working.",
}
# Extract whole upstream behavioral tests. Only implementation-specific SQL
# formatting assertions are replaced below by independent behavioral checks.
EXTRACT = {
    "548a886": {
        "tests/test_cli.py": [
            "test_extract_bad_column_clean_error",
            "test_extract_view_clean_error",
        ],
        "tests/test_cli_insert.py": ["test_insert_invalid_pk_clean_error"],
    },
    "fcfccea": {
        "tests/test_create.py": ["test_create_strict_with_any"],
        "tests/test_extract.py": [
            "test_extract_preserves_strict_any",
            "test_extract_strict_any_rejects_non_strict_lookup",
        ],
        "tests/test_transform.py": [
            "test_transform_preserves_any_column_in_strict_table",
            "test_transform_any_column_from_strict_to_non_strict",
        ],
        "tests/test_cli.py": [
            "test_transform_column_to_any",
            "test_create_table_strict_any",
            "test_insert_upsert_strict_any",
        ],
    },
    "57192ef": {
        "tests/test_transform.py": [
            "test_transform_recreates_renamed_index_from_metadata",
            "test_transform_rename_complex_index_errors",
        ]
    },
    "29ca9d2": {
        "tests/test_foreign_keys.py": [
            "test_create_table_mixed_foreign_keys_list",
            "test_create_table_mixed_foreign_keys_with_string",
        ]
    },
    "8e015d0": {
        "tests/test_foreign_keys.py": [
            "test_implicit_compound_foreign_key_resolves_pk_declaration_order",
            "test_transform_implicit_compound_foreign_key_stays_valid",
            "test_create_compound_foreign_key_guesses_pk_declaration_order",
            "test_add_compound_foreign_key_guesses_pk_declaration_order",
        ],
        "tests/test_introspect.py": ["test_pks_use_primary_key_declaration_order"],
    },
}
SQLITE_HEADER = """import io
import json
import sqlite3
import pytest
import sqlite_utils
from sqlite_utils import Database, cli
from sqlite_utils.db import ForeignKey, InvalidColumns, TransformError
from click.testing import CliRunner
# Base may lack the new public constant; tests must fail behaviorally, not
# fail collection. A distinct unsupported type yields a valid failed test.
ANY = getattr(sqlite_utils, 'ANY', object())
@pytest.fixture
def fresh_db():
    db=Database(memory=True)
    yield db
    db.close()
@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path/'test.db')
"""
SQLITE_REGRESSION = """
def test_regression(fresh_db):
    t=fresh_db['ordinary'];t.insert({'id':1,'value':'keep'},pk='id')
    assert t.get(1)=={'id':1,'value':'keep'}
    t.transform(rename={'value':'label'})
    assert t.get(1)=={'id':1,'label':'keep'}
    with pytest.raises(sqlite3.IntegrityError):t.insert({'id':1,'label':'bad'})
    assert t.get(1)['label']=='keep'
"""
EXTRA = {
    "548a886": """
def test_errors_preserve_rows(db_path):
    db=Database(db_path);db['t'].insert({'id':1,'name':'keep'},pk='id');db.close()
    for args, data in [(['insert',db_path,'t','-','--pk','missing'],'{"id":2}'),(['extract',db_path,'t','missing'],None)]:
        result=CliRunner().invoke(cli.cli,args,input=data)
        assert result.exit_code==1 and result.output.startswith('Error:')
        check=Database(db_path);assert list(check['t'].rows)==[{'id':1,'name':'keep'}];check.close()
""",
    "2b52b5e": """
@pytest.mark.parametrize('deleted', [2, 41])
def test_sequence_survives_transform(fresh_db,deleted):
    fresh_db.execute('CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)')
    t=fresh_db['entries'];t.insert({'id':1,'value':'one'});t.insert({'id':deleted,'value':'gone'});t.delete(deleted)
    t.transform(rename={'value':'label'});t.insert({'label':'next'})
    assert list(t.rows)==[{'id':1,'label':'one'},{'id':deleted+1,'label':'next'}]
""",
    "57192ef": """
@pytest.mark.parametrize('table_name,index_name',[('name','idx_name'),('t','name')])
def test_index_name_collision_behavior(fresh_db,table_name,index_name):
    t=fresh_db[table_name];t.insert({'id':1,'name':'keep'},pk='id');t.create_index(['name'],index_name=index_name,unique=True)
    t.transform(rename={'name':'full_name'})
    assert [(i.name,i.columns) for i in t.indexes]==[(index_name,['full_name'])]
    with pytest.raises(sqlite3.IntegrityError):t.insert({'id':2,'full_name':'keep'})
    assert list(t.rows)==[{'id':1,'full_name':'keep'}]

def test_index_drop_rejection_preserves_rows(fresh_db):
    t=fresh_db['t'];t.insert({'id':1,'name':'keep'},pk='id');t.create_index(['name'])
    with pytest.raises(TransformError):t.transform(drop=['name'])
    assert list(t.rows)==[{'id':1,'name':'keep'}]
""",
    "29ca9d2": """
def test_mixed_constraints_enforced(fresh_db):
    fresh_db.execute('pragma foreign_keys=on')
    fresh_db['authors'].insert({'id':1},pk='id');fresh_db['publishers'].insert({'id':1},pk='id')
    t=fresh_db['books'];t.create({'id':int,'author_id':int,'publisher_id':int},pk='id',foreign_keys=['author_id',('publisher_id','publishers','id')])
    t.insert({'id':1,'author_id':1,'publisher_id':1})
    with pytest.raises(sqlite3.IntegrityError):t.insert({'id':2,'author_id':999,'publisher_id':1})
    assert t.count==1
""",
    "8e015d0": """
def test_transformed_pk_order(fresh_db):
    fresh_db.execute('create table t (a text, b text, c text, primary key (b,a))')
    fresh_db['t'].insert({'a':'A','b':'B','c':'drop'})
    fresh_db['t'].transform(drop={'c'})
    assert fresh_db['t'].pks==['b','a']
    assert fresh_db['t'].get(('B','A'))=={'a':'A','b':'B'}
""",
    "80437fd": """import pytest
from csvkit.cli import parse_column_identifiers, ColumnIdentifierError
@pytest.mark.parametrize('unknown',['no-pe','no:pe','2026-09-20'])
def test_unknown_range_names(unknown):
    names=['id','known-name','value']
    assert parse_column_identifiers('id,'+unknown+',value',names,ignore_unknown_columns=True)==[0,2]
    with pytest.raises(ColumnIdentifierError,match=unknown):parse_column_identifiers(unknown,names)

def test_excluded_invalid_range_message():
    with pytest.raises(ColumnIdentifierError,match='no-pe'):
        parse_column_identifiers('1-3',['id','name','value'],excluded_columns='no-pe')

def test_regression():
    names=['id','known-name','value']
    assert parse_column_identifiers('known-name',names,ignore_unknown_columns=True)==[1]
    assert parse_column_identifiers('1-3',names)==[0,1,2]
    assert parse_column_identifiers('1-3',names,excluded_columns='2')==[0,2]
""",
    "19810a3": """import io
import csv
import pytest
from csvkit.utilities.in2csv import In2CSV
from csvkit.utilities.csvformat import CSVFormat
from csvkit.utilities.csvpy import CSVPy
from csvkit.utilities.sql2csv import SQL2CSV

def convert(tmp_path,utility,flags):
    source=tmp_path/'data.csv';source.write_text('name,value\\n"Café,茶",001\\n',encoding='utf8')
    buffer=io.BytesIO();output=io.TextIOWrapper(buffer,encoding='utf8',newline='')
    args=[str(source),*flags]
    if utility is In2CSV:args+=['-f','csv','-I']
    u=utility(args,output_file=output);u.run();output.flush();result=buffer.getvalue();output.detach();return result

@pytest.mark.parametrize('utility',[In2CSV,CSVFormat])
def test_bom(tmp_path,utility):
    result=convert(tmp_path,utility,['--add-bom'])
    assert result.startswith(b'\\xef\\xbb\\xbf')
    assert list(csv.reader(io.StringIO(result.decode('utf-8-sig'))))==[['name','value'],['Café,茶','001']]

@pytest.mark.parametrize('utility',[CSVPy,SQL2CSV])
def test_bom_option_excluded(utility):
    with pytest.raises(SystemExit) as error:
        utility(['--add-bom'],output_file=io.StringIO())
    assert error.value.code==2

def test_regression(tmp_path):
    result=convert(tmp_path,In2CSV,[])
    assert not result.startswith(b'\\xef\\xbb\\xbf')
    assert list(csv.reader(io.StringIO(result.decode('utf8'))))==[['name','value'],['Café,茶','001']]
""",
}
