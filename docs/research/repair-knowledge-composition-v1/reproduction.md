# 实际入口

在项目根目录，以 `PYTHONPATH=src /opt/anaconda3/bin/python` 运行。

- `scripts/repair_knowledge_composition/source_pool.py`：公开列注册，禁止读取patch列。
- `prepare_pro.py`：资格准备方下载base、单独存放reference/test patch；公开字符串正确解码。
- `build_corpus.py --base ... --repository ansible/ansible --revision <base> --output ...`：独立源码输入，无题目/答案/模型调用。
- `resolve_selectors.py`、`qualify.py`：解析完整源测试并验证base/reference，失败准备记录保留。
- `freeze.py`：模型身份、源/知识/算法/预算冻结，拒绝替换既有计划。
- `legacy_posthoc.py`：只复验指定六份历史原补丁。

真实研究入口：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.repair_content_study native \
  --plan configs/repair-knowledge-composition-v1/plan.json \
  --tasks ../hermes-repair-knowledge-private/tasks \
  --knowledge ../hermes-repair-knowledge-private/knowledge \
  --skills configs/conditional-applicability-v1/skills \
  --output ../hermes-repair-knowledge-private/study-v1
```

相同参数下 `compose` 额外接收 `--payloads configs/adaptive-skill-intervention-v1/payloads --encoder <冻结MiniLM本地目录>`；`pilot` 执行锁定尾程，`evaluate --phase native|pilot` 在完整相位尝试后才释放功能标签。`confirm-prefix / confirm-compose / confirm` 均检查冻结继续规则。CLI存在不表示该命令已经完成；结果页记录实际执行。

原目录是样本账本，不是可删缓存。存在的研究格不会重新采样，部分中断保持UNKNOWN。临时认证只在私有session-home中复制，进程finally清理，不进入Git；完整第三方源码、权重、私密会话也不提交。

记录导出与复算入口为 `scripts/repair_knowledge_composition/export.py`：`prepare` 导出公开资格与知识，`source-support` 将单元及base身份绑定冻结计划后逐来源行核验，`phase --phase native|pilot|confirm` 导出完成相位，`replay --phase ...` 从已导出的JUnit和选择记录复算。前三类需要 `--private ../hermes-repair-knowledge-private --plan configs/repair-knowledge-composition-v1/plan.json --output artifacts/repair-knowledge-composition-v1`；`replay` 只需要 `--output` 和 `--phase`。

`export.py costs --private ../hermes-repair-knowledge-private --output artifacts/repair-knowledge-composition-v1` 统计所有已预留尝试（含中断与确认前缀），不会把导出操作的零模型调用误当整个研究零调用。token是服务端通知中的观察值，费用未知；离线知识构建原耗时未采集，不能补造。共享在线计时不包含首次编码器加载与旧技能检索的全部开销，成本不用于功能判定。

`report.py --evidence artifacts/repair-knowledge-composition-v1 --plan configs/repair-knowledge-composition-v1/plan.json --output docs/research/repair-knowledge-composition-v1/results.md` 从公开功能记录生成主表与选择函数分解，不重新执行Agent或隐藏验收。
