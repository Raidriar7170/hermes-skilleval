---
name: httpx-trio-redirect-tls-diagnostics
description: Historical HTTPX 0.9 diagnostic reference for Trio SSL WRONG_VERSION_NUMBER after an HTTP-to-HTTPS redirect, with no validated fix.
---

# Trio TLS failure after redirect

Use this optional reference when an HTTPX 0.9-era Trio request to an IP on port 80 redirects to HTTPS on port 443 and reports `ssl.SSLError: WRONG_VERSION_NUMBER`. The source trajectory did not resolve the issue; use its observations only to guide diagnosis.

1. Record the original URL, redirect `Location`, effective second URL, hostname, port, and scheme. In the inspected revision, `URL.is_ssl` returned true only for `https`, `Origin` copied that value, and `client.py` built and sent the redirected request through its redirect loop. Those observations locate where to check whether TLS is attempted against the intended endpoint; they do not prove the reported cause.
2. For Trio, inspect `httpx/concurrency/trio.py` at `SocketStream.start_tls` and `TrioBackend.open_tcp_stream`. The recorded code wrapped a TCP stream in `trio.SSLStream` and called `do_handshake()` when an SSL context was supplied. Compare the stream's actual peer and the SSL context before changing handshake or exception logic.
3. Build a controlled local HTTP redirect and TLS endpoint that reproduces the **same** exception before evaluating any patch. The trajectory's first reproduction used `httpx.AsyncClient`, which was absent in this checkout. Later probes produced `BrokenResourceError` or reported no specific SSL error, so they did not establish the original failure.
4. Run focused Trio TLS tests and inspect the full failure details. The recorded `test_start_tls_on_tcp_socket_stream` failed before and after attempted edits; a custom SSL error-handling check also failed after the edits. A passing unrelated API test gives no validation for this failure.

**Author final result:** `author_resolved=0`; execution stopped at the 100-iteration limit. There is no validated fix.

**Local observations:** The reported `WRONG_VERSION_NUMBER` was not reproduced. The attempted Trio exception-handling edits are historical experiments, not a recommended change. The fixture truncated some pytest logs, limiting the available failure detail.

**Version and transfer limits:** Source issue `encode__httpx-649`, trajectory `chatcmpl-93ae0fe5e1e05c5eb9d7b5ea194a219d`; fixed source snapshot: base commit `6c69e0936b0ee1849f0749f04113ec3e6c92c9ff`, trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. This references HTTPX 0.9-era internals; recheck APIs and backend design before transfer. Dataset: CC-BY-4.0. Original repository: BSD 3-Clause "New" or "Revised" License.
