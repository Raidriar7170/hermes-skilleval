# 一个实际补丁：sqlite-utils #344 / J2 / 第一次

这次执行修复公开的 STRICT 建表请求，结果为限定范围内 `SUCCESS`。它不是上游完整回归结论，也不证明技能导致成功。

同一请求的 N 提供原有十技能目录；F2 提供 `sqlite-ingest`、`sqlite-fulltext`；T2 提供 `systematic-debugging`、`verification-before-completion`；J2 提供 `sqlite-schema`、`tabular-conversion`。所有包正文均按需读取。

J 的实际两轴乘积分别为 0.1800255093 和 0.1105554106，排在十候选前二；第三名为 `verification-before-completion`，0.0816829973。这是程序按冻结分数选出的优先级，不是成功概率，也不是模型给出的自然语言解释。完整 logit 和输入身份见 [selections.json](../../../artifacts/advisory-utility-replay-v1/selections.json)。

事件 `item_1` 记录了独立 `sed` 命令读取挂载的 `sqlite-schema/SKILL.md`，输出与冻结正文片段一致。未观察到另一包的同等强度读取证据。包提供、读取、修复成功是三个不同事实，不能据此连接成因果结论。

[完整原始源码补丁](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-J2-r1.patch) 修改了五个文件：`sqlite_utils/db.py`、`sqlite_utils/cli.py` 和三个测试文件。主要行为是将 `strict` 参数贯穿建表与插入路径、生成 `STRICT` SQL、在严格表中将 FLOAT 映射为 REAL，并增加 CLI 参数与候选自写测试。补丁还处理了 transform 的 STRICT/ANY 保留；这些额外修改不代表外部检查覆盖了全部行为。

控制器保存原始候选，再把同一补丁应用到新的干净 base，并核对重建源码一致。外部固定检查实际通过 **1 个目标测试 + 1 个基本 CRUD 回归测试**；候选自己新增的测试未替代它们。独立只读复核未发现裁判或报告干扰。原始目标环境曾 base-red，可信参考在同一检查下 green；#344 参考是较新版本，未提供给 Agent。

本次 Agent 耗时 359.30 秒。供应方报告累计 input 2,287,704、cached input 2,204,544、output 14,481 tokens；cached input 是独立字段，不能再次加到 input 上当总输入，美元账单未知。J 的加载和四任务统一建议计算另行记账，不能因本次复用缓存而当作免费在线建议。

这条链支持“冻结 J 建议进入真实隔离修复，完整补丁在外部有限检查下通过”。策略是否比 N/T2 更好，要看完整四任务、每臂两次的主表，不能由这个成功例子单独回答。
