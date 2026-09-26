---
name: httpx-repr-secret-redaction
description: Historical reference for checking HTTPX URL, Headers, and Request representations that may expose URL passwords or Authorization header values, especially around the 0.7 snapshot.
---

# Sensitive values in HTTPX representations

Use this optional reference when logs or debugging output may include `repr()` of HTTPX URLs, headers, or requests. Its checks come from a public historical issue, not a blanket logging-safety guarantee.

1. **Locate every representation path.** In the recorded 0.7 snapshot, `URL.__repr__`, `Headers.__repr__`, and `BaseRequest.__repr__` were in `httpx/models.py`. The request representation used `str(self.url)`, so checking a URL object alone missed the request leak. Inspect the target version's own call chain and any other representation used by the application.

2. **Reproduce with distinct markers.** The baseline local script displayed a URL password in `URL.__repr__`, `Authorization` and `Proxy-Authorization` values in `Headers.__repr__`, and a password in `Request.__repr__`. Use benign synthetic markers; compare their appearance in each representation and in ordinary accessors separately.

3. **Check complete redaction behavior.** The local post-edit observations showed `[secure]` in URL, header, and request representations. They also covered mixed-case and repeated sensitive header names, an empty password, and a password containing a colon. An intermediate run showed URL and header redaction while `Request.__repr__` still leaked; verify all three paths after any change.

4. **Check functional access and test scope.** The source's final validation showed raw URL and header values remained accessible through normal methods while representations were redacted. It reported six placeholders for six repeated sensitive headers. Several pytest runs displayed passing cases, but the captured output was truncated, and a run disabling coverage failed because configured coverage arguments became unrecognized; those logs do not establish a complete suite pass.

**Result and limits.** The author trajectory is marked `author_resolved: 1`. Local observations support the specific `repr()` cases above, not every logging route or later HTTPX release. Source issue `encode__httpx-222`; trajectory `chatcmpl-b42489962c58a042ffcd59695d5e2159`; base commit `79425b28d092a0e9d2577539a571467395b768c4`; fixed fixture revisions: trajectory `35455389ab51bf5e2306bfd436ef72d0f98bf882`, task `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Dataset license: CC-BY-4.0. Original repository license: BSD 3-Clause "New" or "Revised" License.
