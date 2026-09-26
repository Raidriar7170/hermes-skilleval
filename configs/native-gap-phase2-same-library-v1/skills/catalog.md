# Available historical experience

All entries are optional. Current requirements and actual source take priority. Read the body and references to judge applicability.

- **httpx-line-decoder-performance**: Historical diagnostic reference for slow HTTPX LineDecoder or Response.iter_lines() on chunks containing many lines, especially around the 0.23 source snapshot.
  Path: `/home/native/.agents/skills/httpx-line-decoder-performance/SKILL.md`

- **httpx-proxy-certificate-flow**: Historical HTTPX 0.7 proxy-certificate diagnostic reference for per-request verify settings during HTTPS tunneling, with no validated end-to-end fix.
  Path: `/home/native/.agents/skills/httpx-proxy-certificate-flow/SKILL.md`

- **httpx-redirect-body-headers**: Historical HTTPX 0.7.2 reference for diagnosing stale request-body headers when a POST redirect becomes GET.
  Path: `/home/native/.agents/skills/httpx-redirect-body-headers/SKILL.md`

- **httpx-repr-secret-redaction**: Historical reference for checking HTTPX URL, Headers, and Request representations that may expose URL passwords or Authorization header values, especially around the 0.7 snapshot.
  Path: `/home/native/.agents/skills/httpx-repr-secret-redaction/SKILL.md`

- **httpx-trio-redirect-tls-diagnostics**: Historical HTTPX 0.9 diagnostic reference for Trio SSL WRONG_VERSION_NUMBER after an HTTP-to-HTTPS redirect, with no validated fix.
  Path: `/home/native/.agents/skills/httpx-trio-redirect-tls-diagnostics/SKILL.md`

- **httpx-valueless-query-params**: Historical reference for HTTPX URL query keys disappearing when a valueless key is merged with request params, especially around the 0.23 snapshot.
  Path: `/home/native/.agents/skills/httpx-valueless-query-params/SKILL.md`

- **pyupgrade-del-name-context**: Investigate pyupgrade --py3-plus AssertionError when a function deletes a name with del, especially in the 2.4-era AST visitor.
  Path: `/home/native/.agents/skills/pyupgrade-del-name-context/SKILL.md`

- **pyupgrade-invalid-format-fstring**: Historical checks for pyupgrade --py36-plus crashes on malformed literal .format strings such as a lone opening brace; use when investigating the f-string conversion path at the cited revision.
  Path: `/home/native/.agents/skills/pyupgrade-invalid-format-fstring/SKILL.md`

- **pyupgrade-percent-string-width**: Historical checks for pyupgrade conversions of percent-formatted strings with a minimum width, such as %9s, when output alignment changes at the cited revision.
  Path: `/home/native/.agents/skills/pyupgrade-percent-string-width/SKILL.md`

- **pyupgrade-reraise-keyword-tb**: Investigate pyupgrade --py3-plus rewrites of six.reraise calls whose traceback is passed as tb=, particularly in the 2.30 plugin.
  Path: `/home/native/.agents/skills/pyupgrade-reraise-keyword-tb/SKILL.md`

- **pyupgrade-six-iterator-next**: Investigate pyupgrade rewrites of next(six.itervalues/iterkeys/iteritems(...)) that leave a dict view where an iterator is required.
  Path: `/home/native/.agents/skills/pyupgrade-six-iterator-next/SKILL.md`

- **pyupgrade-six-reraise-arity**: Historical diagnostic checks for pyupgrade --py3-plus IndexError on a six.reraise call with fewer positional arguments than its rewrite template expects.
  Path: `/home/native/.agents/skills/pyupgrade-six-reraise-arity/SKILL.md`
