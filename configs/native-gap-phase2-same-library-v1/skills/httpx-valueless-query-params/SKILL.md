---
name: httpx-valueless-query-params
description: Historical reference for HTTPX URL query keys disappearing when a valueless key is merged with request params, especially around the 0.23 snapshot.
---

# Valueless query keys in HTTPX

Use this optional reference when a URL such as `...?foobar` loses `foobar` after request parameters are added. It records one historical trajectory; check present behavior and serialization requirements in the target version.

1. **Reproduce both parse and merge.** The source's baseline showed `QueryParams("foobar")` had no keys and `https://httpbin.org/get?foobar` merged with `{"hello": "world"}` became only `hello=world`. Compare direct `QueryParams`, `URL.params`, and the final request URL, including an async client if that is the affected path.

2. **Inspect the parsing boundary.** In the recorded snapshot, `QueryParams.__init__` in `httpx/_urls.py` called `urllib.parse.parse_qs(value)` for string or byte input. Local checks showed its default discarded `foobar`, while `keep_blank_values=True` retained `{"foobar": [""]}`. The client merge path was in `httpx/_client.py`. Verify the target version's parser and merge path before attributing loss to either.

3. **Check related inputs.** The local checks covered `a&b&c`, mixed valued and valueless keys, explicit empty values (`a=`), duplicate values, mapping and list inputs, empty input, and overriding an existing key. Confirm both key retention and the intended query encoding; the source's local output serialized bare `foobar` as `foobar=`.

4. **Validate the affected client path.** After the source edit, a direct reproduction and an async-client check retained `foobar` in `https://httpbin.org/get?foobar=&hello=world`. Custom edge-case checks passed. Relevant pytest logs showed passing cases but were truncated, so their complete totals are unavailable from this fixture.

**Result and limits.** The author trajectory is marked `author_resolved: 1`. Local validation supports preservation of the key, while the issue's illustrative expected URL used a bare key and a different ordering; do not infer byte-for-byte URL equality. Source issue `encode__httpx-2354`; trajectory `chatcmpl-72e6e100f8acde0714929179f658626e`; base commit `3eee17e69e43f74df2c9bfaa442da2feac81363c`; fixed fixture revisions: trajectory `35455389ab51bf5e2306bfd436ef72d0f98bf882`, task `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Dataset license: CC-BY-4.0. Original repository license: BSD 3-Clause "New" or "Revised" License.
