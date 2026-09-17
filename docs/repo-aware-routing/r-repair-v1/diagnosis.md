# Legacy R diagnosis (observed development cases)

Baseline source: `d50516b5c0b30d241c25adb001b05e660eb4c122`.
All five legacy routing source hashes in the four real diagnostic outputs were
checked against that commit, before relying on the records. Original results
and weights are untouched. The old code remains available at that commit and
through the unmodified v1 representation/extractor semantics.

| Previously observed family | Raw per-requirement support logit range | Context v1 | Actual action |
|---|---:|---|---|
| delete-transaction | -3.8774 to -2.7911 | incomplete, db.py skipped | N |
| migration-stop-validation | -4.1951 to -2.2923 | incomplete, db.py skipped | N |
| content-key | -3.5112 to -2.2214 | supported | N |
| dotted-columns | -3.3900 to -2.2234 | supported | N |

The complete per-candidate/per-requirement export is
`artifacts/repo-aware-routing-r-repair-v1/legacy-filter-rows.json`; full token IDs,
decoded inputs, candidate conflicts and exact subset outputs are in
`legacy-diagnostic/`. These are actual model forwards, not whole-task proxies.

The legacy support instruction preceding `[TASK]` is removed by four-section
splitting. Independent section caps also waste unused space. Oversized `db.py`
is skipped for byte budget, rather than a missing path or parse error. The two
csv-diff cases show that the skip alone does not explain all fallbacks.

Pairwise loss depends on `z_positive - z_negative`; adding a common constant
leaves that difference fixed but changes each absolute sigmoid and threshold
membership. This mathematical observation is not used to shift actual logits.
New ordinal relevance and separately supervised text support address distinct
semantics. Neither proves better patches.
