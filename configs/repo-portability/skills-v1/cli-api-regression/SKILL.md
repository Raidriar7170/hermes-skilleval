---
name: cli-api-regression
description: Check CLI and Python API behavior together for a Python command-line maintenance change.
---

# cli-api-regression

Hermes-authored generic workflow, newly organized for modern public replay.

Read the checked-out contributing and CLI/API documentation. Reproduce the public request through its reported entry point. Compare return values, exit status, stdout, stderr and stored data. Add focused regression coverage; test both mutation and preview modes if they exist. Verify error paths and that unrelated behavior remains intact. Use the repository version present, not remembered newer APIs.
