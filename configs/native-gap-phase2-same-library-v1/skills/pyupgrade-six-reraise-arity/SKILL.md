---
name: pyupgrade-six-reraise-arity
description: Historical diagnostic checks for pyupgrade --py3-plus IndexError on a six.reraise call with fewer positional arguments than its rewrite template expects.
---

# `six.reraise` rewrite argument count

Optional historical reference: issue `asottile__pyupgrade-247`; trajectory `chatcmpl-0a1f9b25cb575a198877ec9ab90e6c0b`; base commit `711b1cdfa1b92eb035fe379b35d73a23859b5bc3`; fixed trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`; task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. The report names pyupgrade 1.26.0 and `--py3-plus`.

1. **Reproduce the call shape.** `six.reraise(et, (ev[0], ev[1] + (" %s %s" % (func, arg))))` has two top-level arguments. With `--py3-plus`, local reproduction raised `IndexError: list index out of range`. Compare a standard three-argument call.
2. **Compare arguments with the template.** Here `SIX_RAISES['reraise']` referenced `args[1]` and `args[2]`. `_fix_py3_plus` passed parsed arguments and that template to `_replace_call`. Check top-level arity; commas inside the tuple expression do not supply `args[2]`.
3. **Inspect all transformed text.** The local guard skipped `reraise` with fewer than three parsed arguments. The issue-shaped call remained `six.reraise(...)`, while another pass changed its inner percent string to `.format(...)`. A standard three-argument call became `raise exc.with_traceback(tb)`. Compare the entire output and behavior, not just absence of a traceback.

**Source validation and limits.** Local observations show the original `IndexError`, no crash after the guard, and `87 passed` for `tests/six_test.py tests/main_test.py -q`. Separately, the dataset marks `author_resolved: 0` and `exit_status: submit`: this failed final trajectory is not a validated fix. Recheck other versions and `six.reraise` semantics.

Source dataset license: CC-BY-4.0. Original pyupgrade repository license recorded in the fixture: MIT License.
