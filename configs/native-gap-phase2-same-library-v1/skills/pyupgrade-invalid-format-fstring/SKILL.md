---
name: pyupgrade-invalid-format-fstring
description: Historical checks for pyupgrade --py36-plus crashes on malformed literal .format strings such as a lone opening brace; use when investigating the f-string conversion path at the cited revision.
---

# Malformed `.format` literals during f-string conversion

Optional historical reference: issue `asottile__pyupgrade-195`; trajectory `chatcmpl-90ed9922080e9abbb4974b993b88a3f0`; base commit `776d3fd38005862a891ce7a8e9c77fbfaadcca4c`; fixed trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`; task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`.

1. **Reproduce.** A file containing `'{'.format(a)` under `--py36-plus` raised `ValueError: Single '{' encountered in format string`. Consuming `string.Formatter().parse('{')` raised the same exception. Capture traceback and output file; a rewrite exit status does not establish success.
2. **Trace parsing.** `FindSimpleFormats.visit_Call` iterated `parse_format(node.func.value.s)`, which consumed `string.Formatter().parse`. Check validation before the f-string visitor receives malformed strings. Include `'{}'.format(name)` as a valid conversion control.
3. **Check the full pipeline.** The attempt caught `ValueError` inside the visitor, then tried `parse_format` sentinels. A narrow `_fix_fstrings` check left `"{".format(a)` unchanged and converted valid strings, yet the CLI rewrote `'{'.format(a)` to `{}.format(a)`. Inspect all enabled passes and resulting syntax before accepting a fix.

**Source validation and limits.** Local observations show the traceback, narrow conversion behavior, and contradictory CLI output. Verbose pytest output was truncated. Separately, the dataset records `author_resolved: 1`; the trajectory ended at its iteration limit. End-to-end validation is not established by the supplied excerpts. Recheck other versions; the old sentinel and catch placement are not recipes.

Source dataset license: CC-BY-4.0. Original pyupgrade repository license recorded in the fixture: MIT License.
