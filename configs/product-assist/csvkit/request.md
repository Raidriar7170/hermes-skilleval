# Developer-defined assist smoke: null GeoJSON properties

Make `csvkit.convert.geojs.geojson2csv` accept a GeoJSON Feature whose `properties` is JSON null. Treat null properties as an empty property mapping, as already happens when properties is absent. In a mixed FeatureCollection, keep fields from non-null properties and output empty cells for the null feature. Preserve ids, Point coordinates and normal property conversion. Add focused tests and a small non-executable JSON fixture under `examples/assist_null_properties.json`. Do not change configuration/dependencies or unrelated converters.

This is a developer-defined current maintenance request, not an upstream issue or a benchmark task. Controller checks are defined separately before execution; there is no reference patch.
