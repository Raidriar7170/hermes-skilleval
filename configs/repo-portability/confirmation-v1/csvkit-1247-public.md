# TimeDeltas and json

Source: https://github.com/wireservice/csvkit/issues/1247

Hello,
Can TimeDeltas type objects be somehow json-serializable? (or is it expected to work, if not - no question)


`csvstat some_timedelta.csv --json`

_TypeError: datetime.timedelta(seconds=60) is not JSON serializable_

Public acceptance clarification: JSON time delta values are numeric total seconds, including zero, negative and fractional durations. Exercise both the serialization helper and csvstat --json; preserve Decimal and date serialization.
