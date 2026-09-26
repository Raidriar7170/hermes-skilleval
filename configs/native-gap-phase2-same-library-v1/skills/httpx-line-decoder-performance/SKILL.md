---
name: httpx-line-decoder-performance
description: Historical diagnostic reference for slow HTTPX LineDecoder or Response.iter_lines() on chunks containing many lines, especially around the 0.23 source snapshot.
---

# Line decoding performance in HTTPX

Use this optional reference when line iteration is unexpectedly slow on a large text chunk. It documents one public trajectory, not a guaranteed fix. The issue reported a 31 MB chunk with 18,768 lines taking about 1 minute 45 seconds; that figure came from the issue statement, not a local reproduction.

1. **Trace the path.** In the recorded snapshot, `Response.iter_lines()` and `Response.aiter_lines()` were in `httpx/_models.py`, and `LineDecoder.decode()` was in `httpx/_decoders.py`. The decoder's observed loop sliced away a processed prefix after each newline. Inspect the corresponding code in the target version before inferring where time is spent.

2. **Measure representative chunks.** The trajectory compared `LineDecoder` on 1,000, 2,000, 4,000, and 8,000 lines of 100 characters. Before the attempted edit, recorded times were 0.0119, 0.0259, 0.0602, and 0.1624 seconds. Record input size, line count, time, and a same-input `splitlines()` comparison; the figures are environment specific and do not prove a universal complexity bound.

3. **Check line semantics at chunk boundaries.** Cover LF, CR, CRLF, a CR at the end of one chunk followed by LF or another character, empty chunks, and `flush()`. The trajectory's first ad hoc edge-case run reported failures for some trailing-CR expectations even though existing decoder tests passed. Resolve expected behavior against the target version's documented tests before changing it.

4. **Validate any candidate in its own version.** The local trajectory showed 36 decoder tests passing, a selected line-decoder/iteration run with visible passes, and a 1,753,720-character, 18,768-line benchmark taking 0.248 seconds. That benchmark was much smaller than the reported 31 MB input and remained about 47.7 times slower than `splitlines()` in the same run. Some pytest output was truncated.

**Result and limits.** The author trajectory is marked `author_resolved: 0`; its attempted edit is **not a validated fix**, regardless of local passing tests or the script's success wording. Use the observations to design a current-version reproduction and validation, not as a patch recipe. Source issue `encode__httpx-2423`; trajectory `chatcmpl-c14db1332fd751b035c57c4f1a870285`; base commit `e486fbceea7a933baa4b52852681f9c6ac80ac96`; fixed fixture revisions: trajectory `35455389ab51bf5e2306bfd436ef72d0f98bf882`, task `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Dataset license: CC-BY-4.0. Original repository license: BSD 3-Clause "New" or "Revised" License.
