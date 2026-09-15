---
name: schema-change-regression
description: Validate schema maintenance changes involving tables, indexes, constraints, views and transactions.
---

# schema-change-regression

Hermes-authored generic workflow, newly organized for modern public replay.

Read the checked-out schema documentation and nearby tests. Record schema and rows before the operation. Exercise the requested change, then compare preserved data, indexes, constraints, views and transaction state as applicable to the request. Include a failure path to check rollback behavior. Use only capabilities documented or implemented in this checkout; do not assume all SQLite versions behave alike.
