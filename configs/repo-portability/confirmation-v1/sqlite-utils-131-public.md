# sqlite-utils insert: options for column types

Source: https://github.com/simonw/sqlite-utils/issues/131

The `insert` command currently results in string types for every column - at least when used against CSV or TSV inputs.

It would be useful if you could do the following:

- automatically detects the column types based on eg the first 1000 records
- explicitly state the rule for specific columns

`--detect-types` could work for the former - or it could do that by default and allow opt-out using `--no-detect-types`

For specific columns maybe this:

    sqlite-utils insert db.db images images.tsv \
      --tsv \
      -c id int \
      -c score float

Public replay scope: implement explicit --type COLUMN TYPE overrides for insert and upsert, retaining existing --detect-types behavior. Supported names: text, integer, float, blob. Explicit overrides take precedence over detected types. Cover new and existing tables. This clarification corresponds to the public accepted feature.
