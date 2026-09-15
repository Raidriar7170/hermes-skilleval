import datetime
import decimal
import io
import json
import pytest
from csvkit.cli import default_float_decimal
from csvkit.utilities.csvstat import CSVStat


@pytest.mark.parametrize("seconds", [60, 0, -90, 3600.5])
def test_timedelta_json(seconds):
    assert (
        json.loads(
            json.dumps(
                {"value": datetime.timedelta(seconds=seconds)},
                default=default_float_decimal,
            )
        )["value"]
        == seconds
    )


def test_timedelta_cli(tmp_path):
    source = tmp_path / "durations.csv"
    source.write_text("duration\n00:01:00\n00:02:00\n")
    output = io.StringIO()
    CSVStat(["--json", str(source)], output_file=output).run()
    rows = json.loads(output.getvalue())
    assert rows[0]["type"] == "TimeDelta"
    assert rows[0]["min"] == 60 and rows[0]["max"] == 120


@pytest.mark.parametrize(
    "value,expected",
    [(decimal.Decimal("2.5"), 2.5), (datetime.date(2024, 1, 2), "2024-01-02")],
)
def test_existing_json(value, expected):
    assert json.loads(json.dumps(value, default=default_float_decimal)) == expected
