import io
import csv
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


def test_target(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("name,count\nCleo,2\n")
    text = run(CSVFormat, ["-U", "2", str(source)])
    assert text.replace("\r\n", "\n") == '"name","count"\n"Cleo",2\n'
