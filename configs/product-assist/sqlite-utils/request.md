# Developer-defined assist smoke: invalid chunk sizes

Improve `sqlite_utils.utils.chunks` so zero or negative sizes raise a clear ValueError mentioning that size must be positive, including when the input iterable is empty. Validation must happen before consuming the input iterable. Positive sizes must keep the current lazy chunking behavior and output, including the final short chunk. Add focused regression tests under tests. Do not change package/dependency configuration or unrelated functions.

This is a developer-defined usability request for the assist entrypoint, not an upstream issue or a benchmark task. Controller checks are separately frozen before execution; no reference patch is provided.
