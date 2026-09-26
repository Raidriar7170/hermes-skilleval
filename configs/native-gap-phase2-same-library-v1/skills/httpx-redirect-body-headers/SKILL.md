---
name: httpx-redirect-body-headers
description: Historical HTTPX 0.7.2 reference for diagnosing stale request-body headers when a POST redirect becomes GET.
---

# Redirected body headers in HTTPX 0.7.2

Use this optional reference when a body-bearing request follows a redirect and the next request changes to a bodyless method, especially with `h11.LocalProtocolError: Too little data for declared Content-Length`. It records one old trajectory, not a general patch recipe.

1. Reproduce locally with a POST carrying a five-byte body and a 302 redirect. Inspect **both** the redirected method and its outgoing headers. The recorded pre-change mock observed GET with `Content-Length: 5`; an HTTP/1.1 local-server reproduction sent the same inconsistent GET headers. A cross-origin redirect changed `host` but left `Content-Length` intact.
2. In this revision, inspect `httpx/middleware.py`: `build_redirect_request` chose the new method, `redirect_content` emptied the body when changing to GET, and `redirect_headers` copied the original headers. Check these together before attributing an h11 error to header/body disagreement.
3. If adapting the historical change, have header selection see the **resulting** method. The recorded patch removed `Content-Length` and `Transfer-Encoding` for GET/HEAD and retained body framing for a POST-to-POST redirect. Recheck 301, 302, 303, HEAD, and cross-origin behavior against the version actually in use.
4. Validate with a local HTTP/1.1 redirect and an outgoing-header assertion. The recorded after-change run sent GET without `Content-Length`, returned 200, and separate local scripts reported removal on GET, retention on POST-to-POST, and removal of `Transfer-Encoding` on GET. A selected existing `test_redirect_302` passed; longer pytest output was truncated and does not establish a full-suite pass.

**Author final result:** `author_resolved=1`, `exit_status=submit`.

**Local observations:** The recorded before/after traffic and focused checks support the header mismatch and the tested change. An initial HEAD assertion failed because the test expected POST+303 to become HEAD; the test was corrected after source inspection. No live Starlette-to-httpbin end-to-end validation is established here.

**Version and transfer limits:** Source issue `encode__httpx-310`, trajectory `chatcmpl-589eab8bff97d199fc984d997a41eff7`; fixed source snapshot: base commit `b8c5e7a8528978e646c28a5837df5085ea3803fc`, trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. This was HTTPX 0.7.2 behavior; inspect current redirect code before transfer. Dataset: CC-BY-4.0. Original repository: BSD 3-Clause "New" or "Revised" License.
