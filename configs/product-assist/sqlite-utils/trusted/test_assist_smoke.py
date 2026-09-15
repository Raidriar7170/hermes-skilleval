"""Controller-authored checks derived from the public smoke request before execution."""

import pytest
from sqlite_utils.utils import chunks


@pytest.mark.parametrize("size", [0, -1, -10])
@pytest.mark.parametrize("values", [[], [1, 2]])
def test_requirement_invalid_size(values, size):
    with pytest.raises(
        ValueError, match="(?i)(positive|greater than zero|greater than 0|at least 1)"
    ):
        list(chunks(values, size))


def test_requirement_no_input_consumption():
    consumed = []

    def values():
        consumed.append(True)
        yield 1

    with pytest.raises(ValueError):
        list(chunks(values(), 0))
    assert consumed == []


@pytest.mark.parametrize(
    "values,size,expected",
    [([], 2, []), ([1, 2, 3], 2, [[1, 2], [3]]), ([1, 2], 1, [[1], [2]])],
)
def test_regression_positive_sizes(values, size, expected):
    assert [list(chunk) for chunk in chunks(iter(values), size)] == expected
