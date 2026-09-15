# Escape tokenize argument in enable_fts to prevent SQL injection

Source: https://github.com/simonw/sqlite-utils/pull/828

## Summary

`Table.enable_fts(tokenize=...)` interpolated the `tokenize` value directly into the `CREATE VIRTUAL TABLE` statement inside a single-quoted string literal:

```python
tokenize=f"\n    tokenize='{tokenize}'," if tokenize else "",
```

Because the statement runs through `executescript()`, a `tokenize` value containing a single quote can close the literal and append additional statements. This is reachable from the CLI via `sqlite-utils enable-fts ... --tokenize`.

## Fix

Route the value through the existing `Database.quote()` helper, which uses SQLite's own `quote()` to escape the string. Legitimate tokenizers such as `porter` (and multi-word forms like `porter unicode61`) are unaffected, for both FTS4 and FTS5.

## Test

Added `test_fts_tokenize_escaped`, which confirms a crafted `tokenize` value cannot create an extra table. Existing tokenize tests (`test_fts_tokenize`) still pass.

```
python -m pytest tests/test_fts.py -q
# 52 passed
```

<!-- readthedocs-preview sqlite-utils start -->
----
📚 Documentation preview 📚: https://sqlite-utils--828.org.readthedocs.build/en/828/

<!-- readthedocs-preview sqlite-utils end -->


