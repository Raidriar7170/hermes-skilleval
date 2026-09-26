---
name: httpx-proxy-certificate-flow
description: Historical HTTPX 0.7 proxy-certificate diagnostic reference for per-request verify settings during HTTPS tunneling, with no validated end-to-end fix.
---

# Proxy certificate verification flow

Use this optional reference when an HTTPX 0.7-era request through an HTTP proxy reports `CERTIFICATE_VERIFY_FAILED` and a caller supplies a PEM path through `verify`. The issue example used Charles Proxy and an `http://` URL; establish whether an HTTPS tunnel is actually reached before applying any tunnel-specific inference.

1. Separate the client's requested URL, proxy URL, redirect targets, and TLS peer. In the inspected code, `HTTPProxy.acquire_connection` forwarded some origins and tunneled others; `tunnel_start_tls` only created a target SSL context when `origin.is_ssl`. This distinction matters for an initial HTTP request that may later redirect.
2. Trace `verify` and `cert` from the request through `HTTPProxy.send`, connection acquisition, and `tunnel_start_tls`. The recorded revision accepted per-request values in `send` but the tunnel method constructed `SSLConfig(cert=self.cert, verify=self.verify)` from proxy object fields. Treat that as a candidate parameter-flow gap, not proof that it caused the user's certificate error.
3. Use a focused test that asserts which values reach the target tunnel's `SSLConfig`, then verify with a real proxy and trusted certificate chain if available. The trajectory's mock reported request-specific `verify` reaching `SSLConfig` after a patch and restoration of proxy fields; its high-level test only created a client. An earlier reproduction timed out and did not recreate the user's TLS failure.
4. Recheck concurrency and connection reuse before adopting a fix. The historical patch temporarily mutated shared proxy `self.verify` and `self.cert` during `send`; the recorded checks did not exercise overlapping requests or a live Charles tunnel.

**Author final result:** `author_resolved=0`, `exit_status=submit`; no validated fix.

**Local observations:** The mocked parameter check passed and selected proxy tests showed passing cases, but their outputs were truncated. One separate mock test failed from awaiting a `MagicMock`. Neither mock success nor the author's explanatory script establishes end-to-end certificate verification success.

**Version and transfer limits:** Source issue `encode__httpx-377`, trajectory `chatcmpl-e7a14a7a3e547c428e18dc0df4ef6e71`; fixed source snapshot: base commit `e62e5c3758b10a8830c751acbe588d7b572a9957`, trajectory revision `35455389ab51bf5e2306bfd436ef72d0f98bf882`, task revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. This records HTTPX 0.7 internals and cannot establish behavior of later proxy or TLS implementations. Dataset: CC-BY-4.0. Original repository: BSD 3-Clause "New" or "Revised" License.
