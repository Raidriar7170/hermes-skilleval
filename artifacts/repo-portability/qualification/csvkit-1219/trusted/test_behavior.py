import io
import pytest
from csvkit.utilities.csvstack import CSVStack


@pytest.mark.parametrize("size", [32, 140000])
def test_fieldsize_option(tmp_path, size):
    source = tmp_path / "data.csv"
    source.write_text("value\n" + "a" * size + "\n")
    output = io.StringIO()
    CSVStack(["-z", "2500000", str(source)], output_file=output).main()
    assert output.getvalue().splitlines() == ["value", "a" * size]


@pytest.mark.parametrize("values", [["one"], ["one", "two"]])
def test_ordinary_stack(tmp_path, values):
    source = tmp_path / "data.csv"
    source.write_text("value\n" + "\n".join(values) + "\n")
    output = io.StringIO()
    CSVStack([str(source)], output_file=output).main()
    assert output.getvalue().splitlines() == ["value", *values]
