---
name: pyupgrade-reraise-expression-tb
description: Check source reconstruction for complex `tb=` expressions in a pyupgrade `six.reraise` rewrite after simple keyword values already work.
---

# Preserve the traceback expression

Use after a `six.reraise` rewrite recognizes `tb=` but loses `get_traceback()` or mishandles `exc_info[2]`. The recorded 2.30 plugin combined AST discovery with token replacement; an early keyword edit handled names and constants but fell back to `None` for a call.

Inspect `ast.keyword.value` and the token helper's argument spans. The source tried manual AST reconstruction, then `ast.unparse(keyword.value)` for the observed subscript and nested call. Check the checkout's supported Python versions before using `ast.unparse`. Keep the full expression inside `with_traceback(...)` and parse the result.

## Executable checks

Run from the affected checkout.

1. Inspect the AST and available expression rendering:

   ```sh
   python - <<'PY'
   import ast
   for expr in ('exc_info[2]', 'get_traceback()'):
       kw = ast.parse('reraise(T, v, tb=' + expr + ')').body[0].value.keywords[0]
       print(expr, ast.dump(kw.value), ast.unparse(kw.value) if hasattr(ast, 'unparse') else 'unparse unavailable')
   PY
   ```

2. Rewrite a nested call and parse the result. Also try the subscript form when relevant:

   ```sh
   python - <<'PY'
   import ast, pathlib, subprocess, sys, tempfile
   with tempfile.TemporaryDirectory() as d:
       p = pathlib.Path(d) / 'case.py'
       p.write_text('from six import reraise\nreraise(T, v, tb=get_traceback())\n')
       subprocess.run([sys.executable, '-m', 'pyupgrade', '--py3-plus', str(p)], capture_output=True)
       ast.parse(p.read_text())
       assert 'raise v.with_traceback(get_traceback())' in p.read_text()
   PY
   ```

3. Run `python -m pytest tests/features/six_test.py -q` to exercise neighboring rewrites.

## Evidence and limits

The edge-case script first showed `tb=get_traceback()` becoming `None`; after the `ast.unparse` edit it printed `with_traceback(get_traceback())`. A separate probe rendered `exc_info[2]`. The script called the nested case a manual check, and conversion-input pytest excerpt is truncated. Formatting, version support, and wider semantics remain unknown. Author-resolved label: `0`.

Source issue `asottile__pyupgrade-584`; trajectory `chatcmpl-0eb2fe9fe001267babf41342c4812cc9`.

Source dataset: nebius/SWE-rebench-openhands-trajectories, revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, CC-BY-4.0. Source repository: asottile/pyupgrade, MIT License. These are development exploration samples.
