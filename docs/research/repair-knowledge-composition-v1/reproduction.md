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
