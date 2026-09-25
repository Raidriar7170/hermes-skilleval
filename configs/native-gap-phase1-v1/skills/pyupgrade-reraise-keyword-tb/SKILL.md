---
name: pyupgrade-reraise-keyword-tb
description: Inspect `six.reraise` rewrites in pyupgrade when a named `tb=` argument is dropped while positional traceback arguments work.
---

# Keep the named traceback argument

Use when the `six_calls` plugin rewrites `reraise(type, value, tb=traceback)` as `raise value.with_traceback(None)`. The source used pyupgrade 2.30. Check import recognition and starred-argument guards first.

The AST probe showed two positional arguments plus `keyword(arg='tb', ...)`; the working positional form had three. A `len(node.args) == 2` branch chose the no-traceback rewrite. Read `node.keywords` before that branch and retain the named value. Preserve two- and three-positional-argument behavior. An unsupported value must not silently become `None`.

## Executable checks

Run from the affected checkout.

1. Compare the call shapes:

   ```sh
   python - <<'PY'
   import ast
   for src in ('reraise(a, b, tb=c)', 'reraise(a, b, c)', 'reraise(a, b)'):
       call = ast.parse(src).body[0].value
       print(src, len(call.args), [(k.arg, ast.dump(k.value)) for k in call.keywords])
   PY
   ```

2. Check the reported named argument through the CLI. Exit code 1 meant a rewrite in this checkout; inspect file content:

   ```sh
   python - <<'PY'
   import pathlib, subprocess, sys, tempfile
   with tempfile.TemporaryDirectory() as d:
       p = pathlib.Path(d) / 'case.py'
       p.write_text('from six import reraise\nreraise(T, v, tb=c)\n')
       subprocess.run([sys.executable, '-m', 'pyupgrade', '--py3-plus', str(p)], capture_output=True)
       assert 'raise v.with_traceback(c)' in p.read_text(), p.read_text()
   PY
   ```

3. Run `python -m pytest tests/features/six_test.py -q` for the existing plugin cases.

## Evidence and limits

The source reproducer first lost `tb=exc_info[2]` while retaining a positional traceback. Later CLI output showed the named traceback, and a final script printed matching named and positional outputs. The conversion-input pytest excerpt is truncated. Author-resolved label `0` and these examples do not establish an accepted patch. Complex expressions need separate checks.

Source issue `asottile__pyupgrade-584`; trajectory `chatcmpl-0eb2fe9fe001267babf41342c4812cc9`.

Source dataset: nebius/SWE-rebench-openhands-trajectories, revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, CC-BY-4.0. Source repository: asottile/pyupgrade, MIT License. These are development exploration samples.
