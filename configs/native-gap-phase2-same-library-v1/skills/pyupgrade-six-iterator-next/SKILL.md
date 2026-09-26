---
name: pyupgrade-six-iterator-next
description: Investigate pyupgrade rewrites of next(six.itervalues/iterkeys/iteritems(...)) that leave a dict view where an iterator is required.
---

# six iterator calls inside next()

Use this historical case when `pyupgrade --py36-plus` converts a `six.itervalues`, `six.iterkeys`, or `six.iteritems` call inside `next(...)` to a dictionary view. The source revision was pyupgrade 1.24-era code in one `pyupgrade.py` file; later plugin code may have different handling.

1. Reproduce with `print(next(six.itervalues({1: 2})))` and run the result. In the source, the original printed `2`; the rewrite `next({1: 2}.values())` raised `TypeError: 'dict_values' object is not an iterator`.
2. Inspect both the six-call mapping and the parent-call context. The recorded mapping replaced iterator helpers with `.items()`, `.keys()`, or `.values()`, which are views in Python 3. A direct `next` consumer needs an iterator over that view. Check the actual AST relationship rather than assuming all six calls need `iter(...)`.
3. Keep other contexts in the regression set. The local reproduction expected `next(iter(d.values()))`, and analogous keys/items results, while a `for` loop over `six.itervalues(d)` remained a direct `d.values()` iteration. Also check `next` with a default argument and independent calls in the same file.
   The loop served as a control case in the local rewrite checks: its direct view iteration passed without an added `iter(...)` wrapper. Preserve that distinction when evaluating a newer implementation.
4. Validate rewritten syntax and behavior, then run focused tests. The source's final file contained `next(iter({1: 2}.values()))`, printed `2`, and its final `tests/six_test.py` run reported 65 passed. A broader suite stopped at an octal-literal assertion; that run did not establish full-suite success.

**Recorded validation:** A four-case local rewrite script passed for values, keys, items, and a `for` loop. The final command rewrote the example and the resulting script ran successfully. These are observations from the historical checkout only.

**Author result:** `author_resolved: 1`. Source issue `asottile__pyupgrade-208`, trajectory `chatcmpl-1eddbee6dac4154c8e51484018e74a81`; base commit `a5dc2d6c367df8bdac783c4d00cf6dc459f797cf`. Pinned dataset trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`; task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Treat the observed patch as version-specific and recheck the target visitor's context tracking. Dataset: CC-BY-4.0; original repository: MIT License.
