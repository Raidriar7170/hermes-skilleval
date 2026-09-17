# Acceptance semantics and visibility

All new observations are POSTHOC_REVALIDATION_OF_FROZEN_PATCHES. Old outcomes,
patches, prompts, and JUnit remain unchanged. The actual saved prompt in every
one of the 32 runs begins with the byte-identified public request (normal text
newline reading); all 16 affected prompts include both issue title and body.
This is not blind review or independent preregistration.

| Obligation | Source and fixed location | Original visibility | Interpretation / executable observation | Limitation |
|---|---|---|---|---|
| csv.stdin.all | [csvkit #1225](https://github.com/wireservice/csvkit/issues/1225); base ed05def docs/scripts/in2csv.rst:52–55, csvkit/utilities/in2csv.py:47–48,170–195 | YES issue title/body; base files available, reads not established | `--write-sheets` consumes `-` meaning all sheets; no positional file means stdin. Preserve invocation and require exit zero, exact complete CSV matrices per sheet. | Original fixture only one data row; contents newly covered by this appendix. |
| csv.naming | Same sources; no stdin prefix contract found | YES request; base files available | No `stdin_` requirement. Regular CSV files in fresh output directory; compare full matrices as a multiset, retain duplicate rows/tables. | Internal base naming is not a mandatory stdin prefix. This corrects an unsupported old restriction. |
| csv.stdout | Fixed base in2csv.py:157–168 (conversion and table.to_csv), existing default-sheet interface | Available base; actual source reads not claimed | First worksheet CSV on stdout; check separately from exported files. | Interface-preservation assertion, not explicit issue text; scope includes default first sheet only. |
| csv.original.content | Original hash-bound trusted/dummy.xlsx, Sheet1 A1:C2; csvkit/cli.py:327–342 and pinned agate 1.14.2 Boolean.cast/csvify | Fixture hidden from Agent; interface available | Header a,b,c; data True,2,3. Under default type inference 1 becomes Boolean True before Number. Exact parsed strings; no coercion of outputs. | This expected value is derived from workbook cells plus fixed dependency semantics, not reference output. |
| csv.multisheet | Same all-sheets interface; new deterministic two-sheet fixture | NO new fixture | New diagnostic coverage: distinct matrices with duplicate row, comma and quote cells. | Posthoc coverage expansion, not an additional repair task or automatically an old judging error. |
| csv.file.regression | Original fixed file input CLI / prior regression | Available base interface | File input keeps default-sheet stdout conversion for original and new fixture. | Does not cover formulas, dates, merged cells, encodings or all Excel formats. |
| sqlite.package | [sqlite-utils #368 title](https://github.com/simonw/sqlite-utils/issues/368) | YES title | Explicit `runpy.run_module('sqlite_utils', run_name='__main__')`; help plus known table-list operation | Title/body ambiguity retained. |
| sqlite.submodule | Same issue body code/example | YES body | Explicit `runpy.run_module('sqlite_utils.cli', run_name='__main__')`; help plus known table-list operation | Neither choose better entry nor require both as sole success score. |
| sqlite.console | Base 650f97a setup.py entry point; docs/cli.rst:418–433 | Base available; reads not established | `sqlite_utils.cli:cli`, help and `tables /fixture`, expected JSON `[{"table":"acceptance_items"}]` | Original help-only regression expanded by functional probe. |

SQLite table listing is a deterministic read-only operation already supported
by this version. The controller creates one table. JSON whitespace is ignored
by parsing; no semantic values are discarded. Package, submodule and console
help/function are six separate dimensions. Help containing Usage is only a help
observation and never sufficient for the function dimension.

Control development detected one expected-value error before candidates ran:
assuming numeric 1 serialized as "1" ignored the default Boolean-first type
inference. The original XLSX bytes and command remain unchanged. Source review
of fixed csvkit and agate justified "True"; no output is coerced to match it.
The first control launch also used macOS Python 3.9 accidentally, incompatible
with the project's Python >=3.11 contract; subsequent runs use existing 3.12.
Both attempts are retained privately. No original candidate ran before freeze.

Isolation uses source read-only, network none, no credentials/home/socket mounts,
read-only root, dropped capabilities, non-root uid, bounded memory/pids/tmpfs.
Candidate subprocesses only produce stdout/stderr and files; host code computes
new verdicts and writes JUnit afterward. Temporary /tmp scratch is permitted.
Legacy checks retain the exact inherited harness and its bounded non-adversarial
trust limitation. Patch inspection is not a proof against arbitrary malicious code.
