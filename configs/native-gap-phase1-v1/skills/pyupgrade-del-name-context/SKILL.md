---
name: pyupgrade-del-name-context
description: Diagnose pyupgrade crashes on `del` inside a function when a scope-aware AST visitor handles Load and Store names but rejects Del names.
---

# Deletion context in a scope visitor

Use only when `--py3-plus` reaches `visit_Name`, the visitor maintains function-scope name sets, and a Load/Store-only branch rejects a deleted name. The source used pyupgrade 2.4.2; inspect other versions before adapting.

`del bar` parses as an `ast.Name` with `ast.Del` context. The recorded visitor asserted on that context. Trace consumers of its scope sets before classifying deletion; the source classified `ast.Del` with writes. Retain the assertion for truly unknown contexts.

## Executable checks

Run from the affected checkout.

1. Confirm the AST shape:

   ```sh
   python - <<'PY'
   import ast
   tree = ast.parse('def foo(bar):\n    del bar\n')
   print([(n.id, type(n.ctx).__name__) for n in ast.walk(tree) if isinstance(n, ast.Name)])
   PY
   ```

2. Run the reported CLI path on a disposable file; exit zero and no assertion were observed:

   ```sh
   python - <<'PY'
   import pathlib, subprocess, sys, tempfile
   with tempfile.TemporaryDirectory() as d:
       p = pathlib.Path(d) / 'case.py'
       p.write_text('def foo(bar):\n    del bar\n')
       r = subprocess.run([sys.executable, 'pyupgrade.py', '--py3-plus', str(p)], capture_output=True, text=True)
       assert r.returncode == 0, r.stderr
   PY
   ```

3. Run the relevant existing tests: `python -m pytest tests/main_test.py tests/six_test.py -q`.

## Evidence and limits

The trajectory reran a reproducer with basic, multiple, and nested deletions, and six deletion edge cases; those scripts reported passes. The single CLI repro exited zero. The conversion-input pytest excerpt is truncated; the full-suite run visibly reached an `F` near octal-literal tests, with no proven cause. No source checkout was locally verified here.

Source issue `asottile__pyupgrade-308`; trajectory `chatcmpl-f367adf5d3611067e8ab321aae3c122b`. The author-resolved label is historical metadata, not local verification.

Source dataset: nebius/SWE-rebench-openhands-trajectories, revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, CC-BY-4.0. Source repository: asottile/pyupgrade, MIT License. These are development exploration samples.
