---
name: pyupgrade-del-name-context
description: Investigate pyupgrade --py3-plus AssertionError when a function deletes a name with del, especially in the 2.4-era AST visitor.
---

# Deleted names in pyupgrade's Python 3 visitor

Use this historical case when `pyupgrade --py3-plus` raises `AssertionError` on code such as `def foo(bar): del bar`. The record concerns pyupgrade 2.4.2 and its single-file `pyupgrade.py`; later layouts and visitors may differ.

1. Reduce the report to a function containing `del bar` and reproduce the CLI failure. The recorded run reached `FindPy3Plus.visit_Name`, which raised on a name context outside `ast.Load` and `ast.Store`.
2. Inspect the parsed name context and the active visitor before changing scope bookkeeping. In this case, the `bar` node had `ast.Del` context, while the visitor's in-scope branch accepted only `Load` and `Store`. Check nearby scope propagation if a current version uses a different representation.
   The AST observation singled out a deleted `Name`; attribute and subscript deletion are separate probes and do not by themselves identify the same failing visitor branch.
3. For a matching visitor, account for deletion as a name affecting the scope and then check the original command plus distinct deletion shapes. The historical edit grouped `ast.Del` with recorded writes; this is evidence for that revision, not a blanket rule for all AST analyses.
4. Run relevant regression tests and report their actual reach. The local reproduction passed basic, multiple, and nested deletes; edge probes for attribute, subscript, slice, tuple, class attribute, and dict-key deletion also passed. A broader pytest run stopped at an octal-literal assertion that also failed when the patch was stashed, so it did not establish a clean full suite.

**Recorded validation:** The minimal CLI command exited 0 after the edit, the local delete probes passed, and `git diff` showed the two-line `ast.Del` branch. These are trajectory observations, not a fresh verification in another checkout.

**Author result:** `author_resolved: 1`. Source issue `asottile__pyupgrade-308`, trajectory `chatcmpl-f367adf5d3611067e8ab321aae3c122b`; base commit `6eed58483836b7c951f9d1173c1c39700b87c722`. Pinned dataset trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`; task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Transfer only after checking the target version's AST and tests. Dataset: CC-BY-4.0; original repository: MIT License.
