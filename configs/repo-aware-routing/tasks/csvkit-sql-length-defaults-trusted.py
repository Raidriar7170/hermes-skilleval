import io
import csv
from csvkit.utilities.csvsql import CSVSQL
from csvkit.utilities.csvformat import CSVFormat


def run(klass, args):
    output = io.StringIO()
    klass(args, output_file=output).run()
    return output.getvalue()


def test_regression(tmp_path):
    source = tmp_path / "simple.csv"
    source.write_text("name,count\nCleo,2\n")
    assert list(csv.reader(io.StringIO(run(CSVFormat, [str(source)])))) == [
        ["name", "count"],
        ["Cleo", "2"],
    ]


def test_target():
    tool = CSVSQL([])
    assert tool.args.min_col_len == 1
    assert tool.args.col_len_multiplier == 1
    explicit = CSVSQL(["--min-col-len", "3", "--col-len-multiplier", "4"])
    assert explicit.args.min_col_len == 3
    assert explicit.args.col_len_multiplier == 4
