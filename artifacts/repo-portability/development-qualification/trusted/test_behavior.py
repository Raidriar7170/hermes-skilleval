"""Public acceptance supplement to csvkit PR 1345; independently authored."""
import io
import pytest
from csvkit.convert import guess_format
from csvkit.utilities.in2csv import In2CSV

@pytest.mark.parametrize('extension', ['ndjson', 'jsonl', 'jl'])
def test_ndjson_api(extension):
    assert guess_format('records.' + extension) == 'ndjson'

@pytest.mark.parametrize('extension', ['ndjson', 'jsonl', 'jl'])
def test_ndjson_cli(extension, tmp_path):
    source = tmp_path / ('records.' + extension)
    source.write_text('{"name":"a","value":1}\n{"name":"b","value":2}\n')
    output = io.StringIO()
    In2CSV([str(source)], output_file=output).main()
    assert output.getvalue().splitlines() == ['name,value', 'a,1', 'b,2']

@pytest.mark.parametrize('extension,expected', [('csv','csv'), ('json','json'), ('js','json'), ('xls','xls'), ('xlsx','xlsx'), ('dbf','dbf'), ('invalid',None)])
def test_existing_formats(extension, expected):
    assert guess_format('records.' + extension) == expected
