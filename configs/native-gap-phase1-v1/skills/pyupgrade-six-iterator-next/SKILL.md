---
name: pyupgrade-six-iterator-next
description: Check pyupgrade rewrites of `six.iterkeys`, `six.itervalues`, or `six.iteritems` where `next()` needs an iterator after Python 3 conversion.
---

# Keep `next()` input iterable as an iterator

Use when `--py36-plus` turns `next(six.itervalues(d))` into `next(d.values())`, or similarly for keys/items. The source used pyupgrade 1.24. A Python 3 dictionary view is iterable but not an iterator, so direct `next()` raises `TypeError`.

Inspect six-call discovery and token replacement. The source distinguished a `next()` context and emitted `iter(...)` around its dictionary view. Its first parent-detection attempt failed: debug output showed `_previous_node` was `ast.Load`, not the enclosing call. Verify visitor traversal and scope any context state to the subtree. A `for` loop need not inherit the `next()` rewrite.

## Executable checks

Run from the affected checkout.

1. Confirm the Python 3 distinction used by the reproducer:

   ```sh
   python - <<'PY'
   d = {1: 2}
   assert next(iter(d.values())) == 2
   try:
       next(d.values())
   except TypeError:
       pass
   else:
       raise AssertionError('view unexpectedly accepted by next')
   PY
   ```

2. Rewrite and execute the reported form; repeat for `iterkeys` and `iteritems`:

   ```sh
   python - <<'PY'
   import pathlib, subprocess, sys, tempfile
   with tempfile.TemporaryDirectory() as d:
       p = pathlib.Path(d) / 'case.py'
       p.write_text('import six\nprint(next(six.itervalues({1: 2})))\n')
       subprocess.run([sys.executable, 'pyupgrade.py', '--py36-plus', str(p)], capture_output=True)
       assert 'next(iter(' in p.read_text()
       assert subprocess.check_output([sys.executable, str(p)]).strip() == b'2'
   PY
   ```

3. Run `python -m pytest tests/six_test.py -q` for the existing six conversions.

## Evidence and limits

The original example ran, its first rewrite raised `TypeError`, and a later rewrite printed `2`. A source reproduction script reported matching values, keys, items, and `for`-loop cases. Targeted pytest output shows progress dots; the full suite reached an `F` before stored output cut off. Nested contexts and full-suite success remain unverified.

Source issue `asottile__pyupgrade-208`; trajectory `chatcmpl-1eddbee6dac4154c8e51484018e74a81`. The author-resolved label is historical metadata, not local verification.

Source dataset: nebius/SWE-rebench-openhands-trajectories, revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, CC-BY-4.0. Source repository: asottile/pyupgrade, MIT License. These are development exploration samples.
