---
name: pyupgrade-percent-string-width
description: Historical checks for pyupgrade conversions of percent-formatted strings with a minimum width, such as %9s, when output alignment changes at the cited revision.
---

# Percent string width and alignment

Optional historical reference: issue `asottile__pyupgrade-84`; trajectory `chatcmpl-af21bcfb4b49e051135320cf39d0b2f0`; base commit `bbe34c45db1fa1c54969f590fc35571a636132b4`; fixed trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`; task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`.

1. **Compare output including whitespace.** `'%9s %s\n' % ('abc', 'def')` produced `'      abc def\n'`; `'{:9} {}\n'.format('abc', 'def')` produced `'abc       def\n'`. Explicit `{:>9}` matched this source example. Preserve leading spaces and newline in regression checks.
2. **Inspect field construction.** `_percent_to_format` assembled `conversion_flag`, `width`, `precision`, and conversion type. The local change inserted `>` for width-bearing `%s` with an empty `conversion_flag`. Observed adjacent mappings were `%-5s` to `{:<5}` and `%s` to `{}`. Check other types separately.
3. **Inspect the CLI result.** Direct checks reported expected conversions for `%3s`, `%5s`, `%9s`, `%-5s`, and `%s`, and semantic equality for the example. A `%5s` test case was added. The simple CLI example changed as expected; the issue-shaped expression with `self.format_stack(context['stack'])` produced malformed argument text. Check syntax and expression preservation alongside alignment.

**Source validation and limits.** Direct formatting checks passed locally; verbose pytest output was truncated before suite summaries. Separately, the dataset records `author_resolved: 1` and `exit_status: submit`. The complex CLI output remained malformed. The report mentioned multiline indentation, without a validated remedy. Recheck other versions before applying this historical approach.

Source dataset license: CC-BY-4.0. Original pyupgrade repository license recorded in the fixture: MIT License.
