"""Controller-authored checks derived from the public smoke request before execution."""

import csv
import json
from io import StringIO
from csvkit.convert.geojs import geojson2csv


def convert(features):
    return list(
        csv.DictReader(
            StringIO(
                geojson2csv(
                    StringIO(
                        json.dumps({"type": "FeatureCollection", "features": features})
                    )
                )
            )
        )
    )


def test_requirement_null_and_mixed_properties():
    rows = convert(
        [
            {"type": "Feature", "id": "empty", "properties": None, "geometry": None},
            {
                "type": "Feature",
                "id": "full",
                "properties": {"label": "point"},
                "geometry": {"type": "Point", "coordinates": [12, 34]},
            },
        ]
    )
    assert rows[0]["id"] == "empty"
    assert rows[0]["label"] == ""
    assert rows[1]["label"] == "point"
    assert (rows[1]["longitude"], rows[1]["latitude"]) == ("12", "34")


def test_requirement_all_null_properties():
    rows = convert([{"id": "a", "properties": None, "geometry": None}])
    assert len(rows) == 1 and rows[0]["id"] == "a"


def test_regression_absent_properties():
    assert convert([{"id": "a", "geometry": None}])[0]["id"] == "a"


def test_regression_non_null_nested_properties():
    rows = convert(
        [
            {
                "id": 5,
                "properties": {"nested": {"x": 1}, "name": "valid"},
                "geometry": {"type": "Point", "coordinates": [1, 2, 3]},
            }
        ]
    )
    assert json.loads(rows[0]["nested"]) == {"x": 1}
    assert rows[0]["name"] == "valid"
    assert rows[0]["longitude"] == "1" and rows[0]["latitude"] == "2"
