# Acceptance semantics posthoc appendix

**16/16 original candidates reconstructed and revalidated; 32 old records
verified and preserved.** All 16 old target/regression results reproduced.
CSV content dimensions pass for all 8; SQLite package dimensions fail for all 8,
while submodule and console dimensions pass. These are different obligations,
not a new four-task success rate or an independent routing gain.

- [Source/visibility and ambiguity matrix](semantics.md)
- [Three result tables and two concrete examples](results.md)
- [Installed commands and recovery](usage.md)
- [Scope and original baseline](scope.md)
- [Frozen inventory](../../../configs/acceptance-semantics-v1/inventory.json)
- [Frozen checker/fixture identity](../../../configs/acceptance-semantics-v1/freeze.json)
- [Actual candidate observations](../../../artifacts/acceptance-semantics-v1/runs.json)
- [Controls](../../../artifacts/acceptance-semantics-v1/validation.json)
- [Recomputed records](../../../artifacts/acceptance-semantics-v1/records.json)
- [Cost boundary](../../../artifacts/acceptance-semantics-v1/cost.json)
- [Bounded independent review](../../../artifacts/acceptance-semantics-v1/review.json)

Human Brief：本轮修正CSV旧前缀要求的解释，并补测真实内容；保留SQLite标题和正文入口歧义。
没有调用新修复Agent、路由模型、训练或校准。旧32格没有改分；另16份没有重验。
原补丁完整保留，所有新结果均为后验；默认仍为native，不宣称support或独立收益。
同一Draft PR #48交付，不合并、不ready、不发布。

Independent review found and closed a host-symlink publication risk and
incomplete runtime/record identity checks before candidate execution. The
reviewer then independently recomputed all public records without executing
candidates or models. This is a model-agent code/evidence review, not human or
blind adjudication and not an arbitrary-malicious-code safety certification.

Validation: 1446 local tests passed; clean installed Git-archive records passed.
Code HEAD `f6d4951f24956b60eacd6489af5e34ee2383e5a0` passed
[CI 35257827222](https://github.com/Raidriar7170/hermes-skilleval/actions/runs/35257827222).
Final documentation HEAD is checked separately in PR48; code-head green is not
used as a substitute. The first CI failures (raw evidence whitespace and Git
empty-directory omission) are retained in history; both were packaging fixes,
with no candidate or acceptance-rule changes.
