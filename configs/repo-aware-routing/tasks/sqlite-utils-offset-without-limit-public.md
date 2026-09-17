Allow rows_where and pks_and_rows_where to accept offset without limit. SQLite requires LIMIT before OFFSET; use LIMIT -1 to express unlimited rows. Preserve ordinary limited and unfiltered reads.
