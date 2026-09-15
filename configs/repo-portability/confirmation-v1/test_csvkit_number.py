import io
import json
import pytest
from csvkit.utilities.csvstat import CSVStat


@pytest.mark.parametrize("number", ["5.5", "4.4"])
def test_number_with_date_format(tmp_path, number):
    source = tmp_path / "data.csv"
    source.write_text("day,amount\n13/12/2024," + number + "\n")
    output = io.StringIO()
    CSVStat(
        ["--json", "--date-format", "%d/%m/%Y", str(source)], output_file=output
    ).run()
    rows = json.loads(output.getvalue())
    assert rows[0]["type"] == "Date"
    assert rows[1]["type"] == "Number"


def test_explicit_datetime(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("moment\n2024-12-13 12:30\n")
    output = io.StringIO()
    CSVStat(
        ["--json", "--datetime-format", "%Y-%m-%d %H:%M", str(source)],
        output_file=output,
    ).run()
    assert json.loads(output.getvalue())[0]["type"] == "DateTime"


def test_ordinary_numeric(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("amount\n123.45\n")
    output = io.StringIO()
    CSVStat(["--json", str(source)], output_file=output).run()
    assert json.loads(output.getvalue())[0]["type"] == "Number"
