---
name: pyupgrade-reraise-keyword-tb
description: Investigate pyupgrade --py3-plus rewrites of six.reraise calls whose traceback is passed as tb=, particularly in the 2.30 plugin.
---

# Keyword traceback in six.reraise

Use this case when pyupgrade rewrites `reraise(exc_info[0], exc_info[1], tb=exc_info[2])` and loses the keyword traceback. The reported 2.30-era output was `raise exc_info[1].with_traceback(None)`; the expected expression uses `exc_info[2]`. Treat this as an investigation reference: the author outcome is unresolved.

1. Reproduce the exact keyword form and inspect the rewritten file, not merely the CLI status. In the source run, exit code 1 accompanied an ordinary “Rewriting” message, while the file contained the wrong traceback. The exit code alone did not diagnose the bug.
2. Compare AST argument counts and keyword entries with the plugin's `reraise` handling. The recorded visitor selected its two-positional-argument template by `len(node.args) == 2` and had a separate three-positional-argument case. Inspect token parsing before deciding how a keyword value should be preserved.
3. Check the output for `tb=variable`, `tb=None`, and `tb=function_call()`, alongside positional traceback, no traceback, and `*sys.exc_info()`. One intermediate local edit still converted `tb=get_traceback()` to `None`; the later local probes showed the expression preserved. These probes demonstrate why one passing keyword example was insufficient.
4. Run the focused `six` tests and check their complete summary in a current checkout. The historical focused pytest output was truncated in the fixture; its visible passing lines do not prove a complete suite result.

**Recorded validation:** A final local script reported 7/7 text-output checks passing, including the issue example, positional and absent traceback, starred `exc_info`, and three keyword forms. Those checks compared generated text; they were not proof of semantic correctness for all expressions. One earlier script used “manual check” for a complex expression and still exited 0 while showing the wrong output.

**Author result:** `author_resolved: 0`, despite the later local checks. Do not present the attempted patch as a validated fix. Source issue `asottile__pyupgrade-584`, trajectory `chatcmpl-0eb2fe9fe001267babf41342c4812cc9`; base commit `234e07160f1d6a171b1100de7046a92d4866e0ba`. Pinned dataset trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`; task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Recheck current plugin structure before transfer. Dataset: CC-BY-4.0; original repository: MIT License.
